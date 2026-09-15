import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import ProspectsPanel from './ProspectsPanel'

// Lot C, point 22 : le filtre « Tous » dépasse vite vingt prospects.

vi.mock('../../../api/endpoints', () => ({
  platformApi: {
    listProspects: vi.fn(),
    followUpBoard: vi.fn(),
    exportUrl: () => '#',
  },
}))
vi.mock('../../../components/ui/Toast', () => ({ useToast: () => ({ showToast: vi.fn() }) }))

const { platformApi } = await import('../../../api/endpoints')

function prospect(id, company, fullName) {
  return {
    id,
    company,
    full_name: fullName,
    email: `${fullName.split(' ')[0].toLowerCase()}@exemple.test`,
    role: '',
    phone: '',
    status: 'new',
    status_label: 'Nouvelle',
    source_label: 'Site',
    notes: [],
    already_client: false,
  }
}

describe('ProspectsPanel — chercher un prospect', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    platformApi.listProspects.mockResolvedValue({
      data: {
        prospects: [
          prospect(1, 'Boulangerie Moreau', 'Hélène Moreau'),
          prospect(2, 'Cabinet Petit', 'Louis Petit'),
        ],
      },
    })
    platformApi.followUpBoard.mockResolvedValue({ data: { due_today: [], stale: [], stale_after_days: 30 } })
  })

  it('filtre par entreprise ou par contact, sans tenir compte des accents', async () => {
    render(<ProspectsPanel />)

    await userEvent.type(await screen.findByRole('searchbox', { name: 'Rechercher un prospect' }), 'helene')

    expect(screen.getByText('Boulangerie Moreau')).toBeInTheDocument()
    expect(screen.queryByText('Cabinet Petit')).not.toBeInTheDocument()
  })

  it('ne présente pas une recherche vide comme un filtre vide', async () => {
    render(<ProspectsPanel />)

    await userEvent.type(await screen.findByRole('searchbox', { name: 'Rechercher un prospect' }), 'zzz')

    expect(screen.getByText('Aucun prospect ne correspond à cette recherche.')).toBeInTheDocument()
    expect(screen.queryByText('Aucun prospect pour ce filtre.')).not.toBeInTheDocument()
  })
})
