import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import {
  AlertReading,
  Explanation,
  lectureDuScore,
  ProfileDate,
  ScoreReading,
  TechnicalDetail,
  TechnicalValue,
  Term,
} from './DisplayProfile'

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

// --- Lot C : les primitives qui manquaient ----------------------------------

describe('ProfileDate', () => {
  const instant = '2026-09-12T14:03:22Z'

  it('donne une date lisible au dirigeant, et garde l’instant exact', () => {
    profilCourant = 'executive'
    const { container } = render(<ProfileDate value={instant} />)

    const time = container.querySelector('time')
    expect(time).toHaveTextContent(/septembre 2026/)
    expect(time).not.toHaveTextContent(/:\d\d:\d\d/)
    // Même instant : la valeur exacte est portée par l'élément.
    expect(time).toHaveAttribute('dateTime', '2026-09-12T14:03:22.000Z')
  })

  it('donne l’horodatage à la seconde, avec son fuseau, au technicien', () => {
    profilCourant = 'technical'
    const { container } = render(<ProfileDate value={instant} />)

    const time = container.querySelector('time')
    expect(time).toHaveTextContent(/^2026-09-12 \d\d:03:22 UTC[+-]\d\d:\d\d$/)
    expect(time).toHaveAttribute('dateTime', '2026-09-12T14:03:22.000Z')
  })

  it('n’invente pas d’heure pour une date qui n’en a pas', () => {
    profilCourant = 'technical'
    const { container } = render(<ProfileDate value="2026-07-03" dateOnly />)

    expect(container.querySelector('time')).toHaveTextContent(/^2026-07-0[23]$/)
  })

  it('dit qu’une date manque plutôt que d’en afficher une fausse', () => {
    profilCourant = 'executive'
    render(<ProfileDate value={null} fallback="date inconnue" />)
    expect(screen.getByText('date inconnue')).toBeInTheDocument()
  })
})

describe('TechnicalValue', () => {
  it('reste dans la page en profil dirigeant, masquée', () => {
    profilCourant = 'executive'
    render(<TechnicalValue label="source" value="stealer" />)

    const valeur = screen.getByText('source stealer')
    expect(valeur).toBeInTheDocument()
    expect(valeur).not.toBeVisible()
  })

  it('s’affiche en profil technique', () => {
    profilCourant = 'technical'
    render(<TechnicalValue label="source" value="stealer" />)
    expect(screen.getByText('source stealer')).toBeVisible()
  })
})

describe('ScoreReading', () => {
  it('accompagne le chiffre de son sens, pour le dirigeant', () => {
    profilCourant = 'executive'
    const { container } = render(<ScoreReading score={92} scale="maturity" />)
    expect(container).toHaveTextContent('92 sur 100 — votre niveau est solide')
  })

  it('met le chiffre devant pour le technicien, sans perdre la phrase', () => {
    profilCourant = 'technical'
    const { container } = render(<ScoreReading score={92} scale="maturity" />)
    expect(container).toHaveTextContent('92/100')
    expect(container).toHaveTextContent('votre niveau est solide')
  })

  it('lit les deux échelles dans leur sens', () => {
    // Maturité : haut = bien. Exposition : haut = mal. La même valeur ne peut
    // pas se lire pareil sur les deux — c'était le défaut de la jauge.
    expect(lectureDuScore(85, 'maturity')).toBe('votre niveau est solide')
    expect(lectureDuScore(85, 'exposure')).toBe(
      'votre exposition est critique, une action est attendue'
    )
    expect(lectureDuScore(null, 'maturity')).toBeNull()
  })
})

describe('AlertReading', () => {
  function rendu() {
    return render(
      <AlertReading
        meaning="Un escroc peut écrire en votre nom."
        action="Faites compléter SPF et DMARC."
        detail={<p>v=spf1 absent</p>}
      />
    )
  }

  function ordre(container) {
    const racine = container.querySelector('[data-lecture]')
    return [...racine.children].map((bloc) => bloc.textContent)
  }

  it('mène avec l’impact et l’action pour le dirigeant, le constat replié', () => {
    profilCourant = 'executive'
    const { container } = rendu()

    const blocs = ordre(container)
    expect(blocs[0]).toMatch(/Un escroc peut écrire en votre nom/)
    expect(blocs[1]).toMatch(/Faites compléter SPF et DMARC/)
    expect(screen.getByText('v=spf1 absent')).not.toBeVisible()
  })

  it('mène avec le constat déplié pour le technicien', () => {
    profilCourant = 'technical'
    const { container } = rendu()

    expect(ordre(container)[0]).toMatch(/v=spf1 absent/)
    expect(screen.getByText('v=spf1 absent')).toBeVisible()
  })

  it('porte exactement les mêmes faits dans les deux profils', () => {
    profilCourant = 'executive'
    const dirigeant = rendu().container.textContent
    document.body.innerHTML = ''
    profilCourant = 'technical'
    const technique = rendu().container.textContent

    for (const fait of ['Un escroc peut écrire en votre nom.', 'Faites compléter SPF et DMARC.', 'v=spf1 absent']) {
      expect(dirigeant).toContain(fait)
      expect(technique).toContain(fait)
    }
  })
})
