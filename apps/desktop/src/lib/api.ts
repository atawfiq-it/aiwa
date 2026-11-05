import { get } from 'svelte/store';
import { API_BASE, sessionToken } from './stores';

export async function apiFetch(endpoint: string, options: RequestInit = {}): Promise<Response> {
  const token = get(sessionToken);
  const headers = new Headers(options.headers || {});

  if (token) {
    headers.set('X-AIWA-Token', token);
  }

  const url = endpoint.startsWith('http') ? endpoint : `${API_BASE}${endpoint}`;
  return fetch(url, { ...options, headers });
}
