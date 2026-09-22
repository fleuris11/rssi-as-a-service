import ChiffreAnime from './ChiffreAnime'
import { ORDRE_CRANS, CRANS, cranDe } from './crans'

/**
 * LA JAUGE — le score d'exposition, son cran, et l'échelle sur laquelle il se
 * place.
 *
 * Pas un anneau de progression : le plancher de qualité refuse les anneaux et
 * les mini-courbes qui tiennent lieu de contenu. Ici l'échelle est une RÈGLE à
 * quatre crans, comme la graduation d'un cadran, et le score se pose dessus.
 * On voit d'un coup d'œil non seulement la valeur, mais où elle tombe.
 *
 * Le glyphe et le mot accompagnent toujours la couleur (`crans.js`).
 */
export default function Jauge({ score, niveau, libelle = 'Exposition', anime = false }) {
  const cran = cranDe(score, niveau)
  const valeur = Number(score)
  const connu = Number.isFinite(valeur) && cran

  return (
    <div>
      <p className="t-legende">{libelle}</p>

      <div className="mt-1 flex items-end gap-3">
        <p className={`n-grand ${connu ? 'text-ink-900' : 'text-ink-400'}`}>
          {connu ? (
            anime ? (
              <ChiffreAnime valeur={valeur} />
            ) : (
              Math.round(valeur)
            )
          ) : (
            '—'
          )}
        </p>
        <p className="t-meta pb-2">sur 100</p>
      </div>

      <p className={`mt-1.5 flex items-center gap-1.5 text-sm font-semibold ${connu ? cran.texte : 'text-ink-500'}`}>
        <span aria-hidden="true">{connu ? cran.glyphe : '○'}</span>
        {connu ? cran.nom : 'Non mesuré'}
      </p>

      {/* La règle graduée : quatre crans, celui qui est atteint est plein. */}
      <div className="mt-3 flex gap-1" aria-hidden="true">
        {ORDRE_CRANS.map((nom) => {
          const atteint = connu && ORDRE_CRANS.indexOf(nom) <= ORDRE_CRANS.indexOf(cranNom(cran))
          return (
            <span
              key={nom}
              className={`h-1.5 flex-1 rounded-sm ${atteint ? '' : 'bg-ink-200'}`}
              style={atteint ? { backgroundColor: CRANS[nom].trait } : undefined}
            />
          )
        })}
      </div>
      <p className="lecture-seule">
        {connu
          ? `Score ${Math.round(valeur)} sur 100, niveau ${cran.nom}.`
          : 'Score non mesuré.'}
      </p>
    </div>
  )
}

function cranNom(cran) {
  return ORDRE_CRANS.find((nom) => CRANS[nom].cle === cran.cle)
}
