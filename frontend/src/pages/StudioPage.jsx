import { ArrowDown, ArrowUp, Copy, Eye, Plus, Send, Trash2 } from 'lucide-react'
import { useEffect, useState } from 'react'
import { formationApi } from '../api/endpoints'
import ContenuEcran from '../components/formation/ContenuEcran'
import Badge from '../components/ui/Badge'
import Button from '../components/ui/Button'
import Card from '../components/ui/Card'
import EmptyState from '../components/ui/EmptyState'

/**
 * Le studio : écrire un cours, le prévisualiser, le publier (F2).
 *
 * Deux principes tiennent tout l'écran :
 *
 * - **une version publiée ne se modifie pas.** Quand c'est le cas, l'éditeur
 *   passe en lecture seule et propose d'ouvrir une nouvelle version. Les
 *   salariés en cours de parcours terminent sur la leur ;
 * - **on n'écrit pas une variable qui n'existe pas.** La liste des variables
 *   vient du serveur et s'insère par un bouton, jamais à la main.
 */

const TYPES = [
  { valeur: 'paragraphe', libelle: 'Paragraphe' },
  { valeur: 'titre', libelle: 'Titre' },
  { valeur: 'liste', libelle: 'Liste' },
  { valeur: 'encadre', libelle: 'Encadré' },
  { valeur: 'citation', libelle: 'Citation' },
]

const champ =
  'mt-1 w-full rounded-md border border-ink-200 px-3 py-2 text-sm focus-visible:outline-2 focus-visible:outline-brand-600'

function blocNeuf(type) {
  if (type === 'liste') return { type, items: [''] }
  if (type === 'titre') return { type, niveau: 3, texte: '' }
  if (type === 'encadre') return { type, ton: 'info', texte: '' }
  return { type, texte: '' }
}

/** Un bloc contient-il une variable ? La formulation de repli devient alors
 *  obligatoire — le serveur la refuse sinon, et l'éditeur le dit avant. */
function contientUneVariable(bloc) {
  const textes = [bloc.texte ?? '', ...(bloc.items ?? [])]
  return textes.some((texte) => /\{[a-zA-Z_][a-zA-Z0-9_]*\}/.test(texte))
}

