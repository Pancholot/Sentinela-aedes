// Cliente HTTP del backend (FastAPI en Render).
export const API_URL = (import.meta.env.VITE_API_URL || 'http://localhost:8000').replace(/\/$/, '');

async function request(path, { method = 'GET', body } = {}) {
  const ctrl = new AbortController();
  // El plan gratuito de Render "duerme" el servidor: el primer request puede tardar ~1 min.
  const timer = setTimeout(() => ctrl.abort(), 75000);
  try {
    const res = await fetch(API_URL + path, {
      method,
      headers: body ? { 'Content-Type': 'application/json' } : undefined,
      body: body ? JSON.stringify(body) : undefined,
      signal: ctrl.signal,
    });
    const data = await res.json().catch(() => ({}));
    if (!res.ok) {
      const err = new Error(data.detail || `Error HTTP ${res.status}`);
      err.status = res.status;
      throw err;
    }
    return data;
  } finally {
    clearTimeout(timer);
  }
}

export const api = {
  get: (path) => request(path),
  post: (path, body) => request(path, { method: 'POST', body: body || {} }),
};
