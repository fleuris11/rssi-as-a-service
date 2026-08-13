import { useEffect, useRef, useState } from 'react'

/**
 * Schéma du fonctionnement en 4 étapes, animé au défilement : chaque nœud
 * apparaît à son tour, relié au suivant par un trait qui se trace.
 *
 * L'animation est purement décorative — le SVG est `aria-hidden`, le contenu
 * lisible étant la liste d'étapes rendue à côté par HowItWorks. Sous
 * prefers-reduced-motion, tout est affiché d'emblée, sans transition.
 */
const NODES = [
  { x: 60, label: 'Vos actifs' },
  { x: 220, label: 'Neuf sources' },
  { x: 380, label: 'Alerte claire' },
  { x: 540, label: 'Suivi' },
]

export default function FlowDiagram() {
  const ref = useRef(null)
  const [step, setStep] = useState(-1)

  useEffect(() => {
    const reduced = window.matchMedia?.('(prefers-reduced-motion: reduce)')?.matches
    if (reduced || typeof IntersectionObserver === 'undefined') {
      setStep(NODES.length)
      return undefined
    }

    const element = ref.current
    if (!element) return undefined

    let timers = []
    const observer = new IntersectionObserver(
      ([entry]) => {
        if (!entry.isIntersecting) return
        observer.disconnect()
        clearTimeout(failsafe)
        timers = NODES.map((_, index) =>
          setTimeout(() => setStep(index), 220 * index)
        )
      },
      { threshold: 0.35 }
    )
    observer.observe(element)

    // Même filet de sécurité que Reveal : les nœuds démarrent à opacité nulle,
    // un observateur qui ne se déclenche pas laisserait un schéma vide au
    // milieu de la page. Au bout de 2 s, on affiche tout d'un coup.
    const failsafe = setTimeout(() => setStep(NODES.length), 2000)

    return () => {
      observer.disconnect()
      clearTimeout(failsafe)
      timers.forEach(clearTimeout)
    }
  }, [])

  // Le SVG se met à l'échelle via son viewBox au lieu d'être placé dans un
  // conteneur défilant : une zone qui défile horizontalement doit être
  // atteignable au clavier (axe, "scrollable-region-focusable"), ce qui
  // n'aurait aucun sens pour un schéma purement décoratif. Le contenu
  // lisible est la liste d'étapes rendue juste en dessous.
  return (
    <div ref={ref} className="w-full">
      <svg
        viewBox="0 0 600 130"
        className="mx-auto h-auto w-full max-w-3xl"
        aria-hidden="true"
        focusable="false"
      >
        <defs>
          <linearGradient id="flow-line" x1="0" y1="0" x2="1" y2="0">
            <stop offset="0%" className="[stop-color:var(--color-brand-400,#9db4d8)]" />
            <stop offset="100%" className="[stop-color:var(--color-brand-700,#2c4a7c)]" />
          </linearGradient>
        </defs>

        {NODES.slice(0, -1).map((node, index) => {
          const next = NODES[index + 1]
          const drawn = step > index
          return (
            <line
              key={`line-${node.x}`}
              x1={node.x + 30}
              y1={52}
              x2={next.x - 30}
              y2={52}
              stroke="url(#flow-line)"
              strokeWidth="2"
              strokeDasharray="100"
              strokeDashoffset={drawn ? 0 : 100}
              className="transition-[stroke-dashoffset] duration-500 ease-out motion-reduce:transition-none"
            />
          )
        })}

        {NODES.map((node, index) => {
          const shown = step >= index
          return (
            <g
              key={node.label}
              className="transition-opacity duration-500 motion-reduce:transition-none"
              opacity={shown ? 1 : 0}
            >
              <circle
                cx={node.x}
                cy={52}
                r="26"
                className="fill-brand-50 stroke-brand-300"
                strokeWidth="1.5"
              />
              <text
                x={node.x}
                y={58}
                textAnchor="middle"
                className="fill-brand-800 font-display text-[17px] font-semibold"
              >
                {index + 1}
              </text>
              <text
                x={node.x}
                y={104}
                textAnchor="middle"
                className="fill-ink-600 text-[12px]"
              >
                {node.label}
              </text>
            </g>
          )
        })}
      </svg>
    </div>
  )
}
