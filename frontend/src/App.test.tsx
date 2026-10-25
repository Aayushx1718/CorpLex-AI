import { afterEach, expect, it, vi } from 'vitest';
import { cleanup, render, screen, fireEvent, waitFor } from '@testing-library/react';
import App from './App';
afterEach(() => { cleanup(); window.history.replaceState(null, '', '/'); vi.unstubAllGlobals(); vi.restoreAllMocks(); });
it('shows live API status and distinguishes future capabilities', async () => {
  vi.stubGlobal('fetch', vi.fn().mockImplementation(async (url: string) => ({ ok: true, json: async () => url.includes('/health') ? { status: 'ok' } : { items: [] } })));
  window.history.replaceState(null, '', '/#/status');
  render(<App />);
  expect(await screen.findByText('Connected')).toBeInTheDocument();
  expect(screen.getByText('Not activated')).toBeInTheDocument();
  expect(screen.getByRole('link', { name: 'System status' })).toHaveAttribute('aria-current', 'page');
  expect(screen.queryByRole('button', { name: 'Upload and extract' })).not.toBeInTheDocument();
});
it('reports an API failure', async () => {
  vi.stubGlobal('fetch', vi.fn().mockRejectedValue(new Error('offline')));
  window.history.replaceState(null, '', '/#/status');
  render(<App />);
  expect((await screen.findAllByText('Unavailable')).length).toBe(4);
});

it('opens separate workspace pages and responds to history navigation', async () => {
  vi.spyOn(window, 'scrollTo').mockImplementation(() => {});
  vi.stubGlobal('fetch', vi.fn().mockResolvedValue({ ok: true, json: async () => ({ status: 'ok', items: [] }) }));
  render(<App />);
  fireEvent.click(screen.getByRole('link', { name: 'Contract repository' }));
  expect(await screen.findByRole('button', { name: 'Upload and extract' })).toBeInTheDocument();
  expect(screen.queryByRole('heading', { name: /A clearer view/ })).not.toBeInTheDocument();
  expect(screen.getByRole('link', { name: 'Contract repository' })).toHaveAttribute('aria-current', 'page');
  fireEvent.click(screen.getByRole('link', { name: 'Dashboard' }));
  await waitFor(() => expect(screen.queryByRole('button', { name: 'Upload and extract' })).not.toBeInTheDocument());
  window.history.back();
  expect(await screen.findByRole('button', { name: 'Upload and extract' })).toBeInTheDocument();
  window.history.forward();
  expect(await screen.findByRole('heading', { name: /A clearer view/ })).toBeInTheDocument();
});
it('opens a bookmarked workspace directly', async () => {
  window.history.replaceState(null, '', '/#/contracts');
  vi.stubGlobal('fetch', vi.fn().mockResolvedValue({ ok: true, json: async () => ({ items: [] }) }));
  render(<App />);
  expect(await screen.findByRole('button', { name: 'Upload and extract' })).toBeInTheDocument();
  expect(screen.queryByRole('heading', { name: /A clearer view/ })).not.toBeInTheDocument();
});
