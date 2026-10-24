import { useEffect, useState, type FormEvent } from 'react';

type ContractType = 'nda' | 'employment' | 'vendor' | 'service';
type Summary = { contract_id: string; title: string; contract_type: ContractType; document_id: string; version_number: number; original_filename: string };
type Clause = { id: string; ordinal: number; heading: string; text_content: string; page_number: number | null; char_start: number; char_end: number };
type Entity = { kind: string; raw_text: string; normalized_value: string; currency: string | null; char_start: number; char_end: number };
type SourceUnit = { kind: string; number: number; char_start: number; char_end: number };
type Obligation = { id: string; kind: string; description: string; amount: string | number | null; currency: string | null; recurrence: string | null; review_status: string };
type DocumentDetail = Summary & { id: string; sha256: string; status: string; canonical_text: string; clauses: Clause[]; entities: Entity[]; source_units: SourceUnit[]; warnings: string[]; obligations: Obligation[]; extractor_version: string; effective_date: string | null; expiration_date: string | null };

async function readResponse(response: Response) {
  if (!response.ok) {
    let message = `Request failed (${response.status}).`;
    try { const data = await response.json(); if (typeof data.detail === 'string') message = data.detail; } catch { /* retain useful HTTP error */ }
    throw new Error(message);
  }
  return response.json();
}

