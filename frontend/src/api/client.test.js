import { beforeEach, describe, expect, it, vi } from 'vitest'

// Régression coûteuse et invisible : un identifiant d'entreprise hérité d'une
// session précédente était joint à la requête de CONNEXION. Le middleware de
// scoping répondait 403 « Aucun accès à cette entreprise » avant même la
// vérification du mot de passe, et l'écran annonçait un mot de passe
// incorrect. Le compte devenait inutilisable jusqu'à un vidage manuel du
// stockage du navigateur.

describe('intercepteur de requête', () => {
  beforeEach(() => {
    vi.resetModules()
    localStorage.clear()
  })

  async function runInterceptor(config) {
    const { apiClient } = await import('./client')
    const handler = apiClient.interceptors.request.handlers[0]
    return handler.fulfilled({ headers: {}, ...config })
  }

  it('n’envoie ni jeton ni entreprise sur la connexion', async () => {
    localStorage.setItem('rssi.access', 'jeton-perime')
    localStorage.setItem('rssi.tenantId', 'entreprise-precedente')

    const config = await runInterceptor({ url: '/api/v1/auth/token/', method: 'post' })

    expect(config.headers.Authorization).toBeUndefined()
    expect(config.headers['X-Tenant-Id']).toBeUndefined()
  })

  it('n’envoie ni jeton ni entreprise sur l’inscription', async () => {
    localStorage.setItem('rssi.access', 'jeton-perime')
    localStorage.setItem('rssi.tenantId', 'entreprise-precedente')

    const config = await runInterceptor({ url: '/api/v1/auth/register/', method: 'post' })

    expect(config.headers.Authorization).toBeUndefined()
    expect(config.headers['X-Tenant-Id']).toBeUndefined()
  })

  it('joint bien le jeton et l’entreprise sur une route applicative', async () => {
    localStorage.setItem('rssi.access', 'jeton-valide')
    localStorage.setItem('rssi.tenantId', 'entreprise-courante')

    const config = await runInterceptor({ url: '/api/v1/threat-intelligence/feed/', method: 'get' })

    expect(config.headers.Authorization).toBe('Bearer jeton-valide')
    expect(config.headers['X-Tenant-Id']).toBe('entreprise-courante')
  })

  it('joint le jeton au rafraîchissement de session (route authentifiée)', async () => {
    // /token/refresh/ n'est PAS dans la liste : il porte légitimement un
    // contexte de session, et le préfixe de /token/ ne doit pas l'attraper.
    localStorage.setItem('rssi.access', 'jeton-valide')

    const config = await runInterceptor({ url: '/api/v1/auth/me/', method: 'get' })

    expect(config.headers.Authorization).toBe('Bearer jeton-valide')
  })
})

describe('intercepteur de réponse', () => {
  beforeEach(() => {
    vi.resetModules()
    localStorage.clear()
  })

  async function rejectWith(error) {
    const { apiClient } = await import('./client')
    const handler = apiClient.interceptors.response.handlers[0]
    return handler.rejected(error).catch(() => {})
  }

  it('oublie l’entreprise quand le serveur la refuse', async () => {
    localStorage.setItem('rssi.tenantId', 'entreprise-supprimee')

    await rejectWith({
      config: { url: '/api/v1/monitoring/assets/' },
      response: { status: 403, data: { detail: 'Aucun accès à cette entreprise.' } },
    })

    expect(localStorage.getItem('rssi.tenantId')).toBeNull()
  })

  it('conserve l’entreprise sur un 403 sans rapport', async () => {
    // Un refus de droits sur une ressource précise ne dit rien sur la
    // validité du contexte d'entreprise.
    localStorage.setItem('rssi.tenantId', 'entreprise-valide')

    await rejectWith({
      config: { url: '/api/v1/platform/capacity/' },
      response: { status: 403, data: { detail: 'Vous n’avez pas la permission.' } },
    })

    expect(localStorage.getItem('rssi.tenantId')).toBe('entreprise-valide')
  })
})
