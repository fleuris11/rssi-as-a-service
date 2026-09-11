import { apiClient } from './client'

// Endpoint PUBLIC (site vitrine) : aucune authentification, aucun en-tête de
// tenant. Volontairement isolé des autres objets d'API pour que ce caractère
// public soit visible à la lecture.
export const publicApi = {
  requestDemo: (payload) => apiClient.post('/api/v1/public/demo-requests/', payload),
  // Catalogue d'offres : public et non authentifié, c'est la source de la
  // grille tarifaire du site vitrine.
  listPlans: () => apiClient.get('/api/v1/billing/plans/'),
}

// Droits de l'entreprise courante : ce que comprend son offre et, pour le
// reste, l'offre qui le donnerait. Le frontend s'en sert pour AFFICHER les
// fonctionnalités hors offre en désactivé plutôt que les masquer.
export const billingApi = {
  entitlements: () => apiClient.get('/api/v1/billing/entitlements/'),
}

// Back-office plateforme (is_staff). Espace distinct de l'espace client.
export const platformApi = {
  capacity: () => apiClient.get('/api/v1/platform/capacity/'),
  // Actifs dont la possession n'est pas etablie (ADR-026) : ceux declares
  // avant la V2-1, a regulariser sans etre coupes.
  ownershipReview: () => apiClient.get('/api/v1/platform/ownership-review/'),
  listTenants: () => apiClient.get('/api/v1/platform/tenants/'),
  tenantDetail: (id) => apiClient.get(`/api/v1/platform/tenants/${id}/`),
  updateTenant: (id, payload) => apiClient.patch(`/api/v1/platform/tenants/${id}/`, payload),
  subscriptionAction: (id, payload) =>
    apiClient.post(`/api/v1/platform/tenants/${id}/subscription/`, payload),
  listPlans: () => apiClient.get('/api/v1/platform/plans/'),
  updatePlan: (code, payload) => apiClient.patch(`/api/v1/platform/plans/${code}/`, payload),
  createPlan: (payload) => apiClient.post('/api/v1/platform/plans/', payload),
  listDemoRequests: () => apiClient.get('/api/v1/platform/demo-requests/'),
  updateDemoRequest: (id, payload) =>
    apiClient.patch(`/api/v1/platform/demo-requests/${id}/`, payload),
  convertDemoRequest: (id) =>
    apiClient.post(`/api/v1/platform/demo-requests/${id}/convert/`),
  health: () => apiClient.get('/api/v1/platform/health/'),
  configuration: () => apiClient.get('/api/v1/platform/configuration/'),
  audit: () => apiClient.get('/api/v1/platform/audit/'),

  // --- Console d'administration (phase 11) --------------------------------
  // Écriture complète : plus aucune opération de gestion ne demande un shell.
  createClient: (payload) => apiClient.post('/api/v1/platform/clients/', payload),
  clientDetail: (id) => apiClient.get(`/api/v1/platform/clients/${id}/`),
  updateClient: (id, payload) => apiClient.patch(`/api/v1/platform/clients/${id}/`, payload),
  archiveClient: (id, payload) => apiClient.post(`/api/v1/platform/clients/${id}/archive/`, payload),
  deleteClient: (id, confirmName) =>
    apiClient.delete(`/api/v1/platform/clients/${id}/`, { data: { confirm_name: confirmName } }),

  listMembers: (id) => apiClient.get(`/api/v1/platform/clients/${id}/members/`),
  inviteMember: (id, payload) =>
    apiClient.post(`/api/v1/platform/clients/${id}/members/`, payload),
  updateMember: (id, membershipId, payload) =>
    apiClient.patch(`/api/v1/platform/clients/${id}/members/${membershipId}/`, payload),
  removeMember: (id, membershipId) =>
    apiClient.delete(`/api/v1/platform/clients/${id}/members/${membershipId}/`),
  resetMemberPassword: (id, membershipId) =>
    apiClient.post(`/api/v1/platform/clients/${id}/members/${membershipId}/reset-password/`),

  updateSubscription: (id, payload) =>
    apiClient.patch(`/api/v1/platform/clients/${id}/subscription/`, payload),
  clientMonitoredAssets: (id) =>
    apiClient.get(`/api/v1/platform/clients/${id}/monitored-assets/`),
  addMonitoredAsset: (id, assetId) =>
    apiClient.post(`/api/v1/platform/clients/${id}/monitored-assets/`, { asset_id: assetId }),
  removeMonitoredAsset: (id, assetId) =>
    apiClient.delete(`/api/v1/platform/clients/${id}/monitored-assets/`, {
      data: { asset_id: assetId },
    }),
  clientAction: (id, action) =>
    apiClient.post(`/api/v1/platform/clients/${id}/actions/`, { action }),

  planImpact: (code, changes) =>
    apiClient.post(`/api/v1/platform/plans/${code}/impact/`, changes),
  duplicatePlan: (code, payload) =>
    apiClient.post(`/api/v1/platform/plans/${code}/duplicate/`, payload),
  deletePlan: (code) => apiClient.delete(`/api/v1/platform/plans/${code}/delete/`),
  previewPlan: (code) => apiClient.get(`/api/v1/platform/plans/${code}/preview/`),

  // --- Referentiels et demandes (V2-4) ------------------------------------
  listReferentials: () => apiClient.get('/api/v1/platform/referentials/'),
  clientReferentials: (id) => apiClient.get(`/api/v1/platform/clients/${id}/referentials/`),
  assignReferential: (id, slug, note = '') =>
    apiClient.post(`/api/v1/platform/clients/${id}/referentials/`, { referential: slug, note }),
  revokeReferential: (id, slug) =>
    apiClient.delete(`/api/v1/platform/clients/${id}/referentials/`, {
      data: { referential: slug },
    }),
  // --- Veille reglementaire (V2-7) ----------------------------------------
  // Console UNIQUEMENT : la veille alimente le catalogue partage, et une
  // suggestion non triee n'a rien a faire dans un espace client.
  watchQueue: (params = {}) => apiClient.get('/api/v1/platform/watch/', { params }),
  watchSources: () => apiClient.get('/api/v1/platform/watch/sources/'),
  updateWatchSource: (slug, payload) =>
    apiClient.patch(`/api/v1/platform/watch/sources/${slug}/`, payload),
  pollWatchSource: (slug) => apiClient.post(`/api/v1/platform/watch/sources/${slug}/poll/`),
  reviewWatchUpdate: (id, payload) =>
    apiClient.post(`/api/v1/platform/watch/updates/${id}/review/`, payload),
  integrateWatchUpdate: (id, payload) =>
    apiClient.post(`/api/v1/platform/watch/updates/${id}/integrate/`, payload),
  summarizeWatchUpdate: (id) =>
    apiClient.post(`/api/v1/platform/watch/updates/${id}/summary/`),

  listAccessRequests: (status) =>
    apiClient.get('/api/v1/platform/access-requests/', { params: status ? { status } : {} }),
  // V2-6 : une ETAPE de suivi (contacted / proposal / granted / declined),
  // plus un booleen accorder-ou-refuser. Une demande se travaille avant de
  // se conclure.
  advanceAccessRequest: (id, status, response = '') =>
    apiClient.post(`/api/v1/platform/access-requests/${id}/`, { status, response }),

  listProspects: (params) => apiClient.get('/api/v1/platform/prospects/', { params }),
  createProspect: (payload) => apiClient.post('/api/v1/platform/prospects/', payload),
  updateProspect: (id, payload) => apiClient.patch(`/api/v1/platform/prospects/${id}/`, payload),
  addProspectNote: (id, body) =>
    apiClient.post(`/api/v1/platform/prospects/${id}/notes/`, { body }),
  followUpBoard: () => apiClient.get('/api/v1/platform/prospects/follow-up/'),

  listAdmins: () => apiClient.get('/api/v1/platform/admins/'),
  inviteAdmin: (payload) => apiClient.post('/api/v1/platform/admins/', payload),
  changeAdminLevel: (userId, level) =>
    apiClient.patch(`/api/v1/platform/admins/${userId}/`, { level }),
  revokeAdmin: (userId) => apiClient.delete(`/api/v1/platform/admins/${userId}/`),

  settings: () => apiClient.get('/api/v1/platform/settings/'),
  updateSetting: (key, value) => apiClient.patch('/api/v1/platform/settings/', { key, value }),
  resetSetting: (key) => apiClient.post(`/api/v1/platform/settings/${key}/reset/`),

  trash: () => apiClient.get('/api/v1/platform/trash/'),
  search: (q) => apiClient.get('/api/v1/platform/search/', { params: { q } }),
  // L'export est un téléchargement de fichier : on renvoie l'URL, le
  // navigateur s'en charge (une réponse CSV lue en JSON serait illisible).
  exportUrl: (kind) => `/api/v1/platform/export/${kind}/`,
}

