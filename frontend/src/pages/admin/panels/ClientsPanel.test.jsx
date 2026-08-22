import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { ClientCreateModal } from './ClientsPanel'

// Le formulaire par lequel passe toute création de client. Deux règles y sont
// verrouillées : aucun mot de passe n'est jamais saisi ni affiché, et le motif
// exact d'un refus serveur est montré tel quel — un refus de capacité dit ce
// qu'il reste et ce qu'il faut libérer, le résumer perdrait l'essentiel.

vi.mock('../../../api/endpoints', () => ({
  platformApi: { createClient: vi.fn() },
}))

const showToast = vi.fn()
vi.mock('../../../components/ui/Toast', () => ({ useToast: () => ({ showToast }) }))

const { platformApi } = await import('../../../api/endpoints')

const PLANS = [
  { code: 'veille', name: 'Veille', monitored_assets: 1 },
  { code: 'pilotage', name: 'Pilotage', monitored_assets: 3 },
]

function renderModal(props = {}) {
  return render(
    <ClientCreateModal open onClose={vi.fn()} plans={PLANS} onCreated={vi.fn()} {...props} />
  )
}

describe('ClientCreateModal', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('ne propose aucun champ de mot de passe', () => {
    renderModal()

    expect(screen.queryByLabelText(/mot de passe/i)).toBeNull()
    expect(
      screen.getByText(/Il recevra un lien pour définir son mot de passe/)
    ).toBeInTheDocument()
  })

  it('exige le nom et l’email avant d’appeler le serveur', async () => {
    const user = userEvent.setup()
    renderModal()

    await user.click(screen.getByRole('button', { name: 'Créer le client' }))

    expect(platformApi.createClient).not.toHaveBeenCalled()
    expect(screen.getByText('Le nom de l’entreprise est obligatoire.')).toBeInTheDocument()
  })

  it('crée le client et affiche le lien d’invitation, jamais un mot de passe', async () => {
    const user = userEvent.setup()
    platformApi.createClient.mockResolvedValue({
      data: {
        name: 'Atelier Roux',
        invitation: {
          invitation_url: 'http://localhost:5173/invitation/abc123',
          invitation_email: 'gerant@atelier.example',
          email_sent: false,
          expires_in_hours: 72,
        },
      },
    })
    renderModal()

    await user.type(screen.getByLabelText(/Nom de l’entreprise/), 'Atelier Roux')
    await user.type(screen.getByLabelText(/Email du premier utilisateur/), 'gerant@atelier.example')
    await user.click(screen.getByRole('button', { name: 'Créer le client' }))

    expect(await screen.findByText(/invitation\/abc123/)).toBeInTheDocument()
    expect(screen.getByText(/ne fonctionne qu’une fois/)).toBeInTheDocument()
  })

  it('affiche tel quel le motif d’un refus de capacité', async () => {
    const user = userEvent.setup()
    const detail =
      'Cette opération engagerait 17 emplacements de surveillance continue pour un plafond ' +
      'plateforme de 15. Il en reste 1 disponible(s).'
    platformApi.createClient.mockRejectedValue({
      response: { status: 409, data: { detail } },
    })
    renderModal()

    await user.type(screen.getByLabelText(/Nom de l’entreprise/), 'De Trop')
    await user.type(screen.getByLabelText(/Email du premier utilisateur/), 'a@detrop.example')
    await user.click(screen.getByRole('button', { name: 'Créer le client' }))

    await waitFor(() =>
      expect(showToast).toHaveBeenCalledWith({ type: 'error', message: detail })
    )
  })

  it('pré-remplit le formulaire lors d’une conversion de prospect', () => {
    renderModal({
      prefill: {
        name: 'Devient Client',
        owner_email: 'contact@devient.example',
        prospect_id: 12,
      },
    })

    expect(screen.getByLabelText(/Nom de l’entreprise/)).toHaveValue('Devient Client')
    expect(screen.getByLabelText(/Email du premier utilisateur/)).toHaveValue(
      'contact@devient.example'
    )
  })

  it('transmet l’identifiant du prospect pour conserver le lien', async () => {
    const user = userEvent.setup()
    platformApi.createClient.mockResolvedValue({
      data: { name: 'Devient Client', invitation: { invitation_url: 'x', expires_in_hours: 72 } },
    })
    renderModal({
      prefill: { name: 'Devient Client', owner_email: 'c@devient.example', prospect_id: 12 },
    })

    await user.click(screen.getByRole('button', { name: 'Créer le client' }))

    await waitFor(() =>
      expect(platformApi.createClient).toHaveBeenCalledWith(
        expect.objectContaining({ prospect_id: 12 })
      )
    )
  })
})
