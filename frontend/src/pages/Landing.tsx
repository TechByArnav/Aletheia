import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { loadBundles, Bundle } from '../data';

export default function Landing() {
  const [bundles, setBundles] = useState<Bundle[]>([]);
  useEffect(() => { loadBundles().then(d => setBundles(d.bundles)).catch(() => {}); }, []);
  const verified = bundles.filter(b => b.document?.validation_status === 'verified').length;
  const periods = [...new Set(bundles.map(b => b.document?.reporting_period).filter(Boolean))];
  return (
    <div>
      <section className="hero">
        <div className="hero-glow" aria-hidden="true" />
        <div className="eyebrow">Aletheia · unconcealment — what the documents actually say</div>
        <h1>Compare what universities<br />report, not what rumors claim.</h1>
        <p>
          Aletheia discovers, validates, and normalizes university Common Data Sets —
          admissions factors (C7) and testing / academic profiles (C8–C11) —
          with page-level provenance and honest missing-data handling.
        </p>
        <div className="hero-cta">
          <Link className="btn" to="/admissions">Compare admissions factors</Link>
          <Link className="btn btn-ghost" to="/profile">Compare testing &amp; academic profile</Link>
        </div>
        <div className="meta-strip">static build · no backend required · v0.1.0 | C7 + C8–C11 | GitHub Pages ready</div>
      </section>

      <div className="grid-3">
        <div className="card"><div className="eyebrow">Coverage</div>
          <h3>{bundles.length} institutions in bundle</h3>
          <p className="muted small">{verified} verified · periods: {periods.join(', ') || 'none yet'} · mixed-year comparisons are labeled.</p>
        </div>
        <div className="card"><div className="eyebrow">Method</div>
          <h3>First result is a candidate</h3>
          <p className="muted small">Identity, campus, CDS content, and reporting period are validated. Failures enter a review queue — never shown as verified.</p>
        </div>
        <div className="card"><div className="eyebrow">What is the CDS?</div>
          <h3>A common reporting standard</h3>
          <p className="muted small">The Common Data Set is a shared questionnaire colleges publish. C7 reports factor importance; C8–C11 report testing policy and enrolled-student academics. It is not an admissions formula.</p>
        </div>
      </div>

      <div className="card" style={{ marginTop: 24 }}>
        <div className="eyebrow">Preview · C7 matrix</div>
        <p className="muted small">Very Important → Not Considered are ordinal categories. Gaps are not equal and carry no percentage weight.</p>
        <div style={{ overflowX: 'auto' }}>
        <table className="matrix" aria-label="C7 preview">
          <thead><tr><th>University</th><th>Academic GPA</th><th>Class rank</th><th>State residency</th></tr></thead>
          <tbody>
            {bundles.slice(0, 4).map(b => (
              <tr key={b.institution.institution_id}>
                <td><Link to={`/u/${b.institution.institution_id}`}>{b.institution.display_name}</Link></td>
                {['Academic GPA', 'Class rank', 'State residency'].map(f => {
                  const hit = b.c7?.factors.find(x => x.factor_normalized === f);
                  return <td key={f}>{hit ? hit.rating_normalized : '—'}</td>;
                })}
              </tr>
            ))}
          </tbody>
        </table>
        </div>
      </div>
      <p className="small muted" style={{ marginTop: 16 }}>
        Starter institution list is user-provided, not a verified ranking. Source PDFs stay local by default and are not republished.
      </p>
    </div>
  );
}
