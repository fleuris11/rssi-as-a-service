import { apiClient } from './client'

export const authApi = {
  register: (payload) => apiClient.post('/api/v1/auth/register/', payload),
  login: (email, password) => apiClient.post('/api/v1/auth/token/', { email, password }),
  verifyTwoFactor: (challengeToken, { code = '', recoveryCode = '' } = {}) =>
    apiClient.post('/api/v1/auth/token/verify-2fa/', {
      challenge_token: challengeToken,
      code,
      recovery_code: recoveryCode,
    }),
  me: () => apiClient.get('/api/v1/auth/me/'),
}

export const twoFactorApi = {
  status: () => apiClient.get('/api/v1/auth/2fa/status/'),
  setup: () => apiClient.post('/api/v1/auth/2fa/setup/'),
  confirm: (code) => apiClient.post('/api/v1/auth/2fa/confirm/', { code }),
  disable: (password) => apiClient.post('/api/v1/auth/2fa/disable/', { password }),
}

export const tenantsApi = {
  listMine: () => apiClient.get('/api/v1/tenants/'),
  listMembers: () => apiClient.get('/api/v1/tenants/members/'),
}

export const assessmentsApi = {
  referential: () => apiClient.get('/api/v1/assessments/referential/'),
  start: () => apiClient.post('/api/v1/assessments/start/'),
  current: () => apiClient.get('/api/v1/assessments/current/'),
  list: () => apiClient.get('/api/v1/assessments/'),
  detail: (id) => apiClient.get(`/api/v1/assessments/${id}/`),
  submitAnswer: (assessmentId, measureId, value, note = '') =>
    apiClient.put(`/api/v1/assessments/${assessmentId}/answers/${measureId}/`, { value, note }),
  complete: (id) => apiClient.post(`/api/v1/assessments/${id}/complete/`),
  scores: (id) => apiClient.get(`/api/v1/assessments/${id}/scores/`),
}

export const actionsApi = {
  list: (params = {}) => apiClient.get('/api/v1/actions/', { params }),
  // The kanban board wants every item at once (unlike a normal list view) —
  // walks DRF's paginated "next" links (page_size=20) rather than showing
  // only page 1 of a tenant's plan.
  listAll: async (params = {}) => {
    const results = []
    let url = '/api/v1/actions/'
    let requestParams = params
    while (url) {
      const response = await apiClient.get(url, { params: requestParams })
      results.push(...response.data.results)
      url = response.data.next
      requestParams = undefined
    }
    return results
  },
  update: (id, payload) => apiClient.patch(`/api/v1/actions/${id}/`, payload),
  projectedScore: (assessmentId) =>
    apiClient.get('/api/v1/actions/projected-score/', {
      params: assessmentId ? { assessment: assessmentId } : {},
    }),
}

export const monitoringApi = {
  listAssets: () => apiClient.get('/api/v1/monitoring/assets/'),
  createAsset: (payload) => apiClient.post('/api/v1/monitoring/assets/', payload),
  updateAsset: (id, payload) => apiClient.patch(`/api/v1/monitoring/assets/${id}/`, payload),
  deleteAsset: (id) => apiClient.delete(`/api/v1/monitoring/assets/${id}/`),
  assetCheckHistory: (id, checkType) =>
    apiClient.get(`/api/v1/monitoring/assets/${id}/checks/`, {
      params: checkType ? { check_type: checkType } : {},
    }),
  dashboard: () => apiClient.get('/api/v1/monitoring/dashboard/'),
  openAlerts: () => apiClient.get('/api/v1/monitoring/alerts/'),
}

