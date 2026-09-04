import { render, screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import ActionPlanPage from './ActionPlanPage'

// Défaut relevé le 04/09/2026 en parcourant l'application comme un client :
// après avoir répondu aux 42 mesures et terminé son diagnostic, un client sans
// aucun écart lisait, sur son plan d'action :
//
//     « Aucune action pour l'instant — Terminez une évaluation pour générer
//       votre plan d'action priorisé. »
//
// On lui demandait de faire ce qu'il venait de faire. Deux situations très
// différentes — « pas encore évalué » et « évalué, rien à corriger » —
// partageaient un seul message, et c'était celui de la première.
//
// Ni le code ni les tests ne le montraient : il fallait terminer le parcours
// pour le voir.

vi.mock('../api/endpoints', () => ({
  actionsApi: {
    listAll: vi.fn(),
    projectedScore: vi.fn(),
    update: vi.fn(),
  },
  tenantsApi: {
    listMembers: vi.fn(() => Promise.resolve({ data: { results: [] } })),
  },
}))

vi.mock('../components/ui/Toast', () => ({
  useToast: () => ({ showToast: vi.fn() }),
}))

const { actionsApi } = await import('../api/endpoints')

function afficher() {
  return render(
    <MemoryRouter>
      <ActionPlanPage />
    </MemoryRouter>
  )
}

describe('ActionPlanPage — le plan vide', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    actionsApi.listAll.mockResolvedValue([])
  })

  it('invite à faire le diagnostic quand aucune évaluation n’est terminée', async () => {
    // `projectedScore` échoue tant qu'aucune évaluation n'est terminée :
    // c'est ce qui distingue les deux vides.
    actionsApi.projectedScore.mockRejectedValue(new Error('aucune évaluation'))

    afficher()

    expect(await screen.findByText('Aucune action pour l’instant')).toBeInTheDocument()
    expect(screen.getByText(/Terminez une évaluation/)).toBeInTheDocument()
  })

  it('félicite au lieu de renvoyer au diagnostic quand il est déjà terminé', async () => {
    actionsApi.projectedScore.mockResolvedValue({ data: { global_score: 100 } })

    afficher()

    expect(await screen.findByText('Aucune action à mener')).toBeInTheDocument()
    expect(screen.getByText(/aucun écart/)).toBeInTheDocument()
    // Le message fautif ne doit plus apparaître : le client vient précisément
    // de terminer son évaluation.
    expect(screen.queryByText(/Terminez une évaluation/)).not.toBeInTheDocument()
  })
})