export default function ContractRepository() {
  const [items, setItems] = useState<Summary[]>([]);
  const [offset, setOffset] = useState(0);
  const [refresh, setRefresh] = useState(0);
  const [listLoading, setListLoading] = useState(true);
  const [listError, setListError] = useState('');
  const [type, setType] = useState<ContractType>('vendor');
  const [target, setTarget] = useState('');
  const [busy, setBusy] = useState(false);
  const [loadingDocument, setLoadingDocument] = useState(false);
  const [error, setError] = useState('');
  const [notice, setNotice] = useState('');
  const [document, setDocument] = useState<DocumentDetail | null>(null);
  useEffect(() => {
    const controller = new AbortController();
    setListLoading(true); setListError('');
    fetch(`/api/contracts?limit=25&offset=${offset}`, { signal: controller.signal })
      .then(readResponse).then(data => {
        if (!Array.isArray(data.items)) throw new Error('Unexpected contract repository response.');
        setItems(data.items);
      })
      .catch(err => { if (err.name !== 'AbortError') setListError(err.message); })
      .finally(() => { if (!controller.signal.aborted) setListLoading(false); });
    return () => controller.abort();
  }, [offset, refresh]);

  async function upload(event: FormEvent<HTMLFormElement>) {
    event.preventDefault(); setError(''); setNotice('');
    const form = event.currentTarget;
    const data = new FormData(form);
    const fileInput = form.elements.namedItem('file') as HTMLInputElement;
    const file = fileInput.files?.[0];
    if (!file || !file.size) { setError('Choose a non-empty PDF or DOCX file.'); return; }
    if (file.size > 10 * 1024 * 1024) { setError('File exceeds 10 MiB.'); return; }
    data.set('file', file);
    if (target) data.set('contract_id', target);
    else data.delete('contract_id');
    data.set('contract_type', type);
    if (!String(data.get('title') || '').trim()) data.delete('title');
    setBusy(true);
    try {
      const result = await readResponse(await fetch('/api/contracts', { method: 'POST', body: data }));
      setDocument(result.document);
      setNotice(result.duplicate ? 'Identical content already exists. The existing document is shown; no duplicate was created.' : 'Document ingested. Review the extracted evidence and obligation candidates below.');
      setOffset(0); setRefresh(value => value + 1);
      for (const name of ['file', 'title']) {
        const input = form.elements.namedItem(name);
        if (input instanceof HTMLInputElement) input.value = '';
      }
    } catch (err) { setError(err instanceof Error ? err.message : 'Upload failed.'); }
    finally { setBusy(false); }
  }

  async function openDocument(id: string) {
    setError(''); setNotice(''); setLoadingDocument(true);
    try { setDocument(await readResponse(await fetch(`/api/documents/${id}`))); }
    catch (err) { setError(err instanceof Error ? err.message : 'Could not open document.'); }
    finally { setLoadingDocument(false); }
  }

  return <section id="contracts" className="repository">
    <div className="section-title"><h2>Contract repository</h2><span>Source-backed ingestion</span></div>
    <div className="upload-panel">
      <h3>Upload an agreement</h3><p>PDF or DOCX · up to 10 MiB · text-based documents only. Use synthetic demonstration files.</p>
      <form onSubmit={upload}>
        <label>Version target<select aria-label="Version target" value={target} onChange={event => {
          setTarget(event.target.value);
          const existing = items.find(item => item.contract_id === event.target.value);
          if (existing) setType(existing.contract_type);
        }} disabled={busy}><option value="">New contract</option>{items.map(item => <option key={item.contract_id} value={item.contract_id}>{item.title} (v{item.version_number})</option>)}</select></label>
        <label>Contract type<select aria-label="Contract type" name="contract_type" value={type} onChange={event => setType(event.target.value as ContractType)} disabled={busy || Boolean(target)}><option value="nda">NDA</option><option value="employment">Employment</option><option value="vendor">Vendor</option><option value="service">Service</option></select></label>
        <label>Title (new contracts only)<input name="title" maxLength={200} placeholder="Uses filename if empty" disabled={busy || Boolean(target)} /></label>
        <label className="file-field">Document<input type="file" name="file" accept=".pdf,.docx" required disabled={busy} /></label>
        <button type="submit" disabled={busy || loadingDocument}>{busy ? 'Extracting…' : 'Upload and extract'}</button>
      </form>
      <p className="help-text">Rule-based extraction requires review. Relative deadlines and multi-amount clauses are not automatically resolved. Image-only PDFs require OCR, which is not available yet.</p>
    </div>
    {error && <p className="error-message" role="alert">{error}</p>}
    {notice && <p className="success-message" role="status">{notice}</p>}
    <div className="contract-list" aria-label="Uploaded agreements">
      {listLoading ? <p>Loading contracts…</p> : listError ? <p role="alert">{listError} <button onClick={() => setRefresh(value => value + 1)}>Retry</button></p> : items.length === 0 ? <p>No contracts on this page. Upload a synthetic agreement to begin.</p> : items.map(item => <div className="contract-row" key={item.contract_id}><div><strong>{item.title}</strong><span>{item.contract_type} · v{item.version_number} · {item.original_filename}</span></div><button disabled={busy || loadingDocument} onClick={() => openDocument(item.document_id)}>Inspect extraction</button></div>)}
      <div className="pagination"><button disabled={offset === 0 || listLoading || busy} onClick={() => { setTarget(''); setOffset(value => Math.max(0, value - 25)); }}>Previous</button><span>Page {offset / 25 + 1}</span><button disabled={items.length < 25 || listLoading || busy} onClick={() => { setTarget(''); setOffset(value => value + 25); }}>Next</button></div>
    </div>
    {loadingDocument && <p role="status">Loading extraction…</p>}
    {document && <div className="document-detail">
      <div className="section-title"><h2>{document.title} · v{document.version_number}</h2><span>{document.extractor_version}</span></div>
      <p>{document.original_filename} · {document.contract_type} · Effective: {document.effective_date || 'Not extracted'} · Expiration: {document.expiration_date || 'Not extracted'}</p>
      <p className="help-text">“Validated” means structurally valid, not legally verified. Character ranges refer to the stored extracted text and are half-open: the end index is excluded.</p>
      <details><summary>Extraction limitations ({document.warnings.length})</summary><ul>{document.warnings.map((warning, index) => <li key={index}>{warning}</li>)}</ul></details>
      <h3>Extracted entities</h3><div className="entity-grid">{document.entities.length ? document.entities.map((entity, index) => <div key={index}><span className="eyebrow">{entity.kind}</span><strong>{entity.kind === 'money' ? `${entity.currency} ${entity.normalized_value}` : entity.normalized_value}</strong><small>Characters {entity.char_start}–{entity.char_end}</small></div>) : <p>No supported entities found. Review the source.</p>}</div>
      <h3>Clauses and source evidence</h3>{document.clauses.map(clause => {
        const units = document.source_units.filter(unit => unit.char_end > clause.char_start && unit.char_start < clause.char_end);
        return <details className="clause" key={clause.id}><summary>{clause.heading || `Clause ${clause.ordinal}`}</summary><small>{units.map(unit => `${unit.kind} ${unit.number}`).join(', ')} · Characters {clause.char_start}–{clause.char_end}</small><pre>{clause.text_content}</pre></details>;
      })}
      <h3>Obligation candidates · review pending</h3><p className="help-text">These are extracted terms, not losses, predictions, or approved legal conclusions. Review approval is not implemented in this phase.</p>{document.obligations.length ? document.obligations.map(obligation => <div className="obligation" key={obligation.id}><strong>{obligation.kind} · {obligation.review_status}</strong><p>{obligation.description}</p><small>{obligation.amount != null ? `Candidate amount: ${obligation.currency} ${obligation.amount}${obligation.recurrence ? ` · ${obligation.recurrence}` : ''}` : 'No single amount assigned; review source terms.'}</small></div>) : <p>No supported obligation candidates found.</p>}
      <details><summary>Canonical extracted text and content hash</summary><p className="hash">SHA-256: {document.sha256}</p><pre>{document.canonical_text}</pre></details>
    </div>}
  </section>;
}
