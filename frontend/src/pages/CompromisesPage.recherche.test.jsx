import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import CompromisesPage from './CompromisesPage'

// Lot C, point 22. La liste est paginée par le serveur : ce qui compte est
// que les filtres PARTENT au serveur — filtrer la seule page affichée mentirait
// sur les autres — et qu'un filtre vide n'annonce pas « aucune fuite en cours ».

vi.mock('../api/endpoints', () => ({
  threatIntelligenceApi: {
    listFindings: vi.fn(),
    status: vi.fn(),
    listMonitoredAssets: vi.fn(),
    listRevealAudit: vi.fn(),
    getScanJob: vi.fn(),
    triggerScan: vi.fn(),
    updateFindingStatus: vi.fn(),
    registerMonitoredAsset: vi.fn(),
    unregisterMonitoredAsset: vi.fn(),
  },
  monitoringApi: { listAssets: vi.fn() },
}))
vi.mock('../context/AuthContext', () => ({
  useAuth: () => ({ user: { is_staff: false }, currentTenant: { role: 'admin' } }),
  useOptionalAuth: () => null,
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

const { threatIntelligenceApi, monitoringApi } = await import('../api/endpoints')

const FUITE = {
  id: 1,
  severity: 'critical',
  status: 'open',
  asset_value: 'compta.acme.example',
  source_endpoint: 'stealer',
  meaning: 'Explication.',
  recommended_action: 'Action.',
  has_secret: false,
  details: [],
}

function servir() {
  threatIntelligenceApi.listFindings.mockResolvedValue({ data: { count: 1, results: [FUITE] } })
  threatIntelligenceApi.status.mockResolvedValue({ data: { cooldown_active: false } })
  monitoringApi.listAssets.mockResolvedValue({
    data: {
      results: [
        { id: 4, value: 'compta.acme.example' },
        { id: 5, value: 'boutique.acme.example' },
      ],
    },
  })
  threatIntelligenceApi.listMonitoredAssets.mockResolvedValue({ data: { results: [] } })
}

describe('CompromisesPage — chercher et filtrer', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('envoie la recherche au serveur', async () => {
    servir()
    render(<CompromisesPage />)

    await userEvent.type(
      await screen.findByRole('searchbox', { name: 'Rechercher une compromission' }),
      'compta'
    )

    await waitFor(() =>
      expect(threatIntelligenceApi.listFindings).toHaveBeenLastCalledWith(
        'open',
        1,
        expect.objectContaining({ q: 'compta' })
      )
    )
  })

  it('envoie la gravité et l’actif au serveur', async () => {
    servir()
    render(<CompromisesPage />)

    await userEvent.selectOptions(
      await screen.findByRole('combobox', { name: 'Filtrer par gravité' }),
      'critical'
    )
    await userEvent.selectOptions(screen.getByRole('combobox', { name: 'Filtrer par actif' }), '5')

    await waitFor(() =>
      expect(threatIntelligenceApi.listFindings).toHaveBeenLastCalledWith(
        'open',
        1,
        expect.objectContaining({ severity: 'critical', asset: '5' })
      )
    )
  })

  it('ne présente pas un filtre vide comme une bonne nouvelle', async () => {
    servir()
    render(<CompromisesPage />)
    await screen.findByText('compta.acme.example', { selector: 'p' })
    threatIntelligenceApi.listFindings.mockResolvedValue({ data: { count: 0, results: [] } })

    await userEvent.selectOptions(screen.getByRole('combobox', { name: 'Filtrer par gravité' }), 'attention')

    expect(await screen.findByText('Aucune compromission ne correspond')).toBeInTheDocument()
    expect(screen.queryByText('Aucune fuite en cours')).not.toBeInTheDocument()
  })
})
