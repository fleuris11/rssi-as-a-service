import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import RevealSecretModal from './RevealSecretModal'

// Le composant le plus sensible du produit : il affiche en clair un mot de
// passe issu d'une fuite, derrière une ré-authentification. Les tests ci-
// dessous ciblent les comportements dont la régression serait à la fois
// silencieuse et coûteuse — pas la couverture de lignes.

vi.mock('../api/endpoints', () => ({
  threatIntelligenceApi: { revealFindingSecret: vi.fn() },
}))

const { threatIntelligenceApi } = await import('../api/endpoints')

function renderModal(props = {}) {
  return render(
    <RevealSecretModal open findingId={42} onClose={vi.fn()} {...props} />
  )
}

async function submitPassword(user, password = 'MotDePasse!') {
  await user.type(screen.getByLabelText('Votre mot de passe'), password)
  await user.click(screen.getByRole('button', { name: /Vérifier et révéler/ }))
}

describe('RevealSecretModal', () => {
  beforeEach(() => {
    threatIntelligenceApi.revealFindingSecret.mockReset()
  })

  describe('ré-authentification', () => {
    it('affiche le secret déchiffré après une ré-authentification réussie', async () => {
      const user = userEvent.setup()
      threatIntelligenceApi.revealFindingSecret.mockResolvedValue({
        data: { secret: 'Hiver2024!durand' },
      })
      renderModal()

      await submitPassword(user)

      expect(await screen.findByText('Hiver2024!durand')).toBeInTheDocument()
    })

    it('transmet le mot de passe saisi, jamais un code TOTP vide en plus', async () => {
      const user = userEvent.setup()
      threatIntelligenceApi.revealFindingSecret.mockResolvedValue({ data: { secret: 'x' } })
      renderModal()

      await submitPassword(user, 'MonMotDePasse')

      expect(threatIntelligenceApi.revealFindingSecret).toHaveBeenCalledWith(42, {
        password: 'MonMotDePasse',
        totpCode: '',
      })
    })

    it('affiche une erreur et AUCUN secret quand les identifiants sont refusés', async () => {
      const user = userEvent.setup()
      threatIntelligenceApi.revealFindingSecret.mockRejectedValue({
        response: { status: 401, data: { detail: 'Ré-authentification invalide.' } },
      })
      renderModal()

      await submitPassword(user, 'MauvaisMotDePasse')

      expect(await screen.findByText('Ré-authentification invalide.')).toBeInTheDocument()
      expect(screen.queryByText(/Masqué automatiquement/)).not.toBeInTheDocument()
    })

    it("n'émet QU'UN SEUL appel réseau pour un identifiant refusé", async () => {
      // Régression de la Phase 7 : l'intercepteur Axios retentait tout 401
      // après rafraîchissement du jeton, en supposant un jeton expiré. Le 401
      // de step-up (mot de passe erroné) déclenchait donc une seconde
      // soumission automatique — deux lignes d'audit et deux décomptes de
      // rate limit pour une seule erreur de saisie. Corrigé par le flag
      // skipAuthRetry ; ce test verrouille le comportement au niveau du
      // composant, où il est observable sans monter tout l'intercepteur.
      const user = userEvent.setup()
      threatIntelligenceApi.revealFindingSecret.mockRejectedValue({
        response: { status: 401, data: { detail: 'Ré-authentification invalide.' } },
      })
      renderModal()

      await submitPassword(user, 'MauvaisMotDePasse')

      await screen.findByText('Ré-authentification invalide.')
      expect(threatIntelligenceApi.revealFindingSecret).toHaveBeenCalledTimes(1)
    })

    it('affiche un message dédié en cas de dépassement du rate limit', async () => {
      const user = userEvent.setup()
      threatIntelligenceApi.revealFindingSecret.mockRejectedValue({
        response: { status: 429, data: {} },
      })
      renderModal()

      await submitPassword(user)

      expect(await screen.findByText(/Trop de tentatives/)).toBeInTheDocument()
    })
  })

  describe('état de chargement et double soumission', () => {
    it('affiche « Vérification de votre identité… » pendant l’appel', async () => {
      const user = userEvent.setup()
      let resolveCall
      threatIntelligenceApi.revealFindingSecret.mockReturnValue(
        new Promise((resolve) => {
          resolveCall = resolve
        })
      )
      renderModal()

      await submitPassword(user)

      // La vérification serveur prend ~1,5 s (PBKDF2) : sans ce message, la
      // modale paraît figée.
      expect(screen.getAllByText(/Vérification de votre identité/).length).toBeGreaterThan(0)

      resolveCall({ data: { secret: 'ok' } })
      expect(await screen.findByText('ok')).toBeInTheDocument()
    })

    it('ignore les clics répétés pendant la vérification', async () => {
      const user = userEvent.setup()
      threatIntelligenceApi.revealFindingSecret.mockReturnValue(new Promise(() => {}))
      renderModal()

      await user.type(screen.getByLabelText('Votre mot de passe'), 'MotDePasse!')
      const submit = screen.getByRole('button', { name: /Vérifier et révéler/ })
      await user.click(submit)
      await user.click(submit).catch(() => {})
      await user.click(submit).catch(() => {})

      // Trois clics, un seul appel : deux tentatives pour un seul geste
      // compteraient double dans le journal d'audit et le rate limit.
      expect(threatIntelligenceApi.revealFindingSecret).toHaveBeenCalledTimes(1)
    })
  })

  describe('affichage éphémère du secret', () => {
    it('masque le secret automatiquement au bout de 30 secondes', async () => {
      // shouldAdvanceTime : sans lui, `waitFor` (qui sonde sur l'horloge
      // réelle) et les promesses de l'appel API resteraient bloqués sous
      // horloge figée.
      vi.useFakeTimers({ shouldAdvanceTime: true })
      const user = userEvent.setup({ advanceTimers: vi.advanceTimersByTime })
      threatIntelligenceApi.revealFindingSecret.mockResolvedValue({
        data: { secret: 'SecretEphemere' },
      })
      renderModal()

      await submitPassword(user)
      await waitFor(() => expect(screen.getByText('SecretEphemere')).toBeInTheDocument())

      await vi.advanceTimersByTimeAsync(31000)

      // Le secret disparaît et le formulaire de ré-authentification revient :
      // un secret laissé à l'écran indéfiniment annulerait tout l'intérêt de
      // la révélation ponctuelle (ADR-014).
      await waitFor(() => expect(screen.queryByText('SecretEphemere')).not.toBeInTheDocument())
      expect(screen.getByLabelText('Votre mot de passe')).toBeInTheDocument()
    })

    it('décompte le temps restant à l’écran', async () => {
      // shouldAdvanceTime : sans lui, `waitFor` (qui sonde sur l'horloge
      // réelle) et les promesses de l'appel API resteraient bloqués sous
      // horloge figée.
      vi.useFakeTimers({ shouldAdvanceTime: true })
      const user = userEvent.setup({ advanceTimers: vi.advanceTimersByTime })
      threatIntelligenceApi.revealFindingSecret.mockResolvedValue({ data: { secret: 's' } })
      renderModal()

      await submitPassword(user)
      await waitFor(() => expect(screen.getByText(/Masqué automatiquement dans/)).toBeInTheDocument())

      await vi.advanceTimersByTimeAsync(5000)

      expect(screen.getByText(/Masqué automatiquement dans/).textContent).toMatch(/2[0-9]s/)
    })

    it('efface le secret de l’écran à la fermeture', async () => {
      const user = userEvent.setup()
      const onClose = vi.fn()
      threatIntelligenceApi.revealFindingSecret.mockResolvedValue({
        data: { secret: 'SecretAFermer' },
      })
      const { rerender } = renderModal({ onClose })

      await submitPassword(user)
      await screen.findByText('SecretAFermer')
      // « Fermer » désigne trois éléments (l'arrière-plan, la croix, le
      // bouton de pied de modale) : on vise celui du pied, seul à porter le
      // libellé comme contenu textuel plutôt que comme aria-label.
      const closeButtons = screen.getAllByRole('button', { name: 'Fermer' })
      await user.click(closeButtons[closeButtons.length - 1])

      expect(onClose).toHaveBeenCalled()

      // Réouverture : on doit repartir du formulaire, jamais du secret encore
      // affiché.
      rerender(<RevealSecretModal open={false} findingId={42} onClose={onClose} />)
      rerender(<RevealSecretModal open findingId={42} onClose={onClose} />)
      expect(screen.queryByText('SecretAFermer')).not.toBeInTheDocument()
      expect(screen.getByLabelText('Votre mot de passe')).toBeInTheDocument()
    })
  })

  describe('traçabilité', () => {
    it('rappelle que l’accès est tracé, avant toute saisie', () => {
      renderModal()
      expect(screen.getByText(/Cet accès est tracé/)).toBeInTheDocument()
    })
  })
})
