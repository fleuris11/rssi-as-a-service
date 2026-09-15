import { render, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import RequestsPanel from './RequestsPanel'

// Lot C, point 22 : la file de tous les clients dépasse vite vingt demandes.

vi.mock('../../../api/endpoints', () => ({
  platformApi: { listAccessRequests: vi.fn(), advanceAccessRequest: vi.fn() },
}))
vi.mock('../../../components/ui/Toast', () => ({ useToast: () => ({ showToast: vi.fn() }) }))

const { platformApi } = await import('../../../api/endpoints')

function demande(id, client, sujet, type, typeLibelle) {
  return {
    id,
    tenant_name: client,
    subject_label: sujet,
    subject_type: type,
    subject_type_label: typeLibelle,
    requested_by_email: `contact@${client.toLowerCase().replace(/\s/g, '')}.example`,
    reason: '',
    status: 'pending',
    status_label: 'Nouvelle',
    is_open: true,
    created_at: '2026-09-10T08:00:00Z',
  }
}

function servir() {
  platformApi.listAccessRequests.mockResolvedValue({
    data: {
      open_count: 3,
      results: [
        demande(1, 'Cabinet Durand', 'ISO 27001', 'referential', 'Référentiel'),
        demande(2, 'Menuiserie Lambert', 'Surveillance continue', 'feature', 'Fonctionnalité'),
        demande(3, 'Garage Martin', 'Sécurité des emails', 'feature', 'Fonctionnalité'),
      ],
    },
  })
}

function lignes() {
  return within(screen.getAllByRole('list')[0]).getAllByRole('listitem')
}

describe('RequestsPanel — chercher dans la file', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('cherche par client, sans tenir compte des accents', async () => {
    servir()
    render(<RequestsPanel />)

    await userEvent.type(await screen.findByRole('searchbox', { name: 'Rechercher une demande' }), 'securite')

    expect(lignes()).toHaveLength(1)
    expect(screen.getByText(/Garage Martin — Sécurité des emails/)).toBeInTheDocument()
  })

  it('filtre par type de demande', async () => {
    servir()
    render(<RequestsPanel />)

    await userEvent.selectOptions(
      await screen.findByRole('combobox', { name: 'Filtrer par type de demande' }),
      'referential'
    )

    expect(lignes()).toHaveLength(1)
    expect(screen.getByText(/Cabinet Durand — ISO 27001/)).toBeInTheDocument()
  })

  it('ne présente pas une recherche vide comme une file vide', async () => {
    servir()
    render(<RequestsPanel />)

    await userEvent.type(await screen.findByRole('searchbox', { name: 'Rechercher une demande' }), 'inexistant')

    expect(screen.getByText('Aucune demande ne correspond')).toBeInTheDocument()
    expect(screen.queryByText('Aucune demande en cours')).not.toBeInTheDocument()
  })
})
