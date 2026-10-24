import { afterEach, expect, it, vi } from 'vitest';
import { cleanup, render, screen } from '@testing-library/react';
import ModelLab from './ModelLab';
afterEach(() => { cleanup(); vi.unstubAllGlobals(); });
const status = {
  task: 'clause_type', model_available: false, risk_model_available: false, status: 'license_verification_pending',
  message: 'Training withheld until license verification succeeds.', report: null,
  dataset: { dataset: 'CUAD adaptation', source_url: 'https://github.com/TheAtticusProject/cuad', citation: 'CUAD (2021)',
    license: { name: 'CC-BY-4.0 (verification pending)', verified: false },
    counts: { train: { 'Anti-Assignment': 396 }, validation: { 'Anti-Assignment': 78 }, calibration: { 'Anti-Assignment': 54 }, test: { 'Anti-Assignment': 92 } } },
};
it('shows dataset counts while withholding untrained metrics and predictions', async () => {
  vi.stubGlobal('fetch', vi.fn().mockResolvedValue({ ok: true, json: async () => status }));
  render(<ModelLab />);
  expect(await screen.findByText('396')).toBeInTheDocument();
  expect(screen.getByText('Pending')).toBeInTheDocument();
  expect(screen.getByRole('button', { name: 'Classify clause type' })).toBeDisabled();
  expect(screen.getByLabelText('Clause text')).toBeDisabled();
  expect(screen.getByText(/results are withheld/)).toBeInTheDocument();
  expect(screen.queryByText('Held-out model comparison')).not.toBeInTheDocument();
});
it('handles missing datasets without inventing model results', async () => {
  vi.stubGlobal('fetch', vi.fn().mockResolvedValue({ ok: true, json: async () => ({ ...status, dataset: null }) }));
  render(<ModelLab />);
  expect(await screen.findByText('Not active')).toBeInTheDocument();
  expect(screen.queryByText('Dataset provenance and split support')).not.toBeInTheDocument();
});
it('reports a model-status service failure', async () => {
  vi.stubGlobal('fetch', vi.fn().mockResolvedValue({ ok: false }));
  render(<ModelLab />);
  expect(await screen.findByRole('alert')).toHaveTextContent('Could not load model status.');
});
