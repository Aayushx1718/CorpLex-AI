import { apiFetch as fetch } from './api';
import { lazy, Suspense, useEffect, useState } from 'react';
import ContractRepository from './ContractRepository';
const AnalyticsDashboard = lazy(() => import('./AnalyticsDashboard'));
const ModelLab = lazy(() => import('./ModelLab'));
const Workbench = lazy(() => import('./Workbench'));


export default function App() {
  const [refreshKey, setRefreshKey] = useState(0);
  const [inspectRequest, setInspectRequest] = useState<{ id: string; key: number }>();
  const [status, setStatus] = useState('Checking');
  useEffect(() => {
    const controller = new AbortController();
    fetch('/api/health', { signal: controller.signal })
      .then(async response => {
        if (!response.ok) throw new Error('API unavailable');
        const data = await response.json();
        if (data.status !== 'ok') throw new Error('Unexpected response');
        setStatus('Connected');
      })
      .catch(error => { if (error.name !== 'AbortError') setStatus('Unavailable'); });
    return () => controller.abort();
  }, []);
  return <div className="shell">
    <aside><a className="brand" href="/">C<span>CorpLex <b>AI</b></span></a>
      <p className="eyebrow">WORKSPACE</p><nav aria-label="Main navigation"><a className="active" href="#overview">Executive overview</a><a href="#analytics">Portfolio analytics</a><a href="#contracts">Contract repository</a><a href="#models">Machine learning lab</a><a href="#workbench">Research & review tools</a></nav>
      <div className="aside-note">Built for clarity.<br/>Grounded in evidence.</div>
    </aside>
    <main id="overview"><header><span>Corporate intelligence / Overview</span><span className="badge">Contract intelligence workspace</span></header>
      <section className="hero"><p className="eyebrow">CONTRACT INTELLIGENCE</p><h1>Understand the agreement.<br/><span>See the exposure.</span></h1><p>A foundation for turning corporate contracts into structured, explainable decisions.</p></section>
      <section className="status-grid" aria-label="Environment status"><div><span>Backend API</span><strong role="status">{status}</strong><small>Live health check</small></div><div><span>Contract data</span><strong>PDF / DOCX</strong><small>Upload and inspect source evidence</small></div><div><span>Business-risk model</span><strong>Not trained</strong><small>No validated risk model yet</small></div></section>
      <Suspense fallback={<p role="status">Loading analytics workspace…</p>}><AnalyticsDashboard refreshKey={refreshKey} onInspect={id => setInspectRequest(previous => ({ id, key: (previous?.key || 0) + 1 }))} /></Suspense>
      <ContractRepository inspectRequest={inspectRequest} onIngested={() => setRefreshKey(value => value + 1)} />
      <Suspense fallback={<p>Loading model lab…</p>}><ModelLab /></Suspense>
      <Suspense fallback={<p>Loading intelligence workbench…</p>}><Workbench refreshKey={refreshKey} onInspect={id => setInspectRequest(previous => ({ id, key: (previous?.key || 0) + 1 }))} onReviewed={() => setRefreshKey(value => value + 1)} /></Suspense>
      <footer>Decision-support information only. Not legal advice. Extraction requires human review. No validated risk model is available.</footer>
    </main>
  </div>;
}
