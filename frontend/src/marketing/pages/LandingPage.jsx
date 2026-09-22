import { ArrowRight } from 'lucide-react'
import { Link } from 'react-router-dom'
import BandeauEtat from '../../components/instrument/BandeauEtat'
import ChiffreAnime from '../../components/instrument/ChiffreAnime'
import Jauge from '../../components/instrument/Jauge'
import ListeQuiTombe from '../../components/instrument/ListeQuiTombe'
import Serie from '../../components/instrument/Serie'
import { CRANS } from '../../components/instrument/crans'
import BrowserFrame from '../components/BrowserFrame'
import MarketingLayout from '../components/MarketingLayout'
import { DEMONSTRATION, HERO, PREUVES, PROBLEM } from '../content'
import { Acte, Action } from '../atomes'
import { ORGANISATION_JSON_LD, useSeo } from '../useSeo'

/**
 * L'ACCUEIL — six actes, une idée par acte, une seule action répétée.
 *
 * La page tenait sept sections d'un seul tenant et le visiteur s'y perdait.
 * Rien n'a été supprimé : le détail est parti sur /fonctionnalites,
 * /securite-du-produit, /offres et /questions. L'inventaire de ce qui a bougé
 * est dans docs/design.md.
 *
 * Le premier écran ne promet rien, il MONTRE : le pupitre en marche sur les
 * données du client de démonstration. C'est la seule preuve qu'un produit de
 * surveillance puisse donner à quelqu'un qui n'a encore rien déclaré.
 */

/** Un renvoi vers la page qui porte le détail. Jamais une suppression. */
function Approfondir({ vers, children, sombre = false }) {
  return (
    <Link
      to={vers}
      className={`t-menu mt-6 inline-flex items-center gap-1.5 underline underline-offset-4 ${
        sombre ? 'text-action-claire hover:text-craie' : 'text-brand-600 hover:text-brand-700'
      }`}
    >
      {children}
      <ArrowRight className="size-4" aria-hidden="true" />
    </Link>
  )
}

/* ------------------------------------------------------------------ *
 * ACTE 1 — L'instrument en marche.
 * ------------------------------------------------------------------ */
function Accroche() {
  return (
    <Acte id="accroche" fond="haute">
      <div className="grid items-start gap-10 lg:grid-cols-[minmax(0,1fr)_minmax(0,1.05fr)] lg:gap-14">
        <div className="lg:pt-4">
          <h1 className="t-hero">{HERO.title}</h1>
          <p className="t-lead mt-6">{HERO.subtitle}</p>

          <div className="mt-8 flex flex-wrap items-center gap-x-6 gap-y-3">
            <Action />
            <p className="t-meta max-w-xs">{HERO.note}</p>
          </div>
        </div>

        {/* Le pupitre. Tout ce qui s'y affiche vient du client de
            DÉMONSTRATION — une entreprise fictive, jamais un client réel. */}
        <div className="panneau overflow-hidden">
          <div className="panneau-tete">
            <span className="t-legende">{DEMONSTRATION.entreprise}</span>
            <span className="t-legende">Données de démonstration</span>
          </div>
          <div className="panneau-corps">
            <div className="flex flex-wrap items-start justify-between gap-6">
              <Jauge score={DEMONSTRATION.score} niveau={DEMONSTRATION.niveau} anime />
              <dl className="grid grid-cols-2 gap-x-8 gap-y-4 sm:gap-x-12">
                <div>
                  <dt className="t-legende">Actifs suivis</dt>
                  <dd className="n mt-1 text-2xl text-ink-900">
                    <ChiffreAnime valeur={4} />
                  </dd>
                </div>
                <div>
                  <dt className="t-legende">Alertes ouvertes</dt>
                  <dd className="n mt-1 text-2xl text-ink-900">
                    <ChiffreAnime valeur={2} />
                  </dd>
                </div>
              </dl>
            </div>

            <Serie
              className="mt-7"
              points={DEMONSTRATION.serie}
              legende="Exposition, 90 derniers jours"
            />
          </div>

          <div className="border-t border-ink-200 bg-canvas p-4">
            <p className="t-legende mb-2.5">Ce qui est tombé cette semaine</p>
            <ListeQuiTombe>
              {DEMONSTRATION.alertes.map((alerte) => {
                const cran = CRANS[alerte.cran]
                return (
                  <article key={alerte.cle} className="panneau p-3">
                    <p className={`flex items-center gap-1.5 text-xs font-semibold ${cran.texte}`}>
                      <span aria-hidden="true">{cran.glyphe}</span>
                      {cran.nom}
                    </p>
                    <h2 className="mt-1 text-sm font-semibold text-ink-900">{alerte.titre}</h2>
                    <p className="t-meta n mt-0.5">{alerte.corps}</p>
                    <p className="t-meta mt-1.5 text-ink-700">{alerte.traduction}</p>
                  </article>
                )
              })}
            </ListeQuiTombe>
          </div>
        </div>
      </div>
    </Acte>
  )
}

