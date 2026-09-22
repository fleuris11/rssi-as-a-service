import { Menu } from 'lucide-react'
import { useLocation } from 'react-router-dom'
import { pageTitleFor } from '../config/navigation'
import { EXECUTIVE, TECHNICAL, useDisplayProfile } from '../context/useDisplayProfile'
import NotificationBell from './NotificationBell'

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
      className="flex items-center rounded-sm border border-ink-300 bg-creuse p-0.5"
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
          className={`transition-smooth rounded-sm px-3 py-1 text-xs font-semibold ${
            profile === option.value
              ? 'bg-surface text-ink-900 shadow-soft'
              : 'text-ink-600 hover:text-ink-900'
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
    <header className="sticky top-0 z-30 flex h-14 items-center gap-3 border-b border-ink-200 bg-surface px-4 sm:px-6 lg:px-8">
      <button
        type="button"
        onClick={onOpenMenu}
        aria-label="Ouvrir le menu"
        className="transition-smooth -ml-1 rounded-sm p-1.5 text-ink-600 hover:bg-creuse lg:hidden"
      >
        <Menu className="size-5" aria-hidden="true" />
      </button>
      {/* PAS un <h1> : chaque page rend déjà le sien. C'est un repère de
          position — « où suis-je » — pas le titre du document. Deux <h1> au
          même texte est à la fois une faute d'accessibilité et une ambiguïté
          pour les tests.

          Le fil d'adresse est l'une des quatre disciplines empruntées aux
          mondes adverses du tirage de direction : dans un magazine télétexte,
          chaque page porte son numéro, visible en permanence. */}
      <p className="flex min-w-0 items-baseline gap-2">
        <span className="t-legende hidden sm:inline">Écran</span>
        <span className="truncate text-sm font-semibold text-ink-900">{title}</span>
      </p>
      <div className="ml-auto flex items-center gap-2">
        {/* Lot C, point 20 : la cloche, sur chaque écran de l'application. */}
        <NotificationBell />
        <ProfileSwitch />
      </div>
    </header>
  )
}
