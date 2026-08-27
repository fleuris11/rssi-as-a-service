import { useEffect, useRef, useState } from 'react'

/**
 * Apparition au défilement, discrète : translation de quelques pixels et
 * fondu, une seule fois.
 *
 * **Le contenu ne dépend JAMAIS de l'animation pour être visible.**
 *
 * C'est une inversion par rapport à la première version, et elle corrige un
 * défaut réel. Auparavant l'état initial était `opacity-0`, et un minuteur de
 * 2 s servait de filet : si l'observateur ne se déclenchait pas, le contenu
 * finissait par apparaître. Ce filet ne tenait pas.
 *
 * Constaté en capture pleine hauteur, sans défilement : la grille tarifaire
 * était **entièrement absente de la page**. Les cartes existaient bien dans le
 * DOM — elles étaient à `opacity-0`. La raison : elles sont rendues après la
 * réponse de l'API, donc montées tardivement, donc leur minuteur de 2 s
 * repartait de zéro à chaque remontage. Un filet dont le compte à rebours
 * redémarre n'est pas un filet.
 *
 * La correction ne consiste pas à raccourcir le délai — ce serait déplacer le
 * problème — mais à **renverser l'état par défaut** : l'élément est visible,
 * et l'entrée dans le champ de vision ne fait qu'y *ajouter* une animation.
 * Si l'observateur ne se déclenche jamais (défilement direct en bas de page,
 * capture pleine hauteur, robot d'indexation, impression, navigateur sans
 * IntersectionObserver), il ne se passe rien de plus : le contenu est là.
 *
 * On ne peut donc plus rendre du contenu invisible en cassant l'animation.
 * C'est la seule garantie qui vaille sur une page dont l'objet est d'être lue.
 *
 * `prefers-reduced-motion` est respecté par la feuille de style (`.apparition`
 * n'anime rien), et la garde JS reste : inutile d'observer quoi que ce soit
 * pour un visiteur qui ne veut pas de mouvement.
 *
 * IntersectionObserver plutôt qu'un écouteur de défilement : pas de calcul à
 * chaque pixel parcouru, et l'observateur se débranche dès l'élément vu.
 */
export default function Reveal({ children, delay = 0, className = '', as: Tag = 'div' }) {
  const ref = useRef(null)
  const [anime, setAnime] = useState(false)

  useEffect(() => {
    const prefersReducedMotion = window.matchMedia?.('(prefers-reduced-motion: reduce)')?.matches
    if (prefersReducedMotion || typeof IntersectionObserver === 'undefined') return undefined

    const element = ref.current
    if (!element) return undefined

    const observer = new IntersectionObserver(
      ([entry]) => {
        if (entry.isIntersecting) {
          setAnime(true)
          observer.disconnect()
        }
      },
      { threshold: 0.12, rootMargin: '0px 0px -40px 0px' }
    )
    observer.observe(element)
    return () => observer.disconnect()
  }, [])

  // `as` permet de conserver la sémantique du parent : glisser une <div>
  // entre un <ol> et ses <li> casse la liste pour un lecteur d'écran (axe le
  // signale en "serious"). Les listes passent donc `as="li"`.
  return (
    <Tag
      ref={ref}
      className={`${anime ? 'apparition' : ''} ${className}`}
      style={anime && delay ? { animationDelay: `${delay}ms` } : undefined}
    >
      {children}
    </Tag>
  )
}
