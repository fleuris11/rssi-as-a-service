import { render, screen } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import CompromisesPage from './CompromisesPage'

// Ce qui est vérifié ici : les deux états que le jeu de démonstration ne
// permet pas d'atteindre à la main. Une entreprise de démonstration a
// toujours des fuites ouvertes — l'écran « aucune fuite » est donc invisible
// en vérification manuelle, alors que c'est celui que le client verra le jour
// où le produit a fait son travail.

vi.mock('../api/endpoints', () => ({
  threatIntelligenceApi: {
    listFindings: vi.fn(),
    status: vi.fn(),
    listMonitoredAssets: vi.fn(),
    listRevealAudit: vi.fn(),
    getScanJob: vi.fn(),
    triggerScan: vi.fn(),
    updateFindingStatus: vi.fn(),
    registerMonitoredAsset: vi.fn(),
    unregisterMonitoredAsset: vi.fn(),
  },
  monitoringApi: { listAssets: vi.fn() },
}))
vi.mock('../context/AuthContext', () => ({
  useAuth: () => ({ user: { is_staff: false }, currentTenant: { role: 'admin' } }),
}))
vi.mock('../components/ui/Toast', () => ({ useToast: () => ({ showToast: vi.fn() }) }))
vi.mock('../context/EntitlementsContext', () => ({
  useEntitlements: () => ({
    hasFeature: () => true,
    featureInfo: () => null,
    requiredPlanFor: () => '',
    isOperational: true,
    loading: false,
  }),
}))

const { threatIntelligenceApi, monitoringApi } = await import('../api/endpoints')

const fuite = (id, severity, asset) => ({
  id,
  severity,
  status: 'open',
  asset_value: asset,
  source_endpoint: 'stealer',
  meaning: 'Explication.',
  recommended_action: 'Action.',
  has_secret: false,
  breach_date: '2026-07-03',
})

function servir(findings) {
  threatIntelligenceApi.listFindings.mockResolvedValue({ data: { results: findings } })
  // Statut CLOISONNÉ : ce que l'offre du client comprend, jamais les
  // chiffres de la plateforme (voir le test « ne montre jamais… » plus bas).
  threatIntelligenceApi.status.mockResolvedValue({
    data: {
      scans_quota: 20,
      scans_used: 3,
      scans_remaining: 17,
      monitored_quota: 1,
      monitored_used: 0,
      monitored_remaining: 1,
      cooldown_active: false,
      cooldown_hours: 24,
    },
  })
  monitoringApi.listAssets.mockResolvedValue({ data: { results: [] } })
  threatIntelligenceApi.listMonitoredAssets.mockResolvedValue({ data: { results: [] } })
}

describe('CompromisesPage', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('annonce l’absence de fuite comme une bonne nouvelle, pas comme un vide', async () => {
    // « Aucune compromission ouverte », en gris sous un pictogramme d'alerte,
    // se lisait comme une panne. C'est pourtant le résultat que le client
    // paie pour obtenir.
    servir([])
    render(<CompromisesPage />)

    expect(await screen.findByText('Aucune fuite en cours')).toBeInTheDocument()
    expect(screen.getByText(/La surveillance continue en arrière-plan/)).toBeInTheDocument()
  })

  it('regroupe par gravité et met le compte dans le séparateur', async () => {
    // Le serveur ne garantit pas l'ordre : ici, une critique arrive APRÈS
    // deux élevées, comme sur le jeu de démonstration.
    servir([
      fuite(1, 'high', 'a.example'),
      fuite(2, 'high', 'b.example'),
      fuite(3, 'critical', 'c.example'),
    ])
    render(<CompromisesPage />)

    expect(await screen.findByRole('heading', { name: 'Critique — 1 fuite' })).toBeInTheDocument()
    expect(screen.getByRole('heading', { name: 'Élevée — 2 fuites' })).toBeInTheDocument()

    // Le groupe critique passe devant, quel que soit l'ordre d'arrivée.
    const titres = screen.getAllByRole('heading', { level: 2 }).map((h) => h.textContent)
    expect(titres.indexOf('Critique — 1 fuite')).toBeLessThan(titres.indexOf('Élevée — 2 fuites'))
  })

  it('ne laisse qu’une seule action remplie par fuite', async () => {
    // Trois actions de poids voisin ne disent plus laquelle est le chemin
    // normal. `Button` rend l'action primaire avec `bg-brand-600`.
    servir([fuite(1, 'critical', 'a.example')])
    render(<CompromisesPage />)

    const traiter = await screen.findByRole('button', { name: 'Marquer traité' })
    expect(traiter.className).toContain('bg-brand-600')
    expect(screen.getByRole('button', { name: 'Ignorer' }).className).not.toContain('bg-brand-600')
  })
  it('ne montre jamais les chiffres de la plateforme au client', async () => {
    // Cet écran affichait « Quota de requêtes restant (plateforme) : 971 » et
    // « 0 / 15 emplacements utilisés … pour toute la plateforme ». Deux
    // nombres qui ne concernent pas celui qui les lit, et qui publient la
    // consommation des autres clients — dans un produit dont l'argument est
    // le cloisonnement.
    servir([fuite(1, 'critical', 'a.example')])
    render(<CompromisesPage />)
    await screen.findByRole('heading', { name: 'Critique — 1 fuite' })

    const texte = document.body.textContent
    expect(texte).not.toMatch(/plateforme/i)
    expect(texte).not.toMatch(/toute la plateforme/i)
    expect(texte).not.toMatch(/15 actifs/)
  })

  it('affiche le quota d’analyses de l’offre du client', async () => {
    servir([fuite(1, 'critical', 'a.example')])
    render(<CompromisesPage />)
    await screen.findByRole('heading', { name: 'Critique — 1 fuite' })

    expect(screen.getByText(/Analyses restantes ce mois/)).toBeInTheDocument()
    expect(screen.getByText('17')).toBeInTheDocument()
    expect(screen.getByText(/sur 20 comprises dans votre offre/)).toBeInTheDocument()
  })
})
