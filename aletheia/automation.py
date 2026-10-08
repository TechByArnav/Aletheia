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
from .search import BingRssProvider, ChainedProvider, DuckDuckGoProvider, SearchProvider
from .seed import starter_list_count, top_100_us_universities


def default_provider() -> SearchProvider:
    return ChainedProvider([DuckDuckGoProvider(), BingRssProvider()])


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
) -> dict[str, str]:
    """Collect over the starter list. Returns {display_name: status}."""
    names = list(top_100_us_universities)
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

    for i, name in enumerate(names):
        if statuses.get(name) == "verified":
            continue  # resumable: only verified work is skipped
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
        except Exception:
            pass
        if progress:
            progress(name, status)
        if delay and i < len(names) - 1:
            time.sleep(delay)

    if bundles:
        export_frontend_datasets(bundles, out_dir)
        rep = completeness_report(statuses)
        (out_dir / "completeness.json").write_text(json.dumps(rep, indent=2), encoding="utf-8")
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
    args = ap.parse_args(argv)
    print(f"starter list entries (computed): {starter_list_count()}")
    statuses = run_collection(
        target_year=args.target_year, limit=args.limit, delay=args.delay,
        cache_dir=Path(args.cache_dir), out_dir=Path(args.out),
        statuses_path=Path(args.statuses), logs_dir=Path(args.logs_dir),
        overrides_path=Path(args.overrides),
        progress=lambda n, s: print(f"{n}: {s}"),
    )
    print(json.dumps(completeness_report(statuses), indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
