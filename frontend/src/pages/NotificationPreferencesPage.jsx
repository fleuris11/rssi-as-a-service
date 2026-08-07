import { useEffect, useState } from 'react'
import { notificationsApi } from '../api/endpoints'
import Button from '../components/ui/Button'
import Card from '../components/ui/Card'
import { SkeletonText } from '../components/ui/Skeleton'
import { useToast } from '../components/ui/Toast'

export default function NotificationPreferencesPage() {
  const { showToast } = useToast()
  const [weatherEnabled, setWeatherEnabled] = useState(true)
  const [weatherTime, setWeatherTime] = useState('08:00')
  const [realtimeAlertsEnabled, setRealtimeAlertsEnabled] = useState(true)
  const [weatherEnrichmentEnabled, setWeatherEnrichmentEnabled] = useState(false)
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)

  useEffect(() => {
    async function load() {
      setLoading(true)
      try {
        const response = await notificationsApi.getPreferences()
        setWeatherEnabled(response.data.weather_enabled)
        setWeatherTime(response.data.weather_time.slice(0, 5))
        setRealtimeAlertsEnabled(response.data.realtime_alerts_enabled)
        setWeatherEnrichmentEnabled(response.data.weather_enrichment_enabled)
      } catch {
        showToast({ type: 'error', message: 'Impossible de charger vos préférences.' })
      } finally {
        setLoading(false)
      }
    }
    load()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  async function handleSubmit(event) {
    event.preventDefault()
    setSaving(true)
    try {
      await notificationsApi.updatePreferences({
        weather_enabled: weatherEnabled,
        weather_time: `${weatherTime}:00`,
        realtime_alerts_enabled: realtimeAlertsEnabled,
        weather_enrichment_enabled: weatherEnrichmentEnabled,
      })
      showToast({ type: 'success', message: 'Préférences enregistrées.' })
    } catch {
      showToast({ type: 'error', message: 'L’enregistrement a échoué.' })
    } finally {
      setSaving(false)
    }
  }

  return (
    <div className="max-w-lg space-y-6">
      <div>
        <h1 className="font-display text-2xl font-semibold text-ink-900">Préférences de notification</h1>
        <p className="mt-1 text-sm text-ink-500">
          Choisissez quand et comment vous recevez la météo cyber et les alertes.
        </p>
      </div>

      <Card>
        {loading ? (
          <SkeletonText lines={4} />
        ) : (
          <form onSubmit={handleSubmit} className="space-y-5">
            <label className="flex items-start gap-2 text-sm text-ink-700">
              <input
                type="checkbox"
                checked={weatherEnabled}
                onChange={(e) => setWeatherEnabled(e.target.checked)}
                className="mt-0.5"
              />
              Recevoir la météo cyber quotidienne par email
            </label>

            <div>
              <label className="block text-sm font-medium text-ink-700" htmlFor="weather-time">
                Heure d’envoi
              </label>
              <input
                id="weather-time"
                type="time"
                value={weatherTime}
                onChange={(e) => setWeatherTime(e.target.value)}
                disabled={!weatherEnabled}
                className="transition-smooth mt-1 rounded-md border border-ink-200 px-3 py-2 text-sm focus-visible:outline-2 focus-visible:outline-brand-600 disabled:bg-ink-100 disabled:text-ink-500"
              />
            </div>

            <label className="flex items-start gap-2 text-sm text-ink-700">
              <input
                type="checkbox"
                checked={weatherEnrichmentEnabled}
                onChange={(e) => setWeatherEnrichmentEnabled(e.target.checked)}
                disabled={!weatherEnabled}
                className="mt-0.5"
              />
              Enrichir la météo par IA (reformulation plus lisible du résumé — nécessite l’IA activée
              pour l’entreprise ; le résumé standard reste envoyé en cas d’indisponibilité)
            </label>

            <label className="flex items-start gap-2 text-sm text-ink-700">
              <input
                type="checkbox"
                checked={realtimeAlertsEnabled}
                onChange={(e) => setRealtimeAlertsEnabled(e.target.checked)}
                className="mt-0.5"
              />
              Recevoir une alerte email en temps réel (site indisponible, certificat expiré...)
            </label>

            <Button type="submit" variant="primary" loading={saving}>
              Enregistrer
            </Button>
          </form>
        )}
      </Card>
    </div>
  )
}
