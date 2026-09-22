import { Link } from 'react-router-dom'
import { CRANS } from './instrument/crans'

/**
 * L'ENVELOPPE D'AUTHENTIFICATION — le pupitre éteint, qu'on vient allumer.
 *
 * Le panneau de gauche est le BÂTI : le même graphite que le rail de
 * l'application et le bandeau d'état. Il ne raconte plus le produit en trois
 * arguments avec une icône devant chacun — il montre l'instrument au repos,
 * avec la graduation des quatre crans. Quelqu'un qui se connecte ici connaît
 * déjà le produit ; ce qu'il lui faut, c'est reconnaître l'endroit.
 *
 * Le formulaire, lui, est sur la face claire. Sous 1024 px le bâti se réduit
 * à la marque en haut : personne ne remplit un mot de passe sous un panneau
 * de présentation.
 */

const CRANS_AFFICHES = ['calme', 'surveille', 'preoccupant', 'critique']

export function Monogramme({ sombre = false }) {
  return (
    <span
      aria-hidden="true"
      className={`grid size-8 shrink-0 place-items-center rounded-sm ${
        sombre ? 'bg-craie text-bati-900' : 'bg-brand-600 text-white'
      }`}
    >
      <span
        className="text-[0.6875rem] font-semibold uppercase leading-none"
        style={{ fontVariationSettings: "'wdth' 70" }}
      >
        net
      </span>
    </span>
  )
}

export default function AuthLayout({ children, title }) {
  return (
    <div className="flex min-h-screen">
      <aside
        aria-label="Présentation du produit"
        className="sur-bati hidden w-[40%] max-w-md flex-col justify-between p-10 lg:flex"
      >
        <Link to="/" className="flex items-center gap-2.5 rounded-sm">
          <Monogramme sombre />
          <span
            className="font-display text-base font-semibold text-craie"
            style={{ fontVariationSettings: "'wdth' 92" }}
          >
            RSSI as a Service
          </span>
        </Link>

        <div>
          <p className="t-display text-craie">
            Ce qui est visible de votre entreprise depuis l’extérieur, relevé
            tous les jours.
          </p>

          {/* La graduation de l'instrument, au repos. Elle dit en un coup
              d'œil ce que le produit mesure et sur quelle échelle — sans
              afficher de valeur, puisqu'il n'y a pas encore de client. */}
          <dl className="mt-10 border-t border-bati-500 pt-5">
            <dt className="t-legende text-craie-douce">Échelle d’exposition</dt>
            <dd className="mt-3 space-y-2.5">
              {CRANS_AFFICHES.map((nom) => (
                <span key={nom} className="flex items-baseline gap-3 text-sm text-craie-douce">
                  <span
                    aria-hidden="true"
                    className="w-3 shrink-0 text-center leading-none"
                    style={{ color: CRANS[nom].trait }}
                  >
                    {CRANS[nom].glyphe}
                  </span>
                  {/* Pas de `truncate` : une phrase coupée à « méritent… » ne
                      dit plus rien. Elle passe à la ligne, le bâti a la place. */}
                  <span className="w-24 shrink-0 text-craie">{CRANS[nom].nom}</span>
                  <span className="text-xs leading-relaxed">{CRANS[nom].phrase}</span>
                </span>
              ))}
            </dd>
          </dl>
        </div>

        <p className="text-xs text-craie-douce">
          © {new Date().getFullYear()} RSSI as a Service
        </p>
      </aside>

      <main className="flex flex-1 flex-col items-center justify-center bg-canvas px-6 py-12">
        <Link to="/" className="mb-8 flex items-center gap-2.5 rounded-sm lg:hidden">
          <Monogramme />
          <span
            className="font-display text-base font-semibold text-ink-900"
            style={{ fontVariationSettings: "'wdth' 92" }}
          >
            RSSI as a Service
          </span>
        </Link>
        <div className="w-full max-w-sm">
          {/* `title` était déjà passé par la page d'invitation, et l'ancienne
              enveloppe le jetait : ces écrans n'avaient donc AUCUN titre de
              premier niveau. Trouvé en reprenant la surface, pas par l'audit —
              axe-core ne réclame pas un h1, il réclame une hiérarchie. */}
          {title && <h1 className="t-display mb-6">{title}</h1>}
          {children}
        </div>
      </main>
    </div>
  )
}
