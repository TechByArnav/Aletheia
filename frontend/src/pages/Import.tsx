import { useState } from 'react';
import { Bundle, saveLocalBundle } from '../data';

// Browser-side import (GitHub Pages edition): PDF via pasted text for now,
// HTML via file, JSON round-trip. CORS prevents arbitrary URL fetch — explained below.
const FACTORS = ['Rigor of secondary school record','Class rank','Academic GPA','Standardized test scores','Application essay','Recommendations','Interview','Extracurricular activities','Talent/ability','Character/personal qualities','First-generation status','Alumni relation','Geographical residence','State residency','Religious affiliation/commitment','Volunteer work','Work experience','Applicant interest'];
const RATINGS = ['Very Important','Important','Considered','Not Considered','Not reported'];

export default function Import() {
  const [name, setName] = useState('My University');
  const [period, setPeriod] = useState('2025-2026');
  const [ratings, setRatings] = useState<Record<string, string>>({ 'Academic GPA': 'Very Important' });
  const [msg, setMsg] = useState('');
  const [url, setUrl] = useState('');

  const build = (): Bundle => ({
    institution: { institution_id: slug(name), display_name: name, campus_scope: 'User import (browser-local)', is_ambiguous: false, ambiguity_note: '' },
    document: { source_url: url || 'browser-upload', source_domain: 'local', is_official: false, file_type: 'pdf', file_hash: 'browser-local', reporting_period: period, cohort_year: '', policy_term: '', validation_status: 'needs_review', validation_notes: ['Browser import: user-reviewed; scanned PDFs need local OCR workflow.'] },
    c7: { reporting_period: period, status: 'needs_review', factors: FACTORS.map(f => {
      const r = ratings[f] || 'Not reported';
      const reported = (['Very Important','Important','Considered','Not Considered'] as string[]).includes(r);
      return { factor_raw: f, factor_normalized: f, rating_raw: reported ? r : '', rating_normalized: r, missing: reported ? null : 'not_reported',
        provenance: { source_url: 'browser-upload', document_hash: 'browser-local', excerpt: 'user review', section: 'C7', raw_value: r, normalized_value: r, method: 'manual', status: reported ? 'verified' : 'needs_review', confidence: 0.7 } };
    }) }
  });

  const save = () => { const b = build(); saveLocalBundle(b); setMsg(`Saved "${name}" locally in this browser. It now appears in Compare views.`); };

  const onJson = async (f: File) => {
    try {
      const j = JSON.parse(await f.text());
      const list = Array.isArray(j) ? j : [j];
      list.forEach(saveLocalBundle);
      setMsg(`Imported ${list.length} normalized record(s) from JSON.`);
    } catch { setMsg('Could not parse JSON. Expected Aletheia normalized record(s).'); }
  };
  const onHtml = async (f: File) => {
    const html = await f.text();
    const doc = new DOMParser().parseFromString(html, 'text/html');
    const text = doc.body.textContent || '';
    const found = FACTORS.filter(f => text.toLowerCase().includes(f.toLowerCase().slice(0, 12)));
    setMsg(`Parsed HTML text (${text.length} chars). Pre-filled ${found.length} factor rows mentioned — assign ratings below; mentions alone are never ratings.`);
  };

  return (
    <div>
      <div className="eyebrow">Import · review</div>
      <h1 style={{ fontWeight: 400 }}>Bring your own CDS</h1>
      <div className="notice">GitHub Pages cannot run the Python pipeline and browsers block many cross-origin fetches (CORS). If a URL will not fetch, download the PDF/HTML and upload it here — or run <span className="kbd">aletheia scan-one</span> locally. Nothing leaves your browser unless you export it.</div>
      <div className="grid-2" style={{ marginTop: 16 }}>
        <div className="card">
          <div className="eyebrow">1 · Identify</div>
          <label>University<input value={name} onChange={e => setName(e.target.value)} /></label>
          <label>Reporting period (as printed)<input value={period} onChange={e => setPeriod(e.target.value)} placeholder="2025-2026" /></label>
          <label>Source URL (optional)<input value={url} onChange={e => setUrl(e.target.value)} placeholder="https://…/cds.pdf" /></label>
          <div className="toolbar">
            <label>Upload normalized JSON<input type="file" accept=".json" onChange={e => e.target.files && onJson(e.target.files[0])} /></label>
            <label>Upload HTML<input type="file" accept=".html,.htm" onChange={e => e.target.files && onHtml(e.target.files[0])} /></label>
          </div>
          <p className="small muted">PDF text extraction in-browser is limited; scanned PDFs show a warning and point to the local OCR workflow (<span className="kbd">docs/METHODOLOGY</span>). Export/import reviewed JSON to share.</p>
        </div>
        <div className="card">
          <div className="eyebrow">2 · Review C7 ratings</div>
          {FACTORS.map(f => (
            <div key={f} style={{ display: 'flex', gap: 8, alignItems: 'center', margin: '6px 0' }}>
              <span className="small" style={{ flex: 1 }}>{f}</span>
              <select value={ratings[f] || 'Not reported'} onChange={e => setRatings({ ...ratings, [f]: e.target.value })} aria-label={f}>
                {RATINGS.map(r => <option key={r}>{r}</option>)}
              </select>
            </div>
          ))}
          <button className="btn" onClick={save}>Review &amp; save locally</button>
          <button className="btn btn-ghost" style={{ marginLeft: 8 }} onClick={() => {
            const blob = new Blob([JSON.stringify(build(), null, 2)], { type: 'application/json' });
            const a = document.createElement('a'); a.href = URL.createObjectURL(blob); a.download = `${slug(name)}.aletheia.json`; a.click();
          }}>Export JSON</button>
          {msg && <p className="small">{msg}</p>}
        </div>
      </div>
    </div>
  );
}
function slug(s: string) { return s.toLowerCase().replace(/[^a-z0-9]+/g, '-').slice(0, 60) || 'custom'; }
