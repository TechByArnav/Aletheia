# Schema v1.0.0

`aletheia/models.py` is canonical. Key rules:

- Every record: `institution_id`, `display_name`, `campus/scope`, `reporting_period`, cohort/policy terms where relevant, provenance, status, `updated_at`, `schema_version`.
- C7 ratings preserved verbatim: Very Important / Important / Considered / Not Considered. Ordinal; gaps not equal; no percentage weights.
- Missing enum: `not_reported`, `not_applicable`, `unreadable`, `extraction_failed`, `needs_review`. Raw wording preserved alongside normalized.
- C8: policy notes + effective term. C9: submitter n/%, percentiles (p25/p75 only; p50 only if printed — never derived), scales separate, submitter shares may overlap. C10: rank + reporting coverage. C11: GPA buckets + scale + coverage. C10/C11 are not examinations.
- Provenance per field: source_url, document_hash, page, bbox, excerpt, section, raw, normalized, method (deterministic/html/ocr/ai_fallback/manual), status, confidence. Low-confidence → review queue.
- Frontend files: `universities.json` (list of `UniversityBundle`), `manifest.json`, `completeness.json` (batch only).
