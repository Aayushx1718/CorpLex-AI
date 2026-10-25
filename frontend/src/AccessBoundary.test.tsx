import { afterEach, expect, it, vi } from 'vitest';
import { cleanup, render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import AccessBoundary from './AccessBoundary';
import { setAccessToken } from './api';
afterEach(() => { cleanup(); setAccessToken(''); vi.unstubAllGlobals(); });
it('opens local development without requiring a token', async () => {
  vi.stubGlobal('fetch', vi.fn().mockResolvedValue({ json: async () => ({ authentication_required: false }) }));
  render(<AccessBoundary><p>Workspace content</p></AccessBoundary>);
  expect(screen.getByText('Workspace content')).toBeInTheDocument();
});
it('requires a valid token and sends it in the header', async () => {
  const fetch = vi.fn().mockResolvedValueOnce({ json: async () => ({ authentication_required: true }) }).mockResolvedValue({ ok: true });
  vi.stubGlobal('fetch', fetch); render(<AccessBoundary><p>Unlocked content</p></AccessBoundary>);
  await userEvent.type(await screen.findByLabelText('Workspace access token'), 'test-workspace-token');
  await userEvent.click(screen.getByRole('button', { name: 'Unlock workspace' }));
  expect(await screen.findByText('Unlocked content')).toBeInTheDocument();
  expect(fetch.mock.calls[1][0]).toBe('/api/contracts?limit=1');
  expect(new Headers(fetch.mock.calls[1][1].headers).get('Authorization')).toBe('Bearer test-workspace-token');
});
it('keeps the workspace locked when authentication fails', async () => {
  const fetch = vi.fn().mockResolvedValueOnce({ json: async () => ({ authentication_required: true }) }).mockResolvedValue({ ok: false });
  vi.stubGlobal('fetch', fetch); render(<AccessBoundary><p>Private workspace</p></AccessBoundary>);
  await userEvent.type(await screen.findByLabelText('Workspace access token'), 'invalid-test-token');
  await userEvent.click(screen.getByRole('button', { name: 'Unlock workspace' }));
  expect(await screen.findByRole('alert')).toHaveTextContent('Access token was rejected.');
  expect(screen.queryByText('Private workspace')).not.toBeInTheDocument();
});
