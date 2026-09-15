import { render, screen, within } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { describe, expect, it, vi } from 'vitest'
import Sidebar from './Sidebar'

// Lot C, point 2 : « les écrans purement techniques sont accessibles mais pas
// mis en avant ». Le test tient les deux moitiés de la phrase : en profil
// dirigeant ils descendent dans leur section, et ils y restent cliquables.

let profilCourant = 'executive'

vi.mock('../context/useDisplayProfile', async () => {
  const reel = await vi.importActual('../context/useDisplayProfile')
  return {
    ...reel,
    useDisplayProfile: () => ({
      profile: profilCourant,
      isExecutive: profilCourant === 'executive',
      isTechnical: profilCourant === 'technical',
      setProfile: vi.fn(),
    }),
  }
})
vi.mock('../context/AuthContext', () => ({
  useAuth: () => ({
    user: { is_staff: false },
    currentTenant: { tenant_name: 'Cabinet Durand' },
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

function libellesPrincipaux() {
  const nav = screen.getByRole('navigation')
  return [...nav.querySelectorAll(':scope > a')].map((lien) => lien.textContent)
}

describe('Sidebar selon le profil', () => {
  it('range les écrans techniques à part pour le dirigeant, sans les retirer', () => {
    profilCourant = 'executive'
    rendu()

    expect(libellesPrincipaux()).not.toContain('Surveillance')
    expect(libellesPrincipaux()).not.toContain('Compromissions')

    const section = screen.getByRole('group', { name: 'Détails techniques' })
    expect(within(section).getByRole('link', { name: 'Surveillance' })).toHaveAttribute(
      'href',
      '/surveillance'
    )
    expect(within(section).getByRole('link', { name: 'Compromissions' })).toBeInTheDocument()
  })

  it('les laisse à leur place pour le technicien', () => {
    profilCourant = 'technical'
    rendu()

    expect(libellesPrincipaux()).toContain('Surveillance')
    expect(libellesPrincipaux()).toContain('Compromissions')
    expect(screen.queryByRole('group', { name: 'Détails techniques' })).not.toBeInTheDocument()
  })

  it('offre exactement les mêmes destinations dans les deux profils', () => {
    profilCourant = 'executive'
    const { unmount } = rendu()
    const dirigeant = screen.getAllByRole('link').map((l) => l.getAttribute('href')).sort()
    unmount()

    profilCourant = 'technical'
    rendu()
    const technique = screen.getAllByRole('link').map((l) => l.getAttribute('href')).sort()

    expect(dirigeant).toEqual(technique)
  })
})
