import { render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { PRICING } from '../content'
import LandingPage from './LandingPage'

// La vitrine sera montrée à de vrais prospects. Ces tests verrouillent deux
// choses : la navigation publique fonctionne (les liens de conversion mènent
// où il faut), et le discours ne dérive pas vers des promesses que le produit
// ne tient pas.

vi.mock('../../api/client', () => ({
  tokenStorage: { getAccess: vi.fn(() => null) },
  // La grille tarifaire est lue sur l'endpoint PUBLIC des offres. Par défaut
  // on fait échouer l'appel : les tests ci-dessous vérifient alors le repli
  // statique, qui est le comportement à garantir en priorité (une grille vide
  // sur la vitrine est pire qu'une grille légèrement datée).
  apiClient: { get: vi.fn(() => Promise.reject(new Error('hors ligne'))) },
}))

const { tokenStorage, apiClient } = await import('../../api/client')

function renderPage() {
  return render(
    <MemoryRouter>
      <LandingPage />
    </MemoryRouter>
  )
}

describe('LandingPage', () => {
  beforeEach(() => {
    tokenStorage.getAccess.mockReturnValue(null)
  })

  describe('structure et navigation', () => {
    it('a un seul titre de premier niveau', () => {
      renderPage()
      expect(screen.getAllByRole('heading', { level: 1 })).toHaveLength(1)
    })

    it('propose les deux actions de l’accroche', () => {
      renderPage()
      const demoLinks = screen.getAllByRole('link', { name: /Demander une démonstration/ })
      expect(demoLinks.length).toBeGreaterThan(0)
      expect(demoLinks[0]).toHaveAttribute('href', '/demonstration')
      expect(screen.getAllByRole('link', { name: 'Se connecter' })[0]).toHaveAttribute(
        'href',
        '/connexion'
      )
    })

    it('affiche toutes les sections attendues', () => {
      const { container } = renderPage()
      for (const id of ['probleme', 'produit', 'fonctionnement', 'securite', 'tarifs', 'questions']) {
        expect(container.querySelector(`#${id}`)).toBeInTheDocument()
      }
    })

    it('propose un lien d’évitement vers le contenu', () => {
      renderPage()
      expect(screen.getByRole('link', { name: /Aller au contenu/ })).toHaveAttribute(
        'href',
        '#contenu'
      )
    })
  })

  describe('visiteur déjà connecté', () => {
    it('propose l’accès à son espace plutôt que la connexion', () => {
      tokenStorage.getAccess.mockReturnValue('un-jeton')
      renderPage()

      expect(screen.getAllByRole('link', { name: /Accéder à mon espace/ })[0]).toHaveAttribute(
        'href',
        '/tableau-de-bord'
      )
    })

    it('ne déclenche aucun appel authentifié', () => {
      // La vitrine n'interroge que l'endpoint PUBLIC des offres : elle lit le
      // jeton stocké pour adapter son bouton, sans jamais appeler une route
      // qui exige une authentification.
      renderPage()
      expect(tokenStorage.getAccess).toHaveBeenCalled()
      for (const [url] of apiClient.get.mock.calls) {
        expect(url).toBe('/api/v1/billing/plans/')
      }
    })
  })

  describe('tarifs', () => {
    it('affiche les trois paliers avec leurs montants', () => {
      renderPage()
      const pricing = document.querySelector('#tarifs')
      for (const plan of PRICING.plans) {
        expect(within(pricing).getByText(plan.name)).toBeInTheDocument()
        // Le montant est rendu dans un <span> imbriqué dans un <p> : les deux
        // correspondent au texte, on cible donc le nœud le plus profond.
        expect(
          within(pricing).getAllByText(new RegExp(`^${plan.price}\\s*€$`)).length
        ).toBeGreaterThan(0)
      }
    })

    it('présente clairement les montants comme indicatifs', () => {
      renderPage()
      const pricing = document.querySelector('#tarifs')
      // Mentionné deux fois à dessein : en sous-titre et en avertissement bas
      // de section — un prospect ne doit pas pouvoir le manquer.
      expect(within(pricing).getAllByText(/indicatif/i).length).toBeGreaterThan(0)
    })

    it('met un seul palier en avant', () => {
      renderPage()
      expect(screen.getAllByText('Le plus demandé')).toHaveLength(1)
    })

    it('affiche les offres publiées par l’administration plutôt que le repli', async () => {
      // Modifier une offre en back-office doit se voir sur la vitrine sans
      // redéploiement (ADR-019).
      apiClient.get.mockResolvedValueOnce({
        data: {
          plans: [
            {
              code: 'veille',
              name: 'Veille renommée',
              tagline: 'Nouveau positionnement',
              price_monthly: 119,
              currency: '€',
              is_quote_only: false,
              is_highlighted: false,
              features: [{ key: 'a', label: 'Surveillance continue' }],
            },
          ],
        },
      })
      renderPage()

      expect(await screen.findByText('Veille renommée')).toBeInTheDocument()
      expect(screen.getByText(/^119\s*€$/)).toBeInTheDocument()
    })

    it('conserve la grille statique quand l’API ne répond pas', async () => {
      // Le repli est le comportement par défaut du mock : on vérifie qu'un
      // échec réseau laisse une grille complète, pas une section vide.
      renderPage()
      const pricing = document.querySelector('#tarifs')

      await waitFor(() => expect(apiClient.get).toHaveBeenCalled())
      for (const plan of PRICING.plans) {
        expect(within(pricing).getByText(plan.name)).toBeInTheDocument()
      }
    })
  })

  describe('questions fréquentes', () => {
    it('déplie une réponse au clic', async () => {
      const user = userEvent.setup()
      renderPage()

      const question = screen.getByRole('button', { name: /Où sont hébergées nos données/ })
      // La première est ouverte par défaut : on en ouvre une autre.
      const another = screen.getByRole('button', { name: /Faut-il installer quelque chose/ })
      expect(another).toHaveAttribute('aria-expanded', 'false')

      await user.click(another)

      expect(another).toHaveAttribute('aria-expanded', 'true')
      expect(question).toHaveAttribute('aria-expanded', 'false')
    })
  })

  describe('exactitude du discours', () => {
    it('ne promet jamais de bloquer les attaques', () => {
      const { container } = renderPage()
      const text = container.textContent.toLowerCase()
      // Le produit détecte et alerte : il n'intervient pas sur les systèmes
      // du client. Cette limite est un argument de crédibilité, pas un aveu.
      expect(text).not.toMatch(/nous bloquons/)
      expect(text).not.toMatch(/protection totale/)
      expect(text).not.toMatch(/100\s*% (sécurisé|protégé)/)
    })

    it('ne garantit jamais la conformité', () => {
      const { container } = renderPage()
      const text = container.textContent.toLowerCase()
      expect(text).not.toMatch(/conformité garantie/)
      expect(text).not.toMatch(/vous met en conformité/)
    })

    it('parle de réutilisation possible, jamais confirmée', () => {
      const { container } = renderPage()
      const text = container.textContent.toLowerCase()
      expect(text).toMatch(/réutilisation possible/)
      expect(text).not.toMatch(/réutilisation confirmée/)
      expect(text).not.toMatch(/mot de passe confirmé/)
    })

    it('annonce neuf sources, le nombre réellement interrogé', () => {
      // La dixième valeur de l'énumération côté serveur est « webhook », un
      // canal de livraison et non une source : annoncer dix serait faux.
      const { container } = renderPage()
      expect(container.textContent).toMatch(/neuf sources/i)
      expect(container.textContent).not.toMatch(/dix sources/i)
    })

    it('ne cible aucun pays', () => {
      const { container } = renderPage()
      const text = container.textContent.toLowerCase()
      expect(text).not.toMatch(/française|francaises|français(e|es)\b/)
    })

    it('n’emploie aucun superlatif creux', () => {
      const { container } = renderPage()
      const text = container.textContent.toLowerCase()
      for (const banned of ['révolutionnaire', 'innovant', 'de pointe', 'boostez', 'unlock']) {
        expect(text).not.toContain(banned)
      }
    })
  })
})
