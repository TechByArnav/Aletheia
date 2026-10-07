# Aletheia — Implementation

## 1. Available files
- `designs.md`: copied verbatim from `DESIGN (2).md` (Raycast midnight command-center, coral neon). Visual source of truth.
- `C:\Python\CDS Project` was empty; all files below are new except `designs.md`.
- Name: **Aletheia**, slug `aletheia`, applied to title, nav, metadata, package names, README/docs.

## 2. Architecture
- Python package `aletheia/`: `seed` (exact starter list + `starter_list_count()`), `models` (pydantic, schema v1.0.0), `search` (replaceable provider), `download` (timeouts, retries/backoff, size/redirect limits, hashing, safe filenames, cache, resumable), `extract` (deterministic first: pypdf + BeautifulSoup; heading-located sections; checkbox-column mapping), `pipeline` (discover→validate→extract→export), `cli` (`scan-one`, `scan-batch`, `review`), `golden` (reviewed synthetic fixtures).
- Frontend `frontend/` (React + TS + Vite, HashRouter, recharts): routes `/` landing, `/admissions` C7, `/profile` C8–C11, `/u/:id` detail, `/import` review, `/methodology`. Static JSON in `public/data/`. Groups + local imports in localStorage.
- No live Python server required for browsing. Optional local API intentionally omitted from baseline (documented; static + CLI cover requirements).

## 3. Search & validation
- Default `DuckDuckGoProvider` (unauthenticated HTML, no key). Limits documented: rate-limits, layout drift, no SLA, never bypass CAPTCHA/auth.
- Queries: `"[Name] 2026 Common Data Set filetype:pdf"` then 2025-2026 / 2026-2027 / IR archive / `site:edu`.
- Tracked separately: requested year, reporting period, cohort, policy term, pub date, retrieval time.
- Validation: institution tokens, campus, title/content (“Common Data Set”), period, sections, domain (.edu preferred; mirrors labeled), PDF magic/content-type, size floor. Ambiguous systems (Minnesota, CUNY) flagged; never silently substituted.
- No bulk download executed in this build; pipeline is resumable (`--resume`) with per-university logs and `completeness.json` (`found/downloaded/parsed/verified/partial/needs_review/not_available/failed`).

## 4. Schemas (v1.0.0)
- `Institution`, `CDSDocument`, `C7Record/C7Factor` (VI/I/C/NC preserved; rows discovered per CDS version; raw + normalized), `C8Record`, `C9Record` (SAT/ACT separate; percentiles only when reported; no invented medians), `C10Record`, `C11Record`, `Provenance` (URL, hash, page/bbox, excerpt, section, raw/normalized, method, status, confidence), `DatasetManifest`.
- Frontend export: `frontend/public/data/universities.json` + `manifest.json`.

## 5. GitHub Pages compatibility
- `base: './'`, HashRouter, relative `BASE_URL` fetches, no secrets, small JSON, PDFs stay in `data/cache` (gitignored).
- Works on Pages: browse/compare published data, groups, browser import (PDF-text/HTML/JSON), review/edit, JSON export.
- Works locally only: full search/download/extraction, scanned-PDF OCR, batch refresh.
- CORS: arbitrary URLs may not fetch from browser — UI explains, asks for file upload, points to local CLI.
- Workflows: `ci.yml` (pytest + golden + frontend build), `pages.yml` (build + deploy Pages, routine UI deploys do NOT re-download), `data-refresh.yml` (manual dispatch, Python pipeline → commit JSON).

## 6. Design direction
- From `designs.md`: void-black `#040506` canvas, ink cards, single coral `#ff6363` accent (logo/hero/charts sparingly), mist `#e6e6e6` neutral CTAs, Inter + mono micro-labels, 8px grid, 16px cards with key-shadow inset stack, glass pill nav, hairline borders, reduced-motion + keyboard support, responsive grids.

## 7. Testing & review
- `pytest tests -q` (12 tests): identity, period, wrong-year/institution rejection, PDF/HTML ID, C7 column mapping (incl. reordered), C8/C9/C10/C11 extraction, missing≠zero, provenance, aggregation, schema, golden layouts.
- Golden dataset: text-native, reordered-HTML, scanned-needs-review, ambiguous-system — synthetic, in `data/golden` + frontend data.
- Honest coverage: golden manifest shows 4 bundles, 1 verified period `2025-2026`; production `completeness.json` generated only by real scans (never fabricated).

## 8. Unresolved (defaults used; confirm before bulk scan)
- Target period default `2026` → prefer `2025-2026` latest-available; confirm whether 2026-2027 should supersede when present.
- Ambiguous campuses: default = flag `needs_review`; confirm reviewed mapping (e.g. Minnesota→Twin Cities? CUNY→which college?) or keep as needing clarification.
- Repository name/slug default `aletheia`; license TBD (required before publication).
