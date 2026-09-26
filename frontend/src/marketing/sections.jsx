import { Check } from 'lucide-react'
import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { publicApi } from '../api/endpoints'
import ApercuProduit from './components/ApercuProduit'
import { Acte, Action } from './atomes'
import BrowserFrame from './components/BrowserFrame'
import FlowDiagram from './components/FlowDiagram'
import Defilement from '../components/ui/Defilement'
import {
  ASSISTANT,
  AUSSI_LIVRE,
  DIAGNOSTIC,
  DIFFERENTIATORS,
  FAQ,
  HOW_IT_WORKS,
  NOTIFICATIONS,
  PRICING,
  TRUST,
  quotaLines,
} from './content'

/**
 * LES SECTIONS DE LA VITRINE, partagées entre les pages.
 *
 * L'accueil n'en garde que l'essentiel ; ces sections portent le détail sur
 * /fonctionnalites, /securite-du-produit, /offres et /questions. **Rien n'a
 * été supprimé** au passage : l'inventaire de ce qui a bougé est dans
 * docs/design.md.
 *
 * Aucune section n'emploie de sur-titre au-dessus de son titre : le plancher
 * de qualité l'interdit, et le titre porte son propre poids.
 */

/* ================================================================== *
 * CE QUE LE PRODUIT FAIT DIFFÉREMMENT
 * ================================================================== */
export function Differences() {
  return (
    <Acte id="produit" fond="haute">
      <h2 className="t-display max-w-3xl">{DIFFERENTIATORS.title}</h2>
      <div className="mt-12 space-y-14">
        {DIFFERENTIATORS.items.map((item, rang) => (
          <article
            key={item.id}
            className={`grid items-start gap-8 lg:grid-cols-2 lg:gap-14 ${
              rang % 2 === 1 ? 'lg:[&>*:first-child]:order-2' : ''
            }`}
          >
            <div>
              <h3 className="t-title text-xl sm:text-2xl">{item.title}</h3>
              <p className="t-body mt-3 text-base">{item.body}</p>
              {item.detail && (
                <p className="t-body mt-4 border-t border-ink-200 pt-4 text-ink-600">
                  {item.detail}
                </p>
              )}
            </div>

            <div>
              {item.example ? (
                <ApercuProduit label={item.example.label}>
                  <p className="t-body rounded-md bg-ink-100 px-4 py-3">{item.example.meaning}</p>
                  <p className="t-body mt-2.5 rounded-md border border-ink-200 px-4 py-3 text-ink-800">
                    <span className="font-semibold">À faire : </span>
                    {item.example.action}
                  </p>
                </ApercuProduit>
              ) : (
                <VisuelDifference id={item.id} />
              )}
            </div>
          </article>
        ))}
      </div>
    </Acte>
  )
}

