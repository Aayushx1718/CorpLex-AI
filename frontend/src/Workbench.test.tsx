import { afterEach, expect, it, vi } from 'vitest';
import { cleanup, render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import Workbench from './Workbench';
import { setAccessToken, apiFetch } from './api';
const choices = [{ id: 'doc1', title: 'Synthetic vendor', version_number: 1, contract_type: 'vendor' }, { id: 'doc2', title: 'Synthetic vendor', version_number: 2, contract_type: 'vendor' }];
const obligation = { id: 'o1', kind: 'payment', description: 'Pay USD 100.00 monthly.', amount: '100.00', currency: 'USD', review_status: 'pending' };
const run = { id: 'run1', state: 'awaiting_review', report: { title: 'Synthetic vendor', version_number: 1, trace: ['Document Extraction Agent', 'Report Generation Agent'], clauses: [], risk: { review_cues: [], validated_risk_model: false }, notice: 'Review required.', financial_notice: 'No inferred losses.' } };
afterEach(() => { cleanup(); setAccessToken(''); vi.unstubAllGlobals(); });
function mockFetch() {
  const fetch = vi.fn().mockImplementation(async (url: string, init?: RequestInit) => {
    let body: unknown = {};
    if (url === '/api/workbench/documents') body = { items: choices, total: 2 };
    else if (url === '/api/research/status') body = { hosted_configured: false };
    else if (url === '/api/access') body = { reviewer_token_required: false };
    else if (url.startsWith('/api/documents/')) body = { obligations: [obligation] };
    else if (url === '/api/research/ask') body = { answer: '[1] Pay USD 100.00 monthly.', abstained: false, citations: [{ number: 1, document_id: 'doc1', title: 'Synthetic vendor', version_number: 1, quote: 'Pay USD 100.00 monthly.', char_start: 0, char_end: 23, source_units: [{ kind: 'paragraph', number: 1 }] }], notice: 'Not legal advice.' };
    else if (url === '/api/finance/scenarios') body = { id: 's1', amount: '300.0000', currency: 'USD', formula: 'rate × quantity', notice: 'Hypothetical only.', lines: [] };
    else if (url === '/api/workflows') body = run;
    else if (url.includes('/review')) body = { ...run, state: 'approved' };
    return { ok: true, json: async () => body };
  });
  vi.stubGlobal('fetch', fetch); return fetch;
}
it('retrieves cited evidence with an explicit version filter and no unconfigured hosted mode', async () => {
  const fetch = mockFetch(); const inspect = vi.fn(); render(<Workbench onInspect={inspect} />);
  await screen.findByRole('option', { name: 'Synthetic vendor · v1 · vendor' });
  await userEvent.selectOptions(screen.getByLabelText('Workbench source version'), 'doc1');
  await userEvent.type(screen.getByLabelText('Contract research question'), 'What payment terms apply?');
  await userEvent.click(screen.getByRole('button', { name: 'Research contract' }));
  expect(await screen.findByText('Retrieved source evidence')).toBeInTheDocument();
  await userEvent.click(screen.getByRole('link', { name: 'Inspect source' }));
  expect(inspect).toHaveBeenCalledWith('doc1');
  const request = fetch.mock.calls.find(([url]) => url === '/api/research/ask')!;
  expect(JSON.parse(request[1]!.body as string).document_ids).toEqual(['doc1']);
  expect(screen.getByRole('option', { name: /key not configured/ })).toBeDisabled();
});
it('sends exact decimal strings and requires explicit scenario assumptions', async () => {
  const fetch = mockFetch(); render(<Workbench />);
  await screen.findByRole('option', { name: 'Synthetic vendor · v1 · vendor' });
  await userEvent.click(screen.getByRole('tab', { name: 'What-if scenarios' }));
  await userEvent.selectOptions(screen.getByLabelText('Workbench source version'), 'doc1');
  await screen.findByRole('option', { name: /payment · USD 100.00/ });
  await userEvent.selectOptions(screen.getByLabelText('Scenario obligation'), 'o1');
  await userEvent.clear(screen.getByLabelText('Scenario quantity')); await userEvent.type(screen.getByLabelText('Scenario quantity'), '3');
  await userEvent.type(screen.getByLabelText('Scenario assumptions'), 'Assume three monthly payments for this test.');
  await userEvent.click(screen.getByRole('checkbox', { name: 'Explicitly include unreviewed candidates' }));
  await userEvent.click(screen.getByRole('button', { name: 'Calculate hypothetical scenario' }));
  expect(await screen.findByText('Hypothetical amount: USD 300.0000')).toBeInTheDocument();
  const request = fetch.mock.calls.find(([url]) => url === '/api/finance/scenarios')!;
  const body = JSON.parse(request[1]!.body as string);
  expect(body.lines[0].quantity).toBe('3'); expect(body.include_unreviewed).toBe(true);
});
it('keeps report export disabled until an explicit reviewer decision', async () => {
  mockFetch(); const reviewed = vi.fn(); render(<Workbench onReviewed={reviewed} />);
  await screen.findByRole('option', { name: 'Synthetic vendor · v1 · vendor' });
  await userEvent.click(screen.getByRole('tab', { name: 'Review workflow' }));
  await userEvent.selectOptions(screen.getByLabelText('Workbench source version'), 'doc1');
  await userEvent.click(screen.getByRole('button', { name: 'Generate or reopen review report' }));
  expect(await screen.findByRole('button', { name: 'Download approved report' })).toBeDisabled();
  await userEvent.type(screen.getByLabelText('Reviewer name'), 'Demo reviewer');
  await userEvent.type(screen.getByLabelText('Review note'), 'Compared terms against the stored source.');
  await userEvent.click(screen.getByRole('button', { name: 'Approve reviewed report' }));
  await waitFor(() => expect(screen.getByRole('button', { name: 'Download approved report' })).toBeEnabled());
  expect(reviewed).toHaveBeenCalled();
});
it('keeps access tokens out of request URLs', async () => {
  const fetch = vi.fn().mockResolvedValue({ ok: true }); vi.stubGlobal('fetch', fetch);
  setAccessToken('test-token'); await apiFetch('/api/contracts');
  expect(fetch.mock.calls[0][0]).toBe('/api/contracts');
  expect(new Headers(fetch.mock.calls[0][1].headers).get('Authorization')).toBe('Bearer test-token');
});
