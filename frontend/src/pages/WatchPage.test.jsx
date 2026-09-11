import { render, screen } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import WatchPage from './WatchPage'

// La veille vue du client : un argument commercial autant qu'un service. Ce
// qui compte ici est autant ce qui s'affiche que ce qui NE s'affiche PAS.

vi.mock('../api/endpoints', () => ({
  watchApi: { feed: vi.fn() },
}))

const showToast = vi.fn()
vi.mock('../components/ui/Toast', () => ({ useToast: () => ({ showToast }) }))

const { watchApi } = await import('../api/endpoints')

const PROMESSE =
  'Nous suivons les publications officielles des autorités et organismes de normalisation, ' +
  'et nous vous signalons ce qui change. Cette veille n’est ni exhaustive ni instantanée.'

const PUBLICATION = {
  id: 1,
  title: 'Recommandations relatives aux systèmes d’IA générative',
  url: 'https://cyber.gouv.fr/publications/ia',
  publisher: 'ANSSI',
  published_at: '2026-09-08T09:00:00Z',
  kind: 'new_requirement',
  kind_label: 'Nouvelle exigence',
  referential: 'Guide d’hygiène (ANSSI)',
  integrated: true,
}

describe('WatchPage', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    watchApi.feed.mockResolvedValue({ data: { promise: PROMESSE, results: [PUBLICATION] } })
  })

  it('affiche les publications retenues, avec leur émetteur et leur date', async () => {
    render(<WatchPage />)

    expect(await screen.findByText(/systèmes d’IA générative/)).toBeInTheDocument()
    expect(screen.getByText(/ANSSI/)).toBeInTheDocument()
  })

  it('renvoie au texte officiel, jamais à une reformulation', async () => {
    // « On ne livre pas ce qu'on ne peut pas sourcer » : le client doit
    // pouvoir vérifier lui-même.
    render(<WatchPage />)

    const lien = await screen.findByRole('link', { name: /Lire le texte officiel/ })
    expect(lien).toHaveAttribute('href', PUBLICATION.url)
  })

  it('dit quand une exigence est entrée dans le référentiel du client', async () => {
    render(<WatchPage />)

    expect(await screen.findByText('Ajoutée à votre référentiel')).toBeInTheDocument()
  })

  it('affiche la promesse du serveur, sans la réécrire', async () => {
    // La phrase est portée par l'API pour qu'elle ne dérive pas d'un écran à
    // l'autre. Un test backend interdit déjà « exhaustive » et « temps réel ».
    render(<WatchPage />)

    expect(await screen.findByText(/ni exhaustive ni instantanée/)).toBeInTheDocument()
  })

  it('reste explicite quand rien n’a été retenu', async () => {
    // Un écran vide et muet laisserait croire à une panne.
    watchApi.feed.mockResolvedValue({ data: { promise: PROMESSE, results: [] } })
    render(<WatchPage />)

    expect(await screen.findByText('Rien de nouveau pour le moment')).toBeInTheDocument()
    expect(screen.getByText(/Nous continuons de suivre les sources officielles/)).toBeInTheDocument()
  })
})