// Définition du mot de passe depuis un lien d'invitation. Route PUBLIQUE :
// la personne invitée n'a précisément pas encore de mot de passe.
export const invitationApi = {
  check: (token) => apiClient.get(`/api/v1/auth/invitation/${token}/`),
  accept: (token, password) =>
    apiClient.post(`/api/v1/auth/invitation/${token}/`, { password }),
}

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
  // Profil d'affichage (V2-5). Le seul champ de l'identité modifiable ici :
  // il ne donne accès à rien et se change a tout moment.
  setDisplayProfile: (profile) =>
    apiClient.patch('/api/v1/auth/me/', { display_profile: profile }),
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
  // Le catalogue vu par l'entreprise courante : ce qu'elle a, ce qu'elle a eu,
  // et ce qu'elle pourrait demander (chaque ligne porte `granted`).
  listReferentials: () => apiClient.get('/api/v1/assessments/referentials/'),
  // Sans slug : le référentiel par défaut (le premier attribué). Cet appel
  // existait avant V2-4 et garde exactement le même contrat.
  referential: (slug, subset) =>
    apiClient.get(slug ? `/api/v1/assessments/referentials/${slug}/` : '/api/v1/assessments/referential/', {
      params: subset ? { subset } : {},
    }),
  start: (referential, subset) =>
    apiClient.post('/api/v1/assessments/start/', {
      ...(referential ? { referential } : {}),
      ...(subset ? { subset } : {}),
    }),
  current: (referential) =>
    apiClient.get('/api/v1/assessments/current/', {
      params: referential ? { referential } : {},
    }),
  list: (referential) =>
    apiClient.get('/api/v1/assessments/', { params: referential ? { referential } : {} }),
  detail: (id) => apiClient.get(`/api/v1/assessments/${id}/`),
  submitAnswer: (assessmentId, measureId, value, note = '') =>
    apiClient.put(`/api/v1/assessments/${assessmentId}/answers/${measureId}/`, { value, note }),
  complete: (id) => apiClient.post(`/api/v1/assessments/${id}/complete/`),
  scores: (id) => apiClient.get(`/api/v1/assessments/${id}/scores/`),
  // Le score par référentiel et, quand il y en a plusieurs, le consolidé —
  // qui ne voyage jamais sans son détail (ADR-030).
  consolidatedScores: () => apiClient.get('/api/v1/assessments/scores/consolidated/'),

  listSubsets: (referential) =>
    apiClient.get('/api/v1/assessments/subsets/', {
      params: referential ? { referential } : {},
    }),
  createSubset: (payload) => apiClient.post('/api/v1/assessments/subsets/', payload),

  // Reformulation d'une mesure pour cette entreprise. Elle vit A COTE du
  // référentiel : `plain_language` reste l'énoncé d'origine, `statement` est
  // ce qu'on affiche.
  listOverrides: () => apiClient.get('/api/v1/assessments/overrides/'),
  setOverride: (measureId, payload) =>
    apiClient.put(`/api/v1/assessments/measures/${measureId}/override/`, payload),
  clearOverride: (measureId) =>
    apiClient.delete(`/api/v1/assessments/measures/${measureId}/override/`),
}

