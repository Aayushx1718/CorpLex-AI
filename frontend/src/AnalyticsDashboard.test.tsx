import { afterEach, expect, it, vi } from 'vitest';
import { cleanup, render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import AnalyticsDashboard from './AnalyticsDashboard';
// jsdom has no layout engine; browser smoke checks exercise the actual charts.
vi.mock('recharts', () => ({
  ResponsiveContainer: ({ children }: { children: React.ReactNode }) => <div>{children}</div>,
  BarChart: () => <div>Obligation chart</div>, PieChart: () => <div>Agreement chart</div>,
  Bar: () => null, Pie: () => null, Cell: () => null, CartesianGrid: () => null,
  XAxis: () => null, YAxis: () => null, Tooltip: () => null,
}));
const overview = {
  as_of: '2026-03-01', through: '2026-05-30', limit: 20, offset: 0,
  kpis: { contracts: 1, obligations: 2, pending_review: 2, missing_expiration: 0, expiring: 1, past_due_dates: 0, missing_due_dates: 2 },
  by_type: [{ contract_type: 'vendor', count: 1 }], by_kind: [{ kind: 'payment', review_status: 'pending', count: 2 }],
  amount_groups: [
    { currency: 'USD', kind: 'payment', recurrence: 'monthly', review_status: 'pending', count: 1, amount: '9007199254740993.1234' },
    { currency: 'EUR', kind: 'payment', recurrence: null, review_status: 'pending', count: 1, amount: '30.0000' },
  ],
  contracts: [{ contract_id: 'c1', document_id: 'd2', title: 'Vendor v2', contract_type: 'vendor', version_number: 2, party_names: ['Buyer', 'Vendor'], obligations: 2, pending_review: 2, expiration_date: '2026-04-01' }],
  deadlines: [], deadline_total: 0,
};
afterEach(() => { cleanup(); vi.unstubAllGlobals(); });
function mockData(data = overview) {
  const fetch = vi.fn().mockResolvedValue({ ok: true, json: async () => data });
  vi.stubGlobal('fetch', fetch); return fetch;
}

it('renders precise separate currencies, recurrence and source links', async () => {
  mockData(); const inspect = vi.fn(); render(<AnalyticsDashboard onInspect={inspect} />);
  expect(await screen.findByText('9007199254740993.1234')).toBeInTheDocument();
  expect(screen.getByText('30.0000')).toBeInTheDocument();
  expect(screen.getByText('monthly')).toBeInTheDocument();
  expect(screen.getByText('Unspecified')).toBeInTheDocument();
  expect(screen.getByText(/Past due dates do not prove nonpayment/)).toBeInTheDocument();
  await userEvent.click(screen.getByRole('link', { name: 'Vendor v2' }));
  expect(inspect).toHaveBeenCalledWith('d2');
});

it('applies filters together and refreshes after ingestion', async () => {
  const fetch = mockData(); const { rerender } = render(<AnalyticsDashboard refreshKey={0} />);
  await screen.findByText('9007199254740993.1234');
  await userEvent.selectOptions(screen.getByLabelText('Analytics currency'), 'EUR');
  await userEvent.selectOptions(screen.getByLabelText('Analytics agreement type'), 'vendor');
  await userEvent.selectOptions(screen.getByLabelText('Analytics review state'), 'pending');
  await userEvent.type(screen.getByLabelText('Analytics as-of date'), '2026-03-01');
  await userEvent.click(screen.getByRole('button', { name: 'Apply filters' }));
  await waitFor(() => expect(fetch).toHaveBeenCalledTimes(2));
  const query = new URL(fetch.mock.calls[1][0], 'http://test').searchParams;
  expect(query.get('currency')).toBe('EUR'); expect(query.get('contract_type')).toBe('vendor');
  expect(query.get('review_status')).toBe('pending'); expect(query.get('as_of')).toBe('2026-03-01');
  rerender(<AnalyticsDashboard refreshKey={1} />);
  await waitFor(() => expect(fetch).toHaveBeenCalledTimes(3));
});

it('shows an empty state without fabricated charts or amounts', async () => {
  mockData({ ...overview, kpis: { ...overview.kpis, contracts: 0 }, contracts: [], amount_groups: [], by_kind: [], by_type: [] });
  render(<AnalyticsDashboard />);
  expect(await screen.findByText(/No agreements match these filters/)).toBeInTheDocument();
  expect(screen.queryByText('Agreement chart')).not.toBeInTheDocument();
});

it('reports and retries a database failure', async () => {
  const fetch = vi.fn().mockResolvedValueOnce({ ok: false, status: 503, json: async () => ({ detail: 'Analytics unavailable.' }) })
    .mockResolvedValue({ ok: true, json: async () => overview });
  vi.stubGlobal('fetch', fetch); render(<AnalyticsDashboard />);
  expect(await screen.findByRole('alert')).toHaveTextContent('Analytics unavailable.');
  await userEvent.click(screen.getByRole('button', { name: 'Retry analytics' }));
  expect(await screen.findByText('9007199254740993.1234')).toBeInTheDocument();
});

it('paginates the register without requesting a different filter scope', async () => {
  const fetch = mockData({ ...overview, kpis: { ...overview.kpis, contracts: 21 } });
  render(<AnalyticsDashboard />); await screen.findByText('9007199254740993.1234');
  await userEvent.click(screen.getByRole('button', { name: 'Next agreements' }));
  await waitFor(() => expect(fetch).toHaveBeenCalledTimes(2));
  expect(new URL(fetch.mock.calls[1][0], 'http://test').searchParams.get('offset')).toBe('20');
});

it('shows live summary charts and a bounded register without the full analytics forms', async () => {
  mockData({ ...overview, contracts: Array.from({ length: 8 }, (_, i) => ({ ...overview.contracts[0], contract_id: `c${i}`, document_id: `d${i}`, title: `Demo ${i}` })) });
  render(<AnalyticsDashboard summary />);
  expect(await screen.findByText('Agreement chart')).toBeInTheDocument();
  expect(screen.getByText('Obligation chart')).toBeInTheDocument();
  expect(screen.queryByRole('button', { name: 'Apply filters' })).not.toBeInTheDocument();
  expect(screen.getByRole('link', { name: 'Demo 5' })).toHaveAttribute('href', '#/contracts');
  expect(screen.queryByRole('link', { name: 'Demo 6' })).not.toBeInTheDocument();
  expect(screen.queryByText('9007199254740993.1234')).not.toBeInTheDocument();
});