/* ------------------------------------------------------------------ *
 * ACTE 2 — Le problème, sur le bâti : un acte sombre, dense, court.
 * ------------------------------------------------------------------ */
function Probleme() {
  return (
    <Acte id="probleme" fond="bati">
      <div className="grid gap-8 lg:grid-cols-[minmax(0,0.85fr)_minmax(0,1.15fr)] lg:gap-16">
        <h2 className="t-display text-craie">{PROBLEM.title}</h2>
        <div>
          {PROBLEM.items.map((item) => (
            <div key={item.title} className="ligne-liste border-bati-600 py-5 first:pt-0">
              <h3 className="text-base font-semibold text-craie">{item.title}</h3>
              <p className="mt-1.5 text-sm leading-relaxed text-craie-douce">{item.body}</p>
            </div>
          ))}
          <Approfondir vers="/fonctionnalites" sombre>
            Ce que le produit surveille, en détail
          </Approfondir>
        </div>
      </div>
    </Acte>
  )
}

/* ------------------------------------------------------------------ *
 * ACTE 3 — Ce qui arrive sans se connecter.
 * ------------------------------------------------------------------ */
function Recevoir() {
  return (
    <Acte id="recevoir" fond="haute">
      <div className="grid items-center gap-10 lg:grid-cols-2 lg:gap-16">
        <div>
          <h2 className="t-display">
            Un dirigeant n’ouvre pas un outil de sécurité tous les matins. Il ouvre ses emails.
          </h2>
          <p className="t-lead mt-5">
            Le produit vient à vous : une météo quotidienne, une alerte dès qu’un contrôle échoue,
            un signal quand votre exposition publique change. Et vous réglez ce que vous recevez.
          </p>
          <Approfondir vers="/fonctionnalites#alertes">Le détail de chaque envoi</Approfondir>
        </div>
        <BrowserFrame
          src="/screenshots/tableau-de-bord.webp"
          alt="Le tableau de bord du produit sur le client de démonstration : score d’exposition, alertes ouvertes et actions à mener."
          caption="Capture réelle, client de démonstration."
          url="rssiasservice.online/tableau-de-bord"
        />
      </div>
    </Acte>
  )
}

/* ------------------------------------------------------------------ *
 * ACTE 4 — Le diagnostic : par où commencer.
 * ------------------------------------------------------------------ */
