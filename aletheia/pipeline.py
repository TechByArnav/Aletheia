"""Collection + canonical extraction pipeline (local / CI, never on Pages)."""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from . import SCHEMA_VERSION
from .download import ValidationResult, detect_reporting_period, download_with_retries, safe_filename, validate_candidate
from .extract import (
    extract_c7_from_html, extract_c7_from_text, extract_c8_policies_from_text,
    extract_c9_from_text, extract_text_from_pdf,
)
from .models import (
    C7Record, C8Record, C9Record, C10Record, C11Record, CDSDocument,
    DatasetManifest, Institution, MissingReason, PercentileSet, Provenance,
    UniversityBundle,
)
from .search import Candidate, DiscoveryLog, SearchProvider, build_queries
from .seed import ambiguity_note


def slugify(name: str) -> str:
    import re
    s = re.sub(r"[^A-Za-z0-9]+", "-", name).strip("-").lower()
    return s[:80] or "institution"


STATUS_ORDER = ["found", "downloaded", "parsed", "verified", "partial", "needs_review", "not_available", "failed"]


def _url_score(url: str) -> int:
    """Pre-download ranking: official PDF-looking URLs first, junk last."""
    low = url.lower()
    s = 0
    if low.endswith(".pdf"):
        s += 3
    if ".edu" in low:
        s += 2
    if "common-data-set" in low or "commondataset" in low or "/cds" in low:
        s += 2
    return s


def _validation_score(url: str, validation: ValidationResult, n_c7: int) -> int:
    s = _url_score(url)
    if validation.file_type == "pdf":
        s += 3
    elif validation.file_type == "html":
        s += 1
    else:
        s -= 5
    if validation.is_official_hint:
        s += 2
    for n in validation.notes:
        if "tokens not found" in n:
            s -= 3
        if "Phrase 'Common Data Set' not found" in n:
            s -= 3
        if "too small" in n:
            s -= 5
    if validation.reporting_period:
        s += 1
    s += min(n_c7, 6)
    return s


def _extract_c7_count(text: str, ftype: str, url: str, h: str) -> int:
    try:
        if ftype == "html":
            return len(extract_c7_from_html(text, url, h))
        return len(extract_c7_from_text(text, url, h))
    except Exception:
        return 0


def _readable_text(data: bytes, ftype: str, cache_dir: Path, inst_id: str) -> str:
    if ftype == "pdf":
        tmp = cache_dir / f"{inst_id}.pdf"
        try:
            tmp.write_bytes(data)
            text, _ = extract_text_from_pdf(tmp)
            return text
        except Exception:
            return ""
    return data.decode("utf-8", errors="ignore")


