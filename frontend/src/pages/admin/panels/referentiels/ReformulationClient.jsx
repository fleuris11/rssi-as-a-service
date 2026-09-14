import { useEffect, useState } from 'react'
import { platformApi } from '../../../../api/endpoints'
import Badge from '../../../../components/ui/Badge'
import Button from '../../../../components/ui/Button'
import Card, { CardHeader } from '../../../../components/ui/Card'
import { useToast } from '../../../../components/ui/Toast'
import { CHAMP } from './outils'

function parMesure(surcharges = []) {
  return surcharges.reduce((acc, surcharge) => ({ ...acc, [surcharge.measure_id]: surcharge }), {})
}

/**
 * Reformuler l'énoncé d'une mesure pour un client donné (B2.6).
 *
 * La surcharge vit À CÔTÉ : l'énoncé d'origine n'est jamais modifié, les
 * autres clients continuent de le lire, et retirer la reformulation le fait
 * réapparaître. L'énoncé d'origine reste affiché au-dessus du champ — sans
 * lui, on ne saurait plus ce qu'on a remplacé.
 */
export default function ReformulationClient({ catalogue, clients = [] }) {
  const { showToast } = useToast()
  const [client, setClient] = useState('')
  const [slug, setSlug] = useState('')
  const [plan, setPlan] = useState(null)
  const [surcharges, setSurcharges] = useState({})
  const [brouillons, setBrouillons] = useState({})
  const [occupe, setOccupe] = useState(null)

  useEffect(() => {
    if (!client || !slug) {
      setPlan(null)
      setSurcharges({})
      return undefined
    }
    let annule = false
    Promise.all([platformApi.referentialOutline(slug), platformApi.clientOverrides(client, slug)])
      .then(([reponsePlan, reponseSurcharges]) => {
        if (annule) return
        setPlan(reponsePlan.data)
        setSurcharges(parMesure(reponseSurcharges.data.overrides))
        setBrouillons({})
      })
      .catch(() => {
        if (!annule) showToast({ type: 'error', message: 'Impossible de charger les énoncés.' })
      })
    return () => {
      annule = true
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [client, slug])

  async function agir(mesureId, appel, succes) {
    setOccupe(mesureId)
    try {
      const reponse = await appel()
      setSurcharges(parMesure(reponse.data.overrides))
      setBrouillons((actuel) => {
        const suivant = { ...actuel }
        delete suivant[mesureId]
        return suivant
      })
      showToast({ type: 'success', message: succes })
    } catch (err) {
      showToast({ type: 'error', message: err.response?.data?.detail || 'Action impossible.' })
    } finally {
      setOccupe(null)
    }
  }

  const mesures = plan?.domains.flatMap((d) => d.measures) ?? []

  return (
    <Card>
      <CardHeader
        title="Reformuler pour un client"
        description="L’énoncé d’origine n’est jamais modifié : la reformulation vit à côté, pour ce client seulement."
      />
      <div className="grid gap-3 sm:grid-cols-2">
        <label className="text-xs text-ink-600">
          Client
          <select className={CHAMP} value={client} onChange={(e) => setClient(e.target.value)}>
            <option value="">Choisir un client…</option>
            {clients.map((c) => (
              <option key={c.tenant_id ?? c.id} value={c.tenant_id ?? c.id}>
                {c.name}
              </option>
            ))}
          </select>
        </label>
        <label className="text-xs text-ink-600">
          Référentiel à reformuler
          <select className={CHAMP} value={slug} onChange={(e) => setSlug(e.target.value)}>
            <option value="">Choisir un référentiel…</option>
            {catalogue.map((ref) => (
              <option key={ref.slug} value={ref.slug}>
                {ref.name}
              </option>
            ))}
          </select>
        </label>
      </div>

      {plan && (
        <ul className="mt-4 divide-y divide-ink-100">
          {mesures.map((m) => {
            const surcharge = surcharges[m.id]
            const valeur = brouillons[m.id] ?? surcharge?.plain_language ?? ''
            return (
              <li key={m.id} className="py-3">
                <div className="flex flex-wrap items-center justify-between gap-2">
                  <p className="text-sm font-medium text-ink-800">
                    <span className="text-xs text-ink-400">{m.code}</span> {m.official_title}
                  </p>
                  {surcharge && <Badge variant="brand">Reformulée</Badge>}
                </div>
                <p className="mt-1 text-xs text-ink-500">
                  <span className="font-medium">Énoncé d’origine : </span>
                  {m.plain_language}
                </p>
                <label className="mt-2 block text-xs text-ink-600">
                  {`Reformulation de la mesure ${m.code}`}
                  <textarea
                    className={CHAMP}
                    rows={2}
                    value={valeur}
                    placeholder="Laisser vide pour conserver l’énoncé d’origine"
                    onChange={(e) => setBrouillons((b) => ({ ...b, [m.id]: e.target.value }))}
                  />
                </label>
                <div className="mt-2 flex gap-2">
                  <Button
                    variant="secondary"
                    disabled={!valeur.trim() || valeur === surcharge?.plain_language}
                    loading={occupe === m.id}
                    onClick={() =>
                      agir(
                        m.id,
                        () =>
                          platformApi.setClientOverride(client, {
                            measure_id: m.id,
                            plain_language: valeur,
                          }),
                        'Reformulation enregistrée pour ce client.'
                      )
                    }
                  >
                    Enregistrer
                  </Button>
                  {surcharge && (
                    <Button
                      variant="ghost"
                      onClick={() =>
                        agir(
                          m.id,
                          () => platformApi.clearClientOverride(client, m.id),
                          'L’énoncé d’origine est rétabli.'
                        )
                      }
                    >
                      Revenir à l’énoncé d’origine
                    </Button>
                  )}
                </div>
              </li>
            )
          })}
        </ul>
      )}
    </Card>
  )
}
