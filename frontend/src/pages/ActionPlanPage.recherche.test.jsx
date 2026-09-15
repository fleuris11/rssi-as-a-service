import { render, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import ActionPlanPage from './ActionPlanPage'

// Lot C, point 22 : un plan compte vite plus de vingt actions — quarante-deux
// pour le seul guide d'hygiène.

vi.mock('../api/endpoints', () => ({
  actionsApi: { listAll: vi.fn(), projectedScore: vi.fn(), update: vi.fn() },
  tenantsApi: { listMembers: vi.fn(() => Promise.resolve({ data: { results: [] } })) },
}))
vi.mock('../components/ui/Toast', () => ({ useToast: () => ({ showToast: vi.fn() }) }))

const { actionsApi } = await import('../api/endpoints')

function action(id, code, statement, { overdue = false } = {}) {
  return {
    id,
    priority: 1,
    status: 'todo',
    measure: {
      code,
      statement,
      official_title: statement,
      impact: 3,
      effort: 1,
      level: 'standard',
      weight: 1,
    },
    domain_name: 'Sensibiliser et former',
    referential_name: 'Guide d’hygiène',
    referential_slug: 'anssi-hygiene',
    is_overdue: overdue,
    due_date: overdue ? '2026-01-01' : null,
    assignee: null,
    assignee_email: '',
  }
}

function afficher() {
  return render(
    <MemoryRouter>
      <ActionPlanPage />
    </MemoryRouter>
  )
}

describe('ActionPlanPage — chercher une action', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    actionsApi.projectedScore.mockResolvedValue({ data: null })
    actionsApi.listAll.mockResolvedValue([
      action(1, 'M01', 'Former les équipes à la sécurité'),
      action(2, 'M02', 'Sauvegarder les données hors ligne', { overdue: true }),
    ])
  })

  it('filtre les actions par leur intitulé, sans tenir compte des accents', async () => {
    afficher()

    await userEvent.type(await screen.findByRole('searchbox', { name: 'Rechercher une action' }), 'equipes')

    expect(screen.getAllByText('Former les équipes à la sécurité').length).toBeGreaterThan(0)
    expect(screen.queryByText('Sauvegarder les données hors ligne')).not.toBeInTheDocument()
    expect(screen.getByText('1 action(s) affichée(s)')).toBeInTheDocument()
  })

  it('n’affiche que les actions en retard sur demande', async () => {
    afficher()

    await userEvent.click(await screen.findByRole('checkbox', { name: 'En retard seulement' }))

    expect(screen.getAllByText('Sauvegarder les données hors ligne').length).toBeGreaterThan(0)
    expect(screen.queryByText('Former les équipes à la sécurité')).not.toBeInTheDocument()
    expect(within(document.body).getByText('1 action(s) affichée(s)')).toBeInTheDocument()
  })
})
