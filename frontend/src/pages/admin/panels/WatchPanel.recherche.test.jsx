import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import WatchPanel from './WatchPanel'

// Lot C, point 22 : l'onglet « Toutes » porte jusqu'à deux cents suggestions.

vi.mock('../../../api/endpoints', () => ({
  platformApi: { watchQueue: vi.fn(), watchSources: vi.fn() },
}))
vi.mock('../../../components/ui/Toast', () => ({ useToast: () => ({ showToast: vi.fn() }) }))

const { platformApi } = await import('../../../api/endpoints')

function suggestion(id, title, publisher) {
  return {
    id,
    title,
    url: `https://exemple-autorite.test/${id}`,
    source_name: 'Publications',
    source_publisher: publisher,
    published_at: '2026-09-08T09:00:00Z',
    detected_at: '2026-09-10T06:15:00Z',
    source_excerpt: '',
    status: 'new',
    kind: 'unqualified',
    ai_summary: '',
    review_note: '',
    integrated_measures: [],
  }
}

describe('WatchPanel — chercher une suggestion', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    platformApi.watchQueue.mockResolvedValue({
      data: {
        summary: { new: 2, kept: 0, integrated: 0, promise: 'Nous suivons…' },
        health: { total: 2, active: 2, failing: [], unconfigured: [] },
        results: [
          suggestion(1, 'Délibération sur les violations de données', 'CNIL'),
          suggestion(2, 'Guide d’hygiène informatique', 'ANSSI'),
        ],
      },
    })
    platformApi.watchSources.mockResolvedValue({ data: [] })
  })

  it('filtre par titre ou par émetteur, sans tenir compte des accents', async () => {
    render(<WatchPanel />)

    await userEvent.type(await screen.findByRole('searchbox', { name: 'Rechercher une suggestion' }), 'hygiene')

    expect(screen.getByText('Guide d’hygiène informatique')).toBeInTheDocument()
    expect(screen.queryByText('Délibération sur les violations de données')).not.toBeInTheDocument()

    await userEvent.clear(screen.getByRole('searchbox', { name: 'Rechercher une suggestion' }))
    await userEvent.type(screen.getByRole('searchbox', { name: 'Rechercher une suggestion' }), 'cnil')

    expect(screen.getByText('Délibération sur les violations de données')).toBeInTheDocument()
    expect(screen.queryByText('Guide d’hygiène informatique')).not.toBeInTheDocument()
  })

  it('ne présente pas une recherche vide comme une file vide', async () => {
    render(<WatchPanel />)

    await userEvent.type(await screen.findByRole('searchbox', { name: 'Rechercher une suggestion' }), 'zzz')

    expect(screen.getByText('Aucune suggestion ne correspond à cette recherche.')).toBeInTheDocument()
    expect(screen.queryByText('Rien à examiner')).not.toBeInTheDocument()
  })
})