export default function StudioPage() {
  const [donnees, setDonnees] = useState(null)
  const [coursOuvert, setCoursOuvert] = useState(null)
  const [erreur, setErreur] = useState('')
  const [problemes, setProblemes] = useState([])

  async function recharger() {
    const { data } = await formationApi.studioCours()
    setDonnees(data)
    return data
  }

  useEffect(() => {
    recharger().catch(() => setErreur('Le studio n’a pas pu être chargé.'))
  }, [])

  function signaler(err) {
    const data = err.response?.data
    setProblemes(data?.problemes ?? [])
    setErreur(data?.detail ?? 'L’action n’a pas abouti.')
  }

  if (!donnees) return null

  if (coursOuvert) {
    return (
      <Editeur
        coursId={coursOuvert}
        variables={donnees.variables}
        onFermer={() => {
          setCoursOuvert(null)
          setErreur('')
          setProblemes([])
          recharger()
        }}
        erreur={erreur}
        problemes={problemes}
        onErreur={signaler}
        onEffacerErreur={() => {
          setErreur('')
          setProblemes([])
        }}
      />
    )
  }

  return (
    <div className="space-y-6">
      {/* Titre de premier niveau, qui manquait ici aussi. */}
      <div>
        <h1 className="t-display">Studio de formation</h1>
        <p className="t-meta mt-1">
          Créer un cours, le composer écran par écran, le prévisualiser, puis le publier. Une
          version publiée ne change plus : on en publie une nouvelle.
        </p>
      </div>

      {erreur && (
        <p role="alert" className="rounded-md bg-critical-subtle px-4 py-3 text-sm text-critical-strong">
          {erreur}
        </p>
      )}

      <NouveauCours
        onCree={async (titre) => {
          try {
            const { data } = await formationApi.studioCreerCours({ title: titre })
            await recharger()
            setCoursOuvert(data.id)
          } catch (err) {
            signaler(err)
          }
        }}
      />

      <Card>
        <h2 className="font-semibold text-ink-900">Mes cours</h2>
        {donnees.mine.length === 0 ? (
          <EmptyState
            title="Aucun cours pour l’instant"
            description="Écrivez-en un, ou partez d’un cours de la bibliothèque pour l’adapter."
          />
        ) : (
          <ul className="mt-4 divide-y divide-ink-100">
            {donnees.mine.map((cours) => (
              <LigneCours
                key={cours.id}
                cours={cours}
                onOuvrir={() => setCoursOuvert(cours.id)}
                onDupliquer={async () => {
                  try {
                    await formationApi.studioDupliquer(cours.id, {})
                    await recharger()
                  } catch (err) {
                    signaler(err)
                  }
                }}
              />
            ))}
          </ul>
        )}
      </Card>

      <Card>
        <h2 className="font-semibold text-ink-900">Bibliothèque</h2>
        <p className="mt-1 text-sm text-ink-600">
          Des cours prêts à l’emploi. Proposez-les tels quels à vos salariés, ou dupliquez-en un
          pour l’adapter à votre maison — la copie devient la vôtre.
        </p>
        {donnees.library.length === 0 ? (
          <EmptyState title="La bibliothèque est vide" description="Aucun cours publié pour l’instant." />
        ) : (
          <ul className="mt-4 divide-y divide-ink-100">
            {donnees.library.map((cours) => (
              <LigneCours
                key={cours.id}
                cours={cours}
                bibliotheque
                onDupliquer={async () => {
                  try {
                    const { data } = await formationApi.studioDupliquer(cours.id, {})
                    await recharger()
                    setCoursOuvert(data.id)
                  } catch (err) {
                    signaler(err)
                  }
                }}
              />
            ))}
          </ul>
        )}
      </Card>
    </div>
  )
}

function LigneCours({ cours, bibliotheque = false, onOuvrir, onDupliquer }) {
  return (
    <li className="flex flex-col gap-2 py-3 sm:flex-row sm:items-center sm:justify-between">
      <div>
        <div className="font-medium text-ink-900">{cours.title}</div>
        <div className="mt-1 flex flex-wrap items-center gap-2 text-xs text-ink-500">
          {cours.published_version ? (
            <Badge variant="ok">Publié — version {cours.published_version}</Badge>
          ) : (
            <Badge variant="neutral">Jamais publié</Badge>
          )}
          {cours.draft_version && <Badge variant="brand">Brouillon v{cours.draft_version}</Badge>}
          <span>{cours.screens} écran(s)</span>
        </div>
      </div>
      <div className="flex gap-2">
        {!bibliotheque && (
          <Button variant="secondary" size="sm" onClick={onOuvrir}>
            Ouvrir
          </Button>
        )}
        <Button variant="ghost" size="sm" onClick={onDupliquer}>
          <Copy className="size-4" aria-hidden="true" />
          Dupliquer
        </Button>
      </div>
    </li>
  )
}

function NouveauCours({ onCree }) {
  const [titre, setTitre] = useState('')
  return (
    <Card>
      <h2 className="font-semibold text-ink-900">Écrire un cours</h2>
      <p className="mt-1 text-sm text-ink-600">
        Court : dix minutes au plus. Un sujet long devient plusieurs cours.
      </p>
      <form
        className="mt-4 flex flex-col gap-2 sm:flex-row"
        onSubmit={(event) => {
          event.preventDefault()
          if (titre.trim()) onCree(titre.trim())
        }}
      >
        <label className="sr-only" htmlFor="titre-cours">
          Titre du cours
        </label>
        <input
          id="titre-cours"
          className={`${champ} mt-0 flex-1`}
          value={titre}
          onChange={(event) => setTitre(event.target.value)}
          placeholder="Reconnaître un courriel d’hameçonnage"
          required
        />
        <Button type="submit">
          <Plus className="size-4" aria-hidden="true" />
          Créer
        </Button>
      </form>
    </Card>
  )
}

