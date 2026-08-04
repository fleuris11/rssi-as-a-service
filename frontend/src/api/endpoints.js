import { apiClient } from './client'

export const authApi = {
  register: (payload) => apiClient.post('/api/v1/auth/register/', payload),
  login: (email, password) => apiClient.post('/api/v1/auth/token/', { email, password }),
  me: () => apiClient.get('/api/v1/auth/me/'),
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

export const notificationsApi = {
  getPreferences: () => apiClient.get('/api/v1/notifications/preferences/'),
  updatePreferences: (payload) =>
    apiClient.patch('/api/v1/notifications/preferences/', payload),
}
