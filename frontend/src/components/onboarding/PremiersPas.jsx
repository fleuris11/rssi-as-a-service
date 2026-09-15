import { ArrowRight, CheckCircle2, ClipboardCheck, Info, Lock, Radar, Trophy } from 'lucide-react'
import { Link } from 'react-router-dom'
import FeatureGate from '../FeatureGate'
import Button from '../ui/Button'
import Card from '../ui/Card'

/**
 * La séquence d'accueil d'un nouveau client (lot C, point 21).
 *
 * « Aujourd'hui un client arrive sur un espace vide ou sur un premier scan
 * massif, sans accompagnement. » Trois étapes, dans cet ordre : déclarer un
 * actif, lancer le diagnostic, comprendre son premier résultat.
 *
 * Les deux premières sont LUES dans les données (un actif déclaré, un
 * diagnostic terminé) : l'accueil ne peut pas annoncer « fait » ce qui ne
 * l'est pas. Seule la troisième est mémorisée par personne, côté serveur.
 *
 * Le message sur le premier scan est ici, au moment où le client déclare son
 * premier actif — pas après, quand il découvre des fuites anciennes par
 * dizaines et croit à une catastrophe du jour. C'est ce qui a manqué au
 * premier client réel.
 */
export default function PremiersPas({
  aUnActif,
  aUnDiagnostic,
  resultatCompris,
  compact = false,
  onMasquer,
}) {
  const etapes = [
    {
      cle: 'actif',
      titre: 'Déclarez un actif',
      description:
        'Votre site ou votre domaine de messagerie : c’est ce que la plateforme surveille chaque jour.',
      lien: '/surveillance',
      action: 'Ajouter un actif',
      icone: Radar,
      fait: aUnActif,
    },
    {
      cle: 'diagnostic',
      // Libellé conservé : les parcours de bout en bout le recherchent.
      titre: 'Faites votre diagnostic',
      description: 'Répondez au questionnaire pour connaître votre score de maturité et obtenir votre plan d’action.',
      lien: '/diagnostic',
      action: 'Démarrer le diagnostic',
      icone: ClipboardCheck,
      fait: aUnDiagnostic,
      // Conditionne l'étape à l'offre. Le nom de la clé vient du registre
      // serveur : l'interface n'invente pas de fonctionnalité.
      fonctionnalite: 'anssi_assessment',
    },
    {
      cle: 'resultat',
      titre: 'Comprenez votre premier résultat',
      description: 'Ce que dit votre score, par où commencer, et ce qui peut attendre.',
      lien: '/resultats',
      action: 'Voir mon résultat',
      icone: Trophy,
      fait: resultatCompris,
      // Sans diagnostic terminé, il n'y a pas de résultat à comprendre.
      verrouillee: !aUnDiagnostic,
    },
  ]
  const faites = etapes.filter((e) => e.fait).length

  return (
    <section aria-labelledby="premiers-pas-titre" className="space-y-4">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h2 id="premiers-pas-titre" className="font-display text-lg font-semibold text-ink-900">
            Vos premiers pas
          </h2>
          <p className="mt-0.5 text-sm text-ink-500">
            {faites} étape{faites > 1 ? 's' : ''} sur 3 — trois gestes pour une vision complète de
            votre sécurité.
          </p>
        </div>
        {onMasquer && (
          <Button variant="ghost" size="sm" onClick={onMasquer}>
            Masquer l’accueil
          </Button>
        )}
      </div>

      <ol className={`grid gap-4 ${compact ? 'md:grid-cols-3' : 'md:grid-cols-3'}`}>
        {etapes.map((etape, index) => {
          const lienBouton = (
            <Link to={etape.lien} className="mt-4 block">
              <Button variant={!etape.fait && !etape.verrouillee ? 'primary' : 'secondary'} className="w-full">
                {etape.action}
                <ArrowRight className="size-4" aria-hidden="true" />
              </Button>
            </Link>
          )
          return (
            <li key={etape.cle}>
              <Card className="flex h-full flex-col" padding={compact ? 'p-4' : 'p-6'}>
                <div className="flex items-center justify-between gap-2">
                  <span className="flex items-center gap-2 text-xs font-medium text-brand-600">
                    <span className="flex size-5 items-center justify-center rounded-full bg-brand-100 text-[11px]">
                      {index + 1}
                    </span>
                    Étape {index + 1}
                  </span>
                  {/* L'état est écrit, pas seulement une coche : un lecteur
                      d'écran ne voit pas la couleur. */}
                  {etape.fait ? (
                    <span className="flex items-center gap-1 text-xs font-medium text-ok-strong">
                      <CheckCircle2 className="size-4" aria-hidden="true" />
                      Fait
                    </span>
                  ) : etape.verrouillee ? (
                    <span className="flex items-center gap-1 text-xs text-ink-500">
                      <Lock className="size-3.5" aria-hidden="true" />
                      Après le diagnostic
                    </span>
                  ) : (
                    <span className="text-xs text-ink-500">À faire</span>
                  )}
                </div>
                <div className="mt-3 flex size-10 items-center justify-center rounded-md bg-brand-50 text-brand-700">
                  <etape.icone className="size-5" aria-hidden="true" />
                </div>
                <p className="mt-3 font-display text-base font-semibold text-ink-900">{etape.titre}</p>
                <p className="mt-1 flex-1 text-sm text-ink-500">{etape.description}</p>

                {etape.cle === 'actif' && !etape.fait && (
                  <p className="mt-3 flex items-start gap-1.5 rounded-md bg-brand-50 px-3 py-2 text-xs text-ink-700">
                    <Info className="mt-0.5 size-3.5 shrink-0 text-brand-700" aria-hidden="true" />
                    <span>
                      Le premier scan remonte tout l’historique connu de vos actifs : il peut
                      signaler des fuites anciennes, parfois nombreuses. C’est normal, ce n’est pas
                      un incident du jour — les analyses suivantes ne rapportent que du nouveau.
                    </span>
                  </p>
                )}

                {/* Une étape faite n'offre plus son bouton : « Démarrer le
                    diagnostic » sous un diagnostic terminé inviterait à le
                    refaire. L'état « Fait » est écrit plus haut. */}
                {etape.fait || etape.verrouillee ? null : etape.fonctionnalite ? (
                  // L'étape reste VISIBLE et décrite quand elle est hors offre :
                  // seul son bouton est désactivé, avec l'offre qui la débloque.
                  <FeatureGate feature={etape.fonctionnalite}>{lienBouton}</FeatureGate>
                ) : (
                  lienBouton
                )}
              </Card>
            </li>
          )
        })}
      </ol>
    </section>
  )
}
