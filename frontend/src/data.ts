export interface Provenance {
  source_url: string; document_hash: string; page?: number | null;
  excerpt: string; section: string; raw_value: string; normalized_value: string;
  method: string; status: string; confidence: number;
}
export interface C7Factor {
  factor_raw: string; factor_normalized: string; rating_raw: string;
  rating_normalized: string; missing?: string | null; provenance: Provenance;
}
export interface Bundle {
  institution: { institution_id: string; display_name: string; campus_scope: string; is_ambiguous: boolean; ambiguity_note: string };
  document?: { source_url: string; source_domain: string; is_official: boolean; file_type: string; file_hash: string; reporting_period: string; cohort_year: string; policy_term: string; validation_status: string; validation_notes: string[] } | null;
  c7?: { reporting_period: string; status: string; factors: C7Factor[] } | null;
  c8?: { reporting_period: string; policy_term: string; status: string; policies: { item_raw: string }[]; notes: string } | null;
  c9?: { reporting_period: string; cohort: string; status: string; sat_submitters_pct?: number | null; sat_ebrw: { p25?: number | null; p75?: number | null }; sat_math: { p25?: number | null; p75?: number | null }; sat_composite: { p25?: number | null; p75?: number | null }; act_composite: { p25?: number | null; p75?: number | null } } | null;
  c10?: { status: string; pct_reporting_rank?: number | null; top_tenth_pct?: number | null; top_quarter_pct?: number | null } | null;
  c11?: { status: string; gpa_scale: string; pct_reporting_gpa?: number | null; buckets: Record<string, number | null> } | null;
}

export async function loadBundles(): Promise<{ bundles: Bundle[]; manifest: unknown }> {
  const base = import.meta.env.BASE_URL;
  const [u, m] = await Promise.all([
    fetch(`${base}data/universities.json`).then(r => { if (!r.ok) throw new Error('dataset missing'); return r.json(); }),
    fetch(`${base}data/manifest.json`).then(r => r.json()).catch(() => ({}))
  ]);
  const local = readLocalBundles();
  return { bundles: [...u, ...local], manifest: m };
}

const LOCAL_KEY = 'aletheia.localBundles.v1';
export function readLocalBundles(): Bundle[] {
  try { return JSON.parse(localStorage.getItem(LOCAL_KEY) || '[]'); } catch { return []; }
}
export function saveLocalBundle(b: Bundle) {
  const cur = readLocalBundles();
  const i = cur.findIndex(x => x.institution.institution_id === b.institution.institution_id);
  if (i >= 0) cur[i] = b; else cur.push(b);
  localStorage.setItem(LOCAL_KEY, JSON.stringify(cur));
}

export const C7_ORDER = ['Very Important', 'Important', 'Considered', 'Not Considered'];
export function ratingClass(r: string): string {
  if (r === 'Very Important') return 'pill p-very';
  if (r === 'Important') return 'pill p-important';
  if (r === 'Considered') return 'pill p-considered';
  if (r === 'Not Considered') return 'pill p-not';
  return 'pill p-missing';
}

// Groups
export interface Group { name: string; ids: string[] }
const GROUP_KEY = 'aletheia.groups.v1';
export function readGroups(): Group[] {
  try { return JSON.parse(localStorage.getItem(GROUP_KEY) || '[]'); } catch { return []; }
}
export function saveGroups(g: Group[]) { localStorage.setItem(GROUP_KEY, JSON.stringify(g)); }

// Similarity: mean absolute ordinal distance over shared reported factors (ordinal, gaps not equal).
export function similarity(a: Bundle, b: Bundle): { score: number; shared: number } {
  const w: Record<string, number> = { 'Very Important': 3, Important: 2, Considered: 1, 'Not Considered': 0 };
  const am = new Map((a.c7?.factors || []).filter(f => f.rating_normalized in w).map(f => [f.factor_normalized, w[f.rating_normalized]]));
  const bm = new Map((b.c7?.factors || []).filter(f => f.rating_normalized in w).map(f => [f.factor_normalized, w[f.rating_normalized]]));
  let shared = 0, dist = 0;
  am.forEach((v, k) => { if (bm.has(k)) { shared++; dist += Math.abs(v - (bm.get(k) as number)); } });
  if (!shared) return { score: 0, shared: 0 };
  return { score: 1 - dist / (3 * shared), shared };
}
