import {
  ArrowRight,
  CloudLightning,
  CloudSun,
  Download,
  FileText,
  ShieldAlert,
  Sun,
} from 'lucide-react'
import { useCallback, useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { actionsApi, assessmentsApi, authApi, monitoringApi, reportingApi } from '../api/endpoints'
import { lectureDuScore, lectureEnTete } from '../components/DisplayProfile'
import Jauge from '../components/instrument/Jauge'
import Serie from '../components/instrument/Serie'
import { CRANS, cranDe } from '../components/instrument/crans'
import { useDisplayProfile } from '../context/useDisplayProfile'
import { useEtatSurveillance } from '../context/EtatSurveillance'
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
 *
 * LES DEUX PROFILS NE SONT PLUS DEUX VOCABULAIRES, CE SONT DEUX ÉCRANS.
 *
 * C'est la thèse de la direction visuelle (ADR-042) : le réseau électrique
 * publie Ecowatt — une couleur, une phrase, une action — et éCO2mix — des
 * courbes, un curseur, des filtres, un export. Même donnée, à la même
 * seconde, deux surfaces.
 *
 *   Dirigeant : le signal. Une jauge en grand, trois chiffres, ce qu'il faut
 *   décider cette semaine, une seule courbe. Ni sélecteur de période, ni
 *   export, ni tableau — un dirigeant ne fait pas de l'analyse, il tranche.
 *
 *   Technique : la console. Les cinq indicateurs, le sélecteur de période, les
 *   quatre courbes, les alertes détaillées, les deux exports.
 *
 * Les CHIFFRES sont les mêmes des deux côtés, lus de la même réponse : jamais
 * deux valeurs différentes pour la même chose, c'est la première règle du
 * produit.
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
  // Un écran qui n'affiche RIEN pendant qu'il charge se lit comme une panne.
  // C'est exactement le « trou blanc » qu'on reprochait à la version
  // précédente : le bloc d'indicateurs restait absent, sans rien dire.
  const [indicateursEnCours, setIndicateursEnCours] = useState(true)
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

  const { isTechnical: technique } = useDisplayProfile()
  // Le bandeau qui coiffe l'application n'a que la surveillance ; cet ecran a
  // le score d'exposition. On le lui donne plutot que de le laisser afficher
  // une lecture plus pauvre que celle qui est sous les yeux.
  const { preciser } = useEtatSurveillance()

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
    setIndicateursEnCours(true)
    try {
      const reponse = await reportingApi.dashboard(parametresDePeriode(periode, personnalisee))
      setDonnees(reponse.data)
    } catch (err) {
      showToast({
        type: 'error',
        message: err.response?.data?.detail || 'Impossible de charger les indicateurs.',
      })
    } finally {
      setIndicateursEnCours(false)
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [periode, personnalisee.start, personnalisee.end])

  useEffect(() => {
    if (!donnees) return
    const cran = cranDe(donnees.exposure.exposure_score)
    preciser({
      score: donnees.exposure.exposure_score,
      niveau: cran?.cle,
      phrase: `Score d’exposition ${donnees.exposure.exposure_score}/100 — ${lectureDuScore(
        donnees.exposure.exposure_score,
        'exposure'
      )}.`,
      action: { vers: '/exposition', libelle: 'Voir l’exposition' },
    })
  }, [donnees, preciser])

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
    <div className="space-y-6" data-densite={technique ? 'compacte' : 'confortable'}>
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <h1 className="t-display">Tableau de bord</h1>
          <p className="t-meta mt-1">
            {technique
              ? 'Indicateurs, évolutions et alertes détaillées sur la période choisie.'
              : 'Où vous en êtes, ce qui bouge, et ce qu’il faut décider cette semaine.'}
          </p>
        </div>
        {/* Les exports sont une affaire de console : un dirigeant ne
            télécharge pas un tableur, il demande un rapport. Le rapport de
            comité reste donc des deux côtés, le tableur non. */}
        <div className="flex flex-wrap gap-2">
          {technique && (
            <Button
              variant="secondary"
              icon={Download}
              disabled={telechargement !== null || !donnees}
              onClick={() => exporter('csv')}
              aria-label="Exporter les chiffres de la période en tableur"
            >
              Tableur
            </Button>
          )}
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

      {/* Lot C, point 21 : l'accueil reste là, en format compact, tant que les
          trois étapes ne sont pas franchies. */}
      {accueilEnCours && (
        <PremiersPas
          compact
          aUnActif={aUnActif}
          aUnDiagnostic={aDesDonnees}
          resultatCompris={resultatCompris}
          onMasquer={() => franchir('dismissed')}
        />
      )}

      {!donnees && indicateursEnCours && (
        <div className="grid gap-4 lg:grid-cols-3" aria-busy="true" data-loading="true">
          <SkeletonCard className="lg:col-span-3" />
          <SkeletonCard />
          <SkeletonCard />
          <SkeletonCard />
        </div>
      )}

      {!donnees && !indicateursEnCours && (
        <div className="panneau p-6">
          <p className="t-body">
            Les indicateurs de la période n’ont pas pu être chargés. Le reste de l’écran
            reste utilisable, et le rapport de comité porte sur les mêmes chiffres.
          </p>
          <Button className="mt-4" onClick={chargerIndicateurs}>
            Réessayer
          </Button>
        </div>
      )}

      {donnees && !technique && (
        <SignalDirigeant
          donnees={donnees}
          meteo={meteo}
          nombreActifs={surveillance.length}
          alertes={alertesOuvertes}
          actions={prochainesActions}
        />
      )}

      {donnees && technique && (
        <ConsoleTechnique
          donnees={donnees}
          periode={periode}
          setPeriode={setPeriode}
          personnalisee={personnalisee}
          setPersonnalisee={setPersonnalisee}
          meteo={meteo}
          nombreActifs={surveillance.length}
          alertes={alertesOuvertes}
          actions={prochainesActions}
        />
      )}
    </div>
  )
}

