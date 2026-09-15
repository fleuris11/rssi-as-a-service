import { ExternalLink, Newspaper } from 'lucide-react'
import { useEffect, useState } from 'react'
import { watchApi } from '../api/endpoints'
import { ProfileDate, TechnicalValue } from '../components/DisplayProfile'
import Badge from '../components/ui/Badge'
import Button from '../components/ui/Button'
import SearchInput from '../components/ui/SearchInput'
import Card, { CardHeader } from '../components/ui/Card'
import EmptyState from '../components/ui/EmptyState'
import { SkeletonCard } from '../components/ui/Skeleton'
import { useToast } from '../components/ui/Toast'

/**
 * La veille réglementaire, vue du client (B5.18).
 *
 * **Lecture seule, et volontairement partielle.** Le client voit ce qui a été
 * jugé pertinent — avec sa source officielle et sa date — jamais la file de
 * tri, jamais l'état de nos sources.
 *
 * Ce n'est pas de la rétention d'information : une suggestion non triée n'est
 * pas une information, c'est une hypothèse. L'annoncer comme une exigence
 * coûterait plus cher au client qu'une exigence manquée.
 *
 * La promesse servie par le serveur accompagne le flux, mot pour mot : ni
 * « exhaustive », ni « temps réel ». Une formule honnête est déjà plus que ce
 * que font la plupart des concurrents ; une formule fausse se retourne au
 * premier client qui découvre une exigence ailleurs.
 */

const QUALIFICATIONS = {
  new_requirement: { libelle: 'Nouvelle exigence', variant: 'warning' },
  update: { libelle: 'Évolution', variant: 'accent' },
  information: { libelle: 'Information', variant: 'neutral' },
  unqualified: { libelle: 'À qualifier', variant: 'neutral' },
}

