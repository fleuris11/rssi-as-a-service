import { ArrowDown, ArrowUp, ChevronLeft, ChevronRight } from 'lucide-react'
import { useId, useMemo, useState } from 'react'
import { filtrerParTexte } from '../../utils/recherche'
import Button from './Button'
import EmptyState from './EmptyState'
import SearchInput from './SearchInput'
import Defilement from './Defilement'

/**
 * Le tableau de données du produit — un seul, réutilisé partout.
 *
 * C'est l'objet qu'un RSSI manipule le plus : une liste de compromissions,
 * de clients, de salariés. Il portait jusqu'ici autant de mises en forme
 * qu'il y avait d'écrans, aucune avec tri ni pagination.
 *
 * Quatre choix structurants :
 *
 * - **la densité est un réglage, pas un thème.** Quelqu'un qui balaie deux
 *   cents lignes et quelqu'un qui en lit six n'ont pas le même besoin, et le
 *   réglage doit se voir changer sans recharger ;
 * - **le tri, la recherche et la pagination vivent ici**, pas dans chaque
 *   page. Dupliquer cette logique, c'est la voir diverger au premier ajout ;
 * - **l'en-tête porte `aria-sort`** et le tri se déclenche par un vrai
 *   bouton : un tableau trié à la souris seule est inutilisable au clavier ;
 * - **rien n'est trié par défaut.** L'ordre d'arrivée du serveur porte déjà
 *   un sens (le plus grave d'abord, le plus récent d'abord) ; le remplacer
 *   par un tri alphabétique le détruirait.
 */

const PAR_PAGE = 25

function valeurDeTri(ligne, colonne) {
  const brute = colonne.valeur ? colonne.valeur(ligne) : ligne[colonne.cle]
  return brute ?? ''
}

