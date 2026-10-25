import { useEffect, useState } from 'react';
import { apiFetch } from './api';

type Check = { label: string; state: string; detail: string; ok: boolean };
export default function SystemStatus() {
  const [checks, setChecks] = useState<Check[]>([]);
  const [loading, setLoading] = useState(true);
  const [revision, setRevision] = useState(0);
  useEffect(() => {
    const controller = new AbortController();
    setLoading(true);
    const sources = [
      { label: 'Backend API', path: '/api/health', describe: (data: { status?: string }) => ({ state: data.status === 'ok' ? 'Connected' : 'Unavailable', detail: 'Application service liveness check.', ok: data.status === 'ok' }) },
      { label: 'Database & schema', path: '/api/ready', describe: (data: { status?: string }) => ({ state: data.status === 'ready' ? 'Ready' : 'Unavailable', detail: 'Database and analytics schema readiness check.', ok: data.status === 'ready' }) },
      { label: 'Local research', path: '/api/research/status', describe: (data: { local_available?: boolean }) => ({ state: data.local_available ? 'Available' : 'Unavailable', detail: 'Cited excerpts without paid APIs.', ok: data.local_available === true }) },
      { label: 'Clause classifier', path: '/api/ml/status', describe: (data: { model_available?: boolean }) => ({ state: data.model_available ? 'Active' : 'Not activated', detail: 'Recorded benchmarks are separate from a locally installed model.', ok: data.model_available === true }) },
    ];
    Promise.all(sources.map(async source => {
      try {
        const response = await apiFetch(source.path, { signal: controller.signal });
        if (!response.ok) throw new Error();
        return { label: source.label, ...source.describe(await response.json()) };
      } catch { return { label: source.label, state: 'Unavailable', detail: 'Could not verify. Check service connectivity and workspace access.', ok: false }; }
    })).then(results => { if (!controller.signal.aborted) { setChecks(results); setLoading(false); } });
    return () => controller.abort();
  }, [revision]);
  return <section className="system-page"><div className="page-intro"><div><p className="eyebrow">WORKSPACE OPERATIONS</p><h1>System status</h1><p>Connections and capabilities, in one place.</p></div><button onClick={() => setRevision(v => v + 1)} disabled={loading}>Refresh status</button></div>
    {loading ? <p role="status">Checking workspace services…</p> : <div className="system-grid">{checks.map(check => <article key={check.label}><div className="system-card-top"><span>{check.label}</span><i className={check.ok ? 'service-dot good' : 'service-dot'} /></div><strong>{check.state}</strong><p>{check.detail}</p></article>)}</div>}
    <div className="status-note"><h3>Built for a local workflow</h3><p>PDF and DOCX extraction, analytics, local research, financial scenarios and human review work without an API key. Scanned PDFs need OCR, which is not included. Clause classification requires a trusted trained artifact; a validated business-risk severity model is not available.</p></div>
  </section>;
}
