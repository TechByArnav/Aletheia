"""Versioned normalized schemas for Aletheia. Schema version: 1.0.0."""
from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any, Literal

from pydantic import BaseModel, Field

from . import SCHEMA_VERSION


def utcnow_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class MissingReason(str, Enum):
    NOT_REPORTED = "not_reported"
    NOT_APPLICABLE = "not_applicable"
    UNREADABLE = "unreadable"
    EXTRACTION_FAILED = "extraction_failed"
    NEEDS_REVIEW = "needs_review"


class C7Rating(str, Enum):
    VERY_IMPORTANT = "Very Important"
    IMPORTANT = "Important"
    CONSIDERED = "Considered"
    NOT_CONSIDERED = "Not Considered"


C7_RATING_ORDER: dict[str, int] = {
    C7Rating.VERY_IMPORTANT.value: 3,
    C7Rating.IMPORTANT.value: 2,
    C7Rating.CONSIDERED.value: 1,
    C7Rating.NOT_CONSIDERED.value: 0,
}


class Provenance(BaseModel):
    source_url: str = ""
    document_hash: str = ""
    page: int | None = None
    bbox: list[float] | None = None
    excerpt: str = ""
    section: str = ""
    raw_value: str = ""
    normalized_value: str = ""
    method: Literal["deterministic", "html", "ocr", "ai_fallback", "manual"] = "deterministic"
    status: Literal["verified", "needs_review", "unreadable", "failed"] = "verified"
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)


class Institution(BaseModel):
    schema_version: str = SCHEMA_VERSION
    institution_id: str
    display_name: str
    campus_scope: str = ""
    is_ambiguous: bool = False
    ambiguity_note: str = ""


class CDSDocument(BaseModel):
    schema_version: str = SCHEMA_VERSION
    doc_id: str
    institution_id: str
    display_name: str = ""
    campus_scope: str = ""
    source_url: str = ""
    source_domain: str = ""
    is_official: bool = False
    is_mirror: bool = False
    file_type: Literal["pdf", "html", "unknown"] = "unknown"
    file_hash: str = ""
    requested_target_year: str = ""  # e.g. "2026" as requested
    reporting_period: str = ""  # e.g. "2025-2026" as printed in CDS
    cohort_year: str = ""  # enrolled cohort, e.g. "Fall 2025"
    policy_term: str = ""  # testing-policy effective term
    publication_date: str = ""
    retrieved_at: str = Field(default_factory=utcnow_iso)
    validation_status: Literal["verified", "partial", "needs_review", "rejected"] = "needs_review"
    validation_notes: list[str] = Field(default_factory=list)


class C7Factor(BaseModel):
    factor_raw: str
    factor_normalized: str
    rating_raw: str = ""
    rating_normalized: str = ""  # one of C7Rating values or MissingReason value
    missing: MissingReason | None = None
    provenance: Provenance = Field(default_factory=Provenance)


class C7Record(BaseModel):
    schema_version: str = SCHEMA_VERSION
    institution_id: str
    display_name: str = ""
    campus_scope: str = ""
    reporting_period: str = ""
    cohort_year: str = ""
    source: Provenance = Field(default_factory=Provenance)
    status: Literal["verified", "partial", "needs_review", "not_available"] = "needs_review"
    factors: list[C7Factor] = Field(default_factory=list)
    updated_at: str = Field(default_factory=utcnow_iso)


class C8Policy(BaseModel):
    item_raw: str
    item_normalized: str
    value_raw: str = ""
    value_normalized: str = ""
    missing: MissingReason | None = None
    provenance: Provenance = Field(default_factory=Provenance)


class C8Record(BaseModel):
    schema_version: str = SCHEMA_VERSION
    institution_id: str
    display_name: str = ""
    reporting_period: str = ""
    policy_term: str = ""
    source: Provenance = Field(default_factory=Provenance)
    status: str = "needs_review"
    policies: list[C8Policy] = Field(default_factory=list)
    notes: str = ""
    updated_at: str = Field(default_factory=utcnow_iso)


class PercentileSet(BaseModel):
    p25: float | None = None
    p50: float | None = None  # never invented; None means not reported
    p75: float | None = None
    missing: MissingReason | None = None


class C9Record(BaseModel):
    schema_version: str = SCHEMA_VERSION
    institution_id: str
    display_name: str = ""
    reporting_period: str = ""
    cohort: str = ""
    source: Provenance = Field(default_factory=Provenance)
    status: str = "needs_review"
    sat_submitters_n: int | None = None
    sat_submitters_pct: float | None = None
    act_submitters_n: int | None = None
    act_submitters_pct: float | None = None
    sat_ebrw: PercentileSet = Field(default_factory=PercentileSet)
    sat_math: PercentileSet = Field(default_factory=PercentileSet)
    sat_composite: PercentileSet = Field(default_factory=PercentileSet)
    act_composite: PercentileSet = Field(default_factory=PercentileSet)
    notes: str = ""
    updated_at: str = Field(default_factory=utcnow_iso)


class C10Record(BaseModel):
    schema_version: str = SCHEMA_VERSION
    institution_id: str
    display_name: str = ""
    reporting_period: str = ""
    cohort: str = ""
    source: Provenance = Field(default_factory=Provenance)
    status: str = "needs_review"
    pct_reporting_rank: float | None = None
    top_tenth_pct: float | None = None
    top_quarter_pct: float | None = None
    top_half_pct: float | None = None
    bottom_half_pct: float | None = None
    bottom_quarter_pct: float | None = None
    notes: str = ""
    updated_at: str = Field(default_factory=utcnow_iso)


class C11Record(BaseModel):
    schema_version: str = SCHEMA_VERSION
    institution_id: str
    display_name: str = ""
    reporting_period: str = ""
    cohort: str = ""
    source: Provenance = Field(default_factory=Provenance)
    status: str = "needs_review"
    gpa_scale: str = ""
    pct_reporting_gpa: float | None = None
    buckets: dict[str, float | None] = Field(default_factory=dict)
    notes: str = ""
    updated_at: str = Field(default_factory=utcnow_iso)


class UniversityBundle(BaseModel):
    institution: Institution
    document: CDSDocument | None = None
    c7: C7Record | None = None
    c8: C8Record | None = None
    c9: C9Record | None = None
    c10: C10Record | None = None
    c11: C11Record | None = None


class DatasetManifest(BaseModel):
    schema_version: str = SCHEMA_VERSION
    generated_at: str = Field(default_factory=utcnow_iso)
    reporting_periods: list[str] = Field(default_factory=list)
    n_institutions: int = 0
    counts: dict[str, Any] = Field(default_factory=dict)
    limitations: list[str] = Field(default_factory=list)
