import { Eye, Radar, ShieldCheck } from 'lucide-react'
import Badge from './ui/Badge'
import Card from './ui/Card'

// Visuellement distinct de la liste des fuites (bordure et fond "veille",
// icône radar, pas de rouge) : c'est du pré-incident — un signal sur
// l'exposition publique du tenant, pas le constat qu'une donnée a fuité.
// Le rouge reste réservé aux compromissions avérées, pour ne pas habituer
// le dirigeant à ignorer les vraies alertes.
const URGENCY_LABEL = { high: 'À traiter', info: 'Pour information' }
const URGENCY_VARIANT = { high: 'warning', info: 'neutral' }

function SignalRow({ signal }) {
  return (
    <li className="rounded-md border border-ink-200/70 bg-surface px-4 py-3">
      <div className="flex flex-wrap items-center gap-2">
        <p className="text-sm font-medium text-ink-800">{signal.label}</p>
        <Badge variant={URGENCY_VARIANT[signal.urgency] || 'neutral'} dot>
          {URGENCY_LABEL[signal.urgency] || signal.urgency}
        </Badge>
        {signal.count > 1 && (
          <span className="text-xs text-ink-500">{signal.count} détections</span>
        )}
      </div>
      <ul className="mt-1.5 flex flex-wrap gap-x-3 gap-y-1">
        {signal.items.map((item) => (
          <li key={item.id} className="font-mono text-xs text-ink-600">
            {item.detail}
          </li>
        ))}
      </ul>
      <p className="mt-2 text-sm leading-relaxed text-ink-700">{signal.plain_language}</p>
    </li>
  )
}

export default function PreIncidentRadar({ summary }) {
  if (!summary) return null
  const isCalm = summary.total === 0

  return (
    <Card className="border-brand-200 bg-brand-50/40">
      <div className="mb-4 flex items-start gap-3">
        <div className="mt-0.5 flex size-9 shrink-0 items-center justify-center rounded-md bg-brand-100 text-brand-800">
          {isCalm ? (
            <ShieldCheck className="size-5" aria-hidden="true" />
          ) : (
            <Radar className="size-5" aria-hidden="true" />
          )}
        </div>
        <div>
          <h2 className="font-display text-lg font-semibold text-ink-900">
            Signaux avant-coureurs
          </h2>
          <p className="mt-0.5 text-sm text-ink-600">
            Ce que l’on observe sur votre exposition publique — avant qu’une fuite ne se produise.
          </p>
        </div>
      </div>

      {isCalm ? (
        <div className="flex items-start gap-2 rounded-md bg-ok-subtle px-4 py-3">
          <Eye className="mt-0.5 size-4 shrink-0 text-ok-strong" aria-hidden="true" />
          <p className="text-sm text-ok-strong">
            Aucun signal avant-coureur détecté — votre exposition publique est calme. Nous
            continuons à surveiller en permanence.
          </p>
        </div>
      ) : (
        <ul className="space-y-3">
          {summary.signals.map((signal) => (
            <SignalRow key={signal.signal_type} signal={signal} />
          ))}
        </ul>
      )}
    </Card>
  )
}
