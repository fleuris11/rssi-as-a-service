import { AlertTriangle, Check, Info, X } from 'lucide-react'
import MarketingLayout from '../components/MarketingLayout'
import {
  HOSTING,
  LEGAL_ENTITY,
  RETENTION,
  SECURITY_LIMITS,
  SECURITY_MEASURES,
  SUBPROCESSORS,
  missingEntityFields,
  missingHostingFields,
  orPlaceholder,
} from '../legalConfig'
import { useSeo } from '../useSeo'

/**
 * Pages légales, générées depuis `legalConfig.js`.
 *
 * Ce qui décrit le PRODUIT (ce qu'il transmet, à qui, combien de temps il
 * conserve) est factuel et vérifiable dans le code : ces sections sont
 * complètes. Ce qui relève de l'IDENTITÉ DE L'ÉDITEUR reste à remplir, et
 * s'affiche comme tel — inventer une raison sociale plausible donnerait
 * l'apparence de la conformité sans la substance.
 *
 * Aucune de ces pages n'affirme que le service « est conforme au RGPD » :
 * on décrit ce qui est fait, le lecteur juge.
 */

function PendingBanner({ missing }) {
  if (missing.length === 0) return null
  return (
    <div className="mt-6 flex gap-3 rounded-md border border-warning-strong/30 bg-warning-subtle px-4 py-3">
      <AlertTriangle className="mt-0.5 size-4 shrink-0 text-warning-strong" aria-hidden="true" />
      <div className="text-sm leading-relaxed text-warning-strong">
        <p className="font-medium">Mentions à compléter par l’éditeur</p>
        <p className="mt-1">{missing.join(', ')}.</p>
        <p className="mt-1">
          Le contenu juridique définitif doit être rédigé ou validé par un professionnel du droit.
        </p>
      </div>
    </div>
  )
}

function Section({ heading, children }) {
  return (
    <section>
      <h2 className="font-display text-lg font-semibold text-ink-900">{heading}</h2>
      <div className="mt-2.5 space-y-2.5 text-sm leading-relaxed text-ink-600">{children}</div>
    </section>
  )
}

function LegalNotice() {
  const missing = [...missingEntityFields(), ...missingHostingFields()]
  return (
    <>
      <PendingBanner missing={missing} />
      <div className="mt-10 space-y-9">
        <Section heading="Éditeur du service">
          <p>
            {orPlaceholder(LEGAL_ENTITY.companyName)}
            {LEGAL_ENTITY.legalForm && `, ${LEGAL_ENTITY.legalForm}`}
            {LEGAL_ENTITY.shareCapital && ` au capital de ${LEGAL_ENTITY.shareCapital}`}.
          </p>
          <p>
            Immatriculation : {orPlaceholder(LEGAL_ENTITY.registrationNumber)}
            {LEGAL_ENTITY.vatNumber && ` — TVA : ${LEGAL_ENTITY.vatNumber}`}
          </p>
          <p>
            Siège : {orPlaceholder(LEGAL_ENTITY.address)}{' '}
            {LEGAL_ENTITY.postalCode} {LEGAL_ENTITY.city} {LEGAL_ENTITY.country}
          </p>
        </Section>
        <Section heading="Directeur de la publication">
          <p>{orPlaceholder(LEGAL_ENTITY.publicationDirector)}</p>
        </Section>
        <Section heading="Hébergement">
          <p>
            {orPlaceholder(HOSTING.providerName)} — {orPlaceholder(HOSTING.providerAddress)}
          </p>
          <p>Les données sont hébergées dans l’{HOSTING.dataLocation}.</p>
        </Section>
        <Section heading="Contact">
          <p>{LEGAL_ENTITY.contactEmail}</p>
        </Section>
        <Section heading="Propriété intellectuelle">
          <p>
            L’ensemble des contenus de ce site est protégé. Toute reproduction sans autorisation
            est interdite.
          </p>
        </Section>
      </div>
    </>
  )
}

