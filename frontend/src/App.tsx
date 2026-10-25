import { apiFetch as fetch } from './api';
import { lazy, Suspense, useEffect, useState } from 'react';
import ContractRepository from './ContractRepository';
const AnalyticsDashboard = lazy(() => import('./AnalyticsDashboard'));
const ModelLab = lazy(() => import('./ModelLab'));
const Workbench = lazy(() => import('./Workbench'));


const pages = [
  { id: 'overview', label: 'Executive overview' },
  { id: 'analytics', label: 'Portfolio analytics' },
  { id: 'contracts', label: 'Contract repository' },
  { id: 'models', label: 'Machine learning lab' },
  { id: 'workbench', label: 'Research & review tools' },
];
function currentPage() {
  const id = window.location.hash.replace(/^#\/?/, '');
  return pages.some(page => page.id === id) ? id : 'overview';
}

export default function App() {
  const [page, setPage] = useState(currentPage);
  useEffect(() => {
    const navigate = () => {
      setPage(currentPage());
      window.scrollTo(0, 0);
    };
    window.addEventListener('hashchange', navigate);
    return () => window.removeEventListener('hashchange', navigate);
  }, []);

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
    <aside><a className="brand" href="#/overview">C<span>CorpLex <b>AI</b></span></a>
      <p className="eyebrow">WORKSPACE</p><nav aria-label="Main navigation">{pages.map(item => <a key={item.id} className={page === item.id ? 'active' : undefined} aria-current={page === item.id ? 'page' : undefined} href={`#/${item.id}`}>{item.label}</a>)}</nav>
      <div className="aside-note">Built for clarity.<br/>Grounded in evidence.</div>
    </aside>
    <main><header><span>Corporate intelligence / {pages.find(item => item.id === page)?.label}</span><span className="badge">Contract intelligence workspace</span></header>
      {page === 'overview' && <><section className="hero"><p className="eyebrow">CONTRACT INTELLIGENCE</p><h1>Understand the agreement.<br/><span>See the exposure.</span></h1><p>A foundation for turning corporate contracts into structured, explainable decisions.</p></section>
      <section className="status-grid" aria-label="Environment status"><div><span>Backend API</span><strong role="status">{status}</strong><small>Live health check</small></div><div><span>Contract data</span><strong>PDF / DOCX</strong><small>Upload and inspect source evidence</small></div><div><span>Business-risk model</span><strong>Not trained</strong><small>No validated risk model yet</small></div></section></>}
      {page === 'analytics' && <Suspense fallback={<p role="status">Loading analytics workspace…</p>}><AnalyticsDashboard refreshKey={refreshKey} onInspect={id => setInspectRequest(previous => ({ id, key: (previous?.key || 0) + 1 }))} /></Suspense>}
      {page === 'contracts' && <ContractRepository inspectRequest={inspectRequest} onIngested={() => setRefreshKey(value => value + 1)} />}
      {page === 'models' && <Suspense fallback={<p>Loading model lab…</p>}><ModelLab /></Suspense>}
      {page === 'workbench' && <Suspense fallback={<p>Loading intelligence workbench…</p>}><Workbench refreshKey={refreshKey} onInspect={id => setInspectRequest(previous => ({ id, key: (previous?.key || 0) + 1 }))} onReviewed={() => setRefreshKey(value => value + 1)} /></Suspense>}
      <footer>Decision-support information only. Not legal advice. Extraction requires human review. No validated risk model is available.</footer>
    </main>
  </div>;
}
