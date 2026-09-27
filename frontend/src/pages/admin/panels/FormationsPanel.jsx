import { useCallback, useEffect, useState } from 'react'
import { platformApi } from '../../../api/endpoints'
import Button from '../../../components/ui/Button'
import Card, { CardHeader } from '../../../components/ui/Card'
import EchecChargement from '../../../components/ui/EchecChargement'
import { SkeletonCard } from '../../../components/ui/Skeleton'
import { useToast } from '../../../components/ui/Toast'

/**
 * La bibliothèque de cours, et ce qu'on en propose à chaque client.
 *
 * Le pendant de `ReferentialsPanel`, et il manquait pour la même raison : les
 * cours existaient, la mesure existait, mais l'attribution n'avait aucun
 * chemin dans l'interface — seule une commande Django savait la faire. Un
 * module dont l'exploitant ne peut rien proposer n'est pas un module.
 *
 * Deux chiffres sont affichés parce qu'ils décident de ce qu'on fait :
 * la durée annoncée (elle est **calculée** depuis les écrans, jamais saisie),
 * et le nombre de salariés encore inscrits — c'est lui qui fait hésiter avant
 * un retrait.
 */
export default function FormationsPanel({ clients = [] }) {
  const { showToast } = useToast()
  const [clientChoisi, setClientChoisi] = useState('')
  const [etat, setEtat] = useState(null)
  const [echec, setEchec] = useState(false)
  const [enCours, setEnCours] = useState(null)

  const charger = useCallback(async (tenantId) => {
    if (!tenantId) {
      setEtat(null)
      setEchec(false)
      return
    }
    setEchec(false)
    try {
      const response = await platformApi.clientCourses(tenantId)
      setEtat(response.data)
    } catch {
      // Un squelette qui ne se remplit jamais est pire qu'un message : on dit
      // que ça a échoué, et on laisse de quoi réessayer.
      setEtat(null)
      setEchec(true)
    }
  }, [])

  useEffect(() => {
    charger(clientChoisi)
  }, [clientChoisi, charger])

  async function agir(slug, action, message) {
    setEnCours(slug)
    try {
      const response = await action(clientChoisi, slug)
      setEtat(response.data)
      showToast({ type: 'success', message })
    } catch (err) {
      showToast({
        type: 'error',
        message: err.response?.data?.detail || 'Opération impossible.',
      })
    } finally {
      setEnCours(null)
    }
  }

  const proposer = (slug) =>
    agir(slug, platformApi.assignCourse, 'Cours proposé au client.')

  const retirer = (slug) =>
    agir(
      slug,
      platformApi.revokeCourse,
      // Dit à chaque retrait : c'est la question que se pose celui qui clique.
      'Cours retiré. Les salariés déjà inscrits terminent leur parcours.',
    )

  return (
    <div className="space-y-4">
      <Card>
        <CardHeader
          title="Proposer des formations à un client"
          description="Un client ne voit que les cours qui lui sont proposés. Les cours qu'un client a écrits lui-même n'apparaissent pas ici : ils ne se proposent pas à quelqu'un d'autre."
        />
        <label className="t-legende" htmlFor="client-formations">
          Client
        </label>
        <select
          id="client-formations"
          className="mt-1 w-full max-w-md rounded-md border border-ink-200 bg-surface px-3 py-2 text-sm"
          value={clientChoisi}
          onChange={(event) => setClientChoisi(event.target.value)}
        >
          <option value="">Choisir un client…</option>
          {clients.map((client) => (
            <option key={client.tenant_id ?? client.id} value={client.tenant_id ?? client.id}>
              {client.name}
            </option>
          ))}
        </select>

        {echec && <EchecChargement onReessayer={() => charger(clientChoisi)} />}

        {clientChoisi && !etat && !echec && <SkeletonCard />}

        {etat && (
          <div className="mt-4 grid gap-6 lg:grid-cols-2">
            <div>
              <p className="t-legende">Proposés</p>
              <ul className="mt-2 divide-y divide-ink-100">
                {etat.assigned.length === 0 && (
                  <li className="py-2 text-sm text-ink-500">Aucun.</li>
                )}
                {etat.assigned.map((cours) => (
                  <li key={cours.slug} className="flex items-start justify-between gap-3 py-2">
                    <div className="min-w-0">
                      <p className="text-sm text-ink-700">{cours.title}</p>
                      <p className="t-meta text-ink-500">
                        <span className="num">{cours.minutes}</span> min · seuil{' '}
                        <span className="num">{cours.pass_threshold}</span> %
                        {cours.ongoing > 0 && (
                          <>
                            {' · '}
                            <span className="num">{cours.ongoing}</span> salarié
                            {cours.ongoing > 1 ? 's' : ''} en cours
                          </>
                        )}
                      </p>
                    </div>
                    <Button
                      variant="secondary"
                      loading={enCours === cours.slug}
                      onClick={() => retirer(cours.slug)}
                    >
                      Retirer
                    </Button>
                  </li>
                ))}
              </ul>
            </div>
            <div>
              <p className="t-legende">Bibliothèque</p>
              <ul className="mt-2 divide-y divide-ink-100">
                {etat.available.length === 0 && (
                  <li className="py-2 text-sm text-ink-500">
                    Toute la bibliothèque lui est déjà proposée.
                  </li>
                )}
                {etat.available.map((cours) => (
                  <li key={cours.slug} className="flex items-start justify-between gap-3 py-2">
                    <div className="min-w-0">
                      <p className="text-sm text-ink-700">{cours.title}</p>
                      <p className="t-meta text-ink-500">
                        <span className="num">{cours.minutes}</span> min ·{' '}
                        <span className="num">{cours.screens}</span> écrans ·{' '}
                        <span className="num">{cours.questions}</span> questions
                      </p>
                    </div>
                    <Button
                      variant="primary"
                      loading={enCours === cours.slug}
                      onClick={() => proposer(cours.slug)}
                    >
                      Proposer
                    </Button>
                  </li>
                ))}
              </ul>
            </div>
          </div>
        )}
      </Card>
    </div>
  )
}
