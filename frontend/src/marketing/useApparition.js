import { useEffect } from 'react'

/**
 * LES APPARITIONS AU DÉFILEMENT, posées une fois pour toute une page.
 *
 * Trois garanties, et chacune répond à un défaut classique de ce mécanisme :
 *
 * 1. **Rien n'est masqué au départ.** L'élément est visible ; la classe
 *    `.apparition` n'est ajoutée qu'au moment où il entre dans le champ, et
 *    l'animation part alors de son état final. Un contenu laissé à
 *    `opacity: 0` en attendant un observateur disparaît pour un robot
 *    d'indexation, une impression et une capture pleine hauteur. C'est
 *    exactement le défaut qui avait fait disparaître la grille tarifaire.
 * 2. **Ça ne se déclenche qu'une fois**, puis l'observateur se débranche :
 *    un élément qui rejoue son entrée à chaque passage est du bruit.
 * 3. **`prefers-reduced-motion` coupe tout**, avant même d'observer quoi que
 *    ce soit.
 *
 * Employé sur les MÉDIAS et les blocs de chiffres, jamais sur chaque section :
 * une entrée identique partout se lit comme un gabarit, pas comme une
 * intention.
 */
export function useApparition(dependance) {
  useEffect(() => {
    if (
      typeof window.matchMedia === 'function' &&
      window.matchMedia('(prefers-reduced-motion: reduce)').matches
    ) {
      return undefined
    }
    if (typeof IntersectionObserver !== 'function') return undefined

    const cibles = document.querySelectorAll('[data-apparition]:not([data-apparue])')
    if (cibles.length === 0) return undefined

    const observateur = new IntersectionObserver(
      (entrees) => {
        for (const entree of entrees) {
          if (!entree.isIntersecting) continue
          const element = entree.target
          element.dataset.apparue = 'oui'
          // Le décalage fait avancer les éléments d'un même groupe l'un après
          // l'autre plutôt que tous ensemble : c'est ce qui distingue une
          // arrivée d'un clignotement.
          element.style.animationDelay = `${Number(element.dataset.apparition) * 90}ms`
          element.classList.add('apparition')
          observateur.unobserve(element)
        }
      },
      { threshold: 0.15, rootMargin: '0px 0px -8% 0px' }
    )

    cibles.forEach((cible) => observateur.observe(cible))
    return () => observateur.disconnect()
  }, [dependance])
}
