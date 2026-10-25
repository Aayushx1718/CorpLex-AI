import { afterEach, expect, it, vi } from 'vitest';
import { cleanup, render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import AccessBoundary from './AccessBoundary';
import { useContext } from 'react';
import { WorkspaceSession } from './WorkspaceSession';
import { apiFetch } from './api';
import { setAccessToken } from './api';
afterEach(() => { cleanup(); setAccessToken(''); vi.unstubAllGlobals(); });
it('opens local development without requiring a token', async () => {
  vi.stubGlobal('fetch', vi.fn().mockResolvedValue({ ok: true, json: async () => ({ authentication_required: false }) }));
  render(<AccessBoundary><p>Workspace content</p></AccessBoundary>);
  expect(screen.queryByText('Workspace content')).not.toBeInTheDocument();
  await userEvent.click(await screen.findByRole('button', { name: 'Open local workspace' }));
  expect(await screen.findByText('Workspace content')).toBeInTheDocument();
});
it('requires a valid token and sends it in the header', async () => {
  const fetch = vi.fn().mockResolvedValueOnce({ ok: true, json: async () => ({ authentication_required: true }) }).mockResolvedValue({ ok: true });
  vi.stubGlobal('fetch', fetch); render(<AccessBoundary><p>Unlocked content</p></AccessBoundary>);
  await userEvent.type(await screen.findByLabelText('Workspace access token'), 'test-workspace-token');
  await userEvent.click(screen.getByRole('button', { name: 'Unlock workspace' }));
  expect(await screen.findByText('Unlocked content')).toBeInTheDocument();
  expect(fetch.mock.calls[1][0]).toBe('/api/contracts?limit=1');
  expect(new Headers(fetch.mock.calls[1][1].headers).get('Authorization')).toBe('Bearer test-workspace-token');
});
it('keeps the workspace locked when authentication fails', async () => {
  const fetch = vi.fn().mockResolvedValueOnce({ ok: true, json: async () => ({ authentication_required: true }) }).mockResolvedValue({ ok: false });
  vi.stubGlobal('fetch', fetch); render(<AccessBoundary><p>Private workspace</p></AccessBoundary>);
  await userEvent.type(await screen.findByLabelText('Workspace access token'), 'invalid-test-token');
  await userEvent.click(screen.getByRole('button', { name: 'Unlock workspace' }));
  expect(await screen.findByRole('alert')).toHaveTextContent('Access token was rejected.');
  expect(screen.queryByText('Private workspace')).not.toBeInTheDocument();
});

it('does not reveal children when access configuration is unavailable', async () => {
  vi.stubGlobal('fetch', vi.fn().mockRejectedValue(new Error('Service unavailable')));
  render(<AccessBoundary><p>Private data</p></AccessBoundary>);
  expect(await screen.findByRole('alert')).toHaveTextContent('Service unavailable');
  expect(screen.queryByText('Private data')).not.toBeInTheDocument();
  expect(screen.getByRole('button', { name: 'Checking workspace…' })).toBeDisabled();
});

it('clears protected access and session identity when leaving the workspace', async () => {
  const fetch = vi.fn().mockImplementation(async (url: string) => ({ ok: true, json: async () => url === '/api/access' ? { authentication_required: true } : { items: [] } }));
  vi.stubGlobal('fetch', fetch);
  function Controls() {
    const session = useContext(WorkspaceSession);
    return <><p>{session.name}</p><button onClick={session.signOut}>Leave test workspace</button></>;
  }
  render(<AccessBoundary><Controls /></AccessBoundary>);
  await userEvent.type(await screen.findByLabelText('Your name (optional)'), 'Test reviewer');
  await userEvent.type(screen.getByLabelText('Workspace access token'), 'test-workspace-token');
  await userEvent.click(screen.getByRole('button', { name: 'Unlock workspace' }));
  expect(await screen.findByText('Test reviewer')).toBeInTheDocument();
  await userEvent.click(screen.getByRole('button', { name: 'Leave test workspace' }));
  expect(await screen.findByLabelText('Workspace access token')).toHaveValue('');
  expect(screen.getByLabelText('Your name (optional)')).toHaveValue('');
  await apiFetch('/api/check-cleared');
  expect(new Headers(fetch.mock.calls.at(-1)?.[1]?.headers).has('Authorization')).toBe(false);
});
it('sets up a password account, rejects confirmation mismatch and never stores credentials in browser storage', async () => {
  const fetch = vi.fn().mockImplementation(async (url: string) => ({ ok: true, json: async () => url === '/api/access' ? { authentication_required: true, auth_mode: 'password', setup_required: true, authenticated: false } : { username: 'aayush', authenticated: true } }));
  vi.stubGlobal('fetch', fetch);
  render(<AccessBoundary><p>Password workspace</p></AccessBoundary>);
  await userEvent.type(await screen.findByLabelText('Username'), 'aayush');
  await userEvent.type(screen.getByLabelText('Password'), 'Example-test-password-2026');
  await userEvent.type(screen.getByLabelText('Confirm password'), 'Different-test-password-2026');
  await userEvent.click(screen.getByRole('button', { name: 'Create account & continue' }));
  expect(await screen.findByRole('alert')).toHaveTextContent('Passwords do not match.');
  expect(fetch).toHaveBeenCalledTimes(1);
  await userEvent.clear(screen.getByLabelText('Confirm password'));
  await userEvent.type(screen.getByLabelText('Confirm password'), 'Example-test-password-2026');
  await userEvent.click(screen.getByRole('button', { name: 'Create account & continue' }));
  expect(await screen.findByText('Password workspace')).toBeInTheDocument();
  expect(fetch.mock.calls[1][0]).toBe('/api/auth/setup');
  expect(fetch.mock.calls[1][1].credentials).toBe('same-origin');
  expect(localStorage.length).toBe(0);
  expect(sessionStorage.length).toBe(0);
});

it('restores an authenticated server session without prompting for the password again', async () => {
  vi.stubGlobal('fetch', vi.fn().mockResolvedValue({ ok: true, json: async () => ({ authentication_required: true, auth_mode: 'password', setup_required: false, authenticated: true, username: 'owner' }) }));
  render(<AccessBoundary><p>Restored workspace</p></AccessBoundary>);
  expect(await screen.findByText('Restored workspace')).toBeInTheDocument();
  expect(screen.queryByLabelText('Password')).not.toBeInTheDocument();
});
