import { lazy, Suspense, useContext, useEffect, useState } from 'react';
import ContractRepository from './ContractRepository';
import { WorkspaceSession } from './WorkspaceSession';
const AnalyticsDashboard = lazy(() => import('./AnalyticsDashboard'));
const ModelLab = lazy(() => import('./ModelLab'));
const Workbench = lazy(() => import('./Workbench'));
const SystemStatus = lazy(() => import('./SystemStatus'));

const pages = [
  { id: 'overview', label: 'Dashboard', icon: 'grid', description: 'Your agreements. A clearer perspective.' },
  { id: 'analytics', label: 'Portfolio analytics', icon: 'chart', description: 'Explore patterns across your portfolio.' },
  { id: 'contracts', label: 'Contract repository', icon: 'file', description: 'Every agreement, organized and source-backed.' },
  { id: 'models', label: 'Machine learning lab', icon: 'lab', description: 'Explore clause classification and its evidence.' },
  { id: 'workbench', label: 'Research & review tools', icon: 'search', description: 'Move from source evidence to a reviewed decision.' },
  { id: 'status', label: 'System status', icon: 'status', description: 'Workspace connections and capabilities.' },
];
function Icon({ kind }: { kind: string }) {
  const paths: Record<string, string> = { grid: 'M3 3h7v7H3z M14 3h7v7h-7z M3 14h7v7H3z M14 14h7v7h-7z', chart: 'M4 20V10 M12 20V4 M20 20v-8', file: 'M14 3H5v18h14V8z M14 3v6h5 M8 13h8 M8 17h5', lab: 'M9 3h6 M10 3v7L4 20h16l-6-10V3 M8 14h8', search: 'M20 20l-5-5 M17 10a7 7 0 1 1-14 0 7 7 0 0 1 14 0', status: 'M2 12h5l3-8 4 16 3-8h5' };
  return <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true"><path d={paths[kind] || paths.grid} /></svg>;
}
function currentPage() {
  const id = window.location.hash.replace(/^#\/?/, '');
  return pages.some(page => page.id === id) ? id : 'overview';
}
export default function App() {
  const session = useContext(WorkspaceSession);
  const [page, setPage] = useState(currentPage);
  const [refreshKey, setRefreshKey] = useState(0);
  const [inspectRequest, setInspectRequest] = useState<{ id: string; key: number }>();
  useEffect(() => {
    const navigate = () => { setPage(currentPage()); window.scrollTo(0, 0); };
    window.addEventListener('hashchange', navigate);
    return () => window.removeEventListener('hashchange', navigate);
  }, []);
  const current = pages.find(item => item.id === page)!;
  function inspect(id: string) { setInspectRequest(previous => ({ id, key: (previous?.key || 0) + 1 })); }
  return <div className="shell">
    <aside><a className="brand" href="#/overview"><span className="brand-mark">C</span><span>CorpLex <b>AI</b></span></a>
      <p className="eyebrow">WORKSPACE</p><nav aria-label="Main navigation">{pages.map(item => <a key={item.id} className={`${page === item.id ? 'active' : ''} ${item.id === 'status' ? 'status-nav' : ''}`} aria-current={page === item.id ? 'page' : undefined} href={`#/${item.id}`}><Icon kind={item.icon} /><span>{item.label}</span>{page === item.id && <i aria-hidden="true" />}</a>)}</nav>
      <div className="aside-note"><span className="workspace-avatar">{session.name[0].toUpperCase()}</span><div><strong>{session.name}</strong><small>{session.protected ? 'Protected workspace' : 'Local workspace'}</small></div><button className="sign-out" onClick={session.signOut} aria-label="Leave workspace" title="Leave workspace">→</button></div>
    </aside>
    <main><header><span className="breadcrumb">Workspace <span>/</span> <strong>{current.label}</strong></span><div className="header-tools"><span className="badge">{session.protected ? 'Protected mode' : 'Local edition'}</span><span className="header-avatar" aria-label={session.name}>{session.name[0].toUpperCase()}</span></div></header>
      {page === 'overview' && <><section className="dashboard-welcome"><div><p className="eyebrow">YOUR CONTRACT INTELLIGENCE HUB</p><h1>A clearer view.<br/><span>Better-informed decisions.</span></h1><p>Understand your agreements, follow the evidence, and keep review moving.</p></div><a className="primary-link" href="#/contracts">Upload an agreement <span aria-hidden="true">→</span></a></section><div className="quick-links"><a href="#/contracts"><span className="quick-icon"><Icon kind="file" /></span><div><strong>Organize your agreements</strong><small>Upload, extract & track versions</small></div><span aria-hidden="true">→</span></a><a href="#/workbench"><span className="quick-icon purple"><Icon kind="search" /></span><div><strong>Find the evidence</strong><small>Research, compare & review</small></div><span aria-hidden="true">→</span></a></div>
      <Suspense fallback={<p role="status">Loading dashboard…</p>}><AnalyticsDashboard summary refreshKey={refreshKey} onInspect={inspect} /></Suspense></>}
      {page !== 'overview' && page !== 'status' && <div className="page-intro"><div><p className="eyebrow">CONTRACT INTELLIGENCE</p><h1>{current.label}</h1><p>{current.description}</p></div></div>}
      {page === 'analytics' && <Suspense fallback={<p role="status">Loading analytics workspace…</p>}><AnalyticsDashboard refreshKey={refreshKey} onInspect={inspect} /></Suspense>}
      {page === 'contracts' && <ContractRepository inspectRequest={inspectRequest} onIngested={() => setRefreshKey(value => value + 1)} />}
      {page === 'models' && <Suspense fallback={<p>Loading model lab…</p>}><ModelLab /></Suspense>}
      {page === 'workbench' && <Suspense fallback={<p>Loading intelligence workbench…</p>}><Workbench refreshKey={refreshKey} onInspect={inspect} onReviewed={() => setRefreshKey(value => value + 1)} /></Suspense>}
      {page === 'status' && <Suspense fallback={<p role="status">Loading system status…</p>}><SystemStatus /></Suspense>}
      <footer><span>CorpLex AI <b>·</b> Evidence before decisions.</span><span>Decision support only. Human review required. Not legal advice.</span></footer>
    </main>
  </div>;
}
