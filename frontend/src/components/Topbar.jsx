import { Menu } from 'lucide-react'
import { useLocation } from 'react-router-dom'
import { pageTitleFor } from '../config/navigation'
import { EXECUTIVE, TECHNICAL, useDisplayProfile } from '../context/useDisplayProfile'

const PROFILS = [
  { value: EXECUTIVE, label: 'Dirigeant' },
  { value: TECHNICAL, label: 'Technique' },
]

/**
 * Le sélecteur de profil d'affichage (V2-5, ADR-031).
 *
 * Dans la barre du haut et non dans une page de réglages : la consigne est
 * qu'il se change **à tout moment**, et un réglage qu'il faut aller chercher
 * dans un menu ne se change jamais. Le dirigeant qui bute sur un mot bascule
 * en un clic, sans quitter l'écran qu'il est en train de lire.
 */
function ProfileSwitch() {
  const { profile, setProfile } = useDisplayProfile()

  return (
    <div
      className="flex items-center gap-1 rounded-full border border-ink-200 bg-canvas p-0.5"
      role="group"
      aria-label="Profil d’affichage"
    >
      {PROFILS.map((option) => (
        <button
          key={option.value}
          type="button"
          onClick={() => setProfile(option.value)}
          aria-pressed={profile === option.value}
          title={
            option.value === EXECUTIVE
              ? 'Vocabulaire courant, détails techniques repliés'
              : 'Champs bruts dépliés, explications resserrées'
          }
          className={`transition-smooth rounded-full px-2.5 py-1 text-xs ${
            profile === option.value
              ? 'bg-brand-600 text-white'
              : 'text-ink-500 hover:text-brand-600'
          }`}
        >
          {option.label}
        </button>
      ))}
    </div>
  )
}

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
      <div className="ml-auto">
        <ProfileSwitch />
      </div>
    </header>
  )
}
