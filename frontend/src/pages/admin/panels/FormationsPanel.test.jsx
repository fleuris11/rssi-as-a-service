import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, expect, it, vi } from 'vitest'
import FormationsPanel from './FormationsPanel'

// Cet écran est le seul chemin d'attribution d'un cours : avant lui, une
// commande Django. Quatre choses doivent tenir :
//
//   1. rien n'est chargé avant qu'un client soit choisi — une console qui
//      interroge l'API au montage pour n'afficher aucun client travaille pour
//      rien ;
//   2. proposer envoie le bon slug et remplace l'état par la réponse du
//      serveur, jamais par une supposition locale ;
//   3. le retrait dit ce qu'il advient des parcours en cours. C'est la
//      question de celui qui clique ;
//   4. un appel qui échoue laisse un état durable, pas un squelette éternel.

vi.mock('../../../api/endpoints', () => ({
  platformApi: {
    clientCourses: vi.fn(),
    assignCourse: vi.fn(),
    revokeCourse: vi.fn(),
  },
}))

const showToast = vi.fn()
vi.mock('../../../components/ui/Toast', () => ({
  useToast: () => ({ showToast }),
}))

const { platformApi } = await import('../../../api/endpoints')

const CLIENTS = [{ tenant_id: 'abc', name: 'Société Exemple' }]

// Les chiffres sont enveloppes dans un <span class="num"> — la ligne est donc
// decoupee en plusieurs elements, et un matcher de texte simple ne la voit
// pas. On interroge le textContent du paragraphe.
const ligne = (motif) => (_texte, element) =>
  element?.tagName === 'P' && motif.test(element.textContent)

const VIDE = {
  assigned: [],
  available: [
    {
      id: 1,
      slug: 'mots-de-passe',
      title: 'Mots de passe : un par service, et une deuxième clé',
      summary: 'Court.',
      minutes: 8,
      pass_threshold: 80,
      screens: 6,
      questions: 6,
    },
  ],
}

const PROPOSE = {
  assigned: [
    {
      id: 1,
      slug: 'mots-de-passe',
      title: 'Mots de passe : un par service, et une deuxième clé',
      summary: 'Court.',
      minutes: 8,
      pass_threshold: 80,
      ongoing: 3,
    },
  ],
  available: [],
}

beforeEach(() => {
  vi.clearAllMocks()
  platformApi.clientCourses.mockResolvedValue({ data: VIDE })
})

async function choisirLeClient() {
  render(<FormationsPanel clients={CLIENTS} />)
  await userEvent.selectOptions(screen.getByLabelText('Client'), 'abc')
  await waitFor(() => expect(platformApi.clientCourses).toHaveBeenCalledWith('abc'))
}

it('n’interroge pas l’API avant qu’un client soit choisi', () => {
  render(<FormationsPanel clients={CLIENTS} />)
  expect(platformApi.clientCourses).not.toHaveBeenCalled()
})

it('affiche la bibliothèque avec sa durée et son nombre de questions', async () => {
  await choisirLeClient()

  expect(screen.getByText('Bibliothèque')).toBeInTheDocument()
  expect(
    screen.getByText('Mots de passe : un par service, et une deuxième clé'),
  ).toBeInTheDocument()
  expect(screen.getByText(ligne(/8 min.*6 écrans.*6 questions/))).toBeInTheDocument()
})

it('propose un cours avec son slug, et reprend l’état du serveur', async () => {
  platformApi.assignCourse.mockResolvedValue({ data: PROPOSE })
  await choisirLeClient()

  await userEvent.click(screen.getByRole('button', { name: 'Proposer' }))

  expect(platformApi.assignCourse).toHaveBeenCalledWith('abc', 'mots-de-passe')
  await waitFor(() => expect(screen.getByText('Proposés')).toBeInTheDocument())
  // Le compteur de salariés en cours vient du serveur : il n'est pas déduit.
  expect(screen.getByText(ligne(/8 min.*seuil 80 %.*3 salariés en cours/))).toBeInTheDocument()
  expect(screen.getByText('Toute la bibliothèque lui est déjà proposée.')).toBeInTheDocument()
})

it('dit ce qu’il advient des parcours en cours quand on retire un cours', async () => {
  platformApi.clientCourses.mockResolvedValue({ data: PROPOSE })
  platformApi.revokeCourse.mockResolvedValue({ data: VIDE, kept_enrollments: true })
  await choisirLeClient()

  await userEvent.click(screen.getByRole('button', { name: 'Retirer' }))

  expect(platformApi.revokeCourse).toHaveBeenCalledWith('abc', 'mots-de-passe')
  await waitFor(() =>
    expect(showToast).toHaveBeenCalledWith({
      type: 'success',
      message: 'Cours retiré. Les salariés déjà inscrits terminent leur parcours.',
    }),
  )
})

it('un chargement en échec laisse un état durable, pas un squelette', async () => {
  platformApi.clientCourses.mockRejectedValue(new Error('réseau'))
  render(<FormationsPanel clients={CLIENTS} />)

  await userEvent.selectOptions(screen.getByLabelText('Client'), 'abc')

  await waitFor(() => expect(screen.getByRole('alert')).toBeInTheDocument())
  expect(screen.getByRole('button', { name: /réessayer/i })).toBeInTheDocument()
})

it('remonte le refus du serveur tel quel', async () => {
  platformApi.assignCourse.mockRejectedValue({
    response: { data: { detail: 'Ce cours n’a pas de version publiée.' } },
  })
  await choisirLeClient()

  await userEvent.click(screen.getByRole('button', { name: 'Proposer' }))

  await waitFor(() =>
    expect(showToast).toHaveBeenCalledWith({
      type: 'error',
      message: 'Ce cours n’a pas de version publiée.',
    }),
  )
})
