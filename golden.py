"""Reviewed golden dataset — synthetic, multi-layout. Never scraped data."""
from __future__ import annotations

import json
from pathlib import Path

from .extract import extract_c7_from_html, extract_c7_from_text, extract_c9_from_text
from .models import (
    C7Record, C8Record, C9Record, C10Record, C11Record, CDSDocument,
    Institution, PercentileSet, Provenance, UniversityBundle,
)


def _prov(url: str, section: str) -> Provenance:
    return Provenance(source_url=url, document_hash="golden-fixture",
                      section=section, method="deterministic", status="verified", confidence=0.95)


def build_golden() -> list[UniversityBundle]:
    out: list[UniversityBundle] = []
    # 1. Text-native PDF layout
    t1 = Path("tests/fixtures/c7_text_native.txt").read_text(encoding="utf-8")
    f1 = extract_c7_from_text(t1, "https://example.edu/cds-mit.pdf", "golden-fixture")
    c9d = extract_c9_from_text(t1)
    inst = Institution(institution_id="example-institute-technology", display_name="Example Institute of Technology",
                       campus_scope="Main campus")
    doc = CDSDocument(doc_id="example-institute-technology--golden1", institution_id=inst.institution_id,
                      display_name=inst.display_name, source_url="https://example.edu/cds-mit.pdf",
                      source_domain="example.edu", is_official=True, file_type="pdf",
                      file_hash="golden-fixture", requested_target_year="2026",
                      reporting_period="2025-2026", cohort_year="Fall 2025", policy_term="Fall 2026",
                      validation_status="verified")
    c9 = C9Record(institution_id=inst.institution_id, display_name=inst.display_name,
                  reporting_period="2025-2026", cohort="Fall 2025",
                  source=_prov(doc.source_url, "C9"), status="verified",
                  sat_submitters_pct=c9d.get("sat_submitters_pct"))
    for k in ("sat_ebrw", "sat_math"):
        if k in c9d:
            setattr(c9, k, PercentileSet(**c9d[k]))
    out.append(UniversityBundle(
        institution=inst, document=doc,
        c7=C7Record(institution_id=inst.institution_id, display_name=inst.display_name,
                    reporting_period="2025-2026", source=_prov(doc.source_url, "C7"),
                    status="verified", factors=f1),
        c8=C8Record(institution_id=inst.institution_id, display_name=inst.display_name,
                    reporting_period="2025-2026", policy_term="Fall 2026",
                    source=_prov(doc.source_url, "C8"), status="verified",
                    notes="Test-optional for Fall 2026."),
        c9=c9,
        c10=C10Record(institution_id=inst.institution_id, display_name=inst.display_name,
                      reporting_period="2025-2026", cohort="Fall 2025",
                      source=_prov(doc.source_url, "C10"), status="verified",
                      pct_reporting_rank=78.0, top_tenth_pct=62.0, top_quarter_pct=88.0),
        c11=C11Record(institution_id=inst.institution_id, display_name=inst.display_name,
                      reporting_period="2025-2026", cohort="Fall 2025",
                      source=_prov(doc.source_url, "C11"), status="verified",
                      gpa_scale="4.0", pct_reporting_gpa=99.0,
                      buckets={"4.0": 42.0, "3.75-3.99": 31.0, "3.50-3.74": 15.0}),
    ))
    # 2. Reordered-column HTML layout
    html = Path("tests/fixtures/c7_reordered.html").read_text(encoding="utf-8")
    f2 = extract_c7_from_html(html, "https://example.edu/cds-lakeside.html", "golden-fixture")
    inst2 = Institution(institution_id="lakeside-college", display_name="Lakeside College")
    doc2 = CDSDocument(doc_id="lakeside-college--golden2", institution_id=inst2.institution_id,
                       display_name=inst2.display_name, source_url="https://example.edu/cds-lakeside.html",
                       source_domain="example.edu", is_official=True, file_type="html",
                       file_hash="golden-fixture", requested_target_year="2026",
                       reporting_period="2025-2026", validation_status="verified")
    out.append(UniversityBundle(
        institution=inst2, document=doc2,
        c7=C7Record(institution_id=inst2.institution_id, display_name=inst2.display_name,
                    reporting_period="2025-2026", source=_prov(doc2.source_url, "C7"),
                    status="verified", factors=f2),
        c8=C8Record(institution_id=inst2.institution_id, display_name=inst2.display_name,
                    reporting_period="2025-2026", source=_prov(doc2.source_url, "C8"), status="partial"),
        c9=C9Record(institution_id=inst2.institution_id, display_name=inst2.display_name,
                    reporting_period="2025-2026", source=_prov(doc2.source_url, "C9"), status="not_available"),
        c10=C10Record(institution_id=inst2.institution_id, display_name=inst2.display_name,
                      reporting_period="2025-2026", source=_prov(doc2.source_url, "C10"), status="not_available"),
        c11=C11Record(institution_id=inst2.institution_id, display_name=inst2.display_name,
                      reporting_period="2025-2026", source=_prov(doc2.source_url, "C11"), status="not_available"),
    ))
    # 3. Scanned PDF — needs review / OCR path
    inst3 = Institution(institution_id="harbor-state-university", display_name="Harbor State University")
    doc3 = CDSDocument(doc_id="harbor-state-university--golden3", institution_id=inst3.institution_id,
                       display_name=inst3.display_name, source_url="https://example.edu/harbor-cds.pdf",
                       source_domain="example.edu", is_official=True, file_type="pdf",
                       file_hash="golden-fixture", requested_target_year="2026",
                       reporting_period="2025-2026", validation_status="needs_review",
                       validation_notes=["Scanned PDF without text layer: use local OCR workflow."])
    out.append(UniversityBundle(
        institution=inst3, document=doc3,
        c7=C7Record(institution_id=inst3.institution_id, display_name=inst3.display_name,
                    reporting_period="2025-2026", source=_prov(doc3.source_url, "C7"), status="needs_review"),
    ))
    # 4. Ambiguous system entry — needs clarification
    inst4 = Institution(institution_id="city-university-of-new-york", display_name="City University of New York",
                        is_ambiguous=True,
                        ambiguity_note="System entry: requires reviewed college mapping; not silently substituted.")
    doc4 = CDSDocument(doc_id="city-university-of-new-york--golden4", institution_id=inst4.institution_id,
                       display_name=inst4.display_name, source_url="",
                       source_domain="", file_type="unknown", file_hash="",
                       requested_target_year="2026", reporting_period="",
                       validation_status="needs_review",
                       validation_notes=["System entry: choose a specific college CDS via manual override."])
    out.append(UniversityBundle(institution=inst4, document=doc4))
    return out


def main() -> None:
    from .pipeline import export_frontend_datasets
    bundles = build_golden()
    for d in ("frontend/public/data", "data/golden"):
        m = export_frontend_datasets(bundles, Path(d))
        print(f"wrote {len(bundles)} bundles to {d} periods={m.reporting_periods}")


if __name__ == "__main__":
    main()
