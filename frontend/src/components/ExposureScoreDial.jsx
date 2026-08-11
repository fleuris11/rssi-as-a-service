// Score d'exposition : un chiffre, son niveau, et l'accès au « pourquoi ».
// Le détail du calcul (ADR-016) est affichable à la demande — un score qu'on
// ne peut pas justifier devant un client ne vaut rien.
const LEVEL_STYLES = {
  calme: { ring: 'text-ok-strong', bg: 'bg-ok-subtle', text: 'text-ok-strong' },
  a_surveiller: { ring: 'text-warning-strong', bg: 'bg-warning-subtle', text: 'text-warning-strong' },
  preoccupant: { ring: 'text-accent-700', bg: 'bg-accent-100', text: 'text-accent-900' },
  critique: { ring: 'text-critical-strong', bg: 'bg-critical-subtle', text: 'text-critical-strong' },
}

export default function ExposureScoreDial({ score, level, levelLabel }) {
  const style = LEVEL_STYLES[level] || LEVEL_STYLES.calme
  const circumference = 2 * Math.PI * 20
  const filled = (Math.min(100, Math.max(0, score)) / 100) * circumference

  return (
    <div className="flex items-center gap-3">
      <div className="relative size-14 shrink-0">
        <svg viewBox="0 0 48 48" className="size-full -rotate-90" aria-hidden="true">
          <circle cx="24" cy="24" r="20" fill="none" strokeWidth="4" className="stroke-ink-200" />
          <circle
            cx="24"
            cy="24"
            r="20"
            fill="none"
            strokeWidth="4"
            strokeLinecap="round"
            strokeDasharray={`${filled} ${circumference}`}
            className={`${style.ring} stroke-current`}
          />
        </svg>
        <span className="absolute inset-0 flex items-center justify-center font-display text-sm font-semibold text-ink-900">
          {score}
        </span>
      </div>
      <span
        className={`rounded-full px-2.5 py-1 text-xs font-medium ${style.bg} ${style.text}`}
      >
        {levelLabel}
      </span>
    </div>
  )
}
