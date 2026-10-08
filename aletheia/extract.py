"""Deterministic extraction first. Locate by headings, never fixed pages.

Supports: text-native PDFs (pypdf), HTML CDS pages (BeautifulSoup),
table/reordered columns, X/checkmark cells, multi-page C7 tables.
Scanned PDFs without text layer -> UNREADABLE + OCR workflow pointer.
Never infer a rating from mere mention in text.
"""
from __future__ import annotations

import re
from pathlib import Path

from bs4 import BeautifulSoup

from .models import (
    C7Factor, C7Rating, C8Policy, MissingReason, Provenance,
)

C7_EXPECTED_FACTORS = [
    "Rigor of secondary school record", "Class rank", "Academic GPA",
    "Standardized test scores", "Application essay", "Recommendations",
    "Interview", "Extracurricular activities", "Talent/ability",
    "Character/personal qualities", "First-generation status",
    "Alumni relation", "Geographical residence", "State residency",
    "Religious affiliation/commitment", "Volunteer work", "Work experience",
    "Applicant interest",
]

C7_COLUMNS = ["Very Important", "Important", "Considered", "Not Considered"]

CHECK_MARKS = {"x", "X", "✓", "✔", "☑", "■", "●", "*"}


def header_label_to_rating(cell: str) -> str:
    """Exact header-cell match, longest-first. Avoids 'Considered' matching 'Not Considered'."""
    n = _norm(cell)
    for col in sorted(C7_COLUMNS, key=len, reverse=True):
        if n == _norm(col):
            return col
    return ""


def _norm(s: str) -> str:
    return re.sub(r"\s+", " ", (s or "").strip().lower())


def normalize_factor_name(raw: str) -> str:
    n = _norm(raw)
    for known in C7_EXPECTED_FACTORS:
        kn = _norm(known)
        if n == kn or kn in n or n in kn:
            return known
    # Discover new factor rows from CDS version — preserve raw wording.
    return raw.strip()


def normalize_rating(raw: str) -> tuple[str, MissingReason | None]:
    t = (raw or "").strip()
    low = _norm(t)
    mapping = {
        "very important": C7Rating.VERY_IMPORTANT.value,
        "important": C7Rating.IMPORTANT.value,
        "considered": C7Rating.CONSIDERED.value,
        "not considered": C7Rating.NOT_CONSIDERED.value,
    }
    if low in mapping:
        return mapping[low], None
    if low in ("", "n/a", "na", "-", "—", "nr"):
        return MissingReason.NOT_REPORTED.value, MissingReason.NOT_REPORTED
    return MissingReason.NEEDS_REVIEW.value, MissingReason.NEEDS_REVIEW


def extract_text_from_pdf(path: Path) -> tuple[str, int]:
    """Returns (text, n_pages). Empty text => scanned/unreadable."""
    try:
        from pypdf import PdfReader
        reader = PdfReader(str(path))
        parts: list[str] = []
        for i, page in enumerate(reader.pages):
            try:
                parts.append(page.extract_text() or "")
            except Exception:
                parts.append("")
        return "\n\f".join(parts), len(reader.pages)
    except Exception:
        return "", 0


def find_section_span(text: str, start_markers: list[str], end_markers: list[str]) -> str:
    low = text.lower()
    start = -1
    for m in start_markers:
        i = low.find(m.lower())
        if i != -1 and (start == -1 or i < start):
            start = i
    if start == -1:
        return ""
    end = len(text)
    for m in end_markers:
        j = low.find(m.lower(), start + 10)
        if j != -1 and j < end:
            end = j
    return text[start:end]


