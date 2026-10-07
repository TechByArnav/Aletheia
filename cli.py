"""CLI: scan one university or the starter list, review, export."""
from __future__ import annotations

import json
from pathlib import Path

import click

from .pipeline import completeness_report, export_frontend_datasets, run_one
from .search import DuckDuckGoProvider
from .seed import starter_list_count, top_100_us_universities


@click.group()
def cli() -> None:
    pass


@cli.command()
@click.option("--university", required=True, help="Display name, e.g. 'Rice University'")
@click.option("--target-year", default="2026", show_default=True)
@click.option("--cache-dir", default="data/cache")
@click.option("--out", default="frontend/public/data")
@click.option("--source-url", multiple=True, help="Manual override URL(s)")
def scan_one(university: str, target_year: str, cache_dir: str, out: str, source_url: tuple[str, ...]) -> None:
    bundle, log, status = run_one(university, DuckDuckGoProvider(), Path(cache_dir), target_year, list(source_url))
    click.echo(f"status={status} candidates={len(log.candidates)}")
    for n in log.notes:
        click.echo(f" - {n}")
    export_frontend_datasets([bundle], Path(out))
    click.echo(f"exported 1 bundle to {out}")


@cli.command()
@click.option("--target-year", default="2026", show_default=True)
@click.option("--cache-dir", default="data/cache")
@click.option("--out", default="frontend/public/data")
@click.option("--limit", type=int, default=0, help="0 = full starter list")
@click.option("--resume", default="", help="Path to prior statuses json for resumable scans")
def scan_batch(target_year: str, cache_dir: str, out: str, limit: int, resume: str) -> None:
    names = list(top_100_us_universities)
    click.echo(f"starter list entries (computed, not assumed): {starter_list_count()}")
    if limit:
        names = names[:limit]
    prior: dict[str, str] = {}
    if resume and Path(resume).exists():
        prior = json.loads(Path(resume).read_text(encoding="utf-8"))
    provider = DuckDuckGoProvider()
    bundles = []
    statuses: dict[str, str] = dict(prior)
    for name in names:
        if name in statuses and statuses[name] in ("verified",):
            continue  # resumable
        bundle, log, status = run_one(name, provider, Path(cache_dir), target_year)
        bundles.append(bundle)
        statuses[name] = status
        click.echo(f"{name}: {status}")
    export_frontend_datasets(bundles, Path(out))
    rep = completeness_report(statuses)
    Path(out, "completeness.json").write_text(json.dumps(rep, indent=2), encoding="utf-8")
    click.echo(json.dumps(rep, indent=2))


@cli.command()
@click.argument("bundles_json")
def review(bundles_json: str) -> None:
    """List fields flagged needs_review."""
    data = json.loads(Path(bundles_json).read_text(encoding="utf-8"))
    for b in data:
        c7 = b.get("c7") or {}
        for f in c7.get("factors", []):
            if f.get("missing") == "needs_review":
                click.echo(f"{b['institution']['display_name']} C7 {f['factor_normalized']} NEEDS_REVIEW: {f['provenance']['excerpt'][:80]}")


def main() -> None:
    cli()


if __name__ == "__main__":
    main()
