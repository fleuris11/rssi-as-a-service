/**
 * UNE ZONE QUI DÉFILE HORIZONTALEMENT, ATTEIGNABLE AU CLAVIER.
 *
 * Un `overflow-x-auto` nu se fait défiler à la souris et au doigt, mais pas
 * au clavier : rien n'y prend le focus, donc les flèches n'ont aucun effet et
 * les colonnes de droite d'un tableau deviennent inatteignables. axe-core le
 * classe « serious » (`scrollable-region-focusable`), et il a raison : c'est
 * du contenu réellement inaccessible, pas une nuance de balisage.
 *
 * `tabIndex={0}` suffit à le rendre focalisable ; le libellé dit ce qu'on
 * vient d'atteindre, sans quoi le focus tombe sur un objet anonyme.
 */
export default function Defilement({ libelle = 'Tableau, défilement horizontal', className = '', children }) {
  return (
    <div tabIndex={0} role="group" aria-label={libelle} className={`overflow-x-auto ${className}`}>
      {children}
    </div>
  )
}
