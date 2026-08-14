import { Check, ChevronDown } from 'lucide-react'
import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { publicApi } from '../../api/endpoints'
import BrowserFrame from '../components/BrowserFrame'
import ExposureMockup from '../components/ExposureMockup'
import FlowDiagram from '../components/FlowDiagram'
import MarketingLayout from '../components/MarketingLayout'
import Reveal from '../components/Reveal'
import {
  DIFFERENTIATORS,
  FAQ,
  FINAL_CTA,
  HERO,
  HOW_IT_WORKS,
  PRICING,
  PROBLEM,
  TRUST,
} from '../content'
import { ORGANISATION_JSON_LD, useSeo } from '../useSeo'

function Section({ id, children, className = '' }) {
  return (
    <section id={id} className={`px-5 py-20 sm:py-24 ${className}`}>
      <div className="mx-auto max-w-6xl">{children}</div>
    </section>
  )
}

function SectionTitle({ eyebrow, title, subtitle }) {
  return (
    <div className="max-w-2xl">
      {eyebrow && (
        <p className="text-xs font-semibold uppercase tracking-wide text-brand-700">{eyebrow}</p>
      )}
      <h2 className="mt-2 font-display text-2xl font-semibold text-ink-900 sm:text-3xl">{title}</h2>
      {subtitle && <p className="mt-3 text-base leading-relaxed text-ink-600">{subtitle}</p>}
    </div>
  )
}

function Hero() {
  return (
    <div className="relative overflow-hidden border-b border-ink-200/70">
      {/* Décor : dégradé discret et grille légère, en CSS pur. */}
      <div
        aria-hidden="true"
        className="pointer-events-none absolute inset-0 bg-[radial-gradient(60%_50%_at_50%_0%,var(--color-brand-100,#e3eaf6)_0%,transparent_70%)]"
      />
      <div className="relative mx-auto grid max-w-6xl items-center gap-12 px-5 py-20 sm:py-24 lg:grid-cols-[1.05fr_1fr] lg:gap-16">
        <div>
          <Reveal>
            <h1 className="font-display text-3xl font-semibold leading-tight text-ink-900 sm:text-4xl lg:text-[2.75rem]">
              {HERO.title}
            </h1>
          </Reveal>
          <Reveal delay={80}>
            <p className="mt-5 max-w-xl text-lg leading-relaxed text-ink-600">{HERO.subtitle}</p>
          </Reveal>
          <Reveal delay={160}>
            <div className="mt-8 flex flex-wrap gap-3">
              <Link
                to="/demonstration"
                className="transition-smooth rounded-md bg-brand-700 px-5 py-3 text-sm font-medium text-white hover:bg-brand-800 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-brand-600"
              >
                {HERO.primaryCta}
              </Link>
              <Link
                to="/connexion"
                className="transition-smooth rounded-md border border-ink-300 px-5 py-3 text-sm font-medium text-ink-800 hover:bg-ink-50 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-brand-600"
              >
                {HERO.secondaryCta}
              </Link>
            </div>
            <p className="mt-4 text-sm text-ink-500">{HERO.note}</p>
          </Reveal>
        </div>

        <Reveal delay={220}>
          <BrowserFrame caption="Page Exposition — reconstitution de l'interface réelle.">
            <ExposureMockup />
          </BrowserFrame>
        </Reveal>
      </div>
    </div>
  )
}

function Problem() {
  return (
    <Section id="probleme" className="bg-ink-50/50">
      <Reveal>
        <SectionTitle title={PROBLEM.title} />
      </Reveal>
      <div className="mt-10 grid gap-6 md:grid-cols-3">
        {PROBLEM.items.map((item, index) => (
          <Reveal key={item.title} delay={index * 90}>
            <div className="h-full rounded-lg border border-ink-200 bg-surface p-6">
              <span
                aria-hidden="true"
                className="block h-1 w-10 rounded-full bg-brand-600"
              />
              <h3 className="mt-4 font-display text-lg font-semibold text-ink-900">
                {item.title}
              </h3>
              <p className="mt-2.5 text-sm leading-relaxed text-ink-600">{item.body}</p>
            </div>
          </Reveal>
        ))}
      </div>
    </Section>
  )
}

