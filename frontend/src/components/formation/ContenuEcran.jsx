import { Info, Lightbulb, TriangleAlert } from 'lucide-react'
import { segmentsGras } from './texteRiche'

/** Le texte d'un bloc, avec ses passages en gras — et sans aucun HTML. */
function Texte({ children }) {
  return segmentsGras(children).map((segment, index) =>
    segment.gras ? <strong key={index}>{segment.texte}</strong> : <span key={index}>{segment.texte}</span>
  )
}

/**
 * Le rendu d'un écran de cours, bloc par bloc.
 *
 * Le contenu est validé à l'ÉCRITURE (backend/apps/training/blocks.py) : ce
 * composant n'a donc pas de chemin d'erreur pour cause de bloc mal formé, et
 * n'en invente pas. Un type inconnu est ignoré silencieusement plutôt
 * qu'affiché en rouge — si un jour le studio produit un septième type que
 * cette version ne connaît pas encore, un salarié doit voir un écran
 * incomplet, pas un message technique.
 *
 * Accessibilité : le titre de l'écran est un h2 porté par la page, donc les
 * blocs « titre » ne peuvent être que h3 ou h4 — c'est vérifié côté serveur.
 * La hiérarchie des en-têtes est ce qui permet de naviguer au lecteur d'écran.
 */

const TONS = {
  info: {
    icone: Info,
    classes: 'border-brand-200 bg-brand-50 text-ink-800',
    libelle: 'Information',
  },
  attention: {
    icone: TriangleAlert,
    classes: 'border-warning-border bg-warning-subtle text-ink-900',
    libelle: 'Point de vigilance',
  },
  exemple: {
    icone: Lightbulb,
    classes: 'border-ink-200 bg-ink-50 text-ink-800',
    libelle: 'Exemple',
  },
}

function Encadre({ ton, texte }) {
  const { icone: Icone, classes, libelle } = TONS[ton] ?? TONS.info
  return (
    <div className={`flex gap-3 rounded-lg border p-4 ${classes}`}>
      <Icone className="mt-0.5 size-5 shrink-0" aria-hidden="true" />
      <p className="text-[0.95rem] leading-relaxed">
        {/* Le ton est porté par la couleur ET par un mot : une couleur seule
            ne dit rien à qui ne la distingue pas. */}
        <span className="sr-only">{libelle} : </span>
        <Texte>{texte}</Texte>
      </p>
    </div>
  )
}

function Bloc({ bloc }) {
  switch (bloc.type) {
    case 'paragraphe':
      return (
        <p className="text-[1.05rem] leading-relaxed text-ink-800">
          <Texte>{bloc.texte}</Texte>
        </p>
      )

    case 'titre': {
      const Niveau = bloc.niveau === 4 ? 'h4' : 'h3'
      return (
        <Niveau className="text-lg font-semibold text-ink-900">{bloc.texte}</Niveau>
      )
    }

    case 'liste': {
      const Liste = bloc.ordonnee ? 'ol' : 'ul'
      return (
        <Liste
          className={`ml-5 space-y-2 text-[1.05rem] leading-relaxed text-ink-800 ${
            bloc.ordonnee ? 'list-decimal' : 'list-disc'
          }`}
        >
          {bloc.items.map((item, index) => (
            <li key={index}>
              <Texte>{item}</Texte>
            </li>
          ))}
        </Liste>
      )
    }

    case 'encadre':
      return <Encadre ton={bloc.ton} texte={bloc.texte} />

    case 'image':
      return (
        <img
          src={bloc.source}
          alt={bloc.alternative}
          className="w-full rounded-lg border border-ink-200"
        />
      )

    case 'citation':
      return (
        <figure className="border-l-2 border-ink-300 pl-4">
          <blockquote className="text-[1.05rem] italic leading-relaxed text-ink-700">
            <Texte>{bloc.texte}</Texte>
          </blockquote>
          {bloc.source && (
            <figcaption className="mt-1 text-sm text-ink-500">— {bloc.source}</figcaption>
          )}
        </figure>
      )

    default:
      return null
  }
}

export default function ContenuEcran({ blocs = [] }) {
  return (
    <div className="space-y-4">
      {blocs.map((bloc, index) => (
        <Bloc key={index} bloc={bloc} />
      ))}
    </div>
  )
}
