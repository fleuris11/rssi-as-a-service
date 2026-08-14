import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import PlatformAdminPage from './PlatformAdminPage'

// Cette page est l'écran de pilotage de la ressource rare : la licence CTI
// plafonne la PLATEFORME ENTIÈRE, pas chaque client. Les tests ci-dessous
// pinnent ce qui rend un dépassement impossible à commettre par inadvertance :
// voir l'état du pool, savoir à l'avance si une activation passerait, et lire
// le motif exact d'un refus serveur.

vi.mock('../../api/endpoints', () => ({
  platformApi: {
    capacity: vi.fn(),
    listTenants: vi.fn(),
    listPlans: vi.fn(),
    configuration: vi.fn(),
    audit: vi.fn(),
    listDemoRequests: vi.fn(),
    updateDemoRequest: vi.fn(),
    convertDemoRequest: vi.fn(),
    health: vi.fn(),
    subscriptionAction: vi.fn(),
    updatePlan: vi.fn(),
  },
}))

const showToast = vi.fn()
vi.mock('../../components/ui/Toast', () => ({
  useToast: () => ({ showToast }),
}))

const { platformApi } = await import('../../api/endpoints')

const CAPACITY = {
  resources: [
    {
      resource: 'monitored_assets',
      label: 'Emplacements de surveillance continue',
      used: 14,
      capacity: 15,
      remaining: 1,
      ratio: 14 / 15,
    },
    {
      resource: 'monthly_scans',
      label: 'Analyses ponctuelles ce mois-ci',
      used: 120,
      capacity: 1000,
      remaining: 880,
      ratio: 0.12,
    },
  ],
  projections: [
    {
      plan_code: 'veille',
      plan_name: 'Veille',
      monitored_assets: 1,
      would_use: 15,
      capacity: 15,
      remaining_after: 0,
      would_fit: true,
    },
    {
      plan_code: 'pilotage',
      plan_name: 'Pilotage',
      monitored_assets: 3,
      would_use: 17,
      capacity: 15,
      remaining_after: 0,
      would_fit: false,
    },
  ],
  by_tenant: [
    {
      tenant_id: 1,
      tenant_name: 'Menuiserie Lambert',
      plan_name: 'Veille',
      status: 'active',
      monitored_assets: 1,
      monthly_scans_used: 0,
    },
  ],
}

const TENANTS = [
  {
    id: 1,
    name: 'Menuiserie Lambert',
    subscription: {
      status: 'active',
      plan_name: 'Veille',
      monitored_assets: 1,
      trial_ends_at: null,
    },
  },
]

function mockOk() {
  platformApi.capacity.mockResolvedValue({ data: CAPACITY })
  platformApi.listTenants.mockResolvedValue({ data: TENANTS })
  platformApi.listPlans.mockResolvedValue({ data: [] })
  platformApi.configuration.mockResolvedValue({ data: { sections: [] } })
  platformApi.audit.mockResolvedValue({ data: { entries: [] } })
  platformApi.listDemoRequests.mockResolvedValue({ data: { requests: [], open_count: 0 } })
  platformApi.health.mockResolvedValue({ data: { checks: [], scheduled: [], volumes: {} } })
}

describe('PlatformAdminPage', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    mockOk()
  })

  it('affiche l’occupation du pool partagé et ce qu’il en reste', async () => {
    render(<PlatformAdminPage />)

    expect(
      await screen.findByText('Emplacements de surveillance continue')
    ).toBeInTheDocument()
    expect(screen.getByText('14')).toBeInTheDocument()
    expect(screen.getByText('1 disponible')).toBeInTheDocument()
  })

  it('rappelle que le plafond est celui de la plateforme, pas d’un client', async () => {
    render(<PlatformAdminPage />)

    expect(
      await screen.findByText(/s’appliquent à la plateforme entière, pas à/)
    ).toBeInTheDocument()
  })

  it('annonce à l’avance l’offre qui ne tiendrait PAS dans le pool restant', async () => {
    render(<PlatformAdminPage />)
    await screen.findByText('Projection par offre')

    // Veille (1 emplacement) tiendrait, Pilotage (3) non : c'est l'information
    // qui évite d'engager une vente irréalisable.
    expect(screen.getByText('Oui')).toBeInTheDocument()
    expect(screen.getByText('Non — plafond atteint')).toBeInTheDocument()
  })

  it('affiche tel quel le motif de refus du serveur sur un 409', async () => {
    const user = userEvent.setup()
    const detail =
      'Cette opération engagerait 17 emplacements de surveillance continue pour un ' +
      'plafond plateforme de 15. Il en reste 1 disponible(s).'
    platformApi.subscriptionAction.mockRejectedValue({
      response: { status: 409, data: { detail } },
    })
    render(<PlatformAdminPage />)

    await user.click(await screen.findByRole('tab', { name: /Clients/ }))
    await user.click(await screen.findByRole('button', { name: /Activer/ }))

    // Le message du serveur dit ce qui reste et ce qu'il faut libérer : le
    // résumer ferait perdre l'information utile à l'exploitant.
    expect(showToast).toHaveBeenCalledWith({ type: 'error', message: detail })
  })

  it('garde le titre et les onglets visibles pendant le chargement', async () => {
    // Une page entièrement remplacée par des squelettes ne dit même pas où
    // l'on se trouve — et la sonde de santé prend plusieurs secondes.
    render(<PlatformAdminPage />)

    expect(screen.getByText('Administration de la plateforme')).toBeInTheDocument()
    expect(screen.getByRole('tab', { name: /Ressources/ })).toBeInTheDocument()

    // On laisse le chargement se terminer avant de démonter, sinon React
    // signale une mise à jour hors act() qui n'apprend rien.
    await screen.findByText('Emplacements de surveillance continue')
  })

  it('reste utilisable quand la sonde de santé échoue', async () => {
    platformApi.health.mockRejectedValue(new Error('celery injoignable'))
    render(<PlatformAdminPage />)

    // Les ressources rares s'affichent quand même : la santé est un onglet
    // parmi d'autres, pas un préalable au reste de la page.
    expect(
      await screen.findByText('Emplacements de surveillance continue')
    ).toBeInTheDocument()
  })
})
