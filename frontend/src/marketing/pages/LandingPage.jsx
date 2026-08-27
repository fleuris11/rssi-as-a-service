import { Check, ChevronDown } from 'lucide-react'
import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { publicApi } from '../../api/endpoints'
import ApercuProduit from '../components/ApercuProduit'
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
    // Rythme vertical unique entre sections : deux valeurs voisines (80 px
    // puis 96 px) ne créaient aucune régularité perceptible, seulement de
    // l'irrégularité.
    <section id={id} className={`px-5 py-20 sm:py-28 ${className}`}>
      <div className="mx-auto max-w-6xl">{children}</div>
    </section>
  )
}

/**
 * Point d'entrée du regard, identique dans toutes les sections.
 *
 * Trois rôles typographiques dans un ordre fixe — surtitre, titre, phrase de
 * tête — et un filet court sous le surtitre. Le filet n'est pas un ornement :
 * il donne à l'œil un point d'accroche à hauteur constante, si bien qu'en
 * faisant défiler la page on retrouve toujours le début d'une section au même
 * endroit.
 *
 * Le surtitre passe du bleu au gris : en bleu, il rivalisait avec les actions,
 * qui sont la seule chose bleue que le visiteur doive repérer d'un coup d'œil.
 */
function SectionTitle({ eyebrow, title, subtitle }) {
  return (
    <div className="max-w-2xl">
      {eyebrow && (
        <p className="t-eyebrow flex items-center gap-2.5">
          <span className="h-px w-6 bg-brand-600" aria-hidden="true" />
          {eyebrow}
        </p>
      )}
      <h2 className="t-display mt-3 text-2xl sm:text-3xl">{title}</h2>
      {subtitle && <p className="t-lead mt-3">{subtitle}</p>}
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
          {/* L'accroche doit se lire en une seconde. Trois leviers, aucun
              n'étant du décor :
              — une seule chose est grande sur cet écran, le titre ;
              — la phrase de tête n'est pas un second paragraphe mais un
                complément, d'où la largeur bornée qui l'empêche de rivaliser ;
              — une seule action est remplie, comme partout ailleurs dans le
                produit. « Se connecter » s'adresse à un client existant, pas
                au prospect : elle n'a pas à peser autant. */}
          <Reveal>
            <h1 className="t-display max-w-[19ch] text-3xl leading-[1.08] sm:text-4xl lg:text-[3rem]">
              {HERO.title}
            </h1>
          </Reveal>
          <Reveal delay={80}>
            <p className="t-lead mt-5 max-w-[46ch] text-lg">{HERO.subtitle}</p>
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
                className="transition-smooth rounded-md px-5 py-3 text-sm font-medium text-ink-600 hover:bg-ink-100 hover:text-ink-800 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-brand-600"
              >
                {HERO.secondaryCta}
              </Link>
            </div>
            <p className="t-meta mt-4">{HERO.note}</p>
          </Reveal>
        </div>

        <Reveal delay={220}>
          <BrowserFrame
            src="/screenshots/exposition.png"
            alt="Page Exposition du produit : les actifs classés par niveau d’exposition, avec l’analyse en tête."
            caption="Page Exposition — reconstitution de l’interface réelle."
          >
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
        <SectionTitle eyebrow="Le constat" title={PROBLEM.title} />
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
                  // Le bandeau « À faire » reproduit celui de l'application,
                  // couleurs comprises. Il n'est donc légitime que DANS le
                  // cadre produit — hors de lui, la vitrine s'en tient au bleu
                  // et au gris.
                  <ApercuProduit label={item.example.label}>
                    <p className="t-body rounded-md bg-ink-50 px-4 py-3">{item.example.meaning}</p>
                    <p className="t-body mt-2.5 rounded-md bg-accent-100/50 px-4 py-3 text-accent-900">
                      <span className="font-semibold">À faire : </span>
                      {item.example.action}
                    </p>
                  </ApercuProduit>
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
          {/* Ce schéma n'est pas une capture du produit : il illustre une idée.
              Il employait pourtant l'ambre et le rouge de l'échelle de
              gravité pour opposer les deux domaines — de la décoration payée
              avec le vocabulaire du risque.
              La différence est désormais portée par ce qui la constitue
              réellement : le caractère qui change. C'est plus juste ET plus
              accessible, la couleur n'étant jamais seule porteuse de sens. */}
          <line x1="90" y1="52" x2="176" y2="40" className="stroke-ink-300" strokeWidth="1.5" />
          <rect x="176" y="26" width="150" height="28" rx="6" className="fill-surface stroke-ink-300" strokeWidth="1" />
          <text x="186" y="45" className="fill-ink-600 font-mono text-[11px]">votre-societe.fr</text>
          <line x1="90" y1="88" x2="176" y2="100" className="stroke-brand-600" strokeWidth="1.5" />
          <rect x="176" y="86" width="150" height="28" rx="6" className="fill-brand-50 stroke-brand-600" strokeWidth="1.5" />
          <text x="186" y="105" className="fill-ink-800 font-mono text-[11px]">
            votre-soci
            <tspan className="fill-brand-800 font-semibold" style={{ textDecoration: 'underline' }}>
              é
            </tspan>
            te.fr
          </text>
        </svg>
        <p className="mt-3 text-xs text-ink-600">
          Un caractère de différence suffit à tromper un lecteur pressé.
        </p>
      </div>
    )
  }

  return (
    // Reproduction fidèle d'un encadré de l'application : le cadre autorise
    // ses couleurs, et dit au visiteur qu'il regarde l'écran.
    <ApercuProduit
      label="Dans l’application"
      src="/screenshots/revelation.png"
      alt="Encadré « Réutilisation possible » et accès tracé au mot de passe fuité."
    >
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
      <p className="t-meta mt-2.5">
        Consultation possible après vérification d’identité. Chaque accès est tracé.
      </p>
    </ApercuProduit>
  )
}

function HowItWorks() {
  return (
    <Section id="fonctionnement" className="bg-ink-50/50">
      <Reveal>
        <SectionTitle eyebrow="Fonctionnement" title={HOW_IT_WORKS.title} subtitle={HOW_IT_WORKS.subtitle} />
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
                className="mt-0.5 flex size-7 shrink-0 items-center justify-center rounded-md bg-brand-100 text-brand-700"
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
        <SectionTitle eyebrow="Tarifs" title={PRICING.title} subtitle={PRICING.subtitle} />
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
                    <Check className="mt-0.5 size-4 shrink-0 text-brand-600" aria-hidden="true" />
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
        <SectionTitle eyebrow="Questions" title={FAQ.title} />
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
