import { useEffect, useMemo, useState } from 'react';
import { Link } from 'react-router-dom';
import { Bundle, C7_ORDER, loadBundles, ratingClass, readGroups, saveGroups, similarity } from '../data';

export default function Admissions() {
  const [bundles, setBundles] = useState<Bundle[]>([]);
  const [q, setQ] = useState('');
  const [factor, setFactor] = useState('All factors');
  const [selected, setSelected] = useState<string[]>([]);
  const [groupName, setGroupName] = useState('');
  useEffect(() => { loadBundles().then(d => setBundles(d.bundles)).catch(() => {}); }, []);

  const factors = useMemo(() => {
    const s = new Set<string>();
    bundles.forEach(b => b.c7?.factors.forEach(f => s.add(f.factor_normalized)));
    return ['All factors', ...[...s].sort()];
  }, [bundles]);
  const filtered = useMemo(() => bundles.filter(b =>
    b.institution.display_name.toLowerCase().includes(q.toLowerCase())), [bundles, q]);
  const rows = factor === 'All factors' ? filtered : filtered.filter(b =>
    b.c7?.factors.some(f => f.factor_normalized === factor));

  const toggle = (id: string) => setSelected(s => s.includes(id) ? s.filter(x => x !== id) : [...s, id].slice(0, 4));
  const sims = useMemo(() => {
    if (selected.length !== 2) return null;
    const a = bundles.find(b => b.institution.institution_id === selected[0]);
    const b = bundles.find(b => b.institution.institution_id === selected[1]);
    if (!a || !b) return null;
    return similarity(a, b);
  }, [selected, bundles]);

  const shownFactors = (factor === 'All factors'
    ? [...new Set(rows.flatMap(b => (b.c7?.factors || []).map(f => f.factor_normalized)))].sort().slice(0, 10)
    : [factor]);

  return (
    <div>
      <div className="eyebrow">C7 · Admissions factors</div>
      <h1 style={{ fontWeight: 400 }}>How universities weigh admissions factors</h1>
      <p className="muted">C7 reports institutional importance — not a formula or prediction. Categories are ordinal; do not treat gaps as equal.</p>
      <div className="toolbar" role="search">
        <label>Search<input value={q} onChange={e => setQ(e.target.value)} placeholder="e.g. Lakeside" aria-label="Search institutions" /></label>
        <label>Factor<select value={factor} onChange={e => setFactor(e.target.value)}>{factors.map(f => <option key={f}>{f}</option>)}</select></label>
        <label>Save selection as group<input value={groupName} onChange={e => setGroupName(e.target.value)} placeholder="e.g. Midwest reach" /></label>
        <button className="btn btn-ghost" onClick={() => {
          if (!groupName || !selected.length) return;
          saveGroups([...readGroups(), { name: groupName, ids: selected }]); setGroupName('');
        }}>Save group ({selected.length})</button>
      </div>
      {sims && <div className="notice">Similarity between the two selected: <strong>{(sims.score * 100).toFixed(0)}%</strong> over {sims.shared} shared reported factors. Method: mean absolute ordinal distance (VI=3…NC=0); missing excluded; gaps not equal.</div>}
      <div className="card" style={{ marginTop: 16, overflowX: 'auto' }}>
        <table className="matrix" aria-label="University by factor matrix">
          <thead><tr><th><input type="checkbox" aria-label="select visible" onChange={() => setSelected(rows.slice(0, 4).map(b => b.institution.institution_id))} /></th><th>University</th><th>Period</th>{shownFactors.map(f => <th key={f}>{f}</th>)}</tr></thead>
          <tbody>
            {rows.map(b => (
              <tr key={b.institution.institution_id}>
                <td><input type="checkbox" checked={selected.includes(b.institution.institution_id)} onChange={() => toggle(b.institution.institution_id)} aria-label={`Select ${b.institution.display_name}`} /></td>
                <td><Link to={`/u/${b.institution.institution_id}`}>{b.institution.display_name}</Link> <span className="badge">{b.document?.validation_status || 'local'}</span></td>
                <td className="muted">{b.document?.reporting_period || '—'}</td>
                {shownFactors.map(f => {
                  const hit = b.c7?.factors.find(x => x.factor_normalized === f);
                  const v = hit?.rating_normalized || 'Not reported';
                  return <td key={f} title={hit?.provenance.excerpt || ''}><span className={ratingClass(v)}>{v}</span></td>;
                })}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <div className="grid-2" style={{ marginTop: 16 }}>
        <div className="card"><div className="eyebrow">Category shares</div><CategoryShares bundles={rows} factor={shownFactors[0]} /></div>
        <div className="card"><div className="eyebrow">Side-by-side</div>
          {selected.length === 0 && <p className="muted small">Select up to 4 universities to compare shared factors.</p>}
          {selected.map(id => { const b = bundles.find(x => x.institution.institution_id === id); return b ? <p key={id} className="small">{b.institution.display_name}</p> : null; })}
        </div>
      </div>
    </div>
  );
}

function CategoryShares({ bundles, factor }: { bundles: Bundle[]; factor?: string }) {
  if (!factor) return <p className="muted small">No factor selected.</p>;
  const counts: Record<string, number> = {};
  bundles.forEach(b => {
    const v = b.c7?.factors.find(f => f.factor_normalized === factor)?.rating_normalized || 'Not reported';
    counts[v] = (counts[v] || 0) + 1;
  });
  const total = Math.max(1, Object.values(counts).reduce((a, b) => a + b, 0));
  return (
    <div>
      {C7_ORDER.concat(['Not reported']).map(c => (
        <div key={c} style={{ display: 'flex', gap: 8, alignItems: 'center', margin: '6px 0' }}>
          <span className="small" style={{ width: 120 }}>{c}</span>
          <div style={{ flex: 1, background: '#151619', borderRadius: 4, height: 10 }}>
            <div style={{ width: `${((counts[c] || 0) / total) * 100}%`, background: '#ff6363', height: 10, borderRadius: 4 }} />
          </div>
          <span className="small muted">{counts[c] || 0}/{total}</span>
        </div>
      ))}
      <p className="small muted">Coverage n={total}. Missing never enters the numerator silently.</p>
    </div>
  );
}
