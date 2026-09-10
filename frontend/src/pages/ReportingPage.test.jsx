import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import ReportingPage from './ReportingPage'

// V2-3 (ADR-028). Ce que ces tests vérifient n'est pas l'apparence, mais deux
// règles de fond qu'une relecture ne rattrape pas :
//
// 1. le SENS d'une évolution vient du serveur — une flèche verte sur « fuites
//    en hausse » est le genre d'erreur qu'on ne voit qu'en comité ;
// 2. les deux scores ne se mélangent jamais.

vi.mock('../api/endpoints', () => ({
  reportingApi: {
    dashboard: vi.fn(),
    report: vi.fn(),
    reportPdf: vi.fn(),
    exportCsv: vi.fn(),
  },
}))
vi.mock('../components/ui/Toast', () => ({ useToast: () => ({ showToast: vi.fn() }) }))
vi.mock('../context/AuthContext', () => ({
  useAuth: () => ({ currentTenant: { id: 't', role: 'admin' } }),
}))

const { reportingApi } = await import('../api/endpoints')

function servir(surcharge = {}) {
  reportingApi.dashboard.mockResolvedValue({
    data: {
      period: {
        key: 'quarter',
        label: 'Trimestre',
        start: '2026-06-11T00:00:00Z',
        end: '2026-09-09T23:59:59Z',
        days: 91,
      },
      available_periods: [
        { key: '30d', label: '30 derniers jours' },
        { key: 'quarter', label: 'Trimestre' },
        { key: 'custom', label: 'Période personnalisée' },
      ],
      exposure: {
        open_total: 14,
        open_at_period_start: 31,
        open_by_severity: { critical: 2, high: 9, attention: 3 },
        new_in_period: 6,
        treated_in_period: 20,
        ignored_in_period: 3,
        closed_in_period: 23,
        average_treatment_days: 8.5,
        exposure_score: 47,
        exposure_score_at_period_start: 62,
        series: [
          { date: '2026-09-01', open: 20 },
          { date: '2026-09-09', open: 14 },
        ],
        evolution: { delta: -15, direction: 'baisse', is_improvement: true },
        open_evolution: { delta: -17, direction: 'baisse', is_improvement: true },
        by_asset: [{ asset_id: 1, asset_value: 'acme.fr', score: 47, findings_count: 14 }],
      },
      action_plan: {
        total: 12,
        open: 5,
        todo: 3,
        in_progress: 2,
        done: 7,
        overdue: 2,
        without_due_date: 3,
        completed_in_period: 4,
        created_in_period: 0,
        completion_rate: 58.3,
      },
      maturity: {
        score: 61.5,
        previous_score: 48.0,
        measured_at: '2026-08-01T00:00:00Z',
        previous_measured_at: '2026-03-01T00:00:00Z',
        delta: 13.5,
        completed_in_period: 1,
        history: [],
        evolution: { delta: 13.5, direction: 'hausse', is_improvement: true },
      },
      monitoring: {
        assets_total: 3,
        assets_active: 3,
        uptime_percentage: 99.8,
        checks_in_period: 8000,
        failed_checks_in_period: 16,
        open_alerts: 1,
        alerts_opened_in_period: 2,
        alerts_resolved_in_period: 2,
        certificates: [{ asset_id: 1, asset_value: 'acme.fr', days_left: 12 }],
        uptime_evolution: { delta: 0.2, direction: 'hausse', is_improvement: true },
      },
      ...surcharge,
    },
  })
}

