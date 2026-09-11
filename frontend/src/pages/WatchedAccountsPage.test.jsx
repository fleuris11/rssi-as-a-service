import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import WatchedAccountsPage from './WatchedAccountsPage'

// V2-6, point 4 : faire surveiller l'adresse d'un tiers engage le client. La
// déclaration doit être DANS le geste d'ajout — pas dans un écran d'après, pas
// dans des conditions générales acceptées il y a six mois.
//
// Ces tests interdisent la version facile : un formulaire où l'on coche par
// réflexe, ou où le bouton part sans qu'on ait rien lu.

const DECLARATION =
  'Je déclare avoir le droit de faire surveiller ce compte. Si ce compte n’est pas le mien, ' +
  'je reconnais que cette surveillance constitue un traitement de données personnelles.'

vi.mock('../api/endpoints', () => ({
  threatIntelligenceApi: {
    listWatchedAccounts: vi.fn(),
    listWatchedAccountFindings: vi.fn(),
    // Lot A : l'ecran interroge desormais une API GROUPEE et paginee, et
    // propose un export filtre comme l'ecran.
    watchedAccountFindingsExportUrl: vi.fn(() => '/export.csv'),
    declareWatchedAccount: vi.fn(),
    removeWatchedAccount: vi.fn(),
    scanWatchedAccounts: vi.fn(),
    updateWatchedAccountFinding: vi.fn(),
  },
}))

vi.mock('../components/ui/Toast', () => ({
  useToast: () => ({ showToast: vi.fn() }),
}))

vi.mock('../context/EntitlementsContext', () => ({
  useEntitlements: () => ({
    hasFeature: () => true,
    featureInfo: () => null,
    features: [],
  }),
}))

const { threatIntelligenceApi } = await import('../api/endpoints')

const COMPTE = {
  id: 1,
  value: 'directrice@exemple.fr',
  label: 'Directrice générale',
  category_label: 'Dirigeant ou mandataire social',
  legal_basis_label: 'Compte professionnel fourni par mon entreprise',
  purpose: 'Cible probable d’une fraude au président.',
  declared_at: '2026-09-01T10:00:00Z',
  declared_by_email: 'dg@exemple.fr',
  last_scanned_at: null,
  open_findings: 0,
  is_active: true,
}

function afficher() {
  return render(
    <MemoryRouter>
      <WatchedAccountsPage />
    </MemoryRouter>
  )
}

describe('WatchedAccountsPage', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    threatIntelligenceApi.listWatchedAccounts.mockResolvedValue({
      data: {
        declaration_text: DECLARATION,
        declaration_version: '2026-09-1',
        summary: { accounts: 1, open_findings: 0, critical_findings: 0, last_scanned_at: null },
        results: [COMPTE],
      },
    })
    threatIntelligenceApi.listWatchedAccountFindings.mockResolvedValue({
      data: { count: 0, results: [], filters: { types: [], severities: [] } },
    })
  })

  it('affiche la déclaration à signer, et non un renvoi aux conditions générales', async () => {
    afficher()
    await userEvent.click(await screen.findByRole('button', { name: 'Ajouter un compte' }))

    // Le texte intégral, sous les yeux, au moment où on l'accepte.
    expect(screen.getByText(new RegExp(DECLARATION.slice(0, 40)))).toBeInTheDocument()
  })

  it('n’autorise pas l’ajout tant que la déclaration n’est pas cochée', async () => {
    afficher()
    await userEvent.click(await screen.findByRole('button', { name: 'Ajouter un compte' }))
    await userEvent.type(screen.getByLabelText('Compte à surveiller'), 'president@exemple.fr')
    await userEvent.type(
      screen.getByLabelText(/Pourquoi surveillez-vous ce compte/),
      'Fraude au président.'
    )

    // Tout est rempli SAUF la déclaration : le bouton reste inactif.
    expect(screen.getByRole('button', { name: 'Déclarer et surveiller' })).toBeDisabled()
    expect(threatIntelligenceApi.declareWatchedAccount).not.toHaveBeenCalled()
  })

  it('n’autorise pas l’ajout sans finalité, même déclaration cochée', async () => {
    afficher()
    await userEvent.click(await screen.findByRole('button', { name: 'Ajouter un compte' }))
    await userEvent.type(screen.getByLabelText('Compte à surveiller'), 'president@exemple.fr')
    await userEvent.click(screen.getByRole('checkbox'))

    // Une finalité vide rendrait la déclaration ininterprétable le jour où
    // quelqu'un la relit — y compris la personne concernée.
    expect(screen.getByRole('button', { name: 'Déclarer et surveiller' })).toBeDisabled()
  })

  it('transmet la déclaration complète au serveur', async () => {
    threatIntelligenceApi.declareWatchedAccount.mockResolvedValue({ data: COMPTE })
    afficher()
    await userEvent.click(await screen.findByRole('button', { name: 'Ajouter un compte' }))
    await userEvent.type(screen.getByLabelText('Compte à surveiller'), 'president@exemple.fr')
    await userEvent.type(
      screen.getByLabelText(/Pourquoi surveillez-vous ce compte/),
      'Fraude au président.'
    )
    await userEvent.click(screen.getByRole('checkbox'))
    await userEvent.click(screen.getByRole('button', { name: 'Déclarer et surveiller' }))

    await waitFor(() =>
      expect(threatIntelligenceApi.declareWatchedAccount).toHaveBeenCalledWith(
        expect.objectContaining({
          value: 'president@exemple.fr',
          purpose: 'Fraude au président.',
          declaration_accepted: true,
        })
      )
    )
  })

  it('montre la finalité déclarée à côté de chaque compte', async () => {
    afficher()

    // C'est ce que le client montrera si la personne concernée lui demande
    // pourquoi son compte est surveillé.
    expect(await screen.findByText(/Cible probable d’une fraude au président/)).toBeInTheDocument()
    expect(
      screen.getByText(/Compte professionnel fourni par mon entreprise/)
    ).toBeInTheDocument()
  })

  it('dit que ces résultats ne se mélangent pas à l’exposition générale', async () => {
    afficher()

    expect(
      await screen.findByText(/ce ne sont pas vos actifs, ce sont des comptes que vous surveillez/)
    ).toBeInTheDocument()
  })
})
