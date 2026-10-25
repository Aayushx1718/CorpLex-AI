import { apiFetch as fetch } from './api';
import { useEffect, useState, type FormEvent } from 'react';
import { Bar, BarChart, CartesianGrid, Cell, Pie, PieChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts';

type Filters = { contract_type: string; currency: string; review_status: string; as_of: string; horizon_days: string };
type Overview = {
  as_of: string; through: string; limit: number; offset: number;
  kpis: { contracts: number; obligations: number; pending_review: number; missing_expiration: number; expiring: number; past_due_dates: number; missing_due_dates: number };
  by_type: { contract_type: string; count: number }[];
  by_kind: { kind: string; review_status: string; count: number }[];
  amount_groups: { currency: string; kind: string; review_status: string; recurrence: string | null; amount: string; count: number }[];
  contracts: { contract_id: string; document_id: string; title: string; contract_type: string; version_number: number; party_names: string[]; obligations: number; pending_review: number; expiration_date: string | null }[];
  deadlines: { document_id: string; contract_id: string; title: string; event_date: string; event_type: string; clause_id: string | null; description: string; review_status: string | null }[];
  deadline_total: number;
};
const colors = ['#8b7ad5', '#79a8b7', '#b9a3d8', '#d7b47c'];
const defaults: Filters = { contract_type: '', currency: '', review_status: '', as_of: '', horizon_days: '90' };

export default function AnalyticsDashboard({ refreshKey = 0, onInspect, summary = false }: { refreshKey?: number; onInspect?: (id: string) => void; summary?: boolean }) {
  const [draft, setDraft] = useState<Filters>(defaults);
  const [filters, setFilters] = useState<Filters>(defaults);
  const [offset, setOffset] = useState(0);
  const [refresh, setRefresh] = useState(0);
  const [data, setData] = useState<Overview | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  useEffect(() => {
    const controller = new AbortController();
    const query = new URLSearchParams({ limit: '20', offset: String(offset) });
    Object.entries(filters).forEach(([key, value]) => { if (value) query.set(key, value); });
    setLoading(true); setError(''); setData(null);
    fetch(`/api/analytics/overview?${query}`, { signal: controller.signal })
      .then(async response => {
        if (!response.ok) {
          const body = await response.json().catch(() => ({}));
          throw new Error(typeof body.detail === 'string' ? body.detail : `Analytics request failed (${response.status}).`);
        }
        return response.json();
      })
      .then(result => {
        if (!result.kpis || !Array.isArray(result.amount_groups)) throw new Error('Unexpected analytics response.');
        if (!controller.signal.aborted) setData(result);
      })
      .catch(err => { if (err.name !== 'AbortError') setError(err.message); })
      .finally(() => { if (!controller.signal.aborted) setLoading(false); });
    return () => controller.abort();
  }, [filters, offset, refresh, refreshKey]);
  function apply(event: FormEvent) { event.preventDefault(); setOffset(0); setFilters({ ...draft }); }
  function field(key: keyof Filters, value: string) { setDraft(previous => ({ ...previous, [key]: value })); }
  const kindData = data ? [...new Set(data.by_kind.map(row => row.kind))].map(kind => ({
    kind, ...Object.fromEntries(['pending', 'approved', 'rejected'].map(state => [state, data.by_kind.find(row => row.kind === kind && row.review_status === state)?.count || 0])),
  })) : [];
  function inspect(id: string) { onInspect?.(id); }
  return <section id={summary ? "dashboard-charts" : "analytics"} className={`analytics ${summary ? "analytics-summary" : ""}`}>
    <div className="section-title"><h2>{summary ? "Portfolio at a glance" : "Portfolio analytics"}</h2><button onClick={() => setRefresh(value => value + 1)} disabled={loading}>Refresh analytics</button></div>
    <p className="help-text">Latest validated version per agreement. Extracted terms are decision-support evidence, not verified liabilities or estimated losses.</p>
    {!summary && <><form className="analytics-filters" onSubmit={apply}>
      <label>Agreement type<select aria-label="Analytics agreement type" value={draft.contract_type} onChange={e => field('contract_type', e.target.value)}><option value="">All types</option><option value="nda">NDA</option><option value="employment">Employment</option><option value="vendor">Vendor</option><option value="service">Service</option></select></label>
      <label>Currency<select aria-label="Analytics currency" value={draft.currency} onChange={e => field('currency', e.target.value)}><option value="">All currencies</option>{['USD', 'EUR', 'GBP', 'INR', 'CAD', 'AUD', 'JPY', 'CHF'].map(code => <option key={code}>{code}</option>)}</select></label>
      <label>Review state<select aria-label="Analytics review state" value={draft.review_status} onChange={e => field('review_status', e.target.value)}><option value="">All review states</option><option value="pending">Pending</option><option value="approved">Approved</option><option value="rejected">Rejected</option></select></label>
      <label>As-of date<input aria-label="Analytics as-of date" type="date" value={draft.as_of} onChange={e => field('as_of', e.target.value)} /></label>
      <label>Look ahead (days)<input aria-label="Analytics look ahead" type="number" min={1} max={365} value={draft.horizon_days} onChange={e => field('horizon_days', e.target.value)} required /></label>
      <button type="submit" disabled={loading}>Apply filters</button>
    </form>
    <p className="help-text">Currency/review filters retain only agreements with matching obligations. Leaving the as-of date empty uses today's UTC date. Expiration dates describe contract end dates; renewal notice dates are not inferred.</p></>}
    {loading && <p role="status">Loading portfolio analytics…</p>}
    {error && <p role="alert" className="error-message">{error} <button onClick={() => setRefresh(value => value + 1)}>Retry analytics</button></p>}
    {data && <>
      <p className="analytics-window">Recorded deadlines: {data.as_of} through {data.through}, inclusive. Earlier obligation due dates are also listed.</p>
      <div className="analytics-kpis">
        {[
          ['Agreements', data.kpis.contracts], ['Obligation candidates', data.kpis.obligations], ['Awaiting review', data.kpis.pending_review],
          ['Expiring in window', data.kpis.expiring], ['Past recorded due dates', data.kpis.past_due_dates],
          ['No expiration recorded', data.kpis.missing_expiration],
        ].filter((_, index) => !summary || index < 4).map(([label, value]) => <div key={label}><span>{label}</span><strong>{value}</strong></div>)}
      </div>
      {data.kpis.contracts === 0 ? <p className="analytics-empty">No agreements match these filters. Upload a contract or broaden the filters.</p> : <>
        <div className="analytics-charts">
          <article><h3>Agreements by type</h3><div className="chart" aria-label="Agreement type distribution"><ResponsiveContainer width="100%" height="100%"><PieChart><Pie isAnimationActive={false} data={data.by_type} dataKey="count" nameKey="contract_type" innerRadius={55} outerRadius={85}>{data.by_type.map((row, index) => <Cell key={row.contract_type} fill={colors[index % colors.length]} />)}</Pie><Tooltip /></PieChart></ResponsiveContainer></div><ul className="chart-legend">{data.by_type.map((row, index) => <li key={row.contract_type}><i style={{ background: colors[index % colors.length] }} />{row.contract_type}: <b>{row.count}</b></li>)}</ul></article>
          <article><h3>Obligations by kind and review state</h3>{kindData.length ? <><div className="chart" aria-label="Obligation kind distribution"><ResponsiveContainer width="100%" height="100%"><BarChart data={kindData}><CartesianGrid strokeDasharray="3 3" vertical={false} /><XAxis dataKey="kind" tick={{ fontSize: 10 }} /><YAxis allowDecimals={false} width={35} /><Tooltip /><Bar isAnimationActive={false} dataKey="pending" stackId="state" fill="#c2a961" /><Bar isAnimationActive={false} dataKey="approved" stackId="state" fill="#3b8266" /><Bar isAnimationActive={false} dataKey="rejected" stackId="state" fill="#a47c71" /></BarChart></ResponsiveContainer></div><ul className="chart-legend">{data.by_kind.map(row => <li key={`${row.kind}-${row.review_status}`}>{row.kind} · {row.review_status}: <b>{row.count}</b></li>)}</ul></> : <p>No obligation candidates for this scope.</p>}</article>
        </div>
        {!summary && <><h3>Stated single-amount terms</h3><p className="help-text">Amounts are grouped by currency, clause kind, recurrence and review state. Unspecified recurrence is not assumed to be one-time. These sums are not contract values, annualized costs or exposure estimates. Rejected terms remain separately labeled.</p>
        {data.amount_groups.length ? <div className="table-scroll"><table><caption>Exact amounts without currency conversion</caption><thead><tr><th>Currency</th><th>Kind</th><th>Recurrence</th><th>Review</th><th>Terms</th><th>Stated amount sum</th></tr></thead><tbody>{data.amount_groups.map(row => <tr key={`${row.currency}-${row.kind}-${row.recurrence}-${row.review_status}`}><td>{row.currency}</td><td>{row.kind}</td><td>{row.recurrence || 'Unspecified'}</td><td>{row.review_status}</td><td>{row.count}</td><td className="numeric">{row.amount}</td></tr>)}</tbody></table></div> : <p>No unambiguous single-amount terms extracted.</p>}
        </>}<div className="section-title"><h3>Agreement register</h3>{summary && <a className="text-link" href="#/contracts">View all contracts →</a>}</div><p className="help-text">Parties are source names, not verified vendor identities. Party names do not multiply financial or obligation counts.</p>
        <div className="table-scroll"><table><caption>{summary ? 'Agreement preview · latest validated versions' : `Latest versions · page ${offset / 20 + 1}`}</caption><thead><tr><th>Agreement</th><th>Parties</th><th>Obligations</th><th>Pending review</th><th>Expiration</th></tr></thead><tbody>{(summary ? data.contracts.slice(0, 6) : data.contracts).map(row => <tr key={row.contract_id}><td><a href="#/contracts" onClick={() => inspect(row.document_id)}>{row.title}</a><small>{row.contract_type} · v{row.version_number}</small></td><td>{row.party_names.join('; ') || 'Not extracted'}</td><td>{row.obligations}</td><td>{row.pending_review}</td><td>{row.expiration_date || 'Not recorded'}</td></tr>)}</tbody></table></div>
        {!summary && <div className="pagination"><button disabled={offset === 0} onClick={() => setOffset(value => Math.max(0, value - 20))}>Previous agreements</button><span>{Math.min(offset + data.contracts.length, data.kpis.contracts)} of {data.kpis.contracts}</span><button disabled={offset + 20 >= data.kpis.contracts} onClick={() => setOffset(value => value + 20)}>Next agreements</button></div>}
      </>}
      {!summary && <><h3>Recorded deadlines and expiration tracker</h3><p className="help-text">{data.kpis.missing_due_dates} obligation(s) have no explicit due date recorded. Past due dates do not prove nonpayment. Rejected obligations are excluded from this tracker.</p>
      {data.deadlines.length ? <><div className="table-scroll"><table><caption>Showing {data.deadlines.length} of {data.deadline_total} dates (earliest first)</caption><thead><tr><th>Date</th><th>Agreement</th><th>Event</th><th>Review</th><th>Source context</th></tr></thead><tbody>{data.deadlines.map((row, index) => <tr key={`${row.document_id}-${row.event_type}-${index}`}><td>{row.event_date}{row.event_date < data.as_of && <small>Past date</small>}</td><td><a href="#/contracts" onClick={() => inspect(row.document_id)}>{row.title}</a></td><td>{row.event_type.replaceAll('_', ' ')}</td><td>{row.review_status || 'Extracted date'}</td><td>{row.description}</td></tr>)}</tbody></table></div>{data.deadline_total > 100 && <p className="help-text">Tracker limited to the first 100 dates. Narrow the filters to inspect more.</p>}</> : <p>No recorded deadlines in this window.</p>}</>}
    </>}
  </section>;
}
