import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import AssistantPage from './AssistantPage'

// Lot C, C4. Les suggestions viennent de la situation du client (17), une
// réponse mène vers l'écran concerné (18), la pseudonymisation est dite une
// fois, sans bandeau (19).

vi.mock('../api/endpoints', () => ({
  aiApi: {
    getSettings: vi.fn(),
    listConversations: vi.fn(),
    createConversation: vi.fn(),
    listMessages: vi.fn(),
    sendMessage: vi.fn(),
    getJob: vi.fn(),
    previewAssistant: vi.fn(),
    assistantSuggestions: vi.fn(),
  },
}))
vi.mock('../components/ui/Toast', () => ({ useToast: () => ({ showToast: vi.fn() }) }))
vi.mock('../context/EntitlementsContext', () => ({
  useEntitlements: () => ({
    hasFeature: () => true,
    featureInfo: () => null,
    requiredPlanFor: () => '',
    isOperational: true,
    loading: false,
  }),
}))

const { aiApi } = await import('../api/endpoints')

const SUGGESTIONS = [
  {
    question: 'Que faire de mes 2 compromissions critiques ?',
    reason: 'Des accès sont en circulation.',
    link: { to: '/compromissions', label: 'Voir les compromissions' },
  },
  {
    question: "Par quoi commencer dans mon plan d'action ?",
    reason: '12 actions restent à mener.',
    link: { to: '/plan-action', label: 'Ouvrir le plan d’action' },
  },
]

function servir({ messages = [], suggestions = SUGGESTIONS } = {}) {
  aiApi.getSettings.mockResolvedValue({ data: { ai_enabled: true } })
  aiApi.listConversations.mockResolvedValue({ data: { results: [{ id: 3 }] } })
  aiApi.listMessages.mockResolvedValue({ data: { results: messages } })
  aiApi.assistantSuggestions.mockResolvedValue({ data: { results: suggestions } })
}

function rendre() {
  return render(
    <MemoryRouter>
      <AssistantPage />
    </MemoryRouter>
  )
}

describe('AssistantPage', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('propose des questions tirées de la situation réelle du client', async () => {
    servir()
    rendre()

    expect(
      await screen.findByRole('button', { name: 'Que faire de mes 2 compromissions critiques ?' })
    ).toBeInTheDocument()
    expect(screen.getByRole('button', { name: "Par quoi commencer dans mon plan d'action ?" })).toBeInTheDocument()
    // Plus aucune suggestion figée sans rapport avec le client.
    expect(screen.queryByText('Suis-je en conformité RGPD ?')).not.toBeInTheDocument()
  })

  it('pose la question suggérée d’un clic', async () => {
    servir()
    aiApi.sendMessage.mockResolvedValue({
      data: { message: { id: 1, role: 'user', content: 'x' }, job: { id: 9 } },
    })
    aiApi.getJob.mockResolvedValue({ data: { status: 'pending' } })
    rendre()

    await userEvent.click(
      await screen.findByRole('button', { name: 'Que faire de mes 2 compromissions critiques ?' })
    )

    await waitFor(() =>
      expect(aiApi.sendMessage).toHaveBeenCalledWith(3, 'Que faire de mes 2 compromissions critiques ?')
    )
  })

  it('renvoie vers les écrans dont la réponse parle', async () => {
    servir({
      messages: [
        { id: 1, role: 'user', content: 'Que faire ?', links: [] },
        {
          id: 2,
          role: 'assistant',
          content: 'Changez le mot de passe, puis voyez votre plan.',
          links: [
            { to: '/compromissions', label: 'Voir les compromissions' },
            { to: '/plan-action', label: 'Ouvrir le plan d’action' },
          ],
        },
      ],
    })
    rendre()

    expect(await screen.findByRole('link', { name: 'Voir les compromissions' })).toHaveAttribute(
      'href',
      '/compromissions'
    )
    expect(screen.getByRole('link', { name: 'Ouvrir le plan d’action' })).toHaveAttribute('href', '/plan-action')
  })

  it('dit une fois, au début, que les données sont pseudonymisées', async () => {
    servir()
    rendre()

    expect(await screen.findByText(/Vos données sont pseudonymisées avant tout traitement externe/)).toBeInTheDocument()
    expect(screen.getAllByText(/pseudonymisées/)).toHaveLength(1)
  })

  it('ne répète pas ce rappel une fois la conversation engagée', async () => {
    servir({ messages: [{ id: 1, role: 'user', content: 'Bonjour', links: [] }] })
    rendre()

    await screen.findByText('Bonjour')
    expect(screen.queryByText(/pseudonymisées/)).not.toBeInTheDocument()
  })

  it('reste utilisable si les suggestions ne peuvent pas être calculées', async () => {
    servir()
    aiApi.assistantSuggestions.mockRejectedValue(new Error('réseau'))
    rendre()

    expect(await screen.findByText('Posez votre première question à l’assistant.')).toBeInTheDocument()
    expect(screen.getByRole('textbox', { name: 'Votre question pour l’assistant' })).toBeInTheDocument()
    // Le vrai critère : la conversation a bien été chargée. Une neutralisation
    // a montré que la zone de saisie s'affiche AUSSI quand tout le chargement
    // a échoué — le test passait alors pour une mauvaise raison.
    await waitFor(() => expect(aiApi.listMessages).toHaveBeenCalledWith(3))
  })
})