/** Compositions originales — pas de photo, pas d'icône générique. */
function VisuelDifference({ id }) {
  // L'item « assistant » n'avait pas de visuel propre et retombait sur la
  // maquette « Réutilisation possible » : un écran de mot de passe fuité pour
  // illustrer l'assistant. Il a maintenant sa capture.
  if (id === 'assistant') {
    return (
      <BrowserFrame
        src="/screenshots/assistant.webp"
        alt="L’assistant : une question posée en français, une réponse appuyée sur les données du client, et l’action à mener."
        caption="Capture réelle. Valeurs d’exemple."
        url="rssiasservice.online/assistant"
      />
    )
  }
  if (id === 'signaux') {
    return (
      <div className="panneau p-6">
        <svg viewBox="0 0 340 150" className="h-auto w-full" aria-hidden="true" focusable="false">
          {[0, 1, 2].map((anneau) => (
            <circle
              key={anneau}
              cx="60"
              cy="75"
              r={26 + anneau * 26}
              className="fill-none stroke-ink-300"
              strokeWidth="1"
              strokeDasharray="3 5"
            />
          ))}
          <circle cx="60" cy="75" r="7" className="fill-ink-900" />
          {/* La différence est portée par ce qui la constitue réellement : le
              caractère qui change. Jamais par la couleur seule. */}
          <line x1="90" y1="52" x2="176" y2="40" className="stroke-ink-300" strokeWidth="1.5" />
          <rect x="176" y="26" width="150" height="28" rx="4" className="fill-surface stroke-ink-300" strokeWidth="1" />
          <text x="186" y="45" className="fill-ink-600 font-mono text-[11px]">votre-societe.fr</text>
          <line x1="90" y1="88" x2="176" y2="100" className="stroke-brand-600" strokeWidth="1.5" />
          <rect x="176" y="86" width="150" height="28" rx="4" className="fill-brand-50 stroke-brand-600" strokeWidth="1.5" />
          <text x="186" y="105" className="fill-ink-800 font-mono text-[11px]">
            votre-soci
            <tspan className="fill-brand-700 font-semibold" style={{ textDecoration: 'underline' }}>
              é
            </tspan>
            te.fr
          </text>
        </svg>
        <p className="t-meta mt-4">Un caractère de différence suffit à tromper un lecteur pressé.</p>
      </div>
    )
  }

  return (
    <ApercuProduit label="Dans l’application">
      <div className="rounded-md border border-risk-watch-border bg-risk-watch-surface px-4 py-3">
        <p className="t-legende text-risk-watch">Réutilisation possible — à vérifier</p>
        <p className="mt-2 text-sm leading-relaxed text-ink-700">
          Une adresse professionnelle de votre société apparaît dans la fuite d’un service qui n’est
          pas le vôtre.
        </p>
      </div>
      <div className="mt-3 flex items-center gap-2 rounded-md bg-ink-100 px-4 py-3">
        <span className="n text-sm text-ink-700">••••••23</span>
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

/* ================================================================== *
 * L'INTELLIGENCE ARTIFICIELLE, ET SES LIMITES
 *
 * La page disait ce que fait l'assistant et taisait les trois autres usages,
 * les garde-fous, et la nuance qui compte le plus : la plupart des documents
 * ne sont PAS rédigés par l'IA.
 * ================================================================== */
export function IntelligenceArtificielle() {
  return (
    <Acte id="assistant" fond="haute">
      <div className="grid gap-10 lg:grid-cols-[minmax(0,0.85fr)_minmax(0,1.15fr)] lg:gap-16">
        <div>
          <h2 className="t-display">Ce que l’IA fait, et ce qu’elle ne fait pas</h2>
          <p className="t-body mt-4">{ASSISTANT.subtitle}</p>
          <BrowserFrame
            className="mt-8"
            src="/screenshots/assistant.webp"
            alt="L’assistant : une question posée en français, une réponse appuyée sur les données du client, et l’action à mener."
            caption="Capture réelle. Valeurs d’exemple."
            url="rssiasservice.online/assistant"
          />
        </div>

        <div>
          {ASSISTANT.garanties.map((garantie) => (
            <div key={garantie.title} className="ligne-liste py-5 first:pt-0">
              <h3 className="text-base font-semibold text-ink-900">{garantie.title}</h3>
              <p className="t-body mt-1.5">{garantie.body}</p>
            </div>
          ))}

          <h3 className="t-title mt-10">{ASSISTANT.ailleurs.title}</h3>
          {ASSISTANT.ailleurs.items.map((item) => (
            <div key={item.title} className="ligne-liste py-5">
              <h4 className="text-base font-semibold text-ink-900">{item.title}</h4>
              <p className="t-body mt-1.5">{item.body}</p>
            </div>
          ))}

          {/* La nuance à contre-courant, et c'est un argument : un document
              reproductible vaut mieux qu'un document réinventé à chaque fois. */}
          <p className="t-body mt-6 border-t border-ink-200 pt-5 text-ink-600">
            {ASSISTANT.ailleurs.note}
          </p>
          <p className="t-meta mt-4">{ASSISTANT.sobriete}</p>
        </div>
      </div>
    </Acte>
  )
}

/* ================================================================== *
 * LES ENVOIS
 * ================================================================== */
export function Alertes() {
  return (
    <Acte id="alertes" fond="creuse">
      <div className="grid gap-10 lg:grid-cols-[minmax(0,0.85fr)_minmax(0,1.15fr)] lg:gap-16">
        <div>
          <h2 className="t-display">{NOTIFICATIONS.title}</h2>
          <p className="t-body mt-4">{NOTIFICATIONS.subtitle}</p>
          <BrowserFrame
            className="mt-8"
            src="/screenshots/notifications.webp"
            alt="Le centre de notifications : chaque événement porte ce qu’il signifie et l’écran vers lequel il mène."
            caption="Capture réelle. Valeurs d’exemple."
            url="rssiasservice.online/notifications"
          />
        </div>
        <div>
          {NOTIFICATIONS.items.map((item) => (
            <div key={item.title} className="ligne-liste py-5 first:pt-0">
              <h3 className="text-base font-semibold text-ink-900">{item.title}</h3>
              <p className="t-body mt-1.5">{item.body}</p>
              {item.detail && <p className="t-meta mt-2">{item.detail}</p>}
            </div>
          ))}
        </div>
      </div>
    </Acte>
  )
}

/* ================================================================== *
 * LE DIAGNOSTIC
 * ================================================================== */
export function Diagnostic() {
  return (
    <Acte id="diagnostic" fond="haute">
      <div className="grid gap-10 lg:grid-cols-[minmax(0,0.85fr)_minmax(0,1.15fr)] lg:gap-16">
        <div>
          <h2 className="t-display">{DIAGNOSTIC.title}</h2>
          <p className="t-body mt-4">{DIAGNOSTIC.subtitle}</p>
          <p className="t-meta mt-5">{DIAGNOSTIC.note}</p>
        </div>
        <div>
          {DIAGNOSTIC.steps.map((step) => (
            <div key={step.title} className="ligne-liste py-5 first:pt-0">
              <h3 className="text-base font-semibold text-ink-900">{step.title}</h3>
              <p className="t-body mt-1.5">{step.body}</p>
            </div>
          ))}
        </div>
      </div>
      <BrowserFrame
        className="mt-12"
        src="/screenshots/diagnostic.webp"
        alt="La restitution du diagnostic : score global, score par domaine, et les mesures qui les composent."
        caption="Capture réelle. Valeurs d’exemple."
        url="rssiasservice.online/resultats"
      />
    </Acte>
  )
}

/* ================================================================== *
 * LE FONCTIONNEMENT — quatre étapes
 * ================================================================== */
export function Fonctionnement() {
  return (
    <Acte id="fonctionnement" fond="bati">
      <h2 className="t-display max-w-3xl text-craie">{HOW_IT_WORKS.title}</h2>
      <p className="mt-4 max-w-2xl text-sm leading-relaxed text-craie-douce">
        {HOW_IT_WORKS.subtitle}
      </p>
      {/* Une BANDE numérotée, pas quatre cartes surmontées d'une pastille
          ronde. Le numéro porte la progression : ici la séquence est une vraie
          information, c'est l'ordre dans lequel les choses arrivent. */}
      {/* Le schéma reste : il dit en une image ce que les quatre paragraphes
          disent en quatre phrases, et c'est du CONTENU, pas un ornement. */}
      <div className="mt-10 rounded-lg bg-surface p-6 sm:p-8">
        <FlowDiagram />
      </div>
      <ol className="mt-10 grid gap-x-10 gap-y-8 md:grid-cols-2 lg:grid-cols-4">
        {HOW_IT_WORKS.steps.map((step) => (
          <li key={step.number} className="border-t border-bati-500 pt-4">
            <p className="n text-sm text-craie-douce">
              {String(step.number).padStart(2, '0')}
            </p>
            <h3 className="mt-2 text-base font-semibold text-craie">{step.title}</h3>
            <p className="mt-2 text-sm leading-relaxed text-craie-douce">{step.body}</p>
          </li>
        ))}
      </ol>
    </Acte>
  )
}

/* ================================================================== *
 * CE QUI EST LIVRÉ AUSSI
 * ================================================================== */
/** Chaque volet montre son écran : trois affirmations, trois preuves. */
const ECRANS_AUSSI_LIVRE = {
  'Comptes désignés': {
    src: '/screenshots/comptes-surveilles.webp',
    alt: 'Les comptes désignés : chaque compte surveillé porte la finalité déclarée et la date de déclaration.',
    url: 'rssiasservice.online/comptes-surveilles',
  },
  'Veille réglementaire': {
    src: '/screenshots/veille.webp',
    alt: 'La veille réglementaire : chaque publication est rattachée à une obligation, et propose sans jamais modifier.',
    url: 'rssiasservice.online/veille',
  },
  'Formation des salariés': {
    src: '/screenshots/formation.webp',
    alt: 'La formation : les salariés inscrits, leur avancement, et le lien personnel de chacun.',
    url: 'rssiasservice.online/formation',
  },
}

export function EgalementLivre() {
  return (
    <Acte id="egalement" fond="creuse">
      <h2 className="t-display max-w-3xl">{AUSSI_LIVRE.title}</h2>
      <p className="t-lead mt-4">{AUSSI_LIVRE.subtitle}</p>

      <div className="mt-12 space-y-14">
        {AUSSI_LIVRE.items.map((item, rang) => {
          const ecran = ECRANS_AUSSI_LIVRE[item.title]
          return (
            <article
              key={item.title}
              className={`grid items-center gap-8 lg:grid-cols-2 lg:gap-14 ${
                rang % 2 === 1 ? 'lg:[&>*:first-child]:order-2' : ''
              }`}
            >
              <div>
                <h3 className="t-title text-xl">{item.title}</h3>
                <p className="t-body mt-3 text-base">{item.body}</p>
              </div>
              {ecran ? (
                <BrowserFrame
                  src={ecran.src}
                  alt={ecran.alt}
                  caption="Capture réelle. Valeurs d’exemple."
                  url={ecran.url}
                />
              ) : (
                <div />
              )}
            </article>
          )
        })}
      </div>
    </Acte>
  )
}

/* ================================================================== *
 * LES DONNÉES
 * ================================================================== */
export function Donnees({ entete = true }) {
  // Sans le titre de section, les six engagements se retrouvent en h3
  // directement sous le h1 de la page : un niveau saute. Le niveau suit donc
  // la presence de l'en-tete, au lieu d'etre ecrit en dur.
  const Titre = entete ? 'h3' : 'h2'
  return (
    <Acte id="donnees" fond="haute" sansHaut={!entete}>
      {/* Sur /securite-du-produit la page porte deja ce titre et ce chapeau,
          mot pour mot. Les repeter laissait un vide entre deux phrases
          identiques, et c'est le vide qu'on remarquait. */}
      {entete && (
        <>
          <h2 className="t-display max-w-3xl">{TRUST.title}</h2>
          <p className="t-lead mt-5">{TRUST.subtitle}</p>
        </>
      )}
      <div className={`grid gap-x-14 sm:grid-cols-2 ${entete ? 'mt-10' : ''}`}>
        {TRUST.items.map((item) => (
          <div key={item.title} className="ligne-liste py-5 sm:first:pt-0 sm:[&:nth-child(2)]:sm:pt-0">
            <Titre className="text-base font-semibold text-ink-900">{item.title}</Titre>
            <p className="t-body mt-1.5">{item.body}</p>
          </div>
        ))}
      </div>

      {/* Ce que produisent ces engagements, à l'écran : un mot de passe
          retrouvé reste masqué, et sa consultation demande une nouvelle
          preuve d'identité. Le dire est une promesse, le montrer est une
          démonstration. */}
      <BrowserFrame
        className="mt-12"
        src="/screenshots/compromissions.webp"
        alt="L’écran des compromissions : chaque élément retrouvé est expliqué, le mot de passe reste masqué, et sa consultation est tracée."
        caption="Capture réelle. Valeurs d’exemple."
        url="rssiasservice.online/compromissions"
      />
    </Acte>
  )
}

/* ================================================================== *
 * LES OFFRES
 * ================================================================== */

/**
 * L'union des fonctionnalités de toutes les offres, dans l'ordre où elles
 * apparaissent. Une comparaison n'a de sens que si chaque ligne existe pour
 * toutes les colonnes — sinon on ne compare pas, on juxtapose.
 */
export function fonctionnalitesComparees(plans) {
  const vues = []
  for (const plan of plans) {
    for (const feature of plan.features || []) {
      if (!vues.includes(feature.label)) vues.push(feature.label)
    }
  }
  return vues
}

export function Offres({ entete = true }) {
  // Les offres viennent de l'API : les modifier depuis l'administration doit
  // se refléter sur la vitrine sans redéploiement (ADR-019). Le contenu
  // statique sert de REPLI — une grille tarifaire vide serait pire qu'une
  // grille légèrement datée, et c'est la première chose qu'un prospect
  // regarde. Le repli a la forme EXACTE de l'API : c'est dans la traduction
  // entre deux formes que la divergence s'était installée.
  const [plans, setPlans] = useState(null)

  useEffect(() => {
    let annule = false
    publicApi
      .listPlans()
      .then((reponse) => {
        if (annule) return
        const recues = reponse.data?.plans || []
        if (recues.length > 0) setPlans(recues)
      })
      .catch(() => {
        /* repli statique : PRICING.plans */
      })
    return () => {
      annule = true
    }
  }, [])

  const affichees = plans ?? PRICING.plans

  return (
    <Acte id="tarifs" fond="haute" sansHaut={!entete}>
      {/* `entete` : sur /offres la page porte deja son titre, et deux titres
          qui disent la meme chose separes par un vide, c'est le vide qu'on
          remarque. */}
      {entete && (
        <>
          <h2 className="t-display">{PRICING.title}</h2>
          <p className="t-lead mt-5">{PRICING.subtitle}</p>
        </>
      )}

      {/* Un TABLEAU comparatif, et non trois cartes flottantes : un dirigeant
          compare des colonnes, il ne lit pas trois fiches l'une après l'autre.

          Défilement horizontal sur petit écran plutôt qu'un second rendu en
          blocs : deux rendus du même contenu doubleraient chaque libellé dans
          la page, donc pour un lecteur d'écran aussi. */}
      <Defilement
        className={entete ? 'mt-10' : ''}
        libelle="Comparaison des offres, défilement horizontal"
      >
        {/* `aria-label` plutôt qu'un `<caption>` masqué : un caption en
            position absolue s'échappe de son conteneur à défilement et élargit
            la PAGE de 123 px au téléphone. Mesuré, pas supposé. */}
        <table
          className="tableau min-w-[640px]"
          aria-label="Comparaison des offres : prix, quotas et fonctionnalités incluses"
        >
          <thead>
            <tr>
              <th scope="col" className="w-2/6 align-bottom">
                Ce que vous obtenez
              </th>
              {affichees.map((plan) => (
                <th
                  key={plan.code}
                  scope="col"
                  className={`align-bottom ${plan.is_highlighted ? 'bg-brand-50' : ''}`}
                >
                  {plan.is_highlighted && (
                    <span className="mb-1.5 block text-brand-700">Le plus demandé</span>
                  )}
                  <span className="t-title block normal-case tracking-normal">{plan.name}</span>
                  {plan.tagline && (
                    <span className="t-meta mt-1 block font-normal normal-case tracking-normal">
                      {plan.tagline}
                    </span>
                  )}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            <tr>
              <th scope="row" className="normal-case tracking-normal text-ink-800">
                Par mois
              </th>
              {affichees.map((plan) => (
                <td key={plan.code} className={plan.is_highlighted ? 'bg-brand-50' : ''}>
                  {plan.is_quote_only ? (
                    <span className="text-lg font-semibold text-ink-900">{PRICING.quoteLabel}</span>
                  ) : (
                    <>
                      <span className="n text-xl font-semibold text-ink-900">
                        {Math.round(Number(plan.price_monthly))} {PRICING.currency}
                      </span>
                      <span className="t-meta"> / mois</span>
                    </>
                  )}
                </td>
              ))}
            </tr>

            <tr>
              <th scope="row" className="normal-case tracking-normal text-ink-800">
                Ce qui est compté
              </th>
              {affichees.map((plan) => (
                <td key={plan.code} className={plan.is_highlighted ? 'bg-brand-50' : ''}>
                  {/* Les libellés sont DÉRIVÉS des champs de l'offre : aucun
                      nombre n'est recopié à la main. Voir ADR-013. */}
                  <ul className="space-y-1.5">
                    {quotaLines(plan).map((ligne) => (
                      <li key={ligne} className="text-ink-800">
                        {ligne}
                      </li>
                    ))}
                  </ul>
                </td>
              ))}
            </tr>

            {fonctionnalitesComparees(affichees).map((libelle) => (
              <tr key={libelle}>
                <th scope="row" className="font-normal normal-case tracking-normal text-ink-700">
                  {libelle}
                </th>
                {affichees.map((plan) => {
                  const inclus = (plan.features || []).some((f) => f.label === libelle)
                  return (
                    <td key={plan.code} className={plan.is_highlighted ? 'bg-brand-50' : ''}>
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
              <td />
              {affichees.map((plan) => (
                <td key={plan.code} className={plan.is_highlighted ? 'bg-brand-50' : ''}>
                  <Link
                    to="/demonstration"
                    className={`transition-smooth inline-block rounded-md px-4 py-2.5 text-center text-sm font-semibold ${
                      plan.is_highlighted
                        ? 'bg-brand-600 text-white hover:bg-brand-700'
                        : 'border border-ink-300 text-ink-800 hover:bg-ink-100'
                    }`}
                  >
                    Demander une démonstration
                  </Link>
                </td>
              ))}
            </tr>
          </tbody>
        </table>
      </Defilement>
      <p className="t-meta mt-8 max-w-2xl">{PRICING.disclaimer}</p>

      {/* La page n'était qu'un tableau et deux phrases. Ce qui est commun à
          toutes les offres se montre, au lieu de se déduire des colonnes. */}
      <div className="mt-14 grid items-center gap-10 lg:grid-cols-2 lg:gap-16">
        <div>
          <h2 className="t-title text-xl sm:text-2xl">Quelle que soit l’offre</h2>
          <p className="t-body mt-3 text-base">
            Le diagnostic, le plan d’action priorisé et la météo quotidienne sont dans toutes les
            offres. Ce qui change d’une colonne à l’autre, ce sont les volumes engagés et les
            fonctions d’analyse — jamais le fait d’être prévenu.
          </p>
          <p className="t-meta mt-4">
            Aucune offre ne promet plus d’emplacements de surveillance que la plateforme ne peut en
            honorer : une activation qui dépasserait le plafond partagé est refusée avant
            enregistrement, pas après.
          </p>
        </div>
        <BrowserFrame
          src="/screenshots/plan-action.webp"
          alt="Le plan d’action : les actions classées par rapport impact/effort, en trois colonnes — à faire, en cours, fait."
          caption="Capture réelle. Valeurs d’exemple."
          url="rssiasservice.online/plan-action"
        />
      </div>
    </Acte>
  )
}

/* ================================================================== *
 * LES QUESTIONS
 * ================================================================== */
function Question({ item, ouvert, basculer, identifiant }) {
  return (
    <div className="border-b border-ink-200">
      <h3>
        <button
          type="button"
          onClick={basculer}
          aria-expanded={ouvert}
          aria-controls={identifiant}
          className="flex w-full items-start justify-between gap-6 py-5 text-left"
        >
          <span className="text-base font-semibold text-ink-900">{item.question}</span>
          <span aria-hidden="true" className="n mt-0.5 shrink-0 text-lg text-ink-500">
            {ouvert ? '−' : '+'}
          </span>
        </button>
      </h3>
      <div id={identifiant} hidden={!ouvert}>
        <p className="t-body max-w-3xl pb-5">{item.answer}</p>
      </div>
    </div>
  )
}

export function Questions({
  items = FAQ.items,
  titre = FAQ.title,
  chapeau = null,
  fond = 'haute',
  pleinePage = false,
}) {
  const [ouvert, setOuvert] = useState(null)

  const liste = items.map((item, rang) => (
    <Question
      key={item.question}
      item={item}
      identifiant={`question-${rang}`}
      ouvert={ouvert === rang}
      basculer={() => setOuvert(ouvert === rang ? null : rang)}
    />
  ))

  // En PLEINE PAGE, les questions gardent leur colonne de lecture : un texte
  // de réponse à 1 400 px de large ne se lit pas. En bloc SECONDAIRE, elles
  // passent en deux colonnes — titre à gauche, questions à droite — comme le
  // reste de la grammaire, au lieu de laisser la moitié droite vide.
  if (pleinePage) {
    return (
      <Acte id="questions" fond={fond}>
        <h2 className="t-display">{titre}</h2>
        {chapeau && <p className="t-lead mt-5">{chapeau}</p>}
        <div className="mt-8 max-w-4xl">{liste}</div>
      </Acte>
    )
  }

  return (
    <Acte id="questions" fond={fond}>
      <div className="grid gap-8 lg:grid-cols-[minmax(0,0.8fr)_minmax(0,1.2fr)] lg:gap-16">
        <div>
          <h2 className="t-display">{titre}</h2>
          {chapeau && <p className="t-body mt-4">{chapeau}</p>}
        </div>
        <div>{liste}</div>
      </div>
    </Acte>
  )
}

/* ================================================================== *
 * L'ACTION FINALE — la même sur toutes les pages.
 * ================================================================== */
export function Fin() {
  return (
    <Acte id="voir" fond="creuse">
      <div className="mx-auto max-w-3xl text-center">
        <h2 className="t-display">Voir le produit sur vos propres domaines</h2>
        <p className="t-lead mx-auto mt-5">
          Une démonstration dure une vingtaine de minutes, en partage d’écran. Nous vous montrons
          l’interface réelle et répondons à vos questions.
        </p>
        <div className="mt-8 flex justify-center">
          <Action />
        </div>
      </div>
    </Acte>
  )
}
