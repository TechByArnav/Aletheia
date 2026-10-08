"""Batch collection automation — no manual per-university searching.

Runs the full starter list (or a slice) through discovery → download →
validate → extract → export, with:

- provider chain (manual overrides first, then unauthenticated DDG HTML +
  Bing RSS — both best-effort, no keys, documented limits)
- conservative sequential pacing with configurable delay (no parallel
  hammering of university sites)
- resumable statuses (only ``verified`` is skipped on resume)
- per-university JSON logs
- honest statuses: failed / unverified downloads are never marked processed

Usage:
    python -m aletheia.automation --target-year 2026 --limit 10
    aletheia collect --target-year 2026 --limit 0 --delay 2.0
"""
from __future__ import annotations

import argparse
import json
import time
from pathlib import Path
from typing import Callable

from .pipeline import completeness_report, export_frontend_datasets, run_one, slugify
from .search import BingRssProvider, ChainedProvider, DuckDuckGoProvider, GoogleCSEProvider, SearchProvider
from .seed import starter_list_count, top_100_us_universities


def default_provider(timeout: int = 10) -> SearchProvider:
    chain: list[SearchProvider] = []
    google = GoogleCSEProvider(timeout=timeout)
    if google.available:
        chain.append(google)  # best recall when a (free-tier) key is configured
    chain += [DuckDuckGoProvider(timeout=timeout), BingRssProvider(timeout=timeout)]
    return ChainedProvider(chain)


def active_providers(provider: SearchProvider) -> list[str]:
    from .search import ChainedProvider as _C
    if isinstance(provider, _C):
        return [p.name for p in provider.providers if p.available]
    return [provider.name] if provider.available else []


def _safe(s: str) -> str:
    return s.encode("ascii", "replace").decode()


def load_overrides(path: Path) -> dict[str, list[str]]:
    if not path.exists():
        return {}
    data = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(data, dict):
        return {k: (v if isinstance(v, list) else [v]) for k, v in data.items()}
    return {}


