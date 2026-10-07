"""Tests for batch collection automation (offline, injected runner)."""
from __future__ import annotations

import json
from pathlib import Path

from aletheia import automation
from aletheia.models import Institution, UniversityBundle
from aletheia.pipeline import slugify
from aletheia.search import Candidate, SearchProvider


class StubProvider(SearchProvider):
    name = "stub"

    def __init__(self, urls: list[str]) -> None:
        self.urls = urls

    def search(self, query: str, max_results: int = 10) -> list[Candidate]:
        return [Candidate(url=u, title="stub", provider=self.name) for u in self.urls]


def _ok_runner(name, provider, cache_dir, target_year, manual):
    b = UniversityBundle(institution=Institution(institution_id=slugify(name), display_name=name))
    log = type("L", (), {"queries": ["q"], "candidates": [], "notes": []})()
    return b, log, "verified"


def _fail_runner(name, provider, cache_dir, target_year, manual):
    raise RuntimeError("boom")


def test_overrides_passed_to_runner(tmp_path: Path):
    seen: dict = {}

    def runner(name, provider, cache_dir, target_year, manual):
        seen[name] = list(manual)
        return _ok_runner(name, provider, cache_dir, target_year, manual)

    ov = tmp_path / "ov.json"
    ov.write_text(json.dumps({"Rice University": ["https://example.edu/rice.pdf"]}), encoding="utf-8")
    automation.run_collection(limit=0, delay=0, cache_dir=tmp_path / "c", out_dir=tmp_path / "o",
                              statuses_path=tmp_path / "s.json", logs_dir=tmp_path / "l",
                              overrides_path=ov, provider=StubProvider([]), run_one_fn=runner,
                              progress=None)
    # limit=0 means full list; check at least Rice got its override
    assert seen.get("Rice University") == ["https://example.edu/rice.pdf"]


def test_resume_skips_verified(tmp_path: Path):
    from aletheia.seed import top_100_us_universities
    calls: list[str] = []

    def runner(name, provider, cache_dir, target_year, manual):
        calls.append(name)
        return _ok_runner(name, provider, cache_dir, target_year, manual)

    st = tmp_path / "s.json"
    st.write_text(json.dumps({top_100_us_universities[0]: "verified"}), encoding="utf-8")
    automation.run_collection(limit=2, delay=0, cache_dir=tmp_path / "c", out_dir=tmp_path / "o2",
                              statuses_path=st, logs_dir=tmp_path / "l2",
                              overrides_path=tmp_path / "missing.json",
                              provider=StubProvider([]), run_one_fn=runner)
    assert top_100_us_universities[0] not in calls
    assert top_100_us_universities[1] in calls


def test_failure_never_verified(tmp_path: Path):
    st = automation.run_collection(limit=1, delay=0, cache_dir=tmp_path / "c", out_dir=tmp_path / "o3",
                                   statuses_path=tmp_path / "s3.json", logs_dir=tmp_path / "l3",
                                   overrides_path=tmp_path / "missing.json",
                                   provider=StubProvider([]), run_one_fn=_fail_runner)
    assert list(st.values()) == ["failed"]
    data = json.loads((tmp_path / "o3" / "completeness.json").read_text(encoding="utf-8"))
    assert data["failed"] == 1 and data["verified"] == 0
