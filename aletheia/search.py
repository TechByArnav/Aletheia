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

    @property
    def available(self) -> bool:
        return True

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


class BingRssProvider(SearchProvider):
    """Unauthenticated Bing RSS endpoint. Best-effort, no key required.

    Limits: may rate-limit/block automation; markup is unofficial and can
    change; never bypass CAPTCHAs / auth walls.
    """

    name = "bing-rss"

    def __init__(self, timeout: int = 15) -> None:
        self.timeout = timeout

    def search(self, query: str, max_results: int = 10) -> list[Candidate]:
        from xml.etree import ElementTree as ET

        url = f"https://www.bing.com/search?format=rss&q={quote_plus(query)}"
        try:
            r = requests.get(url, headers={"User-Agent": "Mozilla/5.0 Aletheia/0.1"}, timeout=self.timeout)
            r.raise_for_status()
        except Exception:
            return []
        try:
            root = ET.fromstring(r.content)
        except Exception:
            return []
        out: list[Candidate] = []
        for i, item in enumerate(root.iter("item")):
            link = item.findtext("link") or ""
            title = item.findtext("title") or ""
            if link.startswith("http"):
                out.append(Candidate(url=link, title=title.strip(), rank=i, provider=self.name))
            if len(out) >= max_results:
                break
        return out


class ChainedProvider(SearchProvider):
    """Try providers in order, deduplicate URLs. First hit wins per query."""

    name = "chained"

    def __init__(self, providers: list[SearchProvider]) -> None:
        self.providers = providers

    def search(self, query: str, max_results: int = 10) -> list[Candidate]:
        seen: set[str] = set()
        out: list[Candidate] = []
        for p in self.providers:
            if not p.available:
                continue
            try:
                got = p.search(query, max_results=max_results)
            except Exception:
                continue
            for c in got:
                if c.url not in seen:
                    seen.add(c.url)
                    out.append(c)
                if len(out) >= max_results:
                    return out
            if out:
                break
        return out


class GoogleCSEProvider(SearchProvider):
    """Google Custom Search JSON API. Opt-in only — needs a key.

    Reads GOOGLE_CSE_KEY and GOOGLE_CSE_CX from the environment. When absent
    the provider reports unavailable and the chain skips it, so the baseline
    keeps working with no keys. Free tier is ~100 queries/day: use with
    --only-missing / small --limit slices, not full bulk runs.
    Never scrape Google HTML: it blocks automation and we do not bypass
    CAPTCHAs or access restrictions.
    """

    name = "google-cse"

    def __init__(self, timeout: int = 15, key: str = "", cx: str = "") -> None:
        import os

        self.timeout = timeout
        self.key = key or os.environ.get("GOOGLE_CSE_KEY", "")
        self.cx = cx or os.environ.get("GOOGLE_CSE_CX", "")

    @property
    def available(self) -> bool:
        return bool(self.key and self.cx)

    def search(self, query: str, max_results: int = 10) -> list[Candidate]:
        if not self.available:
            return []
        try:
            r = requests.get(
                "https://www.googleapis.com/customsearch/v1",
                params={"key": self.key, "cx": self.cx, "q": query, "num": min(max_results, 10)},
                timeout=self.timeout,
            )
            r.raise_for_status()
            items = r.json().get("items", [])
        except Exception:
            return []
        return [Candidate(url=i.get("link", ""), title=i.get("title", ""), snippet=i.get("snippet", ""),
                          rank=n, provider=self.name)
                for n, i in enumerate(items) if (i.get("link") or "").startswith("http")][:max_results]


class ManualProvider(SearchProvider):
    """Manual URL overrides supplied by user / reviewed mapping."""

    name = "manual"

    def __init__(self, urls: list[str]) -> None:
        self.urls = urls

    def search(self, query: str, max_results: int = 10) -> list[Candidate]:
        return [Candidate(url=u, title="manual override", rank=i, provider=self.name) for i, u in enumerate(self.urls[:max_results])]


def build_queries(display_name: str, target_year: str = "2026") -> list[str]:
    # Operator-free first (Bing RSS ignores filetype:/site: and returns junk
    # when given operators). A filename containing the year never proves the
    # reporting period — validated later.
    return [
        f"{display_name} {target_year} Common Data Set pdf",
        f"{display_name} Common Data Set 2025-2026",
        f"{display_name} common data set site:edu",
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