def run_one(display_name: str, provider: SearchProvider, cache_dir: Path, target_year: str = "2026",
            manual_urls: list[str] | None = None, campus_scope: str = "") -> tuple[UniversityBundle, DiscoveryLog, str]:
    """Discover -> download -> validate -> extract. Never marks failed/unverified as processed."""
    from .search import ManualProvider
    log = DiscoveryLog(display_name=display_name)
    queries = build_queries(display_name, target_year)
    log.queries = queries
    candidates: list[Candidate] = []
    if manual_urls:
        candidates.extend(ManualProvider(manual_urls).search(queries[0]))
    for q in queries[:4]:
        try:
            got = provider.search(q, max_results=6)
        except Exception:
            got = []
        for c in got:
            if c.url not in {x.url for x in candidates}:
                candidates.append(c)
    # Manual overrides first, then URL-ranked (official PDFs before junk).
    manual_set = set(manual_urls or [])
    candidates.sort(key=lambda c: (c.url not in manual_set, -_url_score(c.url)))
    log.candidates = candidates
    inst_id = slugify(display_name)
    amb = ambiguity_note(display_name)
    inst = Institution(institution_id=inst_id, display_name=display_name, campus_scope=campus_scope,
                       is_ambiguous=bool(amb and "System entry" in amb), ambiguity_note=amb or "")
    bundle = UniversityBundle(institution=inst)
    if not candidates:
        log.notes.append("No candidates found.")
        return bundle, log, "not_available"
    # Best-pick: try ranked candidates (bounded), keep the highest score.
    # Never stops at the first junk page.
    best: tuple[int, Candidate, bytes, str, ValidationResult] | None = None
    for cand in candidates[:8]:
        dest = cache_dir / f"{inst_id}__{safe_filename(cand.url[-60:])}.bin"
        try:
            if dest.exists() and dest.stat().st_size > 5000:
                data = dest.read_bytes()
                ctype = ""
            else:
                data, ctype = download_with_retries(cand.url, dest)
        except Exception as e:  # noqa: BLE001
            log.notes.append(f"Candidate failed: {cand.url} ({e})")
            continue
        validation = validate_candidate(display_name, cand.url, data, ctype, target_year)
        text = _readable_text(data, validation.file_type, cache_dir, inst_id)
        n_c7 = _extract_c7_count(text, validation.file_type, cand.url, validation.file_hash)
        score = _validation_score(cand.url, validation, n_c7)
        if best is None or score > best[0]:
            best = (score, cand, data, ctype, validation)
        if score >= 10:
            break
    if best is None:
        log.notes.append("All candidates unavailable.")
        return bundle, log, "failed"
    _, chosen, data, ctype, validation = best
    doc = CDSDocument(doc_id=f"{inst_id}--{validation.file_hash[:10]}", institution_id=inst_id,
                      display_name=display_name, campus_scope=campus_scope, source_url=chosen.url,
                      source_domain=validation.domain, is_official=validation.is_official_hint,
                      is_mirror=not validation.is_official_hint, file_type=validation.file_type,  # type: ignore
                      file_hash=validation.file_hash, requested_target_year=target_year,
                      reporting_period=validation.reporting_period, retrieved_at=datetime.now(timezone.utc).isoformat(),
                      validation_status="needs_review", validation_notes=validation.notes)
    bundle.document = doc
    # Extraction
    text = ""
    tmp_pdf: Path | None = None
    if validation.file_type == "pdf":
        tmp = cache_dir / f"{inst_id}.pdf"
        tmp.write_bytes(data)
        tmp_pdf = tmp
        text, _ = extract_text_from_pdf(tmp)
        if not text.strip():
            doc.validation_notes.append("Scanned PDF without text layer: marked UNREADABLE; use local OCR workflow.")
            doc.validation_status = "needs_review"
            return bundle, log, "needs_review"
    else:
        text = data.decode("utf-8", errors="ignore")
    # Prefer extracted text (not raw bytes) for identity/content/period checks:
    # publisher PDFs compress their streams, so raw heads are unreadable.
    text_head = text[:20000].lower()
    text_confirmed = False
    if "common data set" in text_head:
        doc.validation_notes.append("Confirmed: phrase 'Common Data Set' present in extracted text.")
        text_confirmed = True
    else:
        doc.validation_notes.append("Phrase 'Common Data Set' not found in extracted text; sections may be absent.")
    text_period = detect_reporting_period(text[:20000] + " " + chosen.url)
    if text_period and text_period != validation.reporting_period:
        doc.validation_notes.append(
            f"Reporting period from extracted text is '{text_period}' (download check said '{validation.reporting_period}').")
        validation.reporting_period = text_period
        doc.reporting_period = text_period
    if validation.file_type == "html":
        c7factors = extract_c7_from_html(text, chosen.url, validation.file_hash)
    else:
        c7factors = extract_c7_from_text(text, chosen.url, validation.file_hash)
        if tmp_pdf is not None:
            try:
                from .extract import extract_c7_positional
                positional = extract_c7_positional(tmp_pdf, chosen.url, validation.file_hash)
            except Exception:
                positional = []
            if positional:
                by_name = {f.factor_normalized: f for f in c7factors}
                for pf in positional:
                    cur = by_name.get(pf.factor_normalized)
                    if cur is None or cur.missing is not None:
                        by_name[pf.factor_normalized] = pf
                c7factors = list(by_name.values())
                doc.validation_notes.append(
                    f"Positional C7 parse mapped {len(positional)} factor rows by mark coordinates.")
    c8pols = extract_c8_policies_from_text(text, chosen.url, validation.file_hash)
    c9d = extract_c9_from_text(text, chosen.url, validation.file_hash)
    prov = Provenance(source_url=chosen.url, document_hash=validation.file_hash, section="C",
                      method="html" if validation.file_type == "html" else "deterministic",
                      status="needs_review", confidence=0.6)
    bundle.c7 = C7Record(institution_id=inst_id, display_name=display_name, campus_scope=campus_scope,
                         reporting_period=validation.reporting_period, source=prov,
                         status="needs_review" if c7factors else "not_available", factors=c7factors)
    bundle.c8 = C8Record(institution_id=inst_id, display_name=display_name, reporting_period=validation.reporting_period,
                         source=prov, status="needs_review" if c8pols else "not_available", policies=c8pols)
    c9 = C9Record(institution_id=inst_id, display_name=display_name, reporting_period=validation.reporting_period, source=prov,
                  status="needs_review" if c9d else "not_available")
    for k in ("sat_ebrw", "sat_math", "sat_composite", "act_composite"):
        if k in c9d:
            setattr(c9, k, PercentileSet(**c9d[k]))
    if "sat_submitters_pct" in c9d:
        c9.sat_submitters_pct = c9d["sat_submitters_pct"]
    bundle.c9 = c9
    bundle.c10 = C10Record(institution_id=inst_id, display_name=display_name, reporting_period=validation.reporting_period, source=prov)
    bundle.c11 = C11Record(institution_id=inst_id, display_name=display_name, reporting_period=validation.reporting_period, source=prov)
    identity_ok = validation.ok or text_confirmed
    # Raw-byte head notes are superseded once extracted text confirms the
    # document; only ambiguous-identity notes still block verification.
    ambiguous = any("Ambiguous identity" in n for n in validation.notes)
    verified = bool(c7factors) and identity_ok and not ambiguous
    doc.validation_status = "verified" if verified else ("partial" if c7factors else "needs_review")
    for f in bundle.c7.factors:
        if f.missing == MissingReason.NEEDS_REVIEW:
            doc.validation_status = "needs_review"
            break
    status = doc.validation_status
    log.notes.extend(validation.notes)
    return bundle, log, status