export default function DataTable({
  colonnes,
  lignes,
  cleDeLigne,
  recherche = null,
  filtres = [],
  selection = null,
  parPage = PAR_PAGE,
  densiteParDefaut = 'compacte',
  actions = null,
  titreVide = 'Aucune ligne',
  descriptionVide = '',
  legende,
}) {
  const [texte, setTexte] = useState('')
  const [tri, setTri] = useState(null)
  const [densite, setDensite] = useState(densiteParDefaut)
  const [page, setPage] = useState(1)
  const [filtresActifs, setFiltresActifs] = useState({})
  const identifiant = useId()

  const filtrees = useMemo(() => {
    let resultat = lignes

    for (const filtre of filtres) {
      const choisi = filtresActifs[filtre.cle]
      if (!choisi || choisi === 'tous') continue
      const option = filtre.options.find((o) => o.valeur === choisi)
      if (option?.test) resultat = resultat.filter(option.test)
    }

    if (recherche && texte.trim()) {
      resultat = filtrerParTexte(resultat, texte, recherche.extraire)
    }

    if (tri) {
      const colonne = colonnes.find((c) => c.cle === tri.cle)
      if (colonne) {
        // Copie avant tri : `sort` modifie le tableau en place, et trier la
        // propriété reçue en cascade ferait bouger les données du parent.
        resultat = [...resultat].sort((a, b) => {
          const ga = valeurDeTri(a, colonne)
          const gb = valeurDeTri(b, colonne)
          const ordre =
            typeof ga === 'number' && typeof gb === 'number'
              ? ga - gb
              : String(ga).localeCompare(String(gb), 'fr', { numeric: true })
          return tri.sens === 'asc' ? ordre : -ordre
        })
      }
    }

    return resultat
  }, [lignes, filtres, filtresActifs, recherche, texte, tri, colonnes])

  const pages = Math.max(1, Math.ceil(filtrees.length / parPage))
  const pageSure = Math.min(page, pages)
  const visibles = filtrees.slice((pageSure - 1) * parPage, pageSure * parPage)

  function basculerLeTri(colonne) {
    setPage(1)
    setTri((actuel) => {
      if (actuel?.cle !== colonne.cle) return { cle: colonne.cle, sens: 'asc' }
      // Troisième clic : on retire le tri et on rend l'ordre du serveur,
      // qui porte souvent le vrai classement (le plus grave d'abord).
      return actuel.sens === 'asc' ? { cle: colonne.cle, sens: 'desc' } : null
    })
  }

  const toutesSelectionnees =
    selection && visibles.length > 0 && visibles.every((l) => selection.valeurs.includes(cleDeLigne(l)))

  function basculerTout() {
    if (!selection) return
    const clesVisibles = visibles.map(cleDeLigne)
    selection.onChange(
      toutesSelectionnees
        ? selection.valeurs.filter((v) => !clesVisibles.includes(v))
        : [...new Set([...selection.valeurs, ...clesVisibles])]
    )
  }

  return (
    <div className="panneau overflow-hidden">
      {/* La barre est TOUJOURS là, même sans recherche ni filtre : le réglage
          de densité appartient au tableau, pas à la page qui l'utilise. Il
          n'apparaissait d'abord qu'avec une recherche — donc jamais sur les
          tableaux simples, qui sont précisément ceux qu'on veut resserrer. */}
      <div className="flex flex-wrap items-center gap-3 border-b border-ink-200 p-3">
          {recherche && (
            <SearchInput
              label={recherche.label}
              value={texte}
              onChange={(valeur) => {
                setTexte(valeur)
                setPage(1)
              }}
              placeholder={recherche.placeholder}
            />
          )}

          {filtres.map((filtre) => (
            <label key={filtre.cle} className="t-meta flex items-center gap-2">
              <span className="sr-only">{filtre.libelle}</span>
              <select
                className="transition-smooth rounded-md border border-ink-200 bg-surface px-2 py-1.5 text-sm text-ink-700 focus-visible:outline-2 focus-visible:outline-brand-600"
                value={filtresActifs[filtre.cle] ?? 'tous'}
                onChange={(event) => {
                  setFiltresActifs((a) => ({ ...a, [filtre.cle]: event.target.value }))
                  setPage(1)
                }}
              >
                <option value="tous">{filtre.libelle} : tous</option>
                {filtre.options.map((option) => (
                  <option key={option.valeur} value={option.valeur}>
                    {option.libelle}
                  </option>
                ))}
              </select>
            </label>
          ))}

          <div className="ml-auto flex items-center gap-2">
            <fieldset className="flex items-center gap-1">
              <legend className="sr-only">Densité du tableau</legend>
              {[
                ['compacte', 'Compacte'],
                ['confortable', 'Confortable'],
              ].map(([valeur, libelle]) => (
                <button
                  key={valeur}
                  type="button"
                  aria-pressed={densite === valeur}
                  onClick={() => setDensite(valeur)}
                  className={`transition-smooth rounded-md px-2.5 py-1 text-xs font-medium ${
                    densite === valeur
                      ? 'bg-brand-600 text-white'
                      : 'border border-ink-200 text-ink-600 hover:bg-ink-50'
                  }`}
                >
                  {libelle}
                </button>
              ))}
            </fieldset>
            {actions}
          </div>
      </div>

      {visibles.length === 0 ? (
        <EmptyState
          title={texte ? 'Aucun résultat' : titreVide}
          description={texte ? 'Aucune ligne ne correspond à cette recherche.' : descriptionVide}
        />
      ) : (
        <Defilement>
          <table className="tableau" data-densite={densite}>
            <caption className="sr-only">{legende}</caption>
            <thead>
              <tr>
                {selection && (
                  <th scope="col" className="w-10">
                    <input
                      type="checkbox"
                      className="size-4"
                      checked={Boolean(toutesSelectionnees)}
                      onChange={basculerTout}
                      aria-label="Tout sélectionner sur cette page"
                    />
                  </th>
                )}
                {colonnes.map((colonne) => {
                  const trieePar = tri?.cle === colonne.cle
                  return (
                    <th
                      key={colonne.cle}
                      scope="col"
                      className={colonne.num ? 'text-right' : undefined}
                      aria-sort={
                        trieePar ? (tri.sens === 'asc' ? 'ascending' : 'descending') : 'none'
                      }
                    >
                      {colonne.triable === false ? (
                        colonne.entete
                      ) : (
                        <button
                          type="button"
                          onClick={() => basculerLeTri(colonne)}
                          className="transition-smooth inline-flex items-center gap-1 uppercase tracking-[0.07em] hover:text-ink-800"
                        >
                          {colonne.entete}
                          {trieePar &&
                            (tri.sens === 'asc' ? (
                              <ArrowUp className="size-3" aria-hidden="true" />
                            ) : (
                              <ArrowDown className="size-3" aria-hidden="true" />
                            ))}
                        </button>
                      )}
                    </th>
                  )
                })}
              </tr>
            </thead>
            <tbody>
              {visibles.map((ligne) => {
                const cle = cleDeLigne(ligne)
                const choisie = selection?.valeurs.includes(cle)
                return (
                  <tr key={cle} data-selectionnee={choisie ? 'true' : undefined}>
                    {selection && (
                      <td>
                        <input
                          type="checkbox"
                          className="size-4"
                          checked={Boolean(choisie)}
                          onChange={() =>
                            selection.onChange(
                              choisie
                                ? selection.valeurs.filter((v) => v !== cle)
                                : [...selection.valeurs, cle]
                            )
                          }
                          aria-label={`Sélectionner ${selection.nommer ? selection.nommer(ligne) : cle}`}
                        />
                      </td>
                    )}
                    {colonnes.map((colonne) => (
                      <td
                        key={colonne.cle}
                        className={colonne.num ? 'num text-right' : undefined}
                      >
                        {colonne.rendu ? colonne.rendu(ligne) : ligne[colonne.cle]}
                      </td>
                    ))}
                  </tr>
                )
              })}
            </tbody>
          </table>
        </Defilement>
      )}

      {filtrees.length > parPage && (
        <div className="flex flex-wrap items-center gap-3 border-t border-ink-200 px-4 py-2.5">
          <span className="t-meta num">
            {(pageSure - 1) * parPage + 1}–{Math.min(pageSure * parPage, filtrees.length)} sur{' '}
            {filtrees.length}
          </span>
          <div className="ml-auto flex gap-2">
            <Button
              variant="secondary"
              size="sm"
              disabled={pageSure === 1}
              onClick={() => setPage(pageSure - 1)}
            >
              <ChevronLeft className="size-4" aria-hidden="true" />
              Précédent
            </Button>
            <Button
              variant="secondary"
              size="sm"
              disabled={pageSure === pages}
              onClick={() => setPage(pageSure + 1)}
            >
              Suivant
              <ChevronRight className="size-4" aria-hidden="true" />
            </Button>
          </div>
        </div>
      )}
      <span id={identifiant} className="sr-only">
        {filtrees.length} ligne(s)
      </span>
    </div>
  )
}
