import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import SurveillancePage from './SurveillancePage'

// Lot C, point 22 : aucun plafond ne borne les actifs DÉCLARÉS — la liste
// peut dépasser vingt, elle se cherche.

vi.mock('../api/endpoints', () => ({
  monitoringApi: {
    dashboard: vi.fn(),
    assetCheckHistory: vi.fn(),
    updateAsset: vi.fn(),
    deleteAsset: vi.fn(),
    createAsset: vi.fn(),
  },
}))
vi.mock('../components/ui/Toast', () => ({ useToast: () => ({ showToast: vi.fn() }) }))

const { monitoringApi } = await import('../api/endpoints')

function ligne(id, type, value) {
  return { asset: { id, type, value, is_active: true }, uptime_24h: null, latest_checks: {}, open_alerts: [] }
}

function servir() {
  monitoringApi.dashboard.mockResolvedValue({
    data: [
      ligne(1, 'email_domain', 'durand.example'),
      ligne(2, 'email_domain', 'lambert.example'),
      ligne(3, 'email_domain', 'compta-durand.example'),
    ],
  })
}

describe('SurveillancePage — chercher un actif', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('filtre les actifs par leur adresse', async () => {
    servir()
    render(<SurveillancePage />)

    await userEvent.type(await screen.findByRole('searchbox', { name: 'Rechercher un actif' }), 'durand')

    expect(screen.getByText('durand.example')).toBeInTheDocument()
    expect(screen.getByText('compta-durand.example')).toBeInTheDocument()
    expect(screen.queryByText('lambert.example')).not.toBeInTheDocument()
  })

  it('dit qu’aucun actif ne correspond, sans inviter à en déclarer un', async () => {
    servir()
    render(<SurveillancePage />)

    await userEvent.type(await screen.findByRole('searchbox', { name: 'Rechercher un actif' }), 'inexistant')

    expect(screen.getByText('Aucun actif ne correspond à cette recherche.')).toBeInTheDocument()
    expect(screen.queryByText('Aucun actif déclaré')).not.toBeInTheDocument()
  })
})
