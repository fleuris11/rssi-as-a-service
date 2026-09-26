import { Menu, X } from 'lucide-react'
import { useEffect, useState } from 'react'
import { Link, NavLink, useLocation } from 'react-router-dom'
import { tokenStorage } from '../../api/client'
import Logo, { LogoComplet } from '../../components/Logo'
import { FOOTER, NAV, SITE } from '../content'

function Entete() {
  const [ouvert, setOuvert] = useState(false)
  const { pathname } = useLocation()
  // Un client déjà connecté ne doit pas voir « Se connecter » : on regarde le
  // jeton stocké, sans appeler l'API — une route publique ne déclenche aucun
  // appel authentifié.
  const [connecte] = useState(() => Boolean(tokenStorage.getAccess()))

  // Le menu du téléphone ne doit pas survivre au changement de page : sinon on
  // arrive sur la nouvelle page avec le panneau encore déplié par-dessus.
  useEffect(() => setOuvert(false), [pathname])

  const lienPrincipal = connecte
    ? { vers: '/tableau-de-bord', libelle: 'Accéder à mon espace' }
    : { vers: '/demonstration', libelle: 'Demander une démonstration' }

  return (
    <header className="sticky top-0 z-40 border-b border-ink-200 bg-surface">
      <div className="mx-auto flex max-w-7xl items-center justify-between gap-6 px-4 py-3 sm:px-6">
        {/* Dans une barre de 56 px, le bloc complet rendrait le nom
            illisible : son rapport est de 2,5:1, et la signature sous le nom
            devient une bouillie grise. L'embleme porte donc l'identite, et le
            nom est du TEXTE — net a toute taille, selectionnable, lu par un
            lecteur d'ecran. Le bloc complet, lui, sert la ou il y a de la
            place : le panneau de connexion et le pied de page. */}
        <Link to="/" className="shrink-0 rounded-sm">
          <Logo taille="size-9" />
        </Link>

        <nav aria-label="Sections du site" className="hidden items-center gap-6 lg:flex">
          {NAV.map((entree) => (
            <NavLink
              key={entree.href}
              to={entree.href}
              className={({ isActive }) =>
                `t-menu transition-smooth border-b-2 pb-0.5 ${
                  isActive
                    ? 'border-brand-600 text-ink-900'
                    : 'border-transparent text-ink-600 hover:text-ink-900'
                }`
              }
            >
              {entree.label}
            </NavLink>
          ))}
        </nav>

        <div className="hidden items-center gap-4 sm:flex">
          {!connecte && (
            <Link to="/connexion" className="t-menu text-ink-600 hover:text-ink-900">
              Se connecter
            </Link>
          )}
          <Link
            to={lienPrincipal.vers}
            className="transition-smooth rounded-md bg-brand-600 px-4 py-2 text-sm font-semibold text-white hover:bg-brand-700"
          >
            {lienPrincipal.libelle}
          </Link>
        </div>

        <button
          type="button"
          onClick={() => setOuvert((v) => !v)}
          aria-expanded={ouvert}
          aria-label={ouvert ? 'Fermer le menu' : 'Ouvrir le menu'}
          className="rounded-sm p-2 text-ink-700 lg:hidden"
        >
          {ouvert ? <X className="size-5" /> : <Menu className="size-5" />}
        </button>
      </div>

      {ouvert && (
        <div className="border-t border-ink-200 bg-surface px-4 py-3 lg:hidden">
          <nav aria-label="Menu" className="flex flex-col">
            {NAV.map((entree) => (
              <Link
                key={entree.href}
                to={entree.href}
                className="ligne-liste t-menu py-3 text-ink-800"
              >
                {entree.label}
              </Link>
            ))}
            <div className="mt-3 flex flex-col gap-2 border-t border-ink-200 pt-3">
              {!connecte && (
                <Link
                  to="/connexion"
                  className="rounded-md border border-ink-200 px-4 py-2.5 text-center text-sm font-medium text-ink-800"
                >
                  Se connecter
                </Link>
              )}
              <Link
                to={lienPrincipal.vers}
                className="rounded-md bg-brand-600 px-4 py-2.5 text-center text-sm font-semibold text-white"
              >
                {lienPrincipal.libelle}
              </Link>
            </div>
          </nav>
        </div>
      )}
    </header>
  )
}

/**
 * Le pied de page est sur le BÂTI : c'est le bas du pupitre, le même graphite
 * que le rail de l'application. Il ferme la page sur la matière du produit
 * plutôt que sur un aplat gris de plus.
 */
function PiedDePage() {
  return (
    <footer className="sur-bati">
      <div className="mx-auto grid max-w-7xl gap-10 px-4 py-14 sm:px-6 sm:grid-cols-2 lg:grid-cols-4">
        <div className="lg:col-span-2">
          <LogoComplet className="w-56" hauteur="h-auto" />
          <p className="mt-4 max-w-sm text-sm leading-relaxed text-craie-douce">
            {FOOTER.description}
          </p>
          <p className="mt-3 max-w-sm text-xs text-craie-douce">{FOOTER.legalNote}</p>
        </div>
        {FOOTER.columns.map((colonne) => (
          <div key={colonne.title}>
            <h2 className="t-legende text-craie-douce">{colonne.title}</h2>
            <ul className="mt-3 space-y-2.5">
              {colonne.links.map((lien) => (
                <li key={lien.label}>
                  <Link
                    to={lien.href}
                    className="transition-smooth text-sm text-craie-douce hover:text-craie"
                  >
                    {lien.label}
                  </Link>
                </li>
              ))}
            </ul>
          </div>
        ))}
      </div>
      <div className="border-t border-bati-600">
        <div className="mx-auto flex max-w-7xl flex-wrap items-center justify-between gap-3 px-4 py-5 text-xs text-craie-douce sm:px-6">
          <p>
            © {new Date().getFullYear()} {SITE.name}
          </p>
          <p className="n">{SITE.contactEmail}</p>
        </div>
      </div>
    </footer>
  )
}

export default function MarketingLayout({ children, bandeau = null }) {
  const { hash, pathname } = useLocation()

  // Ancre profonde (arrivée depuis le pied de page d'une autre page) : le
  // navigateur ne défile pas tout seul quand la cible est montée après coup.
  useEffect(() => {
    if (!hash) {
      // jsdom déclare `scrollTo` mais lève « Not implemented » : sans ce
      // filet, chaque test de page marketing crache une trace d'erreur qui
      // n'en est pas une, et le vrai bruit se perd dedans.
      try {
        window.scrollTo(0, 0)
      } catch {
        /* environnement sans défilement */
      }
      return
    }
    document.querySelector(hash)?.scrollIntoView({ behavior: 'smooth', block: 'start' })
  }, [hash, pathname])

  return (
    <div className="flex min-h-screen flex-col bg-canvas">
      <a
        href="#contenu"
        className="lecture-seule focus:absolute focus:left-4 focus:top-4 focus:z-50 focus:h-auto focus:w-auto focus:rounded-md focus:bg-brand-600 focus:px-4 focus:py-2 focus:text-sm focus:text-white focus:[clip-path:none]"
      >
        Aller au contenu
      </a>
      <Entete />
      {bandeau}
      <main id="contenu" className="flex-1">
        {children}
      </main>
      <PiedDePage />
    </div>
  )
}
