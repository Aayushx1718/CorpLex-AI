import { useEffect, useState, type FormEvent } from 'react';
import { apiFetch, jsonResponse } from './api';
type Choice = { id: string; title: string; version_number: number; contract_type: string };
type Obligation = { id: string; kind: string; description: string; amount: string | null; currency: string | null; review_status: string };
type Citation = { number: number; document_id: string; title: string; version_number: number; quote: string; char_start: number; char_end: number; source_units: { kind: string; number: number }[] };
type Answer = { answer: string; abstained: boolean; citations: Citation[]; notice: string; answer_mode: string };
type Scenario = { id: string; currency: string; amount: string; formula: string; notice: string; lines: { source_text: string; rate: string; quantity: string; cap: string | null; amount: string; assumption_note: string; rate_origin: string }[] };
type Compared = { same_contract: boolean; diff: string; diff_truncated: boolean; notice: string; pairs: { status: string; near_duplicate: boolean; left: { id: string; heading: string; text_content: string }; right: { id: string; heading: string; text_content: string } }[]; left_only: { id: string; text_content: string }[]; right_only: { id: string; text_content: string }[] };
type Run = { id: string; state: string; reviewer: string | null; report: { title: string; version_number: number; trace: string[]; notice: string; financial_notice: string; clauses: { id: string; heading: string; text: string }[]; risk: { validated_risk_model: boolean; review_cues: { clause_id: string; source_text: string; reason: string }[] } } };
type Audit = { id: string; actor_id: string; action: string; entity_type: string; entity_id: string; created_at: string };

