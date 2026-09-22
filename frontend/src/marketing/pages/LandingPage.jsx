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
  AUSSI_LIVRE,
  DIAGNOSTIC,
  DIFFERENTIATORS,
  FAQ,
  FINAL_CTA,
  HERO,
  HOW_IT_WORKS,
  NOTIFICATIONS,
  PREUVES,
  PRICING,
  PROBLEM,
  quotaLines,
  TRUST,
} from '../content'
import { ORGANISATION_JSON_LD, useSeo } from '../useSeo'

function Section({ id, children, className = '' }) {
  return (
    // Rythme vertical unique entre sections : deux valeurs voisines (80 px
    // puis 96 px) ne créaient aucune régularité perceptible, seulement de
    // l'irrégularité.
    <section id={id} className={`px-5 py-14 sm:py-20 ${className}`}>
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
    <div className="relative overflow-hidden border-b border-ink-200 bg-surface">
      {/* Plus de dégradé de fond (refonte). Il était discret, mais il faisait
          exactement ce qu'on reproche au web généré : poser une ambiance à la
          place d'une preuve. Ce qui doit attirer l'œil ici est la capture du
          produit, pas la lumière derrière le titre. */}
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
            {/* `t-hero` : le seul emploi de ce rôle dans tout le produit. */}
            <h1 className="t-hero max-w-[19ch]">{HERO.title}</h1>
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
            src="/screenshots/exposition.webp"
            alt="Page Exposition du produit : les actifs classés par niveau d’exposition, avec l’analyse en tête."
            caption="Page Exposition — capture réelle, sur le client de démonstration."
          >
            <ExposureMockup />
          </BrowserFrame>
        </Reveal>
      </div>
    </div>
  )
}

/**
 * Le bandeau de preuve, juste sous l'accroche.
 *
 * Trois faits, pas trois arguments. Chacun est vérifiable dans le code ou la
 * documentation (voir `PREUVES` dans content.js) : aucun chiffre commercial
 * n'y figure, parce que le produit n'a qu'un client et que tout chiffre de ce
 * genre serait faux.
 */
function Preuves() {
  return (
    <div className="border-b border-ink-200 bg-brand-900">
      <div className="mx-auto grid max-w-6xl gap-8 px-5 py-9 sm:grid-cols-3">
        {PREUVES.map((preuve) => (
          <div key={preuve.valeur}>
            <p className="num font-display text-2xl font-bold text-white sm:text-3xl">
              {preuve.valeur}
            </p>
            <p className="mt-1 text-sm leading-relaxed text-brand-200">{preuve.libelle}</p>
          </div>
        ))}
      </div>
    </div>
  )
}

/**
 * Comptes désignés, veille réglementaire, formation — livrés, et absents de
 * la vitrine jusqu'ici. Raccourcir la page ne doit rien faire disparaître de
 * ce que le produit fait.
 */
function AussiLivre() {
  return (
    <Section className="bg-ink-50/50">
      <Reveal>
        <SectionTitle
          eyebrow="Également livré"
          title={AUSSI_LIVRE.title}
          subtitle={AUSSI_LIVRE.subtitle}
        />
      </Reveal>
      <div className="mt-10 grid items-start gap-10 lg:grid-cols-[7fr_5fr]">
        <div>
          {AUSSI_LIVRE.items.map((item, index) => (
            <Reveal key={item.title} delay={index * 60} className="ligne-liste block py-5">
              <h3 className="t-title text-base">{item.title}</h3>
              <p className="t-body mt-1.5">{item.body}</p>
            </Reveal>
          ))}
        </div>
        <Reveal delay={120}>
          <BrowserFrame
            src="/screenshots/formation.webp"
            alt="Le module de formation : campagnes, taux de participation et questions les plus ratées."
            caption="La formation des salariés — capture réelle, sur le client de démonstration."
          />
        </Reveal>
      </div>
    </Section>
  )
}

