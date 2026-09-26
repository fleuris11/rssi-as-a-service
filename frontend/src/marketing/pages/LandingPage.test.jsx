import { render, screen, within } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { ASSISTANT, DEMONSTRATION, NAV } from '../content'
import LandingPage from './LandingPage'

/**
 * La vitrine sera montrée à de vrais prospects. Ces tests verrouillent trois
 * choses : la navigation publique mène où il faut, l'accueil reste COURT et
 * renvoie vers les pages qui portent le détail, et le discours ne dérive pas
 * vers des promesses que le produit ne tient pas.
 */

vi.mock('../../api/client', () => ({
  tokenStorage: { getAccess: vi.fn(() => null) },
  apiClient: { get: vi.fn(() => Promise.reject(new Error('hors ligne'))) },
}))

const { tokenStorage } = await import('../../api/client')

function afficher() {
  return render(
    <MemoryRouter>
      <LandingPage />
    </MemoryRouter>
  )
}

describe('L’accueil', () => {
  beforeEach(() => {
    tokenStorage.getAccess.mockReturnValue(null)
  })

  describe('structure', () => {
    it('a un seul titre de premier niveau', () => {
      afficher()
      expect(screen.getAllByRole('heading', { level: 1 })).toHaveLength(1)
    })

    it('tient en sept actes, pas un de plus', () => {
      // C'est LE point de la refonte : la page était trop dense et le visiteur
      // s'y perdait. Si un huitième acte apparaît, c'est que le détail est
      // remonté ici au lieu de rester sur sa page.
      const { container } = afficher()
      const actes = container.querySelectorAll('main > section')
      expect(actes).toHaveLength(7)
    })

    it('porte les sept actes attendus, dans l’ordre', () => {
      const { container } = afficher()
      const identifiants = [...container.querySelectorAll('main > section')].map((s) => s.id)
      expect(identifiants).toEqual([
        'accroche',
        'probleme',
        'recevoir',
        'commencer',
        'assistant',
        'faits',
        'voir',
      ])
    })

    it('renvoie vers les pages qui portent le détail, au lieu de le supprimer', () => {
      afficher()
      for (const chemin of ['/fonctionnalites', '/securite-du-produit', '/offres']) {
        expect(
          screen.getAllByRole('link').some((lien) => lien.getAttribute('href')?.startsWith(chemin))
        ).toBe(true)
      }
    })

    it('expose la navigation vers les quatre pages secondaires', () => {
      afficher()
      const entete = screen.getByRole('banner')
      for (const entree of NAV) {
        expect(within(entete).getAllByRole('link', { name: entree.label })[0]).toHaveAttribute(
          'href',
          entree.href
        )
      }
    })
  })

  describe('l’action', () => {
    it('propose « Demander une démonstration » et rien d’autre comme action principale', () => {
      afficher()
      const demonstration = screen.getAllByRole('link', { name: /Demander une démonstration/ })
      expect(demonstration.length).toBeGreaterThan(0)
      expect(demonstration[0]).toHaveAttribute('href', '/demonstration')
    })

    it('propose la connexion depuis l’en-tête', () => {
      afficher()
      expect(screen.getAllByRole('link', { name: 'Se connecter' })[0]).toHaveAttribute(
        'href',
        '/connexion'
      )
    })

    it('remplace les deux actions par l’accès à l’espace quand on est déjà connecté', () => {
      tokenStorage.getAccess.mockReturnValue('un-jeton')
      afficher()
      expect(screen.getAllByRole('link', { name: /Accéder à mon espace/ })[0]).toHaveAttribute(
        'href',
        '/tableau-de-bord'
      )
      expect(screen.queryByRole('link', { name: 'Se connecter' })).not.toBeInTheDocument()
    })
  })

  describe('l’instrument du premier écran', () => {
    it('montre le produit en marche, sans nommer personne', () => {
      // L'accueil donnait l'impression que le produit était fait pour un
      // client en particulier : le panneau portait son nom en tête. Il montre
      // désormais ce que N'IMPORTE QUELLE organisation y voit.
      afficher()
      expect(screen.getByText('Ce que vous voyez en ouvrant le produit')).toBeInTheDocument()
      expect(screen.getAllByText(DEMONSTRATION.mention).length).toBeGreaterThan(0)
    })

    it('dit que les valeurs sont fictives, deux fois plutôt qu’une', () => {
      // Un instrument sans mention visible de son caractère fictif finit par
      // être lu comme les chiffres d'un vrai client. Le bandeau le dit, le
      // panneau le redit.
      afficher()
      expect(screen.getAllByText(/valeurs fictives/).length).toBeGreaterThanOrEqual(2)
    })

    it('affiche un score cohérent avec la dernière mesure de la courbe', () => {
      // Un instrument qui se contredit à l'écran est pire qu'un instrument
      // absent : la dernière valeur de la série DOIT être le score affiché.
      const derniere = DEMONSTRATION.serie[DEMONSTRATION.serie.length - 1]
      expect(Number(derniere.valeur)).toBe(DEMONSTRATION.score)
    })

    it('nomme le niveau en toutes lettres, pas seulement par la couleur', () => {
      afficher()
      expect(screen.getAllByText('À surveiller').length).toBeGreaterThan(0)
    })

    it('rend les alertes de démonstration dès le premier rendu', () => {
      // Elles arrivent en séquence à l'écran, mais aucune n'est conditionnée à
      // l'animation : un robot, une capture ou un lecteur d'écran voit tout.
      afficher()
      for (const alerte of DEMONSTRATION.alertes) {
        expect(screen.getByText(alerte.titre)).toBeInTheDocument()
      }
    })
  })

  describe('l’intelligence artificielle', () => {
    it('dit que le produit en contient une, et où elle sert', () => {
      // Elle n'apparaissait nulle part sur l'accueil alors que quatre usages
      // existent dans le produit.
      afficher()
      expect(screen.getByText(ASSISTANT.title)).toBeInTheDocument()
      for (const exemple of ASSISTANT.exemples) {
        expect(screen.getByText(`« ${exemple} »`)).toBeInTheDocument()
      }
    })

    it('annonce les trois garde-fous en même temps que la promesse', () => {
      // « Nous faisons de l'IA » ne distingue personne. Ce qui distingue,
      // c'est ce qu'elle s'interdit — et ça doit être sur la même page que
      // l'argument, pas trois clics plus loin.
      afficher()
      for (const garantie of ASSISTANT.garanties) {
        expect(screen.getByText(garantie.title)).toBeInTheDocument()
      }
    })
  })

  describe('le discours', () => {
    it('n’annonce ni blocage ni certification', () => {
      const { container } = afficher()
      const texte = container.textContent
      expect(texte).not.toMatch(/nous bloquons|bloque les attaques/i)
      // La page DOIT contenir « il ne vous certifie pas » : c'est le
      // démenti, pas la promesse. On cherche donc l'affirmation, jamais sa
      // négation — le premier jet de ce test attrapait son propre démenti.
      expect(texte).not.toMatch(/vous met en conformité|conformité garantie/i)
      expect(texte).toMatch(/ne vous certifie pas/i)
    })

    it('ne restreint pas le produit aux PME', () => {
      // Le produit s'adresse à toute organisation sans équipe sécurité, pas
      // aux seules PME : la vitrine ne doit pas refermer le marché.
      const { container } = afficher()
      expect(container.textContent).not.toMatch(/\bPME\b/)
    })

    it('ne grave aucun nombre de sources de renseignement', () => {
      // Il peut augmenter. Une vitrine qui annonce « neuf sources » devient
      // fausse le jour où il y en a dix, et personne ne pense à la corriger.
      const { container } = afficher()
      expect(container.textContent).not.toMatch(/(neuf|dix|onze|\d+)\s+sources/i)
    })

    it('ne cite aucun chiffre commercial', () => {
      const { container } = afficher()
      const texte = container.textContent
      expect(texte).not.toMatch(/\d+\s*(clients|entreprises)\s*(nous font confiance|accompagnées)/i)
      expect(texte).not.toMatch(/satisfaction/i)
    })

    it('ne nomme jamais le fournisseur de renseignement', () => {
      const { container } = afficher()
      expect(container.innerHTML.toLowerCase()).not.toContain('breachsense')
    })
  })
})
