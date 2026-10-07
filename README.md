# Aletheia — Common Data Set Comparison

Aletheia (ah-lay-TAY-ah; Greek ἀλήθεια: truth as disclosure) compares university
Common Data Sets with source traceability: admissions factors (C7) and
testing/academic profiles (C8–C11).

- Starter institution list is **user-provided, not a verified ranking**.
- First search result is a **candidate, never proof** — identity, campus,
  CDS content, and reporting period are validated.
- Missing values are explicit (`not_reported`, `not_applicable`, `unreadable`,
  `extraction_failed`, `needs_review`) — never zero, never “Not Considered.”
- Static frontend works on GitHub Pages with **no backend**. Python runs
  locally / in a manual data-refresh workflow.

## Quick start

```bash
# Python pipeline
pip install -e ".[pdf,test]"
python -m pytest tests -q
python -m aletheia.golden

# Scan one university (local; unauthenticated search, manual override supported)
aletheia scan-one --university "Rice University" --target-year 2026
aletheia scan-one --university "City University of New York" --source-url "https://.../baruch-cds.pdf"

# Batch automation: full starter list (or --limit N), resumable, per-university logs
# Overrides (reviewed official URLs) live in data/overrides.json
aletheia collect --target-year 2026 --limit 10 --delay 2.0
aletheia collect --target-year 2026 --limit 0  # full list

# Frontend
cd frontend && npm install && npm run build
```

## Docs

- `IMPLEMENTATION.md` — architecture, commands, deployment
- `docs/SCHEMA.md` — versioned dataset schema
- `docs/METHODOLOGY.md` — extraction + validation method
- `designs.md` — visual source of truth (Raycast midnight reference)

## License

Choose before publication (e.g. MIT / Apache-2.0 / CC-BY-4.0 for data docs).
No license is assumed here.
