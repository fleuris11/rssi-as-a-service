"""La bibliothèque de cours livrée avec le produit.

Pourquoi ici et non dans la commande de chargement : le contenu est une
DONNÉE, la commande est un mécanisme. Séparer les deux permet aux tests de
vérifier chaque cours sans exécuter de chargement, et à la commande de rester
assez courte pour qu'on la relise.

Le cours « hameçonnage » n'est pas repris ici : il est déjà chargé par
``seed_training_demo`` (F1) et sa version publiée porte des inscriptions. Le
dupliquer créerait deux cours du même sujet dans le catalogue.

Règles d'écriture suivies par tous les cours, et la raison de chacune :

- **cinq questions au moins**, parce qu'en deçà un seuil de réussite ne veut
  plus rien dire : une seule erreur fait basculer le résultat
  (``QUESTIONS_MINIMUM_POUR_UN_SEUIL``) ;
- **chaque question est rattachée à l'écran qui y répond**, pour que « revoir
  ce que vous avez raté » ait une source ;
- **l'explication est écrite même quand la réponse attendue est évidente** :
  c'est la seule partie du quiz qui forme ;
- **aucun piège** : les mauvaises réponses sont des erreurs courantes et
  plausibles, pas des absurdités. Une mauvaise réponse ridicule ne mesure
  rien ;
- **aucune image** : un bloc ``image`` doit désigner un fichier livré avec
  l'application (``PREFIXE_IMAGE``). Tant que le dépôt n'en porte pas, le
  catalogue s'en passe plutôt que de pointer vers un fichier absent ;
- **une seule variable dans tout le catalogue**, dans le dernier écran du
  cours sur les appareils, et avec sa formulation de repli. Les cours de
  bibliothèque sont lus par tous les clients : un texte qui dépend de données
  que la plupart n'ont pas encore serait un texte de repli déguisé.
"""

from apps.training.models import Question

#: Un seuil plus haut que le défaut (70) sur les cours dont une erreur coûte de
#: l'argent tout de suite. Ailleurs le défaut suffit : un quiz est un outil
#: pédagogique, pas un examen d'embauche.
SEUIL_EXIGEANT = 80

UNIQUE = Question.Kind.SINGLE
MULTIPLE = Question.Kind.MULTIPLE


