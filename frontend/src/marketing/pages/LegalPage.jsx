import { AlertTriangle } from 'lucide-react'
import MarketingLayout from '../components/MarketingLayout'
import { SITE } from '../content'
import { useSeo } from '../useSeo'

/**
 * Pages légales. Le contenu juridique doit être rédigé ou validé par un
 * professionnel : ce qui figure ici est une trame honnête, qui décrit
 * fidèlement ce que le produit fait techniquement (et qui est donc utile au
 * juriste), assortie d'un avertissement visible plutôt que d'un faux texte
 * d'apparence définitive. Publier un texte juridique inventé serait pire que
 * de ne rien publier.
 */
const PAGES = {
  legal: {
    title: 'Mentions légales',
    description: 'Mentions légales du service RSSI as a Service.',
    path: '/mentions-legales',
    sections: [
      {
        heading: 'Éditeur du service',
        body: "Raison sociale, forme juridique, capital social, adresse du siège, numéro d'immatriculation et numéro de TVA intracommunautaire : à compléter.",
      },
      {
        heading: 'Directeur de la publication',
        body: 'À compléter.',
      },
      {
        heading: 'Hébergement',
        body: "Le service est hébergé sur une infrastructure située dans l'Union européenne. Nom et adresse de l'hébergeur : à compléter.",
      },
      {
        heading: 'Contact',
        body: `Pour toute question relative au service : ${SITE.contactEmail}`,
      },
      {
        heading: 'Propriété intellectuelle',
        body: "L'ensemble des contenus de ce site est protégé. Toute reproduction sans autorisation est interdite.",
      },
    ],
  },
  privacy: {
    title: 'Politique de confidentialité',
    description:
      'Données collectées, durées de conservation et transmissions à des tiers pour le service RSSI as a Service.',
    path: '/confidentialite',
    sections: [
      {
        heading: 'Données que nous traitons',
        body: "Trois catégories. (1) Vos données de compte : nom, adresse email professionnelle, société, rôle. (2) Les actifs que vous déclarez : noms de domaine, sites, domaines de messagerie. (3) Les résultats de surveillance : éléments retrouvés dans des fuites de données concernant les actifs que vous avez déclarés, ce qui peut inclure des adresses email et des mots de passe fuités.",
      },
      {
        heading: 'Mots de passe retrouvés dans des fuites',
        body: "Ils sont chiffrés dès leur réception et ne sont jamais lisibles par défaut. En consulter la valeur exacte exige d'être administrateur de l'espace client et de re-prouver son identité à ce moment précis. Chaque consultation, acceptée ou refusée, est enregistrée avec son auteur, sa date et son adresse IP. Ces valeurs sont effacées automatiquement au bout de 90 jours ; l'historique de la fuite est conservé sans la valeur.",
      },
      {
        heading: 'Transmissions à des tiers',
        body: "Deux flux sortants. Vers notre fournisseur de renseignement sur les fuites : uniquement les noms de domaine que vous avez déclarés. Vers un fournisseur d'intelligence artificielle, pour la rédaction de synthèses : un contexte pseudonymisé, dans lequel noms, adresses email et noms de domaine sont remplacés par des identifiants neutres avant l'envoi. Aucun mot de passe n'est transmis à un tiers, sous aucune forme.",
      },
      {
        heading: 'Durées de conservation',
        body: "Mots de passe retrouvés : 90 jours. Journal des consultations : 365 jours. Données de compte : durée de la relation contractuelle, puis suppression ou anonymisation. Demandes de démonstration : le temps du suivi commercial.",
      },
      {
        heading: 'Vos droits',
        body: `Vous disposez d'un droit d'accès, de rectification, d'effacement, de limitation et d'opposition sur vos données. Pour l'exercer : ${SITE.contactEmail}. Les modalités précises et le délai de réponse sont à compléter avec notre conseil juridique.`,
      },
      {
        heading: 'Mesure d’audience',
        body: "Ce site n'utilise aucun traceur publicitaire, aucun cookie tiers et aucun outil de mesure d'audience. Aucun consentement n'est donc demandé, faute d'objet.",
      },
    ],
  },
  contact: {
    title: 'Contact',
    description: 'Contacter l’équipe RSSI as a Service.',
    path: '/contact',
    sections: [
      {
        heading: 'Demande de démonstration',
        body: "Le plus simple est de passer par le formulaire dédié : nous vous recontactons sous un jour ouvré pour convenir d'un créneau.",
      },
      {
        heading: 'Questions commerciales ou techniques',
        body: `Écrivez-nous à ${SITE.contactEmail}.`,
      },
      {
        heading: 'Signaler une vulnérabilité',
        body: "Si vous pensez avoir identifié une faille de sécurité sur ce service, écrivez-nous directement plutôt que de la publier. Nous accusons réception et vous tenons informé du traitement.",
      },
      {
        heading: 'Adresse postale',
        body: 'À compléter.',
      },
    ],
  },
}

export default function LegalPage({ page }) {
  const content = PAGES[page]
  useSeo({ title: content.title, description: content.description, path: content.path })

  const needsCompletion = page !== 'privacy'

  return (
    <MarketingLayout>
      <div className="mx-auto max-w-3xl px-5 py-16 sm:py-20">
        <h1 className="font-display text-3xl font-semibold text-ink-900">{content.title}</h1>

        {needsCompletion && (
          <div className="mt-6 flex gap-3 rounded-md border border-warning-strong/30 bg-warning-subtle px-4 py-3">
            <AlertTriangle
              className="mt-0.5 size-4 shrink-0 text-warning-strong"
              aria-hidden="true"
            />
            <p className="text-sm leading-relaxed text-warning-strong">
              Cette page comporte des mentions à compléter par l’éditeur. Le contenu juridique
              définitif doit être rédigé ou validé par un professionnel du droit.
            </p>
          </div>
        )}

        <div className="mt-10 space-y-9">
          {content.sections.map((section) => (
            <section key={section.heading}>
              <h2 className="font-display text-lg font-semibold text-ink-900">
                {section.heading}
              </h2>
              <p className="mt-2.5 text-sm leading-relaxed text-ink-600">{section.body}</p>
            </section>
          ))}
        </div>
      </div>
    </MarketingLayout>
  )
}