def run_collection(
    target_year: str = "2026",
    limit: int = 0,
    delay: float = 2.0,
    cache_dir: Path = Path("data/cache"),
    out_dir: Path = Path("frontend/public/data"),
    statuses_path: Path = Path("data/statuses.json"),
    logs_dir: Path = Path("data/logs"),
    overrides_path: Path = Path("data/overrides.json"),
    provider: SearchProvider | None = None,
    run_one_fn: Callable | None = None,
    progress: Callable[[str, str], None] | None = None,
    recheck: bool = False,
    offset: int = 0,
    only_missing: bool = False,
) -> dict[str, str]:
    """Collect over the starter list. Returns {display_name: status}."""
    names = list(top_100_us_universities)[offset:]
    if only_missing:
        # Retry universities whose exported bundle has no C7 factors yet.
        have: set[str] = set()
        existing_file = out_dir / "universities.json"
        if existing_file.exists():
            try:
                for b in json.loads(existing_file.read_text(encoding="utf-8")):
                    if (b.get("c7") or {}).get("factors"):
                        have.add(b["institution"]["display_name"])
            except Exception:
                pass
        names = [n for n in names if n not in have]
    if limit and limit > 0:
        names = names[:limit]
    provider = provider or default_provider()
    run = run_one_fn or run_one
    overrides = load_overrides(overrides_path)

    statuses: dict[str, str] = {}
    if statuses_path.exists():
        try:
            statuses = json.loads(statuses_path.read_text(encoding="utf-8"))
        except Exception:
            statuses = {}
    bundles = []
    logs_dir.mkdir(parents=True, exist_ok=True)
    statuses_path.parent.mkdir(parents=True, exist_ok=True)

    def _export() -> None:
        # Merge with previously exported bundles so interrupted/resumed runs
        # keep earlier work instead of replacing the dataset with one slice.
        # Synthetic golden fixtures (example.edu) never ship in app data.
        SYNTHETIC_IDS = {"example-institute-technology", "lakeside-college", "harbor-state-university"}
        merged: dict[str, dict] = {}
        existing = out_dir / "universities.json"
        if existing.exists():
            try:
                for b in json.loads(existing.read_text(encoding="utf-8")):
                    if b["institution"]["institution_id"] not in SYNTHETIC_IDS:
                        merged[b["institution"]["institution_id"]] = b
            except Exception:
                pass
        for b in bundles:
            merged[b.institution.institution_id] = b.model_dump()
        out_dir.mkdir(parents=True, exist_ok=True)
        (out_dir / "universities.json").write_text(json.dumps(list(merged.values()), indent=2), encoding="utf-8")
        from .models import DatasetManifest

        periods = sorted({(b.get("document") or {}).get("reporting_period", "") for b in merged.values()} - {""})
        manifest = DatasetManifest(reporting_periods=periods, n_institutions=len(merged),
                                   counts=completeness_report(statuses),
                                   limitations=[
                                       "Starter list is user-provided, not a verified ranking.",
                                       "Mixed reporting periods are labeled; disable mixed-year comparison in UI when strict.",
                                       "System entries (Minnesota, CUNY) require reviewed campus mapping.",
                                       "Missing values are never zero; see schema docs.",
                                   ])
        (out_dir / "manifest.json").write_text(manifest.model_dump_json(indent=2), encoding="utf-8")
        (out_dir / "completeness.json").write_text(json.dumps(completeness_report(statuses), indent=2), encoding="utf-8")

    for i, name in enumerate(names):
        if not recheck and statuses.get(name) in ("verified", "partial", "needs_review", "failed", "not_available"):
            continue  # resumable: redo only with recheck=True
        manual = overrides.get(name, [])
        try:
            bundle, log, status = run(name, provider, cache_dir, target_year, manual)
        except Exception as e:  # noqa: BLE001 — never crash the batch
            from .models import UniversityBundle
            from .seed import ambiguity_note
            from .models import Institution

            amb = ambiguity_note(name)
            bundle = UniversityBundle(
                institution=Institution(institution_id=slugify(name), display_name=name,
                                        is_ambiguous=bool(amb and "System entry" in amb),
                                        ambiguity_note=amb or "")
            )
            log = type("L", (), {"queries": [], "candidates": [], "notes": [f"runner error: {e}"]})()
            status = "failed"
        bundles.append(bundle)
        statuses[name] = status
        try:
            (logs_dir / f"{slugify(name)}.json").write_text(
                json.dumps({"display_name": name, "status": status,
                            "queries": getattr(log, "queries", []),
                            "candidates": [{"url": c.url, "provider": c.provider} for c in getattr(log, "candidates", [])],
                            "notes": getattr(log, "notes", [])}, indent=2),
                encoding="utf-8",
            )
            statuses_path.write_text(json.dumps(statuses, indent=2), encoding="utf-8")
            _export()
        except Exception:
            pass
        if progress:
            progress(_safe(name), status)
        if delay and i < len(names) - 1:
            time.sleep(delay)

    if bundles:
        _export()
    return statuses


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Aletheia batch collection automation")
    ap.add_argument("--target-year", default="2026")
    ap.add_argument("--limit", type=int, default=0, help="0 = full starter list")
    ap.add_argument("--delay", type=float, default=2.0, help="seconds between universities")
    ap.add_argument("--cache-dir", default="data/cache")
    ap.add_argument("--out", default="frontend/public/data")
    ap.add_argument("--statuses", default="data/statuses.json")
    ap.add_argument("--logs-dir", default="data/logs")
    ap.add_argument("--overrides", default="data/overrides.json")
    ap.add_argument("--recheck", action="store_true", help="redo already-recorded universities")
    ap.add_argument("--offset", type=int, default=0, help="skip first N starter-list entries")
    ap.add_argument("--only-missing", action="store_true", help="retry only universities with no C7 factors yet")
    args = ap.parse_args(argv)
    print(f"starter list entries (computed): {starter_list_count()}")
    print(f"search providers: {active_providers(default_provider())} (google-cse needs GOOGLE_CSE_KEY + GOOGLE_CSE_CX)")
    statuses = run_collection(
        target_year=args.target_year, limit=args.limit, delay=args.delay,
        cache_dir=Path(args.cache_dir), out_dir=Path(args.out),
        statuses_path=Path(args.statuses), logs_dir=Path(args.logs_dir),
        overrides_path=Path(args.overrides), recheck=args.recheck, offset=args.offset,
        only_missing=args.only_missing,
        progress=lambda n, s: print(f"{_safe(n)}: {s}"),
    )
    print(json.dumps(completeness_report(statuses), indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
