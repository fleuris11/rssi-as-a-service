import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import NotificationsPage from './NotificationsPage'

vi.mock('../api/endpoints', () => ({
  notificationsApi: { inbox: vi.fn(), markRead: vi.fn(), markAllRead: vi.fn() },
}))
vi.mock('../components/ui/Toast', () => ({ useToast: () => ({ showToast: vi.fn() }) }))

const { notificationsApi } = await import('../api/endpoints')

function servir(results = []) {
  notificationsApi.inbox.mockResolvedValue({
    data: { count: results.length, next: null, previous: null, results },
  })
}

function rendre() {
  return render(
    <MemoryRouter>
      <NotificationsPage />
    </MemoryRouter>
  )
}

describe('NotificationsPage', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('liste les notifications avec leur nature, leur client et leur date', async () => {
    servir([
      {
        id: 1,
        title: '4 nouvelles fuites sur vos comptes surveillés',
        body: 'Chaque résultat est détaillé.',
        kind_label: 'Nouvelles fuites sur un compte surveillé',
        tenant_name: 'Cabinet Durand',
        link: '/comptes-surveilles',
        is_read: false,
        created_at: '2026-09-14T09:00:00Z',
      },
    ])
    rendre()

    expect(await screen.findByText('4 nouvelles fuites sur vos comptes surveillés')).toBeInTheDocument()
    expect(screen.getByText(/Nouvelles fuites sur un compte surveillé · Cabinet Durand/)).toBeInTheDocument()
    expect(screen.getByText('Non lue')).toBeInTheDocument()
  })

  it('filtre les non lues côté serveur', async () => {
    servir()
    rendre()
    await waitFor(() => expect(notificationsApi.inbox).toHaveBeenCalled())

    await userEvent.click(screen.getByRole('button', { name: 'Non lues' }))

    await waitFor(() =>
      expect(notificationsApi.inbox).toHaveBeenLastCalledWith({ page: 1, unread: '1' })
    )
  })

  it('cherche dans les notifications', async () => {
    servir()
    rendre()
    await waitFor(() => expect(notificationsApi.inbox).toHaveBeenCalled())

    await userEvent.type(screen.getByRole('searchbox', { name: 'Rechercher dans les notifications' }), 'rapport')

    await waitFor(() =>
      expect(notificationsApi.inbox).toHaveBeenLastCalledWith({ page: 1, q: 'rapport' })
    )
  })

  it('marque tout comme lu', async () => {
    servir()
    notificationsApi.markAllRead.mockResolvedValue({ data: { updated: 4 } })
    rendre()
    await waitFor(() => expect(notificationsApi.inbox).toHaveBeenCalled())

    await userEvent.click(screen.getByRole('button', { name: 'Tout marquer comme lu' }))

    expect(notificationsApi.markAllRead).toHaveBeenCalled()
  })
})