/* ================================================================== *
 * PROFIL DIRIGEANT : le signal.
 *
 * Une jauge en grand, trois chiffres, ce qu'il faut decider, une courbe.
 * Aucun panneau ne peut etre vide : chacun dit ce qu'il dirait s'il avait
 * quelque chose a dire, et pourquoi il n'a rien. Un cadre blanc au milieu
 * d'un tableau de bord se lit comme une panne.
 * ================================================================== */
function SignalDirigeant({ donnees, meteo, nombreActifs, alertes, actions }) {
  const cran = cranDe(donnees.exposure.exposure_score)

  return (
    <>
      <div className="panneau">
        <div className="panneau-tete">
          <span className="t-legende">Votre exposition aujourd’hui</span>
          <span className="t-meta">
            Du {formatJour(donnees.period.start)} au {formatJour(donnees.period.end)}
          </span>
        </div>
        <div className="panneau-corps grid gap-8 lg:grid-cols-[minmax(0,260px)_minmax(0,1fr)]">
          <div>
            <Jauge score={donnees.exposure.exposure_score} libelle="Score d’exposition" anime />
            <p className="t-body mt-4">
              {lectureEnTete(donnees.exposure.exposure_score, 'exposure')}. Plus le score est bas,
              mieux c’est.
            </p>
          </div>
          <Serie
            points={(donnees.exposure.score_series || []).map((point) => ({
              valeur: point.score,
              libelle: formatJour(point.date ?? point.day ?? point.label),
            }))}
            legende="Évolution sur la période"
            couleur={cran?.trait}
          />
        </div>
      </div>

      <div className="grid gap-4 sm:grid-cols-3">
        <Resume
          titre="Compromissions ouvertes"
          valeur={donnees.exposure.open_total}
          phrase={
            donnees.exposure.open_total === 0
              ? 'Rien qui circule et qui ne soit pas traité.'
              : `Dont ${donnees.exposure.open_by_severity.critical} critique(s), à traiter en priorité.`
          }
          lien="/compromissions"
          libelleLien="Voir les compromissions"
        />
        <Resume
          titre="Plan d’action"
          valeur={formatNombre(donnees.action_plan.completion_rate, ' %')}
          phrase={
            donnees.action_plan.total === 0
              ? 'Aucun plan d’action pour l’instant.'
              : `${donnees.action_plan.done} action(s) faite(s) sur ${donnees.action_plan.total}, dont ${donnees.action_plan.overdue} en retard.`
          }
          lien="/plan-action"
          libelleLien="Voir le plan"
        />
        <Resume
          titre="Vos sites"
          valeur={
            nombreActifs === 0 ? '—' : formatNombre(donnees.monitoring.uptime_percentage, ' %')
          }
          phrase={
            nombreActifs === 0
              ? 'Aucun actif déclaré : il n’y a encore rien à surveiller.'
              : `${meteo.label.toLowerCase()} — ${nombreActifs} actif(s) surveillé(s).`
          }
          lien="/surveillance"
          libelleLien="Voir la surveillance"
        />
      </div>

      <APremier alertes={alertes} actions={actions} />
    </>
  )
}

