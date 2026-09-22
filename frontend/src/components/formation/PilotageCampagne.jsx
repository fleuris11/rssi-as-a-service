import { BellOff, Download, FileText, Upload, UserRoundSearch } from 'lucide-react'
import { useEffect, useState } from 'react'
import { formationApi } from '../../api/endpoints'
import Badge from '../ui/Badge'
import Button from '../ui/Button'
import Card from '../ui/Card'
import Defilement from '../ui/Defilement'

/**
 * Le pilotage d'une campagne (F3) : relances, import, rapport, preuves.
 *
 * Un principe traverse ces quatre blocs : **l'agrégé d'abord**. Le rapport
 * s'affiche sans qu'on le demande ; le suivi nominatif, non — il faut cliquer,
 * et ce clic est enregistré côté serveur (ADR-041).
 */

const champ =
  'mt-1 w-full rounded-md border border-ink-200 px-3 py-2 text-sm focus-visible:outline-2 focus-visible:outline-brand-600'

function telecharger(reponse, nomParDefaut) {
  const entete = reponse.headers?.['content-disposition'] ?? ''
  const trouve = /filename="([^"]+)"/.exec(entete)
  const url = URL.createObjectURL(new Blob([reponse.data]))
  const lien = document.createElement('a')
  lien.href = url
  lien.download = trouve ? trouve[1] : nomParDefaut
  lien.click()
  URL.revokeObjectURL(url)
}

export function ReglagesRelances({ onErreur }) {
  const [politique, setPolitique] = useState(null)

  useEffect(() => {
    formationApi
      .relances()
      .then(({ data }) => setPolitique(data))
      .catch(() => setPolitique(null))
  }, [])

  async function regler(champs) {
    try {
      const { data } = await formationApi.reglerRelances({ ...politique, ...champs })
      setPolitique(data)
    } catch (err) {
      onErreur(err)
    }
  }

  if (!politique) return null

  return (
    <Card>
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h2 className="font-semibold text-ink-900">Relances automatiques</h2>
          <p className="mt-1 text-sm text-ink-600">
            Trois moments au plus, et chacun se coupe séparément. Un salarié qui a terminé ne
            reçoit plus rien.
          </p>
        </div>
        <Button
          variant={politique.enabled ? 'secondary' : 'primary'}
          size="sm"
          onClick={() => regler({ enabled: !politique.enabled })}
        >
          <BellOff className="size-4" aria-hidden="true" />
          {politique.enabled ? 'Tout couper' : 'Réactiver'}
        </Button>
      </div>

      {politique.enabled && (
        <div className="mt-4 grid gap-3 sm:grid-cols-3">
          <label className="flex items-center gap-2 text-sm text-ink-700">
            <input
              type="checkbox"
              className="size-4"
              checked={politique.mid_course}
              onChange={(event) => regler({ mid_course: event.target.checked })}
            />
            À mi-parcours
          </label>
          <label className="text-sm text-ink-700">
            Jours avant l’échéance
            <input
              type="number"
              min={0}
              max={15}
              className={champ}
              value={politique.before_due_days}
              onChange={(event) => regler({ before_due_days: Number(event.target.value) })}
            />
          </label>
          <label className="text-sm text-ink-700">
            Jours après l’échéance
            <input
              type="number"
              min={0}
              max={7}
              className={champ}
              value={politique.after_due_days}
              onChange={(event) => regler({ after_due_days: Number(event.target.value) })}
            />
          </label>
        </div>
      )}
      {politique.enabled && (
        <p className="mt-2 text-xs text-ink-500">
          Zéro coupe le moment correspondant. Chaque relance porte un lien neuf, qui remplace le
          précédent.
        </p>
      )}
    </Card>
  )
}

