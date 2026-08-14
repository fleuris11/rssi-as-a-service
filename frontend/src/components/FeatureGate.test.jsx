import { render, screen, waitFor } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { EntitlementsProvider } from '../context/EntitlementsContext'
import FeatureGate, { FeatureLockedNotice } from './FeatureGate'

// Règle produit à ne pas laisser régresser : une fonctionnalité hors offre est
// DÉSACTIVÉE, jamais masquée, et indique l'offre qui la débloque. Masquer
// laisserait croire que le produit ne sait pas le faire — c'est faux, et le
// client n'aurait aucune raison de monter d'offre.

vi.mock('../api/endpoints', () => ({
  billingApi: { entitlements: vi.fn() },
}))

vi.mock('../context/AuthContext', () => ({
  useAuth: () => ({ currentTenantId: 7 }),
}))

const { billingApi } = await import('../api/endpoints')

const FEATURES = [
  { key: 'secret_reveal', label: 'Consultation du mot de passe', included: true },
  {
    key: 'exposure_synthesis',
    label: 'Synthèse d’exposition',
    teaser: 'Une lecture consolidée de vos expositions.',
    included: false,
    required_plan: 'Pilotage',
  },
]

function renderGate(ui) {
  return render(<EntitlementsProvider>{ui}</EntitlementsProvider>)
}

describe('FeatureGate', () => {
  beforeEach(() => {
    billingApi.entitlements.mockReset()
    billingApi.entitlements.mockResolvedValue({
      data: {
        subscription: { plan_name: 'Veille', status: 'active', is_operational: true },
        quotas: {},
        features: FEATURES,
      },
    })
  })

  it('rend la fonctionnalité normalement quand elle est comprise dans l’offre', async () => {
    renderGate(
      <FeatureGate feature="secret_reveal">
        <button type="button">Révéler</button>
      </FeatureGate>
    )

    const button = await screen.findByRole('button', { name: 'Révéler' })
    expect(button.closest('[aria-disabled="true"]')).toBeNull()
  })

  it('affiche la fonctionnalité hors offre DÉSACTIVÉE et non masquée', async () => {
    renderGate(
      <FeatureGate feature="exposure_synthesis">
        <button type="button">Rafraîchir la synthèse</button>
      </FeatureGate>
    )

    // Toujours présente dans le document…
    await screen.findByText('Rafraîchir la synthèse')
    // …mais dans un conteneur explicitement désactivé pour les technologies
    // d'assistance, pas simplement grisé visuellement. On ré-interroge le DOM
    // à chaque tentative : le nœud est remplacé quand les droits arrivent et
    // que l'enfant passe sous le conteneur du verrou.
    await waitFor(() =>
      expect(
        screen.getByText('Rafraîchir la synthèse').closest('[aria-disabled="true"]')
      ).not.toBeNull()
    )
  })

  it('nomme l’offre qui débloque la fonctionnalité', async () => {
    renderGate(
      <FeatureGate feature="exposure_synthesis">
        <button type="button">Rafraîchir la synthèse</button>
      </FeatureGate>
    )

    expect(
      await screen.findByText(/Compris à partir de l’offre Pilotage\./)
    ).toBeInTheDocument()
  })

  it('n’annonce jamais une fonctionnalité hors offre comme un échec du produit', async () => {
    renderGate(
      <FeatureGate feature="exposure_synthesis">
        <button type="button">Rafraîchir la synthèse</button>
      </FeatureGate>
    )
    await screen.findByText('Rafraîchir la synthèse')

    expect(screen.queryByText(/indisponible|erreur|impossible/i)).toBeNull()
  })

  it('reste optimiste si le chargement des droits échoue', async () => {
    // Un incident réseau passager ne doit pas griser toute l'interface : le
    // serveur reste l'autorité et refusera l'appel avec un message explicite.
    billingApi.entitlements.mockRejectedValue(new Error('réseau'))

    renderGate(
      <FeatureGate feature="exposure_synthesis">
        <button type="button">Rafraîchir la synthèse</button>
      </FeatureGate>
    )

    const button = await screen.findByRole('button', { name: 'Rafraîchir la synthèse' })
    await waitFor(() => expect(button.closest('[aria-disabled="true"]')).toBeNull())
  })

  it('affiche un badge portant le nom de l’offre en mode badge', async () => {
    renderGate(<FeatureGate feature="exposure_synthesis" mode="badge">{null}</FeatureGate>)

    expect(await screen.findByText('Pilotage')).toBeInTheDocument()
  })
})

describe('FeatureLockedNotice', () => {
  beforeEach(() => {
    billingApi.entitlements.mockReset()
    billingApi.entitlements.mockResolvedValue({
      data: { subscription: null, quotas: {}, features: FEATURES },
    })
  })

  it('explique la fonctionnalité manquante et l’offre requise', async () => {
    renderGate(<FeatureLockedNotice feature="exposure_synthesis" />)

    expect(await screen.findByText('Synthèse d’exposition')).toBeInTheDocument()
    expect(
      screen.getByText('Une lecture consolidée de vos expositions.')
    ).toBeInTheDocument()
    expect(
      screen.getByText(/Compris à partir de l’offre Pilotage\./)
    ).toBeInTheDocument()
  })

  it('ne s’affiche pas quand la fonctionnalité est comprise', async () => {
    const { container } = renderGate(<FeatureLockedNotice feature="secret_reveal" />)

    await waitFor(() => expect(billingApi.entitlements).toHaveBeenCalled())
    expect(container).toBeEmptyDOMElement()
  })
})
