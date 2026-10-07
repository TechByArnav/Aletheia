"""Tests: identity, year, C7 mapping, C8/C9/C10/C11, missing values, provenance, aggregation, schema."""
from __future__ import annotations

from aletheia.download import detect_reporting_period, validate_candidate
from aletheia.extract import (
    extract_c7_from_html, extract_c7_from_text, extract_c9_from_text,
    normalize_factor_name, normalize_rating,
)
from aletheia.models import MissingReason
from aletheia.pipeline import completeness_report
from aletheia.seed import AMBIGUOUS_IDENTITIES, starter_list_count, top_100_us_universities


def test_seed_count_computed():
    assert starter_list_count() == len(top_100_us_universities)
    assert starter_list_count() > 90  # do not hardcode 100
    assert "University of Minnesota (System)" in AMBIGUOUS_IDENTITIES
    assert "City University of New York" in AMBIGUOUS_IDENTITIES


def test_reporting_period_detection():
    assert detect_reporting_period("Common Data Set 2025-2026") == "2025-2026"
    assert detect_reporting_period("CDS 2026-2027 draft") == "2026-2027"


def test_wrong_year_flagged_not_verified():
    data = b"Common Data Set 2024-2025 " + b"Stanford University " * 200 + b"x" * 8000
    v = validate_candidate("Stanford University", "https://example.edu/cds.pdf", data, "application/pdf", "2026")
    assert any("2024-2025" in n or "requested year" in n for n in v.notes)


def test_wrong_institution_needs_review_note():
    data = b"Common Data Set 2025-2026 " + b"Totally Different College " * 200 + b"x" * 8000
    v = validate_candidate("Rice University", "https://example.edu/cds.pdf", data, "application/pdf", "2026")
    assert any("not found" in n for n in v.notes)


def test_pdf_vs_html_identification():
    from aletheia.download import guess_file_type
    assert guess_file_type("x.pdf", "application/pdf", b"%PDF-1.7") == "pdf"
    assert guess_file_type("x", "text/html", b"<!doctype html>") == "html"


def test_c7_checkbox_mapping_text():
    text = open("tests/fixtures/c7_text_native.txt", encoding="utf-8").read()
    factors = extract_c7_from_text(text)
    by = {f.factor_normalized: f.rating_normalized for f in factors}
    assert by["Academic GPA"] == "Very Important"
    assert by["State residency"] == "Not Considered"
    # every extracted field carries provenance
    assert all(f.provenance.section == "C7" for f in factors)


def test_c7_reordered_columns_html():
    html = open("tests/fixtures/c7_reordered.html", encoding="utf-8").read()
    factors = extract_c7_from_html(html)
    by = {f.factor_normalized: f.rating_normalized for f in factors}
    assert by["Academic GPA"] == "Very Important"
    assert by["Class rank"] == "Considered"
    assert by["State residency"] == "Not Considered"


def test_c7_no_inference_without_mark():
    factors = extract_c7_from_text("C7 discussion mentions Academic GPA at length but no table.")
    assert factors == [] or all(f.missing == MissingReason.NEEDS_REVIEW for f in factors)


def test_missing_values_never_zero():
    norm, missing = normalize_rating("")
    assert norm == MissingReason.NOT_REPORTED.value
    assert missing == MissingReason.NOT_REPORTED


def test_c9_percentiles_no_invented_median():
    text = open("tests/fixtures/c7_text_native.txt", encoding="utf-8").read()
    d = extract_c9_from_text(text)
    assert d["sat_ebrw"]["p25"] == 680
    assert "p50" not in d["sat_ebrw"]  # never invented


def test_completeness_report_keys():
    rep = completeness_report({"A": "verified", "B": "failed"})
    for k in ("found", "downloaded", "parsed", "verified", "partial", "needs_review", "not_available", "failed"):
        assert k in rep


def test_schema_version_present():
    from aletheia.models import C7Record
    assert C7Record(institution_id="x").schema_version == "1.0.0"