export function ImportSalaries({ onImporte, onErreur }) {
  const [contenu, setContenu] = useState('')
  const [resultat, setResultat] = useState(null)
  const [envoi, setEnvoi] = useState(false)

  async function envoyer(event) {
    event.preventDefault()
    setEnvoi(true)
    setResultat(null)
    try {
      const { data } = await formationApi.importer(contenu)
      setResultat(data)
      setContenu('')
      await onImporte()
    } catch (err) {
      onErreur(err)
    } finally {
      setEnvoi(false)
    }
  }

  function lireLeFichier(event) {
    const fichier = event.target.files?.[0]
    if (!fichier) return
    const lecteur = new FileReader()
    lecteur.onload = () => setContenu(String(lecteur.result ?? ''))
    lecteur.readAsText(fichier)
  }

  return (
    <Card>
      <h2 className="font-semibold text-ink-900">Importer une liste</h2>
      <p className="mt-1 text-sm text-ink-600">
        Un nom et une adresse par ligne, séparés par un point-virgule. Les lignes en erreur sont
        signalées une par une : l’import ne s’arrête pas à la première.
      </p>
      <form onSubmit={envoyer} className="mt-4 space-y-3">
        <label className="block text-sm font-medium text-ink-700" htmlFor="fichier-salaries">
          Fichier (CSV)
          <input
            id="fichier-salaries"
            type="file"
            accept=".csv,text/csv,text/plain"
            className={champ}
            onChange={lireLeFichier}
          />
        </label>
        <label className="block text-sm font-medium text-ink-700" htmlFor="colle-salaries">
          …ou collez la liste
          <textarea
            id="colle-salaries"
            rows={4}
            className={champ}
            value={contenu}
            onChange={(event) => setContenu(event.target.value)}
            placeholder="Camille Martin;camille@exemple.fr"
          />
        </label>
        <Button type="submit" loading={envoi} disabled={!contenu.trim()}>
          <Upload className="size-4" aria-hidden="true" />
          Importer
        </Button>
      </form>

      {resultat && (
        <div className="mt-4 space-y-2 text-sm" role="status">
          <p className="text-ink-800">
            {resultat.crees.length} salarié(s) déclaré(s).
            {resultat.deja_presents.length > 0 &&
              ` ${resultat.deja_presents.length} figuraient déjà.`}
          </p>
          {resultat.invalides.length > 0 && (
            <div>
              <p className="font-medium text-ink-900">Lignes non reprises</p>
              <ul className="mt-1 list-disc pl-5 text-ink-700">
                {resultat.invalides.map((ligne) => (
                  <li key={ligne.ligne}>
                    Ligne {ligne.ligne} — {ligne.raison}
                  </li>
                ))}
              </ul>
            </div>
          )}
        </div>
      )}
    </Card>
  )
}

