export default function Methodology() {
  return (
    <div>
      <div className="eyebrow">Sources · methodology · limitations</div>
      <h1 style={{ fontWeight: 400 }}>What works where</h1>
      <div className="grid-2">
        <div className="card"><div className="eyebrow">Static site (GitHub Pages)</div>
          <ul className="small"><li>Browse/compare published JSON</li><li>Groups in localStorage</li><li>Browser import (PDF-text/HTML/JSON), review, JSON export</li><li>No Python, no server search</li></ul>
        </div>
        <div className="card"><div className="eyebrow">Local Python pipeline</div>
          <ul className="small"><li><span className="kbd">pip install -e .</span> then <span className="kbd">aletheia scan-one --university "Rice University"</span></li><li>Unauthenticated DDG search + manual overrides; respects robots/CAPTCHA (no bypass)</li><li>Validation, provenance, review queue, <span className="kbd">frontend/public/data</span> export</li><li>Optional API not required for baseline</li></ul>
        </div>
      </div>
      <div className="card" style={{ marginTop: 16 }}>
        <div className="eyebrow">Schema v1.0.0 · missing values</div>
        <p className="small">Missing is explicit: <span className="kbd">not_reported</span>, <span className="kbd">not_applicable</span>, <span className="kbd">unreadable</span>, <span className="kbd">extraction_failed</span>, <span className="kbd">needs_review</span>. Never zero, never conflated with “Not Considered.” Each value carries source URL, hash, page/excerpt, method, and confidence. See <span className="kbd">docs/SCHEMA.md</span> and <span className="kbd">designs.md</span>.</p>
        <p className="small muted">C7 categories are ordinal. Similarity = 1 − mean absolute distance / 3 over shared reported factors. C8 policy term ≠ cohort year. C9 = enrolled submitters only; SAT/ACT shares may overlap; no invented medians. C10/C11 are academic standing, not examinations. Group aggregates show coverage n and distinguish unweighted institutional summaries; student-weighted only with compatible denominators.</p>
      </div>
    </div>
  );
}
