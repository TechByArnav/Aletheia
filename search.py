"""Replaceable search-provider interface.

Default: unauthenticated DuckDuckGo HTML (no API key). Documented limits:
- May rate-limit or block automated queries; HTML layout changes without notice.
- Not guaranteed available indefinitely.
- Never bypass CAPTCHAs / auth walls.
- Manual source overrides always supported.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from urllib.parse import quote_plus

import requests
from bs4 import BeautifulSoup


@dataclass
class Candidate:
    url: str
    title: str = ""
    snippet: str = ""
    rank: int = 0
    provider: str = ""


class SearchProvider:
    name: str = "base"

    def search(self, query: str, max_results: int = 10) -> list[Candidate]:
        raise NotImplementedError


class DuckDuckGoProvider(SearchProvider):
    """Unauthenticated HTML endpoint. Best-effort, no key required."""

    name = "duckduckgo-html"

    def __init__(self, timeout: int = 15) -> None:
        self.timeout = timeout

    def search(self, query: str, max_results: int = 10) -> list[Candidate]:
        url = f"https://html.duckduckgo.com/html/?q={quote_plus(query)}"
        try:
            r = requests.get(url, headers={"User-Agent": "Mozilla/5.0 Aletheia/0.1"}, timeout=self.timeout)
            r.raise_for_status()
        except Exception:
            return []
        soup = BeautifulSoup(r.text, "html.parser")
        out: list[Candidate] = []
        for i, a in enumerate(soup.select("a.result__a")):
            href = a.get("href", "")
            if href and href.startswith("http"):
                out.append(Candidate(url=href, title=a.get_text(strip=True), rank=i, provider=self.name))
            if len(out) >= max_results:
                break
        return out


class ManualProvider(SearchProvider):
    """Manual URL overrides supplied by user / reviewed mapping."""

    name = "manual"

    def __init__(self, urls: list[str]) -> None:
        self.urls = urls

    def search(self, query: str, max_results: int = 10) -> list[Candidate]:
        return [Candidate(url=u, title="manual override", rank=i, provider=self.name) for i, u in enumerate(self.urls[:max_results])]


def build_queries(display_name: str, target_year: str = "2026") -> list[str]:
    # Requested query first, then targeted fallbacks. A filename containing
    # the year never proves the reporting period — validated later.
    return [
        f"{display_name} {target_year} Common Data Set filetype:pdf",
        f"{display_name} Common Data Set 2025-2026",
        f"{display_name} Common Data Set 2026-2027",
        f"{display_name} institutional research common data set",
        f"{display_name} CDS archive site:edu",
    ]


@dataclass
class DiscoveryLog:
    display_name: str
    queries: list[str] = field(default_factory=list)
    candidates: list[Candidate] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)
