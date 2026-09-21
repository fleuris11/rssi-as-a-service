import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import {
  ImportSalaries,
  PropositionsPreuve,
  RapportCampagne,
  ReglagesRelances,
} from './PilotageCampagne'

vi.mock('../../api/endpoints', () => ({
  formationApi: {
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

const { formationApi } = await import('../../api/endpoints')

const POLITIQUE = { enabled: true, mid_course: true, before_due_days: 3, after_due_days: 2 }

const RAPPORT = {
  summary: {
    learners_total: 3,
    not_started: 1,
    in_progress: 1,
    completed: 1,
    participation_rate: 67,
    success_rate: 33,
    average_score: 75,
    attempts_total: 2,
  },
  hardest_questions: [
    {
      question_id: 'q1',
      text: 'Que fait le sentiment d’urgence ?',
      course_title: 'Hameçonnage',
      screen_title: 'Signe n° 1',
      screen_order: 3,
      answers: 6,
      failed: 4,
      failure_rate: 67,
    },
  ],
  campaigns: [],
}

describe('ReglagesRelances', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    formationApi.relances.mockResolvedValue({ data: POLITIQUE })
  })

  it('permet de tout couper', async () => {
    formationApi.reglerRelances.mockResolvedValue({ data: { ...POLITIQUE, enabled: false } })
    render(<ReglagesRelances onErreur={vi.fn()} />)

    await userEvent.click(await screen.findByRole('button', { name: /Tout couper/ }))

    // Une relance qu'on ne peut pas couper devient du harcèlement.
    await waitFor(() =>
      expect(formationApi.reglerRelances).toHaveBeenCalledWith(
        expect.objectContaining({ enabled: false })
      )
    )
  })

  it('coupe chaque moment séparément', async () => {
    formationApi.reglerRelances.mockResolvedValue({ data: { ...POLITIQUE, mid_course: false } })
    render(<ReglagesRelances onErreur={vi.fn()} />)

    await userEvent.click(await screen.findByLabelText('À mi-parcours'))

    await waitFor(() =>
      expect(formationApi.reglerRelances).toHaveBeenCalledWith(
        expect.objectContaining({ mid_course: false })
      )
    )
  })

  it('cache les réglages quand tout est coupé', async () => {
    formationApi.relances.mockResolvedValue({ data: { ...POLITIQUE, enabled: false } })
    render(<ReglagesRelances onErreur={vi.fn()} />)

    expect(await screen.findByRole('button', { name: /Réactiver/ })).toBeInTheDocument()
    expect(screen.queryByLabelText('À mi-parcours')).not.toBeInTheDocument()
  })
})

describe('RapportCampagne', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    formationApi.rapport.mockResolvedValue({ data: RAPPORT })
  })

  it('montre les agrégats', async () => {
    render(<RapportCampagne onErreur={vi.fn()} />)

    expect(await screen.findByText('Où en sont les équipes')).toBeInTheDocument()
    expect(screen.getByText('67 %')).toBeInTheDocument()
  })

  it('met en avant les questions les plus ratées', async () => {
    render(<RapportCampagne onErreur={vi.fn()} />)

    // C'est l'information la plus utile : elle dit ce que l'entreprise ne
    // maîtrise pas.
    expect(await screen.findByText('Que fait le sentiment d’urgence ?')).toBeInTheDocument()
    expect(screen.getByText('67 % d’échec')).toBeInTheDocument()
    expect(screen.getByText(/Écran 3 — Signe n° 1/)).toBeInTheDocument()
  })

  it('ne charge PAS le suivi nominatif tout seul', async () => {
    render(<RapportCampagne onErreur={vi.fn()} />)
    await screen.findByText('Où en sont les équipes')

    // Sa consultation est enregistrée côté serveur : elle ne doit pas partir
    // d'un simple affichage de page.
    expect(formationApi.suivi).not.toHaveBeenCalled()
    expect(screen.getByRole('button', { name: /Afficher la liste/ })).toBeInTheDocument()
  })

  it('affiche le suivi sans aucun score, et le dit', async () => {
    formationApi.suivi.mockResolvedValue({
      data: {
        results: [
          {
            enrollment_id: 'i1',
            full_name: 'Camille Martin',
            email: 'camille@exemple.fr',
            course_title: 'Hameçonnage',
            due_date: '2026-10-01',
            state: 'pas_commence',
            overdue: false,
          },
        ],
        notice: 'Cette liste sert à relancer. Sa consultation est enregistrée…',
      },
    })
    render(<RapportCampagne onErreur={vi.fn()} />)
    await screen.findByText('Où en sont les équipes')

    await userEvent.click(screen.getByRole('button', { name: /Afficher la liste/ }))

    expect(await screen.findByText('Camille Martin')).toBeInTheDocument()
    expect(screen.getByText('Pas commencé')).toBeInTheDocument()
    expect(screen.getByText(/consultation est enregistrée/)).toBeInTheDocument()
  })
})

describe('ImportSalaries', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('rend le détail ligne par ligne', async () => {
    formationApi.importer.mockResolvedValue({
      data: {
        crees: [{ id: 's1', full_name: 'Alex Dubois' }],
        deja_presents: [],
        invalides: [{ ligne: 2, raison: 'Il manque une colonne.' }],
      },
    })
    render(<ImportSalaries onImporte={vi.fn()} onErreur={vi.fn()} />)

    await userEvent.type(screen.getByLabelText(/collez la liste/), 'Alex Dubois;alex@exemple.fr')
    await userEvent.click(screen.getByRole('button', { name: /Importer/ }))

    expect(await screen.findByText(/1 salarié\(s\) déclaré\(s\)/)).toBeInTheDocument()
    // Un import qui ne dit pas quelle ligne a échoué oblige à tout reprendre.
    expect(screen.getByText(/Ligne 2 — Il manque une colonne\./)).toBeInTheDocument()
  })
})

describe('PropositionsPreuve', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('ne montre rien quand il n’y a rien à proposer', async () => {
    formationApi.preuves.mockResolvedValue({ data: [] })
    const { container } = render(<PropositionsPreuve onErreur={vi.fn()} />)

    await waitFor(() => expect(formationApi.preuves).toHaveBeenCalled())
    expect(container).toBeEmptyDOMElement()
  })

  it('demande une confirmation, et ne coche rien tout seul', async () => {
    formationApi.preuves.mockResolvedValue({
      data: [
        {
          id: 'p1',
          measure_title: 'Sensibiliser les utilisateurs',
          evidence: 'Campagne de formation « Hameçonnage »…',
          participation_rate: 100,
          success_rate: 100,
        },
      ],
    })
    formationApi.confirmerPreuve.mockResolvedValue({ data: {} })
    render(<PropositionsPreuve onErreur={vi.fn()} />)

    expect(await screen.findByText(/Rien n’est coché tant que vous/)).toBeInTheDocument()

    await userEvent.click(screen.getByRole('button', { name: /Confirmer et renseigner/ }))
    await waitFor(() => expect(formationApi.confirmerPreuve).toHaveBeenCalledWith('p1'))
  })

  it('permet d’écarter une proposition', async () => {
    formationApi.preuves.mockResolvedValue({
      data: [{ id: 'p1', measure_title: 'Sensibiliser', evidence: '…' }],
    })
    formationApi.ecarterPreuve.mockResolvedValue({ data: {} })
    render(<PropositionsPreuve onErreur={vi.fn()} />)

    await userEvent.click(await screen.findByRole('button', { name: 'Écarter' }))

    await waitFor(() => expect(formationApi.ecarterPreuve).toHaveBeenCalledWith('p1'))
  })
})