function Commencer() {
  return (
    <Acte id="commencer" fond="creuse">
      <div className="grid items-center gap-10 lg:grid-cols-2 lg:gap-16">
        <BrowserFrame
          className="lg:order-2"
          src="/screenshots/diagnostic.webp"
          alt="La restitution du diagnostic ANSSI : score global, score par domaine et mesures qui les composent."
          caption="Capture réelle, client de démonstration."
          url="rssiasservice.online/resultats"
        />
        <div className="lg:order-1">
          <h2 className="t-display">
            La question d’une PME n’est presque jamais « que se passe-t-il ? », c’est « par quoi je
            commence ? ».
          </h2>
          <p className="t-lead mt-5">
            Les 42 mesures du guide d’hygiène informatique de l’ANSSI, un score et le détail de son
            calcul, puis un plan d’action priorisé que vous suivez comme un tableau de tâches.
          </p>
          <p className="t-meta mt-4">Le diagnostic vous aide à progresser ; il ne vous certifie pas.</p>
          <Approfondir vers="/fonctionnalites#diagnostic">
            Comment le diagnostic est construit
          </Approfondir>
        </div>
      </div>
    </Acte>
  )
}

/* ------------------------------------------------------------------ *
 * ACTE 5 — Les faits, sur le bâti.
 *
 * Trois chiffres vérifiables dans le code, aucun chiffre commercial : le
 * produit n'a qu'un client, et tout nombre de clients, de fuites détectées ou
 * de taux de satisfaction serait faux. Un prospect qui vérifie une seule
 * affirmation fausse cesse de croire les autres.
 * ------------------------------------------------------------------ */
function Faits() {
  return (
    <Acte id="faits" fond="bati">
      <h2 className="t-display max-w-2xl text-craie">
        Vous nous confiez des informations sur vos vulnérabilités.
      </h2>
      <dl className="mt-10 grid gap-8 sm:grid-cols-3 sm:gap-10">
        {PREUVES.map((preuve) => (
          <div key={preuve.valeur} className="border-t border-bati-500 pt-4">
            <dt
              className={
                preuve.mesure
                  ? 'n-grand text-craie'
                  : 'font-display text-[clamp(2.5rem,2rem+2.6vw,4rem)] font-bold leading-none tracking-tight text-craie'
              }
            >
              {preuve.valeur}
            </dt>
            <dd className="mt-3 text-sm leading-relaxed text-craie-douce">{preuve.libelle}</dd>
          </div>
        ))}
      </dl>
      <p className="mt-9 max-w-2xl text-sm leading-relaxed text-craie-douce">
        Un mot de passe retrouvé dans une fuite est chiffré dès sa réception. En consulter la valeur
        exacte exige d’être administrateur et de re-prouver son identité à ce moment précis. Chaque
        tentative, acceptée ou refusée, est enregistrée.
      </p>
      <Approfondir vers="/securite-du-produit" sombre>
        Vos données et ce que nous en faisons
      </Approfondir>
    </Acte>
  )
}

/* ------------------------------------------------------------------ *
 * ACTE 6 — L'action finale.
 * ------------------------------------------------------------------ */
function Fin() {
  return (
    <Acte id="voir" fond="haute">
      <div className="mx-auto max-w-3xl text-center">
        <h2 className="t-display">Voir le produit sur vos propres domaines</h2>
        <p className="t-lead mx-auto mt-5">
          Une démonstration dure une vingtaine de minutes, en partage d’écran. Nous vous montrons
          l’interface réelle et répondons à vos questions.
        </p>
        <div className="mt-8 flex flex-wrap items-center justify-center gap-x-6 gap-y-3">
          <Action />
          <Link
            to="/offres"
            className="t-menu text-brand-600 underline underline-offset-4 hover:text-brand-700"
          >
            Voir les offres
          </Link>
        </div>
      </div>
    </Acte>
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
    <MarketingLayout
      bandeau={
        <BandeauEtat
          score={DEMONSTRATION.score}
          niveau={DEMONSTRATION.niveau}
          phrase={`Client de démonstration — ${DEMONSTRATION.phrase}`}
          action={{ vers: '/fonctionnalites', libelle: 'Ce que le produit surveille' }}
        />
      }
    >
      <Accroche />
      <Probleme />
      <Recevoir />
      <Commencer />
      <Faits />
      <Fin />
    </MarketingLayout>
  )
}
