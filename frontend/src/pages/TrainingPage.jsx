import { Check, Copy, KeyRound, Link2, Trash2, UserPlus } from 'lucide-react'
import { useEffect, useMemo, useState } from 'react'
import { formationApi } from '../api/endpoints'
import Badge from '../components/ui/Badge'
import Button from '../components/ui/Button'
import Card from '../components/ui/Card'
import EmptyState from '../components/ui/EmptyState'
import SearchInput from '../components/ui/SearchInput'
import { filtrerParTexte } from '../utils/recherche'
import Defilement from '../components/ui/Defilement'
import {
  ImportSalaries,
  PropositionsPreuve,
  RapportCampagne,
  ReglagesRelances,
} from '../components/formation/PilotageCampagne'

/**
 * Piloter les formations, depuis l'espace client (F1).
 *
 * Ce que cet écran n'est PAS : un tableau de bord de résultats. Les rapports
 * arrivent en F2 ; ici on compose une campagne — déclarer des salariés, les
 * inscrire, leur transmettre leur lien — et on voit l'état de chacun.
 *
 * Le lien d'un salarié n'apparaît qu'UNE FOIS, à l'émission : il n'est stocké
 * que haché, et le relire est impossible par construction. D'où le bandeau de
 * copie, et le bouton « Réémettre un lien » quand il a été perdu.
 */