// Demandes de l'entreprise a l'exploitant : un référentiel aujourd'hui,
// d'autres fonctionnalités demain — le mécanisme est générique (V2-4/V2-6).
// B5.18 : la veille vue du client — lecture seule, et seulement ce qui a ete
// juge pertinent. Ni la file de tri, ni l etat des sources.
export const watchApi = {
  feed: () => apiClient.get('/api/v1/watch/'),
}

export const accessRequestsApi = {
  list: (status) =>
    apiClient.get('/api/v1/access-requests/', { params: status ? { status } : {} }),
  create: (payload) => apiClient.post('/api/v1/access-requests/', payload),
  cancel: (id) => apiClient.delete(`/api/v1/access-requests/${id}/`),
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
  // Possession d'un domaine (ADR-026) : l'etat, l'ouverture d'une preuve,
  // et sa verification.
  ownership: (assetId) => apiClient.get(`/api/v1/monitoring/assets/${assetId}/ownership/`),
  startOwnershipProof: (assetId, payload) =>
    apiClient.post(`/api/v1/monitoring/assets/${assetId}/ownership/`, payload),
  verifyOwnershipProof: (assetId, proofId, payload) =>
    apiClient.post(
      `/api/v1/monitoring/assets/${assetId}/ownership/${proofId}/verify/`,
      payload
    ),
}

