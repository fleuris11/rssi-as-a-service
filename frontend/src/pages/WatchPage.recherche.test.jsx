import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import WatchPage from './WatchPage'

// Lot C, point 22 : la veille était tronquée à vingt publications, sans
// recherche ni page suivante.

vi.mock('../api/endpoints', () => ({ watchApi: { feed: vi.fn() } }))
vi.mock('../components/ui/Toast', () => ({ useToast: () => ({ showToast: vi.fn() }) }))

const { watchApi } = await import('../api/endpoints')

const PUBLICATION = {
  id: 1,
  title: 'Délibération sur les violations de données',
  url: 'https://exemple.test/violations',
  publisher: 'CNIL',
  published_at: '2026-09-07',
  kind: 'update',
  integrated: false,
}

function servir(surcharge = {}) {
  watchApi.feed.mockResolvedValue({
    data: { promise: 'Promesse.', count: 1, page: 1, has_next: false, results: [PUBLICATION], ...surcharge },
  })
}

describe('WatchPage — chercher et parcourir', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('envoie la recherche au serveur', async () => {
    servir()
    render(<WatchPage />)

    await userEvent.type(await screen.findByRole('searchbox', { name: 'Rechercher dans la veille' }), 'violations')

    await waitFor(() =>
      expect(watchApi.feed).toHaveBeenLastCalledWith({ page: 1, q: 'violations' })
    )
  })

  it('filtre par nature', async () => {
    servir()
    render(<WatchPage />)

    await userEvent.selectOptions(await screen.findByRole('combobox', { name: 'Filtrer par nature' }), 'new_requirement')

    await waitFor(() =>
      expect(watchApi.feed).toHaveBeenLastCalledWith({ page: 1, kind: 'new_requirement' })
    )
  })

  it('donne accès aux publications au-delà de la première page', async () => {
    servir({ count: 25, has_next: true })
    render(<WatchPage />)

    await userEvent.click(await screen.findByRole('button', { name: 'Suivantes' }))

    await waitFor(() => expect(watchApi.feed).toHaveBeenLastCalledWith({ page: 2 }))
  })

  it('dit qu’aucune publication ne correspond, sans prétendre que rien n’est paru', async () => {
    servir()
    render(<WatchPage />)
    await screen.findByText('Délibération sur les violations de données')
    watchApi.feed.mockResolvedValue({
      data: { promise: 'Promesse.', count: 0, page: 1, has_next: false, results: [] },
    })

    await userEvent.type(screen.getByRole('searchbox', { name: 'Rechercher dans la veille' }), 'zzz')

    expect(await screen.findByText('Aucune publication ne correspond')).toBeInTheDocument()
    expect(screen.queryByText('Rien de nouveau pour le moment')).not.toBeInTheDocument()
  })
})
