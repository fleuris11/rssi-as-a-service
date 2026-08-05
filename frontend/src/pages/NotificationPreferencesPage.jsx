import { useEffect, useState } from 'react'
import { notificationsApi } from '../api/endpoints'

export default function NotificationPreferencesPage() {
  const [weatherEnabled, setWeatherEnabled] = useState(true)
  const [weatherTime, setWeatherTime] = useState('08:00')
  const [realtimeAlertsEnabled, setRealtimeAlertsEnabled] = useState(true)
  const [weatherEnrichmentEnabled, setWeatherEnrichmentEnabled] = useState(false)
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState('')
  const [saved, setSaved] = useState(false)

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
        setError('Impossible de charger vos préférences.')
      } finally {
        setLoading(false)
      }
    }
    load()
  }, [])

  async function handleSubmit(event) {
    event.preventDefault()
    setSaving(true)
    setError('')
    setSaved(false)
    try {
      await notificationsApi.updatePreferences({
        weather_enabled: weatherEnabled,
        weather_time: `${weatherTime}:00`,
        realtime_alerts_enabled: realtimeAlertsEnabled,
        weather_enrichment_enabled: weatherEnrichmentEnabled,
      })
      setSaved(true)
    } catch {
      setError("L'enregistrement a échoué.")
    } finally {
      setSaving(false)
    }
  }

  if (loading) {
    return <p className="text-slate-500">Chargement…</p>
  }

  return (
    <div className="max-w-lg space-y-6">
      <div>
        <h1 className="text-2xl font-semibold text-slate-900">Préférences de notification</h1>
        <p className="mt-1 text-sm text-slate-500">
          Choisissez quand et comment vous recevez la météo cyber et les alertes.
        </p>
      </div>

      <form
        onSubmit={handleSubmit}
        className="space-y-5 rounded-lg border border-slate-200 bg-white p-6 shadow-sm"
      >
        <label className="flex items-start gap-2 text-sm text-slate-700">
          <input
            type="checkbox"
            checked={weatherEnabled}
            onChange={(e) => setWeatherEnabled(e.target.checked)}
            className="mt-0.5"
          />
          Recevoir la météo cyber quotidienne par email
        </label>

        <div>
          <label className="block text-sm font-medium text-slate-700" htmlFor="weather-time">
            Heure d’envoi
          </label>
          <input
            id="weather-time"
            type="time"
            value={weatherTime}
            onChange={(e) => setWeatherTime(e.target.value)}
            disabled={!weatherEnabled}
            className="mt-1 rounded-md border border-slate-300 px-3 py-2 text-sm disabled:bg-slate-100 disabled:text-slate-500"
          />
        </div>

        <label className="flex items-start gap-2 text-sm text-slate-700">
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

        <label className="flex items-start gap-2 text-sm text-slate-700">
          <input
            type="checkbox"
            checked={realtimeAlertsEnabled}
            onChange={(e) => setRealtimeAlertsEnabled(e.target.checked)}
            className="mt-0.5"
          />
          Recevoir une alerte email en temps réel (site indisponible, certificat expiré...)
        </label>

        {error && <p className="text-sm text-red-600">{error}</p>}
        {saved && <p className="text-sm text-emerald-600">Préférences enregistrées.</p>}

        <button
          type="submit"
          disabled={saving}
          className="rounded-md bg-slate-900 px-4 py-2 text-sm font-medium text-white hover:bg-slate-800 disabled:opacity-50"
        >
          {saving ? 'Enregistrement…' : 'Enregistrer'}
        </button>
      </form>
    </div>
  )
}
