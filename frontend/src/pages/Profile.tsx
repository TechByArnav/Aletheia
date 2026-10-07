import { useEffect, useMemo, useState } from 'react';
import { Link } from 'react-router-dom';
import { Bar, BarChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts';
import { Bundle, loadBundles } from '../data';

export default function Profile() {
  const [bundles, setBundles] = useState<Bundle[]>([]);
  const [q, setQ] = useState('');
  const [strictYear, setStrictYear] = useState(true);
  useEffect(() => { loadBundles().then(d => setBundles(d.bundles)).catch(() => {}); }, []);
  const periods = [...new Set(bundles.map(b => b.document?.reporting_period).filter(Boolean) as string[])];
  const [period, setPeriod] = useState('');
  const filtered = useMemo(() => bundles.filter(b =>
    b.institution.display_name.toLowerCase().includes(q.toLowerCase()) &&
    (!period || b.document?.reporting_period === period)), [bundles, q, period]);
  const mixed = periods.length > 1 && !strictYear;

  const satData = filtered.map(b => ({
    name: short(b.institution.display_name),
    p25: b.c9?.sat_ebrw?.p25 ?? b.c9?.sat_math?.p25 ?? null,
    p75: b.c9?.sat_ebrw?.p75 ?? b.c9?.sat_math?.p75 ?? null,
    pct: b.c9?.sat_submitters_pct ?? null
  })).filter(d => d.p25 && d.p75);

  return (
    <div>
      <div className="eyebrow">C8–C11 · Testing &amp; academic profile</div>
      <h1 style={{ fontWeight: 400 }}>Testing policy and enrolled-student academics</h1>
      <p className="muted">C8 = policy (effective term). C9 = enrolled first-year scores (cohort). C10 = class rank. C11 = GPA — not examinations. SAT and ACT scales stay separate.</p>
      <div className="toolbar">
        <label>Search<input value={q} onChange={e => setQ(e.target.value)} placeholder="Search" /></label>
        <label>Reporting period<select value={period} onChange={e => setPeriod(e.target.value)}><option value="">All periods</option>{periods.map(p => <option key={p} value={p}>{p}</option>)}</select></label>
        <label style={{ flexDirection: 'row', alignItems: 'center' }}><input type="checkbox" checked={strictYear} onChange={e => setStrictYear(e.target.checked)} /> Strict single-period (hide mixed-year)</label>
      </div>
      {mixed && <div className="notice">Mixed reporting periods visible ({periods.join(', ')}). Comparisons across years are labeled and should be interpreted cautiously.</div>}
      {strictYear && periods.length > 1 && !period && <div className="notice">Strict mode: pick one reporting period to enable interval charts.</div>}

      <div className="card" style={{ marginTop: 16 }}>
        <div className="eyebrow">C8 · Testing-policy comparison</div>
        <table className="matrix"><thead><tr><th>University</th><th>Policy term</th><th>Notes</th></tr></thead>
          <tbody>{filtered.map(b => <tr key={b.institution.institution_id}>
            <td><Link to={`/u/${b.institution.institution_id}`}>{b.institution.display_name}</Link></td>
            <td className="muted">{b.c8?.policy_term || b.document?.policy_term || '—'}</td>
            <td className="small">{b.c8?.notes || b.c8?.policies.map(p => p.item_raw).slice(0, 2).join(' · ') || 'Not reported'}</td>
          </tr>)}</tbody>
        </table>
      </div>

      <div className="grid-2" style={{ marginTop: 16 }}>
        <div className="card"><div className="eyebrow">C9 · SAT interval (25th–75th)</div>
          {satData.length === 0 ? <p className="muted small">No submittable intervals for current filter. Medians are never invented.</p> : (
            <ResponsiveContainer width="100%" height={220}>
              <BarChart data={satData} layout="vertical">
                <CartesianGrid stroke="#222" /><XAxis type="number" domain={[400, 800]} stroke="#666" /><YAxis type="category" dataKey="name" width={110} stroke="#999" fontSize={12} />
                <Tooltip />
                <Bar dataKey="p25" fill="#2a2b2d" name="25th" /><Bar dataKey="p75" fill="#ff6363" name="75th" />
              </BarChart>
            </ResponsiveContainer>)}
          <p className="small muted">Enrolled submitters only — not all applicants/admits. SAT/ACT submitter shares may overlap.</p>
        </div>
        <div className="card"><div className="eyebrow">C9 · Submission rates</div>
          <ResponsiveContainer width="100%" height={220}>
            <BarChart data={filtered.map(b => ({ name: short(b.institution.display_name), pct: b.c9?.sat_submitters_pct ?? 0 }))}>
              <CartesianGrid stroke="#222" /><XAxis dataKey="name" stroke="#666" fontSize={11} /><YAxis stroke="#666" /><Tooltip />
              <Bar dataKey="pct" fill="#e6e6e6" name="% submitting SAT" />
            </BarChart>
          </ResponsiveContainer>
        </div>
      </div>

      <div className="grid-2" style={{ marginTop: 16 }}>
        <div className="card"><div className="eyebrow">C10 · Class rank (top tenth)</div>
          <ResponsiveContainer width="100%" height={200}>
            <BarChart data={filtered.map(b => ({ name: short(b.institution.display_name), v: b.c10?.top_tenth_pct ?? 0 }))}>
              <CartesianGrid stroke="#222" /><XAxis dataKey="name" stroke="#666" fontSize={11} /><YAxis stroke="#666" /><Tooltip />
              <Bar dataKey="v" fill="#56c2ff" name="% top tenth" />
            </BarChart>
          </ResponsiveContainer>
          <p className="small muted">Share of cohort reporting rank varies; check coverage before comparing.</p>
        </div>
        <div className="card"><div className="eyebrow">C11 · GPA 4.0 share</div>
          <ResponsiveContainer width="100%" height={200}>
            <BarChart data={filtered.map(b => ({ name: short(b.institution.display_name), v: b.c11?.buckets?.['4.0'] ?? 0 }))}>
              <CartesianGrid stroke="#222" /><XAxis dataKey="name" stroke="#666" fontSize={11} /><YAxis stroke="#666" /><Tooltip />
              <Bar dataKey="v" fill="#59d499" name="% with 4.0" />
            </BarChart>
          </ResponsiveContainer>
          <p className="small muted">GPA scales differ; do not combine incompatible definitions without warning.</p>
        </div>
      </div>
    </div>
  );
}
function short(s: string) { return s.length > 18 ? s.slice(0, 17) + '…' : s; }