export const threatIntelligenceApi = {
  // La reponse est paginee cote serveur depuis le correctif du 06/09 (28 450
  // entrees figeaient le navigateur). L'ecran n'exposait pourtant aucune
  // navigation : un client avec 165 compromissions en voyait 20, sans savoir
  // que les autres existaient. `page` rend le reste atteignable.
  listFindings: (status, page = 1) =>
    apiClient.get('/api/v1/threat-intelligence/findings/', {
      params: { ...(status ? { status } : {}), ...(page > 1 ? { page } : {}) },
    }),
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

  // --- Comptes designes (V2-6) --------------------------------------------
  // Espace distinct de l'exposition : ce ne sont pas les actifs du client,
  // ce sont des comptes qu'il declare surveiller, avec une declaration
  // engageante a l'ajout (ADR-033).
  listWatchedAccounts: () => apiClient.get('/api/v1/threat-intelligence/watched-accounts/'),
  declareWatchedAccount: (payload) =>
    apiClient.post('/api/v1/threat-intelligence/watched-accounts/', payload),
  removeWatchedAccount: (id, reason = '') =>
    apiClient.delete(`/api/v1/threat-intelligence/watched-accounts/${id}/`, {
      data: { reason },
    }),
  listWatchedAccountFindings: (params = {}) =>
    apiClient.get('/api/v1/threat-intelligence/watched-accounts/findings/', { params }),
  // Lot A : l'export reprend EXACTEMENT les filtres de l'ecran. On renvoie
  // l'URL plutot que la reponse : un telechargement de fichier n'a pas a
  // transiter par un blob en memoire.
  watchedAccountFindingsExportUrl: (params = {}) =>
    `/api/v1/threat-intelligence/watched-accounts/findings/export/?${new URLSearchParams(params)}`,
  updateWatchedAccountFinding: (id, status) =>
    apiClient.patch(`/api/v1/threat-intelligence/watched-accounts/findings/${id}/`, { status }),
  scanWatchedAccounts: (accountIds = []) =>
    apiClient.post('/api/v1/threat-intelligence/watched-accounts/scans/', {
      account_ids: accountIds,
    }),
  adminStatus: () => apiClient.get('/api/v1/threat-intelligence/admin/status/'),
}

// Restitution de comité (ADR-028). La période est résolue par le SERVEUR :
// une clé (`quarter`) ou deux dates. Le frontend n'en calcule aucune — deux
// implémentations du même trimestre finiraient par diverger, et l'écart se
// verrait le jour où le PDF ne dirait pas la même chose que la page.
export const reportingApi = {
  dashboard: (params) => apiClient.get('/api/v1/reporting/dashboard/', { params }),
  report: (params) => apiClient.get('/api/v1/reporting/report/', { params }),
  reportPdf: (params) =>
    apiClient.get('/api/v1/reporting/report.pdf', { params, responseType: 'blob' }),
  exportCsv: (params) =>
    apiClient.get('/api/v1/reporting/export.csv', { params, responseType: 'blob' }),
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

  // La bibliothèque documentaire (V2-5) : les sept documents que la
  // plateforme sait produire, l'état de chacun, et ce qui manque pour qu'il
  // soit personnalisé.
  documentCatalog: () => apiClient.get('/api/v1/ai/documents/catalog/'),
  listDocuments: () => apiClient.get('/api/v1/ai/documents/'),
  // Réponse en 201 avec le document prêt pour un document composé, en 202
  // avec un job pour la charte, qui passe par l'IA.
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
  // Format éditable : ce que « modifiable » veut dire pour une PME, qui
  // n'ouvre pas un fichier Markdown.
  exportDocumentDocx: (id) =>
    apiClient.get(`/api/v1/ai/documents/${id}/export/docx/`, { responseType: 'blob' }),

  listConversations: () => apiClient.get('/api/v1/ai/conversations/'),
  createConversation: () => apiClient.post('/api/v1/ai/conversations/'),
  listMessages: (conversationId) =>
    apiClient.get(`/api/v1/ai/conversations/${conversationId}/messages/`),
  sendMessage: (conversationId, content) =>
    apiClient.post(`/api/v1/ai/conversations/${conversationId}/messages/`, { content }),

  getJob: (jobId) => apiClient.get(`/api/v1/ai/jobs/${jobId}/`),
}
