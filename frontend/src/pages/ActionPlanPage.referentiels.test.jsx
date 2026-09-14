import { render, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import ActionPlanPage from './ActionPlanPage'

// Lot B — B3.10 et B20. Quand un client suit plusieurs référentiels, une
// action sans provenance visible laisse le client se demander pourquoi elle
// apparaît ; et un plan mélangé sans vue par référentiel ne permet pas de
// suivre l'un sans l'autre.

vi.mock('../api/endpoints', () => ({
  actionsApi: { listAll: vi.fn(), projectedScore: vi.fn(), update: vi.fn() },
  tenantsApi: { listMembers: vi.fn(() => Promise.resolve({ data: { results: [] } })) },
}))
vi.mock('../components/ui/Toast', () => ({ useToast: () => ({ showToast: vi.fn() }) }))
// Les cartes replient leur référence technique selon le profil d'affichage,
// qui se lit dans la session (`useAuth`). Hors de l'application, pas de
// session : on rend le détail tel quel, sans ce contexte.
vi.mock('../components/DisplayProfile', () => ({
  TechnicalDetail: ({ summary, children }) => (
    <div>
      <span>{summary}</span>
      {children}
    </div>
  ),
}))

const { actionsApi } = await import('../api/endpoints')

function action(id, referentiel, domaine, enonce) {
  return {
    id,
    status: 'todo',
    priority: 1,
    assignee: null,
    assignee_email: null,
    due_date: null,
    is_overdue: false,
    domain_name: domaine,
    referential_slug: referentiel.slug,
    referential_name: referentiel.name,
    measure: {
      code: String(id),
      // Intitulé officiel et énoncé DIFFÉRENTS, comme dans un vrai
      // référentiel : identiques, chaque texte apparaîtrait deux fois par
      // carte et aucune recherche ne serait univoque.
      official_title: `Intitulé officiel ${id}`,
      statement: enonce,
      impact: 'medium',
      effort: 'medium',
      level: '',
      weight: 1,
    },
  }
}

const ANSSI = { slug: 'anssi', name: 'ANSSI' }
const ISO = { slug: 'iso', name: 'ISO 27001' }

function afficher() {
  return render(
    <MemoryRouter>
      <ActionPlanPage />
    </MemoryRouter>
  )
}

describe('ActionPlanPage — plusieurs référentiels', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    actionsApi.projectedScore.mockResolvedValue({ data: { global_score: 70 } })
    actionsApi.listAll.mockResolvedValue([
      action(1, ANSSI, 'Sensibiliser', 'Former les équipes'),
      action(2, ISO, 'Organisation', 'Écrire la politique'),
    ])
  })

  it('dit de quel référentiel vient chaque action, sur la carte elle-même', async () => {
    afficher()

    const enonce = await screen.findByText('Former les équipes')
    const carte = enonce.closest('[class~="space-y-2.5"]')
    // L'étiquette visible, et non la seule référence repliée dans le détail.
    expect(within(carte).getByText('ANSSI')).toBeInTheDocument()
  })

  it('propose une vue par référentiel, et une vue d’ensemble', async () => {
    afficher()
    await screen.findByText('Former les équipes')

    await userEvent.selectOptions(screen.getByLabelText('Référentiel'), 'iso')

    expect(screen.getByText('Écrire la politique')).toBeInTheDocument()
    expect(screen.queryByText('Former les équipes')).not.toBeInTheDocument()
  })

  it('explique la règle de consolidation sur la vue d’ensemble', async () => {
    afficher()

    expect(await screen.findByText(/chaque référentiel compte pour un/)).toBeInTheDocument()
  })

  it('avec un seul référentiel, ni filtre ni étiquette superflus', async () => {
    actionsApi.listAll.mockResolvedValue([action(1, ANSSI, 'Sensibiliser', 'Former les équipes')])
    afficher()
    const enonce = await screen.findByText('Former les équipes')

    expect(screen.queryByLabelText('Référentiel')).not.toBeInTheDocument()
    expect(screen.queryByText(/chaque référentiel compte pour un/)).not.toBeInTheDocument()
    const carte = enonce.closest('[class~="space-y-2.5"]')
    expect(within(carte).queryByText('ANSSI')).not.toBeInTheDocument()
  })
})
