import { useLayoutEffect, useRef, useState } from 'react'

/**
 * UNE AIGUILLE QUI SE POSE — le chiffre rejoint sa valeur, dépasse d'un
 * cheveu, se stabilise.
 *
 * Le mécanisme vient de `number-ticker` du MCP Magic UI. Ce qui en est gardé :
 * l'idée d'un ressort plutôt qu'une interpolation linéaire, et le départ au
 * moment où l'élément entre dans le champ de vision. Ce qui change :
 *
 * - la version d'origine dépend de `motion` (framer-motion), une trentaine de
 *   kilo-octets compressés pour animer un nombre. Le projet a un budget de
 *   performance et une exigence Green IT : le ressort tient en vingt lignes
 *   de `requestAnimationFrame` ;
 * - la valeur finale est rendue DÈS LE PREMIER RENDU dans le DOM. Un chiffre
 *   qui n'existe qu'à la fin d'une animation n'existe pas pour un robot
 *   d'indexation, pour une capture pleine hauteur, ni pour quelqu'un qui
 *   arrive au clavier. L'animation part de zéro et y revient ; elle n'est
 *   jamais la condition de l'affichage.
 *
 * Employé une seule fois par surface : c'est le moment d'auteur, pas un
 * effet qu'on saupoudre.
 */

const DUREE = 1100

function mouvementDoux(t) {
  // Sortie exponentielle : très rapide au début, longue arrivée. Le ressort
  // sans le rebond, qui sur un score se lirait comme une hésitation.
  return 1 - 2 ** (-10 * t)
}

export default function ChiffreAnime({ valeur, decimales = 0, className = '', ...reste }) {
  // `Number(null)` vaut 0, et `Number('')` aussi : sans ce filtre, une absence
  // de mesure s'afficherait comme un score de zéro. Un score de zéro et un
  // score inconnu ne veulent pas dire la même chose du tout.
  const cible = valeur === null || valeur === undefined || valeur === '' ? NaN : Number(valeur)
  const reference = useRef(null)
  const [affiche, setAffiche] = useState(cible)

  // `useLayoutEffect` et non `useEffect` : la remise à zéro doit avoir lieu
  // AVANT que le navigateur ne peigne. Avec `useEffect`, on voit le chiffre
  // juste pendant une image, puis un saut à zéro — le pire des deux mondes.
  useLayoutEffect(() => {
    if (!Number.isFinite(cible)) return undefined

    const element = reference.current
    if (!element) return undefined

    const sansMouvement =
      typeof window.matchMedia === 'function' &&
      window.matchMedia('(prefers-reduced-motion: reduce)').matches
    if (sansMouvement) {
      setAffiche(cible)
      return undefined
    }

    let image = 0
    let observateur = null

    const lancer = () => {
      setAffiche(0)
      const debut = performance.now()
      const avancer = (maintenant) => {
        const t = Math.min(1, (maintenant - debut) / DUREE)
        setAffiche(cible * mouvementDoux(t))
        if (t < 1) image = requestAnimationFrame(avancer)
        else setAffiche(cible)
      }
      image = requestAnimationFrame(avancer)
    }

    // Sans IntersectionObserver, on n'anime pas : on ne sait pas si l'élément
    // est regardé, et un compteur qui démarre hors du champ se termine avant
    // qu'on arrive dessus. Pas d'observateur, pas d'animation, la bonne valeur
    // — c'est aussi ce qui garantit qu'un rendu hors navigateur (test, capture
    // sans JavaScript complet) montre le chiffre juste.
    if (typeof IntersectionObserver !== 'function') {
      setAffiche(cible)
    } else {
      // Déjà dans le champ au montage : on part avant la peinture, sinon on
      // voit le chiffre juste puis un saut à zéro.
      const cadre = element.getBoundingClientRect()
      if (cadre.top < window.innerHeight && cadre.bottom > 0) {
        lancer()
        return () => cancelAnimationFrame(image)
      }
      observateur = new IntersectionObserver(
        (entrees) => {
          if (entrees.some((entree) => entree.isIntersecting)) {
            observateur.disconnect()
            lancer()
          }
        },
        { threshold: 0.2 }
      )
      observateur.observe(element)
    }

    return () => {
      cancelAnimationFrame(image)
      observateur?.disconnect()
    }
  }, [cible])

  if (!Number.isFinite(cible)) {
    return (
      <span className={className} {...reste}>
        —
      </span>
    )
  }

  return (
    <span ref={reference} className={className} {...reste}>
      {affiche.toLocaleString('fr-FR', {
        minimumFractionDigits: decimales,
        maximumFractionDigits: decimales,
      })}
    </span>
  )
}
