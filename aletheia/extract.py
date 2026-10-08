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


# ---------------------------------------------------------------------------
# Positional C7 extraction (real CDS PDFs).
#
# Many publishers' C7 tables extract as "FactorName X" with a single trailing
# X per line — the rating lives only in the mark's *horizontal position*.
# Line-based parsing cannot map those, so we cluster mark x-coordinates into
# columns and assign each factor row's mark to its nearest column.
# ---------------------------------------------------------------------------

MARK_CHARS = {"x", "X", "\u2713", "\u2714", "\u2611", "\u2612"}
# Note: "\u2610" (empty ballot box = unchecked) is deliberately NOT a mark.


def cluster_xs(xs: list[float], tol: float = 14.0) -> list[float]:
    """Group nearby x-centers; returns sorted cluster centers."""
    centers: list[float] = []
    for x in sorted(xs):
        if centers and abs(x - centers[-1]) <= tol:
            centers[-1] = (centers[-1] + x) / 2
        else:
            centers.append(x)
    return centers


def assign_c7_marks(rows: list[dict], clusters: list[float], col_order: list[str], tol: float = 14.0) -> dict[str, str]:
    """Map factor rows to ratings by nearest mark column. Pure function.

    rows: [{"text": factor label, "mark_x": x-center of the row's single mark}]
    Returns {factor text: rating}; rows whose mark fits no column are skipped
    (caller marks them needs_review — never inferred).
    """
    out: dict[str, str] = {}
    for row in rows:
        best_i: int | None = None
        best_d = tol
        for i, c in enumerate(clusters):
            d = abs(row["mark_x"] - c)
            if d <= best_d:
                best_d = d
                best_i = i
        if best_i is not None and best_i < len(col_order):
            out[row["text"]] = col_order[best_i]
    return out


def _factor_tokens(name: str) -> list[str]:
    toks = re.sub(r"[^a-z0-9 ]", " ", name.lower()).split()
    return [t for t in toks if len(t) > 3 and t not in ("with", "from")]


def _match_factors(text: str) -> list[tuple[str, int]]:
    """Token-overlap factor matching tolerant of CDS wording variants.

    Handles 'Alumni/ae relation', 'First generation' (vs 'First-generation
    status'), 'Recommendation(s)', curly apostrophes. Returns
    [(factor, hits)] sorted by hits desc. Single-token factors need 1 hit,
    others need >= 2 (avoids 'Class rank' matching rank-talk elsewhere).
    """
    toks = set(re.sub(r"[^a-z0-9 ]", " ", text.lower()).split())
    out: list[tuple[str, int]] = []
    for known in C7_EXPECTED_FACTORS:
        sig = _factor_tokens(known)
        if not sig:
            continue
        hits = 0
        for k in sig:
            if k in toks or (k.endswith("s") and k[:-1] in toks):
                hits += 1
        need = 1 if len(sig) <= 1 else 2
        if hits >= need:
            out.append((known, hits))
    out.sort(key=lambda p: -p[1])
    return out


def _header_anchors(header_words: list[dict]) -> list[tuple[float, str]] | None:
    """Column anchors from a C7 header row: [(x-center, rating)] sorted by x.

    Needs all four labels; handles the wrapped 'Not \\n Considered'.
    Returns None when the header is unusable (caller falls back to clusters).
    """
    vi_x: list[float] = []
    imp: list[float] = []
    conss: list[float] = []
    nots: list[float] = []
    for i, w in enumerate(header_words):
        t = w["text"].strip()
        if t == "Very" and i + 1 < len(header_words) and header_words[i + 1]["text"].strip() == "Important":
            vi_x.append((w["xc"] + header_words[i + 1]["xc"]) / 2)
        elif t == "Important":
            if i == 0 or header_words[i - 1]["text"].strip() != "Very":
                imp.append(w["xc"])
        elif t == "Considered":
            conss.append(w["xc"])
        elif t == "Not":
            nots.append(w["xc"])
    if not (vi_x and imp and conss and nots):
        return None
    # Pair leftmost Not with nearest Considered → the wrapped 4th column.
    pair = min(conss, key=lambda c: abs(c - nots[0]))
    rest = [c for c in conss if c != pair]
    if not rest:
        return None
    cols = [(vi_x[0], C7Rating.VERY_IMPORTANT.value), (imp[0], C7Rating.IMPORTANT.value),
            (rest[0], C7Rating.CONSIDERED.value), ((nots[0] + pair) / 2, "Not Considered")]
    cols.sort(key=lambda c: c[0])
    return cols


