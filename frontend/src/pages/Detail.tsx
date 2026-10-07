import { useEffect, useState } from 'react';
import { Link, useParams } from 'react-router-dom';
import { Bundle, loadBundles, ratingClass } from '../data';

export default function Detail() {
  const { id } = useParams();
  const [b, setB] = useState<Bundle | null>(null);
  useEffect(() => { loadBundles().then(d => setB(d.bundles.find(x => x.institution.institution_id === id) || null)).catch(() => {}); }, [id]);
  if (!b) return <p className="muted">Loading… <Link to="/admissions">Back</Link></p>;
  return (
    <div>
      <Link to="/admissions" className="small muted">← All universities</Link>
      <h1 style={{ fontWeight: 400 }}>{b.institution.display_name}</h1>
      <p className="muted small">
        {b.institution.campus_scope || 'Campus/scope as reported'} · Reporting period {b.document?.reporting_period || '—'} ·
        Cohort {b.document?.cohort_year || '—'} · Policy term {b.document?.policy_term || '—'} ·
        Status <span className="badge">{b.document?.validation_status || 'local import'}</span>
      </p>
      {b.institution.is_ambiguous && <div className="notice">{b.institution.ambiguity_note}</div>}
      {b.document?.source_url && <p className="small">Source: <a href={b.document.source_url}>{b.document.source_domain || b.document.source_url}</a> {b.document.is_official ? '(official .edu)' : '(mirror — verify)'} · hash <span className="kbd">{b.document.file_hash.slice(0, 12)}</span></p>}
      {(b.document?.validation_notes || []).map((n, i) => <p key={i} className="small muted">· {n}</p>)}

      <div className="grid-2" style={{ marginTop: 16 }}>
        <div className="card"><div className="eyebrow">C7 · Factors</div>
          <table className="matrix"><thead><tr><th>Factor</th><th>Rating</th></tr></thead><tbody>
            {(b.c7?.factors || []).map(f => <tr key={f.factor_normalized}><td>{f.factor_normalized}</td>
              <td title={f.provenance.excerpt}><span className={ratingClass(f.rating_normalized)}>{f.rating_normalized}</span></td></tr>)}
          </tbody></table>
          {!b.c7?.factors.length && <p className="muted small">Not reported / needs review.</p>}
        </div>
        <div>
          <div className="card"><div className="eyebrow">C8 · Testing policy</div><p className="small">{b.c8?.notes || 'Not reported'}</p></div>
          <div className="card" style={{ marginTop: 16 }}><div className="eyebrow">C9 · Scores (enrolled)</div>
            <p className="small">SAT EBRW 25–75: {fmt(b.c9?.sat_ebrw?.p25)}–{fmt(b.c9?.sat_ebrw?.p75)} · Math: {fmt(b.c9?.sat_math?.p25)}–{fmt(b.c9?.sat_math?.p75)} · SAT submitters: {b.c9?.sat_submitters_pct ?? '—'}%</p>
            <p className="small muted">Enrolled first-year submitters only. No median invented when absent.</p>
          </div>
          <div className="card" style={{ marginTop: 16 }}><div className="eyebrow">C10 · Rank / C11 · GPA</div>
            <p className="small">Top tenth: {b.c10?.top_tenth_pct ?? '—'}% · 4.0 GPA: {b.c11?.buckets?.['4.0'] ?? '—'}% (scale {b.c11?.gpa_scale || '—'})</p>
          </div>
        </div>
      </div>
    </div>
  );
}
function fmt(v?: number | null) { return v == null ? '—' : String(v); }
