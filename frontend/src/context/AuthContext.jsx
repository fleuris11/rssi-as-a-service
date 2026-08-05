import { createContext, useCallback, useContext, useEffect, useMemo, useState } from 'react'
import { tokenStorage } from '../api/client'
import { authApi } from '../api/endpoints'

const AuthContext = createContext(null)

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null)
  const [tenants, setTenants] = useState([])
  const [currentTenantId, setCurrentTenantId] = useState(tokenStorage.getTenantId())
  const [loading, setLoading] = useState(true)

  const loadMe = useCallback(async () => {
    const response = await authApi.me()
    setUser(response.data)
    const memberships = response.data.memberships || []
    setTenants(memberships)

    const stillValid = memberships.some((m) => m.tenant_id === tokenStorage.getTenantId())
    if (!stillValid) {
      const nextTenantId = memberships[0]?.tenant_id ?? null
      tokenStorage.setTenantId(nextTenantId)
      setCurrentTenantId(nextTenantId)
    }
    return response.data
  }, [])

  useEffect(() => {
    if (!tokenStorage.getAccess()) {
      setLoading(false)
      return
    }
    loadMe().finally(() => setLoading(false))
  }, [loadMe])

  const login = useCallback(
    async (email, password) => {
      const response = await authApi.login(email, password)
      if (response.data.mfa_required) {
        // Second factor required (US-1.3) — no tokens issued yet. The
        // caller (LoginPage) shows the code-entry step and finishes the
        // flow via completeTwoFactorLogin.
        return { mfaRequired: true, challengeToken: response.data.challenge_token }
      }
      tokenStorage.setTokens(response.data.access, response.data.refresh)
      await loadMe()
      return { mfaRequired: false }
    },
    [loadMe]
  )

  const completeTwoFactorLogin = useCallback(
    async (challengeToken, credentials) => {
      const response = await authApi.verifyTwoFactor(challengeToken, credentials)
      tokenStorage.setTokens(response.data.access, response.data.refresh)
      await loadMe()
    },
    [loadMe]
  )

  const register = useCallback(
    async (payload) => {
      await authApi.register(payload)
      await login(payload.email, payload.password)
    },
    [login]
  )

  const logout = useCallback(() => {
    tokenStorage.clear()
    setUser(null)
    setTenants([])
    setCurrentTenantId(null)
  }, [])

  const selectTenant = useCallback((tenantId) => {
    tokenStorage.setTenantId(tenantId)
    setCurrentTenantId(tenantId)
  }, [])

  const currentTenant = useMemo(
    () => tenants.find((t) => t.tenant_id === currentTenantId) || null,
    [tenants, currentTenantId]
  )

  const value = useMemo(
    () => ({
      user,
      tenants,
      currentTenantId,
      currentTenant,
      loading,
      isAuthenticated: Boolean(user),
      login,
      completeTwoFactorLogin,
      register,
      logout,
      selectTenant,
    }),
    [
      user,
      tenants,
      currentTenantId,
      currentTenant,
      loading,
      login,
      completeTwoFactorLogin,
      register,
      logout,
      selectTenant,
    ]
  )

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
}

export function useAuth() {
  const context = useContext(AuthContext)
  if (!context) {
    throw new Error('useAuth doit être utilisé à l’intérieur de AuthProvider.')
  }
  return context
}