export default function TrainingPage() {
  const [catalogue, setCatalogue] = useState([])
  const [salaries, setSalaries] = useState([])
  const [inscriptions, setInscriptions] = useState([])
  const [recherche, setRecherche] = useState('')
  const [lienEmis, setLienEmis] = useState(null)
  const [copie, setCopie] = useState(false)
  const [erreur, setErreur] = useState('')
  const [chargement, setChargement] = useState(true)

  async function recharger() {
    const [c, s, i] = await Promise.all([
      formationApi.catalogue(),
      formationApi.salaries(),
      formationApi.inscriptions(),
    ])
    setCatalogue(c.data)
    setSalaries(s.data)
    setInscriptions(i.data)
    setChargement(false)
  }

  useEffect(() => {
    recharger().catch(() => setChargement(false))
  }, [])

  const filtrees = useMemo(
    () =>
      filtrerParTexte(inscriptions, recherche, (ligne) => [
        ligne.learner.full_name,
        ligne.learner.email,
        ligne.course_title,
      ]),
    [inscriptions, recherche]
  )

  // Un refus du serveur est remonté TEL QUEL : les phrases du module disent
  // quoi faire (« ouvrez un diagnostic », « il manque une colonne »), les
  // résumer les viderait.
  function signaler(err) {
    setErreur(err?.response?.data?.detail ?? 'L’action n’a pas abouti.')
  }

  async function agir(action) {
    setErreur('')
    try {
      await action()
      await recharger()
    } catch (err) {
      setErreur(err.response?.data?.detail ?? 'L’action n’a pas abouti.')
    }
  }

  async function copier(lien) {
    await navigator.clipboard.writeText(lien)
    setCopie(true)
    setTimeout(() => setCopie(false), 2000)
  }

  if (chargement) return null

  return (
    <div className="space-y-6">
      {/* Un titre de premier niveau, qui manquait : axe-core le releve en
          « moderate », donc au seuil du balayage, et sans lui un lecteur
          d'ecran ne sait pas sur quelle page il arrive. */}
      <div>
        <h1 className="t-display">Formation des salariés</h1>
        <p className="t-meta mt-1">
          Des parcours de dix minutes, envoyés par lien personnel. Aucun compte n’est créé,
          et aucun classement des salariés par score n’est produit.
        </p>
      </div>
      {erreur && (
        <p role="alert" className="rounded-lg bg-critical-subtle px-4 py-3 text-sm text-critical-strong">
          {erreur}
        </p>
      )}

      {lienEmis && (
        <Card>
          <h2 className="font-semibold text-ink-900">Le lien de {lienEmis.learner.full_name}</h2>
          <p className="mt-1 text-sm text-ink-600">
            Transmettez-le à {lienEmis.learner.email}. Il n’est affiché qu’une fois : il n’est
            pas conservé en clair. Si vous le perdez, réémettez-en un.
          </p>
          <div className="mt-3 flex flex-col gap-2 sm:flex-row">
            <code className="flex-1 overflow-x-auto rounded-lg border border-ink-200 bg-ink-50 px-3 py-2 text-xs text-ink-800">
              {lienEmis.link}
            </code>
            <Button variant="secondary" onClick={() => copier(lienEmis.link)}>
              {copie ? (
                <Check className="size-4" aria-hidden="true" />
              ) : (
                <Copy className="size-4" aria-hidden="true" />
              )}
              {copie ? 'Copié' : 'Copier'}
            </Button>
            <Button variant="ghost" onClick={() => setLienEmis(null)}>
              Fermer
            </Button>
          </div>
        </Card>
      )}

      {/* F3 — dans cet ordre, et il compte : ce qui demande une décision
          d'abord, ce qui informe ensuite, ce qui se règle une fois à la fin. */}
      <PropositionsPreuve onErreur={signaler} />
      <RapportCampagne onErreur={signaler} />
      <ReglagesRelances onErreur={signaler} />
      <ImportSalaries onImporte={recharger} onErreur={signaler} />

      <NouvelleInscription
        catalogue={catalogue}
        salaries={salaries}
        onSalarieCree={recharger}
        onInscrit={(donnees) => {
          setLienEmis(donnees)
          recharger()
        }}
        onErreur={setErreur}
      />

      <Card>
        <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
          <h2 className="font-semibold text-ink-900">Salariés inscrits</h2>
          <SearchInput
            label="Rechercher un salarié ou un cours"
            value={recherche}
            onChange={setRecherche}
            placeholder="Nom, adresse, cours…"
          />
        </div>

        {filtrees.length === 0 ? (
          <EmptyState
            title={recherche ? 'Aucun résultat' : 'Personne n’est encore inscrit'}
            description={
              recherche
                ? 'Aucun salarié ne correspond à cette recherche.'
                : 'Déclarez un salarié, puis inscrivez-le à un cours.'
            }
          />
        ) : (
          <Defilement className="mt-4">
            <table className="w-full text-sm">
              <caption className="sr-only">
                Salariés inscrits, avec l’état de leur parcours
              </caption>
              <thead>
                <tr className="border-b border-ink-200 text-left text-ink-600">
                  <th scope="col" className="py-2 pr-3 font-medium">Salarié</th>
                  <th scope="col" className="py-2 pr-3 font-medium">Cours</th>
                  <th scope="col" className="py-2 pr-3 font-medium">Échéance</th>
                  <th scope="col" className="py-2 pr-3 font-medium">État</th>
                  <th scope="col" className="py-2 font-medium">
                    <span className="sr-only">Actions</span>
                  </th>
                </tr>
              </thead>
              <tbody>
                {filtrees.map((ligne) => (
                  <tr key={ligne.id} className="border-b border-ink-100">
                    <td className="py-3 pr-3">
                      <div className="font-medium text-ink-900">{ligne.learner.full_name}</div>
                      <div className="text-xs text-ink-500">{ligne.learner.email}</div>
                    </td>
                    <td className="py-3 pr-3 text-ink-700">{ligne.course_title}</td>
                    <td className="py-3 pr-3 tabular-nums text-ink-700">
                      {new Date(ligne.due_date).toLocaleDateString('fr-FR')}
                    </td>
                    <td className="py-3 pr-3">
                      <Etat ligne={ligne} />
                    </td>
                    <td className="py-3">
                      <div className="flex flex-wrap justify-end gap-1">
                        {!ligne.revoked_at && !ligne.passed && (
                          <>
                            <Button
                              variant="ghost"
                              size="sm"
                              onClick={() =>
                                agir(async () => {
                                  const { data } = await formationApi.reemettreLien(ligne.id)
                                  setLienEmis(data)
                                })
                              }
                            >
                              <Link2 className="size-4" aria-hidden="true" />
                              <span className="sr-only sm:not-sr-only">Réémettre un lien</span>
                            </Button>
                            <Button
                              variant="ghost"
                              size="sm"
                              onClick={() => agir(() => formationApi.accorderEssai(ligne.id))}
                            >
                              <KeyRound className="size-4" aria-hidden="true" />
                              <span className="sr-only sm:not-sr-only">Accorder un essai</span>
                            </Button>
                          </>
                        )}
                        {!ligne.revoked_at && (
                          <Button
                            variant="ghost"
                            size="sm"
                            onClick={() => agir(() => formationApi.revoquer(ligne.id))}
                          >
                            <Trash2 className="size-4" aria-hidden="true" />
                            <span className="sr-only sm:not-sr-only">Retirer l’accès</span>
                          </Button>
                        )}
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </Defilement>
        )}
      </Card>
    </div>
  )
}

function Etat({ ligne }) {
  if (ligne.revoked_at) return <Badge variant="neutral">Accès retiré</Badge>
  if (ligne.passed) return <Badge variant="ok">Validé</Badge>
  if (ligne.first_opened_at) return <Badge variant="brand">En cours</Badge>
  return <Badge variant="neutral">Pas encore ouvert</Badge>
}

function NouvelleInscription({ catalogue, salaries, onSalarieCree, onInscrit, onErreur }) {
  const [nom, setNom] = useState('')
  const [email, setEmail] = useState('')
  const [salarieId, setSalarieId] = useState('')
  const [coursSlug, setCoursSlug] = useState('')
  const [echeance, setEcheance] = useState('')
  const [envoi, setEnvoi] = useState(false)

  const champ =
    'mt-1 w-full rounded-md border border-ink-200 px-3 py-2 text-sm focus-visible:outline-2 focus-visible:outline-brand-600'

  async function declarer(event) {
    event.preventDefault()
    onErreur('')
    setEnvoi(true)
    try {
      await formationApi.creerSalarie({ full_name: nom, email })
      setNom('')
      setEmail('')
      await onSalarieCree()
    } catch (err) {
      onErreur(err.response?.data?.detail ?? 'Ce salarié n’a pas pu être déclaré.')
    } finally {
      setEnvoi(false)
    }
  }

  async function inscrire(event) {
    event.preventDefault()
    onErreur('')
    setEnvoi(true)
    try {
      const { data } = await formationApi.inscrire({
        learner_id: salarieId,
        course_slug: coursSlug,
        due_date: echeance,
      })
      setSalarieId('')
      onInscrit(data)
    } catch (err) {
      onErreur(err.response?.data?.detail ?? 'L’inscription n’a pas abouti.')
    } finally {
      setEnvoi(false)
    }
  }

  return (
    <div className="grid gap-4 lg:grid-cols-2">
      <Card>
        <h2 className="font-semibold text-ink-900">Déclarer un salarié</h2>
        <p className="mt-1 text-sm text-ink-600">
          Aucun compte n’est créé : le salarié reçoit un lien personnel.
        </p>
        <form onSubmit={declarer} className="mt-4 space-y-3">
          <div>
            <label className="block text-sm font-medium text-ink-700" htmlFor="nom">
              Nom et prénom
            </label>
            <input
              id="nom"
              className={champ}
              value={nom}
              onChange={(e) => setNom(e.target.value)}
              required
            />
          </div>
          <div>
            <label className="block text-sm font-medium text-ink-700" htmlFor="email">
              Adresse professionnelle
            </label>
            <input
              id="email"
              type="email"
              className={champ}
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              required
            />
          </div>
          <Button type="submit" className="w-full" loading={envoi}>
            <UserPlus className="size-4" aria-hidden="true" />
            Déclarer
          </Button>
        </form>
      </Card>

      <Card>
        <h2 className="font-semibold text-ink-900">Inscrire à un cours</h2>
        <p className="mt-1 text-sm text-ink-600">
          Le lien reste valable jusqu’à l’échéance, plus sept jours.
        </p>
        <form onSubmit={inscrire} className="mt-4 space-y-3">
          <div>
            <label className="block text-sm font-medium text-ink-700" htmlFor="salarie">
              Salarié
            </label>
            <select
              id="salarie"
              className={champ}
              value={salarieId}
              onChange={(e) => setSalarieId(e.target.value)}
              required
            >
              <option value="">Choisir…</option>
              {salaries.map((s) => (
                <option key={s.id} value={s.id}>
                  {s.full_name}
                </option>
              ))}
            </select>
          </div>
          <div>
            <label className="block text-sm font-medium text-ink-700" htmlFor="cours">
              Cours
            </label>
            <select
              id="cours"
              className={champ}
              value={coursSlug}
              onChange={(e) => setCoursSlug(e.target.value)}
              required
            >
              <option value="">Choisir…</option>
              {catalogue.map((c) => (
                <option key={c.slug} value={c.slug}>
                  {c.title} — {c.estimated_minutes} min
                </option>
              ))}
            </select>
          </div>
          <div>
            <label className="block text-sm font-medium text-ink-700" htmlFor="echeance">
              Échéance de la campagne
            </label>
            <input
              id="echeance"
              type="date"
              className={champ}
              value={echeance}
              onChange={(e) => setEcheance(e.target.value)}
              required
            />
          </div>
          <Button type="submit" className="w-full" loading={envoi}>
            Inscrire et obtenir le lien
          </Button>
        </form>
      </Card>
    </div>
  )
}
