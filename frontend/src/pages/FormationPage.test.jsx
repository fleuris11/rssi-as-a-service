import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import FormationPage from './FormationPage'

vi.mock('../api/endpoints', () => ({
  formationApi: {
    session: vi.fn(),
    marquerEcran: vi.fn(),
    soumettreQuiz: vi.fn(),
    attestation: vi.fn(),
    demanderAcces: vi.fn(),
  },
}))

const { formationApi } = await import('../api/endpoints')

function sessionFactice(surcharges = {}) {
  return {
    learner_name: 'Camille Martin',
    company_name: 'Entreprise Test',
    course_title: 'Reconnaître un courriel d’hameçonnage',
    course_summary: '',
    course_version: 1,
    estimated_minutes: 10,
    due_date: '2026-10-01',
    expires_at: '2026-10-08T23:59:59Z',
    screens: [
      { id: 'e1', order: 1, title: 'Premier écran', content: [], completed: false },
      { id: 'e2', order: 2, title: 'Deuxième écran', content: [], completed: false },
      { id: 'e3', order: 3, title: 'Troisième écran', content: [], completed: false },
    ],
    screens_total: 3,
    screens_completed: 0,
    resume_index: 0,
    quiz_unlocked: false,
    pass_threshold: 70,
    attempts_used: 0,
    attempts_allowed: 3,
    passed: false,
    certificate: null,
    quiz: [
      {
        id: 'q1',
        order: 1,
        text: 'Première question ?',
        kind: 'single',
        choices: [
          { id: 'c1', text: 'Bonne' },
          { id: 'c2', text: 'Mauvaise' },
        ],
      },
    ],
    ...surcharges,
  }
}

function afficher(token = 'jeton-de-test') {
  return render(
    <MemoryRouter initialEntries={[`/formation/${token}`]}>
      <Routes>
        <Route path="/formation/:token" element={<FormationPage />} />
      </Routes>
    </MemoryRouter>
  )
}

describe('FormationPage', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('montre une barre de progression et la position dans le cours', async () => {
    formationApi.session.mockResolvedValue({ data: sessionFactice() })
    afficher()

    expect(await screen.findByRole('heading', { name: 'Premier écran' })).toBeInTheDocument()
    const barre = screen.getByRole('progressbar', { name: 'Progression dans le cours' })
    expect(barre).toHaveAttribute('aria-valuenow', '0')
    // Savoir combien il reste est ce qui fait terminer.
    expect(screen.getByText('Écran 1 sur 3')).toBeInTheDocument()
  })

  it('dit où l’on reprend au lieu de replacer quelqu’un sans explication', async () => {
    formationApi.session.mockResolvedValue({
      data: sessionFactice({
        screens_completed: 1,
        resume_index: 1,
        screens: [
          { id: 'e1', order: 1, title: 'Premier écran', content: [], completed: true },
          { id: 'e2', order: 2, title: 'Deuxième écran', content: [], completed: false },
          { id: 'e3', order: 3, title: 'Troisième écran', content: [], completed: false },
        ],
      }),
    })
    afficher()

    expect(await screen.findByRole('heading', { name: 'Deuxième écran' })).toBeInTheDocument()
    expect(
      screen.getAllByText('Vous reprenez à l’écran 2 sur 3.').length
    ).toBeGreaterThan(0)
  })

  it('enregistre l’écran terminé en passant au suivant', async () => {
    formationApi.session.mockResolvedValue({ data: sessionFactice() })
    formationApi.marquerEcran.mockResolvedValue({
      data: sessionFactice({ screens_completed: 1 }),
    })
    afficher()

    await screen.findByRole('heading', { name: 'Premier écran' })
    await userEvent.click(screen.getByRole('button', { name: /Suivant/ }))

    expect(formationApi.marquerEcran).toHaveBeenCalledWith('jeton-de-test', 'e1')
    expect(await screen.findByRole('heading', { name: 'Deuxième écran' })).toBeInTheDocument()
  })

  it('laisse revenir en arrière sans faire reculer la progression', async () => {
    formationApi.session.mockResolvedValue({
      data: sessionFactice({ screens_completed: 2, resume_index: 2 }),
    })
    afficher()

    await screen.findByRole('heading', { name: 'Troisième écran' })
    await userEvent.click(screen.getByRole('button', { name: /Précédent/ }))

    expect(await screen.findByRole('heading', { name: 'Deuxième écran' })).toBeInTheDocument()
    // La progression enregistrée reste la progression réelle.
    expect(screen.getByRole('progressbar')).toHaveAttribute('aria-valuenow', '67')
    expect(formationApi.marquerEcran).not.toHaveBeenCalled()
  })

  it('explique chaque question après le quiz, et ne renvoie qu’aux écrans ratés', async () => {
    formationApi.session.mockResolvedValue({
      data: sessionFactice({ screens_completed: 3, resume_index: 2, quiz_unlocked: true }),
    })
    formationApi.marquerEcran.mockResolvedValue({
      data: sessionFactice({ screens_completed: 3, quiz_unlocked: true }),
    })
    formationApi.soumettreQuiz.mockResolvedValue({
      data: {
        score: 50,
        passed: false,
        pass_threshold: 70,
        attempt_number: 1,
        attempts_used: 1,
        attempts_allowed: 3,
        questions: [
          {
            id: 'q1',
            text: 'Première question ?',
            correct: false,
            explanation: 'Parce que l’urgence sert à empêcher de vérifier.',
            correct_choice_ids: ['c1'],
            selected_choice_ids: ['c2'],
            screen: { id: 'e1', order: 1, title: 'Premier écran' },
          },
        ],
        screens_to_review: [{ id: 'e1', order: 1, title: 'Premier écran' }],
        certificate: null,
      },
    })

    afficher()
    await screen.findByRole('heading', { name: 'Troisième écran' })
    await userEvent.click(screen.getByRole('button', { name: /Passer au questionnaire/ }))

    await screen.findByRole('heading', { name: 'Questionnaire' })
    await userEvent.click(screen.getByLabelText('Bonne'))
    await userEvent.click(screen.getByRole('button', { name: 'Valider mes réponses' }))

    expect(await screen.findByText(/Ce n’est pas encore validé/)).toBeInTheDocument()
    // Un quiz qui dit seulement « faux » n'apprend rien.
    expect(
      screen.getByText('Parce que l’urgence sert à empêcher de vérifier.')
    ).toBeInTheDocument()
    // Et on ne renvoie pas dans le cours entier.
    expect(screen.getByRole('button', { name: /Écran 1 — Premier écran/ })).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: /Écran 2/ })).not.toBeInTheDocument()
  })

  it('sur un lien mort, explique et propose de demander un accès', async () => {
    formationApi.session.mockRejectedValue({ response: { status: 404 } })
    formationApi.demanderAcces.mockResolvedValue({ data: {} })
    afficher()

    expect(
      await screen.findByRole('heading', { name: 'Ce lien n’est plus valable' })
    ).toBeInTheDocument()
    // Jamais d'erreur technique : un salarié qui lit « 403 Forbidden » abandonne.
    expect(screen.queryByText(/404|403|Forbidden/)).not.toBeInTheDocument()

    await userEvent.click(screen.getByRole('button', { name: 'Demander un nouvel accès' }))
    await waitFor(() => expect(formationApi.demanderAcces).toHaveBeenCalledWith('jeton-de-test'))
    expect(screen.getByText(/transmise aux responsables/)).toBeInTheDocument()
  })
})
