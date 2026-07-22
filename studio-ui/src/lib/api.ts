/**
 * Where the backend lives, and how to reach it.
 *
 * Locally the Python API is on 127.0.0.1:7788 and needs no token. When the
 * laptop is exposed through a tunnel, the deployed site is pointed at it by
 * opening the page once with ?api=<url>&token=<token> — both are remembered in
 * localStorage, so the query string only has to be used the first time (and
 * after the tunnel URL changes).
 */
const LS_API = 'tg.api'
const LS_TOKEN = 'tg.token'

function boot(key: string, param: string, fallback = ''): string {
  if (typeof window === 'undefined') return fallback
  const q = new URLSearchParams(window.location.search).get(param)
  if (q !== null) {
    // Empty value clears it — handy for getting back to the local default.
    if (q) localStorage.setItem(key, q)
    else localStorage.removeItem(key)
  }
  return localStorage.getItem(key) || fallback
}

export const IS_LOCAL = typeof window !== 'undefined'
  && /^(localhost|127\.0\.0\.1)$/.test(window.location.hostname)

/** Trailing slash stripped so `API + '/ask'` never produces a double slash. */
export const API = boot(LS_API, 'api', IS_LOCAL ? 'http://127.0.0.1:7788' : '')
  .replace(/\/$/, '')

export const TOKEN = boot(LS_TOKEN, 'token')

export const HAS_BACKEND = !!API

/** fetch() against the API with the token attached, if there is one. */
export function apiFetch(path: string, init: RequestInit = {}) {
  if (!API) return Promise.reject(new Error('no backend configured'))
  const headers = new Headers(init.headers || {})
  if (TOKEN) headers.set('X-TG-Token', TOKEN)
  // ngrok's free tier serves an HTML interstitial to anything that looks like a
  // browser; this header opts out and gets the real JSON back.
  headers.set('ngrok-skip-browser-warning', '1')
  return fetch(API + path, { ...init, headers })
}

/**
 * URL for a 3D graph view. The token goes in the query string because an
 * iframe cannot send headers.
 */
export function graphUrl(view = 'FULL_3plane_clean.html'): string {
  if (!API) return ''
  return `${API}/graph/${view}${TOKEN ? `?token=${encodeURIComponent(TOKEN)}` : ''}`
}