COURS = [
    # ----------------------------------------------------------------- 1 -----
    {
        "slug": "mots-de-passe",
        "title": "Mots de passe : un par service, et une deuxième clé",
        "summary": "Pourquoi un seul mot de passe réutilisé suffit à ouvrir toute "
        "l'entreprise, comment en fabriquer un dont on se souvient, et à quoi sert le "
        "code reçu sur le téléphone.",
        "seuil": SEUIL_EXIGEANT,
        "ecrans": [
            {
                "title": "Un mot de passe, et toute l'entreprise s'ouvre",
                "seconds": 90,
                "content": [
                    {
                        "type": "paragraphe",
                        "texte": "Les attaquants n'essaient presque jamais de deviner votre "
                        "mot de passe. Ils le connaissent déjà : il a fuité d'un site sur "
                        "lequel vous vous étiez inscrit, parfois il y a des années, et il "
                        "circule dans des listes de plusieurs milliards de lignes.",
                    },
                    {
                        "type": "paragraphe",
                        "texte": "Ce qui transforme cette fuite en incident, c'est la "
                        "**réutilisation**. Le même mot de passe sur un site de covoiturage "
                        "et sur la messagerie professionnelle, et la liste devient une clé.",
                    },
                    {
                        "type": "encadre",
                        "ton": "exemple",
                        "texte": "Une boutique en ligne se fait voler sa base de clients. "
                        "Votre adresse professionnelle y figure, avec le mot de passe que "
                        "vous utilisez aussi au bureau. Personne n'a attaqué votre "
                        "entreprise : elle est pourtant ouverte.",
                    },
                    {
                        "type": "paragraphe",
                        "texte": "C'est pour cela qu'un mot de passe long ne suffit pas s'il "
                        "est partagé entre plusieurs services. La longueur protège contre "
                        "celui qui cherche ; elle ne protège pas contre celui qui sait.",
                    },
                ],
            },
            {
                "title": "Un mot de passe qui tient",
                "seconds": 90,
                "content": [
                    {
                        "type": "paragraphe",
                        "texte": "La règle a changé, et beaucoup d'entreprises appliquent "
                        "encore l'ancienne. Ce qui rend un mot de passe résistant, c'est "
                        "d'abord sa **longueur**, pas sa ponctuation.",
                    },
                    {"type": "titre", "niveau": 3, "texte": "La phrase de passe"},
                    {
                        "type": "paragraphe",
                        "texte": "Quatre ou cinq mots sans rapport entre eux, que vous êtes "
                        "seul à pouvoir associer : c'est long, c'est solide, et cela se "
                        "retient. « cerisier tramway onze pluie » se tape en quelques "
                        "secondes et se retient mieux que « P@ssw0rd2026! ».",
                    },
                    {
                        "type": "liste",
                        "items": [
                            "Évitez une citation connue, un titre de chanson ou un proverbe : "
                            "ils figurent dans les listes d'essai.",
                            "Évitez ce qui vous désigne : prénoms, dates de naissance, nom de "
                            "l'entreprise, plaque du véhicule.",
                            "N'ajoutez pas un chiffre à la fin d'un mot de passe existant : "
                            "c'est la première variation testée.",
                        ],
                    },
                    {
                        "type": "encadre",
                        "ton": "info",
                        "texte": "Le changement obligatoire tous les trois mois n'est plus "
                        "recommandé. Il pousse à des variations prévisibles et à des "
                        "pense-bêtes sous le clavier. On change un mot de passe quand on a "
                        "une raison de croire qu'il a fuité.",
                    },
                ],
            },
            {
                "title": "Un par service, et un coffre pour les tenir",
                "seconds": 90,
                "content": [
                    {
                        "type": "paragraphe",
                        "texte": "Un mot de passe différent par service est la seule règle "
                        "qui empêche une fuite de s'étendre. Personne ne peut retenir "
                        "quarante phrases de passe : c'est le travail d'un gestionnaire de "
                        "mots de passe.",
                    },
                    {
                        "type": "paragraphe",
                        "texte": "Un gestionnaire est un coffre chiffré. Vous retenez **une "
                        "seule** phrase de passe, celle du coffre ; il retient les autres, "
                        "les remplit à votre place, et refuse de les remplir sur un site "
                        "dont l'adresse ne correspond pas — ce qui vous protège au passage "
                        "d'une fausse page de connexion.",
                    },
                    {"type": "titre", "niveau": 3, "texte": "Ce qui ne remplace pas un coffre"},
                    {
                        "type": "liste",
                        "items": [
                            "Un fichier tableur, même nommé « divers » : il est lisible par "
                            "tout programme qui passe sur le poste.",
                            "Le carnet dans le tiroir : il survit mal à un départ et se "
                            "photographie en une seconde.",
                            "La mémoire du navigateur sur un poste partagé : quiconque ouvre "
                            "la session ouvre les comptes.",
                        ],
                    },
                    {
                        "type": "encadre",
                        "ton": "attention",
                        "texte": "Un compte ne se partage pas. Si plusieurs personnes doivent "
                        "accéder au même service, demandez plusieurs comptes, ou un partage "
                        "par le coffre. Un compte partagé rend impossible de savoir qui a "
                        "fait quoi — et de couper l'accès à une seule personne.",
                    },
                ],
            },
            {
                "title": "La deuxième clé",
                "seconds": 90,
                "content": [
                    {
                        "type": "paragraphe",
                        "texte": "L'authentification à deux facteurs ajoute une seconde "
                        "preuve à la connexion : quelque chose que vous savez, le mot de "
                        "passe, et quelque chose que vous avez, le téléphone ou une clé. Un "
                        "mot de passe volé ne suffit plus.",
                    },
                    {
                        "type": "paragraphe",
                        "texte": "C'est la mesure qui a le meilleur rapport entre l'effort et "
                        "l'effet. Activez-la d'abord sur la **messagerie** : c'est par elle "
                        "qu'on réinitialise tous les autres mots de passe.",
                    },
                    {
                        "type": "titre",
                        "niveau": 3,
                        "texte": "Toutes les secondes clés ne valent pas la même chose",
                    },
                    {
                        "type": "liste",
                        "ordonnee": True,
                        "items": [
                            "Une clé physique ou une empreinte : le plus solide.",
                            "Une application qui affiche un code à six chiffres : très bien, "
                            "et gratuit.",
                            "Un code par message texte : mieux que rien, mais un numéro peut "
                            "être détourné auprès de l'opérateur.",
                        ],
                    },
                    {
                        "type": "encadre",
                        "ton": "info",
                        "texte": "Conservez les codes de secours fournis à l'activation, "
                        "ailleurs que dans le téléphone. Un téléphone perdu sans code de "
                        "secours, c'est un compte perdu.",
                    },
                ],
            },
            {
                "title": "Quand on vous demande votre code",
                "seconds": 75,
                "content": [
                    {
                        "type": "paragraphe",
                        "texte": "Les attaquants se sont adaptés. Puisqu'ils ne peuvent plus "
                        "se connecter avec le seul mot de passe, ils vous demandent le code.",
                    },
                    {
                        "type": "encadre",
                        "ton": "exemple",
                        "texte": "« Bonjour, service informatique. Nous vérifions une alerte "
                        "sur votre compte : pouvez-vous me lire le code que vous venez de "
                        "recevoir ? » Le code vient d'arriver parce que l'attaquant est en "
                        "train de se connecter. Le lui donner, c'est lui ouvrir la porte.",
                    },
                    {"type": "titre", "niveau": 3, "texte": "Deux règles, sans exception"},
                    {
                        "type": "liste",
                        "items": [
                            "Un code de validation ne se communique à personne — pas même à "
                            "un collègue, pas même au service informatique.",
                            "Une demande de validation que vous n'avez pas déclenchée se "
                            "refuse, puis se signale : elle signifie que quelqu'un possède "
                            "déjà votre mot de passe.",
                        ],
                    },
                    {
                        "type": "paragraphe",
                        "texte": "Ne validez jamais une demande pour qu'elle cesse. Des "
                        "notifications répétées à deux heures du matin sont une technique : "
                        "on compte sur la fatigue.",
                    },
                ],
            },
            {
                "title": "Si un mot de passe a fuité",
                "seconds": 60,
                "content": [
                    {
                        "type": "paragraphe",
                        "texte": "Une fuite n'est pas une faute. Ce qui compte, c'est la "
                        "vitesse : entre la fuite et l'usage il y a une fenêtre, et elle se "
                        "referme en agissant.",
                    },
                    {
                        "type": "liste",
                        "ordonnee": True,
                        "items": [
                            "Changez le mot de passe du service concerné.",
                            "Changez-le partout où vous l'aviez réutilisé — c'est le moment "
                            "de faire la liste.",
                            "Vérifiez que l'authentification à deux facteurs est active sur "
                            "ces comptes.",
                            "Signalez-le à votre référent : il vérifiera si le compte a été "
                            "utilisé, et comment.",
                        ],
                    },
                    {
                        "type": "encadre",
                        "ton": "info",
                        "texte": "Signaler tôt coûte dix minutes. Signaler trois semaines "
                        "plus tard coûte une enquête, et parfois une déclaration à "
                        "l'autorité de protection des données.",
                    },
                ],
            },
        ],
        "questions": [
            (
                1,
                1,
                "Votre mot de passe professionnel fait dix-huit caractères et contient des "
                "majuscules, des chiffres et de la ponctuation. Vous l'utilisez aussi sur "
                "trois sites personnels. Est-il sûr ?",
                UNIQUE,
                "La longueur ne protège que contre celui qui essaie de deviner. Dès qu'un des "
                "sites fuite, le mot de passe est connu, et sa complexité n'y change rien. "
                "C'est la réutilisation qui est le défaut, pas la forme.",
                [
                    ("Non : réutilisé, il vaut ce que vaut le site le moins bien protégé.", True),
                    ("Oui : à cette longueur, il est impossible à casser.", False),
                    ("Oui, tant que les sites personnels ne sont pas professionnels.", False),
                    ("Non, mais il suffit d'ajouter un chiffre différent sur chaque site.", False),
                ],
            ),
            (
                2,
                2,
                "Quelles affirmations sont exactes à propos d'un bon mot de passe ?",
                MULTIPLE,
                "La longueur prime sur la complexité, et le changement périodique "
                "obligatoire a été abandonné par les recommandations : il produit des "
                "variations prévisibles. Une citation connue, elle, figure dans les listes "
                "d'essai — sa longueur ne la sauve pas.",
                [
                    (
                        "Quatre ou cinq mots sans rapport valent mieux qu'un mot court ponctué.",
                        True,
                    ),
                    ("On le change quand on a une raison de croire qu'il a fuité.", True),
                    ("Un vers de poème connu est un bon choix, car il est long.", False),
                    ("Il faut le changer tous les trois mois, par principe.", False),
                ],
            ),
            (
                3,
                3,
                "Deux personnes doivent consulter le même compte fournisseur. Quelle est la "
                "bonne réponse ?",
                UNIQUE,
                "Un compte partagé rend impossible de savoir qui a agi, et de retirer l'accès "
                "à une seule personne le jour d'un départ. Deux comptes nominatifs règlent "
                "les deux problèmes. À défaut, le partage par un coffre est un pis-aller "
                "acceptable — le fichier partagé, non.",
                [
                    ("Demander deux comptes nominatifs au fournisseur.", True),
                    ("Partager le mot de passe, en le changeant souvent.", False),
                    (
                        "Créer un compte commun et noter le mot de passe dans un fichier partagé.",
                        False,
                    ),
                    ("Utiliser un compte commun : le fournisseur facture par compte.", False),
                ],
            ),
            (
                4,
                4,
                "Sur quel compte activer en priorité l'authentification à deux facteurs ?",
                UNIQUE,
                "La messagerie est la clé des autres comptes : c'est par elle que passent "
                "toutes les réinitialisations de mot de passe. La protéger d'abord protège "
                "tout le reste, y compris la banque.",
                [
                    ("La messagerie professionnelle.", True),
                    ("Le compte bancaire seulement.", False),
                    ("Le réseau social de l'entreprise.", False),
                    ("Peu importe : l'ordre n'a pas d'effet.", False),
                ],
            ),
            (
                5,
                5,
                "Votre téléphone affiche une demande de validation de connexion que vous "
                "n'avez pas déclenchée. Que faites-vous ?",
                UNIQUE,
                "Cette demande signifie que quelqu'un dispose déjà de votre mot de passe : il "
                "ne lui manque que votre accord. Refuser bloque la connexion ; signaler "
                "permet de changer le mot de passe avant la tentative suivante. Valider pour "
                "que cela cesse est exactement ce que l'attaquant attend.",
                [
                    ("Je refuse, puis je signale et je change mon mot de passe.", True),
                    ("J'ignore la notification : si je ne réponds pas, rien ne se passe.", False),
                    ("Je valide : c'est probablement une application restée ouverte.", False),
                    ("J'attends de voir si la demande revient.", False),
                ],
            ),
            (
                6,
                5,
                "Un appel du « service informatique » vous demande de lire le code à six "
                "chiffres que vous venez de recevoir. Quelle est la bonne conduite ?",
                UNIQUE,
                "Aucun service légitime n'a besoin de ce code : il est destiné à vous seul, et "
                "il vient d'être envoyé parce qu'une connexion est en cours. On ne le "
                "communique à personne, et on rappelle son interlocuteur par un numéro qu'on "
                "connaît déjà plutôt que par celui qu'il donne.",
                [
                    ("Je ne le communique pas, et je signale l'appel.", True),
                    ("Je le communique : l'appel vient du service informatique.", False),
                    (
                        "Je le communique après avoir vérifié que la personne connaît mon nom.",
                        False,
                    ),
                    ("Je le communique partiellement, pour vérifier son identité.", False),
                ],
            ),
        ],
    },
    # ----------------------------------------------------------------- 2 -----
    {
        "slug": "rancongiciel",
        "title": "Rançongiciel : ce qui sauve une entreprise, c'est la sauvegarde",
        "summary": "Comment une entreprise se retrouve à l'arrêt du jour au lendemain, "
        "pourquoi payer ne règle rien, et à quoi ressemble une sauvegarde qui tient "
        "vraiment.",
        "seuil": SEUIL_EXIGEANT,
        "ecrans": [
            {
                "title": "Le matin où plus rien ne s'ouvre",
                "seconds": 90,
                "content": [
                    {
                        "type": "paragraphe",
                        "texte": "Un rançongiciel chiffre les fichiers de l'entreprise et "
                        "réclame de l'argent pour les rendre lisibles. Les devis, la "
                        "comptabilité, les dossiers clients, les sauvegardes s'il les "
                        "atteint : tout devient illisible en quelques heures.",
                    },
                    {
                        "type": "paragraphe",
                        "texte": "L'entrée se fait rarement par un exploit spectaculaire. "
                        "Trois portes reviennent : une pièce jointe ouverte, un accès à "
                        "distance protégé par un mot de passe faible, un logiciel non mis à "
                        "jour exposé sur Internet.",
                    },
                    {
                        "type": "encadre",
                        "ton": "attention",
                        "texte": "Les attaquants attendent souvent plusieurs jours avant de "
                        "chiffrer. Ils cherchent d'abord les sauvegardes, et les détruisent. "
                        "C'est pour cela qu'une sauvegarde accessible depuis le réseau ne "
                        "suffit pas.",
                    },
                    {
                        "type": "paragraphe",
                        "texte": "Ce cours ne parle pas de technique. Il parle de ce qui "
                        "décide, le jour venu, si l'entreprise redémarre en deux jours ou "
                        "ne redémarre pas.",
                    },
                ],
            },
            {
                "title": "Pourquoi payer ne règle rien",
                "seconds": 75,
                "content": [
                    {
                        "type": "paragraphe",
                        "texte": "La rançon est présentée comme une transaction simple. Elle "
                        "ne l'est pas.",
                    },
                    {
                        "type": "liste",
                        "items": [
                            "Payer n'assure pas de récupérer les fichiers : la clé fournie est "
                            "parfois incomplète, parfois jamais fournie.",
                            "Payer ne fait pas disparaître les données volées : elles ont "
                            "souvent été copiées avant le chiffrement, et servent ensuite à "
                            "un second chantage.",
                            "Payer ne referme pas la porte d'entrée : sans la corriger, "
                            "l'attaque peut se reproduire.",
                            "Payer finance directement l'activité qui vise l'entreprise suivante.",
                        ],
                    },
                    {
                        "type": "encadre",
                        "ton": "info",
                        "texte": "La décision de payer ou non n'appartient jamais à la "
                        "personne qui découvre l'incident. Elle revient à la direction, avec "
                        "l'assureur et, selon les pays, après dépôt de plainte. Votre rôle "
                        "est de signaler, pas d'arbitrer.",
                    },
                    {
                        "type": "paragraphe",
                        "texte": "Ce qui remet une entreprise debout, ce n'est pas une "
                        "négociation : c'est une sauvegarde qu'on sait restaurer.",
                    },
                ],
            },
            {
                "title": "Trois copies, deux supports, une hors ligne",
                "seconds": 90,
                "content": [
                    {
                        "type": "paragraphe",
                        "texte": "La règle dite « 3-2-1 » tient en une phrase : trois copies "
                        "des données, sur deux types de supports différents, dont **une hors "
                        "de portée du réseau**.",
                    },
                    {"type": "titre", "niveau": 3, "texte": "Ce que chaque chiffre protège"},
                    {
                        "type": "liste",
                        "items": [
                            "Trois copies : une panne matérielle ne détruit pas tout.",
                            "Deux supports : un défaut de série ou un logiciel de sauvegarde "
                            "défaillant ne détruit pas tout.",
                            "Une hors ligne : un attaquant entré sur le réseau ne détruit pas "
                            "tout. C'est le chiffre qui compte face à un rançongiciel.",
                        ],
                    },
                    {
                        "type": "encadre",
                        "ton": "exemple",
                        "texte": "Un disque externe branché en permanence sur le serveur "
                        "n'est pas une sauvegarde hors ligne : il est chiffré avec le reste. "
                        "Un disque qu'on débranche après la copie, ou un espace distant dont "
                        "les versions ne peuvent pas être supprimées, en est une.",
                    },
                    {
                        "type": "paragraphe",
                        "texte": "Une copie synchronisée dans un espace partagé n'est pas non "
                        "plus une sauvegarde : la synchronisation recopie fidèlement les "
                        "fichiers chiffrés. Ce qui sauve, c'est l'**historique de versions**.",
                    },
                ],
            },
            {
                "title": "Une sauvegarde jamais restaurée n'est pas une sauvegarde",
                "seconds": 75,
                "content": [
                    {
                        "type": "paragraphe",
                        "texte": "C'est la découverte la plus fréquente le jour de "
                        "l'incident : la sauvegarde existait, elle tournait, et elle ne "
                        "contenait pas ce qu'il fallait — ou personne ne savait s'en servir.",
                    },
                    {
                        "type": "liste",
                        "items": [
                            "Restaurer un fichier au hasard, une fois par trimestre, et "
                            "vérifier qu'il s'ouvre.",
                            "Vérifier que le périmètre est complet : les postes, les boîtes "
                            "de messagerie, les applications en ligne, pas seulement le "
                            "serveur de fichiers.",
                            "Noter le temps que prend une restauration : c'est la durée "
                            "pendant laquelle l'entreprise sera arrêtée.",
                            "Garder la procédure sur papier : elle ne sert à rien dans un "
                            "fichier chiffré par l'attaque.",
                        ],
                    },
                    {
                        "type": "citation",
                        "texte": "Personne n'a jamais eu besoin d'une sauvegarde. Tout le "
                        "monde a besoin d'une restauration.",
                        "source": "Adage d'exploitation informatique",
                    },
                ],
            },
            {
                "title": "Les premières heures",
                "seconds": 90,
                "content": [
                    {
                        "type": "paragraphe",
                        "texte": "Si vous découvrez des fichiers illisibles, des extensions "
                        "inhabituelles ou un message de rançon, l'ordre des gestes compte "
                        "plus que la rapidité.",
                    },
                    {"type": "titre", "niveau": 3, "texte": "À faire"},
                    {
                        "type": "liste",
                        "ordonnee": True,
                        "items": [
                            "Débranchez le câble réseau du poste, ou coupez son wifi.",
                            "Prévenez immédiatement votre référent et la direction.",
                            "Photographiez l'écran avec votre téléphone : le message de "
                            "rançon est une pièce utile.",
                            "Notez l'heure et ce que vous faisiez juste avant.",
                        ],
                    },
                    {"type": "titre", "niveau": 3, "texte": "À ne pas faire"},
                    {
                        "type": "liste",
                        "items": [
                            "N'éteignez pas le poste brutalement : de la mémoire utile à "
                            "l'enquête disparaîtrait.",
                            "Ne réinstallez rien, ne supprimez rien, ne « nettoyez » pas.",
                            "Ne branchez pas le disque de sauvegarde pour vérifier : vous le "
                            "perdriez aussi.",
                            "Ne répondez pas aux attaquants, et ne négociez pas de votre "
                            "propre initiative.",
                        ],
                    },
                    {
                        "type": "encadre",
                        "ton": "info",
                        "texte": "Débrancher le réseau sans éteindre : la formule tient les "
                        "deux exigences. On arrête la propagation, on conserve les traces.",
                    },
                ],
            },
        ],
        "questions": [
            (
                1,
                3,
                "Votre serveur est sauvegardé chaque nuit sur un disque externe resté branché "
                "en permanence. Un rançongiciel chiffre le serveur. Que se passe-t-il ?",
                UNIQUE,
                "Un support accessible depuis la machine compromise est chiffré avec elle. "
                "C'est le sens du « 1 » de la règle 3-2-1 : une copie hors de portée du "
                "réseau. Un disque qu'on débranche après la copie aurait survécu.",
                [
                    ("Le disque est chiffré lui aussi : la sauvegarde est perdue.", True),
                    ("Le disque est protégé : il est externe.", False),
                    ("Seuls les fichiers modifiés cette nuit-là sont perdus.", False),
                    ("Le logiciel de sauvegarde détecte le chiffrement et l'interrompt.", False),
                ],
            ),
            (
                2,
                2,
                "Quels effets peut-on attendre du paiement d'une rançon ?",
                MULTIPLE,
                "Le paiement n'achète, au mieux, qu'une clé de déchiffrement — et parfois "
                "rien. Les données déjà copiées restent entre les mains des attaquants, et la "
                "porte d'entrée reste ouverte si personne ne la corrige.",
                [
                    ("Il peut ne rien rendre du tout.", True),
                    ("Il ne supprime pas les données déjà volées.", True),
                    ("Il referme la vulnérabilité utilisée pour entrer.", False),
                    ("Il garantit l'absence d'une seconde attaque.", False),
                ],
            ),
            (
                3,
                4,
                "À quelle condition peut-on dire qu'une sauvegarde fonctionne ?",
                UNIQUE,
                "Un travail de sauvegarde qui se termine sans erreur ne prouve pas que le "
                "contenu est exploitable ni que le périmètre est complet. Seule une "
                "restauration réelle, essayée régulièrement, le prouve.",
                [
                    (
                        "Quand on a restauré un fichier et vérifié qu'il s'ouvre, récemment.",
                        True,
                    ),
                    ("Quand le journal de sauvegarde ne signale aucune erreur.", False),
                    ("Quand elle tourne chaque nuit depuis plusieurs mois.", False),
                    ("Quand le disque de destination a assez d'espace libre.", False),
                ],
            ),
            (
                4,
                5,
                "Vous découvrez un message de rançon sur votre écran. Quel est le premier geste ?",
                UNIQUE,
                "Débrancher le réseau arrête la propagation vers les autres postes, tout en "
                "laissant la machine allumée : une extinction brutale ferait disparaître des "
                "éléments utiles à l'enquête, et une réinstallation les effacerait "
                "définitivement.",
                [
                    ("Débrancher le réseau, sans éteindre le poste.", True),
                    ("Éteindre le poste en maintenant le bouton d'alimentation.", False),
                    ("Lancer une analyse antivirale complète.", False),
                    ("Brancher le disque de sauvegarde pour vérifier son état.", False),
                ],
            ),
            (
                5,
                5,
                "Qui décide de payer ou non une rançon ?",
                UNIQUE,
                "C'est une décision de direction, prise avec l'assureur et, selon les pays, "
                "après dépôt de plainte. La personne qui découvre l'incident a un rôle "
                "différent et tout aussi décisif : signaler vite, et ne rien détruire.",
                [
                    ("La direction, avec l'assureur et les autorités.", True),
                    ("La personne qui a découvert l'incident.", False),
                    ("Le prestataire informatique, qui connaît le dossier.", False),
                    ("Personne : la loi l'interdit dans tous les cas.", False),
                ],
            ),
            (
                6,
                3,
                "Vos fichiers sont synchronisés en continu vers un espace partagé en ligne. "
                "Est-ce une sauvegarde ?",
                UNIQUE,
                "La synchronisation recopie fidèlement ce qui change, y compris le "
                "chiffrement. Ce qui sauve, c'est l'historique de versions : la possibilité "
                "de revenir à l'état d'avant. Beaucoup d'offres le proposent, encore faut-il "
                "l'avoir activé et vérifié.",
                [
                    (
                        "Seulement si l'espace conserve un historique de versions restaurable.",
                        True,
                    ),
                    ("Oui : les fichiers existent en deux endroits.", False),
                    ("Oui, puisque le prestataire sauvegarde ses propres serveurs.", False),
                    ("Non, une sauvegarde ne peut être que locale.", False),
                ],
            ),
        ],
    },
    # ----------------------------------------------------------------- 3 -----
    {
        "slug": "fraude-au-virement",
        "title": "Fraude au virement : quand c'est le patron qui écrit",
        "summary": "L'attaque qui ne casse rien et coûte le plus cher : une demande "
        "urgente, un changement de coordonnées bancaires, et un virement qui part. "
        "Comment la reconnaître et quelle procédure l'arrête.",
        "seuil": SEUIL_EXIGEANT,
        "ecrans": [
            {
                "title": "Une attaque qui ne casse rien",
                "seconds": 75,
                "content": [
                    {
                        "type": "paragraphe",
                        "texte": "Il n'y a ici ni virus, ni faille, ni intrusion. Un message "
                        "arrive, il est crédible, et quelqu'un fait un virement. C'est la "
                        "fraude la plus coûteuse par incident pour les entreprises de toute "
                        "taille.",
                    },
                    {
                        "type": "paragraphe",
                        "texte": "Les attaquants se renseignent avant d'écrire : site de "
                        "l'entreprise, réseaux professionnels, annonces de recrutement, "
                        "communiqués. Ils connaissent les noms, les fonctions, parfois les "
                        "dossiers en cours et les dates d'absence.",
                    },
                    {
                        "type": "encadre",
                        "ton": "exemple",
                        "texte": "« Je suis en déplacement, je ne peux pas être joint. Nous "
                        "finalisons une opération confidentielle. Peux-tu passer ce virement "
                        "aujourd'hui, et n'en parler à personne ? Je compte sur ta "
                        "discrétion. » Rien dans ce message n'est technique.",
                    },
                ],
            },
            {
                "title": "Autorité, urgence, secret",
                "seconds": 90,
                "content": [
                    {
                        "type": "paragraphe",
                        "texte": "Presque toutes ces tentatives combinent les mêmes trois "
                        "leviers. Les reconnaître ensemble est plus fiable que de chercher "
                        "une faute d'orthographe.",
                    },
                    {"type": "titre", "niveau": 3, "texte": "L'autorité"},
                    {
                        "type": "paragraphe",
                        "texte": "Le message se présente comme venant de la direction, d'un "
                        "avocat, d'un commissaire aux comptes, d'un cadre d'une maison mère. "
                        "Contredire une autorité coûte, et l'attaque repose sur ce coût.",
                    },
                    {"type": "titre", "niveau": 3, "texte": "L'urgence"},
                    {
                        "type": "paragraphe",
                        "texte": "Aujourd'hui, avant la fermeture, avant la fin du trimestre. "
                        "L'urgence sert à empêcher la vérification, jamais à autre chose.",
                    },
                    {"type": "titre", "niveau": 3, "texte": "Le secret"},
                    {
                        "type": "paragraphe",
                        "texte": "« Opération confidentielle », « n'en parlez à personne », "
                        "« je vous ai choisi pour votre discrétion ». Le secret isole la "
                        "personne du seul geste qui l'aurait protégée : demander à un "
                        "collègue.",
                    },
                    {
                        "type": "encadre",
                        "ton": "attention",
                        "texte": "Une demande légitime supporte toujours une vérification. "
                        "Une demande qui interdit la vérification s'est désignée elle-même.",
                    },
                ],
            },
            {
                "title": "Le changement de coordonnées bancaires",
                "seconds": 90,
                "content": [
                    {
                        "type": "paragraphe",
                        "texte": "C'est la variante la plus discrète, et la plus fréquente. "
                        "Un fournisseur connu écrit que ses coordonnées bancaires ont changé, "
                        "et joint une facture à l'identique de celles qu'il envoie "
                        "d'habitude.",
                    },
                    {
                        "type": "paragraphe",
                        "texte": "Souvent, la boîte de messagerie du fournisseur est réellement "
                        "compromise : l'échange reprend une conversation existante, avec "
                        "l'historique. Parfois, seule l'adresse a été imitée, à une lettre "
                        "près.",
                    },
                    {
                        "type": "liste",
                        "items": [
                            "Un changement de coordonnées bancaires se vérifie par téléphone, "
                            "sur le numéro que vous avez au contrat — jamais sur celui du "
                            "message.",
                            "Regardez l'adresse complète de l'expéditeur, pas le nom affiché.",
                            "Méfiez-vous d'un changement de pays ou d'établissement sans "
                            "raison expliquée.",
                            "Un fournisseur légitime ne trouvera jamais anormal qu'on vérifie.",
                        ],
                    },
                    {
                        "type": "encadre",
                        "ton": "info",
                        "texte": "Le premier virement après un changement de coordonnées "
                        "mérite un appel, même si le montant est faible. Les fraudeurs "
                        "commencent souvent petit pour valider le canal.",
                    },
                ],
            },
            {
                "title": "La procédure qui arrête tout",
                "seconds": 75,
                "content": [
                    {
                        "type": "paragraphe",
                        "texte": "Contre cette fraude, la protection n'est pas la vigilance : "
                        "c'est une **règle écrite**, connue de tous, qui ne dépend pas de "
                        "l'humeur ni de la charge de travail du jour.",
                    },
                    {"type": "titre", "niveau": 3, "texte": "Le double canal"},
                    {
                        "type": "paragraphe",
                        "texte": "Toute demande de paiement inhabituelle, et tout changement "
                        "de coordonnées bancaires, est confirmé par un **second canal** et "
                        "par un **contact déjà connu**. Un message vérifié par un appel, sur "
                        "un numéro déjà enregistré.",
                    },
                    {
                        "type": "liste",
                        "items": [
                            "Au-delà d'un montant fixé, deux personnes valident.",
                            "La règle s'applique à tous, direction comprise — surtout à la "
                            "direction, puisque c'est son nom qui est usurpé.",
                            "Personne ne peut être sanctionné pour avoir appliqué la "
                            "procédure. C'est la direction qui doit le dire, une fois, "
                            "clairement.",
                        ],
                    },
                    {
                        "type": "encadre",
                        "ton": "attention",
                        "texte": "Une voix au téléphone n'est plus une preuve d'identité : "
                        "quelques secondes d'enregistrement public suffisent à imiter une "
                        "voix. Ce qui fait la vérification, c'est de **rappeler un numéro "
                        "connu**, pas de reconnaître une voix.",
                    },
                ],
            },
            {
                "title": "Si le virement est parti",
                "seconds": 60,
                "content": [
                    {
                        "type": "paragraphe",
                        "texte": "Les premières heures décident du reste. Un virement peut "
                        "parfois être rappelé s'il n'a pas encore été retiré.",
                    },
                    {
                        "type": "liste",
                        "ordonnee": True,
                        "items": [
                            "Appelez la banque immédiatement et demandez le rappel du "
                            "virement, même la nuit ou le week-end.",
                            "Prévenez la direction : c'est elle qui portera plainte.",
                            "Conservez tout — messages, pièces jointes, en-têtes complets, "
                            "relevés — sans rien supprimer.",
                            "Vérifiez si d'autres demandes du même type ont circulé dans "
                            "l'entreprise.",
                        ],
                    },
                    {
                        "type": "encadre",
                        "ton": "info",
                        "texte": "La personne qui a fait le virement est une victime, pas une "
                        "coupable : l'attaque était conçue pour réussir. Une entreprise qui "
                        "cherche un fautif apprend seulement à ses équipes à se taire plus "
                        "longtemps la fois suivante.",
                    },
                ],
            },
        ],
        "questions": [
            (
                1,
                2,
                "Quels signaux, pris ensemble, doivent faire suspendre une demande de paiement ?",
                MULTIPLE,
                "L'urgence et le secret n'ont aucune raison d'être dans une demande "
                "légitime : ils servent à empêcher la vérification et à isoler la personne. "
                "Un montant élevé ou un virement à l'étranger, en revanche, sont des "
                "opérations ordinaires dans beaucoup d'entreprises.",
                [
                    ("Le message impose un délai très court.", True),
                    ("Le message demande de n'en parler à personne.", True),
                    ("Le montant est élevé.", False),
                    ("Le bénéficiaire est à l'étranger.", False),
                ],
            ),
            (
                2,
                3,
                "Un fournisseur habituel annonce par courriel un changement de coordonnées "
                "bancaires, dans un échange qui reprend votre conversation précédente. Que "
                "faites-vous ?",
                UNIQUE,
                "Reprendre la conversation existante est justement le signe que la boîte du "
                "fournisseur est peut-être compromise : l'historique ne prouve rien. Seul un "
                "appel sur le numéro du contrat, jamais celui du message, tranche.",
                [
                    ("J'appelle le fournisseur sur le numéro figurant au contrat.", True),
                    (
                        "Je réponds au courriel pour demander confirmation.",
                        False,
                    ),
                    ("J'appelle le numéro indiqué dans le message.", False),
                    ("J'accepte : l'historique de la conversation prouve l'authenticité.", False),
                ],
            ),
            (
                3,
                4,
                "Votre dirigeant vous appelle : c'est bien sa voix, il demande un virement "
                "urgent et confidentiel. Que faites-vous ?",
                UNIQUE,
                "Une voix n'est plus une preuve : quelques secondes d'enregistrement public "
                "suffisent à l'imiter. La procédure ne fait aucune exception pour la "
                "direction, précisément parce que c'est son nom qui est usurpé — et rappeler "
                "un numéro connu est le geste qui tranche.",
                [
                    ("J'applique la procédure et je rappelle sur un numéro connu.", True),
                    ("J'exécute : la voix est reconnaissable.", False),
                    ("J'exécute, et je préviens la comptabilité ensuite.", False),
                    ("Je demande un courriel de confirmation avant d'exécuter.", False),
                ],
            ),
            (
                4,
                4,
                "À qui s'applique la règle de validation par un second canal ?",
                UNIQUE,
                "Une procédure qui exempte la direction ne protège de rien, puisque c'est son "
                "identité que la fraude emprunte. Et la direction doit dire une fois, "
                "clairement, que personne ne sera sanctionné pour l'avoir appliquée.",
                [
                    ("À tout le monde, direction comprise.", True),
                    ("Aux comptables seulement.", False),
                    ("À tous sauf à la direction, qui engage l'entreprise.", False),
                    ("Aux virements dépassant un montant élevé, uniquement.", False),
                ],
            ),
            (
                5,
                5,
                "Le virement frauduleux est parti il y a une heure. Quelle est la première "
                "chose à faire ?",
                UNIQUE,
                "Un virement peut parfois être rappelé s'il n'a pas encore été retiré : la "
                "banque est donc le premier appel, avant même de reconstituer ce qui s'est "
                "passé. Les preuves, elles, se conservent — on ne supprime rien.",
                [
                    ("Appeler la banque pour demander le rappel du virement.", True),
                    ("Rassembler les preuves avant d'alerter qui que ce soit.", False),
                    ("Supprimer le message pour éviter qu'il soit suivi par un autre.", False),
                    ("Attendre le lendemain : la banque ne traitera rien hors ouverture.", False),
                ],
            ),
            (
                6,
                1,
                "Comment les attaquants savent-ils qui écrire, et à quel sujet ?",
                UNIQUE,
                "Tout se trouve publiquement : le site de l'entreprise, les réseaux "
                "professionnels, les annonces de recrutement, les communiqués. Aucune "
                "intrusion n'est nécessaire — ce qui explique qu'aucun antivirus ne détecte "
                "cette fraude.",
                [
                    (
                        "En rassemblant des informations publiques sur l'entreprise et ses "
                        "équipes.",
                        True,
                    ),
                    ("En ayant préalablement pénétré le réseau de l'entreprise.", False),
                    ("Au hasard : les messages sont envoyés en masse, sans ciblage.", False),
                    ("En achetant la liste des salariés à un ancien employé.", False),
                ],
            ),
        ],
    },
    # ----------------------------------------------------------------- 4 -----
    {
        "slug": "travail-a-distance",
        "title": "Travailler ailleurs qu'au bureau",
        "summary": "Le train, l'hôtel, la maison, le café : ce qui change quand le poste "
        "de travail sort des murs, et les quelques gestes qui suffisent à le tenir.",
        "ecrans": [
            {
                "title": "Le bureau n'est plus un périmètre",
                "seconds": 75,
                "content": [
                    {
                        "type": "paragraphe",
                        "texte": "Longtemps, la sécurité informatique ressemblait à un "
                        "bâtiment : dedans on était protégé, dehors on ne l'était pas. Ce "
                        "modèle ne décrit plus rien. Les données sont sur des services en "
                        "ligne, et l'ordinateur passe du bureau au salon.",
                    },
                    {
                        "type": "paragraphe",
                        "texte": "La protection ne tient donc plus au lieu, mais à trois "
                        "choses qui voyagent avec vous : le **compte** et sa deuxième clé, "
                        "l'**appareil** et ses mises à jour, et l'**attention** à ce qui "
                        "vous entoure.",
                    },
                    {
                        "type": "encadre",
                        "ton": "info",
                        "texte": "Rien dans ce cours ne dépend d'un budget. Tout tient à des "
                        "habitudes, et chacune se prend en une semaine.",
                    },
                ],
            },
            {
                "title": "Les réseaux qu'on ne contrôle pas",
                "seconds": 90,
                "content": [
                    {
                        "type": "paragraphe",
                        "texte": "Un wifi d'hôtel, de gare ou de café est un réseau partagé "
                        "avec des inconnus. Le vrai risque n'est plus tellement l'écoute des "
                        "échanges — la plupart des sites sont chiffrés — mais la **fausse "
                        "borne** et la **fausse page** qu'elle affiche.",
                    },
                    {
                        "type": "liste",
                        "items": [
                            "Préférez le partage de connexion de votre téléphone : c'est "
                            "gratuit, plus rapide à établir, et personne ne le partage avec "
                            "vous.",
                            "Sur un réseau ouvert, n'installez rien et n'acceptez aucun "
                            "certificat que le navigateur signale.",
                            "Si l'entreprise fournit un tunnel chiffré, utilisez-le partout, "
                            "y compris à la maison.",
                            "Un avertissement de sécurité du navigateur ne se contourne "
                            "jamais : on ferme, on change de réseau.",
                        ],
                    },
                    {
                        "type": "encadre",
                        "ton": "attention",
                        "texte": "Ne branchez pas votre téléphone sur une borne de recharge "
                        "publique par son câble de données. Utilisez votre propre chargeur "
                        "sur une prise électrique, ou un câble qui ne transporte que le "
                        "courant.",
                    },
                ],
            },
            {
                "title": "L'écran, et les oreilles autour",
                "seconds": 75,
                "content": [
                    {
                        "type": "paragraphe",
                        "texte": "Dans un train, le voisin lit votre écran sans effort et "
                        "entend votre réunion en entier. Aucune technique ne protège de cela.",
                    },
                    {
                        "type": "liste",
                        "items": [
                            "Verrouillez l'écran dès que vous quittez la table, même pour "
                            "trente secondes. Un raccourci clavier suffit.",
                            "Évitez d'ouvrir des dossiers nominatifs ou des données de santé "
                            "dans un espace public.",
                            "Au téléphone, ne citez ni noms de clients, ni montants, ni "
                            "identifiants.",
                            "En visioconférence, vérifiez ce que montre votre caméra, et ce "
                            "que montre votre partage d'écran avant de le lancer.",
                        ],
                    },
                    {
                        "type": "encadre",
                        "ton": "exemple",
                        "texte": "Le partage d'écran est la fuite la plus banale : on partage "
                        "l'écran entier, une notification de messagerie arrive, et un extrait "
                        "de conversation privée s'affiche devant un client. Partagez une "
                        "fenêtre, pas l'écran.",
                    },
                ],
            },
            {
                "title": "Le matériel personnel",
                "seconds": 75,
                "content": [
                    {
                        "type": "paragraphe",
                        "texte": "Utiliser son ordinateur personnel pour travailler n'est pas "
                        "interdit par nature ; c'est à l'entreprise de dire ce qu'elle "
                        "autorise. Mais deux règles ne se négocient pas.",
                    },
                    {
                        "type": "liste",
                        "ordonnee": True,
                        "items": [
                            "Un appareil qui touche des données professionnelles est à jour, "
                            "et sa session est protégée par un mot de passe.",
                            "Les données professionnelles ne se recopient pas dans un espace "
                            "personnel — messagerie privée, stockage en ligne personnel, clé "
                            "USB familiale.",
                        ],
                    },
                    {
                        "type": "paragraphe",
                        "texte": "Ce second point est le plus souvent enfreint, et de bonne "
                        "foi : on s'envoie un fichier chez soi pour finir un travail le soir. "
                        "Le fichier échappe alors à toute sauvegarde et à toute suppression, "
                        "et il reste là des années.",
                    },
                    {
                        "type": "encadre",
                        "ton": "attention",
                        "texte": "Les assistants et services en ligne gratuits comptent comme "
                        "des espaces personnels. Coller un contrat ou un dossier client dans "
                        "un outil non validé par l'entreprise, c'est le transmettre à un "
                        "tiers.",
                    },
                ],
            },
            {
                "title": "Perdu, volé",
                "seconds": 60,
                "content": [
                    {
                        "type": "paragraphe",
                        "texte": "Un ordinateur oublié dans un train n'est un incident grave "
                        "que si son disque n'est pas chiffré. Chiffré, c'est une perte "
                        "matérielle ; non chiffré, c'est une fuite de tout ce qu'il contient.",
                    },
                    {
                        "type": "liste",
                        "ordonnee": True,
                        "items": [
                            "Signalez la perte le jour même, même un dimanche : ce qui compte "
                            "est de pouvoir couper les accès.",
                            "Changez le mot de passe des comptes ouverts sur l'appareil.",
                            "Demandez l'effacement à distance s'il est possible.",
                            "Déclarez le vol : c'est utile à l'assurance, et parfois exigé.",
                        ],
                    },
                    {
                        "type": "encadre",
                        "ton": "info",
                        "texte": "Vérifiez aujourd'hui, pas le jour de la perte, que le "
                        "chiffrement du disque est actif sur votre ordinateur. C'est une case "
                        "à cocher, et elle divise le coût d'un vol par dix.",
                    },
                ],
            },
        ],
        "questions": [
            (
                1,
                2,
                "Vous devez travailler une heure depuis un café. Quelle est la meilleure option ?",
                UNIQUE,
                "Le partage de connexion du téléphone n'est partagé avec personne, et il "
                "évite la question de la fausse borne. Un wifi ouvert reste utilisable avec un "
                "tunnel d'entreprise, mais il n'apporte rien de mieux — et la présence d'un "
                "mot de passe affiché au comptoir ne prouve rien du tout.",
                [
                    ("Le partage de connexion de mon téléphone.", True),
                    ("Le wifi du café, puisqu'il demande un mot de passe.", False),
                    ("Le wifi ouvert qui porte le nom du café.", False),
                    ("N'importe lequel : les sites sont chiffrés de toute façon.", False),
                ],
            ),
            (
                2,
                2,
                "Le navigateur affiche un avertissement de certificat sur le réseau de "
                "l'hôtel. Que faites-vous ?",
                UNIQUE,
                "Cet avertissement signifie que quelque chose s'interpose entre vous et le "
                "site. Le contourner, c'est accepter cette interposition — et c'est "
                "exactement ce qu'une fausse borne attend.",
                [
                    ("Je ferme, et je passe par un autre réseau.", True),
                    ("Je continue : les hôtels affichent souvent ce message.", False),
                    ("J'accepte le certificat pour cette session seulement.", False),
                    ("Je change de navigateur.", False),
                ],
            ),
            (
                3,
                3,
                "Quelles précautions relèvent du travail dans un lieu public ?",
                MULTIPLE,
                "Le verrouillage et le partage d'une seule fenêtre traitent les deux fuites "
                "réelles : le regard du voisin, et la notification qui s'affiche devant un "
                "client. Un filtre de confidentialité aide, mais ne remplace ni l'un ni "
                "l'autre — et baisser la luminosité ne protège de rien.",
                [
                    ("Verrouiller l'écran en quittant la table, même brièvement.", True),
                    ("Partager une fenêtre plutôt que l'écran entier en visioconférence.", True),
                    ("Baisser la luminosité de l'écran.", False),
                    ("Parler moins fort en citant les noms de clients.", False),
                ],
            ),
            (
                4,
                4,
                "Vous devez finir un dossier le soir chez vous. Quelle solution est acceptable ?",
                UNIQUE,
                "Envoyer un fichier professionnel vers une messagerie ou un stockage "
                "personnels le fait sortir de toute sauvegarde et de toute suppression : il y "
                "reste des années. Passer par les outils de l'entreprise garde le fichier là "
                "où il est protégé et traçable.",
                [
                    (
                        "Accéder au dossier par les outils de l'entreprise depuis un appareil "
                        "à jour.",
                        True,
                    ),
                    ("Me l'envoyer sur ma messagerie personnelle.", False),
                    ("Le déposer sur mon espace de stockage en ligne personnel.", False),
                    ("Le copier sur une clé USB de la maison.", False),
                ],
            ),
            (
                5,
                5,
                "Votre ordinateur professionnel est volé. Qu'est-ce qui détermine la gravité "
                "de l'incident ?",
                UNIQUE,
                "Le chiffrement du disque transforme une fuite de données en simple perte de "
                "matériel. Ni le mot de passe de session seul, ni l'assurance, ni "
                "l'ancienneté de l'appareil ne changent ce qui sortira des fichiers.",
                [
                    ("Le fait que le disque soit chiffré ou non.", True),
                    ("La valeur d'achat de l'appareil.", False),
                    ("Le fait que la session soit protégée par un mot de passe.", False),
                    ("Le fait que l'entreprise soit assurée.", False),
                ],
            ),
            (
                6,
                5,
                "Vous constatez la perte un samedi soir. Quand signalez-vous ?",
                UNIQUE,
                "Le signalement sert à couper les accès, et un accès se coupe à toute heure. "
                "Attendre le lundi laisse deux jours entiers à quiconque récupère l'appareil.",
                [
                    ("Tout de suite, sans attendre le lundi.", True),
                    ("Lundi matin, à l'ouverture.", False),
                    ("Après avoir cherché l'appareil pendant vingt-quatre heures.", False),
                    ("Seulement si des données sensibles s'y trouvaient.", False),
                ],
            ),
        ],
    },
    # ----------------------------------------------------------------- 5 -----
    {
        "slug": "donnees-personnelles",
        "title": "Données personnelles : les réflexes du quotidien",
        "summary": "Ce qui compte comme donnée personnelle, pourquoi en collecter moins "
        "protège l'entreprise, que faire quand quelqu'un demande ses données, et ce "
        "qu'est une violation.",
        "ecrans": [
            {
                "title": "Ce qu'est une donnée personnelle",
                "seconds": 75,
                "content": [
                    {
                        "type": "paragraphe",
                        "texte": "Une donnée personnelle, c'est toute information qui permet "
                        "de reconnaître quelqu'un, directement ou en la rapprochant d'une "
                        "autre. Pas seulement un nom : une adresse de messagerie "
                        "professionnelle, un numéro de client, une plaque, une photo, une "
                        "adresse de connexion.",
                    },
                    {
                        "type": "paragraphe",
                        "texte": "Certaines sont **sensibles** et demandent bien plus de "
                        "précautions : la santé, les convictions, l'appartenance syndicale, "
                        "l'orientation sexuelle, les données biométriques, les infractions.",
                    },
                    {
                        "type": "encadre",
                        "ton": "exemple",
                        "texte": "Un arrêt de travail transmis par un salarié à son "
                        "responsable est une donnée de santé. Il ne se transfère pas dans une "
                        "conversation de groupe, ne reste pas dans un dossier partagé, et ne "
                        "se conserve pas « au cas où ».",
                    },
                ],
            },
            {
                "title": "N'en collecter que ce qui sert",
                "seconds": 90,
                "content": [
                    {
                        "type": "paragraphe",
                        "texte": "C'est le principe le plus utile du lot, et le plus souvent "
                        "oublié : on ne collecte que ce dont on a besoin, on ne le garde que "
                        "le temps nécessaire, et on ne le montre qu'à ceux qui en ont besoin.",
                    },
                    {
                        "type": "paragraphe",
                        "texte": "Ce n'est pas seulement une obligation. Une donnée qu'on n'a "
                        "pas collectée ne peut pas fuir, et un fichier qu'on a supprimé à "
                        "l'heure ne figurera dans aucune fuite.",
                    },
                    {
                        "type": "titre",
                        "niveau": 3,
                        "texte": "Trois questions avant de créer un fichier",
                    },
                    {
                        "type": "liste",
                        "ordonnee": True,
                        "items": [
                            "À quoi sert chaque colonne ? Celle dont personne ne sait dire "
                            "l'usage n'a pas à exister.",
                            "Combien de temps la garde-t-on, et qui supprimera ?",
                            "Qui doit y accéder ? « Tout le monde dans l'entreprise » est "
                            "presque toujours une réponse par défaut, pas une décision.",
                        ],
                    },
                    {
                        "type": "encadre",
                        "ton": "attention",
                        "texte": "Les copies non déclarées sont le vrai problème : l'extrait "
                        "exporté en tableur pour préparer une réunion, envoyé par courriel, "
                        "et jamais supprimé. Une donnée protégée dans l'application ne l'est "
                        "plus dans cet extrait.",
                    },
                ],
            },
            {
                "title": "Où elles vivent, et avec qui",
                "seconds": 75,
                "content": [
                    {
                        "type": "paragraphe",
                        "texte": "Les données de l'entreprise sont rarement chez elle seule : "
                        "un logiciel de paie, un outil de facturation, une messagerie, un "
                        "prestataire informatique. Chacun est un **sous-traitant** au sens du "
                        "règlement, et cela engage l'entreprise.",
                    },
                    {
                        "type": "liste",
                        "items": [
                            "Tenez la liste des outils qui contiennent des données "
                            "personnelles : c'est la moitié du travail de conformité.",
                            "N'ajoutez pas un nouvel outil dans votre coin. Un outil gratuit "
                            "engage l'entreprise autant qu'un outil payant.",
                            "Sachez où sont hébergées les données, et si elles sortent de "
                            "l'Union européenne.",
                            "Avant de partager un document, vérifiez qui recevra le lien, et "
                            "s'il expire.",
                        ],
                    },
                    {
                        "type": "encadre",
                        "ton": "info",
                        "texte": "« Ce n'est qu'un essai » n'existe pas : un essai avec de "
                        "vraies données est un traitement réel. Pour essayer un outil, "
                        "utilisez des données inventées.",
                    },
                ],
            },
            {
                "title": "Quand quelqu'un demande ses données",
                "seconds": 75,
                "content": [
                    {
                        "type": "paragraphe",
                        "texte": "Un client, un salarié, un candidat peut demander à savoir "
                        "quelles données vous détenez sur lui, à les faire corriger, "
                        "supprimer, ou à en recevoir une copie. La demande peut arriver par "
                        "n'importe quel canal, y compris oralement.",
                    },
                    {
                        "type": "liste",
                        "ordonnee": True,
                        "items": [
                            "Ne répondez pas seul : transmettez à la personne désignée dans "
                            "l'entreprise, le jour même.",
                            "Notez la date de réception : le délai de réponse est d'un mois, "
                            "et il court depuis ce jour.",
                            "N'effacez rien de votre propre initiative avant que la demande "
                            "soit traitée.",
                            "Vérifiez l'identité du demandeur, sans exiger plus de pièces que "
                            "nécessaire.",
                        ],
                    },
                    {
                        "type": "encadre",
                        "ton": "attention",
                        "texte": "Une demande ignorée se termine souvent par une plainte, et "
                        "les sanctions les plus fréquentes portent précisément là : non sur "
                        "un défaut technique, mais sur des droits non respectés.",
                    },
                ],
            },
            {
                "title": "Une violation de données, et le délai de 72 heures",
                "seconds": 75,
                "content": [
                    {
                        "type": "paragraphe",
                        "texte": "Une violation, ce n'est pas seulement un piratage. C'est "
                        "toute perte de confidentialité, d'intégrité ou de disponibilité : un "
                        "courriel envoyé au mauvais destinataire, un dossier papier oublié "
                        "dans un train, une clé USB perdue, un fichier supprimé sans "
                        "sauvegarde.",
                    },
                    {
                        "type": "paragraphe",
                        "texte": "Quand elle présente un risque pour les personnes, elle doit "
                        "être notifiée à l'autorité de protection des données dans les **72 "
                        "heures**. Et dans tous les cas, elle doit être inscrite au registre "
                        "interne des violations — même celles qu'on ne notifie pas.",
                    },
                    {
                        "type": "encadre",
                        "ton": "exemple",
                        "texte": "Un fichier de trente bulletins de paie envoyé à un mauvais "
                        "destinataire est une violation, sans aucun attaquant. Elle se signale "
                        "comme les autres, et le délai commence à l'instant où l'entreprise "
                        "en prend connaissance.",
                    },
                    {
                        "type": "paragraphe",
                        "texte": "Votre rôle tient en une phrase : **signaler tout de suite, "
                        "sans juger de la gravité**. L'évaluation est un travail spécialisé ; "
                        "le délai, lui, court dès le premier instant.",
                    },
                ],
            },
        ],
        "questions": [
            (
                1,
                1,
                "Parmi ces informations, lesquelles sont des données personnelles ?",
                MULTIPLE,
                "Une adresse professionnelle nominative et un numéro de client désignent tous "
                "deux une personne, directement ou par rapprochement. Le chiffre d'affaires "
                "de l'entreprise et le nombre de visiteurs d'un site, en revanche, ne "
                "désignent personne.",
                [
                    ("L'adresse de messagerie prenom.nom@entreprise.fr.", True),
                    ("Un numéro de client, sans nom à côté.", True),
                    ("Le chiffre d'affaires annuel de l'entreprise.", False),
                    ("Le nombre total de visiteurs du site le mois dernier.", False),
                ],
            ),
            (
                2,
                2,
                "On vous demande de préparer un extrait de la base clients pour une réunion. "
                "Quel est le bon réflexe ?",
                UNIQUE,
                "Une copie exportée échappe aux protections de l'application : elle n'est plus "
                "ni tracée, ni supprimée. N'exporter que les colonnes utiles, et supprimer "
                "l'extrait après la réunion, est ce qui limite l'exposition.",
                [
                    (
                        "N'exporter que les colonnes utiles, et supprimer l'extrait après la "
                        "réunion.",
                        True,
                    ),
                    ("Exporter toute la base : on ne sait jamais ce qui servira.", False),
                    ("Exporter tout, et le conserver pour les réunions suivantes.", False),
                    ("Exporter tout, mais protéger le fichier par un mot de passe.", False),
                ],
            ),
            (
                3,
                3,
                "Vous voulez tester un nouvel outil en ligne gratuit avec le fichier clients. "
                "Est-ce acceptable ?",
                UNIQUE,
                "Un essai avec de vraies données est un traitement réel, et l'outil devient un "
                "sous-traitant de l'entreprise. Ni la gratuité, ni la brièveté de l'essai, ni "
                "l'absence de contrat n'y changent quelque chose. Des données inventées "
                "permettent de tester sans engager l'entreprise.",
                [
                    ("Non : il faut tester avec des données inventées.", True),
                    ("Oui, le temps de l'essai seulement.", False),
                    ("Oui, si l'outil est gratuit et sans contrat.", False),
                    ("Oui, si je supprime les données après l'essai.", False),
                ],
            ),
            (
                4,
                4,
                "Un ancien salarié demande par téléphone une copie de toutes les données que "
                "vous détenez sur lui. Que faites-vous ?",
                UNIQUE,
                "La demande est valable quel que soit le canal, y compris oral, et le délai "
                "d'un mois court dès sa réception. Elle se transmet le jour même à la personne "
                "désignée ; exiger un courrier recommandé ou renvoyer vers un formulaire "
                "retarde sans fondement.",
                [
                    ("Je note la date et je transmets le jour même à la personne désignée.", True),
                    ("Je demande un courrier recommandé avant toute suite.", False),
                    ("Je réponds moi-même avec ce que je trouve dans mes dossiers.", False),
                    ("J'explique que la demande doit passer par un formulaire écrit.", False),
                ],
            ),
            (
                5,
                5,
                "Vous envoyez par erreur un fichier de bulletins de paie à un mauvais "
                "destinataire. Que faites-vous ?",
                UNIQUE,
                "C'est une violation de données, sans aucun attaquant, et le délai de 72 heures "
                "court à partir du moment où l'entreprise en prend connaissance. Le "
                "signalement est immédiat : l'appréciation du risque est un travail "
                "spécialisé, pas le vôtre.",
                [
                    ("Je signale immédiatement : c'est une violation de données.", True),
                    (
                        "Je demande au destinataire de supprimer le message et je n'en parle pas.",
                        False,
                    ),
                    ("Rien : il n'y a pas eu de piratage.", False),
                    ("J'attends de voir si le destinataire réagit.", False),
                ],
            ),
            (
                6,
                5,
                "Quelles situations constituent une violation de données personnelles ?",
                MULTIPLE,
                "La définition couvre la confidentialité, l'intégrité et la disponibilité : un "
                "envoi au mauvais destinataire comme une perte définitive de fichiers. Un mot "
                "de passe changé ou une demande d'accès reçue ne sont, en eux-mêmes, rien de "
                "tout cela.",
                [
                    ("Un courriel contenant des données envoyé au mauvais destinataire.", True),
                    ("Des fichiers clients perdus définitivement, faute de sauvegarde.", True),
                    ("Un salarié qui change son mot de passe.", False),
                    ("Une demande d'accès à ses données par un client.", False),
                ],
            ),
        ],
    },
    # ----------------------------------------------------------------- 6 -----
    {
        "slug": "appareils-et-mises-a-jour",
        "title": "Appareils et mises à jour : la porte qu'on laisse ouverte",
        "summary": "Pourquoi une faille corrigée reste dangereuse tant que personne "
        "n'installe le correctif, dans quel ordre mettre à jour, et les appareils que "
        "tout le monde oublie.",
        "ecrans": [
            {
                "title": "La faille corrigée que personne n'installe",
                "seconds": 75,
                "content": [
                    {
                        "type": "paragraphe",
                        "texte": "La plupart des attaques réussies n'utilisent pas une faille "
                        "inconnue. Elles utilisent une faille **publiée et corrigée**, sur "
                        "une machine où le correctif n'a pas été installé.",
                    },
                    {
                        "type": "paragraphe",
                        "texte": "C'est logique, et c'est désagréable : le jour où un "
                        "correctif paraît, la faille devient publique. Des programmes "
                        "automatiques balaient alors Internet à la recherche des machines qui "
                        "ne l'ont pas encore appliqué. Le délai se compte en jours.",
                    },
                    {
                        "type": "encadre",
                        "ton": "attention",
                        "texte": "« Je fais les mises à jour pendant les vacances » est la "
                        "phrase la plus coûteuse de ce cours. Reporter un mois, c'est laisser "
                        "un mois d'ouverture sur une porte dont l'adresse est publiée.",
                    },
                ],
            },
            {
                "title": "Quoi mettre à jour, et dans quel ordre",
                "seconds": 90,
                "content": [
                    {
                        "type": "paragraphe",
                        "texte": "Tout ne mérite pas la même urgence. L'ordre qui suit tient "
                        "à une seule question : qu'est-ce qui est **exposé** et "
                        "**directement** au contact de l'extérieur ?",
                    },
                    {
                        "type": "liste",
                        "ordonnee": True,
                        "items": [
                            "Ce qui est accessible depuis Internet : site, accès à distance, "
                            "pare-feu, box, serveur de fichiers publié.",
                            "Le navigateur et le lecteur de documents : ce sont eux qui "
                            "ouvrent les fichiers venus de l'extérieur.",
                            "Le système d'exploitation du poste et du téléphone.",
                            "Les autres logiciels, et les extensions du navigateur — dont on "
                            "supprime celles qu'on n'utilise plus.",
                        ],
                    },
                    {
                        "type": "paragraphe",
                        "texte": "Activez les mises à jour automatiques partout où c'est "
                        "possible. Quand une validation reste nécessaire, redémarrez dans la "
                        "journée : beaucoup de correctifs ne prennent effet qu'au redémarrage.",
                    },
                    {
                        "type": "encadre",
                        "ton": "info",
                        "texte": "Un appareil qui ne reçoit plus de mises à jour du tout — un "
                        "téléphone trop ancien, un système en fin de vie — ne se sécurise "
                        "pas : il se remplace, ou s'isole du reste du réseau.",
                    },
                ],
            },
            {
                "title": "Ce qu'on installe soi-même",
                "seconds": 75,
                "content": [
                    {
                        "type": "paragraphe",
                        "texte": "Une mise à jour légitime ne s'annonce pas par une fenêtre "
                        "surgissante sur un site web. C'est un déguisement classique : le "
                        "faux message « votre navigateur doit être mis à jour » installe "
                        "exactement ce qu'il prétend corriger.",
                    },
                    {
                        "type": "liste",
                        "items": [
                            "N'installez que depuis le site officiel de l'éditeur, le magasin "
                            "d'applications du système, ou le logiciel lui-même.",
                            "Refusez les logiciels envoyés en pièce jointe, même par un collègue.",
                            "Méfiez-vous du premier résultat d'un moteur de recherche : c'est "
                            "souvent une publicité, parfois une copie.",
                            "Les versions « gratuites » de logiciels payants embarquent très "
                            "souvent autre chose.",
                        ],
                    },
                    {
                        "type": "encadre",
                        "ton": "attention",
                        "texte": "Si votre ordinateur vous demande le mot de passe "
                        "administrateur alors que vous n'avez rien lancé, refusez, et "
                        "signalez-le.",
                    },
                ],
            },
            {
                "title": "Le téléphone est un ordinateur",
                "seconds": 75,
                "content": [
                    {
                        "type": "paragraphe",
                        "texte": "Le téléphone contient la messagerie, les documents, la "
                        "deuxième clé d'authentification, et souvent l'accès bancaire. "
                        "Autrement dit, tout — et il est bien plus souvent perdu qu'un "
                        "ordinateur.",
                    },
                    {
                        "type": "liste",
                        "items": [
                            "Un code de déverrouillage, pas un schéma trop simple, et le "
                            "chiffrement activé.",
                            "Les mises à jour du système, installées quand elles arrivent.",
                            "Les applications installées depuis le magasin officiel uniquement.",
                            "Faites le ménage : une application qu'on n'ouvre plus garde ses "
                            "autorisations.",
                        ],
                    },
                    {
                        "type": "encadre",
                        "ton": "info",
                        "texte": "Regardez une fois par trimestre les autorisations "
                        "accordées : une lampe de poche qui accède aux contacts et à la "
                        "position n'a pas besoin de les connaître.",
                    },
                ],
            },
            {
                "title": "Les appareils qu'on oublie",
                "seconds": 75,
                "content": [
                    {
                        "type": "paragraphe",
                        "texte": "Les mises à jour du poste de travail sont devenues une "
                        "habitude. Le reste, non — et c'est souvent là que passent les "
                        "attaques, parce que personne ne s'en occupe.",
                    },
                    {
                        "type": "liste",
                        "items": [
                            "La box ou le routeur : mot de passe d'administration changé, "
                            "micrologiciel à jour, administration à distance désactivée.",
                            "Le boîtier de stockage réseau : c'est une cible de choix, il "
                            "contient les fichiers et parfois les sauvegardes.",
                            "L'imprimante multifonction : elle garde des copies des documents "
                            "scannés, et elle a un mot de passe par défaut.",
                            "Les caméras et objets connectés : à isoler du réseau de travail, "
                            "ou à débrancher.",
                        ],
                    },
                    {
                        "type": "paragraphe",
                        "texte": "Votre entreprise suit {actifs_surveilles} actifs exposés "
                        "sur Internet dans la plateforme : ce sont ceux dont les correctifs "
                        "comptent le plus, puisqu'ils sont visibles de l'extérieur.",
                        "repli": "Les actifs exposés sur Internet — site, messagerie, accès "
                        "à distance — sont ceux dont les correctifs comptent le plus, "
                        "puisqu'ils sont visibles de l'extérieur.",
                    },
                    {
                        "type": "encadre",
                        "ton": "exemple",
                        "texte": "Un mot de passe par défaut laissé sur un boîtier de "
                        "stockage se trouve dans la notice, publiée en ligne. Ce n'est pas un "
                        "secret : c'est une clé sous le paillasson, et le paillasson est le "
                        "même chez tout le monde.",
                    },
                ],
            },
        ],
        "questions": [
            (
                1,
                1,
                "Pourquoi une faille déjà corrigée par l'éditeur reste-t-elle dangereuse ?",
                UNIQUE,
                "La publication du correctif rend la faille publique. Des programmes "
                "automatiques cherchent alors les machines qui ne l'ont pas appliqué : "
                "l'existence du correctif est ce qui déclenche les attaques, pas ce qui les "
                "arrête.",
                [
                    (
                        "Parce que la publication du correctif rend la faille publique et "
                        "exploitable.",
                        True,
                    ),
                    ("Parce que les correctifs ne fonctionnent qu'en partie.", False),
                    ("Parce que les attaquants disposent de failles inconnues.", False),
                    ("Parce que l'antivirus ne détecte pas les failles.", False),
                ],
            ),
            (
                2,
                2,
                "Par quoi commencer quand plusieurs mises à jour sont en attente ?",
                UNIQUE,
                "L'exposition décide de l'ordre : ce qui est joignable depuis Internet peut "
                "être attaqué sans qu'aucun salarié fasse quoi que ce soit. Le reste demande "
                "une action humaine, et vient donc ensuite.",
                [
                    ("Par ce qui est accessible depuis Internet.", True),
                    ("Par les logiciels les plus utilisés au quotidien.", False),
                    ("Par les postes des personnes les plus exposées hiérarchiquement.", False),
                    ("L'ordre n'a pas d'importance si tout est fait la même semaine.", False),
                ],
            ),
            (
                3,
                3,
                "Un site affiche « votre navigateur est obsolète, cliquez pour mettre à "
                "jour ». Que faites-vous ?",
                UNIQUE,
                "Une mise à jour légitime ne s'annonce jamais depuis une page web. On ferme, "
                "puis on vérifie dans le navigateur lui-même — c'est le seul endroit qui dit "
                "la vérité sur sa propre version.",
                [
                    ("Je ferme la page et je vérifie dans le menu du navigateur.", True),
                    ("Je clique : un navigateur à jour est important.", False),
                    ("Je cherche le navigateur dans un moteur de recherche et j'installe.", False),
                    ("Je transmets le lien au service informatique pour qu'il installe.", False),
                ],
            ),
            (
                4,
                4,
                "Quelles précautions concernent le téléphone professionnel ?",
                MULTIPLE,
                "Le chiffrement et un code de déverrouillage protègent le contenu en cas de "
                "perte, et la revue des autorisations limite ce que chaque application peut "
                "atteindre. Installer hors magasin officiel ou désactiver les mises à jour "
                "font exactement le contraire.",
                [
                    ("Activer le chiffrement et un code de déverrouillage.", True),
                    ("Revoir périodiquement les autorisations des applications.", True),
                    ("Installer les applications depuis n'importe quelle source fiable.", False),
                    (
                        "Désactiver les mises à jour automatiques pour économiser la batterie.",
                        False,
                    ),
                ],
            ),
            (
                5,
                5,
                "Quel appareil est le plus souvent oublié dans les mises à jour, alors qu'il "
                "est exposé ?",
                UNIQUE,
                "La box ou le routeur est à la frontière du réseau : il est joignable depuis "
                "l'extérieur, garde souvent son mot de passe d'administration d'origine, et "
                "personne n'a le réflexe de mettre à jour son micrologiciel.",
                [
                    ("La box ou le routeur.", True),
                    ("L'ordinateur portable de la direction.", False),
                    ("Le logiciel de comptabilité.", False),
                    ("Le poste de l'accueil.", False),
                ],
            ),
            (
                6,
                2,
                "Un téléphone qui ne reçoit plus aucune mise à jour du fabricant. Que faire ?",
                UNIQUE,
                "Un appareil qui ne reçoit plus de correctifs ne peut plus être sécurisé : les "
                "failles publiées ne seront jamais comblées. Il se remplace, ou s'isole du "
                "réseau de travail. Un antivirus ne comble pas une faille du système.",
                [
                    ("Le remplacer, ou l'isoler du réseau de travail.", True),
                    ("Y installer un antivirus pour compenser.", False),
                    ("Continuer à l'utiliser en évitant les sites inconnus.", False),
                    ("Le réinitialiser : il repartira à jour.", False),
                ],
            ),
        ],
    },
]
