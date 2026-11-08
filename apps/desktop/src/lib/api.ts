import { get } from 'svelte/store';
import { API_BASE, sessionToken } from './stores';

export async function ensureToken(): Promise<string> {
  // 1. In dev mode, always fetch the active token directly from backend loopback first
  try {
    const res = await fetch(`${API_BASE}/auth/dev-token`);
    if (res.ok) {
      const data = await res.json();
      if (data.token) {
        sessionToken.set(data.token);
        localStorage.setItem('aiwa_session_token', data.token);
        return data.token;
      }
    }
  } catch {}

  // 2. Fallback to Tauri native bridge
  try {
    const { invoke } = await import('@tauri-apps/api/core');
    const nativeToken = await invoke<string>('get_session_token');
    if (nativeToken) {
      sessionToken.set(nativeToken);
      localStorage.setItem('aiwa_session_token', nativeToken);
      return nativeToken;
    }
  } catch {}

  // 3. Fallback to localStorage
  const saved = localStorage.getItem('aiwa_session_token');
  if (saved) {
    sessionToken.set(saved);
    return saved;
  }

  return '';
}

export async function apiFetch(endpoint: string, options: RequestInit = {}): Promise<Response> {
  let token = await ensureToken();
  const headers = new Headers(options.headers || {});

  if (token) {
    headers.set('X-AIWA-Token', token);
  }

  const url = endpoint.startsWith('http') ? endpoint : `${API_BASE}${endpoint}`;
  let response = await fetch(url, { ...options, headers });

  // If rejected with 401 Unauthorized, token is stale: force refresh and retry once
  if (response.status === 401) {
    localStorage.removeItem('aiwa_session_token');
    sessionToken.set('');
    token = await ensureToken();
    if (token) {
      headers.set('X-AIWA-Token', token);
      response = await fetch(url, { ...options, headers });
    }
  }

  return response;
}