def extract_c7_positional(pdf_path: str | Path, source_url: str = "", doc_hash: str = "") -> list[C7Factor]:
    """Coordinate-based C7 parse for real publisher PDFs. Requires pdfplumber.

    Returns [] when pdfplumber is unavailable or no mappable table is found.
    Every returned factor had exactly one mark in exactly one column;
    ambiguous rows are omitted here (line parser flags them needs_review).
    """
    try:
        import pdfplumber
    except Exception:
        return []
    try:
        doc = pdfplumber.open(str(pdf_path))
    except Exception:
        return []
    try:
        page_texts: list[str] = []
        pages_words: list[list[dict]] = []
        for pdf_page in doc.pages:
            try:
                words = pdf_page.extract_words() or []
            except Exception:
                words = []
            pages_words.append(words)
            page_texts.append(" ".join(w.get("text", "") for w in words))
        # C7 page range: heading to next C8 heading.
        start = end = -1
        for i, t in enumerate(page_texts):
            low = t.lower()
            if start == -1 and ("relative importance" in low or ("c7" in low and "very important" in low)):
                start = i
            if start != -1 and i > start and ("c8" in low and ("sat and act" in low or "c8a" in low)):
                end = i
                break
        if start == -1:
            return []
        if end == -1:
            end = min(start + 3, len(pages_words) - 1)
        # Group words into visual rows: single-linkage on top with a 3px
        # gap. (Coarse rounding splits factor text from its own mark when
        # they sit <1px apart, e.g. tops 314.7 vs 315.2.)
        rows: list[dict] = []
        for pno in range(start, end + 1):
            ws = sorted(pages_words[pno], key=lambda w: (float(w.get("top", 0)), float(w.get("x0", 0))))
            cur: list[dict] = []
            last_top: float | None = None
            for w in ws:
                try:
                    t = float(w.get("top", 0))
                except Exception:
                    continue
                if cur and last_top is not None and t - last_top > 3.0:
                    ws_sorted = sorted(cur, key=lambda v: float(v.get("x0", 0)))
                    rows.append({"words": ws_sorted,
                                 "text": " ".join(str(v.get("text", "")) for v in ws_sorted),
                                 "page": pno})
                    cur = []
                cur.append(w)
                last_top = t
            if cur:
                ws_sorted = sorted(cur, key=lambda v: float(v.get("x0", 0)))
                rows.append({"words": ws_sorted,
                             "text": " ".join(str(v.get("text", "")) for v in ws_sorted),
                             "page": pno})
        # Header anchors for column geometry (works even when a rating
        # column received zero marks). Falls back to mark clusters.
        anchors: list[tuple[float, str]] | None = None
        for row in rows:
            low = row["text"].lower()
            if "very important" in low and "consider" in low:
                words = [{"text": str(w.get("text", "")), "xc": (float(w.get("x0", 0)) + float(w.get("x1", 0))) / 2}
                         for w in row["words"]]
                anchors = _header_anchors(words)
                break
        # Logical lines: accumulate wrapped rows until a row carries a mark.
        # Header rows reset the accumulator so intro text never merges in.
        logical: list[dict] = []
        pending: list[dict] = []
        for row in rows:
            low = row["text"].lower()
            words = row["words"]
            if "very important" in low and "not considered" in low:
                # Header row: drop accumulated intro text, but keep any
                # factor content sharing the row (strip label words only).
                label = {"academic", "nonacademic", "very", "important", "considered", "not"}
                words = [w for w in words if str(w.get("text", "")).strip().lower() not in label]
                if not words:
                    pending = []
                    continue
                row = {"words": words,
                       "text": " ".join(str(w.get("text", "")) for w in words),
                       "page": row["page"]}
                pending = []
            pending.append(row)
            marks = [w for w in row["words"] if str(w.get("text", "")).strip() in MARK_CHARS]
            if marks:
                merged_words = [w for r in pending for w in r["words"]]
                merged_text = " ".join(r["text"] for r in pending)
                logical.append({"text": merged_text, "words": merged_words, "page": pending[-1]["page"]})
                pending = []
            elif len(pending) > 3:
                pending = pending[-3:]
        # Match factor rows: known factor + exactly one mark. A merged line
        # can hold two factor names (tight rows): assign the mark to the
        # factor whose words sit vertically nearest the mark.
        marked_rows: list[dict] = []
        for line in logical:
            matches = _match_factors(line["text"])
            if not matches:
                continue
            marks = [w for w in line["words"] if str(w.get("text", "")).strip() in MARK_CHARS]
            if len(marks) != 1:
                continue
            m = marks[0]
            try:
                xc = (float(m.get("x0", 0)) + float(m.get("x1", 0))) / 2
                top = float(m.get("top", 0))
                bot = float(m.get("bottom", top + 10))
                mark_mid = (top + bot) / 2
            except Exception:
                continue
            factor = matches[0][0]
            if len(matches) > 1:
                # The mark belongs to the factor whose name-words sit
                # vertically nearest the mark (tight visual rows merge).
                try:
                    mark_mid = (float(m.get("top", 0)) + float(m.get("bottom", mark_mid))) / 2
                except Exception:
                    mark_mid = None
                best_c, best_d = factor, float("inf")
                for c, _ in matches[:3]:
                    ys: list[float] = []
                    for w in line["words"]:
                        wt = str(w.get("text", "")).lower()
                        if any(k in wt or wt in k for k in _factor_tokens(c) if len(k) > 4):
                            try:
                                ys.append((float(w.get("top", 0)) + float(w.get("bottom", 0))) / 2)
                            except Exception:
                                pass
                    if ys and mark_mid is not None:
                        d = abs(sum(ys) / len(ys) - mark_mid)
                        if d < best_d:
                            best_d, best_c = d, c
                factor = best_c
            marked_rows.append({"factor": factor, "mark_x": xc, "page": line["page"],
                               "bbox": [float(m.get("x0", 0)), top, float(m.get("x1", xc)), bot],
                               "excerpt": line["text"][:300]})
        if not marked_rows:
            return []
        if anchors and len(anchors) == 4:
            out: list[C7Factor] = []
            for r in marked_rows:
                ax, rating = min(anchors, key=lambda a: abs(a[0] - r["mark_x"]))
                if abs(ax - r["mark_x"]) > 40.0:
                    continue  # mark fits no column: refuse, don't guess
                out.append(C7Factor(
                    factor_raw=r["factor"], factor_normalized=normalize_factor_name(r["factor"]),
                    rating_raw=rating, rating_normalized=rating, missing=None,
                    provenance=Provenance(source_url=source_url, document_hash=doc_hash,
                                          page=r["page"], bbox=r["bbox"], section="C7",
                                          raw_value="X", normalized_value=rating,
                                          excerpt=r["excerpt"], method="deterministic",
                                          status="verified", confidence=0.85)))
            seen: dict[str, C7Factor] = {}
            for f in out:
                seen.setdefault(f.factor_normalized, f)
            return list(seen.values())
        xs = [r["mark_x"] for r in marked_rows]
        clusters = cluster_xs(xs)
        if len(clusters) != 4:
            # Adjacent sections can leak stray marks in: keep the 4 columns
            # holding the most marks (the C7 table dominates). Refuse only
            # when no clear 4-column geometry exists.
            from collections import Counter
            counts: Counter[int] = Counter()
            for x in xs:
                for i, c in enumerate(clusters):
                    if abs(x - c) <= 14.0:
                        counts[i] += 1
                        break
            top = [clusters[i] for i, _ in counts.most_common(4)]
            if len(top) != 4 or sum(counts[i] for i, _ in counts.most_common(4)) < 0.8 * len(xs):
                return []
            clusters = sorted(top)
        col_order = [r for _, r in anchors] if anchors else list(C7_COLUMNS)
        assigned = assign_c7_marks(
            [{"text": r["factor"], "mark_x": r["mark_x"]} for r in marked_rows],
            clusters, col_order)
        out: list[C7Factor] = []
        for r in marked_rows:
            rating = assigned.get(r["factor"])
            if not rating:
                continue
            out.append(C7Factor(
                factor_raw=r["factor"], factor_normalized=normalize_factor_name(r["factor"]),
                rating_raw=rating, rating_normalized=rating, missing=None,
                provenance=Provenance(source_url=source_url, document_hash=doc_hash,
                                      page=r["page"], bbox=r["bbox"], section="C7",
                                      raw_value="X", normalized_value=rating,
                                      excerpt=r["excerpt"], method="deterministic",
                                      status="verified", confidence=0.85)))
        seen: dict[str, C7Factor] = {}
        for f in out:
            seen.setdefault(f.factor_normalized, f)
        return list(seen.values())
    finally:
        try:
            doc.close()
        except Exception:
            pass
