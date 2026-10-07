# Methodology

1. Discover via replaceable provider (default unauthenticated DDG HTML). Manual URLs override.
2. Download with timeouts, ≤3 retries + exponential backoff, ≤5 redirects, 25MB cap, SHA-256, safe filenames, `data/cache`, resumable batch.
3. Validate: institution/campus tokens, “Common Data Set” presence, period detection (filename year is not evidence), file signature, domain (.edu preferred; mirrors labeled), size sanity. Ambiguous systems flagged.
4. Extract deterministically: locate C7/C8/C9/C10/C11 by headings; map checkmarks by table coordinates/HTML relations (handles reordered columns, multi-page); never infer rating from mention. Scanned PDFs → `unreadable` + OCR pointer (local: e.g. `ocrmypdf` then re-scan; browser: warning + local workflow).
5. Normalize with Pydantic v1.0.0; missing stays missing; review queue for low-confidence/conflicts.
6. Export static JSON; frontend shows provenance, mixed-year labels, coverage n; groups explain unweighted vs student-weighted (latter only with compatible denominators).
7. AI (optional, unimplemented baseline): fallback only, schema-constrained, excerpt-grounded, validated, consent-gated, no secrets in bundles. Baseline works with no keys.

Limitations: unauthenticated search may block; layouts vary; OCR imperfect; policy term ≠ cohort year; test-submitter stats ≠ all enrollees; GPA scales vary.