def extract_c7_from_text(text: str, source_url: str = "", doc_hash: str = "") -> list[C7Factor]:
    """Row-aware C7 parse: each factor line must carry its own mark.

    Accepts lines like:
      'Academic GPA | Very Important | ...' or 'Academic GPA ... X ...'
      'Academic GPA [X] [ ] [ ] [ ]'  (checkbox order VI,I,C,NC)
    A bare mention without a mappable mark -> NEEDS_REVIEW, never inferred.
    """
    span = find_section_span(text, ["C7 ", "C7.", "relative importance"], ["C8 ", "C8.", "C9 "])
    if not span:
        # fall back to whole text but require explicit table header
        span = text
    lines = [ln.strip() for ln in span.splitlines() if ln.strip()]
    # locate header row to learn column order (handles reordered columns)
    col_order = list(C7_COLUMNS)
    for ln in lines[:80]:
        if "very important" in ln.lower() and "not considered" in ln.lower():
            # Prefer pipe-split cells for exact header mapping; fall back to position search.
            if "|" in ln:
                cells = [c.strip() for c in ln.split("|")]
                mapped = [header_label_to_rating(c) for c in cells]
                mapped = [m for m in mapped if m]
                if mapped:
                    col_order = mapped
                    break
            order: list[str] = []
            # longest-first so 'Very Important' wins over 'Important' substring
            for c in sorted(C7_COLUMNS, key=len, reverse=True):
                idx = ln.lower().find(c.lower())
                if idx != -1:
                    # avoid double-counting 'Important' inside 'Very Important'
                    if c == "Important" and "Very Important" in ln and idx > 0:
                        continue
                    if c == "Considered" and "Not Considered" in ln:
                        # find standalone 'Considered' occurrence, not inside 'Not Considered'
                        tmp = ln.lower().replace("not considered", " " * len("not considered"))
                        idx2 = tmp.find(c.lower())
                        if idx2 == -1:
                            continue
                        idx = idx2
                    order.append((idx, c))
            if order:
                col_order = [c for _, c in sorted(order)]
            break
    factors: list[C7Factor] = []
    for ln in lines:
        for known in C7_EXPECTED_FACTORS:
            if _norm(known) in _norm(ln) or _norm(ln).startswith(_norm(known)[:12]):
                # find explicit rating token in same line
                rating_raw = ""
                # 1) pipe-delimited table: 'Factor | X | | |' with known col_order
                if "|" in ln:
                    cells = [c.strip() for c in ln.split("|")]
                    # first cell is factor label; remaining map to col_order
                    for i, cell in enumerate(cells[1:]):
                        if cell.strip() in CHECK_MARKS or cell.strip().lower() == "x":
                            if i < len(col_order):
                                rating_raw = col_order[i]
                            break
                # 2) explicit rating words, longest-first exact containment
                if not rating_raw:
                    for c in sorted(C7_COLUMNS, key=len, reverse=True):
                        # word-boundary style containment to avoid substring collisions
                        if re.search(r"(?<!not\s)" + re.escape(c) if c in ("Considered", "Important") else re.escape(c), ln, re.I):
                            # verify it is not just the header row itself
                            if _norm(known) in _norm(ln):
                                # header row has all four ratings; skip if line looks like header
                                if all(h.lower() in ln.lower() for h in ("Very Important", "Not Considered")):
                                    break
                            rating_raw = c
                            break
                boxes = re.findall(r"\[(X|✓|x| |)\]", ln)
                if not rating_raw and boxes:
                    try:
                        idx = next(i for i, b in enumerate(boxes) if b.strip().lower() in ("x", "✓"))
                        rating_raw = col_order[idx] if idx < len(col_order) else ""
                    except StopIteration:
                        rating_raw = ""
                if not rating_raw:
                    # X-count fallback: 'Academic GPA .... X' with column positions unknown -> review
                    if re.search(r"(?<!\w)[Xx✓✔](?!\w)", ln):
                        rating_raw = ""  # ambiguous position
                norm, missing = normalize_rating(rating_raw) if rating_raw else (MissingReason.NEEDS_REVIEW.value, MissingReason.NEEDS_REVIEW)
                prov = Provenance(source_url=source_url, document_hash=doc_hash, section="C7",
                                  raw_value=rating_raw, normalized_value=norm,
                                  excerpt=ln[:400], method="deterministic",
                                  status="verified" if not missing else "needs_review",
                                  confidence=0.9 if not missing else 0.4)
                factors.append(C7Factor(factor_raw=known, factor_normalized=normalize_factor_name(known),
                                        rating_raw=rating_raw, rating_normalized=norm, missing=missing, provenance=prov))
                break
    # de-duplicate preserving first
    seen: dict[str, C7Factor] = {}
    for f in factors:
        seen.setdefault(f.factor_normalized, f)
    return list(seen.values())


