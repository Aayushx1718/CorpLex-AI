import { afterEach, expect, it, vi } from 'vitest';
import { cleanup, render, screen, fireEvent, waitFor } from '@testing-library/react';
import App from './App';
afterEach(() => { cleanup(); window.history.replaceState(null, '', '/'); vi.unstubAllGlobals(); vi.restoreAllMocks(); });
it('shows live API status and distinguishes future capabilities', async () => {
  vi.stubGlobal('fetch', vi.fn().mockImplementation(async (url: string) => ({ ok: true, json: async () => url.includes('/health') ? { status: 'ok' } : { items: [] } })));
  render(<App />);
  expect(await screen.findByText('Connected')).toBeInTheDocument();
  expect(screen.getByText('Not trained')).toBeInTheDocument();
  expect(screen.getByText('Contract intelligence workspace')).toBeInTheDocument();
  expect(screen.queryByRole('button', { name: 'Upload and extract' })).not.toBeInTheDocument();
});
it('reports an API failure', async () => {
  vi.stubGlobal('fetch', vi.fn().mockRejectedValue(new Error('offline')));
  render(<App />);
  expect(await screen.findByText('Unavailable')).toBeInTheDocument();
});

it('opens separate workspace pages and responds to history navigation', async () => {
  vi.spyOn(window, 'scrollTo').mockImplementation(() => {});
  vi.stubGlobal('fetch', vi.fn().mockResolvedValue({ ok: true, json: async () => ({ status: 'ok', items: [] }) }));
  render(<App />);
  fireEvent.click(screen.getByRole('link', { name: 'Contract repository' }));
  expect(await screen.findByRole('button', { name: 'Upload and extract' })).toBeInTheDocument();
  expect(screen.queryByRole('heading', { name: /Understand the agreement/ })).not.toBeInTheDocument();
  expect(screen.getByRole('link', { name: 'Contract repository' })).toHaveAttribute('aria-current', 'page');
  fireEvent.click(screen.getByRole('link', { name: 'Executive overview' }));
  await waitFor(() => expect(screen.queryByRole('button', { name: 'Upload and extract' })).not.toBeInTheDocument());
  window.history.back();
  expect(await screen.findByRole('button', { name: 'Upload and extract' })).toBeInTheDocument();
  window.history.forward();
  expect(await screen.findByRole('heading', { name: /Understand the agreement/ })).toBeInTheDocument();
});
it('opens a bookmarked workspace directly', async () => {
  window.history.replaceState(null, '', '/#/contracts');
  vi.stubGlobal('fetch', vi.fn().mockResolvedValue({ ok: true, json: async () => ({ items: [] }) }));
  render(<App />);
  expect(await screen.findByRole('button', { name: 'Upload and extract' })).toBeInTheDocument();
  expect(screen.queryByRole('heading', { name: /Understand the agreement/ })).not.toBeInTheDocument();
});