function Editeur({ coursId, variables, onFermer, erreur, problemes, onErreur, onEffacerErreur }) {
  const [cours, setCours] = useState(null)
  const [version, setVersion] = useState(null)
  const [apercu, setApercu] = useState(false)

  async function charger() {
    const { data: fiche } = await formationApi.studioCours1(coursId)
    setCours(fiche)
    const versionId = fiche.draft_version_id || fiche.published_version_id
    if (versionId) {
      const { data } = await formationApi.studioVersion(versionId)
      setVersion({ ...data, id: versionId })
    }
  }

  useEffect(() => {
    charger().catch(() => onErreur(new Error()))
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [coursId])

  if (!cours || !version) return null

  const verrouille = version.is_published

  async function agir(action) {
    onEffacerErreur()
    try {
      await action()
      await charger()
    } catch (err) {
      onErreur(err)
    }
  }

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div>
          <Button variant="ghost" size="sm" onClick={onFermer}>
            ← Tous les cours
          </Button>
          <h2 className="mt-1 text-xl font-semibold text-ink-900">{cours.title}</h2>
          <p className="text-sm text-ink-600">
            Version {version.course_version} — {verrouille ? 'publiée' : 'brouillon'} ·{' '}
            {version.estimated_minutes} min annoncées
          </p>
        </div>
        <div className="flex flex-wrap gap-2">
          <Button variant="secondary" size="sm" onClick={() => setApercu((v) => !v)}>
            <Eye className="size-4" aria-hidden="true" />
            {apercu ? 'Revenir à l’édition' : 'Aperçu apprenant'}
          </Button>
          {verrouille ? (
            <Button
              size="sm"
              onClick={() => agir(() => formationApi.studioNouvelleVersion(coursId, {}))}
            >
              Ouvrir une nouvelle version
            </Button>
          ) : (
            <Button
              size="sm"
              disabled={version.blocking?.length > 0}
              onClick={() => agir(() => formationApi.studioPublier(version.id))}
            >
              <Send className="size-4" aria-hidden="true" />
              Publier
            </Button>
          )}
        </div>
      </div>

      {erreur && (
        <div role="alert" className="rounded-lg bg-critical-subtle px-4 py-3 text-sm text-critical-strong">
          {erreur}
          {problemes.length > 0 && (
            <ul className="mt-2 list-disc pl-5">
              {problemes.map((probleme) => (
                <li key={probleme}>{probleme}</li>
              ))}
            </ul>
          )}
        </div>
      )}

      {verrouille && (
        <p className="rounded-lg border border-brand-200 bg-brand-50 px-4 py-3 text-sm text-ink-800">
          Cette version est publiée : elle ne se modifie plus. Ouvrez une nouvelle version pour la
          corriger — les salariés en cours de parcours termineront sur celle qu’ils ont commencée.
        </p>
      )}

      {version.blocking?.length > 0 && (
        <div className="rounded-lg border border-warning-border bg-warning-subtle px-4 py-3 text-sm text-ink-900">
          <strong>À corriger avant publication</strong>
          <ul className="mt-1 list-disc pl-5">
            {version.blocking.map((refus) => (
              <li key={refus}>{refus}</li>
            ))}
          </ul>
        </div>
      )}

      {version.warnings?.length > 0 && (
        <div className="rounded-lg border border-ink-200 bg-ink-50 px-4 py-3 text-sm text-ink-700">
          <strong>Points de vigilance</strong>
          <ul className="mt-1 list-disc pl-5">
            {version.warnings.map((avertissement) => (
              <li key={avertissement}>{avertissement}</li>
            ))}
          </ul>
        </div>
      )}

      {apercu ? (
        <Apercu version={version} />
      ) : (
        <Ecrans
          version={version}
          variables={variables}
          verrouille={verrouille}
          agir={agir}
        />
      )}
    </div>
  )
}