def export_frontend_datasets(bundles: list[UniversityBundle], out_dir: Path) -> DatasetManifest:
    out_dir.mkdir(parents=True, exist_ok=True)
    data = [b.model_dump() for b in bundles]
    (out_dir / "universities.json").write_text(json.dumps(data, indent=2), encoding="utf-8")
    periods = sorted({b.document.reporting_period for b in bundles if b.document and b.document.reporting_period})
    counts: dict[str, int] = {"total": len(bundles)}
    for key in ("verified", "partial", "needs_review", "not_available", "failed"):
        counts[key] = sum(1 for b in bundles if b.document and b.document.validation_status == key)
    manifest = DatasetManifest(reporting_periods=periods, n_institutions=len(bundles), counts=counts,
                               limitations=[
                                   "Starter list is user-provided, not a verified ranking.",
                                   "Mixed reporting periods are labeled; disable mixed-year comparison in UI when strict.",
                                   "System entries (Minnesota, CUNY) require reviewed campus mapping.",
                                   "Missing values are never zero; see schema docs.",
                               ])
    (out_dir / "manifest.json").write_text(manifest.model_dump_json(indent=2), encoding="utf-8")
    return manifest


def completeness_report(statuses: dict[str, str]) -> dict[str, int]:
    from collections import Counter
    c = Counter(statuses.values())
    return {k: c.get(k, 0) for k in STATUS_ORDER}
