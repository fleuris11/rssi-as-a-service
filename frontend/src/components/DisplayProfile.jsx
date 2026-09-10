import { ChevronDown, ChevronRight } from 'lucide-react'
import { useState } from 'react'
import { useDisplayProfile } from '../context/useDisplayProfile'

/**
 * Les deux primitives du profil d'affichage (V2-5, ADR-031).
 *
 * La règle qu'elles font respecter : **le contenu ne change jamais, seule sa
 * présentation change**. Un détail technique reste dans le DOM dans les deux
 * profils — il est replié en profil dirigeant, déplié en profil technique.
 * Rien n'est retiré, rien n'est réécrit : un même fait reste le même fait, et
 * un dirigeant qui déplie voit exactement ce que voit son prestataire.
 *
 * C'est aussi pour cela que ce sont des composants d'affichage et non des
 * conditions `if (isTechnical)` disséminées : une condition finit toujours
 * par supprimer quelque chose.
 */

export function TechnicalDetail({ summary = 'Détail technique', children, className = '' }) {
  const { isTechnical } = useDisplayProfile()
  const [open, setOpen] = useState(isTechnical)

  const Icone = open ? ChevronDown : ChevronRight
  return (
    <div className={`mt-2 ${className}`}>
      <button
        type="button"
        onClick={() => setOpen((value) => !value)}
        aria-expanded={open}
        className="transition-smooth flex items-center gap-1 text-xs text-ink-500 hover:text-brand-600"
      >
        <Icone className="size-3.5" aria-hidden="true" />
        {summary}
      </button>
      {/* `hidden` plutôt qu'un rendu conditionnel : le contenu existe dans la
          page quel que soit le profil, il est seulement masqué. Un lecteur
          d'écran et une recherche dans la page le retrouvent. */}
      <div hidden={!open} className="mt-2 rounded-md border border-ink-200 bg-canvas p-3 text-xs">
        {children}
      </div>
    </div>
  )
}

/**
 * Un terme technique et sa traduction. En profil dirigeant on lit la
 * traduction, le terme technique suit entre parenthèses ; en profil technique
 * c'est l'inverse.
 *
 * Les deux sont toujours affichés. Masquer le terme technique au dirigeant
 * l'empêcherait de le reconnaître dans le courriel de son prestataire — or
 * c'est précisément le moment où il en a besoin.
 */
export function Term({ code, plain, className = '' }) {
  const { isTechnical } = useDisplayProfile()
  const [devant, derriere] = isTechnical ? [code, plain] : [plain, code]
  return (
    <span className={className}>
      {devant} <span className="text-ink-400">({derriere})</span>
    </span>
  )
}

/**
 * Un bloc d'explication. Toujours présent, mais discret en profil technique :
 * la consigne V2-5 demande que les explications « restent mais ne prennent
 * pas toute la place ».
 */
export function Explanation({ children, className = '' }) {
  const { isTechnical } = useDisplayProfile()
  if (isTechnical) {
    return <p className={`mt-1 text-xs text-ink-400 ${className}`}>{children}</p>
  }
  return (
    <p className={`mt-2 rounded-md bg-brand-50 px-3 py-2 text-sm text-ink-600 ${className}`}>
      {children}
    </p>
  )
}