function Apercu({ version }) {
  return (
    <div className="space-y-6">
      <p className="text-sm text-ink-600">
        Tel que le verra un salarié. Les variables sont remplies avec les données de votre
        entreprise — c’est le seul moyen de voir si la phrase se tient avec de vrais chiffres.
      </p>
      {version.screens.map((ecran) => (
        <Card key={ecran.id}>
          <h3 className="text-lg font-semibold text-ink-900">
            {ecran.order}. {ecran.title}
          </h3>
          <div className="mt-4">
            <ContenuEcran blocs={ecran.content} />
          </div>
        </Card>
      ))}
    </div>
  )
}

function Ecrans({ version, variables, verrouille, agir }) {
  return (
    <div className="space-y-4">
      {version.screens.map((ecran, index) => (
        <EditeurEcran
          key={ecran.id}
          ecran={ecran}
          index={index}
          total={version.screens.length}
          versionId={version.id}
          variables={variables}
          verrouille={verrouille}
          agir={agir}
          ordre={version.screens.map((e) => e.id)}
        />
      ))}

      {!verrouille && (
        <Button
          variant="secondary"
          onClick={() =>
            agir(() =>
              formationApi.studioEcrireEcran(version.id, {
                title: 'Nouvel écran',
                content: [{ type: 'paragraphe', texte: 'À compléter.' }],
              })
            )
          }
        >
          <Plus className="size-4" aria-hidden="true" />
          Ajouter un écran
        </Button>
      )}
    </div>
  )
}

