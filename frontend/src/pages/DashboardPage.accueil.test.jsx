import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import DashboardPage from './DashboardPage'

// Lot C, point 21 — l'accueil sur le tableau de bord. Ce que ces tests
// tiennent : un nouveau client est accompagné, l'accueil reste tant que les
// trois étapes ne sont pas franchies, et il disparaît quand la personne le
// masque ou quand tout est fait.

let session = null

vi.mock('../context/AuthContext', () => ({
  useOptionalAuth: () => session,
  useAuth: () => session,
}))
vi.mock('../api/endpoints', () => ({
  assessmentsApi: { list: vi.fn() },
  monitoringApi: { dashboard: vi.fn() },
  actionsApi: { listAll: vi.fn() },
  authApi: { completeOnboardingStep: vi.fn() },
  reportingApi: { dashboard: vi.fn(), reportPdf: vi.fn(), exportCsv: vi.fn() },
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

const { assessmentsApi, monitoringApi, actionsApi, authApi, reportingApi } = await import(
  '../api/endpoints'
)

const INDICATEURS = {
  period: { key: 'quarter', start: '2026-06-17T00:00:00Z', end: '2026-09-15T21:59:59Z', days: 91 },
  available_periods: [{ key: 'quarter', label: 'Trimestre' }],
  exposure: {
    open_total: 0,
    open_by_severity: { critical: 0 },
    ignored_in_period: 0,
    exposure_score: 0,
    evolution: null,
    open_evolution: null,
    series: [],
    score_series: [],
  },
  maturity: { score: 58, evolution: null, history: [] },
  action_plan: { total: 10, done: 0, overdue: 0, completion_rate: 0, completion_evolution: null, series: [] },
  monitoring: { uptime_percentage: null, uptime_evolution: null },
}

const LIGNE_ACTIF = { asset: { id: 1, value: 'acme.example' }, open_alerts: [], latest_checks: {} }

function servir({ evaluations = [], actifs = [] } = {}) {
  assessmentsApi.list.mockResolvedValue({ data: { results: evaluations } })
  monitoringApi.dashboard.mockResolvedValue({ data: actifs })
  actionsApi.listAll.mockResolvedValue([])
  reportingApi.dashboard.mockResolvedValue({ data: INDICATEURS })
}

function rendre() {
  return render(
    <MemoryRouter>
      <DashboardPage />
    </MemoryRouter>
  )
}

describe('DashboardPage — l’accueil d’un nouveau client', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    session = {
      user: { onboarding: { result_seen: false, dismissed: false } },
      setUser: vi.fn(),
    }
  })

  it('accueille un client qui arrive, avec les trois étapes', async () => {
    servir()
    rendre()

    expect(await screen.findByText('Bienvenue sur RSSI as a Service')).toBeInTheDocument()
    expect(screen.getByText('Déclarez un actif')).toBeInTheDocument()
    expect(screen.getByText('Faites votre diagnostic')).toBeInTheDocument()
    expect(screen.getByText('Comprenez votre premier résultat')).toBeInTheDocument()
    expect(screen.getByText(/Le premier scan remonte tout l’historique connu/)).toBeInTheDocument()
  })

  it('garde l’accueil au-dessus des indicateurs tant que le premier résultat n’est pas compris', async () => {
    servir({ evaluations: [{ id: 1, status: 'completed' }], actifs: [LIGNE_ACTIF] })
    rendre()

    expect(await screen.findByText('Vos premiers pas')).toBeInTheDocument()
    expect(screen.getByText(/2 étapes sur 3/)).toBeInTheDocument()
    expect(screen.getByRole('link', { name: /Voir mon résultat/ })).toBeInTheDocument()
  })

  it('le retire quand les trois étapes sont franchies', async () => {
    session.user.onboarding.result_seen = true
    servir({ evaluations: [{ id: 1, status: 'completed' }], actifs: [LIGNE_ACTIF] })
    rendre()

    await screen.findByText('Tableau de bord')
    expect(screen.queryByText('Vos premiers pas')).not.toBeInTheDocument()
  })

  it('le retire quand la personne choisit de le masquer, et le mémorise', async () => {
    servir({ evaluations: [{ id: 1, status: 'completed' }] })
    authApi.completeOnboardingStep.mockResolvedValue({
      data: { onboarding: { result_seen: false, dismissed: true } },
    })
    rendre()

    await userEvent.click(await screen.findByRole('button', { name: 'Masquer l’accueil' }))

    await waitFor(() => expect(authApi.completeOnboardingStep).toHaveBeenCalledWith('dismissed'))
    expect(session.setUser).toHaveBeenCalledWith({ onboarding: { result_seen: false, dismissed: true } })
  })

  it('ne l’affiche plus une fois masqué, même avec des étapes restantes', async () => {
    session.user.onboarding.dismissed = true
    servir({ evaluations: [{ id: 1, status: 'completed' }] })
    rendre()

    await screen.findByText('Tableau de bord')
    expect(screen.queryByText('Vos premiers pas')).not.toBeInTheDocument()
  })
})
