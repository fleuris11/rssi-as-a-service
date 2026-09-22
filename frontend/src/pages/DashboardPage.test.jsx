import { render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import DashboardPage from './DashboardPage'

// Lot C, C2 — « supprimer une soirée de travail ». Ce que ces tests tiennent :
// la comparaison est là par défaut, chaque indicateur mène à son écran, chaque
// courbe porte sa question, aucune courbe n'est dessinée pour décorer, et les
// exports couvrent la période affichée.

vi.mock('../api/endpoints', () => ({
  assessmentsApi: { list: vi.fn() },
  monitoringApi: { dashboard: vi.fn() },
  actionsApi: { listAll: vi.fn() },
  reportingApi: { dashboard: vi.fn(), reportPdf: vi.fn(), exportCsv: vi.fn() },
}))
vi.mock('../components/ui/Toast', () => ({ useToast: () => ({ showToast: vi.fn() }) }))
// Le profil n'est plus un vocabulaire, c'est une mise en page : les
// indicateurs, le selecteur de periode, les courbes et le tableur vivent
// desormais dans la CONSOLE (profil Technique). Chaque test declare donc le
// profil qu'il exerce, au lieu de dependre d'un defaut.
let profilCourant = 'technical'
vi.mock('../context/useDisplayProfile', () => ({
  EXECUTIVE: 'executive',
  TECHNICAL: 'technical',
  useDisplayProfile: () => ({
    profile: profilCourant,
    isTechnical: profilCourant === 'technical',
    setProfile: vi.fn(),
  }),
}))
vi.mock('../context/EntitlementsContext', () => ({
  useEntitlements: () => ({
    hasFeature: () => true,
    featureInfo: () => null,
    requiredPlanFor: () => '',
    isOperational: true,
    loading: false,
  }),
}))

const { assessmentsApi, monitoringApi, actionsApi, reportingApi } = await import('../api/endpoints')

function indicateurs(surcharge = {}) {
  return {
    period: { key: 'quarter', label: 'Trimestre', start: '2026-06-17T00:00:00Z', end: '2026-09-15T21:59:59Z', days: 91 },
    available_periods: [
      { key: '30d', label: '30 derniers jours' },
      { key: 'quarter', label: 'Trimestre' },
      { key: 'custom', label: 'Période personnalisée' },
    ],
    exposure: {
      open_total: 12,
      open_at_period_start: 30,
      open_by_severity: { critical: 2, high: 6, attention: 4 },
      ignored_in_period: 3,
      exposure_score: 41,
      exposure_score_at_period_start: 63,
      evolution: { delta: -22, direction: 'baisse', is_improvement: true },
      open_evolution: { delta: -18, direction: 'baisse', is_improvement: true },
      series: [
        { date: '2026-06-17', open: 30, treated: 0 },
        { date: '2026-09-15', open: 12, treated: 15 },
      ],
      score_series: [
        { date: '2026-06-17', score: 63 },
        { date: '2026-09-15', score: 41 },
      ],
    },
    maturity: {
      score: 58,
      evolution: { delta: 12, direction: 'hausse', is_improvement: true },
      history: [
        { date: '2026-07-01', score: 46, referential: 'ANSSI' },
        { date: '2026-09-01', score: 58, referential: 'ANSSI' },
      ],
    },
    action_plan: {
      total: 20,
      done: 9,
      overdue: 1,
      completion_rate: 45,
      completion_evolution: { delta: 25, direction: 'hausse', is_improvement: true },
      series: [
        { date: '2026-06-17', done: 4, total: 20, completion_rate: 20 },
        { date: '2026-09-15', done: 9, total: 20, completion_rate: 45 },
      ],
    },
    monitoring: {
      uptime_percentage: 99.9,
      uptime_evolution: { delta: 0.1, direction: 'hausse', is_improvement: true },
    },
    ...surcharge,
  }
}

function servir({ evaluations = [{ id: 1, status: 'completed' }], donnees = indicateurs() } = {}) {
  assessmentsApi.list.mockResolvedValue({ data: { results: evaluations } })
  monitoringApi.dashboard.mockResolvedValue({ data: [] })
  actionsApi.listAll.mockResolvedValue([])
  reportingApi.dashboard.mockResolvedValue({ data: donnees })
}

function rendre(profil = 'technical') {
  profilCourant = profil
  return render(
    <MemoryRouter>
      <DashboardPage />
    </MemoryRouter>
  )
}

describe('DashboardPage — le tableau de bord d’un RSSI', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    profilCourant = 'technical'
  })

  describe('les deux profils sont deux ecrans, pas deux vocabulaires', () => {
    it('le profil Dirigeant ne montre ni selecteur de periode, ni tableur', async () => {
      servir()
      rendre('executive')

      // Le chiffre est la : c'est la MEME donnee, lue de la meme reponse.
      // Il apparait deux fois — la jauge et le curseur de la courbe, qui se
      // pose par defaut sur la derniere mesure. C'est voulu : les deux
      // doivent dire la meme chose.
      expect((await screen.findAllByText('41')).length).toBeGreaterThan(0)
      // Mais l'outillage d'analyse n'y est pas : un dirigeant tranche, il
      // n'analyse pas.
      expect(screen.queryByRole('button', { name: /tableur/i })).not.toBeInTheDocument()
      expect(screen.queryByText(/comparé aux 91 jours précédents/)).not.toBeInTheDocument()
    })

    it('le profil Dirigeant garde le rapport de comité', async () => {
      servir()
      rendre('executive')
      expect(
        await screen.findByRole('button', { name: /rapport de comité/i })
      ).toBeInTheDocument()
    })

    it('les deux profils lisent le même score, jamais deux valeurs', async () => {
      servir()
      const dirigeant = rendre('executive')
      expect((await screen.findAllByText('41')).length).toBeGreaterThan(0)
      dirigeant.unmount()

      servir()
      rendre('technical')
      expect(await screen.findByText('41/100')).toBeInTheDocument()
    })

    it('le panneau « À traiter en premier » n’est jamais un cadre vide', async () => {
      // Sans alerte ni action rapide, l'ancienne version laissait un blanc :
      // impossible de distinguer « rien à faire » d'un chargement rate.
      servir()
      actionsApi.listAll.mockResolvedValue([])
      rendre('executive')

      expect(
        await screen.findByText(/Rien n’attend de décision de votre part aujourd’hui/)
      ).toBeInTheDocument()
      expect(
        screen.getByText(/Ce panneau se remplit tout seul/)
      ).toBeInTheDocument()
    })
  })

  it('compare à la période précédente par défaut', async () => {
    servir()
    rendre()

    expect(await screen.findByText(/comparé aux 91 jours précédents/)).toBeInTheDocument()
    expect(reportingApi.dashboard).toHaveBeenCalledWith({ period: 'quarter' })
  })

  it('donne pour chaque indicateur sa valeur, sa tendance et le chemin vers le détail', async () => {
    servir()
    const { container } = rendre()
    await screen.findByText('41/100')

    const attendus = [
      ['Voir l’exposition', '/exposition'],
      ['Voir les compromissions', '/compromissions'],
      ['Voir les résultats', '/resultats'],
      ['Voir le plan', '/plan-action'],
      ['Voir la surveillance', '/surveillance'],
    ]
    for (const [libelle, cible] of attendus) {
      expect(screen.getByRole('link', { name: libelle })).toHaveAttribute('href', cible)
    }
    // Cinq tendances lues dans le sens décidé par le serveur.
    expect(container.querySelectorAll('[data-improvement="true"]')).toHaveLength(5)
  })

  it('accompagne les scores de leur sens', async () => {
    servir()
    rendre()

    expect(await screen.findByText(/votre exposition est à surveiller/)).toBeInTheDocument()
    expect(screen.getByText(/votre niveau progresse, mais reste insuffisant/)).toBeInTheDocument()
  })

  it('pose sa question à chaque courbe, et en écrit la lecture', async () => {
    servir()
    rendre()
    await screen.findByText('41/100')

    for (const question of [
      'Le score d’exposition baisse-t-il ?',
      'Traite-t-on les fuites, ou se contente-t-on de les écarter ?',
      'Notre maturité progresse-t-elle ?',
      'Le plan d’action avance-t-il ?',
    ]) {
      expect(screen.getByText(question)).toBeInTheDocument()
    }
    expect(screen.getByText(/De 63\/100 à 41\/100 sur la période : c’est une amélioration/)).toBeInTheDocument()
    expect(screen.getByText(/12 encore ouverte\(s\), 15 traitée\(s\) sur la période, 3 écartée\(s\)/)).toBeInTheDocument()
    expect(screen.getByText(/De 20 % à 45 % sur la période : c’est une amélioration/)).toBeInTheDocument()
  })

  it('ne dessine pas de courbe de maturité sur un seul diagnostic', async () => {
    servir({
      donnees: indicateurs({
        maturity: {
          score: 58,
          evolution: { delta: null, direction: 'inconnue', is_improvement: null },
          history: [{ date: '2026-09-01', score: 58, referential: 'ANSSI' }],
        },
      }),
    })
    rendre()

    expect(
      await screen.findByText(/Un seul diagnostic terminé sur la période : la tendance apparaîtra au suivant/)
    ).toBeInTheDocument()
  })

  it('recharge tous les indicateurs quand la période change', async () => {
    servir()
    rendre()
    await screen.findByText('41/100')

    await userEvent.click(screen.getByRole('button', { name: '30 derniers jours' }))

    await waitFor(() => expect(reportingApi.dashboard).toHaveBeenCalledWith({ period: '30d' }))
  })

  it('exporte le rapport de comité sur la période affichée', async () => {
    servir()
    reportingApi.reportPdf.mockResolvedValue({ data: 'pdf', headers: {} })
    globalThis.URL.createObjectURL = vi.fn(() => 'blob:x')
    globalThis.URL.revokeObjectURL = vi.fn()
    rendre()
    await screen.findByText('41/100')

    await userEvent.click(screen.getByRole('button', { name: '30 derniers jours' }))
    await waitFor(() => expect(reportingApi.dashboard).toHaveBeenCalledWith({ period: '30d' }))
    await userEvent.click(
      screen.getByRole('button', { name: 'Télécharger le rapport de comité de la période en PDF' })
    )

    await waitFor(() => expect(reportingApi.reportPdf).toHaveBeenCalledWith({ period: '30d' }))
  })

  it('exporte les données en tableur', async () => {
    servir()
    reportingApi.exportCsv.mockResolvedValue({ data: 'csv', headers: {} })
    globalThis.URL.createObjectURL = vi.fn(() => 'blob:x')
    globalThis.URL.revokeObjectURL = vi.fn()
    rendre()
    await screen.findByText('41/100')

    await userEvent.click(
      screen.getByRole('button', { name: 'Exporter les chiffres de la période en tableur' })
    )

    await waitFor(() => expect(reportingApi.exportCsv).toHaveBeenCalledWith({ period: 'quarter' }))
  })

  it('garde l’accueil tant qu’aucun diagnostic n’est terminé', async () => {
    servir({ evaluations: [] })
    rendre()

    expect(await screen.findByText('Bienvenue sur RSSI as a Service')).toBeInTheDocument()
    expect(reportingApi.dashboard).not.toHaveBeenCalled()
    const etape = screen.getByText('Faites votre diagnostic').closest('div')
    expect(within(etape.parentElement).getByText('Démarrer le diagnostic')).toBeInTheDocument()
  })
})
