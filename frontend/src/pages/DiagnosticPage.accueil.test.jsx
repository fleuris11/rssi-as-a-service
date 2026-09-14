import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import DiagnosticPage from './DiagnosticPage'

// Lot B — l'écran Diagnostic devient un ACCUEIL.
//
// Le défaut que ces tests épinglent : avec un seul référentiel, l'écran
// démarrait tout seul le questionnaire complet. C'était le parcours d'avant
// V2-4 — et c'est aussi ce qui rendait « les 10 mesures essentielles »
// invisible pour TOUS les clients réels, qui n'ont qu'un référentiel. On ne
// choisit pas 42 questions à la place d'un dirigeant quand on lui en propose 10.

vi.mock('../api/endpoints', () => ({
  assessmentsApi: {
    listReferentials: vi.fn(),
    referential: vi.fn(),
    current: vi.fn(),
    start: vi.fn(),
    detail: vi.fn(),
    submitAnswer: vi.fn(),
    complete: vi.fn(),
    importReferential: vi.fn(),
    referentialTemplate: vi.fn(),
  },
  accessRequestsApi: {
    list: vi.fn(() => Promise.resolve({ data: [] })),
    create: vi.fn(),
  },
}))

vi.mock('../components/ui/Toast', () => ({ useToast: () => ({ showToast: vi.fn() }) }))
vi.mock('../context/EntitlementsContext', () => ({
  useEntitlements: () => ({ hasFeature: () => true }),
}))

const { assessmentsApi } = await import('../api/endpoints')

const ESSENTIELLES = {
  slug: 'anssi-10-essentielles',
  name: 'Les 10 mesures essentielles',
  description: 'Par où commencer.',
  measure_count: 10,
}

const ANSSI = {
  id: 1,
  slug: 'anssi-hygiene-informatique',
  name: 'Guide d’hygiène informatique (ANSSI)',
  publisher: 'ANSSI',
  granted: true,
  readable: true,
  measure_count: 42,
  assessment_status: 'completed',
  last_score: 63.4,
  last_assessed_at: '2026-09-01T10:00:00Z',
  available_subsets: [ESSENTIELLES],
}

function structure(nbMesures) {
  return {
    data: {
      slug: ANSSI.slug,
      name: ANSSI.name,
      description: '',
      publisher: 'ANSSI',
      licence_notice: '',
      granted: true,
      subset: null,
      domains: [
        {
          id: 1,
          code: 'domaine-a',
          name: 'Domaine A',
          description: '',
          order: 1,
          measures: Array.from({ length: nbMesures }, (_, i) => ({
            id: 100 + i,
            code: String(i + 1),
            official_title: `Mesure ${i + 1}`,
            plain_language: `Question ${i + 1} ?`,
            statement: `Question ${i + 1} ?`,
            context_note: '',
            is_overridden: false,
          })),
        },
      ],
    },
  }
}

function evaluation(subsetSlug = null) {
  return {
    data: {
      id: 9,
      referential_slug: ANSSI.slug,
      subset_slug: subsetSlug,
      subset_name: subsetSlug ? ESSENTIELLES.name : null,
      answers: [],
      progress: {
        answered: 0,
        total: 2,
        by_domain: [{ domain_code: 'domaine-a', answered: 0, total: 2 }],
      },
    },
  }
}

function afficher() {
  return render(
    <MemoryRouter>
      <DiagnosticPage />
    </MemoryRouter>
  )
}

describe('DiagnosticPage — l’accueil et les compositions', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    assessmentsApi.listReferentials.mockResolvedValue({ data: [ANSSI] })
    assessmentsApi.current.mockRejectedValue({ response: { status: 404 } })
    assessmentsApi.referential.mockImplementation((slug, composition) =>
      Promise.resolve(structure(composition ? 2 : 4))
    )
  })

  it('ne démarre pas seul le questionnaire complet quand une composition est proposée', async () => {
    afficher()

    expect(
      await screen.findByRole('button', { name: 'Commencer par ce questionnaire' })
    ).toBeInTheDocument()
    expect(screen.getByText(/Les 10 mesures essentielles — 10 mesures/)).toBeInTheDocument()
    expect(assessmentsApi.start).not.toHaveBeenCalled()
  })

  it('dit où en est le client sur ce référentiel', async () => {
    afficher()

    expect(await screen.findByText(/Terminé · dernier score 63\/100/)).toBeInTheDocument()
  })

  it('démarre sur la composition, et charge la structure de SON périmètre', async () => {
    assessmentsApi.start.mockResolvedValue(evaluation(ESSENTIELLES.slug))
    afficher()

    await userEvent.click(
      await screen.findByRole('button', { name: 'Commencer par ce questionnaire' })
    )

    await waitFor(() =>
      expect(assessmentsApi.start).toHaveBeenCalledWith(ANSSI.slug, ESSENTIELLES.slug)
    )
    expect(assessmentsApi.referential).toHaveBeenCalledWith(ANSSI.slug, ESSENTIELLES.slug)
    // Deux questions affichées, pas quatre : le périmètre de la composition.
    expect(await screen.findByText('Question 2 ?')).toBeInTheDocument()
    expect(screen.queryByText('Question 3 ?')).not.toBeInTheDocument()
  })

  it('le questionnaire complet reste proposé, et son appel ne change pas', async () => {
    assessmentsApi.start.mockResolvedValue(evaluation())
    afficher()

    await userEvent.click(await screen.findByRole('button', { name: 'Démarrer ce diagnostic' }))

    await waitFor(() => expect(assessmentsApi.start).toHaveBeenCalledWith(ANSSI.slug))
  })

  it('reprend une évaluation sur composition avec la structure de son périmètre', async () => {
    // Le défaut qu'on évite : une évaluation ouverte sur dix mesures qui,
    // à la reprise, afficherait les quarante-deux.
    assessmentsApi.current.mockResolvedValue(evaluation(ESSENTIELLES.slug))
    afficher()

    expect(await screen.findByText('Question 2 ?')).toBeInTheDocument()
    expect(assessmentsApi.referential).toHaveBeenCalledWith(ANSSI.slug, ESSENTIELLES.slug)
    expect(screen.queryByText('Question 3 ?')).not.toBeInTheDocument()
  })

  it('propose d’importer son propre référentiel', async () => {
    afficher()

    expect(
      await screen.findByRole('button', { name: 'Importer votre propre référentiel' })
    ).toBeInTheDocument()
  })

  it('sans composition proposée, le parcours d’avant ne change pas', async () => {
    assessmentsApi.listReferentials.mockResolvedValue({
      data: [{ ...ANSSI, available_subsets: [] }],
    })
    assessmentsApi.start.mockResolvedValue(evaluation())
    afficher()

    // Rien à choisir : on entre directement dans le questionnaire.
    expect(await screen.findByText('Question 1 ?')).toBeInTheDocument()
    expect(assessmentsApi.start).toHaveBeenCalledWith(ANSSI.slug)
  })
})
