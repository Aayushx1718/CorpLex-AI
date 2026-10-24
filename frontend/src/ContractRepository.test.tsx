import { afterEach, expect, it, vi } from 'vitest';
import { cleanup, fireEvent, render, screen } from '@testing-library/react';
import ContractRepository from './ContractRepository';
import userEvent from '@testing-library/user-event';

const document = {
  id: 'doc-1', contract_id: 'contract-1', title: 'Synthetic vendor', contract_type: 'vendor',
  version_number: 1, original_filename: 'vendor.docx', extractor_version: 'rules-0.2.0',
  warnings: ['Review required.'], effective_date: '2026-03-01', expiration_date: null,
  entities: [{ kind: 'money', normalized_value: '12000.00', currency: 'USD', char_start: 8, char_end: 20 }],
  clauses: [{ id: 'clause-1', heading: 'Payment', text_content: 'Pay USD 12000.00', char_start: 0, char_end: 15 }],
  source_units: [{ kind: 'paragraph', number: 1, char_start: 0, char_end: 15 }],
  obligations: [{ id: 'obligation-1', kind: 'payment', description: 'Pay USD 12000.00', amount: '12000.00', currency: 'USD', recurrence: null, review_status: 'pending' }],
  canonical_text: 'Pay USD 12000.00', sha256: 'abc',
};
afterEach(() => { cleanup(); vi.unstubAllGlobals(); });
async function chooseFile() {
  const input = screen.getByLabelText('Document') as HTMLInputElement;
  await userEvent.upload(input, new File(['sample'], 'vendor.docx', { type: 'application/vnd.openxmlformats-officedocument.wordprocessingml.document' }));
}

it.each([false, true])('uploads real multipart data and handles duplicate=%s', async duplicate => {
  const fetch = vi.fn().mockImplementation(async (_url, options) => ({ ok: true, json: async () => options?.method === 'POST' ? { duplicate, document } : { items: [] } }));
  vi.stubGlobal('fetch', fetch);
  render(<ContractRepository />);
  await chooseFile();
  // jsdom native file validity does not see user-event's FileList override.
  fireEvent.submit(screen.getByRole('button', { name: 'Upload and extract' }).closest('form')!);
  expect(await screen.findByText('Synthetic vendor · v1')).toBeInTheDocument();
  expect(screen.getByText('USD 12000.00')).toBeInTheDocument();
  expect(screen.getByText('payment · pending')).toBeInTheDocument();
  expect(screen.getByText(duplicate ? /no duplicate was created/ : /Document ingested/)).toBeInTheDocument();
  const [, options] = fetch.mock.calls.find(([, opts]) => opts?.method === 'POST')!;
  expect(options.body).toBeInstanceOf(FormData);
  expect(options.body.get('contract_type')).toBe('vendor');
  expect(options.body.get('file').name).toBe('vendor.docx');
});

it('shows actionable server validation failures', async () => {
  vi.stubGlobal('fetch', vi.fn().mockImplementation(async (_url, options) => options?.method === 'POST'
    ? { ok: false, status: 422, json: async () => ({ detail: 'Encrypted PDFs are unsupported.' }) }
    : { ok: true, json: async () => ({ items: [] }) }));
  render(<ContractRepository />); await chooseFile();
  // jsdom native file validity does not see user-event's FileList override.
  fireEvent.submit(screen.getByRole('button', { name: 'Upload and extract' }).closest('form')!);
  expect(await screen.findByRole('alert')).toHaveTextContent('Encrypted PDFs are unsupported.');
});

it('opens an existing document and submits a selected version target', async () => {
  const fetch = vi.fn().mockImplementation(async (url, options) => ({ ok: true, json: async () => options?.method === 'POST' ? { duplicate: false, document: { ...document, version_number: 2 } } : url.startsWith('/api/documents/') ? document : { items: [{ ...document, document_id: 'doc-1' }] } }));
  vi.stubGlobal('fetch', fetch); render(<ContractRepository />);
  fireEvent.click(await screen.findByRole('button', { name: 'Inspect extraction' }));
  expect(await screen.findByText('Synthetic vendor · v1')).toBeInTheDocument();
  fireEvent.change(screen.getByLabelText('Version target'), { target: { value: 'contract-1' } });
  await chooseFile(); // jsdom native file validity does not see user-event's FileList override.
  fireEvent.submit(screen.getByRole('button', { name: 'Upload and extract' }).closest('form')!);
  expect(await screen.findByText('Synthetic vendor · v2')).toBeInTheDocument();
  const [, options] = fetch.mock.calls.find(([, opts]) => opts?.method === 'POST')!;
  expect(options.body.get('contract_id')).toBe('contract-1');
});
