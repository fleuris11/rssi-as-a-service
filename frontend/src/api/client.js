import axios from 'axios'

// ?? (not ||): an explicitly empty VITE_API_URL ('' — set at Docker build
// time in production, see deploy/Dockerfile.caddy) must mean "same origin"
// (axios treats an empty baseURL as relative-to-current-origin, which is
// correct behind Caddy's reverse proxy) — || would treat '' as unset and
// wrongly fall back to the localhost dev default.
const API_BASE_URL = import.meta.env.VITE_API_URL ?? 'http://localhost:8000'

const STORAGE_KEYS = {
  access: 'rssi.access',
  refresh: 'rssi.refresh',
  tenantId: 'rssi.tenantId',
}

export const tokenStorage = {
  getAccess: () => localStorage.getItem(STORAGE_KEYS.access),
  getRefresh: () => localStorage.getItem(STORAGE_KEYS.refresh),
  getTenantId: () => localStorage.getItem(STORAGE_KEYS.tenantId),
  setTokens: (access, refresh) => {
    localStorage.setItem(STORAGE_KEYS.access, access)
    localStorage.setItem(STORAGE_KEYS.refresh, refresh)
  },
  setAccess: (access) => localStorage.setItem(STORAGE_KEYS.access, access),
  setTenantId: (tenantId) => {
    if (tenantId) {
      localStorage.setItem(STORAGE_KEYS.tenantId, tenantId)
    } else {
      localStorage.removeItem(STORAGE_KEYS.tenantId)
    }
  },
  clear: () => {
    localStorage.removeItem(STORAGE_KEYS.access)
    localStorage.removeItem(STORAGE_KEYS.refresh)
    localStorage.removeItem(STORAGE_KEYS.tenantId)
  },
}

export const apiClient = axios.create({ baseURL: API_BASE_URL })

apiClient.interceptors.request.use((config) => {
  const access = tokenStorage.getAccess()
  if (access) {
    config.headers.Authorization = `Bearer ${access}`
  }
  const tenantId = tokenStorage.getTenantId()
  if (tenantId) {
    config.headers['X-Tenant-Id'] = tenantId
  }
  return config
})

let refreshPromise = null

async function refreshAccessToken() {
  const refresh = tokenStorage.getRefresh()
  if (!refresh) {
    throw new Error('Aucun jeton de rafraîchissement disponible.')
  }
  // Rotation (backend/config/settings.py: ROTATE_REFRESH_TOKENS) means each
  // refresh call returns a new refresh token too — the old one is
  // blacklisted server-side, so it must be replaced, not just the access.
  const response = await axios.post(`${API_BASE_URL}/api/v1/auth/token/refresh/`, { refresh })
  tokenStorage.setTokens(response.data.access, response.data.refresh)
  return response.data.access
}

apiClient.interceptors.response.use(
  (response) => response,
  async (error) => {
    const { config, response } = error
    // skipAuthRetry: some endpoints return 401 for a business reason (e.g.
    // POST .../reveal/'s step-up re-authentication rejecting a wrong
    // password/TOTP code) rather than an expired access token — retrying
    // those after a token refresh would silently resubmit the same
    // (still-wrong) credentials a second time against the server, double
    // counting against its rate limit and audit log for a single mistake.
    if (
      response?.status === 401 &&
      !config._retried &&
      !config.skipAuthRetry &&
      tokenStorage.getRefresh()
    ) {
      config._retried = true
      try {
        if (!refreshPromise) {
          refreshPromise = refreshAccessToken().finally(() => {
            refreshPromise = null
          })
        }
        const access = await refreshPromise
        config.headers.Authorization = `Bearer ${access}`
        return apiClient(config)
      } catch {
        tokenStorage.clear()
      }
    }
    return Promise.reject(error)
  }
)