function Differentiators() {
  return (
    <Section id="produit">
      <Reveal>
        <SectionTitle eyebrow="Le produit" title={DIFFERENTIATORS.title} />
      </Reveal>
      <div className="mt-12 space-y-14">
        {DIFFERENTIATORS.items.map((item, index) => (
          <Reveal key={item.id}>
            <article
              className={`grid items-center gap-8 lg:grid-cols-2 lg:gap-14 ${
                index % 2 === 1 ? 'lg:[&>*:first-child]:order-2' : ''
              }`}
            >
              <div>
                <p className="text-xs font-semibold uppercase tracking-wide text-brand-700">
                  {item.eyebrow}
                </p>
                <h3 className="mt-2 font-display text-xl font-semibold text-ink-900 sm:text-2xl">
                  {item.title}
                </h3>
                <p className="mt-3 text-base leading-relaxed text-ink-600">{item.body}</p>
                {item.detail && (
                  <p className="mt-3 border-l-2 border-brand-300 pl-4 text-sm leading-relaxed text-ink-600">
                    {item.detail}
                  </p>
                )}
              </div>

              <div>
                {item.example ? (
                  <div className="rounded-lg border border-ink-200 bg-surface p-5 shadow-soft">
                    <p className="text-xs font-semibold uppercase tracking-wide text-ink-500">
                      {item.example.label}
                    </p>
                    <p className="mt-3 rounded-md bg-ink-50 px-4 py-3 text-sm leading-relaxed text-ink-700">
                      {item.example.meaning}
                    </p>
                    <p className="mt-2.5 rounded-md bg-accent-100/50 px-4 py-3 text-sm leading-relaxed text-accent-900">
                      <span className="font-semibold">À faire : </span>
                      {item.example.action}
                    </p>
                  </div>
                ) : (
                  <DifferentiatorVisual id={item.id} />
                )}
              </div>
            </article>
          </Reveal>
        ))}
      </div>
    </Section>
  )
}

/** Compositions SVG originales — pas de photo, pas d'icône générique. */
function DifferentiatorVisual({ id }) {
  if (id === 'signaux') {
    return (
      <div className="rounded-lg border border-brand-200 bg-brand-50/40 p-6">
        <svg viewBox="0 0 340 150" className="h-auto w-full" aria-hidden="true" focusable="false">
          {[0, 1, 2].map((ring) => (
            <circle
              key={ring}
              cx="60"
              cy="75"
              r={26 + ring * 26}
              className="fill-none stroke-brand-300"
              strokeWidth="1"
              strokeDasharray="3 5"
            />
          ))}
          <circle cx="60" cy="75" r="7" className="fill-brand-700" />
          <line x1="90" y1="52" x2="176" y2="40" className="stroke-warning-strong" strokeWidth="1.5" />
          <rect x="176" y="26" width="150" height="28" rx="6" className="fill-surface stroke-warning-strong" strokeWidth="1" />
          <text x="186" y="45" className="fill-ink-800 font-mono text-[11px]">votre-societe.fr</text>
          <line x1="90" y1="88" x2="176" y2="100" className="stroke-critical-strong" strokeWidth="1.5" />
          <rect x="176" y="86" width="150" height="28" rx="6" className="fill-surface stroke-critical-strong" strokeWidth="1" />
          <text x="186" y="105" className="fill-ink-800 font-mono text-[11px]">votre-sociéte.fr</text>
        </svg>
        <p className="mt-3 text-xs text-ink-600">
          Un caractère de différence suffit à tromper un lecteur pressé.
        </p>
      </div>
    )
  }

  return (
    <div className="rounded-lg border border-ink-200 bg-surface p-5 shadow-soft">
      <div className="rounded-md border border-warning-strong/30 bg-warning-subtle px-4 py-3">
        <p className="text-xs font-semibold uppercase tracking-wide text-warning-strong">
          Réutilisation possible — à vérifier
        </p>
        <p className="mt-2 text-sm leading-relaxed text-ink-700">
          Une adresse professionnelle de votre société apparaît dans la fuite d’un service qui
          n’est pas le vôtre.
        </p>
      </div>
      <div className="mt-3 flex items-center gap-2 rounded-md bg-ink-50 px-4 py-3">
        <span className="font-mono text-sm text-ink-700">••••••23</span>
        <span className="ml-auto rounded border border-ink-300 px-2.5 py-1 text-xs text-ink-700">
          Révéler le mot de passe
        </span>
      </div>
      <p className="mt-2.5 text-xs text-ink-500">
        Consultation possible après vérification d’identité. Chaque accès est tracé.
      </p>
    </div>
  )
}

