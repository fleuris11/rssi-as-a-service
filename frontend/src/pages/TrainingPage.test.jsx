import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import TrainingPage from './TrainingPage'

vi.mock('../api/endpoints', () => ({
  formationApi: {
    catalogue: vi.fn(),
    salaries: vi.fn(),
    inscriptions: vi.fn(),
    creerSalarie: vi.fn(),
    inscrire: vi.fn(),
    revoquer: vi.fn(),
    reemettreLien: vi.fn(),
    accorderEssai: vi.fn(),
    // F3 : l'écran charge aussi le rapport, les relances et les propositions.
    relances: vi.fn(),
    reglerRelances: vi.fn(),
    importer: vi.fn(),
    rapport: vi.fn(),
    suivi: vi.fn(),
    exportRapport: vi.fn(),
    preuves: vi.fn(),
    confirmerPreuve: vi.fn(),
    ecarterPreuve: vi.fn(),
  },
}))

const { formationApi } = await import('../api/endpoints')

const COURS = [
  {
    slug: 'hameconnage',
    title: 'Reconnaître un courriel d’hameçonnage',
    summary: '',
    estimated_minutes: 10,
    pass_threshold: 70,
    max_attempts: 3,
    screens: 7,
    questions: 6,
  },
]

const SALARIES = [
  { id: 's1', full_name: 'Camille Martin', email: 'camille@exemple.fr', is_active: true },
]

function inscription(surcharges = {}) {
  return {
    id: 'i1',
    learner: { id: 's1', full_name: 'Camille Martin', email: 'camille@exemple.fr' },
    course_title: 'Reconnaître un courriel d’hameçonnage',
    course_version: 1,
    due_date: '2026-10-01',
    expires_at: '2026-10-08T23:59:59Z',
    first_opened_at: null,
    revoked_at: null,
    attempts_allowed: 3,
    certificate_serial: '',
    passed: false,
    ...surcharges,
  }
}

describe('TrainingPage', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    formationApi.catalogue.mockResolvedValue({ data: COURS })
    formationApi.salaries.mockResolvedValue({ data: SALARIES })
    formationApi.inscriptions.mockResolvedValue({ data: [inscription()] })
    // Les blocs de F3 se chargent seuls : on les neutralise ici pour que ces
    // tests restent ceux de l'inscription.
    formationApi.relances.mockResolvedValue({
      data: { enabled: true, mid_course: true, before_due_days: 3, after_due_days: 2 },
    })
    formationApi.rapport.mockResolvedValue({
      data: {
        summary: {
          learners_total: 1,
          not_started: 1,
          in_progress: 0,
          completed: 0,
          participation_rate: 0,
          success_rate: 0,
          average_score: null,
          attempts_total: 0,
        },
        hardest_questions: [],
        campaigns: [],
      },
    })
    formationApi.preuves.mockResolvedValue({ data: [] })
  })

  it('affiche le lien à l’émission, et jamais dans la liste', async () => {
    formationApi.inscrire.mockResolvedValue({
      data: { ...inscription(), link: 'https://exemple.test/formation/jeton-en-clair' },
    })
    render(<TrainingPage />)

    await screen.findByText('Salariés inscrits')
    await userEvent.selectOptions(screen.getByLabelText('Salarié'), 's1')
    await userEvent.selectOptions(screen.getByLabelText('Cours'), 'hameconnage')
    await userEvent.type(screen.getByLabelText('Échéance de la campagne'), '2026-10-01')
    await userEvent.click(screen.getByRole('button', { name: /Inscrire et obtenir le lien/ }))

    expect(
      await screen.findByText('https://exemple.test/formation/jeton-en-clair')
    ).toBeInTheDocument()
    // Il n'est stocké que haché : le relire est impossible, et l'écran le dit.
    expect(screen.getByText(/n’est affiché qu’une fois/)).toBeInTheDocument()
  })

  it('dit l’état de chaque salarié sans révéler son lien', async () => {
    formationApi.inscriptions.mockResolvedValue({
      data: [inscription({ passed: true, certificate_serial: '2026-A1B2C3D4' })],
    })
    render(<TrainingPage />)

    expect(await screen.findByText('Validé')).toBeInTheDocument()
    expect(document.body.textContent).not.toContain('/formation/')
  })

  it('ne propose ni réémission ni essai supplémentaire sur un accès retiré', async () => {
    formationApi.inscriptions.mockResolvedValue({
      data: [inscription({ revoked_at: '2026-09-20T10:00:00Z' })],
    })
    render(<TrainingPage />)

    expect(await screen.findByText('Accès retiré')).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: /Réémettre un lien/ })).not.toBeInTheDocument()
    expect(screen.queryByRole('button', { name: /Accorder un essai/ })).not.toBeInTheDocument()
  })

  it('accorde un essai supplémentaire au salarié désigné', async () => {
    formationApi.accorderEssai.mockResolvedValue({ data: inscription() })
    render(<TrainingPage />)

    await screen.findByText('Salariés inscrits')
    await userEvent.click(screen.getByRole('button', { name: /Accorder un essai/ }))

    await waitFor(() => expect(formationApi.accorderEssai).toHaveBeenCalledWith('i1'))
  })

  it('remonte le refus du serveur tel quel', async () => {
    formationApi.creerSalarie.mockRejectedValue({
      response: { data: { detail: 'Camille Martin figure déjà dans vos salariés formés.' } },
    })
    render(<TrainingPage />)

    await screen.findByText('Déclarer un salarié')
    await userEvent.type(screen.getByLabelText('Nom et prénom'), 'Camille Martin')
    await userEvent.type(screen.getByLabelText('Adresse professionnelle'), 'camille@exemple.fr')
    await userEvent.click(screen.getByRole('button', { name: 'Déclarer' }))

    expect(
      await screen.findByText('Camille Martin figure déjà dans vos salariés formés.')
    ).toBeInTheDocument()
  })
})
