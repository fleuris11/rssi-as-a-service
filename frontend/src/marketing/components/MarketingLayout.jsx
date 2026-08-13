import { Menu, X } from 'lucide-react'
import { useEffect, useState } from 'react'
import { Link, useLocation } from 'react-router-dom'
import { tokenStorage } from '../../api/client'
import { FOOTER, NAV, SITE } from '../content'

function Wordmark() {
  return (
    <span className="flex items-center gap-2.5">
      <span
        aria-hidden="true"
        className="flex size-8 items-center justify-center rounded-md bg-brand-700 font-display text-sm font-semibold text-white"
      >
        R
      </span>
      <span className="font-display text-base font-semibold text-ink-900">{SITE.name}</span>
    </span>
  )
}

function Header({ showSectionNav }) {
  const [open, setOpen] = useState(false)
  // Un client déjà connecté ne doit pas voir « Se connecter » : on regarde le
  // jeton stocké, sans appeler l'API — une route publique ne déclenche aucun
  // appel authentifié.
  const [hasSession] = useState(() => Boolean(tokenStorage.getAccess()))

  return (
    <header className="sticky top-0 z-40 border-b border-ink-200/70 bg-surface/85 backdrop-blur">
      <div className="mx-auto flex max-w-6xl items-center justify-between gap-4 px-5 py-3.5">
        <Link to="/" className="rounded-md focus-visible:outline-2 focus-visible:outline-brand-600">
          <Wordmark />
        </Link>

        {showSectionNav && (
          <nav aria-label="Sections du site" className="hidden items-center gap-7 lg:flex">
            {NAV.map((item) => (
              <a
                key={item.href}
                href={item.href}
                className="transition-smooth text-sm text-ink-600 hover:text-ink-900"
              >
                {item.label}
              </a>
            ))}
          </nav>
        )}

        <div className="hidden items-center gap-3 sm:flex">
          {hasSession ? (
            <Link
              to="/tableau-de-bord"
              className="transition-smooth rounded-md bg-brand-700 px-4 py-2 text-sm font-medium text-white hover:bg-brand-800 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-brand-600"
            >
              Accéder à mon espace
            </Link>
          ) : (
            <>
              <Link
                to="/connexion"
                className="transition-smooth rounded-md px-3 py-2 text-sm font-medium text-ink-700 hover:text-ink-900 focus-visible:outline-2 focus-visible:outline-brand-600"
              >
                Se connecter
              </Link>
              <Link
                to="/demonstration"
                className="transition-smooth rounded-md bg-brand-700 px-4 py-2 text-sm font-medium text-white hover:bg-brand-800 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-brand-600"
              >
                Demander une démonstration
              </Link>
            </>
          )}
        </div>

        <button
          type="button"
          onClick={() => setOpen((v) => !v)}
          aria-expanded={open}
          aria-label={open ? 'Fermer le menu' : 'Ouvrir le menu'}
          className="rounded-md p-2 text-ink-700 focus-visible:outline-2 focus-visible:outline-brand-600 sm:hidden"
        >
          {open ? <X className="size-5" /> : <Menu className="size-5" />}
        </button>
      </div>

      {open && (
        <div className="border-t border-ink-200/70 bg-surface px-5 py-4 sm:hidden">
          <nav aria-label="Menu" className="flex flex-col gap-1">
            {showSectionNav &&
              NAV.map((item) => (
                <a
                  key={item.href}
                  href={item.href}
                  onClick={() => setOpen(false)}
                  className="rounded-md px-2 py-2.5 text-sm text-ink-700 hover:bg-ink-50"
                >
                  {item.label}
                </a>
              ))}
            <div className="mt-2 flex flex-col gap-2 border-t border-ink-100 pt-3">
              {hasSession ? (
                <Link
                  to="/tableau-de-bord"
                  className="rounded-md bg-brand-700 px-4 py-2.5 text-center text-sm font-medium text-white"
                >
                  Accéder à mon espace
                </Link>
              ) : (
                <>
                  <Link
                    to="/connexion"
                    className="rounded-md border border-ink-200 px-4 py-2.5 text-center text-sm font-medium text-ink-800"
                  >
                    Se connecter
                  </Link>
                  <Link
                    to="/demonstration"
                    className="rounded-md bg-brand-700 px-4 py-2.5 text-center text-sm font-medium text-white"
                  >
                    Demander une démonstration
                  </Link>
                </>
              )}
            </div>
          </nav>
        </div>
      )}
    </header>
  )
}

function Footer() {
  return (
    <footer className="border-t border-ink-200/70 bg-ink-50/60">
      <div className="mx-auto grid max-w-6xl gap-10 px-5 py-14 sm:grid-cols-2 lg:grid-cols-4">
        <div className="lg:col-span-2">
          <Wordmark />
          <p className="mt-3 max-w-sm text-sm leading-relaxed text-ink-600">
            {FOOTER.description}
          </p>
          <p className="mt-3 max-w-sm text-xs text-ink-500">{FOOTER.legalNote}</p>
        </div>
        {FOOTER.columns.map((column) => (
          <div key={column.title}>
            <h2 className="text-xs font-semibold uppercase tracking-wide text-ink-500">
              {column.title}
            </h2>
            <ul className="mt-3 space-y-2">
              {column.links.map((link) => (
                <li key={link.label}>
                  <Link
                    to={link.href}
                    className="transition-smooth text-sm text-ink-600 hover:text-ink-900"
                  >
                    {link.label}
                  </Link>
                </li>
              ))}
            </ul>
          </div>
        ))}
      </div>
      <div className="border-t border-ink-200/70">
        <div className="mx-auto flex max-w-6xl flex-wrap items-center justify-between gap-3 px-5 py-5 text-xs text-ink-500">
          <p>
            © {new Date().getFullYear()} {SITE.name}
          </p>
          <p>{SITE.contactEmail}</p>
        </div>
      </div>
    </footer>
  )
}

export default function MarketingLayout({ children, showSectionNav = false }) {
  const { hash } = useLocation()

  // Ancre profonde (arrivée depuis le pied de page d'une autre page) : le
  // navigateur ne défile pas tout seul quand la cible est montée après coup.
  useEffect(() => {
    if (!hash) return
    const target = document.querySelector(hash)
    target?.scrollIntoView({ behavior: 'smooth', block: 'start' })
  }, [hash])

  return (
    <div className="flex min-h-screen flex-col bg-surface">
      <a
        href="#contenu"
        className="sr-only focus:not-sr-only focus:absolute focus:left-4 focus:top-4 focus:z-50 focus:rounded-md focus:bg-brand-700 focus:px-4 focus:py-2 focus:text-sm focus:text-white"
      >
        Aller au contenu
      </a>
      <Header showSectionNav={showSectionNav} />
      <main id="contenu" className="flex-1">
        {children}
      </main>
      <Footer />
    </div>
  )
}
