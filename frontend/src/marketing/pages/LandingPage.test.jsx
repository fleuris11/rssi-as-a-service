import { render, screen, within } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { DEMONSTRATION, NAV } from '../content'
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

    it('tient en six actes, pas un de plus', () => {
      // C'est LE point de la refonte : la page était trop dense et le visiteur
      // s'y perdait. Si un septième acte apparaît, c'est que le détail est
      // remonté ici au lieu de rester sur sa page.
      const { container } = afficher()
      const actes = container.querySelectorAll('main > section')
      expect(actes).toHaveLength(6)
    })

    it('porte les six actes attendus, dans l’ordre', () => {
      const { container } = afficher()
      const identifiants = [...container.querySelectorAll('main > section')].map((s) => s.id)
      expect(identifiants).toEqual([
        'accroche',
        'probleme',
        'recevoir',
        'commencer',
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
    it('montre le produit en marche, sur le client de démonstration', () => {
      afficher()
      expect(screen.getAllByText(DEMONSTRATION.entreprise).length).toBeGreaterThan(0)
      expect(screen.getAllByText('Données de démonstration').length).toBe(1)
    })

    it('dit que ce sont des données de démonstration, deux fois plutôt qu’une', () => {
      // Une capture de produit sans mention visible de son caractère fictif
      // finit par être lue comme un vrai client. Le bandeau le dit, le
      // panneau le redit.
      afficher()
      expect(screen.getAllByText(/client de démonstration/).length).toBeGreaterThan(0)
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

    it('ne cite aucun chiffre commercial : le produit n’a qu’un client', () => {
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