function Problem() {
  return (
    <Section id="probleme" className="bg-ink-50/50">
      <Reveal>
        <SectionTitle eyebrow="Le constat" title={PROBLEM.title} />
      </Reveal>
      {/* Trois constats, donc une LISTE — pas trois cartes. Le constat se lit
          d'un trait, et trois boîtes de même forme obligeaient l'œil à
          repartir de zéro à chaque fois. */}
      <div className="mt-10 max-w-3xl">
        {PROBLEM.items.map((item, index) => (
          <Reveal key={item.title} delay={index * 60}>
            <div className="ligne-liste flex gap-5 py-5">
              <span className="t-meta num shrink-0 pt-0.5 text-ink-400">
                {String(index + 1).padStart(2, '0')}
              </span>
              <div>
                <h3 className="t-title text-lg">{item.title}</h3>
                <p className="t-body mt-1.5">{item.body}</p>
              </div>
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
      <div className="mt-10 space-y-12">
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
      {/* Quatre étapes, donc une bande — pas quatre cartes surmontées d'une
          pastille ronde, qui est la mise en page la plus reconnaissable du
          web généré. Le filet vertical porte la progression sur grand écran,
          le numéro la porte partout. */}
      <ol className="mt-10 grid gap-x-8 gap-y-7 md:grid-cols-2 lg:grid-cols-4">
        {HOW_IT_WORKS.steps.map((step, index) => (
          <Reveal
            key={step.number}
            as="li"
            delay={index * 60}
            className="lg:border-l lg:border-ink-200 lg:pl-5"
          >
            <span className="t-eyebrow num text-brand-700">Étape {step.number}</span>
            <h3 className="t-title mt-2 text-base">{step.title}</h3>
            <p className="t-body mt-1.5">{step.body}</p>
          </Reveal>
        ))}
      </ol>
    </Section>
  )
}

/**
 * Le diagnostic, en amont de la surveillance dans la page comme dans l'usage.
 *
 * Placé juste après « Le produit » et AVANT « Fonctionnement » : c'est la
 * première chose qu'une PME peut faire le jour de son inscription, et la
 * seule qui ne dépende d'aucune détection. La reléguer en bas de page
 * revenait à la présenter comme un supplément.
 */
function Diagnostic() {
  return (
    <Section id="diagnostic" className="bg-ink-50/50">
      <Reveal>
        <SectionTitle
          eyebrow="Diagnostic"
          title={DIAGNOSTIC.title}
          subtitle={DIAGNOSTIC.subtitle}
        />
      </Reveal>
      {/* La preuve à droite, l'explication à gauche : c'est le score et le
          plan d'action que le visiteur veut voir, pas quatre encadrés. */}
      <div className="mt-10 grid items-start gap-10 lg:grid-cols-[5fr_7fr]">
        <ol>
          {DIAGNOSTIC.steps.map((step, index) => (
            <Reveal key={step.title} as="li" delay={index * 60} className="ligne-liste block py-4">
              {/* Le numéro encode une progression réelle : on répond, on
                  obtient un score, on en tire un plan, puis des documents.
                  Il n'est pas décoratif — d'où la liste ordonnée. */}
              <div className="flex gap-4">
                <span className="t-meta num shrink-0 pt-0.5 text-ink-400">
                  {String(index + 1).padStart(2, '0')}
                </span>
                <div>
                  <h3 className="t-title text-base">{step.title}</h3>
                  <p className="t-body mt-1">{step.body}</p>
                </div>
              </div>
            </Reveal>
          ))}
        </ol>

        <Reveal delay={120}>
          <BrowserFrame
            src="/screenshots/diagnostic.webp"
            alt="Résultats du diagnostic : score de maturité, détail par domaine et plan d’action."
            caption="Les résultats du diagnostic — capture réelle, sur le client de démonstration."
          />
        </Reveal>
      </div>
      <Reveal>
        <p className="t-meta mt-8 max-w-2xl">{DIAGNOSTIC.note}</p>
      </Reveal>
    </Section>
  )
}

/**
 * Ce qui arrive par email. Section volontairement placée après le diagnostic :
 * l'argument n'est pas « nous envoyons des emails », c'est « vous n'avez pas
 * à venir » — il se comprend une fois qu'on sait ce que le produit observe.
 */
function Notifications() {
  return (
    <Section id="alertes">
      <Reveal>
        <SectionTitle
          eyebrow="Sans vous connecter"
          title={NOTIFICATIONS.title}
          subtitle={NOTIFICATIONS.subtitle}
        />
      </Reveal>
      {/* La même enveloppe devant les quatre entrées ne disait rien : une
          icône répétée à l'identique est un ornement, pas une information.
          Le filet sépare, le titre porte le sens. */}
      <div className="mt-10 grid gap-x-12 md:grid-cols-2">
        {NOTIFICATIONS.items.map((item, index) => (
          <Reveal key={item.title} delay={index * 60} className="ligne-liste block py-5">
            <h3 className="t-title text-base">{item.title}</h3>
            <p className="t-body mt-1.5">{item.body}</p>
            {item.detail && <p className="t-meta mt-2">{item.detail}</p>}
          </Reveal>
        ))}
      </div>
    </Section>
  )
}

function Trust() {
  return (
    <Section id="securite">
      <Reveal>
        <SectionTitle eyebrow="Sécurité et données" title={TRUST.title} subtitle={TRUST.subtitle} />
      </Reveal>
      {/* Les six engagements sont CONSERVÉS en entier : c'est la section
          qu'un RSSI lit vraiment, et elle ne se résume pas à une question de
          la foire aux questions. Seule la forme change — des filets, et la
          coche répétée en moins. */}
      <div className="mt-10 grid gap-x-12 md:grid-cols-2">
        {TRUST.items.map((item, index) => (
          <Reveal key={item.title} delay={index * 50} className="ligne-liste block py-5">
            <h3 className="t-title text-base">{item.title}</h3>
            <p className="t-body mt-1.5">{item.body}</p>
          </Reveal>
        ))}
      </div>
    </Section>
  )
}

/**
 * L'union des fonctionnalités de toutes les offres, dans l'ordre où elles
 * apparaissent. Une comparaison n'a de sens que si chaque ligne existe pour
 * toutes les colonnes — sinon on ne compare pas, on juxtapose.
 */
function fonctionnalitesComparees(plans) {
  const vues = []
  for (const plan of plans) {
    for (const feature of plan.features || []) {
      if (!vues.includes(feature.label)) vues.push(feature.label)
    }
  }
  return vues
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

  // Aucune traduction entre les deux sources : le repli a désormais la forme
  // exacte de l'API (content.js). C'est dans cette traduction que la
  // divergence s'était installée — le repli annonçait d'autres noms et
  // d'autres prix que la base, et rien ne le signalait.
  const displayed = plans ?? PRICING.plans

  return (
    <Section id="tarifs" className="bg-ink-50/50">
      <Reveal>
        <SectionTitle eyebrow="Tarifs" title={PRICING.title} subtitle={PRICING.subtitle} />
      </Reveal>
      {/* Un TABLEAU comparatif, et non trois cartes flottantes : un
          dirigeant compare des colonnes, il ne lit pas trois fiches l'une
          après l'autre. Les données restent celles de l'API, avec le repli
          statique — seule la présentation change.

          Défilement horizontal sur petit écran plutôt qu'un second rendu en
          blocs : deux rendus du même contenu doubleraient chaque libellé dans
          la page, donc pour un lecteur d'écran aussi. */}
      <div className="mt-10 overflow-x-auto">
        {/* `aria-label` plutôt qu'un `<caption className="sr-only">` : un
            caption en position absolue s'échappe de son conteneur à
            défilement et élargit la PAGE de 123 px au téléphone. Mesuré, pas
            supposé — la page débordait horizontalement à 390 px. */}
        <table
          className="w-full min-w-[640px] border-collapse text-left"
          aria-label="Comparaison des offres : prix, quotas et fonctionnalités incluses"
        >
          <thead>
            <tr>
              <th scope="col" className="t-meta w-2/6 border-b border-ink-200 px-4 py-3 align-bottom">
                Ce que vous obtenez
              </th>
              {displayed.map((plan) => (
                <th
                  key={plan.code}
                  scope="col"
                  className={`border-b border-ink-200 px-4 py-3 align-bottom ${
                    plan.is_highlighted ? 'bg-brand-50' : ''
                  }`}
                >
                  {plan.is_highlighted && (
                    <span className="t-eyebrow mb-1.5 block text-brand-700">Le plus demandé</span>
                  )}
                  <span className="t-title block text-lg">{plan.name}</span>
                  {plan.tagline && <span className="t-meta mt-1 block font-normal">{plan.tagline}</span>}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            <tr>
              <th scope="row" className="t-body border-b border-ink-100 px-4 py-3 font-medium">
                Par mois
              </th>
              {displayed.map((plan) => (
                <td
                  key={plan.code}
                  className={`border-b border-ink-100 px-4 py-3 ${plan.is_highlighted ? 'bg-brand-50' : ''}`}
                >
                  {plan.is_quote_only ? (
                    <span className="font-display text-xl font-semibold text-ink-900">
                      {PRICING.quoteLabel}
                    </span>
                  ) : (
                    <>
                      <span className="num font-display text-2xl font-semibold text-ink-900">
                        {Math.round(Number(plan.price_monthly))} {PRICING.currency}
                      </span>
                      <span className="t-meta"> / mois</span>
                    </>
                  )}
                </td>
              ))}
            </tr>

            <tr>
              <th scope="row" className="t-body border-b border-ink-100 px-4 py-3 font-medium">
                Ce qui est compté
              </th>
              {displayed.map((plan) => (
                <td
                  key={plan.code}
                  className={`border-b border-ink-100 px-4 py-3 align-top ${
                    plan.is_highlighted ? 'bg-brand-50' : ''
                  }`}
                >
                  {/* Les libellés sont DÉRIVÉS des champs de l'offre
                      (quotaLines) : aucun nombre n'est recopié à la main, ni
                      ici ni dans le repli. Voir ADR-013 sur le pool partagé. */}
                  <ul className="space-y-1.5">
                    {quotaLines(plan).map((line) => (
                      <li key={line} className="t-body text-ink-800">
                        {line}
                      </li>
                    ))}
                  </ul>
                </td>
              ))}
            </tr>

            {fonctionnalitesComparees(displayed).map((libelle) => (
              <tr key={libelle}>
                <th scope="row" className="t-body border-b border-ink-100 px-4 py-3 font-normal">
                  {libelle}
                </th>
                {displayed.map((plan) => {
                  const inclus = (plan.features || []).some((f) => f.label === libelle)
                  return (
                    <td
                      key={plan.code}
                      className={`border-b border-ink-100 px-4 py-3 ${
                        plan.is_highlighted ? 'bg-brand-50' : ''
                      }`}
                    >
                      {/* La coche ne suffit pas : elle n'est pas lue, et un
                          tiret seul ne se distingue pas d'une cellule vide. */}
                      {inclus ? (
                        <span className="flex items-center gap-2 text-brand-700">
                          <Check className="size-4 shrink-0" aria-hidden="true" />
                          <span className="lecture-seule">Inclus</span>
                        </span>
                      ) : (
                        <span className="t-meta">
                          <span aria-hidden="true">—</span>
                          <span className="lecture-seule">Non inclus</span>
                        </span>
                      )}
                    </td>
                  )
                })}
              </tr>
            ))}

            <tr>
              <td className="p-4" />
              {displayed.map((plan) => (
                <td key={plan.code} className={`p-4 ${plan.is_highlighted ? 'bg-brand-50' : ''}`}>
                  <Link
                    to="/demonstration"
                    className={`transition-smooth inline-block rounded-md px-4 py-2.5 text-center text-sm font-medium ${
                      plan.is_highlighted
                        ? 'bg-brand-700 text-white hover:bg-brand-800'
                        : 'border border-ink-300 text-ink-800 hover:bg-ink-50'
                    } focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-brand-600`}
                  >
                    Demander une démonstration
                  </Link>
                </td>
              ))}
            </tr>
          </tbody>
        </table>
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
      <Preuves />
      <Problem />
      <Differentiators />
      <Diagnostic />
      <Notifications />
      <AussiLivre />
      <HowItWorks />
      <Trust />
      <Pricing />
      <Faq />
      <FinalCta />
    </MarketingLayout>
  )
}