export default function WatchPage() {
  const { showToast } = useToast()
  const [flux, setFlux] = useState(null)
  const [chargement, setChargement] = useState(true)

  // Lot C, point 22 : recherche, nature et pages, servies par le serveur. La
  // veille était tronquée à vingt publications sans page suivante.
  const [recherche, setRecherche] = useState('')
  const [rechercheDifferee, setRechercheDifferee] = useState('')
  const [nature, setNature] = useState('')
  const [page, setPage] = useState(1)

  useEffect(() => {
    const minuterie = setTimeout(() => {
      setRechercheDifferee(recherche.trim())
      setPage(1)
    }, 300)
    return () => clearTimeout(minuterie)
  }, [recherche])

  useEffect(() => {
    let annule = false
    const params = { page }
    if (rechercheDifferee) params.q = rechercheDifferee
    if (nature) params.kind = nature
    watchApi
      .feed(params)
      .then((reponse) => {
        if (!annule) setFlux(reponse.data)
      })
      .catch(() => {
        if (!annule) showToast({ type: 'error', message: 'Impossible de charger la veille.' })
      })
      .finally(() => {
        if (!annule) setChargement(false)
      })
    return () => {
      annule = true
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [page, rechercheDifferee, nature])

  const filtresActifs = Boolean(rechercheDifferee || nature)

  const publications = flux?.results ?? []

  return (
    <div className="space-y-6">
      <div>
        <h1 className="font-display text-2xl font-semibold text-ink-900">Veille réglementaire</h1>
        <p className="mt-1 max-w-3xl text-sm text-ink-500">
          Ce qui bouge dans les textes qui vous concernent. Nous suivons les publications des
          autorités et des organismes de normalisation, et nous ne retenons ici que ce qui a été
          jugé pertinent.
        </p>
      </div>

      <div className="flex flex-wrap items-center gap-2">
        <SearchInput
          label="Rechercher dans la veille"
          value={recherche}
          onChange={setRecherche}
          placeholder="Titre, émetteur…"
          className="flex-1 sm:max-w-xs"
        />
        <select
          aria-label="Filtrer par nature"
          value={nature}
          onChange={(e) => {
            setNature(e.target.value)
            setPage(1)
          }}
          className="rounded-md border border-ink-200 px-2 py-1.5 text-sm text-ink-700"
        >
          <option value="">Toutes les natures</option>
          {Object.entries(QUALIFICATIONS)
            .filter(([cle]) => cle !== 'unqualified')
            .map(([cle, qualification]) => (
              <option key={cle} value={cle}>
                {qualification.libelle}
              </option>
            ))}
        </select>
      </div>

      {chargement ? (
        <SkeletonCard />
      ) : (
        <Card padding="p-0">
          <div className="p-5 pb-0">
            <CardHeader
              title="Publications retenues"
              description="Chaque ligne renvoie au texte officiel. Vous pouvez toujours vérifier à la source."
            />
          </div>

          {publications.length === 0 ? (
            <div className="p-5 pt-0">
              {filtresActifs ? (
                <EmptyState
                  icon={Newspaper}
                  title="Aucune publication ne correspond"
                  description="Modifiez la recherche ou la nature pour élargir la liste."
                />
              ) : (
                <EmptyState
                  icon={Newspaper}
                  title="Rien de nouveau pour le moment"
                  description="Aucune publication n’a été retenue depuis le dernier passage. Nous continuons de suivre les sources officielles."
                />
              )}
            </div>
          ) : (
            <ul className="divide-y divide-ink-100 px-5 pb-3">
              {publications.map((publication) => {
                const qualification =
                  QUALIFICATIONS[publication.kind] ?? QUALIFICATIONS.unqualified
                return (
                  <li key={publication.id} className="py-3">
                    <div className="flex flex-wrap items-start justify-between gap-3">
                      <div className="min-w-0">
                        <p className="text-sm font-medium text-ink-800">{publication.title}</p>
                        <p className="mt-0.5 text-xs text-ink-500">
                          {publication.publisher} ·{' '}
                          <ProfileDate
                            value={publication.published_at}
                            fallback="date non précisée"
                            dateOnly
                          />
                          {publication.referential ? ` · ${publication.referential}` : ''}
                        </p>
                        {/* Lot C : la référence exacte, pour qui recoupe avec
                            la source. Masquée pour le dirigeant. */}
                        <p>
                          <TechnicalValue label="URL" value={publication.url} className="break-all" />
                        </p>
                      </div>
                      <div className="flex shrink-0 items-center gap-2">
                        <Badge variant={qualification.variant}>{qualification.libelle}</Badge>
                        {/* « Intégrée » veut dire qu'une exigence en est
                            sortie : le client a le droit de le savoir. */}
                        {publication.integrated ? (
                          <Badge variant="success">Ajoutée à votre référentiel</Badge>
                        ) : null}
                      </div>
                    </div>
                    <a
                      href={publication.url}
                      target="_blank"
                      rel="noreferrer"
                      className="mt-1 inline-flex items-center gap-1 text-xs text-brand-600 hover:underline"
                    >
                      Lire le texte officiel
                      <ExternalLink className="size-3" aria-hidden="true" />
                    </a>
                  </li>
                )
              })}
            </ul>
          )}

          {(page > 1 || flux?.has_next) && (
            <div className="flex items-center justify-between gap-3 px-5 pb-3 text-sm">
              <p className="text-ink-500">
                {flux.count} publication(s) — page {page}
              </p>
              <div className="flex gap-2">
                <Button variant="secondary" size="sm" disabled={page <= 1} onClick={() => setPage((p) => p - 1)}>
                  Précédentes
                </Button>
                <Button variant="secondary" size="sm" disabled={!flux.has_next} onClick={() => setPage((p) => p + 1)}>
                  Suivantes
                </Button>
              </div>
            </div>
          )}

          {/* La promesse vient du SERVEUR, mot pour mot, pour qu'elle ne
              dérive pas d'un écran à l'autre. */}
          {flux?.promise ? (
            <p className="border-t border-ink-100 px-5 py-3 text-xs text-ink-500">
              {flux.promise}
            </p>
          ) : null}
        </Card>
      )}
    </div>
  )
}
