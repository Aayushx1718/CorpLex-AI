import { useEffect, useState, type ReactNode, type FormEvent } from 'react';
import { apiFetch, setAccessToken } from './api';
export default function AccessBoundary({ children }: { children: ReactNode }) {
  const [required, setRequired] = useState(false);
  const [authenticated, setAuthenticated] = useState(false);
  const [token, setToken] = useState('');
  const [error, setError] = useState('');
  useEffect(() => {
    fetch('/api/access').then(r => r.json()).then(data => setRequired(data.authentication_required === true)).catch(() => {});
  }, []);
  async function unlock(event: FormEvent) {
    event.preventDefault(); setError(''); setAccessToken(token);
    try {
      const response = await apiFetch('/api/contracts?limit=1');
      if (!response.ok) throw new Error('Access token was rejected.');
      setToken(''); setAuthenticated(true);
    } catch (err) { setAccessToken(''); setError(err instanceof Error ? err.message : 'Could not unlock workspace.'); }
  }
  if (required && !authenticated) return <main className="access-screen"><h1>CorpLex AI</h1><p>This workspace requires an access token.</p><form onSubmit={unlock}><label>Workspace access token<input type="password" value={token} onChange={e => setToken(e.target.value)} autoComplete="off" required /></label><button type="submit">Unlock workspace</button></form>{error && <p role="alert">{error}</p>}<p>Tokens are held in memory and cleared when this page reloads.</p></main>;
  return <>{children}</>;
}