describe('ReportingPage', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('affiche chaque indicateur avec ce qu’il veut dire', async () => {
    // Un tableau de bord sans cette ligne oblige son lecteur à connaître déjà
    // la réponse — c'est-à-dire à ne pas en avoir besoin.
    servir()
    render(<ReportingPage />)

    expect(await screen.findByText('14')).toBeInTheDocument()
    expect(screen.getByText(/Plus bas est mieux/)).toBeInTheDocument()
    expect(screen.getByText(/Mesure votre organisation, pas les fuites/)).toBeInTheDocument()
  })

  it('dit que les deux scores ne s’additionnent pas', async () => {
    // ADR-028. Le dire à l'écran évite qu'on fabrique la moyenne dans le
    // tableur d'à côté.
    servir()
    render(<ReportingPage />)

    expect(await screen.findByText(/ne s’additionnent pas/)).toBeInTheDocument()
  })

  it('lit le sens de l’évolution du serveur, pas du signe', async () => {
    // Une baisse de 17 fuites est une amélioration ; une baisse de maturité
    // n'en serait pas une. Le composant ne doit pas trancher lui-même.
    servir()
    const { container } = render(<ReportingPage />)

    await screen.findByText('14')
    const sens = [...container.querySelectorAll('[data-improvement]')].map(
      (n) => n.dataset.improvement
    )
    expect(sens).toContain('true')
    expect(sens).not.toContain('false')
  })

  it('signale une dégradation quand le serveur la qualifie ainsi', async () => {
    servir({
      exposure: {
        open_total: 40,
        open_at_period_start: 14,
        open_by_severity: { critical: 5, high: 20, attention: 15 },
        new_in_period: 30,
        treated_in_period: 2,
        ignored_in_period: 0,
        closed_in_period: 2,
        average_treatment_days: null,
        exposure_score: 80,
        exposure_score_at_period_start: 47,
        series: [],
        evolution: { delta: 33, direction: 'hausse', is_improvement: false },
        open_evolution: { delta: 26, direction: 'hausse', is_improvement: false },
        by_asset: [],
      },
    })
    const { container } = render(<ReportingPage />)

    await screen.findByText('40')
    const sens = [...container.querySelectorAll('[data-improvement]')].map(
      (n) => n.dataset.improvement
    )
    expect(sens).toContain('false')
  })

  it('affiche le nombre d’actions sans échéance à côté du retard', async () => {
    // « 2 actions en retard » sur trois sans échéance se lirait comme une
    // bonne nouvelle.
    servir()
    render(<ReportingPage />)

    expect(await screen.findByText('Ouvertes sans échéance')).toBeInTheDocument()
    expect(screen.getByText('En retard')).toBeInTheDocument()
  })

  it('ne dessine pas de courbe quand il n’y a rien à montrer', async () => {
    // Pas de graphique décoratif : une courbe sur un jeu vide n'illustre rien.
    servir({
      exposure: {
        open_total: 0,
        open_at_period_start: 0,
        open_by_severity: { critical: 0, high: 0, attention: 0 },
        new_in_period: 0,
        treated_in_period: 0,
        ignored_in_period: 0,
        closed_in_period: 0,
        average_treatment_days: null,
        exposure_score: 0,
        exposure_score_at_period_start: 0,
        series: [],
        evolution: { delta: 0, direction: 'stable', is_improvement: null },
        open_evolution: { delta: 0, direction: 'stable', is_improvement: null },
        by_asset: [],
      },
    })
    render(<ReportingPage />)

    await waitFor(() => expect(screen.queryAllByText('Compromissions ouvertes').length).toBe(1))
    expect(screen.queryByText(/est-ce qu'il baisse/)).not.toBeInTheDocument()
  })

  it('recharge les indicateurs quand la période change', async () => {
    servir()
    render(<ReportingPage />)
    await screen.findByText('14')

    await userEvent.click(screen.getByRole('button', { name: '30 derniers jours' }))

    await waitFor(() =>
      expect(reportingApi.dashboard).toHaveBeenCalledWith({ period: '30d' })
    )
  })

  it('n’appelle pas le serveur tant que la plage personnalisée est incomplète', async () => {
    // Sans cette garde, chaque frappe dans le champ de date déclencherait un
    // calcul complet sur toute la base du client.
    servir()
    render(<ReportingPage />)
    await screen.findByText('14')
    reportingApi.dashboard.mockClear()

    await userEvent.click(screen.getByRole('button', { name: 'Période personnalisée' }))

    expect(reportingApi.dashboard).not.toHaveBeenCalled()
  })
})
