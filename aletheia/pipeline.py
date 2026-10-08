"""Collection + canonical extraction pipeline (local / CI, never on Pages)."""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from . import SCHEMA_VERSION
from .download import ValidationResult, download_with_retries, safe_filename, validate_candidate
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
    for q in queries[:3]:
        try:
            got = provider.search(q, max_results=6)
        except Exception:
            got = []
        for c in got:
            if c.url not in {x.url for x in candidates}:
                candidates.append(c)
        if candidates:
            break
    log.candidates = candidates
    inst_id = slugify(display_name)
    amb = ambiguity_note(display_name)
    inst = Institution(institution_id=inst_id, display_name=display_name, campus_scope=campus_scope,
                       is_ambiguous=bool(amb and "System entry" in amb), ambiguity_note=amb or "")
    bundle = UniversityBundle(institution=inst)
    if not candidates:
        log.notes.append("No candidates found.")
        return bundle, log, "not_available"
    data: bytes | None = None
    ctype = ""
    chosen: Candidate | None = None
    validation: ValidationResult | None = None
    for cand in candidates:  # first candidate is tried first, never auto-trusted
        dest = cache_dir / f"{inst_id}__{safe_filename(cand.url[-60:])}.bin"
        try:
            data, ctype = download_with_retries(cand.url, dest)
        except Exception as e:  # noqa: BLE001
            log.notes.append(f"Candidate failed: {cand.url} ({e})")
            continue
        validation = validate_candidate(display_name, cand.url, data, ctype, target_year)
        chosen = cand
        if validation.ok or validation.file_type in ("pdf", "html"):
            break
    if not chosen or data is None or validation is None:
        log.notes.append("All candidates unavailable.")
        return bundle, log, "failed"
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
    if validation.file_type == "pdf":
        tmp = cache_dir / f"{inst_id}.pdf"
        tmp.write_bytes(data)
        text, _ = extract_text_from_pdf(tmp)
        if not text.strip():
            doc.validation_notes.append("Scanned PDF without text layer: marked UNREADABLE; use local OCR workflow.")
            doc.validation_status = "needs_review"
            return bundle, log, "needs_review"
    else:
        text = data.decode("utf-8", errors="ignore")
    c7factors = extract_c7_from_html(text, chosen.url, validation.file_hash) if validation.file_type == "html" else extract_c7_from_text(text, chosen.url, validation.file_hash)
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
    verified = bool(c7factors) and validation.ok and not any("needs review" in n for n in validation.notes)
    doc.validation_status = "verified" if verified else ("partial" if c7factors else "needs_review")
    for f in bundle.c7.factors:
        if f.missing == MissingReason.NEEDS_REVIEW:
            doc.validation_status = "needs_review"
            break
    status = "verified" if doc.validation_status == "verified" else ("partial" if c7factors else "needs_review")
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
