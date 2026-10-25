import { useEffect, useState, type ReactNode, type FormEvent } from 'react';
import { apiFetch, setAccessToken } from './api';
import { WorkspaceSession } from './WorkspaceSession';

export default function AccessBoundary({ children }: { children: ReactNode }) {
  const [required, setRequired] = useState<boolean | null>(null);
  const [authenticated, setAuthenticated] = useState(false);
  const [name, setName] = useState('');
  const [token, setToken] = useState('');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [retry, setRetry] = useState(0);
  useEffect(() => {
    const controller = new AbortController();
    setError(''); setRequired(null);
    fetch('/api/access', { signal: controller.signal }).then(async r => {
      if (!r.ok) throw new Error('Workspace unavailable. Check that Docker is running.');
      const data = await r.json();
      if (typeof data.authentication_required !== 'boolean') throw new Error('Could not verify workspace access settings.');
      if (!controller.signal.aborted) setRequired(data.authentication_required);
    }).catch(err => { if (err.name !== 'AbortError') setError(err.message); });
    return () => controller.abort();
  }, [retry]);
  async function unlock(event: FormEvent) {
    event.preventDefault(); setError('');
    if (required === null || busy) return;
    setBusy(true);
    try {
      if (required) {
        setAccessToken(token);
        const response = await apiFetch('/api/contracts?limit=1');
        if (!response.ok) throw new Error('Access token was rejected.');
      }
      setToken(''); setAuthenticated(true);
    } catch (err) { setAccessToken(''); setError(err instanceof Error ? err.message : 'Could not unlock workspace.'); }
    finally { setBusy(false); }
  }
  function signOut() { setAccessToken(''); setToken(''); setName(''); setAuthenticated(false); setRetry(v => v + 1); }
  if (authenticated) return <WorkspaceSession.Provider value={{ name: name.trim() || 'Local workspace', protected: required === true, signOut }}>{children}</WorkspaceSession.Provider>;
  return <div className="entry-shell">
    <section className="entry-story" aria-label="About CorpLex AI">
      <a className="brand" href="#/overview"><span className="brand-mark">C</span><span>CorpLex <b>AI</b></span></a>
      <div className="entry-copy"><p className="eyebrow">YOUR CONTRACT INTELLIGENCE WORKSPACE</p><h1>Every contract.<br/><span>A clearer picture.</span></h1><p>Bring your agreements, evidence and decisions together. From the first upload to the final review.</p>
        <div className="entry-flow" aria-label="Contract workflow"><div><span>01</span><strong>Collect</strong><small>PDF & DOCX agreements</small></div><i aria-hidden="true">→</i><div><span>02</span><strong>Understand</strong><small>Charts & cited evidence</small></div><i aria-hidden="true">→</i><div><span>03</span><strong>Review</strong><small>Human-led decisions</small></div></div>
      </div><p className="entry-foot">Source-backed insights. Thoughtful decisions.</p>
    </section>
    <main className="entry-panel"><div className="entry-card"><span className="entry-symbol" aria-hidden="true">C<span>✦</span></span><p className="eyebrow">WELCOME TO CORPLEX</p><h2>Your workspace,<br/>ready when you are.</h2><p className="entry-subtitle">{required ? 'Enter your workspace access token to continue.' : 'Explore your agreements with a complete local toolkit.'}</p>
      <form onSubmit={unlock}>
        <label>Your name <span>(optional)</span><input value={name} onChange={e => setName(e.target.value)} maxLength={80} autoComplete="given-name" placeholder="How should we greet you?" /></label>
        {required && <label>Workspace access token<input type="password" value={token} onChange={e => setToken(e.target.value)} autoComplete="off" required placeholder="Enter your private access token" /></label>}
        <button type="submit" disabled={required === null || busy}>{busy ? 'Opening workspace…' : required === null ? 'Checking workspace…' : required ? 'Unlock workspace' : 'Open local workspace'}<span aria-hidden="true">→</span></button>
      </form>
      {error && <div className="error-message" role="alert">{error}{required === null && <button onClick={() => setRetry(v => v + 1)}>Try again</button>}</div>}
      <div className="entry-mode"><span aria-hidden="true">◈</span><p>{required ? 'Protected workspace' : 'Free local workspace'}<small>{required ? 'Tokens stay in memory and clear on exit or reload.' : 'No account, API key or subscription required. Your name is a display label, not authentication.'}</small></p></div>
    </div><p className="entry-legal">Decision support with human review. Not legal advice.</p></main>
  </div>;
}