export const threatIntelligenceApi = {
  listFindings: (status) =>
    apiClient.get('/api/v1/threat-intelligence/findings/', { params: status ? { status } : {} }),
  updateFindingStatus: (id, status) =>
    apiClient.patch(`/api/v1/threat-intelligence/findings/${id}/`, { status }),
  // Step-up re-authentication (ADR-014) : mot de passe OU code TOTP, jamais
  // mis en cache côté client — chaque appel doit re-fournir l'un des deux.
  // skipAuthRetry : un 401 ici signifie "identifiants de step-up rejetés",
  // pas "jeton d'accès expiré" — sans ce flag, l'intercepteur retenterait la
  // requête après rafraîchissement du jeton, soumettant deux fois le même
  // mot de passe/code invalide (double comptage dans le rate limit et le
  // journal d'audit pour une seule erreur de saisie).
  revealFindingSecret: (id, { password = '', totpCode = '' } = {}) =>
    apiClient.post(
      `/api/v1/threat-intelligence/findings/${id}/reveal/`,
      { password, totp_code: totpCode },
      { skipAuthRetry: true }
    ),
  preIncident: (status) =>
    apiClient.get('/api/v1/threat-intelligence/pre-incident/', {
      params: status ? { status } : {},
    }),
  exposureFeed: () => apiClient.get('/api/v1/threat-intelligence/exposure-feed/'),
  refreshExposureSynthesis: () =>
    apiClient.post('/api/v1/threat-intelligence/exposure-feed/synthesis/'),
  listRevealAudit: () => apiClient.get('/api/v1/threat-intelligence/audit/reveals/'),
  listMonitoredAssets: () => apiClient.get('/api/v1/threat-intelligence/monitored-assets/'),
  registerMonitoredAsset: (assetId) =>
    apiClient.post('/api/v1/threat-intelligence/monitored-assets/', { asset_id: assetId }),
  unregisterMonitoredAsset: (assetId) =>
    apiClient.delete(`/api/v1/threat-intelligence/monitored-assets/${assetId}/`),
  triggerScan: (assetId) =>
    apiClient.post('/api/v1/threat-intelligence/scans/', assetId ? { asset_id: assetId } : {}),
  getScanJob: (jobId) => apiClient.get(`/api/v1/threat-intelligence/scans/${jobId}/`),
  status: () => apiClient.get('/api/v1/threat-intelligence/status/'),
  adminStatus: () => apiClient.get('/api/v1/threat-intelligence/admin/status/'),
}

export const notificationsApi = {
  getPreferences: () => apiClient.get('/api/v1/notifications/preferences/'),
  updatePreferences: (payload) =>
    apiClient.patch('/api/v1/notifications/preferences/', payload),
}

export const aiApi = {
  getSettings: () => apiClient.get('/api/v1/ai/settings/'),
  updateSettings: (payload) => apiClient.patch('/api/v1/ai/settings/', payload),
  previewCharter: () => apiClient.get('/api/v1/ai/preview/charter/'),
  previewAssistant: () => apiClient.get('/api/v1/ai/preview/assistant/'),

  listDocuments: () => apiClient.get('/api/v1/ai/documents/'),
  generateDocument: (type) => apiClient.post('/api/v1/ai/documents/', { type }),
  getDocument: (id) => apiClient.get(`/api/v1/ai/documents/${id}/`),
  updateDocument: (id, contentMarkdown) =>
    apiClient.patch(`/api/v1/ai/documents/${id}/`, { content_markdown: contentMarkdown }),
  validateDocument: (id) => apiClient.post(`/api/v1/ai/documents/${id}/validate/`),
  // blob (not a plain URL): the export endpoint requires the JWT the
  // apiClient interceptor attaches, so it can't be a bare <a href>.
  exportDocument: (id) =>
    apiClient.get(`/api/v1/ai/documents/${id}/export/`, { responseType: 'blob' }),
  exportDocumentPdf: (id) =>
    apiClient.get(`/api/v1/ai/documents/${id}/export/pdf/`, { responseType: 'blob' }),

  listConversations: () => apiClient.get('/api/v1/ai/conversations/'),
  createConversation: () => apiClient.post('/api/v1/ai/conversations/'),
  listMessages: (conversationId) =>
    apiClient.get(`/api/v1/ai/conversations/${conversationId}/messages/`),
  sendMessage: (conversationId, content) =>
    apiClient.post(`/api/v1/ai/conversations/${conversationId}/messages/`, { content }),

  getJob: (jobId) => apiClient.get(`/api/v1/ai/jobs/${jobId}/`),
}
