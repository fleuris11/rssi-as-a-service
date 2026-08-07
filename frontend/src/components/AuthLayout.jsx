import { Gauge, Radar, ShieldCheck } from 'lucide-react'

const BENEFITS = [
  { icon: Gauge, text: 'Diagnostiquez votre maturité cyber avec le référentiel ANSSI' },
  { icon: ShieldCheck, text: 'Suivez un plan d’action priorisé, sans jargon technique' },
  { icon: Radar, text: 'Recevez une météo cyber quotidienne sur vos actifs' },
]

export default function AuthLayout({ children }) {
  return (
    <div className="flex min-h-screen">
      <div className="hidden w-[42%] flex-col justify-between bg-brand-950 p-10 text-white lg:flex">
        <div className="flex items-center gap-2.5">
          <div className="flex size-8 shrink-0 items-center justify-center rounded-md bg-accent-600 font-display text-sm font-bold text-white">
            R
          </div>
          <span className="font-display text-base font-semibold tracking-tight">
            RSSI as a Service
          </span>
        </div>

        <div>
          <p className="font-display text-3xl font-medium italic text-brand-100">
            La cybersécurité, enfin claire pour les dirigeants de PME.
          </p>
          <ul className="mt-8 space-y-4">
            {BENEFITS.map((benefit) => (
              <li key={benefit.text} className="flex items-start gap-3 text-sm text-brand-200">
                <benefit.icon className="mt-0.5 size-5 shrink-0 text-accent-400" aria-hidden="true" />
                {benefit.text}
              </li>
            ))}
          </ul>
        </div>

        <p className="text-xs text-brand-300">© {new Date().getFullYear()} RSSI as a Service</p>
      </div>

      <div className="flex flex-1 flex-col items-center justify-center bg-canvas px-6 py-12">
        <div className="mb-6 flex items-center gap-2.5 lg:hidden">
          <div className="flex size-8 shrink-0 items-center justify-center rounded-md bg-accent-600 font-display text-sm font-bold text-white">
            R
          </div>
          <span className="font-display text-base font-semibold tracking-tight text-ink-900">
            RSSI as a Service
          </span>
        </div>
        <div className="w-full max-w-sm">{children}</div>
      </div>
    </div>
  )
}
