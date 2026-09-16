import { render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import ClientsPanel from './ClientsPanel'

// V2-8 (ADR-038) : composer le périmètre d'un client depuis la console.
//
// Ce que l'écran doit tenir, et que ces tests épinglent :
//   - l'état HÉRITÉ de l'offre reste lisible à côté de l'état effectif ;
//   - ce qui dévie de l'offre se voit d'un coup d'œil ;
//   - l'aperçu montre le menu du client, écrans dérivés compris ;
//   - un refus du serveur s'affiche tel quel, avec son motif.

vi.mock('../../../api/endpoints', () => ({
  platformApi: {
    clientDetail: vi.fn(),
    listMembers: vi.fn(),
    clientFeatures: vi.fn(),
    setClientFeatures: vi.fn(),
    resetClientFeatures: vi.fn(),
    exportUrl: () => '#',
    exportCsv: vi.fn(),
  },
}))
vi.mock('../../../components/ui/Toast', () => ({ useToast: () => ({ showToast: vi.fn() }) }))

const { platformApi } = await import('../../../api/endpoints')

const FICHE = {
  id: 'c-1',
  name: 'Menuiserie Lambert',
  slug: 'menuiserie-lambert',
  is_active: true,
  usage: { users: 2, assets: 1, monitored_assets: 0, findings_total: 0 },
  subscription: {
    id: 1,
    plan_code: 'veille',
    plan_name: 'Veille',
    status: 'active',
    status_label: 'Actif',
    quotas: { monitored_assets: 1, monthly_scans: 20, max_users: 3 },
    internal_notes: '',
  },
  members: [],
  fiche: { name: 'Menuiserie Lambert', is_archived: false },
}

function fonctionnalite(key, label, { inherited, enabled, deviation = '', derived = [] } = {}) {
  return {
    key,
    label,
    teaser: '',
    inherited,
    enabled,
    deviation,
    derived_screens: derived,
    quota_required: '',
  }
}

const COMPOSITION = {
  plan_code: 'veille',
  plan_name: 'Veille',
  has_override: false,
  features: [
    fonctionnalite('anssi_assessment', 'Diagnostic de maturité', {
      inherited: true,
      enabled: true,
      derived: ['Résultats', "Plan d'action"],
    }),
    fonctionnalite('assistant', 'Assistant conversationnel', { inherited: true, enabled: true }),
    fonctionnalite('watched_accounts', 'Surveillance de comptes désignés', {
      inherited: false,
      enabled: false,
    }),
  ],
}

function servir(composition = COMPOSITION) {
  platformApi.clientDetail.mockResolvedValue({ data: FICHE })
  platformApi.listMembers.mockResolvedValue({ data: [] })
  platformApi.clientFeatures.mockResolvedValue({ data: composition })
}

function afficher() {
  return render(
    <ClientsPanel
      tenants={[{ id: 'c-1', name: 'Menuiserie Lambert', user_count: 2 }]}
      plans={[{ code: 'veille', name: 'Veille', monitored_assets: 1 }]}
      onRefresh={vi.fn()}
      initialTenantId="c-1"
      onFocusConsumed={vi.fn()}
    />
  )
}

describe('Composition du périmètre d’un client', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('montre l’état hérité de l’offre à côté de l’état effectif', async () => {
    servir()
    afficher()

    const diagnostic = await screen.findByRole('checkbox', { name: 'Diagnostic de maturité' })
    expect(diagnostic).toBeChecked()
    expect(screen.getByRole('checkbox', { name: 'Surveillance de comptes désignés' })).not.toBeChecked()
    // L'héritage, dit en toutes lettres : sans lui, personne ne sait plus ce
    // que l'offre donne.
    expect(screen.getAllByText(/Comprise dans l’offre/).length).toBeGreaterThan(0)
    expect(screen.getByText(/Absente de l’offre/)).toBeInTheDocument()
    expect(screen.getByText('Suit l’offre')).toBeInTheDocument()
  })

  it('signale ce qui dévie de l’offre', async () => {
    servir({
      ...COMPOSITION,
      has_override: true,
      features: [
        fonctionnalite('anssi_assessment', 'Diagnostic de maturité', {
          inherited: true,
          enabled: false,
          deviation: 'retiree',
          derived: ['Résultats', "Plan d'action"],
        }),
        fonctionnalite('watched_accounts', 'Surveillance de comptes désignés', {
          inherited: false,
          enabled: true,
          deviation: 'ajoutee',
        }),
      ],
    })
    afficher()

    expect(await screen.findByText('Périmètre composé')).toBeInTheDocument()
    expect(screen.getByText(/Diagnostic de maturité \(retirée\)/)).toBeInTheDocument()
    expect(screen.getByText(/Surveillance de comptes désignés \(ajoutée\)/)).toBeInTheDocument()
  })

  it('montre le menu du client, écrans dérivés compris', async () => {
    servir()
    afficher()

    const apercu = (await screen.findByRole('heading', { name: /Son menu, avec cette composition/ }))
      .parentElement
    expect(within(apercu).getByText('Diagnostic')).toBeInTheDocument()
    expect(within(apercu).getByText('Plan d’action')).toBeInTheDocument()

    await userEvent.click(screen.getByRole('checkbox', { name: 'Diagnostic de maturité' }))

    expect(within(apercu).queryByText('Diagnostic')).not.toBeInTheDocument()
    expect(within(apercu).queryByText('Plan d’action')).not.toBeInTheDocument()
    expect(within(apercu).getByText('Tableau de bord')).toBeInTheDocument()
    expect(
      within(apercu).getByText(/Retiré de son menu.*Résultats.*Plan d'action/s)
    ).toBeInTheDocument()
  })

  it('envoie la composition au serveur', async () => {
    servir()
    platformApi.setClientFeatures.mockResolvedValue({
      data: { ...COMPOSITION, has_override: true },
    })
    afficher()

    await userEvent.click(await screen.findByRole('checkbox', { name: 'Assistant conversationnel' }))
    await userEvent.click(screen.getByRole('button', { name: 'Enregistrer la composition' }))

    await waitFor(() =>
      expect(platformApi.setClientFeatures).toHaveBeenCalledWith('c-1', ['anssi_assessment'])
    )
  })

  it('affiche le motif d’un refus, sans le résumer', async () => {
    servir()
    platformApi.setClientFeatures.mockRejectedValue({
      response: {
        status: 422,
        data: {
          detail: 'refus',
          problemes: [
            '« Surveillance de comptes désignés » est activée, mais ce client n’a aucun compte à surveiller : chaque action lui serait refusée.',
          ],
        },
      },
    })
    afficher()

    await userEvent.click(
      await screen.findByRole('checkbox', { name: 'Surveillance de comptes désignés' })
    )
    await userEvent.click(screen.getByRole('button', { name: 'Enregistrer la composition' }))

    const alerte = await screen.findByRole('alert')
    expect(within(alerte).getByText(/chaque action lui serait refusée/)).toBeInTheDocument()
  })

  it('ne propose le retour à l’offre que s’il y a une composition', async () => {
    servir()
    afficher()

    expect(await screen.findByRole('button', { name: 'Revenir à l’offre' })).toBeDisabled()
  })

  it('revient à l’offre sur demande', async () => {
    servir({ ...COMPOSITION, has_override: true })
    platformApi.resetClientFeatures.mockResolvedValue({ data: COMPOSITION })
    afficher()

    await userEvent.click(await screen.findByRole('button', { name: 'Revenir à l’offre' }))

    await waitFor(() => expect(platformApi.resetClientFeatures).toHaveBeenCalledWith('c-1'))
  })
})
