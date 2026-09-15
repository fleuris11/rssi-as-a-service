import { act, render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import NotificationBell, { INTERVALLE_MS } from './NotificationBell'

// Lot C, point 20 : une cloche, une liste, un état lu / non lu. Et la
// sobriété : le compteur ne s'interroge pas dans un onglet caché.

vi.mock('../api/endpoints', () => ({
  notificationsApi: {
    unreadCount: vi.fn(),
    inbox: vi.fn(),
    markRead: vi.fn(),
    markAllRead: vi.fn(),
  },
}))

const { notificationsApi } = await import('../api/endpoints')

const NOTIFICATIONS = [
  {
    id: 7,
    title: 'Votre demande « ISO 27001 » : contacté',
    link: '/mes-demandes',
    is_read: false,
    tenant_name: 'Cabinet Durand',
    created_at: '2026-09-14T09:00:00Z',
  },
  {
    id: 6,
    title: 'Votre rapport de comité d’août 2026 est prêt',
    link: '/rapports',
    is_read: true,
    tenant_name: 'Cabinet Durand',
    created_at: '2026-09-01T05:00:00Z',
  },
]

function rendre() {
  return render(
    <MemoryRouter initialEntries={['/tableau-de-bord']}>
      <Routes>
        <Route path="*" element={<NotificationBell />} />
      </Routes>
      <Routes>
        <Route path="/mes-demandes" element={<p>Page des demandes</p>} />
        <Route path="*" element={null} />
      </Routes>
    </MemoryRouter>
  )
}

describe('NotificationBell', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    notificationsApi.unreadCount.mockResolvedValue({ data: { unread: 3 } })
    notificationsApi.inbox.mockResolvedValue({ data: { results: NOTIFICATIONS } })
    notificationsApi.markRead.mockResolvedValue({ data: { updated: 1 } })
    notificationsApi.markAllRead.mockResolvedValue({ data: { updated: 3 } })
  })

  afterEach(() => {
    vi.useRealTimers()
    Object.defineProperty(document, 'visibilityState', { value: 'visible', configurable: true })
  })

  it('annonce le nombre de non lues, y compris au lecteur d’écran', async () => {
    rendre()

    expect(
      await screen.findByRole('button', { name: 'Notifications, 3 non lues' })
    ).toBeInTheDocument()
  })

  it('ouvre la liste, et une notification mène à son écran en se marquant lue', async () => {
    rendre()
    await userEvent.click(await screen.findByRole('button', { name: /Notifications, 3 non lues/ }))

    await userEvent.click(await screen.findByRole('button', { name: /ISO 27001/ }))

    expect(notificationsApi.markRead).toHaveBeenCalledWith([7])
    expect(await screen.findByText('Page des demandes')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Notifications, 2 non lues' })).toBeInTheDocument()
  })

  it('ne remarque pas comme lue une notification déjà lue', async () => {
    rendre()
    await userEvent.click(await screen.findByRole('button', { name: /Notifications, 3 non lues/ }))

    await userEvent.click(await screen.findByRole('button', { name: /rapport de comité/ }))

    expect(notificationsApi.markRead).not.toHaveBeenCalled()
  })

  it('marque tout comme lu', async () => {
    rendre()
    await userEvent.click(await screen.findByRole('button', { name: /Notifications, 3 non lues/ }))

    await userEvent.click(await screen.findByRole('button', { name: 'Tout marquer comme lu' }))

    await waitFor(() =>
      expect(screen.getByRole('button', { name: 'Notifications, aucune non lue' })).toBeInTheDocument()
    )
  })

  it('n’interroge pas le serveur quand l’onglet est caché', async () => {
    vi.useFakeTimers({ shouldAdvanceTime: true })
    rendre()
    await waitFor(() => expect(notificationsApi.unreadCount).toHaveBeenCalledTimes(1))

    Object.defineProperty(document, 'visibilityState', { value: 'hidden', configurable: true })
    await act(async () => {
      vi.advanceTimersByTime(INTERVALLE_MS * 3)
    })

    expect(notificationsApi.unreadCount).toHaveBeenCalledTimes(1)
  })
})
