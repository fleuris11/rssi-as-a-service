import { useState } from 'react'
import { Outlet } from 'react-router-dom'
import Sidebar from './Sidebar'
import Topbar from './Topbar'

export default function AppLayout() {
  const [mobileOpen, setMobileOpen] = useState(false)

  return (
    <div className="min-h-screen bg-canvas">
      {/* Tablet (md-lg): icon-only rail. Desktop (lg+): full sidebar. Mobile:
          hidden, replaced by the drawer below. Two Sidebar instances are
          mounted (one per rail state) and toggled via Tailwind's responsive
          `hidden`, which removes the inactive one from the accessibility
          tree entirely — no duplicate-link ambiguity for assistive tech,
          keyboard tabbing, or Playwright's getByRole. */}
      <aside className="fixed inset-y-0 left-0 z-20 hidden md:block md:w-20 lg:w-64">
        <div className="h-full lg:hidden">
          <Sidebar collapsed />
        </div>
        <div className="hidden h-full lg:block">
          <Sidebar />
        </div>
      </aside>

      {mobileOpen && (
        <div className="fixed inset-0 z-40 md:hidden">
          <button
            type="button"
            aria-label="Fermer le menu"
            onClick={() => setMobileOpen(false)}
            className="absolute inset-0 bg-ink-950/50"
          />
          <div className="relative h-full w-72 shadow-elevated">
            <Sidebar onNavigate={() => setMobileOpen(false)} />
          </div>
        </div>
      )}

      <div className="md:pl-20 lg:pl-64">
        <Topbar onOpenMenu={() => setMobileOpen(true)} />
        <main className="px-4 py-6 sm:px-6 lg:px-10 lg:py-8">
          <Outlet />
        </main>
      </div>
    </div>
  )
}
