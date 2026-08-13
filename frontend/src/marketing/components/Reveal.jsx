import { useEffect, useRef, useState } from 'react'

/**
 * Apparition au défilement, discrète : translation de quelques pixels et
 * fondu, une seule fois.
 *
 * Respecte prefers-reduced-motion en ne faisant RIEN plutôt qu'en animant
 * plus lentement — le contenu est simplement là. Sans cette garde, un
 * visiteur sensible au mouvement subirait une animation à chaque section.
 *
 * IntersectionObserver plutôt qu'un écouteur de défilement : pas de calcul à
 * chaque pixel parcouru, et l'observateur se débranche dès l'élément vu.
 */
export default function Reveal({ children, delay = 0, className = '', as: Tag = 'div' }) {
  const ref = useRef(null)
  const [visible, setVisible] = useState(false)

  useEffect(() => {
    const prefersReducedMotion = window.matchMedia?.(
      '(prefers-reduced-motion: reduce)'
    )?.matches
    if (prefersReducedMotion || typeof IntersectionObserver === 'undefined') {
      setVisible(true)
      return undefined
    }

    const element = ref.current
    if (!element) return undefined

    const observer = new IntersectionObserver(
      ([entry]) => {
        if (entry.isIntersecting) {
          setVisible(true)
          observer.disconnect()
        }
      },
      { threshold: 0.12, rootMargin: '0px 0px -40px 0px' }
    )
    observer.observe(element)

    // Filet de sécurité : au bout de 2 s, on affiche quoi qu'il arrive.
    // L'état initial d'une apparition est `opacity-0` — si l'observateur ne
    // se déclenchait jamais (saut direct en bas de page, capture pleine
    // hauteur, robot qui exécute le JS sans faire défiler), le contenu
    // resterait invisible pour de bon. Sur une page dont l'objet est
    // justement d'être lue, c'est un mode de défaillance inacceptable :
    // l'animation est un agrément, la lisibilité est une exigence.
    // Sans effet perceptible pour un visiteur qui fait défiler normalement,
    // l'observateur se déclenchant alors bien avant ce délai.
    const failsafe = setTimeout(() => setVisible(true), 2000)

    return () => {
      observer.disconnect()
      clearTimeout(failsafe)
    }
  }, [])

  // `as` permet de conserver la sémantique du parent : glisser une <div>
  // entre un <ol> et ses <li> casse la liste pour un lecteur d'écran (axe le
  // signale en "serious"). Les listes passent donc `as="li"`.
  return (
    <Tag
      ref={ref}
      className={`transition-all duration-700 ease-out motion-reduce:transition-none ${
        visible ? 'translate-y-0 opacity-100' : 'translate-y-4 opacity-0'
      } ${className}`}
      style={visible && delay ? { transitionDelay: `${delay}ms` } : undefined}
    >
      {children}
    </Tag>
  )
}