function HowItWorks() {
  return (
    <Section id="fonctionnement" className="bg-ink-50/50">
      <Reveal>
        <SectionTitle title={HOW_IT_WORKS.title} subtitle={HOW_IT_WORKS.subtitle} />
      </Reveal>
      <Reveal delay={100}>
        <div className="mt-12">
          <FlowDiagram />
        </div>
      </Reveal>
      <ol className="mt-10 grid gap-6 md:grid-cols-2 lg:grid-cols-4">
        {HOW_IT_WORKS.steps.map((step, index) => (
          <Reveal key={step.number} as="li" delay={index * 80} className="h-full">
            <div className="h-full rounded-lg border border-ink-200 bg-surface p-6">
              <span className="flex size-8 items-center justify-center rounded-full bg-brand-100 font-display text-sm font-semibold text-brand-800">
                {step.number}
              </span>
              <h3 className="mt-4 font-display text-base font-semibold text-ink-900">
                {step.title}
              </h3>
              <p className="mt-2 text-sm leading-relaxed text-ink-600">{step.body}</p>
            </div>
          </Reveal>
        ))}
      </ol>
    </Section>
  )
}

function Trust() {
  return (
    <Section id="securite">
      <Reveal>
        <SectionTitle eyebrow="Sécurité et données" title={TRUST.title} subtitle={TRUST.subtitle} />
      </Reveal>
      <div className="mt-10 grid gap-x-10 gap-y-8 md:grid-cols-2">
        {TRUST.items.map((item, index) => (
          <Reveal key={item.title} delay={index * 60}>
            <div className="flex gap-4">
              <span
                aria-hidden="true"
                className="mt-0.5 flex size-7 shrink-0 items-center justify-center rounded-md bg-ok-subtle text-ok-strong"
              >
                <Check className="size-4" />
              </span>
              <div>
                <h3 className="font-display text-base font-semibold text-ink-900">{item.title}</h3>
                <p className="mt-1.5 text-sm leading-relaxed text-ink-600">{item.body}</p>
              </div>
            </div>
          </Reveal>
        ))}
      </div>
    </Section>
  )
}

function Pricing() {
  // Les offres viennent de l'API : les modifier depuis l'administration doit
  // se refléter sur la vitrine sans redéploiement (ADR-019). Le contenu
  // statique sert de REPLI — une grille tarifaire vide serait pire qu'une
  // grille légèrement datée, et c'est la première chose qu'un prospect
  // regarde.
  const [plans, setPlans] = useState(null)

  useEffect(() => {
    let cancelled = false
    publicApi
      .listPlans()
      .then((response) => {
        if (cancelled) return
        const fetched = response.data?.plans || []
        if (fetched.length > 0) setPlans(fetched)
      })
      .catch(() => {
        /* repli statique : voir PRICING.plans ci-dessous */
      })
    return () => {
      cancelled = true
    }
  }, [])

  const displayed =
    plans ??
    PRICING.plans.map((plan) => ({
      code: plan.id,
      name: plan.name,
      tagline: plan.pitch,
      price_monthly: plan.price,
      currency: '€',
      is_quote_only: false,
      is_highlighted: Boolean(plan.highlighted),
      features: plan.features.map((label) => ({ key: label, label })),
    }))

  return (
    <Section id="tarifs" className="bg-ink-50/50">
      <Reveal>
        <SectionTitle title={PRICING.title} subtitle={PRICING.subtitle} />
      </Reveal>
      <div className="mt-10 grid gap-6 lg:grid-cols-3">
        {displayed.map((plan, index) => (
          <Reveal key={plan.code} delay={index * 90}>
            <div
              className={`flex h-full flex-col rounded-lg border bg-surface p-6 ${
                plan.is_highlighted
                  ? 'border-brand-600 shadow-elevated ring-1 ring-brand-600'
                  : 'border-ink-200'
              }`}
            >
              {plan.is_highlighted && (
                <span className="mb-3 self-start rounded-full bg-brand-100 px-2.5 py-1 text-xs font-medium text-brand-800">
                  Le plus demandé
                </span>
              )}
              <h3 className="font-display text-lg font-semibold text-ink-900">{plan.name}</h3>
              {plan.tagline && <p className="mt-1 text-sm text-ink-600">{plan.tagline}</p>}
              <p className="mt-5">
                {plan.is_quote_only ? (
                  <span className="font-display text-2xl font-semibold text-ink-900">
                    Sur devis
                  </span>
                ) : (
                  <>
                    <span className="font-display text-3xl font-semibold text-ink-900">
                      {Math.round(Number(plan.price_monthly))} {PRICING.currency}
                    </span>
                    <span className="text-sm text-ink-500"> / mois</span>
                  </>
                )}
              </p>
              <ul className="mt-6 flex-1 space-y-2.5">
                {(plan.features || []).map((feature) => (
                  <li key={feature.key} className="flex gap-2.5 text-sm text-ink-700">
                    <Check className="mt-0.5 size-4 shrink-0 text-ok-strong" aria-hidden="true" />
                    {feature.label}
                  </li>
                ))}
              </ul>
              <Link
                to="/demonstration"
                className={`transition-smooth mt-7 rounded-md px-4 py-2.5 text-center text-sm font-medium ${
                  plan.is_highlighted
                    ? 'bg-brand-700 text-white hover:bg-brand-800'
                    : 'border border-ink-300 text-ink-800 hover:bg-ink-50'
                } focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-brand-600`}
              >
                Demander une démonstration
              </Link>
            </div>
          </Reveal>
        ))}
      </div>
      <Reveal>
        <p className="mt-8 max-w-2xl text-sm text-ink-500">{PRICING.disclaimer}</p>
      </Reveal>
    </Section>
  )
}

