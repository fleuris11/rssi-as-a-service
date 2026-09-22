/**
 * L'ÂGE D'UNE INFORMATION, en clair.
 *
 * « il y a 3 jours », jamais une date nue qu'il faut soustraire de tête. Une
 * date exacte reste accessible au survol et aux technologies d'assistance via
 * l'attribut `dateTime` et le titre — on ne perd rien, on épargne un calcul.
 *
 * C'est l'une des quatre disciplines empruntées aux mondes adverses du tirage
 * de direction (docs/design.md § « Les relèvements ») : dans ce produit, une
 * fuite de 2019 et une fuite d'hier n'appellent pas la même réaction, et
 * l'écart doit se lire sans effort.
 */
export default function Age({ date, prefixe = '', className = '' }) {
  if (!date) return <span className={className}>—</span>

  const instant = new Date(date)
  if (Number.isNaN(instant.getTime())) return <span className={className}>—</span>

  const jours = Math.floor((Date.now() - instant.getTime()) / 86_400_000)
  const exacte = instant.toLocaleDateString('fr-FR', {
    day: 'numeric',
    month: 'long',
    year: 'numeric',
  })

  return (
    <time dateTime={instant.toISOString()} title={exacte} className={className}>
      {prefixe}
      {formuler(jours)}
    </time>
  )
}

export function formuler(jours) {
  if (jours < 0) return 'à venir'
  if (jours === 0) return "aujourd'hui"
  if (jours === 1) return 'hier'
  if (jours < 31) return `il y a ${jours} jours`
  const mois = Math.round(jours / 30.4)
  if (mois < 24) return `il y a ${mois} mois`
  return `il y a ${Math.round(jours / 365)} ans`
}