export function RapportCampagne({ onErreur }) {
  const [rapport, setRapport] = useState(null)
  const [suivi, setSuivi] = useState(null)

  useEffect(() => {
    formationApi
      .rapport()
      .then(({ data }) => setRapport(data))
      .catch(() => setRapport(null))
  }, [])

  async function exporter(extension) {
    try {
      const reponse = await formationApi.exportRapport(extension)
      telecharger(reponse, `formation.${extension}`)
    } catch (err) {
      onErreur(err)
    }
  }

  async function voirLeSuivi() {
    try {
      const { data } = await formationApi.suivi()
      setSuivi(data)
    } catch (err) {
      onErreur(err)
    }
  }

  if (!rapport) return null
  const resume = rapport.summary

  return (
    <Card>
      <div className="flex flex-wrap items-start justify-between gap-3">
        <h2 className="font-semibold text-ink-900">Où en sont les équipes</h2>
        <div className="flex gap-2">
          <Button variant="secondary" size="sm" onClick={() => exporter('csv')}>
            <Download className="size-4" aria-hidden="true" />
            Tableur
          </Button>
          <Button variant="secondary" size="sm" onClick={() => exporter('pdf')}>
            <FileText className="size-4" aria-hidden="true" />
            PDF
          </Button>
        </div>
      </div>

      <dl className="mt-4 grid grid-cols-2 gap-3 sm:grid-cols-4">
        {[
          ['Inscrits', resume.learners_total],
          ['N’ont pas commencé', resume.not_started],
          ['Participation', `${resume.participation_rate} %`],
          ['Réussite', `${resume.success_rate} %`],
        ].map(([libelle, valeur]) => (
          <div key={libelle} className="rounded-lg border border-ink-200 p-3">
            <dt className="text-xs text-ink-500">{libelle}</dt>
            <dd className="text-xl font-semibold tabular-nums text-ink-900">{valeur}</dd>
          </div>
        ))}
      </dl>

      {rapport.hardest_questions.length > 0 && (
        <section className="mt-6">
          <h3 className="font-medium text-ink-900">Ce que l’entreprise maîtrise le moins</h3>
          <p className="mt-1 text-sm text-ink-600">
            Les questions les plus souvent ratées. Elles disent ce qu’il faut expliquer
            autrement, plutôt que répéter.
          </p>
          <ul className="mt-3 space-y-2">
            {rapport.hardest_questions.map((question) => (
              <li
                key={question.question_id}
                className="rounded-lg border border-ink-200 p-3 text-sm"
              >
                <div className="flex items-start justify-between gap-3">
                  <span className="text-ink-800">{question.text}</span>
                  <Badge variant={question.failure_rate >= 50 ? 'critical' : 'warning'}>
                    {question.failure_rate} % d’échec
                  </Badge>
                </div>
                <p className="mt-1 text-xs text-ink-500">
                  Écran {question.screen_order} — {question.screen_title}
                </p>
              </li>
            ))}
          </ul>
        </section>
      )}

      {rapport.campaigns.length > 1 && (
        <section className="mt-6">
          <h3 className="font-medium text-ink-900">Campagne après campagne</h3>
          <Defilement className="mt-3">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-ink-200 text-left text-ink-600">
                  <th scope="col" className="py-2 pr-3 font-medium">Cours</th>
                  <th scope="col" className="py-2 pr-3 font-medium">Échéance</th>
                  <th scope="col" className="py-2 pr-3 font-medium">Participation</th>
                  <th scope="col" className="py-2 font-medium">Réussite</th>
                </tr>
              </thead>
              <tbody>
                {rapport.campaigns.map((campagne) => (
                  <tr key={`${campagne.course_id}-${campagne.due_date}`} className="border-b border-ink-100">
                    <td className="py-2 pr-3 text-ink-800">{campagne.course_title}</td>
                    <td className="py-2 pr-3 tabular-nums text-ink-700">
                      {new Date(campagne.due_date).toLocaleDateString('fr-FR')}
                    </td>
                    <td className="py-2 pr-3 tabular-nums text-ink-700">
                      {campagne.participation_rate} %
                    </td>
                    <td className="py-2 tabular-nums text-ink-700">{campagne.success_rate} %</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </Defilement>
        </section>
      )}

      <section className="mt-6 rounded-lg border border-ink-200 bg-ink-50 p-4">
        <h3 className="font-medium text-ink-900">Qui relancer</h3>
        <p className="mt-1 text-sm text-ink-600">
          La liste par salarié sert à relancer. Elle ne comporte aucun résultat individuel, et sa
          consultation est enregistrée.
        </p>
        {suivi ? (
          <ul className="mt-3 space-y-1 text-sm">
            {suivi.results.map((ligne) => (
              <li key={ligne.enrollment_id} className="flex items-center justify-between gap-3">
                <span className="text-ink-800">{ligne.full_name}</span>
                <Badge
                  variant={
                    ligne.state === 'termine'
                      ? 'ok'
                      : ligne.state === 'en_cours'
                        ? 'brand'
                        : 'neutral'
                  }
                >
                  {ligne.state === 'termine'
                    ? 'Terminé'
                    : ligne.state === 'en_cours'
                      ? 'En cours'
                      : 'Pas commencé'}
                </Badge>
              </li>
            ))}
          </ul>
        ) : (
          <Button variant="secondary" size="sm" className="mt-3" onClick={voirLeSuivi}>
            <UserRoundSearch className="size-4" aria-hidden="true" />
            Afficher la liste
          </Button>
        )}
      </section>
    </Card>
  )
}

export function PropositionsPreuve({ onErreur }) {
  const [propositions, setPropositions] = useState([])

  async function recharger() {
    const { data } = await formationApi.preuves()
    setPropositions(data)
  }

  useEffect(() => {
    recharger().catch(() => setPropositions([]))
  }, [])

  async function agir(action) {
    try {
      await action()
      await recharger()
    } catch (err) {
      onErreur(err)
    }
  }

  if (propositions.length === 0) return null

  return (
    <Card>
      <h2 className="font-semibold text-ink-900">Votre formation peut renseigner le diagnostic</h2>
      <p className="mt-1 text-sm text-ink-600">
        Rien n’est coché tant que vous ne l’avez pas confirmé. La preuve sera jointe à la mesure,
        avec ses chiffres et ses dates.
      </p>
      <ul className="mt-4 space-y-3">
        {propositions.map((proposition) => (
          <li key={proposition.id} className="rounded-lg border border-brand-200 bg-brand-50 p-4">
            <p className="font-medium text-ink-900">{proposition.measure_title}</p>
            <p className="mt-1 text-sm text-ink-700">{proposition.evidence}</p>
            <div className="mt-3 flex flex-wrap gap-2">
              <Button
                size="sm"
                onClick={() => agir(() => formationApi.confirmerPreuve(proposition.id))}
              >
                Confirmer et renseigner
              </Button>
              <Button
                variant="ghost"
                size="sm"
                onClick={() => agir(() => formationApi.ecarterPreuve(proposition.id))}
              >
                Écarter
              </Button>
            </div>
          </li>
        ))}
      </ul>
    </Card>
  )
}