function FaqItem({ item, open, onToggle, id }) {
  return (
    <div className="border-b border-ink-200">
      <h3>
        <button
          type="button"
          onClick={onToggle}
          aria-expanded={open}
          aria-controls={`faq-panel-${id}`}
          className="flex w-full items-center justify-between gap-4 py-5 text-left focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-brand-600"
        >
          <span className="font-display text-base font-medium text-ink-900">{item.question}</span>
          <ChevronDown
            aria-hidden="true"
            className={`size-5 shrink-0 text-ink-500 transition-transform duration-200 motion-reduce:transition-none ${
              open ? 'rotate-180' : ''
            }`}
          />
        </button>
      </h3>
      {open && (
        <div id={`faq-panel-${id}`} className="pb-5">
          <p className="max-w-3xl text-sm leading-relaxed text-ink-600">{item.answer}</p>
        </div>
      )}
    </div>
  )
}

function Faq() {
  const [openIndex, setOpenIndex] = useState(0)
  return (
    <Section id="questions">
      <Reveal>
        <SectionTitle title={FAQ.title} />
      </Reveal>
      <div className="mt-8">
        {FAQ.items.map((item, index) => (
          <FaqItem
            key={item.question}
            id={index}
            item={item}
            open={openIndex === index}
            onToggle={() => setOpenIndex(openIndex === index ? -1 : index)}
          />
        ))}
      </div>
    </Section>
  )
}

function FinalCta() {
  return (
    <Section className="bg-brand-900">
      <Reveal>
        <div className="max-w-2xl">
          <h2 className="font-display text-2xl font-semibold text-white sm:text-3xl">
            {FINAL_CTA.title}
          </h2>
          <p className="mt-3 text-base leading-relaxed text-brand-100">{FINAL_CTA.body}</p>
          <Link
            to="/demonstration"
            className="transition-smooth mt-7 inline-block rounded-md bg-white px-5 py-3 text-sm font-medium text-brand-900 hover:bg-brand-50 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-white"
          >
            {FINAL_CTA.cta}
          </Link>
        </div>
      </Reveal>
    </Section>
  )
}

export default function LandingPage() {
  useSeo({
    title: 'Surveillance des fuites de données pour les PME',
    description:
      "Nous surveillons neuf sources de renseignement sur les fuites de données et vous alertons en langage clair, avec l'action à mener. Sans installation.",
    path: '/',
    jsonLd: ORGANISATION_JSON_LD,
  })

  return (
    <MarketingLayout showSectionNav>
      <Hero />
      <Problem />
      <Differentiators />
      <HowItWorks />
      <Trust />
      <Pricing />
      <Faq />
      <FinalCta />
    </MarketingLayout>
  )
}
