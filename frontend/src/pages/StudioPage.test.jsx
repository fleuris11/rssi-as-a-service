import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import StudioPage from './StudioPage'

vi.mock('../api/endpoints', () => ({
  formationApi: {
    studioCours: vi.fn(),
    studioCreerCours: vi.fn(),
    studioCours1: vi.fn(),
    studioVersion: vi.fn(),
    studioDupliquer: vi.fn(),
    studioNouvelleVersion: vi.fn(),
    studioPublier: vi.fn(),
    studioEcrireEcran: vi.fn(),
    studioOrdreEcrans: vi.fn(),
    studioSupprimerEcran: vi.fn(),
  },
}))

const { formationApi } = await import('../api/endpoints')

const VARIABLES = [
  { cle: 'fuites_ouvertes', libelle: 'Compromissions ouvertes', description: '…', feature: '' },
]

function cours(surcharges = {}) {
  return {
    id: 'c1',
    slug: 'mon-cours',
    title: 'Mon cours',
    summary: '',
    is_library: false,
    derived_from: '',
    published_version: null,
    draft_version: 1,
    draft_version_id: 'v1',
    published_version_id: '',
    screens: 1,
    ...surcharges,
  }
}

function version(surcharges = {}) {
  return {
    course_title: 'Mon cours',
    course_version: 1,
    estimated_minutes: 3,
    pass_threshold: 70,
    max_attempts: 3,
    is_published: false,
    screens: [
      {
        id: 'e1',
        order: 1,
        title: 'Premier écran',
        content: [{ type: 'paragraphe', texte: 'Un contenu.' }],
        content_brut: [{ type: 'paragraphe', texte: 'Un contenu.' }],
        estimated_seconds: 60,
      },
    ],
    questions: [],
    blocking: [],
    warnings: [],
    ...surcharges,
  }
}

describe('StudioPage', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    formationApi.studioCours.mockResolvedValue({
      data: {
        mine: [cours()],
        library: [cours({ id: 'b1', title: 'Cours de la maison', is_library: true })],
        variables: VARIABLES,
      },
    })
    formationApi.studioCours1.mockResolvedValue({ data: cours() })
    formationApi.studioVersion.mockResolvedValue({ data: version() })
  })

  it('montre mes cours et la bibliothèque séparément', async () => {
    render(<StudioPage />)

    expect(await screen.findByText('Mes cours')).toBeInTheDocument()
    expect(screen.getByText('Bibliothèque')).toBeInTheDocument()
    expect(screen.getByText('Cours de la maison')).toBeInTheDocument()
  })

  it('crée un cours et l’ouvre', async () => {
    formationApi.studioCreerCours.mockResolvedValue({ data: cours({ id: 'c2' }) })
    render(<StudioPage />)

    await screen.findByText('Mes cours')
    await userEvent.type(screen.getByLabelText('Titre du cours'), 'Hameçonnage')
    await userEvent.click(screen.getByRole('button', { name: /Créer/ }))

    await waitFor(() =>
      expect(formationApi.studioCreerCours).toHaveBeenCalledWith({ title: 'Hameçonnage' })
    )
  })

  it('dérive un cours de la bibliothèque', async () => {
    formationApi.studioDupliquer.mockResolvedValue({ data: cours({ id: 'c3' }) })
    render(<StudioPage />)

    await screen.findByText('Cours de la maison')
    const lignes = screen.getAllByRole('button', { name: /Dupliquer/ })
    await userEvent.click(lignes.at(-1))

    await waitFor(() => expect(formationApi.studioDupliquer).toHaveBeenCalledWith('b1', {}))
  })

  it('passe en lecture seule sur une version publiée, et propose d’en ouvrir une nouvelle', async () => {
    formationApi.studioCours1.mockResolvedValue({
      data: cours({ published_version: 1, draft_version: null, draft_version_id: '', published_version_id: 'v1' }),
    })
    formationApi.studioVersion.mockResolvedValue({ data: version({ is_published: true }) })
    render(<StudioPage />)

    await screen.findByText('Mes cours')
    await userEvent.click(screen.getByRole('button', { name: 'Ouvrir' }))

    expect(await screen.findByText(/ne se modifie plus/)).toBeInTheDocument()
    expect(
      screen.getByRole('button', { name: 'Ouvrir une nouvelle version' })
    ).toBeInTheDocument()
    // Rien à enregistrer : les champs d'édition ne sont pas proposés.
    expect(screen.queryByRole('button', { name: /Enregistrer cet écran/ })).not.toBeInTheDocument()
  })

  it('exige une formulation de repli dès qu’un bloc contient une variable', async () => {
    formationApi.studioVersion.mockResolvedValue({
      data: version({
        screens: [
          {
            id: 'e1',
            order: 1,
            title: 'Écran',
            content: [],
            content_brut: [
              { type: 'paragraphe', texte: 'Vous avez {fuites_ouvertes} comptes.', repli: '' },
            ],
            estimated_seconds: 60,
          },
        ],
      }),
    })
    render(<StudioPage />)

    await screen.findByText('Mes cours')
    await userEvent.click(screen.getByRole('button', { name: 'Ouvrir' }))

    // Le champ n'apparaît QUE là où il est nécessaire, et il est requis.
    const repli = await screen.findByLabelText(/Formulation de repli/)
    expect(repli).toBeRequired()
  })

  it('propose les variables du serveur, et pas d’autres', async () => {
    render(<StudioPage />)
    await screen.findByText('Mes cours')
    await userEvent.click(screen.getByRole('button', { name: 'Ouvrir' }))

    expect(
      await screen.findByRole('button', { name: 'Compromissions ouvertes' })
    ).toBeInTheDocument()
  })
})
