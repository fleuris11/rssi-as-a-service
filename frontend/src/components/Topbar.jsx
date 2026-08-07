import { Menu } from 'lucide-react'
import { useLocation } from 'react-router-dom'
import { pageTitleFor } from '../config/navigation'

export default function Topbar({ onOpenMenu }) {
  const location = useLocation()
  const title = pageTitleFor(location.pathname)

  return (
    <header className="sticky top-0 z-30 flex h-14 items-center gap-3 border-b border-ink-200 bg-surface/90 px-4 backdrop-blur-sm sm:px-6 lg:px-10">
      <button
        type="button"
        onClick={onOpenMenu}
        aria-label="Ouvrir le menu"
        className="transition-smooth -ml-1 rounded-md p-1.5 text-ink-600 hover:bg-ink-100 focus-visible:outline-2 focus-visible:outline-brand-600 lg:hidden"
      >
        <Menu className="size-5" aria-hidden="true" />
      </button>
      {/* Not an <h1>: every page already renders its own — this is a
          persistent location label, not the document heading. Two <h1>s
          with the same text is both bad a11y and ambiguous for tests. */}
      <p className="text-sm font-semibold text-ink-800">{title}</p>
    </header>
  )
}
