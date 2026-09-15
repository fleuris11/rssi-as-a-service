import { useCallback, useEffect, useState } from 'react'
import { platformApi } from '../../../../api/endpoints'
import Badge from '../../../../components/ui/Badge'
import Button from '../../../../components/ui/Button'
import Card, { CardHeader } from '../../../../components/ui/Card'
import { SkeletonCard } from '../../../../components/ui/Skeleton'
import { useToast } from '../../../../components/ui/Toast'
import { CHAMP, NIVEAUX, versIdentifiant } from './outils'

const MESURE_VIDE = {
  domain_code: '',
  code: '',
  official_title: '',
  plain_language: '',
  effort: 'medium',
  impact: 'medium',
}

/**
 * Éditer un référentiel : ses domaines, ses mesures, et les questionnaires
 * qu'on compose à partir de lui (B2.4, B2.5, B2.7).
 *
 * Composer sans client désigné publie un MODÈLE DE PLATEFORME, proposé à tous
 * ceux à qui le référentiel est attribué. Composer pour un client écrit une
 * composition qui n'appartient qu'à lui : c'est la façon d'attribuer « 10 ou
 * 20 mesures » à un client précis.
 */
export default function EditionReferentiel({ catalogue, clients = [], onModifie }) {
  const { showToast } = useToast()
  const [slug, setSlug] = useState(catalogue[0]?.slug ?? '')
  const [plan, setPlan] = useState(null)
  const [domaine, setDomaine] = useState({ code: '', name: '' })
  const [mesure, setMesure] = useState(MESURE_VIDE)
  const [composition, setComposition] = useState({ name: '', cible: '' })
  const [coches, setCoches] = useState(() => new Set())
  const [occupe, setOccupe] = useState(null)

  const charger = useCallback(
    async (cible) => {
      if (!cible) {
        setPlan(null)
        return
      }
      try {
        const reponse = await platformApi.referentialOutline(cible)
        setPlan(reponse.data)
      } catch {
        showToast({ type: 'error', message: 'Impossible d’ouvrir ce référentiel.' })
      }
    },
    // eslint-disable-next-line react-hooks/exhaustive-deps
    []
  )

  useEffect(() => {
    charger(slug)
    setCoches(new Set())
  }, [slug, charger])

  async function agir(nom, appel, succes, apres) {
    setOccupe(nom)
    try {
      const reponse = await appel()
      setPlan(reponse.data)
      showToast({ type: 'success', message: succes })
      apres?.()
      onModifie?.()
    } catch (err) {
      showToast({ type: 'error', message: err.response?.data?.detail || 'Action impossible.' })
    } finally {
      setOccupe(null)
    }
  }

  function basculer(code) {
    setCoches((actuel) => {
      const suivant = new Set(actuel)
      if (suivant.has(code)) suivant.delete(code)
      else suivant.add(code)
      return suivant
    })
  }

  // Ni l'intitulé ni l'énoncé ne se devinent : la validation reste fermée tant
  // qu'ils ne sont pas saisis. Le serveur refuse de toute façon une mesure
  // vide — l'écran évite simplement d'y envoyer l'exploitant.
  const mesureComplete =
    mesure.domain_code &&
    mesure.code.trim() &&
    mesure.official_title.trim() &&
    mesure.plain_language.trim()

  return (
    <Card>
      <CardHeader
        title="Éditer un référentiel"
        description="Ajouter des domaines et des mesures, et composer des questionnaires plus courts."
      />
      <label className="text-xs text-ink-600">
        Référentiel
        <select
          className={`${CHAMP} max-w-md`}
          value={slug}
          onChange={(event) => setSlug(event.target.value)}
        >
          {catalogue.map((ref) => (
            <option key={ref.slug} value={ref.slug}>
              {ref.name}
            </option>
          ))}
        </select>
      </label>

      {!plan ? (
        <div className="mt-4">
          <SkeletonCard />
        </div>
      ) : (
        <div className="mt-4 space-y-6">
          <section>
            <h3 className="text-sm font-medium text-ink-800">Structure</h3>
            {plan.domains.length === 0 ? (
              <p className="mt-1 text-sm text-ink-500">Aucun domaine : commencez par en créer un.</p>
            ) : (
              <ul className="mt-2 space-y-2">
                {plan.domains.map((d) => (
                  <li key={d.code} className="text-sm">
                    <p className="font-medium text-ink-700">
                      {d.name} <span className="text-xs text-ink-500">({d.code})</span>
                    </p>
                    <p className="text-xs text-ink-500">
                      {d.measures.length === 0
                        ? 'Domaine vide'
                        : d.measures.map((m) => m.code).join(', ')}
                    </p>
                  </li>
                ))}
              </ul>
            )}
          </section>

          <section className="grid gap-3 sm:grid-cols-3">
            <h3 className="text-sm font-medium text-ink-800 sm:col-span-3">Ajouter un domaine</h3>
            <label className="text-xs text-ink-600">
              Nom du domaine
              <input
                className={CHAMP}
                value={domaine.name}
                onChange={(event) =>
                  setDomaine({ name: event.target.value, code: versIdentifiant(event.target.value) })
                }
              />
            </label>
            <label className="text-xs text-ink-600">
              Code
              <input
                className={CHAMP}
                value={domaine.code}
                onChange={(event) => setDomaine((d) => ({ ...d, code: event.target.value }))}
              />
            </label>
            <div className="flex items-end">
              <Button
                variant="secondary"
                disabled={!domaine.name.trim() || !domaine.code.trim()}
                loading={occupe === 'domaine'}
                onClick={() =>
                  agir(
                    'domaine',
                    () => platformApi.addReferentialDomain(slug, domaine),
                    'Domaine ajouté.',
                    () => setDomaine({ code: '', name: '' })
                  )
                }
              >
                Ajouter le domaine
              </Button>
            </div>
          </section>

          <section className="grid gap-3 sm:grid-cols-2">
            <h3 className="text-sm font-medium text-ink-800 sm:col-span-2">Ajouter une mesure</h3>
            <label className="text-xs text-ink-600">
              Domaine de la mesure
              <select
                className={CHAMP}
                value={mesure.domain_code}
                onChange={(event) => setMesure((m) => ({ ...m, domain_code: event.target.value }))}
              >
                <option value="">Choisir un domaine…</option>
                {plan.domains.map((d) => (
                  <option key={d.code} value={d.code}>
                    {d.name}
                  </option>
                ))}
              </select>
            </label>
            <label className="text-xs text-ink-600">
              Code de la mesure
              <input
                className={CHAMP}
                value={mesure.code}
                onChange={(event) => setMesure((m) => ({ ...m, code: event.target.value }))}
              />
            </label>
            <label className="text-xs text-ink-600 sm:col-span-2">
              Intitulé officiel
              <input
                className={CHAMP}
                value={mesure.official_title}
                onChange={(event) =>
                  setMesure((m) => ({ ...m, official_title: event.target.value }))
                }
              />
            </label>
            <label className="text-xs text-ink-600 sm:col-span-2">
              Énoncé en langage clair
              <textarea
                className={CHAMP}
                rows={2}
                value={mesure.plain_language}
                onChange={(event) =>
                  setMesure((m) => ({ ...m, plain_language: event.target.value }))
                }
              />
            </label>
            <label className="text-xs text-ink-600">
              Effort
              <select
                className={CHAMP}
                value={mesure.effort}
                onChange={(event) => setMesure((m) => ({ ...m, effort: event.target.value }))}
              >
                {NIVEAUX.map((n) => (
                  <option key={n.value} value={n.value}>
                    {n.label}
                  </option>
                ))}
              </select>
            </label>
            <label className="text-xs text-ink-600">
              Impact
              <select
                className={CHAMP}
                value={mesure.impact}
                onChange={(event) => setMesure((m) => ({ ...m, impact: event.target.value }))}
              >
                {NIVEAUX.map((n) => (
                  <option key={n.value} value={n.value}>
                    {n.label}
                  </option>
                ))}
              </select>
            </label>
            <div className="sm:col-span-2">
              <Button
                variant="secondary"
                disabled={!mesureComplete}
                loading={occupe === 'mesure'}
                onClick={() =>
                  agir(
                    'mesure',
                    () => platformApi.addReferentialMeasure(slug, mesure),
                    'Mesure ajoutée.',
                    () => setMesure({ ...MESURE_VIDE, domain_code: mesure.domain_code })
                  )
                }
              >
                Ajouter la mesure
              </Button>
            </div>
          </section>

          <section>
            <h3 className="text-sm font-medium text-ink-800">Composer un questionnaire</h3>
            <p className="mt-0.5 text-xs text-ink-500">
              Cochez les mesures retenues. Les réponses restent comptées sur le même référentiel.
            </p>
            <ul className="mt-2 max-h-72 space-y-1 overflow-y-auto rounded-md border border-ink-100 p-2">
              {plan.domains.flatMap((d) =>
                d.measures.map((m) => (
                  <li key={m.code}>
                    <label className="flex items-start gap-2 text-sm text-ink-700">
                      <input
                        type="checkbox"
                        className="mt-1"
                        checked={coches.has(m.code)}
                        onChange={() => basculer(m.code)}
                      />
                      <span>
                        <span className="text-xs text-ink-500">{m.code}</span> {m.official_title}
                      </span>
                    </label>
                  </li>
                ))
              )}
            </ul>
            <div className="mt-3 grid gap-3 sm:grid-cols-3">
              <label className="text-xs text-ink-600">
                Nom de la composition
                <input
                  className={CHAMP}
                  value={composition.name}
                  onChange={(event) =>
                    setComposition((c) => ({ ...c, name: event.target.value }))
                  }
                />
              </label>
              <label className="text-xs text-ink-600">
                Pour
                <select
                  className={CHAMP}
                  value={composition.cible}
                  onChange={(event) =>
                    setComposition((c) => ({ ...c, cible: event.target.value }))
                  }
                >
                  <option value="">Tous les clients (modèle de plateforme)</option>
                  {clients.map((client) => (
                    <option key={client.tenant_id ?? client.id} value={client.tenant_id ?? client.id}>
                      {client.name}
                    </option>
                  ))}
                </select>
              </label>
              <div className="flex items-end gap-3">
                <Button
                  variant="primary"
                  disabled={!composition.name.trim() || coches.size === 0}
                  loading={occupe === 'composition'}
                  onClick={() =>
                    agir(
                      'composition',
                      () =>
                        platformApi.composeSubset(slug, {
                          name: composition.name,
                          slug: versIdentifiant(composition.name),
                          measure_codes: [...coches],
                          ...(composition.cible ? { tenant_id: composition.cible } : {}),
                        }),
                      'Composition enregistrée.',
                      () => {
                        setComposition({ name: '', cible: '' })
                        setCoches(new Set())
                      }
                    )
                  }
                >
                  Enregistrer ({coches.size})
                </Button>
              </div>
            </div>

            {plan.subsets.length > 0 && (
              <ul className="mt-4 divide-y divide-ink-100">
                {plan.subsets.map((s) => (
                  <li key={s.slug} className="flex flex-wrap items-center justify-between gap-2 py-2">
                    <span className="text-sm text-ink-700">
                      {s.name}{' '}
                      <span className="text-xs text-ink-500">— {s.measure_codes.length} mesures</span>
                    </span>
                    <Badge variant={s.owner_tenant_name ? 'brand' : 'neutral'}>
                      {s.owner_tenant_name ? `Propre à ${s.owner_tenant_name}` : 'Modèle de plateforme'}
                    </Badge>
                  </li>
                ))}
              </ul>
            )}
          </section>
        </div>
      )}
    </Card>
  )
}
