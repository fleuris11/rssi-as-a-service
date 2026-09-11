import { ChevronDown, ChevronRight, Download, Filter, Search } from 'lucide-react'
import { useCallback, useEffect, useState } from 'react'
import { threatIntelligenceApi } from '../../api/endpoints'
import Badge from '../../components/ui/Badge'
import Button from '../../components/ui/Button'
import Card, { CardHeader } from '../../components/ui/Card'
import EmptyState from '../../components/ui/EmptyState'
import { SkeletonCard } from '../../components/ui/Skeleton'
import { useToast } from '../../components/ui/Toast'

/**
 * La restitution des résultats de comptes surveillés (lot A).
 *
 * Le défaut corrigé, relevé en production : **3 222 résultats pour un seul
 * compte**, affichés en lignes rigoureusement identiques. Le diagnostic a
 * montré que le dédoublonnage fonctionnait — 3 222 empreintes distinctes —
 * et que l'écran masquait précisément les deux champs qui distinguent les
 * lignes : le service concerné et le nom du jeton volé.
 *
 * Trois décisions d'affichage en découlent :
 *
 * 1. **on regroupe avant de paginer.** Paginer 3 222 lignes identiques ne
 *    fait que les étaler sur 162 pages ;
 * 2. **le détail se déplie à la demande**, et porte les champs distinctifs
 *    avec leur phrase d'implication ;
 * 3. **on distingue l'historique des nouveautés.** Le premier passage
 *    remonte tout le passé connu ; c'est normal, et le dire évite la
 *    panique devant un gros volume.
 */

const GRAVITES = {
  critical: { libelle: 'Critique', variant: 'critical' },
  high: { libelle: 'Élevée', variant: 'warning' },
  attention: { libelle: 'Attention', variant: 'neutral' },
}

const STATUTS = [
  { value: 'open', label: 'À traiter' },
  { value: 'treated', label: 'Traités' },
  { value: 'ignored', label: 'Écartés' },
  { value: '', label: 'Tous' },
]

function dateCourte(valeur) {
  // Jamais de date inventée : quand la source n'en fournit pas, on le dit.
  if (!valeur) return 'date inconnue'
  return new Date(valeur).toLocaleDateString('fr-FR')
}

/** Une ligne dépliée : ce que la source a réellement fourni. */
function LigneDetail({ ligne, onStatut, occupe }) {
  return (
    <li className="border-t border-ink-100 py-3">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="min-w-0 flex-1">
          <dl className="grid gap-x-6 gap-y-1 sm:grid-cols-2">
            {ligne.details.map((champ) => (
              <div key={champ.label} className="min-w-0">
                <dt className="t-eyebrow">{champ.label}</dt>
                <dd className="truncate text-sm text-ink-800" title={champ.value}>
                  {champ.value}
                </dd>
                {champ.implication ? (
                  <dd className="mt-0.5 text-xs text-ink-500">{champ.implication}</dd>
                ) : null}
              </div>
            ))}
          </dl>
          <p className="mt-2 text-xs text-ink-500">
            Fuite datée du {dateCourte(ligne.breach_date)}
            {ligne.has_secret ? ' · un mot de passe a fuité' : ''}
            {ligne.from_first_scan ? ' · historique découvert au premier scan' : ' · apparu depuis'}
          </p>
        </div>
        <div className="flex shrink-0 gap-1.5">
          {ligne.status === 'open' ? (
            <>
              <Button
                variant="secondary"
                size="sm"
                loading={occupe === `treated-${ligne.id}`}
                onClick={() => onStatut(ligne, 'treated')}
              >
                Traité
              </Button>
              <Button
                variant="ghost"
                size="sm"
                loading={occupe === `ignored-${ligne.id}`}
                onClick={() => onStatut(ligne, 'ignored')}
              >
                Écarter
              </Button>
            </>
          ) : (
            <Badge variant="neutral">{ligne.status_label}</Badge>
          )}
        </div>
      </div>
    </li>
  )
}

