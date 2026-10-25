// Tokens remain in memory only and are never placed in URLs or browser storage.
let accessToken = '';
export function setAccessToken(value: string) { accessToken = value; }
export function apiFetch(input: RequestInfo | URL, init?: RequestInit): Promise<Response> {
  if (!accessToken) return globalThis.fetch(input, init);
  const headers = new Headers(init?.headers);
  headers.set('Authorization', `Bearer ${accessToken}`);
  return globalThis.fetch(input, { ...init, headers });
}
export async function jsonResponse(response: Response) {
  const data = await response.json().catch(() => ({}));
  if (!response.ok) throw new Error(typeof data.detail === 'string' ? data.detail : `Request failed (${response.status}). Check inputs and workspace access.`);
  return data;
}
