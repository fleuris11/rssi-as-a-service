/**
 * Une pastille d'état.
 *
 * Carrée aux angles adoucis, pas une pilule : l'arrondi complet appartient au
 * monde des étiquettes marketing, pas à celui d'un pupitre. Et elle porte un
 * GLYPHE en plus de sa couleur — l'information ne passe jamais par la teinte
 * seule, ni pour un daltonien, ni sur un PDF en noir et blanc.
 */
const GLYPHES = {
  ok: '●',
  warning: '◐',
  critical: '■',
  neutral: '·',
  accent: '·',
  brand: '·',
}

const VARIANTS = {
  ok: 'bg-ok-subtle text-ok-strong',
  warning: 'bg-warning-subtle text-warning-strong',
  critical: 'bg-critical-subtle text-critical-strong',
  neutral: 'bg-ink-100 text-ink-700',
  accent: 'bg-ink-100 text-ink-800',
  brand: 'bg-brand-100 text-brand-800',
}

export default function Badge({ variant = 'neutral', dot = false, className = '', children }) {
  return (
    <span
      className={`inline-flex items-center gap-1.5 rounded-sm px-2 py-0.5 text-xs font-semibold ${VARIANTS[variant]} ${className}`}
    >
      {/* `dot` reste accepté pour ne rien casser, mais rend un glyphe plutôt
          qu'un rond de couleur : un rond ne se lit pas en noir et blanc. */}
      {dot && (
        <span className="text-[0.625rem] leading-none" aria-hidden="true">
          {GLYPHES[variant]}
        </span>
      )}
      {children}
    </span>
  )
}
