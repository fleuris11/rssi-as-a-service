import { createContext, useCallback, useContext, useEffect, useMemo, useState } from 'react'
import { billingApi } from '../api/endpoints'
import { useAuth } from './AuthContext'

const EntitlementsContext = createContext(null)

/**
 * Droits de l'entreprise courante, chargés une fois et partagés.
 *
 * En cas d'échec de chargement, on considère les fonctionnalités comme
 * **incluses** plutôt que refusées : le serveur reste l'autorité (chaque
 * endpoint applique sa propre garde), et griser toute l'interface parce
 * qu'un appel a échoué transformerait un incident réseau passager en
 * dégradation visible du produit. Le pire cas est un bouton actif qui
 * renvoie un refus explicite — pas un produit qui paraît vide.
 */
export function EntitlementsProvider({ children }) {
  const { currentTenantId } = useAuth()
  const [data, setData] = useState(null)
  const [loading, setLoading] = useState(true)
  const [failed, setFailed] = useState(false)

  const load = useCallback(async () => {
    if (!currentTenantId) {
      setData(null)
      setLoading(false)
      return
    }
    setLoading(true)
    try {
      const response = await billingApi.entitlements()
      setData(response.data)
      setFailed(false)
    } catch {
      setData(null)
      setFailed(true)
    } finally {
      setLoading(false)
    }
  }, [currentTenantId])

  useEffect(() => {
    load()
  }, [load])

  const value = useMemo(() => {
    const byKey = new Map((data?.features || []).map((f) => [f.key, f]))

    return {
      loading,
      subscription: data?.subscription || null,
      quotas: data?.quotas || null,
      features: data?.features || [],
      // Optimiste en cas d'échec — voir la note ci-dessus.
      hasFeature: (key) => (failed || !data ? true : Boolean(byKey.get(key)?.included)),
      featureInfo: (key) => byKey.get(key) || null,
      requiredPlanFor: (key) => byKey.get(key)?.required_plan || '',
      isOperational: data?.subscription ? data.subscription.is_operational : true,
      reload: load,
    }
  }, [data, loading, failed, load])

  return (
    <EntitlementsContext.Provider value={value}>{children}</EntitlementsContext.Provider>
  )
}

export function useEntitlements() {
  const context = useContext(EntitlementsContext)
  if (!context) {
    throw new Error('useEntitlements doit être utilisé à l’intérieur d’EntitlementsProvider.')
  }
  return context
}
