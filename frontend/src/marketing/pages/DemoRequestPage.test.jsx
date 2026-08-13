import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import DemoRequestPage from './DemoRequestPage'

// Le formulaire est le seul point de conversion du site vitrine : une
// régression y coûte des prospects sans faire de bruit. Les tests portent sur
// ce qui est envoyé, ce qui est refusé, et ce que voit le visiteur.

vi.mock('../../api/endpoints', () => ({
  publicApi: { requestDemo: vi.fn() },
}))

const { publicApi } = await import('../../api/endpoints')

function renderPage() {
  return render(
    <MemoryRouter>
      <DemoRequestPage />
    </MemoryRouter>
  )
}

async function fillRequired(user) {
  await user.type(screen.getByLabelText(/Nom et prénom/), 'Marie Durand')
  await user.type(screen.getByLabelText(/^Société/), 'Cabinet Durand')
  await user.type(screen.getByLabelText(/Email professionnel/), 'marie@cabinet.example')
}

describe('DemoRequestPage', () => {
  beforeEach(() => {
    publicApi.requestDemo.mockReset()
    publicApi.requestDemo.mockResolvedValue({ data: { detail: 'ok' } })
  })

  describe('soumission', () => {
    it('envoie les champs saisis', async () => {
      const user = userEvent.setup()
      renderPage()

      await fillRequired(user)
      await user.click(screen.getByRole('button', { name: /Envoyer ma demande/ }))

      expect(publicApi.requestDemo).toHaveBeenCalledWith(
        expect.objectContaining({
          full_name: 'Marie Durand',
          company: 'Cabinet Durand',
          email: 'marie@cabinet.example',
        })
      )
    })

    it('affiche une confirmation avec le délai de réponse', async () => {
      const user = userEvent.setup()
      renderPage()

      await fillRequired(user)
      await user.click(screen.getByRole('button', { name: /Envoyer ma demande/ }))

      expect(await screen.findByText(/Votre demande est bien enregistrée/)).toBeInTheDocument()
      // Sans délai annoncé, le prospect ne sait pas s'il doit relancer.
      expect(screen.getByText(/jour ouvré/)).toBeInTheDocument()
    })

    it('remplace le formulaire par la confirmation', async () => {
      const user = userEvent.setup()
      renderPage()

      await fillRequired(user)
      await user.click(screen.getByRole('button', { name: /Envoyer ma demande/ }))

      await screen.findByText(/Votre demande est bien enregistrée/)
      expect(screen.queryByRole('button', { name: /Envoyer ma demande/ })).not.toBeInTheDocument()
    })
  })

  describe('validation côté client', () => {
    it('refuse un envoi sans les champs obligatoires', async () => {
      const user = userEvent.setup()
      renderPage()

      await user.click(screen.getByRole('button', { name: /Envoyer ma demande/ }))

      expect(publicApi.requestDemo).not.toHaveBeenCalled()
      expect(screen.getByText(/Merci d’indiquer votre nom/)).toBeInTheDocument()
    })

    it('refuse une adresse email malformée', async () => {
      const user = userEvent.setup()
      renderPage()

      await user.type(screen.getByLabelText(/Nom et prénom/), 'Marie Durand')
      await user.type(screen.getByLabelText(/^Société/), 'Cabinet Durand')
      await user.type(screen.getByLabelText(/Email professionnel/), 'pas-un-email')
      await user.click(screen.getByRole('button', { name: /Envoyer ma demande/ }))

      expect(publicApi.requestDemo).not.toHaveBeenCalled()
      expect(screen.getByText(/adresse email valide/)).toBeInTheDocument()
    })

    it('efface l’erreur d’un champ dès sa correction', async () => {
      const user = userEvent.setup()
      renderPage()

      await user.click(screen.getByRole('button', { name: /Envoyer ma demande/ }))
      expect(screen.getByText(/Merci d’indiquer votre nom/)).toBeInTheDocument()

      await user.type(screen.getByLabelText(/Nom et prénom/), 'Marie')

      expect(screen.queryByText(/Merci d’indiquer votre nom/)).not.toBeInTheDocument()
    })
  })

  describe('anti-spam', () => {
    it('expose un champ piège hors de l’arbre d’accessibilité', () => {
      const { container } = renderPage()

      const honeypot = container.querySelector('input[name="website"]')
      expect(honeypot).toBeInTheDocument()
      expect(honeypot).toHaveAttribute('tabindex', '-1')
      // Masqué pour l'œil ET pour un lecteur d'écran : aucun humain ne doit
      // le rencontrer, sinon le piège pénaliserait de vrais visiteurs.
      expect(honeypot.closest('[aria-hidden="true"]')).not.toBeNull()
    })

    it('n’expose pas le champ piège aux technologies d’assistance', () => {
      renderPage()
      // getByRole (contrairement à getByLabelText) respecte aria-hidden :
      // c'est la requête qui reflète ce qu'un lecteur d'écran perçoit.
      const textboxes = screen.getAllByRole('textbox')
      expect(textboxes.some((el) => el.getAttribute('name') === 'website')).toBe(false)
    })
  })

  describe('erreurs serveur', () => {
    it('affiche un message dédié en cas de limitation de débit', async () => {
      const user = userEvent.setup()
      publicApi.requestDemo.mockRejectedValue({ response: { status: 429, data: {} } })
      renderPage()

      await fillRequired(user)
      await user.click(screen.getByRole('button', { name: /Envoyer ma demande/ }))

      expect(await screen.findByText(/Trop de demandes/)).toBeInTheDocument()
    })

    it('remonte les erreurs de champ renvoyées par le serveur', async () => {
      const user = userEvent.setup()
      publicApi.requestDemo.mockRejectedValue({
        response: {
          status: 400,
          data: { email: ["Merci d'utiliser une adresse email professionnelle."] },
        },
      })
      renderPage()

      await fillRequired(user)
      await user.click(screen.getByRole('button', { name: /Envoyer ma demande/ }))

      expect(
        await screen.findByText(/adresse email professionnelle/)
      ).toBeInTheDocument()
    })

    it('laisse le formulaire réutilisable après un échec', async () => {
      const user = userEvent.setup()
      publicApi.requestDemo.mockRejectedValue({ response: { status: 500, data: null } })
      renderPage()

      await fillRequired(user)
      await user.click(screen.getByRole('button', { name: /Envoyer ma demande/ }))

      await screen.findByText(/n’a pas pu être envoyée/)
      expect(screen.getByRole('button', { name: /Envoyer ma demande/ })).toBeEnabled()
    })
  })

  describe('double soumission', () => {
    it('n’envoie qu’une seule demande sur plusieurs clics', async () => {
      const user = userEvent.setup()
      publicApi.requestDemo.mockReturnValue(new Promise(() => {}))
      renderPage()

      await fillRequired(user)
      const submit = screen.getByRole('button', { name: /Envoyer ma demande/ })
      await user.click(submit)
      await user.click(submit).catch(() => {})

      expect(publicApi.requestDemo).toHaveBeenCalledTimes(1)
    })
  })
})