/** Un groupe : ce qui se répète, compté une fois. */
function Groupe({ groupe, filtres, onStatut, occupe }) {
  const { showToast } = useToast()
  const [ouvert, setOuvert] = useState(false)
  const [lignes, setLignes] = useState(null)
  const [chargement, setChargement] = useState(false)

  async function basculer() {
    const prochain = !ouvert
    setOuvert(prochain)
    if (!prochain || lignes) return
    setChargement(true)
    try {
      const response = await threatIntelligenceApi.listWatchedAccountFindings({
        ...filtres,
        group: groupe.key,
        page_size: 50,
      })
      setLignes(response.data.results)
    } catch {
      showToast({ type: 'error', message: 'Impossible d’ouvrir ce groupe.' })
      setOuvert(false)
    } finally {
      setChargement(false)
    }
  }

  const gravite = GRAVITES[groupe.severity] ?? { libelle: groupe.severity, variant: 'neutral' }

  return (
    <li className="px-5 py-3">
      <button
        type="button"
        onClick={basculer}
        aria-expanded={ouvert}
        className="transition-smooth flex w-full items-start justify-between gap-3 text-left"
      >
        <div className="flex min-w-0 items-start gap-2">
          {ouvert ? (
            <ChevronDown className="mt-0.5 size-4 shrink-0 text-ink-400" aria-hidden="true" />
          ) : (
            <ChevronRight className="mt-0.5 size-4 shrink-0 text-ink-400" aria-hidden="true" />
          )}
          <div className="min-w-0">
            <p className="truncate text-sm font-medium text-ink-800">
              {groupe.service || 'Service non précisé'}
            </p>
            <p className="mt-0.5 text-xs text-ink-500">
              {groupe.occurrences} occurrence{groupe.occurrences > 1 ? 's' : ''}
              {' · de '}
              {dateCourte(groupe.oldest_breach_date)}
              {' à '}
              {dateCourte(groupe.latest_breach_date)}
            </p>
          </div>
        </div>
        <div className="flex shrink-0 items-center gap-2">
          <Badge variant={gravite.variant}>{gravite.libelle}</Badge>
          {groupe.open_count > 0 ? (
            <Badge variant="neutral">{groupe.open_count} à traiter</Badge>
          ) : (
            <Badge variant="success">traité</Badge>
          )}
        </div>
      </button>

      {ouvert ? (
        <div className="mt-2 pl-6">
          {chargement ? (
            <p className="py-2 text-sm text-ink-500">Chargement…</p>
          ) : (
            <ul>
              {(lignes ?? []).map((ligne) => (
                <LigneDetail key={ligne.id} ligne={ligne} onStatut={onStatut} occupe={occupe} />
              ))}
            </ul>
          )}
        </div>
      ) : null}
    </li>
  )
}