export default function Workbench({ refreshKey = 0, onInspect, onReviewed }: { refreshKey?: number; onInspect?: (id: string) => void; onReviewed?: () => void }) {
  const [tab, setTab] = useState('research');
  const [choices, setChoices] = useState<Choice[]>([]);
  const [totalChoices, setTotalChoices] = useState(0);
  const [selected, setSelected] = useState('');
  const [other, setOther] = useState('');
  const [obligations, setObligations] = useState<Obligation[]>([]);
  const [selectedObligation, setSelectedObligation] = useState('');
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);
  const [question, setQuestion] = useState('');
  const [answerMode, setAnswerMode] = useState('local');
  const [retrievalMode, setRetrievalMode] = useState('hybrid');
  const [hosted, setHosted] = useState(false);
  const [answer, setAnswer] = useState<Answer | null>(null);
  const [quantity, setQuantity] = useState('1');
  const [rate, setRate] = useState('');
  const [cap, setCap] = useState('');
  const [currency, setCurrency] = useState('USD');
  const [assumption, setAssumption] = useState('');
  const [unreviewed, setUnreviewed] = useState(false);
  const [scenario, setScenario] = useState<Scenario | null>(null);
  const [comparison, setComparison] = useState<Compared | null>(null);
  const [run, setRun] = useState<Run | null>(null);
  const [reviewer, setReviewer] = useState('');
  const [reviewNote, setReviewNote] = useState('');
  const [reviewToken, setReviewToken] = useState('');
  const [reviewTokenRequired, setReviewTokenRequired] = useState(false);
  const [approvals, setApprovals] = useState<string[]>([]);
  const [audit, setAudit] = useState<Audit[]>([]);
  const [auditOffset, setAuditOffset] = useState(0);
  const [revision, setRevision] = useState(0);

  useEffect(() => {
    const controller = new AbortController();
    apiFetch('/api/workbench/documents', { signal: controller.signal }).then(jsonResponse).then(body => {
      if (!controller.signal.aborted) { setChoices(body.items || []); setTotalChoices(body.total || 0); }
    }).catch(err => { if (err.name !== 'AbortError') setError(err.message); });
    apiFetch('/api/research/status', { signal: controller.signal }).then(jsonResponse).then(body => setHosted(body.hosted_configured === true)).catch(() => {});
    apiFetch('/api/access', { signal: controller.signal }).then(jsonResponse).then(body => setReviewTokenRequired(body.reviewer_token_required === true)).catch(() => {});
    return () => controller.abort();
  }, [refreshKey]);
  useEffect(() => {
    const controller = new AbortController();
    setObligations([]);
    if (selected) apiFetch(`/api/documents/${selected}`, { signal: controller.signal }).then(jsonResponse).then(body => {
      if (!controller.signal.aborted) setObligations(body.obligations || []);
    }).catch(err => { if (err.name !== 'AbortError') setError(err.message); });
    return () => controller.abort();
  }, [selected, revision, refreshKey]);
  useEffect(() => { setRun(null); setApprovals([]); setSelectedObligation(''); }, [selected]);
  useEffect(() => {
    if (tab !== 'audit') return;
    const controller = new AbortController();
    apiFetch(`/api/workbench/audit?limit=50&offset=${auditOffset}`, { signal: controller.signal }).then(jsonResponse).then(body => { if (!controller.signal.aborted) setAudit(body.items || []); }).catch(err => { if (err.name !== 'AbortError') setError(err.message); });
    return () => controller.abort();
  }, [tab, auditOffset, revision]);

  async function perform(action: () => Promise<void>) { setError(''); setBusy(true); try { await action(); } catch (err) { setError(err instanceof Error ? err.message : 'Request failed.'); } finally { setBusy(false); } }
  async function ask(event: FormEvent) {
    event.preventDefault(); setAnswer(null);
    await perform(async () => setAnswer(await jsonResponse(await apiFetch('/api/research/ask', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ question, document_ids: selected ? [selected] : [], answer_mode: answerMode, retrieval_mode: retrievalMode }) }))));
  }
  async function simulate(event: FormEvent) {
    event.preventDefault(); setScenario(null);
    await perform(async () => setScenario(await jsonResponse(await apiFetch('/api/finance/scenarios', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ document_id: selected, name: 'Interactive what-if scenario', currency, include_unreviewed: unreviewed, lines: [{ obligation_id: selectedObligation, quantity, assumed_rate: rate || null, cap: cap || null, assumption_note: assumption }] }) }))));
  }
  async function compare(event: FormEvent) {
    event.preventDefault(); setComparison(null);
    await perform(async () => setComparison(await jsonResponse(await apiFetch('/api/comparison', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ left_document_id: selected, right_document_id: other }) }))));
  }
  async function generate() { await perform(async () => setRun(await jsonResponse(await apiFetch('/api/workflows', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ document_id: selected }) })))); }
  async function review(decision: string) {
    if (!run) return;
    if (reviewer.trim().length < 2 || reviewNote.trim().length < 10) { setError('Enter a reviewer name and a review note of at least 10 characters.'); return; }
    await perform(async () => {
      const result = await jsonResponse(await apiFetch(`/api/workflows/${run.id}/review`, { method: 'POST', headers: { 'Content-Type': 'application/json', 'X-Review-Token': reviewToken }, body: JSON.stringify({ decision, reviewer, note: reviewNote, obligations: decision === 'approved' ? approvals.map(id => ({ obligation_id: id, decision: 'approved' })) : [] }) }));
      setRun(result); setReviewToken(''); onReviewed?.();
    });
  }
  async function download() {
    if (!run) return;
    await perform(async () => {
      const body = await jsonResponse(await apiFetch(`/api/workflows/${run.id}/export`));
      const url = URL.createObjectURL(new Blob([JSON.stringify(body, null, 2)], { type: 'application/json' }));
      const link = document.createElement('a'); link.href = url; link.download = `corplex-reviewed-${run.id}.json`; link.click(); URL.revokeObjectURL(url);
    });
  }
  return <section id="workbench" className="workbench">
    <div className="section-title"><h2>Contract intelligence workbench</h2><span>Evidence → assumptions → human review</span></div>
    <div className="workbench-tabs" role="tablist" aria-label="Workbench tools">{[['research', 'Contract research'], ['scenario', 'What-if scenarios'], ['compare', 'Compare versions'], ['review', 'Review workflow'], ['audit', 'Audit log']].map(([id, label]) => <button key={id} role="tab" aria-selected={tab === id} onClick={() => { setTab(id); setError(''); }}>{label}</button>)}</div>
    <p className="help-text">Decision-support tools, not legal advice. Select a stored source version; previous versions remain distinct. {totalChoices > 200 && 'Only the latest 200 versions are listed here; older versions remain available through the API.'}</p>
    {error && <p className="error-message" role="alert">{error}</p>}
    {tab !== 'audit' && <label className="scope-label">Source document version<select aria-label="Workbench source version" value={selected} onChange={event => { setSelected(event.target.value); setAnswer(null); setScenario(null); setComparison(null); }} disabled={busy}><option value="">{tab === 'research' ? 'All latest agreements' : 'Choose a document version'}</option>{choices.map(choice => <option key={choice.id} value={choice.id}>{choice.title} · v{choice.version_number} · {choice.contract_type}</option>)}</select></label>}
    {!choices.length && tab !== 'audit' && <p>Upload a synthetic agreement in the contract repository to begin.</p>}
    {tab === 'research' && <div role="tabpanel"><h3>Evidence-grounded contract research</h3><p className="help-text">Local mode returns relevant source excerpts. Hosted mode sends your question and retrieved excerpts to OpenAI to select quotations; every quote is verified against stored text. Free-form legal claims are not returned. Local vectors are corpus-trained LSA, not pretrained semantic embeddings.</p>
      <form onSubmit={ask} className="tool-form"><label>Question<textarea aria-label="Contract research question" value={question} onChange={e => setQuestion(e.target.value)} minLength={5} maxLength={1000} required rows={3} placeholder="What payment terms are stated?" /></label><label>Retrieval<select aria-label="Retrieval method" value={retrievalMode} onChange={e => setRetrievalMode(e.target.value)}><option value="hybrid">Hybrid</option><option value="lexical">Lexical baseline</option><option value="dense">Local latent vectors</option></select></label><label>Answer mode<select aria-label="Research answer mode" value={answerMode} onChange={e => setAnswerMode(e.target.value)}><option value="local">Local cited excerpts</option><option value="hosted" disabled={!hosted}>Hosted LLM-selected evidence{!hosted ? ' · key not configured' : ''}</option></select></label><button disabled={busy}>{busy ? 'Retrieving evidence…' : 'Research contract'}</button></form>
      {answer && <div className="tool-result" role="status"><h3>{answer.abstained ? 'Insufficient source evidence' : 'Retrieved source evidence'}</h3><pre>{answer.answer}</pre>{answer.citations.map(c => <article key={c.number}><h4>[{c.number}] {c.title} · v{c.version_number}</h4><blockquote>{c.quote}</blockquote><small>{c.source_units.map(u => `${u.kind} ${u.number}`).join(', ')} · characters {c.char_start}–{c.char_end} (end excluded)</small><a href="#/contracts" onClick={() => onInspect?.(c.document_id)}>Inspect source</a></article>)}<p className="help-text">{answer.notice}</p></div>}
    </div>}
    {tab === 'scenario' && <div role="tabpanel"><h3>Explicit financial what-if</h3><p className="help-text">Formula: sum of min(rate × quantity, explicitly entered cap). No cap is inferred. Unreviewed terms require acknowledgment. Amounts are hypothetical scenarios, not losses or outstanding balances.</p>
      <form onSubmit={simulate} className="tool-form"><label>Source obligation<select aria-label="Scenario obligation" required value={selectedObligation} onChange={e => { setSelectedObligation(e.target.value); const o = obligations.find(o => o.id === e.target.value); if (o?.currency) setCurrency(o.currency); }}><option value="">Choose a source obligation</option>{obligations.filter(o => o.review_status !== 'rejected').map(o => <option key={o.id} value={o.id}>{o.kind} · {o.currency || ''} {o.amount || 'ambiguous amount'} · {o.review_status}</option>)}</select></label><label>Quantity<input aria-label="Scenario quantity" type="number" min={0} max={36500} step="0.0001" value={quantity} onChange={e => setQuantity(e.target.value)} required /></label><label>Currency<input aria-label="Scenario currency" pattern="[A-Z]{3}" maxLength={3} value={currency} onChange={e => setCurrency(e.target.value.toUpperCase())} required /></label><label>Assumed rate override (optional)<input aria-label="Scenario rate" type="number" min={0} step="0.0001" value={rate} onChange={e => setRate(e.target.value)} placeholder="Blank uses the single extracted amount" /></label><label>Explicit cap (optional)<input aria-label="Scenario cap" type="number" min={0} step="0.0001" value={cap} onChange={e => setCap(e.target.value)} /></label><label>Assumptions<textarea aria-label="Scenario assumptions" value={assumption} onChange={e => setAssumption(e.target.value)} minLength={10} maxLength={500} required placeholder="Explain what quantity represents and why any cap or rate override applies." /></label><label className="check-label"><input type="checkbox" checked={unreviewed} onChange={e => setUnreviewed(e.target.checked)} />Explicitly include unreviewed candidates</label><button disabled={busy || !selected || !selectedObligation}>Calculate hypothetical scenario</button></form>
      {scenario && <div className="tool-result" role="status"><h3>Hypothetical amount: {scenario.currency} {scenario.amount}</h3><p>{scenario.formula}</p>{scenario.lines.map((line, i) => <article key={i}><blockquote>{line.source_text}</blockquote><p>Rate {line.rate} ({line.rate_origin}) × quantity {line.quantity}; cap {line.cap || 'not supplied'} → {line.amount}</p><p>Assumption: {line.assumption_note}</p></article>)}<p>{scenario.notice}</p><small>Saved scenario: {scenario.id}</small></div>}
    </div>}
    {tab === 'compare' && <div role="tabpanel"><h3>Version and cross-contract comparison</h3><form onSubmit={compare} className="tool-form"><label>Compare against<select aria-label="Comparison right version" value={other} onChange={e => setOther(e.target.value)} required><option value="">Choose a different source version</option>{choices.filter(c => c.id !== selected).map(c => <option key={c.id} value={c.id}>{c.title} · v{c.version_number}</option>)}</select></label><button disabled={busy || !selected || !other || selected === other}>Compare source versions</button></form>{comparison && <div className="tool-result"><p>{comparison.notice}</p><p>{comparison.same_contract ? 'Versions of the same agreement' : 'Separate agreements'} · {comparison.left_only.length} left-only clauses · {comparison.right_only.length} right-only clauses</p>{comparison.pairs.map(pair => <details key={pair.left.id}><summary>{pair.left.heading} ↔ {pair.right.heading} · {pair.status}{pair.near_duplicate ? ' · lexically similar' : ''}</summary><h4>Left source</h4><pre>{pair.left.text_content}</pre><h4>Right source</h4><pre>{pair.right.text_content}</pre></details>)}<details><summary>Unified source text differences</summary><pre>{comparison.diff || 'No source-text differences.'}</pre>{comparison.diff_truncated && <p>Diff limited to the first 2,000 lines.</p>}</details></div>}</div>}
    {tab === 'review' && <div role="tabpanel"><h3>Deterministic review workflow</h3><p className="help-text">Six specialized LangGraph steps prepare an evidence report. They cannot approve it. Report approval requires an explicit human decision; legal-risk validation is still unavailable. {reviewTokenRequired ? 'Reviewer authorization is required.' : 'Local demo mode: entered reviewer names are not identity-verified.'}</p><button disabled={busy || !selected} onClick={generate}>Generate or reopen review report</button>{run && <div className="tool-result"><h3>{run.report.title} · v{run.report.version_number} · {run.state}</h3><ol className="workflow-trace">{run.report.trace.map(step => <li key={step}>{step}</li>)}</ol><p>{run.report.notice}</p><p>{run.report.financial_notice}</p><details><summary>Source clauses for review</summary>{run.report.clauses.map(clause => <article key={clause.id}><h4>{clause.heading}</h4><pre>{clause.text}</pre></article>)}</details><details><summary>Rule-based review cues (not risk predictions)</summary>{run.report.risk.review_cues.map(cue => <article key={cue.clause_id}><p>{cue.reason}</p><blockquote>{cue.source_text}</blockquote></article>)}</details>{run.state === 'awaiting_review' && <div className="tool-form"><h4>Record human review</h4><label>Reviewer name<input aria-label="Reviewer name" value={reviewer} onChange={e => setReviewer(e.target.value)} maxLength={100} /></label><label>Review note<textarea aria-label="Review note" value={reviewNote} onChange={e => setReviewNote(e.target.value)} minLength={10} maxLength={1000} /></label>{reviewTokenRequired && <label>Reviewer token<input aria-label="Reviewer token" type="password" value={reviewToken} onChange={e => setReviewToken(e.target.value)} autoComplete="off" /></label>}<p className="help-text">Optionally mark individual extracted terms as reviewed. Leaving these unchecked does not approve them.</p>{obligations.map(o => <label className="check-label" key={o.id}><input type="checkbox" checked={approvals.includes(o.id)} onChange={e => setApprovals(ids => e.target.checked ? [...ids, o.id] : ids.filter(id => id !== o.id))} />Approve extracted {o.kind}: {o.description}</label>)}<div className="action-row"><button disabled={busy} onClick={() => review('approved')}>Approve reviewed report</button><button disabled={busy} onClick={() => review('rejected')}>Reject report</button></div></div>}<button disabled={busy || run.state !== 'approved'} onClick={download}>Download approved report</button></div>}</div>}
    {tab === 'audit' && <div role="tabpanel"><div className="section-title"><h3>Stored audit events</h3><button onClick={() => setRevision(r => r + 1)}>Refresh audit log</button></div><p className="help-text">Application events, not a tamper-proof compliance log. Local demo actor names are unverified. Production requires access and reviewer tokens.</p><div className="table-scroll"><table><caption>Audit page {auditOffset / 50 + 1}</caption><thead><tr><th>Time (UTC)</th><th>Actor</th><th>Action</th><th>Entity</th></tr></thead><tbody>{audit.map(row => <tr key={row.id}><td>{row.created_at}</td><td>{row.actor_id}</td><td>{row.action}</td><td>{row.entity_type}<small>{row.entity_id}</small></td></tr>)}</tbody></table></div>{!audit.length && <p>No events on this page.</p>}<div className="pagination"><button disabled={auditOffset === 0} onClick={() => setAuditOffset(v => Math.max(0, v - 50))}>Previous events</button><button disabled={audit.length < 50} onClick={() => setAuditOffset(v => v + 50)}>Next events</button></div></div>}
  </section>;
}
