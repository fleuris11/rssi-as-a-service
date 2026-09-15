import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import RequestsPage from './RequestsPage'

// Lot C, point 22 : les demandes closes d'un client s'accumulent avec les années.

vi.mock('../api/endpoints', () => ({
  accessRequestsApi: { list: vi.fn(), create: vi.fn(), cancel: vi.fn() },
}))
vi.mock('../components/ui/Toast', () => ({ useToast: () => ({ showToast: vi.fn() }) }))
vi.mock('../context/EntitlementsContext', () => ({
  useEntitlements: () => ({ features: [] }),
}))

const { accessRequestsApi } = await import('../api/endpoints')

function demande(id, label, isOpen, status) {
  return {
    id,
    subject_type: 'feature',
    subject_key: `f${id}`,
    subject_label: label,
    subject_type_label: 'Fonctionnalité',
    reason: '',
    response: '',
    status,
    is_open: isOpen,
    created_at: '2026-09-10T08:00:00Z',
  }
}

describe('RequestsPage — retrouver une demande', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    accessRequestsApi.list.mockResolvedValue({
      data: [
        demande(1, 'Surveillance continue', true, 'pending'),
        demande(2, 'Sécurité des emails', false, 'refused'),
      ],
    })
  })

  it('cherche par sujet, sans tenir compte des accents', async () => {
    render(<RequestsPage />)

    await userEvent.type(await screen.findByRole('searchbox', { name: 'Rechercher une demande' }), 'securite')

    expect(screen.getByText('Sécurité des emails')).toBeInTheDocument()
    expect(screen.queryByText('Surveillance continue')).not.toBeInTheDocument()
  })

  it('n’affiche que les demandes en cours sur demande', async () => {
    render(<RequestsPage />)

    await userEvent.click(await screen.findByRole('checkbox', { name: 'En cours seulement' }))

    expect(screen.getByText('Surveillance continue')).toBeInTheDocument()
    expect(screen.queryByText('Sécurité des emails')).not.toBeInTheDocument()
  })

  it('ne présente pas une recherche vide comme l’absence de demande', async () => {
    render(<RequestsPage />)

    await userEvent.type(await screen.findByRole('searchbox', { name: 'Rechercher une demande' }), 'zzz')

    expect(screen.getByText('Aucune demande ne correspond.')).toBeInTheDocument()
    expect(screen.queryByText('Aucune demande')).not.toBeInTheDocument()
  })
})