function PrivacyPolicy() {
  return (
    <div className="mt-10 space-y-9">
      <Section heading="Notre rôle">
        <p>
          Pour les données que vous nous confiez dans le cadre du service, nous agissons comme
          <strong> sous-traitant</strong> au sens du règlement général sur la protection des
          données : vous restez responsable du traitement, nous traitons ces données sur vos
          instructions et pour les seules finalités du service.
        </p>
      </Section>
      <Section heading="Données traitées">
        <p>
          Trois catégories. Vos données de compte (nom, adresse email professionnelle, société,
          fonction). Les actifs que vous déclarez (noms de domaine, sites, domaines de
          messagerie). Les résultats de surveillance, qui peuvent inclure des adresses email et
          des mots de passe retrouvés dans des fuites concernant ces actifs.
        </p>
      </Section>
      <Section heading="Sous-traitants ultérieurs">
        <p>Nous faisons appel aux prestataires suivants, et à eux seuls :</p>
        <div className="overflow-x-auto">
          <table className="mt-2 w-full text-left text-sm">
            <thead>
              <tr className="border-b border-ink-200 text-xs uppercase tracking-wide text-ink-500">
                <th className="py-2 pr-4 font-medium">Rôle</th>
                <th className="py-2 pr-4 font-medium">Prestataire</th>
                <th className="py-2 font-medium">Données transmises</th>
              </tr>
            </thead>
            <tbody>
              {SUBPROCESSORS.map((sub) => (
                <tr key={sub.role} className="border-b border-ink-100 last:border-0 align-top">
                  <td className="py-2.5 pr-4 text-ink-800">{sub.role}</td>
                  <td className="py-2.5 pr-4 text-ink-700">{orPlaceholder(sub.name)}</td>
                  <td className="py-2.5 text-ink-600">{sub.dataShared}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Section>
      <Section heading="Durées de conservation">
        <div className="overflow-x-auto">
          <table className="w-full text-left text-sm">
            <thead>
              <tr className="border-b border-ink-200 text-xs uppercase tracking-wide text-ink-500">
                <th className="py-2 pr-4 font-medium">Donnée</th>
                <th className="py-2 pr-4 font-medium">Durée</th>
                <th className="py-2 font-medium">Précision</th>
              </tr>
            </thead>
            <tbody>
              {RETENTION.map((row) => (
                <tr key={row.data} className="border-b border-ink-100 last:border-0 align-top">
                  <td className="py-2.5 pr-4 text-ink-800">{row.data}</td>
                  <td className="py-2.5 pr-4 text-ink-700">{row.duration}</td>
                  <td className="py-2.5 text-ink-600">{row.note}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Section>
      <Section heading="Droits des personnes">
        <p>
          Les personnes concernées disposent d’un droit d’accès, de rectification, d’effacement,
          de limitation et d’opposition. En tant que sous-traitant, nous relayons ces demandes au
          responsable de traitement (votre entreprise) et l’assistons pour y répondre. Pour nous
          contacter : {LEGAL_ENTITY.contactEmail}.
        </p>
      </Section>
      <Section heading="Mesure d’audience">
        <p>
          Ce site n’utilise aucun traceur publicitaire, aucun cookie tiers et aucun outil de
          mesure d’audience. Aucun consentement n’est donc demandé, faute d’objet.
        </p>
      </Section>
      <Section heading="Contrat de sous-traitance">
        <p>
          Un contrat de sous-traitance (DPA) décrivant nos engagements est{' '}
          <strong>en cours de finalisation juridique</strong> et sera mis à disposition ici. Dans
          l’intervalle, il peut être demandé à {LEGAL_ENTITY.contactEmail}.
        </p>
      </Section>
    </div>
  )
}

function SecurityPage() {
  return (
    <div className="mt-10 space-y-10">
      <p className="text-base leading-relaxed text-ink-700">
        Vous nous confiez des informations sur vos vulnérabilités. Cette page décrit précisément
        ce que nous en faisons, qui y a accès, et ce que nous ne faisons pas.
      </p>

      <Section heading="Notre rôle">
        <p>
          Nous sommes <strong>sous-traitant</strong> : vous restez responsable du traitement.
          Nous n’utilisons vos données pour aucune finalité qui vous soit étrangère — ni
          entraînement de modèle, ni revente, ni enrichissement de base commerciale.
        </p>
      </Section>

      <section>
        <h2 className="font-display text-lg font-semibold text-ink-900">Mesures en place</h2>
        <div className="mt-4 grid gap-5 sm:grid-cols-2">
          {SECURITY_MEASURES.map((measure) => (
            <div key={measure.title} className="flex gap-3">
              <span
                aria-hidden="true"
                className="mt-0.5 flex size-6 shrink-0 items-center justify-center rounded-md bg-ok-subtle text-ok-strong"
              >
                <Check className="size-3.5" />
              </span>
              <div>
                <h3 className="text-sm font-medium text-ink-900">{measure.title}</h3>
                <p className="mt-1 text-sm leading-relaxed text-ink-600">{measure.body}</p>
              </div>
            </div>
          ))}
        </div>
      </section>

      <section>
        <h2 className="font-display text-lg font-semibold text-ink-900">
          Ce que le service ne fait pas
        </h2>
        <p className="mt-2 text-sm text-ink-600">
          Aussi important que ce qu’il fait : une promesse que nous ne tenons pas serait une
          fausse sécurité.
        </p>
        <ul className="mt-4 space-y-2.5">
          {SECURITY_LIMITS.map((limit) => (
            <li key={limit} className="flex gap-3">
              <span
                aria-hidden="true"
                className="mt-0.5 flex size-6 shrink-0 items-center justify-center rounded-md bg-ink-100 text-ink-500"
              >
                <X className="size-3.5" />
              </span>
              <span className="text-sm leading-relaxed text-ink-600">{limit}</span>
            </li>
          ))}
        </ul>
      </section>

      <Section heading="Transferts vers des tiers">
        <p>
          Deux flux sortent de la plateforme, décrits en détail dans la{' '}
          <a href="/confidentialite" className="text-brand-700 underline">
            politique de confidentialité
          </a>
          . Le point essentiel : <strong>aucun mot de passe n’est transmis à quiconque</strong>,
          sous aucune forme, et les données envoyées au service d’analyse sont pseudonymisées
          avant l’envoi puis rétablies à la réception.
        </p>
      </Section>

      <div className="flex gap-3 rounded-md border border-ink-200 bg-ink-50 px-4 py-3">
        <Info className="mt-0.5 size-4 shrink-0 text-ink-500" aria-hidden="true" />
        <p className="text-sm leading-relaxed text-ink-600">
          Cette page décrit des mesures techniques réellement en place, vérifiables lors d’un
          audit. Elle ne constitue pas une attestation de conformité : celle-ci dépend aussi de
          l’usage que vous faites du service et de vos propres mesures.
        </p>
      </div>
    </div>
  )
}

function TermsPage() {
  return (
    <>
      <PendingBanner missing={['Conditions générales complètes']} />
      <div className="mt-10 space-y-9">
        <Section heading="Objet">
          <p>
            Le service fournit une surveillance des fuites de données concernant les actifs
            déclarés par le client, un diagnostic de maturité et des outils d’aide à la décision.
          </p>
        </Section>
        <Section heading="Offres et quotas">
          <p>
            Chaque offre définit un nombre d’actifs surveillés en continu, un volume d’analyses
            mensuelles et un nombre d’utilisateurs. Ces quotas sont indiqués sur la page des
            offres et applicables dès la souscription.
          </p>
        </Section>
        <Section heading="Obligation de déclaration des actifs">
          <p>
            Le client garantit être propriétaire des actifs qu’il déclare, ou dûment mandaté pour
            en demander la surveillance. Aucun actif non déclaré n’est analysé.
          </p>
        </Section>
        <Section heading="Disponibilité">
          <p>
            Aucun engagement de niveau de service (SLA) n’est souscrit à ce stade. Le service ne
            comporte pas d’astreinte : les alertes sont émises par courrier électronique et
            consultables dans l’espace client.
          </p>
        </Section>
        <Section heading="Résiliation et réversibilité">
          <p>
            En cas de suspension ou de résiliation, les données déjà collectées restent
            consultables par le client : seules les fonctionnalités consommant des ressources
            (analyses, surveillance) sont interrompues.
          </p>
        </Section>
        <Section heading="À compléter">
          <p>
            Durée, prix et modalités de paiement, responsabilité, propriété intellectuelle, droit
            applicable et juridiction compétente doivent être rédigés par un professionnel du
            droit avant toute commercialisation.
          </p>
        </Section>
      </div>
    </>
  )
}

const PAGES = {
  legal: {
    title: 'Mentions légales',
    description: 'Mentions légales du service RSSI as a Service.',
    path: '/mentions-legales',
    render: LegalNotice,
  },
  privacy: {
    title: 'Politique de confidentialité',
    description:
      'Données traitées, sous-traitants, durées de conservation et droits des personnes.',
    path: '/confidentialite',
    render: PrivacyPolicy,
  },
  terms: {
    title: 'Conditions générales',
    description: 'Conditions générales d’utilisation et de service.',
    path: '/conditions-generales',
    render: TermsPage,
  },
  security: {
    title: 'Sécurité et traitement des données',
    description:
      'Ce que nous faisons de vos données, qui y accède, combien de temps nous les conservons, et ce que le service ne fait pas.',
    path: '/securite-donnees',
    render: SecurityPage,
  },
  contact: {
    title: 'Contact',
    description: 'Contacter l’équipe RSSI as a Service.',
    path: '/contact',
    render: function ContactPage() {
      return (
        <>
          <PendingBanner missing={missingEntityFields().length ? ['Adresse postale'] : []} />
          <div className="mt-10 space-y-9">
            <Section heading="Demande de démonstration">
              <p>
                Le plus simple est de passer par le formulaire dédié : nous vous recontactons sous
                un jour ouvré.
              </p>
            </Section>
            <Section heading="Questions commerciales ou techniques">
              <p>{LEGAL_ENTITY.contactEmail}</p>
            </Section>
            <Section heading="Signaler une vulnérabilité">
              <p>
                Si vous pensez avoir identifié une faille de sécurité sur ce service, écrivez-nous
                directement plutôt que de la publier. Nous accusons réception et vous tenons
                informé du traitement.
              </p>
            </Section>
            <Section heading="Adresse postale">
              <p>
                {orPlaceholder(LEGAL_ENTITY.address)} {LEGAL_ENTITY.postalCode}{' '}
                {LEGAL_ENTITY.city}
              </p>
            </Section>
          </div>
        </>
      )
    },
  },
}

export default function LegalPage({ page }) {
  const content = PAGES[page]
  useSeo({ title: content.title, description: content.description, path: content.path })
  const Body = content.render

  return (
    <MarketingLayout>
      <div className="mx-auto max-w-3xl px-5 py-16 sm:py-20">
        <h1 className="font-display text-3xl font-semibold text-ink-900">{content.title}</h1>
        <Body />
      </div>
    </MarketingLayout>
  )
}