/** Un chiffre, et la phrase qui dit ce qu'il veut dire. Jamais l'un sans l'autre. */
function Resume({ titre, valeur, phrase, lien, libelleLien }) {
  return (
    <div className="panneau p-4">
      <p className="t-legende">{titre}</p>
      <p className="n mt-1.5 text-3xl text-ink-900">{valeur}</p>
      <p className="t-body mt-2">{phrase}</p>
      <Link
        to={lien}
        className="t-menu mt-3 inline-flex items-center gap-1 text-brand-600 underline underline-offset-4 hover:text-brand-700"
      >
        {libelleLien}
        <ArrowRight className="size-4" aria-hidden="true" />
      </Link>
    </div>
  )
}

/**
 * A TRAITER EN PREMIER : le panneau qui ne peut pas etre vide.
 *
 * Sa version precedente laissait un cadre blanc quand il n'y avait ni alerte
 * ni action rapide : le lecteur ne pouvait pas distinguer "rien a faire" de
 * "le chargement a echoue". Ici l'absence est un MESSAGE, avec ce qu'elle
 * signifie et ou aller ensuite.
 */
function APremier({ alertes, actions }) {
  const lignes = [
    ...alertes.slice(0, 3).map((alerte) => ({
      cle: `alerte-${alerte.id}`,
      cran: alerte.severity === 'critical' ? 'critique' : 'preoccupant',
      titre: alerte.actif,
      phrase: alerte.recommended_action || 'Une alerte est ouverte sur cet actif.',
      lien: '/surveillance',
    })),
    ...actions.slice(0, 3).map((item) => ({
      cle: `action-${item.id}`,
      cran: 'surveille',
      titre: item.measure.statement || item.measure.official_title,
      phrase: 'Fort impact, peu d’effort : c’est le meilleur rapport du moment.',
      lien: '/plan-action',
    })),
  ]

  return (
    <div className="panneau">
      <div className="panneau-tete">
        <span className="t-legende">À traiter en premier</span>
        {lignes.length > 0 && <span className="n t-meta">{lignes.length}</span>}
      </div>
      <div className="panneau-corps">
        {lignes.length === 0 ? (
          <div>
            <p className="t-body">
              Rien n’attend de décision de votre part aujourd’hui : aucune alerte
              ouverte, et aucune action à fort impact et faible effort en attente.
            </p>
            <p className="t-meta mt-2">
              Ce panneau se remplit tout seul dès qu’un contrôle échoue ou qu’un
              diagnostic produit de nouvelles actions.
            </p>
            <Link
              to="/plan-action"
              className="t-menu mt-4 inline-flex items-center gap-1 text-brand-600 underline underline-offset-4"
            >
              Voir le plan d’action complet
              <ArrowRight className="size-4" aria-hidden="true" />
            </Link>
          </div>
        ) : (
          <ul>
            {lignes.map((ligne) => {
              const cran = CRANS[ligne.cran]
              return (
                <li key={ligne.cle} className="ligne-liste py-3 first:pt-0">
                  <Link to={ligne.lien} className="group block">
                    <p className={`flex items-center gap-1.5 text-xs font-semibold ${cran.texte}`}>
                      <span aria-hidden="true">{cran.glyphe}</span>
                      {cran.nom}
                    </p>
                    <p className="mt-0.5 text-sm font-semibold text-ink-900 group-hover:underline">
                      {ligne.titre}
                    </p>
                    <p className="t-body mt-0.5">{ligne.phrase}</p>
                  </Link>
                </li>
              )
            })}
          </ul>
        )}
      </div>
    </div>
  )
}

/* ================================================================== *
 * PROFIL TECHNIQUE : la console.
 * ================================================================== */
