import { render, screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { describe, expect, it, vi } from 'vitest'
import FeatureGate, { FeatureLockedNotice } from './FeatureGate'

// V2-8 (ADR-038) : la garde distingue la CAUSE de l'absence.
//
//   - hors offre        -> désactivé, avec l'offre qui la débloque (levier commercial) ;
//   - retirée au client -> rien du tout.
//
// La garde serveur, elle, refuse dans les deux cas : ce qui suit est de
// l'affichage, jamais une sécurité.

let droits = {}
vi.mock('../context/EntitlementsContext', () => ({
  useEntitlements: () => droits,
}))

function rendre(feature) {
  return render(
    <MemoryRouter>
      <FeatureGate feature={feature}>
        <button type="button">Analyser</button>
      </FeatureGate>
      <FeatureLockedNotice feature={feature} />
    </MemoryRouter>
  )
}

function poser(info) {
  droits = {
    hasFeature: (key) => Boolean(info[key]?.included),
    featureInfo: (key) => info[key] || null,
  }
}

describe('FeatureGate', () => {
  it('laisse passer ce qui est compris dans l’offre', () => {
    poser({ watched_accounts: { key: 'watched_accounts', included: true, source: 'plan' } })
    rendre('watched_accounts')

    expect(screen.getByRole('button', { name: 'Analyser' })).toBeInTheDocument()
  })

  it('désactive — sans masquer — ce qui est seulement hors offre', () => {
    poser({
      watched_accounts: {
        key: 'watched_accounts',
        included: false,
        source: 'plan',
        label: 'Surveillance de comptes désignés',
        teaser: 'Faites surveiller des comptes précis.',
        required_plan: 'Pilotage',
      },
    })
    rendre('watched_accounts')

    expect(screen.getByRole('button', { name: 'Analyser' })).toBeInTheDocument()
    // La phrase paraît deux fois : sur l'élément désactivé (nom accessible) et
    // dans l'encart de section. Les deux sont voulues.
    expect(screen.getAllByText(/Compris à partir de l’offre Pilotage/).length).toBeGreaterThan(0)
    expect(screen.getByRole('link', { name: 'Demander cette fonctionnalité' })).toBeInTheDocument()
  })

  it('masque ce qui a été retiré à ce client, et n’invite pas à le demander', () => {
    poser({
      watched_accounts: {
        key: 'watched_accounts',
        included: false,
        source: 'override',
        label: 'Surveillance de comptes désignés',
        required_plan: 'Pilotage',
      },
    })
    rendre('watched_accounts')

    expect(screen.queryByRole('button', { name: 'Analyser' })).not.toBeInTheDocument()
    expect(screen.queryByText(/Compris à partir de l’offre/)).not.toBeInTheDocument()
    expect(
      screen.queryByRole('link', { name: 'Demander cette fonctionnalité' })
    ).not.toBeInTheDocument()
  })
})
