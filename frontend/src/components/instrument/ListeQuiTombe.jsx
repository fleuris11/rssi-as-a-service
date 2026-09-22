import { Children } from 'react'

/**
 * LES ALERTES QUI TOMBENT — la démonstration que quelque chose tourne.
 *
 * Le mécanisme vient de `animated-list` du MCP Magic UI : des éléments qui
 * arrivent l'un après l'autre. Trois changements, et ils comptent :
 *
 * - la version d'origine dépend de `motion` (framer-motion) et pilote
 *   l'apparition depuis un état React. Ici il n'y a NI dépendance NI état :
 *   un décalage d'animation CSS par rang suffit. Moins de JavaScript à
 *   charger, et rien à remettre en ordre au remontage ;
 * - la version d'origine **boucle indéfiniment**. Une liste qui rejoue sans
 *   fin est du bruit sur une page qu'on lit : celle-ci se pose et s'arrête ;
 * - aucun élément n'est retiré du DOM ni masqué en attendant son tour.
 *   `.apparition` est une animation, pas un état : sans JavaScript, sous
 *   `prefers-reduced-motion`, dans une capture pleine hauteur ou pour un
 *   lecteur d'écran, la liste entière est là dès le premier rendu.
 *
 * L'ordre visuel est inversé — les alertes récentes remontent — mais l'ordre
 * du DOM reste chronologique, donc l'ordre de lecture aussi.
 */
export default function ListeQuiTombe({ children, delai = 700, className = '' }) {
  const elements = Children.toArray(children)

  return (
    <ul className={`flex flex-col-reverse gap-2 ${className}`}>
      {elements.map((element, rang) => (
        <li key={element.key ?? rang} className="apparition" style={{ animationDelay: `${rang * delai}ms` }}>
          {element}
        </li>
      ))}
    </ul>
  )
}