function ConsoleTechnique({
  donnees,
  periode,
  setPeriode,
  personnalisee,
  setPersonnalisee,
  meteo,
  nombreActifs,
  alertes,
  actions,
}) {
  return (
    <>
      {donnees.exposure.open_by_severity.critical > 0 && (
        <Link
          to="/compromissions"
          className="transition-smooth flex items-center gap-3 rounded-md border border-risk-critical-border bg-risk-critical-surface px-4 py-3"
        >
          <ShieldAlert className="size-5 shrink-0 text-risk-critical" aria-hidden="true" />
          <p className="flex-1 text-sm font-semibold text-risk-critical">
            {donnees.exposure.open_by_severity.critical} compromission(s) critique(s) ouverte(s) —
            action immédiate recommandée.
          </p>
          <ArrowRight className="size-4 shrink-0 text-risk-critical" aria-hidden="true" />
        </Link>
      )}

      <div className="space-y-2">
        <SelecteurDePeriode
          periodes={donnees.available_periods}
          courante={periode}
          onChange={setPeriode}
          personnalisee={personnalisee}
          onPersonnalisee={setPersonnalisee}
        />
        {/* La comparaison est affichée PAR DÉFAUT : un chiffre seul ne dit pas
            si le travail a porté. */}
        <p className="t-meta">
          Du {formatJour(donnees.period.start)} au {formatJour(donnees.period.end)}, comparé aux{' '}
          {donnees.period.days} jours précédents.
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
        Le score d’exposition et le score de maturité ne s’additionnent pas : le premier
        mesure ce qui circule à votre sujet, le second ce que vous avez mis en place.
      </p>

      {/* Quatre courbes, quatre questions. Aucune n'est dessinee quand elle
          n'aurait rien à montrer. */}
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
            {
              cle: 'treated',
              nom: 'Traitées depuis le début de la période',
              couleur: COULEUR_SECONDE,
            },
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

      {/* `items-start` : sans lui, le panneau de météo s'étire à la hauteur de
          la liste d'alertes et laisse un grand vide sous ses deux lignes. Un
          cadre à moitié vide se lit comme un contenu manquant. */}
      <div className="grid items-start gap-4 lg:grid-cols-3">
        <div className="panneau">
          <div className="panneau-tete">
            <span className="t-legende">Météo du jour</span>
          </div>
          <div className="panneau-corps">
            {nombreActifs === 0 ? (
              <p className="t-body">
                Aucun actif surveillé.{' '}
                <Link to="/surveillance" className="text-brand-600 underline underline-offset-4">
                  Déclarer un actif
                </Link>
              </p>
            ) : (
              <div className="flex items-center gap-4">
                <meteo.icon className={`size-9 ${meteo.color}`} aria-hidden="true" />
                <div>
                  <p className="text-base font-semibold text-ink-900">{meteo.label}</p>
                  <p className="t-meta">{nombreActifs} actif(s) surveillé(s)</p>
                </div>
              </div>
            )}
          </div>
        </div>

        <div className="panneau lg:col-span-2">
          <div className="panneau-tete">
            <span className="t-legende">Alertes ouvertes</span>
            {alertes.length > 0 && <span className="n t-meta">{alertes.length}</span>}
          </div>
          <div className="panneau-corps">
            {alertes.length === 0 ? (
              <p className="t-body">
                Aucune alerte ouverte. Un actif passe en alerte après trois échecs consécutifs,
                jamais sur une panne passagère.
              </p>
            ) : (
              <ul>
                {alertes.slice(0, 6).map((alerte) => (
                  <li key={alerte.id} className="ligne-liste py-2.5 first:pt-0">
                    <div className="flex items-baseline justify-between gap-3">
                      <span className="n truncate text-sm text-ink-900">{alerte.actif}</span>
                      <Badge variant={alerte.severity === 'critical' ? 'critical' : 'warning'}>
                        {alerte.severity === 'critical' ? 'Critique' : 'Avertissement'}
                      </Badge>
                    </div>
                    {alerte.recommended_action && (
                      <p className="t-meta mt-0.5">{alerte.recommended_action}</p>
                    )}
                  </li>
                ))}
              </ul>
            )}
          </div>
        </div>
      </div>

      <APremier alertes={[]} actions={actions} />
    </>
  )
}
