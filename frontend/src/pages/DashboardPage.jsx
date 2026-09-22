import {
  ArrowRight,
  CloudLightning,
  CloudSun,
  Download,
  FileText,
  ShieldAlert,
  Sun,
  Zap,
} from 'lucide-react'
import { useCallback, useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { actionsApi, assessmentsApi, authApi, monitoringApi, reportingApi } from '../api/endpoints'
import { lectureDuScore } from '../components/DisplayProfile'
import PremiersPas from '../components/onboarding/PremiersPas'
import { useOptionalAuth } from '../context/AuthContext'
import {
  COULEUR_SECONDE,
  COULEUR_TRAIT,
  Courbe,
  formatJour,
  formatNombre,
  Indicateur,
  SelecteurDePeriode,
} from '../components/reporting/Indicateurs'
import {
  parametresDePeriode,
  periodePrete,
  telechargerReponse,
} from '../components/reporting/telechargement'
import Badge from '../components/ui/Badge'
import Button from '../components/ui/Button'
import Card, { CardHeader } from '../components/ui/Card'
import { SkeletonCard } from '../components/ui/Skeleton'
import { useToast } from '../components/ui/Toast'

/**
 * Le tableau de bord d'un RSSI (lot C, C2).
 *
 * L'objectif n'est pas « ajouter des graphiques » : c'est supprimer la soirée
 * où le RSSI reconstruit ses chiffres à la main avant son comité mensuel. Le
 * tableau de bord donnait un score, deux alertes et des raccourcis — aucune
 * évolution, rien à présenter.
 *
 * Tout ce qui suit lit l'API de restitution (V2-3, ADR-028) : période résolue
 * par le serveur, comparaison à la période précédente, sens des évolutions
 * décidé une fois. L'écran ne recalcule aucun indicateur ; le PDF et le
 * tableur exportent exactement ce qu'il affiche.
 */

const METEO = {
  ok: { icon: Sun, label: 'Tout va bien', color: 'text-ok-strong' },
  warning: { icon: CloudSun, label: 'Points de vigilance', color: 'text-warning-strong' },
  critical: { icon: CloudLightning, label: 'Attention requise', color: 'text-critical-strong' },
}

function pireEtat(lignes) {
  let pire = 'ok'
  for (const ligne of lignes) {
    if (ligne.open_alerts.some((a) => a.severity === 'critical')) return 'critical'
    if (ligne.open_alerts.length > 0) pire = 'warning'
    for (const controle of Object.values(ligne.latest_checks)) {
      if (controle?.status === 'critical') return 'critical'
      if (controle?.status === 'warning') pire = 'warning'
    }
  }
  return pire
}

/** Ce que dit une courbe, en une phrase, entre son premier et son dernier point. */
function tendance(debut, fin, { plusBasEstMieux, unite = '' }) {
  if (debut === null || debut === undefined || fin === null || fin === undefined) return null
  const a = formatNombre(debut, unite)
  const b = formatNombre(fin, unite)
  if (debut === fin) return `Stable sur la période, à ${b}.`
  const monte = fin > debut
  const bonne = plusBasEstMieux ? !monte : monte
  return `De ${a} à ${b} sur la période : ${bonne ? 'c’est une amélioration' : 'c’est une dégradation'}.`
}

export default function DashboardPage() {
  const { showToast } = useToast()
  const [chargement, setChargement] = useState(true)
  const [evaluations, setEvaluations] = useState([])
  const [surveillance, setSurveillance] = useState([])
  const [actions, setActions] = useState([])
  const [periode, setPeriode] = useState('quarter')
  const [personnalisee, setPersonnalisee] = useState({ start: '', end: '' })
  const [donnees, setDonnees] = useState(null)
  const [telechargement, setTelechargement] = useState(null)
  // Lot C, point 21 : ce que l'accueil ne peut pas lire dans les données.
  // `useOptionalAuth` : l'accueil est de la présentation, il ne doit pas
  // faire tomber le tableau de bord rendu hors session.
  const auth = useOptionalAuth()
  const accueil = auth?.user?.onboarding

  async function franchir(etape) {
    try {
      const reponse = await authApi.completeOnboardingStep(etape)
      auth?.setUser?.(reponse.data)
    } catch {
      showToast({ type: 'error', message: 'Ce choix n’a pas pu être enregistré.' })
    }
  }

  const chargerEtat = useCallback(async () => {
    setChargement(true)
    try {
      const [evaluationsRes, surveillanceRes, actionsRes] = await Promise.all([
        assessmentsApi.list(),
        monitoringApi.dashboard(),
        actionsApi.listAll(),
      ])
      setEvaluations(evaluationsRes.data.results.filter((a) => a.status === 'completed'))
      setSurveillance(surveillanceRes.data)
      setActions(actionsRes)
    } catch {
      showToast({
        type: 'error',
        message: 'Impossible de charger le tableau de bord.',
        action: { label: 'Réessayer', onClick: chargerEtat },
      })
    } finally {
      setChargement(false)
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  useEffect(() => {
    chargerEtat()
  }, [chargerEtat])

  const aDesDonnees = evaluations.length > 0

  const chargerIndicateurs = useCallback(async () => {
    try {
      const reponse = await reportingApi.dashboard(parametresDePeriode(periode, personnalisee))
      setDonnees(reponse.data)
    } catch (err) {
      showToast({
        type: 'error',
        message: err.response?.data?.detail || 'Impossible de charger les indicateurs.',
      })
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [periode, personnalisee.start, personnalisee.end])

  useEffect(() => {
    if (!aDesDonnees || !periodePrete(periode, personnalisee)) return
    chargerIndicateurs()
  }, [aDesDonnees, chargerIndicateurs, periode, personnalisee])

  async function exporter(format) {
    setTelechargement(format)
    try {
      const params = parametresDePeriode(periode, personnalisee)
      const reponse =
        format === 'pdf' ? await reportingApi.reportPdf(params) : await reportingApi.exportCsv(params)
      telechargerReponse(reponse, `rapport.${format}`)
    } catch {
      showToast({
        type: 'error',
        message:
          format === 'pdf'
            ? 'Le rapport n’a pas pu être produit. Les mêmes chiffres restent exportables en tableur.'
            : 'L’export n’a pas pu être produit.',
      })
    } finally {
      setTelechargement(null)
    }
  }

  if (chargement) {
    return (
      <div className="grid gap-6 lg:grid-cols-3">
        <SkeletonCard className="lg:col-span-2" />
        <SkeletonCard />
        <SkeletonCard />
      </div>
    )
  }

  // Les deux premières étapes se lisent dans les données : un actif est
  // surveillé, un diagnostic est terminé. Elles ne peuvent pas mentir.
  const aUnActif = surveillance.length > 0
  const resultatCompris = Boolean(accueil?.result_seen)
  const accueilEnCours =
    !accueil?.dismissed && !(aUnActif && aDesDonnees && resultatCompris)

  if (!aDesDonnees) {
    return (
      <div className="space-y-6">
        <div>
          <h1 className="font-display text-2xl font-semibold text-ink-900">
            Bienvenue sur RSSI as a Service
          </h1>
          <p className="mt-1 text-sm text-ink-500">
            Trois étapes pour avoir une vision complète de votre posture cyber.
          </p>
        </div>
        <PremiersPas aUnActif={aUnActif} aUnDiagnostic={false} resultatCompris={false} />
      </div>
    )
  }

  const meteo = METEO[pireEtat(surveillance)]
  const alertesOuvertes = surveillance.flatMap((ligne) =>
    ligne.open_alerts.map((alerte) => ({ ...alerte, actif: ligne.asset.value }))
  )
  const prochainesActions = actions
    .filter((i) => i.status !== 'done' && i.measure.impact === 'high' && i.measure.effort === 'low')
    .slice(0, 3)

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <h1 className="font-display text-2xl font-semibold text-ink-900">Tableau de bord</h1>
          <p className="mt-1 text-sm text-ink-500">
            Où vous en êtes, comment ça évolue, et ce qui reste à faire — prêt pour votre comité.
          </p>
        </div>
        {/* Deux boutons, deux noms accessibles distincts : ce qui part vers une
            direction et ce qui part vers un tableur. */}
        <div className="flex flex-wrap gap-2">
          <Button
            variant="secondary"
            icon={Download}
            disabled={telechargement !== null || !donnees}
            onClick={() => exporter('csv')}
            aria-label="Exporter les chiffres de la période en tableur"
          >
            Tableur
          </Button>
          <Button
            icon={FileText}
            disabled={telechargement !== null || !donnees}
            onClick={() => exporter('pdf')}
            aria-label="Télécharger le rapport de comité de la période en PDF"
          >
            {telechargement === 'pdf' ? 'Génération…' : 'Rapport de comité'}
          </Button>
        </div>
      </div>

      {/* Lot C, point 21 : l'accueil reste là, en format compact, tant que
          les trois étapes ne sont pas franchies — et jusqu'à ce que la
          personne choisisse de le masquer. */}
      {accueilEnCours && (
        <PremiersPas
          compact
          aUnActif={aUnActif}
          aUnDiagnostic={aDesDonnees}
          resultatCompris={resultatCompris}
          onMasquer={() => franchir('dismissed')}
        />
      )}

      {donnees?.exposure.open_by_severity.critical > 0 && (
        <Link
          to="/compromissions"
          className="transition-smooth flex items-center gap-3 rounded-lg border border-critical-strong/20 bg-critical-subtle px-4 py-3 hover:bg-critical-subtle/70"
        >
          <ShieldAlert className="size-5 shrink-0 text-critical-strong" aria-hidden="true" />
          <p className="flex-1 text-sm font-medium text-critical-strong">
            {donnees.exposure.open_by_severity.critical} compromission(s) critique(s) ouverte(s) —
            action immédiate recommandée.
          </p>
          <ArrowRight className="size-4 shrink-0 text-critical-strong" aria-hidden="true" />
        </Link>
      )}

      {donnees && (
        <>
          <div className="space-y-2">
            <SelecteurDePeriode
              periodes={donnees.available_periods}
              courante={periode}
              onChange={setPeriode}
              personnalisee={personnalisee}
              onPersonnalisee={setPersonnalisee}
            />
            {/* La comparaison est affichée PAR DÉFAUT (point 5) : un chiffre
                seul ne dit pas si le travail a porté. */}
            <p className="t-meta">
              Du {formatJour(donnees.period.start)} au {formatJour(donnees.period.end)}, comparé
              aux {donnees.period.days} jours précédents.
            </p>
          </div>

          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-5">
            <Indicateur
              titre="Score d’exposition"
              valeur={`${donnees.exposure.exposure_score}/100`}
              evolution={donnees.exposure.evolution}
              quoi={`Plus bas est mieux — ${lectureDuScore(donnees.exposure.exposure_score, 'exposure')}.`}
              lien="/exposition"
              libelleLien="Voir l’exposition"
            />
            <Indicateur
              titre="Compromissions ouvertes"
              valeur={donnees.exposure.open_total}
              evolution={donnees.exposure.open_evolution}
              quoi={`Dont ${donnees.exposure.open_by_severity.critical} critique(s). Données retrouvées en circulation et pas encore traitées.`}
              lien="/compromissions"
              libelleLien="Voir les compromissions"
            />
            <Indicateur
              titre="Score de maturité"
              valeur={
                donnees.maturity.score === null
                  ? 'non mesuré'
                  : `${formatNombre(donnees.maturity.score)}/100`
              }
              evolution={donnees.maturity.evolution}
              suffixe=" pts"
              quoi={
                donnees.maturity.score === null
                  ? 'Aucun diagnostic terminé.'
                  : `${lectureDuScore(donnees.maturity.score, 'maturity')}. Mesure votre organisation, pas les fuites.`
              }
              lien="/resultats"
              libelleLien="Voir les résultats"
            />
            <Indicateur
              titre="Plan d’action"
              valeur={formatNombre(donnees.action_plan.completion_rate, ' %')}
              evolution={donnees.action_plan.completion_evolution}
              suffixe=" pts"
              quoi={`${donnees.action_plan.done} action(s) terminée(s) sur ${donnees.action_plan.total}, dont ${donnees.action_plan.overdue} en retard.`}
              lien="/plan-action"
              libelleLien="Voir le plan"
            />
            <Indicateur
              titre="Disponibilité"
              valeur={formatNombre(donnees.monitoring.uptime_percentage, ' %')}
              evolution={donnees.monitoring.uptime_evolution}
              suffixe=" pts"
              quoi="Part du temps où vos sites surveillés ont répondu normalement."
              lien="/surveillance"
              libelleLien="Voir la surveillance"
            />
          </div>

          <p className="t-meta">
            Le score d’exposition et le score de maturité ne s’additionnent pas : le premier mesure
            ce qui circule à votre sujet, le second ce que vous avez mis en place.
          </p>

          {/* Quatre courbes, quatre questions (point 10). Aucune n'est dessinée
              quand elle n'aurait rien à montrer. */}
          <div className="grid gap-4 lg:grid-cols-2">
            <Courbe
              titre="Score d’exposition"
              question="Le score d’exposition baisse-t-il ?"
              donnees={donnees.exposure.score_series}
              traits={[{ cle: 'score', nom: 'Score sur 100', couleur: COULEUR_TRAIT }]}
              domaineY={[0, 100]}
              lecture={tendance(
                donnees.exposure.score_series?.[0]?.score,
                donnees.exposure.score_series?.at(-1)?.score,
                { plusBasEstMieux: true, unite: '/100' }
              )}
              vide="Pas assez de recul sur la période pour dessiner une tendance."
            />
            <Courbe
              titre="Compromissions ouvertes et traitées"
              question="Traite-t-on les fuites, ou se contente-t-on de les écarter ?"
              donnees={donnees.exposure.series}
              traits={[
                { cle: 'open', nom: 'Ouvertes', couleur: COULEUR_TRAIT },
                { cle: 'treated', nom: 'Traitées depuis le début de la période', couleur: COULEUR_SECONDE },
              ]}
              lecture={
                donnees.exposure.series?.length
                  ? `${donnees.exposure.series.at(-1).open} encore ouverte(s), ${donnees.exposure.series.at(-1).treated ?? 0} traitée(s) sur la période, ${donnees.exposure.ignored_in_period} écartée(s).`
                  : null
              }
              vide="Aucune compromission sur la période."
            />
            <Courbe
              titre="Score de maturité"
              question="Notre maturité progresse-t-elle ?"
              donnees={donnees.maturity.history}
              traits={[{ cle: 'score', nom: 'Score sur 100', couleur: COULEUR_TRAIT }]}
              domaineY={[0, 100]}
              lecture={tendance(
                donnees.maturity.history?.[0]?.score,
                donnees.maturity.history?.at(-1)?.score,
                { plusBasEstMieux: false, unite: '/100' }
              )}
              vide={
                donnees.maturity.history?.length === 1
                  ? 'Un seul diagnostic terminé sur la période : la tendance apparaîtra au suivant.'
                  : 'Aucun diagnostic terminé sur la période.'
              }
            />
            <Courbe
              titre="Avancement du plan d’action"
              question="Le plan d’action avance-t-il ?"
              donnees={
                donnees.action_plan.series?.some((p) => p.completion_rate !== null)
                  ? donnees.action_plan.series
                  : []
              }
              traits={[{ cle: 'completion_rate', nom: 'Actions terminées (%)', couleur: COULEUR_TRAIT }]}
              domaineY={[0, 100]}
              formatY={(v) => `${v} %`}
              lecture={tendance(
                donnees.action_plan.series?.[0]?.completion_rate,
                donnees.action_plan.series?.at(-1)?.completion_rate,
                { plusBasEstMieux: false, unite: ' %' }
              )}
              vide="Aucun plan d’action sur la période."
            />
          </div>
        </>
      )}

      {/* Aujourd'hui : l'état instantané, sans tendance — la météo et ce qui
          attend une action. */}
      <div className="grid gap-4 lg:grid-cols-3">
        <Card>
          <CardHeader title="Météo du jour" />
          {surveillance.length === 0 ? (
            <p className="text-sm text-ink-500">
              Aucun actif surveillé.{' '}
              <Link to="/surveillance" className="font-medium text-brand-600 hover:text-brand-700">
                Déclarer un actif
              </Link>
            </p>
          ) : (
            <div className="flex items-center gap-4">
              <meteo.icon className={`size-10 ${meteo.color}`} aria-hidden="true" />
              <div>
                <p className="font-display text-base font-semibold text-ink-900">{meteo.label}</p>
                <p className="text-sm text-ink-500">
                  {surveillance.length} actif(s) surveillé(s)
                </p>
              </div>
            </div>
          )}
        </Card>

        <Card>
          <CardHeader
            title="Alertes ouvertes"
            action={
              alertesOuvertes.length > 0 && <Badge variant="critical">{alertesOuvertes.length}</Badge>
            }
          />
          {alertesOuvertes.length === 0 ? (
            <p className="text-sm text-ink-500">Aucune alerte ouverte.</p>
          ) : (
            <ul className="space-y-2.5">
              {alertesOuvertes.slice(0, 4).map((alerte) => (
                <li key={alerte.id} className="text-sm">
                  <div className="flex items-center justify-between gap-3">
                    <span className="truncate text-ink-700">{alerte.actif}</span>
                    <Badge variant={alerte.severity === 'critical' ? 'critical' : 'warning'}>
                      {alerte.severity === 'critical' ? 'Critique' : 'Avertissement'}
                    </Badge>
                  </div>
                  {alerte.recommended_action && (
                    <p className="mt-0.5 line-clamp-2 text-xs text-ink-500">
                      {alerte.recommended_action}
                    </p>
                  )}
                </li>
              ))}
            </ul>
          )}
        </Card>

        <Card>
          <CardHeader title="Prochaines actions" />
          {prochainesActions.length === 0 ? (
            <p className="text-sm text-ink-500">
              Aucune action rapide à fort impact en attente.
            </p>
          ) : (
            <ul className="space-y-1.5">
              {prochainesActions.map((item) => (
                <li key={item.id} className="flex items-start gap-1.5 text-sm text-ink-700">
                  <Zap className="mt-0.5 size-3.5 shrink-0 text-ink-600" aria-hidden="true" />
                  {item.measure.statement || item.measure.official_title}
                </li>
              ))}
            </ul>
          )}
        </Card>
      </div>
    </div>
  )
}