function EditeurEcran({ ecran, index, total, versionId, variables, verrouille, agir, ordre }) {
  const [titre, setTitre] = useState(ecran.title)
  const [blocs, setBlocs] = useState(ecran.content_brut ?? ecran.content)
  const [repli, setRepli] = useState(
    (ecran.content_brut ?? ecran.content).map((bloc) => bloc.repli ?? '')
  )

  function modifier(position, champs) {
    setBlocs((actuels) =>
      actuels.map((bloc, rang) => (rang === position ? { ...bloc, ...champs } : bloc))
    )
  }

  function deplacer(direction) {
    const cible = index + direction
    if (cible < 0 || cible >= total) return
    const nouveau = [...ordre]
    ;[nouveau[index], nouveau[cible]] = [nouveau[cible], nouveau[index]]
    agir(() => formationApi.studioOrdreEcrans(versionId, nouveau))
  }

  function enregistrer() {
    const charge = blocs.map((bloc, rang) =>
      contientUneVariable(bloc) ? { ...bloc, repli: repli[rang] ?? '' } : bloc
    )
    agir(() =>
      formationApi.studioEcrireEcran(versionId, {
        screen_id: ecran.id,
        title: titre,
        content: charge,
        estimated_seconds: ecran.estimated_seconds,
      })
    )
  }

  return (
    <Card>
      <div className="flex flex-wrap items-center justify-between gap-2">
        <label className="flex-1" htmlFor={`titre-${ecran.id}`}>
          <span className="text-xs font-medium uppercase tracking-wide text-ink-500">
            Écran {ecran.order}
          </span>
          <input
            id={`titre-${ecran.id}`}
            className={champ}
            value={titre}
            disabled={verrouille}
            onChange={(event) => setTitre(event.target.value)}
          />
        </label>
        {!verrouille && (
          <div className="flex gap-1 self-end">
            <Button variant="ghost" size="sm" onClick={() => deplacer(-1)} disabled={index === 0}>
              <ArrowUp className="size-4" aria-hidden="true" />
              <span className="sr-only">Monter</span>
            </Button>
            <Button
              variant="ghost"
              size="sm"
              onClick={() => deplacer(1)}
              disabled={index === total - 1}
            >
              <ArrowDown className="size-4" aria-hidden="true" />
              <span className="sr-only">Descendre</span>
            </Button>
            <Button
              variant="ghost"
              size="sm"
              onClick={() => agir(() => formationApi.studioSupprimerEcran(versionId, ecran.id))}
            >
              <Trash2 className="size-4" aria-hidden="true" />
              <span className="sr-only">Supprimer l’écran</span>
            </Button>
          </div>
        )}
      </div>

      <div className="mt-4 space-y-3">
        {blocs.map((bloc, rang) => (
          <div key={rang} className="rounded-lg border border-ink-200 p-3">
            <div className="flex items-center justify-between gap-2">
              <label className="text-xs text-ink-600">
                Type
                <select
                  className={`${champ} mt-0 ml-2 inline-block w-auto`}
                  value={bloc.type}
                  disabled={verrouille}
                  onChange={(event) =>
                    setBlocs((actuels) =>
                      actuels.map((b, i) => (i === rang ? blocNeuf(event.target.value) : b))
                    )
                  }
                >
                  {TYPES.map((type) => (
                    <option key={type.valeur} value={type.valeur}>
                      {type.libelle}
                    </option>
                  ))}
                </select>
              </label>
              {!verrouille && (
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={() => setBlocs((actuels) => actuels.filter((_, i) => i !== rang))}
                >
                  <Trash2 className="size-4" aria-hidden="true" />
                  <span className="sr-only">Retirer ce bloc</span>
                </Button>
              )}
            </div>

            {bloc.type === 'liste' ? (
              <label className="mt-2 block text-xs text-ink-600">
                Une entrée par ligne
                <textarea
                  className={champ}
                  rows={3}
                  disabled={verrouille}
                  value={(bloc.items ?? []).join('\n')}
                  onChange={(event) =>
                    modifier(rang, { items: event.target.value.split('\n') })
                  }
                />
              </label>
            ) : (
              <label className="mt-2 block text-xs text-ink-600">
                Texte — <code>**gras**</code> pour mettre en valeur
                <textarea
                  className={champ}
                  rows={3}
                  disabled={verrouille}
                  value={bloc.texte ?? ''}
                  onChange={(event) => modifier(rang, { texte: event.target.value })}
                />
              </label>
            )}

            {bloc.type === 'encadre' && (
              <label className="mt-2 block text-xs text-ink-600">
                Ton
                <select
                  className={`${champ} mt-0 ml-2 inline-block w-auto`}
                  value={bloc.ton ?? 'info'}
                  disabled={verrouille}
                  onChange={(event) => modifier(rang, { ton: event.target.value })}
                >
                  <option value="info">Information</option>
                  <option value="attention">Point de vigilance</option>
                  <option value="exemple">Exemple</option>
                </select>
              </label>
            )}

            {contientUneVariable(bloc) && (
              <label className="mt-2 block text-xs text-ink-600">
                Formulation de repli — affichée aux clients sans données, ou dont le chiffre est
                trop petit pour être donné sans désigner quelqu’un
                <textarea
                  className={champ}
                  rows={2}
                  required
                  disabled={verrouille}
                  value={repli[rang] ?? ''}
                  onChange={(event) =>
                    setRepli((actuels) =>
                      actuels.map((valeur, i) => (i === rang ? event.target.value : valeur))
                    )
                  }
                />
              </label>
            )}

            {!verrouille && bloc.type !== 'liste' && (
              <div className="mt-2 flex flex-wrap items-center gap-1">
                <span className="text-xs text-ink-500">Insérer :</span>
                {variables.map((variable) => (
                  <button
                    key={variable.cle}
                    type="button"
                    title={variable.description}
                    onClick={() =>
                      modifier(rang, { texte: `${bloc.texte ?? ''}{${variable.cle}}` })
                    }
                    className="rounded-md border border-ink-200 px-2 py-1 text-xs text-ink-600 hover:bg-ink-50"
                  >
                    {variable.libelle}
                  </button>
                ))}
              </div>
            )}
          </div>
        ))}
      </div>

      {!verrouille && (
        <div className="mt-3 flex flex-wrap gap-2">
          <Button
            variant="secondary"
            size="sm"
            onClick={() => setBlocs((actuels) => [...actuels, blocNeuf('paragraphe')])}
          >
            <Plus className="size-4" aria-hidden="true" />
            Ajouter un bloc
          </Button>
          <Button size="sm" onClick={enregistrer}>
            Enregistrer cet écran
          </Button>
        </div>
      )}
    </Card>
  )
}
