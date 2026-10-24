import { afterEach, expect, it, vi } from 'vitest';
import { cleanup, render, screen } from '@testing-library/react';
import App from './App';
afterEach(() => { cleanup(); vi.unstubAllGlobals(); });
it('shows live API status and distinguishes future capabilities', async () => {
  vi.stubGlobal('fetch', vi.fn().mockImplementation(async (url: string) => ({ ok: true, json: async () => url.includes('/health') ? { status: 'ok' } : { items: [] } })));
  render(<App />);
  expect(await screen.findByText('Connected')).toBeInTheDocument();
  expect(screen.getByText('Not trained')).toBeInTheDocument();
  expect(screen.getAllByText('Planned')).toHaveLength(3);
  expect(screen.getByRole('button', { name: 'Upload and extract' })).toBeInTheDocument();
});
it('reports an API failure', async () => {
  vi.stubGlobal('fetch', vi.fn().mockRejectedValue(new Error('offline')));
  render(<App />);
  expect(await screen.findByText('Unavailable')).toBeInTheDocument();
});
