// A calm, single-purpose ring gauge — no animation library: a plain SVG
// stroke-dasharray driven by CSS transition, so it "fills in" once on
// mount without any gratuitous motion afterwards (mission: "aucune
// animation gratuite").
const SIZE = 128
const STROKE = 10
const RADIUS = (SIZE - STROKE) / 2

function ringColor(score) {
  if (score === null || score === undefined) return 'var(--color-ink-300)'
  if (score >= 70) return 'var(--color-ok-strong)'
  if (score >= 40) return 'var(--color-warning-strong)'
  return 'var(--color-critical-strong)'
}

export default function ScoreRing({ score, size = SIZE, label }) {
  const scale = size / SIZE
  const radius = RADIUS * scale
  const stroke = STROKE * scale
  const circumference = 2 * Math.PI * radius
  const progress = score === null || score === undefined ? 0 : Math.max(0, Math.min(100, score))
  const offset = circumference * (1 - progress / 100)

  return (
    <div className="relative inline-flex items-center justify-center" style={{ width: size, height: size }}>
      <svg width={size} height={size} viewBox={`0 0 ${size} ${size}`} className="-rotate-90">
        <circle
          cx={size / 2}
          cy={size / 2}
          r={radius}
          fill="none"
          stroke="var(--color-ink-100)"
          strokeWidth={stroke}
        />
        <circle
          cx={size / 2}
          cy={size / 2}
          r={radius}
          fill="none"
          stroke={ringColor(score)}
          strokeWidth={stroke}
          strokeLinecap="round"
          strokeDasharray={circumference}
          strokeDashoffset={offset}
          style={{ transition: 'stroke-dashoffset 600ms cubic-bezier(0.4, 0, 0.2, 1)' }}
        />
      </svg>
      <div className="absolute flex flex-col items-center justify-center">
        <span className="font-display text-2xl font-semibold text-ink-900">
          {score === null || score === undefined ? '—' : Math.round(score)}
        </span>
        {label && <span className="text-[11px] text-ink-500">{label}</span>}
      </div>
    </div>
  )
}
