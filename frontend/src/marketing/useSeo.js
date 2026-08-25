import { useEffect } from 'react'

const SITE_URL = 'https://rssiasservice.online'
const DEFAULT_IMAGE = `${SITE_URL}/og-image.jpg`

function setMeta(attr, key, content) {
  if (!content) return
  let tag = document.head.querySelector(`meta[${attr}="${key}"]`)
  if (!tag) {
    tag = document.createElement('meta')
    tag.setAttribute(attr, key)
    document.head.appendChild(tag)
  }
  tag.setAttribute('content', content)
}

function setCanonical(path) {
  let link = document.head.querySelector('link[rel="canonical"]')
  if (!link) {
    link = document.createElement('link')
    link.setAttribute('rel', 'canonical')
    document.head.appendChild(link)
  }
  link.setAttribute('href', `${SITE_URL}${path}`)
}

/**
 * Métadonnées par page, posées à la main dans le <head>.
 *
 * Pas de react-helmet ni d'équivalent : une seule dépendance de plus pour
 * écrire quatre balises serait disproportionnée sur une page dont l'argument
 * est la sobriété. La contrepartie assumée est que ces balises sont posées
 * côté client : un robot qui n'exécute pas JavaScript ne les verra pas. Pour
 * un site vitrine dont l'acquisition ne passe pas prioritairement par le
 * référencement, c'est acceptable ; un rendu côté serveur serait la réponse
 * si cela changeait.
 */
export function useSeo({ title, description, path = '/', type = 'website', jsonLd }) {
  useEffect(() => {
    const fullTitle = title ? `${title} — RSSI as a Service` : 'RSSI as a Service'
    document.title = fullTitle

    setMeta('name', 'description', description)
    setMeta('property', 'og:title', fullTitle)
    setMeta('property', 'og:description', description)
    setMeta('property', 'og:type', type)
    setMeta('property', 'og:url', `${SITE_URL}${path}`)
    setMeta('property', 'og:image', DEFAULT_IMAGE)
    setMeta('property', 'og:locale', 'fr_FR')
    setMeta('name', 'twitter:card', 'summary_large_image')
    setMeta('name', 'twitter:title', fullTitle)
    setMeta('name', 'twitter:description', description)
    setCanonical(path)

    if (!jsonLd) return undefined
    const script = document.createElement('script')
    script.type = 'application/ld+json'
    script.textContent = JSON.stringify(jsonLd)
    document.head.appendChild(script)
    return () => document.head.removeChild(script)
  }, [title, description, path, type, jsonLd])
}

export const ORGANISATION_JSON_LD = {
  '@context': 'https://schema.org',
  '@type': 'Organization',
  name: 'RSSI as a Service',
  url: SITE_URL,
  description:
    "Surveillance des fuites de données et accompagnement à la conformité pour les PME.",
  contactPoint: {
    '@type': 'ContactPoint',
    contactType: 'sales',
    email: 'contact@rssiasservice.online',
    availableLanguage: ['French'],
  },
}
