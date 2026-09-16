import { render, screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { describe, expect, it, vi } from 'vitest'
import Sidebar from './Sidebar'

// V2-8 (ADR-038) : le menu d'un client dont on a réduit le périmètre ne montre
// pas ce qu'on lui a retiré. Une fonctionnalité seulement hors offre, elle,
// reste au menu — c'est un levier commercial, pas une décision prise contre ce
// client.

let droits = null
vi.mock('../context/EntitlementsContext', () => ({
  useOptionalEntitlements: () => droits,
}))
vi.mock('../context/useDisplayProfile', async () => {
  const reel = await vi.importActual('../context/useDisplayProfile')
  return {
    ...reel,
    useDisplayProfile: () => ({ isTechnical: true, isExecutive: false, setProfile: vi.fn() }),
  }
})
vi.mock('../context/AuthContext', () => ({
  useAuth: () => ({
    user: { is_staff: false },
    currentTenant: { tenant_name: 'Menuiserie Lambert' },
    logout: vi.fn(),
  }),
}))

function rendu() {
  return render(
    <MemoryRouter>
      <Sidebar />
    </MemoryRouter>
  )
}

function liens() {
  return screen.getAllByRole('link').map((lien) => lien.textContent)
}

describe('Sidebar et périmètre composé', () => {
  it('garde le menu entier quand aucun droit n’est chargé', () => {
    droits = null
    rendu()

    expect(liens()).toContain('Diagnostic')
    expect(liens()).toContain('Comptes surveillés')
  })

  it('laisse au menu ce qui est seulement hors offre', () => {
    droits = { features: [{ key: 'watched_accounts', included: false, source: 'plan' }] }
    rendu()

    expect(liens()).toContain('Comptes surveillés')
  })

  it('retire du menu ce qui a été retiré à ce client', () => {
    droits = { features: [{ key: 'watched_accounts', included: false, source: 'override' }] }
    rendu()

    expect(liens()).not.toContain('Comptes surveillés')
    expect(liens()).toContain('Tableau de bord')
  })

  it('retire aussi les écrans qui n’existent que par la fonctionnalité retirée', () => {
    droits = { features: [{ key: 'anssi_assessment', included: false, source: 'override' }] }
    rendu()

    expect(liens()).not.toContain('Diagnostic')
    expect(liens()).not.toContain('Plan d’action')
    expect(liens()).toContain('Documents')
  })
})