def extract_c7_from_html(html: str, source_url: str = "", doc_hash: str = "") -> list[C7Factor]:
    soup = BeautifulSoup(html, "html.parser")
    tables = soup.find_all("table")
    out: list[C7Factor] = []
    for tbl in tables:
        text = tbl.get_text(" ", strip=True)
        if "Very Important" not in text or "Not Considered" not in text:
            continue
        rows = tbl.find_all("tr")
        header_idx: dict[int, str] = {}
        for row in rows:
            cells = [c.get_text(" ", strip=True) for c in row.find_all(["th", "td"])]
            if any("Very Important" in c for c in cells):
                for i, c in enumerate(cells):
                    rated = header_label_to_rating(c)
                    if rated:
                        header_idx[i] = rated
                continue
            if not header_idx:
                continue
            label = cells[0] if cells else ""
            if not label or len(label) < 3:
                continue
            rating_raw = ""
            for i, cell in enumerate(cells[1:], start=1):
                mark = cell.strip()
                if mark in CHECK_MARKS or mark.lower() == "x" or "checked" in mark.lower():
                    rating_raw = header_idx.get(i, "")
                    break
                # checkbox input elements
                if row.find("input", {"checked": True}) is not None:
                    pass
            norm_name = normalize_factor_name(label)
            if norm_name:
                norm, missing = normalize_rating(rating_raw) if rating_raw else (MissingReason.NEEDS_REVIEW.value, MissingReason.NEEDS_REVIEW)
                out.append(C7Factor(factor_raw=label, factor_normalized=norm_name, rating_raw=rating_raw,
                                    rating_normalized=norm, missing=missing,
                                    provenance=Provenance(source_url=source_url, document_hash=doc_hash,
                                                          section="C7", raw_value=rating_raw, normalized_value=norm,
                                                          excerpt=text[:300], method="html",
                                                          status="verified" if not missing else "needs_review",
                                                          confidence=0.9 if not missing else 0.4)))
    return out


def extract_c8_policies_from_text(text: str, source_url: str = "", doc_hash: str = "") -> list[C8Policy]:
    span = find_section_span(text, ["C8 ", "C8.", "admission requirements"], ["C9 ", "C9."])
    if not span:
        return []
    out: list[C8Policy] = []
    for ln in span.splitlines():
        l = ln.strip()
        if len(l) < 8:
            continue
        if re.search(r"SAT|ACT|test|score|require|optional|blind|flexible|consider", l, re.I):
            out.append(C8Policy(item_raw=l[:160], item_normalized="testing policy note",
                                value_raw=l[:300], value_normalized=l[:300],
                                provenance=Provenance(source_url=source_url, document_hash=doc_hash,
                                                      section="C8", raw_value=l[:200], normalized_value=l[:200],
                                                      excerpt=l[:400], method="deterministic",
                                                      status="needs_review", confidence=0.5)))
        if len(out) >= 20:
            break
    return out


NUM = r"(\d{1,3}(?:,\d{3})*|\d+(?:\.\d+)?)"


def _num(s: str) -> float | None:
    try:
        return float(s.replace(",", "").replace("%", ""))
    except Exception:
        return None


def extract_c9_from_text(text: str, source_url: str = "", doc_hash: str = "") -> dict:
    span = find_section_span(text, ["C9 ", "C9.", "test scores"], ["C10 ", "C10."])
    if not span:
        return {}
    out: dict = {}
    # generic percentile lines: 'SAT EBRW 25th 680 75th 760'.
    # Strip ordinal markers first so '25th' is not parsed as a score.
    for label, key in [("EBRW", "sat_ebrw"), ("Math", "sat_math"), ("Composite", "sat_composite"), ("ACT", "act_composite")]:
        line = next((ln for ln in span.splitlines() if label.lower() in ln.lower() and re.search(r"\d{2,4}", ln)), "")
        if not line:
            continue
        cleaned = re.sub(r"\b(25th|75th|25th percentile|75th percentile)\b", " ", line, flags=re.I)
        nums = re.findall(NUM, cleaned)
        vals = [_num(n) for n in nums if _num(n) is not None]
        # SAT section scores live in 200-800; filter out stray counts/years.
        if "sat" in key:
            vals = [v for v in vals if 200 <= v <= 800]
        else:
            vals = [v for v in vals if 1 <= v <= 36]
        if len(vals) >= 2:
            out[key] = {"p25": vals[0], "p75": vals[1]}
    pct = re.search(r"(\d{1,3}(?:\.\d+)?)\s*%.*(?:SAT|submit)", span, re.I)
    if pct:
        out["sat_submitters_pct"] = _num(pct.group(1))
    return out
