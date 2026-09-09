import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import DiagnosticPage from './DiagnosticPage'

// V2-4 : l'écran ne connaît plus « le » référentiel. Trois comportements
// valent d'être tenus par des tests, parce qu'ils se contredisent facilement
// en cours de route :
//
// 1. avec UN seul référentiel, le parcours d'avant ne change pas — on entre
//    dans le questionnaire sans rien choisir ;
// 2. avec PLUSIEURS, on choisit, et surtout on n'ouvre pas une évaluation
//    par simple curiosité ;
// 3. ce qui n'est pas attribué reste visible et se demande.

vi.mock('../api/endpoints', () => ({
  assessmentsApi: {
    listReferentials: vi.fn(),
    referential: vi.fn(),
    current: vi.fn(),
    start: vi.fn(),
    detail: vi.fn(),
    submitAnswer: vi.fn(),
    complete: vi.fn(),
  },
  accessRequestsApi: {
    list: vi.fn(() => Promise.resolve({ data: [] })),
    create: vi.fn(),
  },
}))

vi.mock('../components/ui/Toast', () => ({
  useToast: () => ({ showToast: vi.fn() }),
}))

vi.mock('../context/EntitlementsContext', () => ({
  useEntitlements: () => ({ hasFeature: () => true }),
}))

const { accessRequestsApi, assessmentsApi } = await import('../api/endpoints')

const ANSSI = {
  id: 1,
  slug: 'anssi-hygiene-informatique',
  name: 'Guide d’hygiène informatique (ANSSI)',
  publisher: 'ANSSI',
  granted: true,
  readable: true,
  measure_count: 42,
}
const ISO = {
  id: 2,
  slug: 'iso-27001-annexe-a',
  name: 'ISO/IEC 27001 — Annexe A',
  publisher: 'ISO/IEC',
  granted: true,
  readable: true,
  measure_count: 93,
}
const NIST = {
  id: 3,
  slug: 'nist-csf',
  name: 'NIST CSF 2.0',
  publisher: 'NIST',
  granted: false,
  readable: false,
  measure_count: 0,
}

function structure(nom) {
  return {
    data: {
      slug: 'x',
      name: nom,
      description: '',
      publisher: '',
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
          measures: [
            {
              id: 10,
              code: '1',
              official_title: 'Intitulé officiel',
              plain_language: 'Énoncé d’origine ?',
              statement: 'Énoncé d’origine ?',
              context_note: '',
              is_overridden: false,
            },
          ],
        },
      ],
    },
  }
}

const EVALUATION = {
  data: {
    id: 7,
    referential_slug: ANSSI.slug,
    subset_name: null,
    answers: [],
    progress: { answered: 0, total: 1, by_domain: [{ domain_code: 'domaine-a', answered: 0, total: 1 }] },
  },
}

function afficher() {
  return render(
    <MemoryRouter>
      <DiagnosticPage />
    </MemoryRouter>
  )
}

describe('DiagnosticPage — plusieurs référentiels', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    accessRequestsApi.list.mockResolvedValue({ data: [] })
    assessmentsApi.referential.mockResolvedValue(structure('Guide d’hygiène informatique (ANSSI)'))
  })

  it('entre directement dans le questionnaire quand il n’y a rien à choisir', async () => {
    assessmentsApi.listReferentials.mockResolvedValue({ data: [ANSSI] })
    assessmentsApi.current.mockResolvedValue(EVALUATION)

    afficher()

    expect(await screen.findByText('Énoncé d’origine ?')).toBeInTheDocument()
    // Le parcours d'avant V2-4 : aucun écran de choix ne s'intercale.
    expect(screen.queryByRole('tablist')).not.toBeInTheDocument()
  })

  it('propose de choisir, sans ouvrir d’évaluation, quand il y en a plusieurs', async () => {
    assessmentsApi.listReferentials.mockResolvedValue({ data: [ANSSI, ISO] })
    // Aucune évaluation en cours sur le référentiel choisi.
    assessmentsApi.current.mockRejectedValue({ response: { status: 404 } })

    afficher()

    expect(await screen.findByRole('button', { name: 'Démarrer ce diagnostic' })).toBeInTheDocument()
    expect(screen.getByRole('tab', { name: ISO.name })).toBeInTheDocument()
    // Le point important : se promener d'un référentiel à l'autre ne doit pas
    // ouvrir des évaluations vides dans le dos du client.
    expect(assessmentsApi.start).not.toHaveBeenCalled()
  })

  it('démarre sur le référentiel choisi, et sur lui seul', async () => {
    assessmentsApi.listReferentials.mockResolvedValue({ data: [ANSSI, ISO] })
    assessmentsApi.current.mockRejectedValue({ response: { status: 404 } })
    assessmentsApi.start.mockResolvedValue(EVALUATION)

    afficher()
    await screen.findByRole('button', { name: 'Démarrer ce diagnostic' })
    await userEvent.click(screen.getByRole('tab', { name: ISO.name }))
    await userEvent.click(await screen.findByRole('button', { name: 'Démarrer ce diagnostic' }))

    await waitFor(() => expect(assessmentsApi.start).toHaveBeenCalledWith(ISO.slug))
  })

  it('affiche ce qui n’est pas attribué et permet de le demander', async () => {
    assessmentsApi.listReferentials.mockResolvedValue({ data: [ANSSI, NIST] })
    assessmentsApi.current.mockResolvedValue(EVALUATION)
    accessRequestsApi.create.mockResolvedValue({
      data: { id: 1, subject_key: NIST.slug, status: 'pending' },
    })

    afficher()

    // Affiché, pas masqué : le client doit savoir que le produit sait le faire.
    expect(await screen.findByText(NIST.name)).toBeInTheDocument()
    await userEvent.click(screen.getByRole('button', { name: 'Demander l’accès' }))
    await userEvent.type(
      screen.getByLabelText(/Pourquoi en avez-vous besoin/),
      'Exigé par notre assureur.'
    )
    await userEvent.click(screen.getByRole('button', { name: 'Envoyer la demande' }))

    await waitFor(() =>
      expect(accessRequestsApi.create).toHaveBeenCalledWith({
        subject_type: 'referential',
        subject_key: NIST.slug,
        reason: 'Exigé par notre assureur.',
      })
    )
    expect(await screen.findByText('Demande en cours d’examen')).toBeInTheDocument()
  })

  it('affiche l’énoncé reformulé par l’entreprise quand il y en a un', async () => {
    assessmentsApi.listReferentials.mockResolvedValue({ data: [ANSSI] })
    assessmentsApi.current.mockResolvedValue(EVALUATION)
    const reformule = structure('ANSSI')
    reformule.data.domains[0].measures[0].statement = 'Notre formulation à nous ?'
    reformule.data.domains[0].measures[0].is_overridden = true
    assessmentsApi.referential.mockResolvedValue(reformule)

    afficher()

    expect(await screen.findByText('Notre formulation à nous ?')).toBeInTheDocument()
    // L'énoncé d'origine ne s'affiche plus à sa place — mais il n'a pas
    // disparu : c'est l'intitulé officiel qui reste sous les yeux.
    expect(screen.queryByText('Énoncé d’origine ?')).not.toBeInTheDocument()
    expect(screen.getByText('Intitulé officiel')).toBeInTheDocument()
  })
})