export default function ResultatsComptes({ comptes = [], resume = {} }) {
  const { showToast } = useToast()
  const [groupes, setGroupes] = useState([])
  const [filtresDispo, setFiltresDispo] = useState({ types: [], severities: [] })
  const [total, setTotal] = useState(0)
  const [chargement, setChargement] = useState(true)
  const [occupe, setOccupe] = useState(null)
  const [statut, setStatut] = useState('open')
  const [severite, setSeverite] = useState('')
  const [type, setType] = useState('')
  const [compte, setCompte] = useState('')
  const [recherche, setRecherche] = useState('')

  const filtres = {
    ...(statut ? { status: statut } : {}),
    ...(severite ? { severity: severite } : {}),
    ...(type ? { type } : {}),
    ...(compte ? { account: compte } : {}),
    ...(recherche ? { q: recherche } : {}),
  }
  const cleFiltres = JSON.stringify(filtres)

  const charger = useCallback(async () => {
    setChargement(true)
    try {
      const response = await threatIntelligenceApi.listWatchedAccountFindings({
        ...JSON.parse(cleFiltres),
        page_size: 100,
      })
      setGroupes(response.data.results)
      setTotal(response.data.count)
      if (response.data.filters) setFiltresDispo(response.data.filters)
    } catch (err) {
      if (err.response?.status !== 402) {
        showToast({ type: 'error', message: 'Impossible de charger les résultats.' })
      }
    } finally {
      setChargement(false)
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [cleFiltres])

  useEffect(() => {
    charger()
  }, [charger])

  async function handleStatut(ligne, nouveau) {
    setOccupe(`${nouveau}-${ligne.id}`)
    try {
      await threatIntelligenceApi.updateWatchedAccountFinding(ligne.id, nouveau)
      showToast({ type: 'success', message: 'Résultat mis à jour.' })
      await charger()
    } catch {
      showToast({ type: 'error', message: 'Action impossible.' })
    } finally {
      setOccupe(null)
    }
  }

  // Les comptes portent chacun leur nombre de résultats : un client qui en
  // surveille dix doit voir dix blocs, pas une liste plate.
  const parCompte = groupes.reduce((acc, g) => {
    const cle = g.account_id
    acc[cle] = acc[cle] ?? { id: cle, value: g.account_value, label: g.account_label, groupes: [] }
    acc[cle].groupes.push(g)
    return acc
  }, {})

  return (
    <Card padding="p-0">
      <div className="space-y-3 p-5 pb-3">
        <CardHeader
          title="Résultats par compte"
          description="Ce qui se répète est compté une fois. Ouvrez un groupe pour voir le détail de chaque occurrence."
        />

        {/* On masque, on ne cache pas : le compteur dit ce qui est déjà
            traité, et le filtre permet d'y revenir. */}
        <p className="text-xs text-ink-500">
          {total} groupe{total > 1 ? 's' : ''} affiché{total > 1 ? 's' : ''}
          {resume.treated_findings ? ` · ${resume.treated_findings} résultat(s) déjà traité(s)` : ''}
          {resume.ignored_findings ? ` · ${resume.ignored_findings} écarté(s)` : ''}
          {resume.from_first_scan
            ? ` · dont ${resume.from_first_scan} venu(s) de la reprise d’historique au premier scan`
            : ''}
        </p>

        <div className="flex flex-wrap items-center gap-2">
          <Filter className="size-4 text-ink-400" aria-hidden="true" />
          <label className="sr-only" htmlFor="filtre-statut">
            Statut
          </label>
          <select
            id="filtre-statut"
            value={statut}
            onChange={(e) => setStatut(e.target.value)}
            className="rounded-md border border-ink-200 px-2 py-1 text-xs"
          >
            {STATUTS.map((s) => (
              <option key={s.value || 'tous'} value={s.value}>
                {s.label}
              </option>
            ))}
          </select>

          <label className="sr-only" htmlFor="filtre-gravite">
            Gravité
          </label>
          <select
            id="filtre-gravite"
            value={severite}
            onChange={(e) => setSeverite(e.target.value)}
            className="rounded-md border border-ink-200 px-2 py-1 text-xs"
          >
            <option value="">Toutes gravités</option>
            {filtresDispo.severities.map((s) => (
              <option key={s} value={s}>
                {GRAVITES[s]?.libelle ?? s}
              </option>
            ))}
          </select>

          <label className="sr-only" htmlFor="filtre-type">
            Type
          </label>
          <select
            id="filtre-type"
            value={type}
            onChange={(e) => setType(e.target.value)}
            className="rounded-md border border-ink-200 px-2 py-1 text-xs"
          >
            <option value="">Tous types</option>
            {filtresDispo.types.map((t) => (
              <option key={t} value={t}>
                {t}
              </option>
            ))}
          </select>

          <label className="sr-only" htmlFor="filtre-compte">
            Compte
          </label>
          <select
            id="filtre-compte"
            value={compte}
            onChange={(e) => setCompte(e.target.value)}
            className="rounded-md border border-ink-200 px-2 py-1 text-xs"
          >
            <option value="">Tous les comptes</option>
            {comptes.map((c) => (
              <option key={c.id} value={c.id}>
                {c.label || c.value}
              </option>
            ))}
          </select>

          <div className="flex items-center gap-1">
            <Search className="size-4 text-ink-400" aria-hidden="true" />
            <label className="sr-only" htmlFor="filtre-recherche">
              Rechercher un compte
            </label>
            <input
              id="filtre-recherche"
              type="search"
              value={recherche}
              onChange={(e) => setRecherche(e.target.value)}
              placeholder="Rechercher un compte"
              className="rounded-md border border-ink-200 px-2 py-1 text-xs"
            />
          </div>

          <a
            href={threatIntelligenceApi.watchedAccountFindingsExportUrl(filtres)}
            className="ml-auto inline-flex items-center gap-1 text-xs text-brand-600 hover:underline"
          >
            <Download className="size-3.5" aria-hidden="true" />
            Exporter (.csv)
          </a>
        </div>
      </div>

      {chargement ? (
        <div className="p-5 pt-0">
          <SkeletonCard />
        </div>
      ) : groupes.length === 0 ? (
        <div className="p-5 pt-0">
          <EmptyState
            title="Rien à traiter"
            description="Aucun résultat ne correspond à ces filtres."
          />
        </div>
      ) : (
        <div className="pb-3">
          {Object.values(parCompte).map((bloc) => (
            <section key={bloc.id} className="border-t border-ink-100">
              <h3 className="px-5 pt-3 text-sm font-medium text-ink-800">
                {bloc.label || bloc.value}{' '}
                <span className="text-xs font-normal text-ink-500">
                  — {bloc.groupes.reduce((n, g) => n + g.open_count, 0)} à traiter
                </span>
              </h3>
              <ul className="divide-y divide-ink-50">
                {bloc.groupes.map((groupe) => (
                  <Groupe
                    key={groupe.key}
                    groupe={groupe}
                    filtres={filtres}
                    onStatut={handleStatut}
                    occupe={occupe}
                  />
                ))}
              </ul>
            </section>
          ))}
        </div>
      )}
    </Card>
  )
}
