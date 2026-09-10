import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { Explanation, TechnicalDetail, Term } from './DisplayProfile'

// V2-5, point 3 de la consigne : « le contenu ne change jamais — seule sa
// présentation change. Un même fait doit rester le même fait. »
//
// C'est facile à écrire et facile à trahir : la tentation, en profil
// dirigeant, est de RETIRER le détail technique plutôt que de le replier. Ces
// tests interdisent la version facile — dans les deux profils, le texte est
// dans le document, seule sa visibilité diffère.

const setProfile = vi.fn()
let profilCourant = 'executive'

vi.mock('../context/useDisplayProfile', async () => {
  const reel = await vi.importActual('../context/useDisplayProfile')
  return {
    ...reel,
    useDisplayProfile: () => ({
      profile: profilCourant,
      isExecutive: profilCourant === 'executive',
      isTechnical: profilCourant === 'technical',
      setProfile,
    }),
  }
})

describe('TechnicalDetail', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('replie le détail en profil dirigeant, sans le retirer de la page', () => {
    profilCourant = 'executive'

    render(
      <TechnicalDetail summary="Détail">
        <p>en-tête Strict-Transport-Security absent</p>
      </TechnicalDetail>
    )

    const detail = screen.getByText('en-tête Strict-Transport-Security absent')
    // Présent dans le document — c'est le point : le dirigeant peut le
    // déplier, et une recherche dans la page le trouve.
    expect(detail).toBeInTheDocument()
    expect(detail).not.toBeVisible()
    expect(screen.getByRole('button', { name: 'Détail' })).toHaveAttribute(
      'aria-expanded',
      'false'
    )
  })

  it('déplie le même détail en profil technique', () => {
    profilCourant = 'technical'

    render(
      <TechnicalDetail summary="Détail">
        <p>en-tête Strict-Transport-Security absent</p>
      </TechnicalDetail>
    )

    expect(screen.getByText('en-tête Strict-Transport-Security absent')).toBeVisible()
  })

  it('se déplie à la demande, quel que soit le profil', async () => {
    profilCourant = 'executive'

    render(
      <TechnicalDetail summary="Détail">
        <p>certificat expirant le 12/10/2026</p>
      </TechnicalDetail>
    )
    await userEvent.click(screen.getByRole('button', { name: 'Détail' }))

    expect(screen.getByText('certificat expirant le 12/10/2026')).toBeVisible()
  })
})

describe('Term', () => {
  it('met la traduction devant pour un dirigeant', () => {
    profilCourant = 'executive'
    render(<Term code="SPF" plain="protection contre l’usurpation d’adresse" />)

    // Les deux sont là, dans les deux profils : masquer le terme technique
    // au dirigeant l'empêcherait de le reconnaître dans le courriel de son
    // prestataire, exactement quand il en a besoin.
    expect(
      screen.getByText(/protection contre l’usurpation d’adresse/)
    ).toBeInTheDocument()
    expect(screen.getByText('(SPF)')).toBeInTheDocument()
  })

  it('met le terme technique devant pour un technicien', () => {
    profilCourant = 'technical'
    render(<Term code="SPF" plain="protection contre l’usurpation d’adresse" />)

    expect(screen.getByText(/SPF/)).toBeInTheDocument()
    expect(screen.getByText('(protection contre l’usurpation d’adresse)')).toBeInTheDocument()
  })
})

describe('Explanation', () => {
  it('reste présente en profil technique, mais discrète', () => {
    profilCourant = 'executive'
    const { rerender, container } = render(<Explanation>Ce score mesure…</Explanation>)
    const classesDirigeant = container.firstChild.className

    profilCourant = 'technical'
    rerender(<Explanation>Ce score mesure…</Explanation>)

    // Même texte, présentation resserrée : « les explications restent mais ne
    // prennent pas toute la place » (consigne V2-5, point 2).
    expect(screen.getByText('Ce score mesure…')).toBeInTheDocument()
    expect(container.firstChild.className).not.toEqual(classesDirigeant)
  })
})
