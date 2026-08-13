# Runbook de démonstration client

Scénario minuté, ~12 minutes. Chaque étape indique **ce qu'on montre** et
**ce qu'on dit**. Le fil conducteur : un dirigeant de TPE ne veut pas une
liste de problèmes, il veut savoir par quoi commencer.

> **Chronométrage mesuré** (2026-08-13, en local, enchaînement automatisé sans
> parole) : **24 s** pour l'ensemble des 8 étapes, dont 6,5 s pour la
> révélation (la vérification du mot de passe est volontairement coûteuse) et
> 3,4 s pour le premier affichage de la page Exposition. Le budget de 12
> minutes est donc presque entièrement du temps de parole — la marge sous les
> 15 minutes est confortable, même en répondant aux questions au fil de l'eau.
> Non encore rejoué sur le VPS : la plateforme n'est pas déployée à ce jour
> (voir `docs/deployment_runbook.md`).

> **Règle absolue : la démo ne dépend jamais d'un appel API réel.** Le tenant
> `Demo — Cabinet Comptable Durand` est intégralement seedé (fuites, scores,
> corrélations, synthèse IA pré-générée). Aucun réseau, aucun quota, aucun
> aléa. Si vous voyez un spinner qui dure, ce n'est pas la démo qui appelle
> Breachsense — c'est un problème local, voir « Si ça casse » en bas.

---

## Avant la démo (5 minutes, à faire une fois)

```bash
docker compose up -d                                     # stack complète
docker compose exec web python manage.py seed_demo_tenant --reset
cd frontend && npm run dev
```

Vérifications rapides :

| Point | Commande / geste | Attendu |
|---|---|---|
| Stack saine | `docker compose ps` | postgres, redis, worker, beat en `healthy` |
| Données de démo | ouvrir `/exposition` | 3 actifs, le premier à 100 |
| Synthèse présente | même page | bandeau « Analyse » visible en haut |

**Préparer l'écran** : navigateur en plein écran, zoom 100 %, onglets inutiles
fermés, notifications système coupées. Se connecter **avant** de partager
l'écran (personne n'a besoin de voir la page de connexion).

Identifiants : `marie.durand@cabinet-durand-demo.fr` / `DemoDurand2026!`

---

## Le scénario

### 1. Le point de départ — 1 min

**Écran** : page `/exposition`, sans rien faire.

> « Voici ce que voit un dirigeant en arrivant le matin. Pas une liste
> d'alertes techniques : ses actifs, classés par niveau d'exposition. Ce qu'il
> doit regarder en premier est en haut. »

Laisser 3 secondes de silence sur la page. C'est le moment où l'interlocuteur
comprend le produit sans explication.

### 2. L'analyse — 1 min 30

**Écran** : bandeau « Analyse » en haut.

> « Cette lecture d'ensemble est générée par IA, à partir des éléments qui
> sont déjà à l'écran. Elle ne remplace rien : elle relie. Ici, elle repère
> que trois fuites concernent le même compte, ce qui suggère un poste infecté
> plutôt que trois incidents séparés — et elle dit par quoi commencer. »

**Point à faire passer** : *« Les identifiants et les noms de domaine sont
pseudonymisés avant d'être envoyés au fournisseur d'IA, et ré-injectés à la
réponse. Aucun mot de passe n'est jamais transmis, même chiffré. »*

Si on vous demande la fiabilité : *« la page reste complète sans cette
analyse — c'est une couche au-dessus, jamais un prérequis. »*

### 3. Les signaux avant-coureurs — 2 min

**Écran** : carte « Signaux avant-coureurs ».

> « Ceci n'est pas une fuite. C'est ce qu'on observe **avant** l'incident. Ici,
> quelqu'un a déposé deux noms de domaine qui imitent le vôtre. C'est le
> préparatif classique d'un faux email demandant un virement. »

**Geste** : cliquer « Marquer traité » sur un signal → il disparaît de la
carte. Puis « Voir les signaux traités » → il est là.

> « Traiter un signal le fait sortir de la vue active, sans le perdre. »

**Différenciateur n°1 à nommer explicitement** : *« La plupart des outils vous
préviennent après. Ici on vous prévient avant, et on vous dit quoi faire :
prévenir la comptabilité de vérifier l'adresse exacte de l'expéditeur. »*

### 4. Le score et son explication — 2 min

**Écran** : premier actif, déjà déplié. Pointer le score (100, Critique), puis
« Comment ce score est calculé ».

> « Le score est calculé de façon déterministe — jamais par une IA. Deux
> raisons : il doit donner le même résultat sur les mêmes données, et il doit
> être justifiable. Vous voyez ici exactement ce qui compose le 100 : quelle
> fuite apporte combien, et pourquoi. »

**Question fréquente** — *« et si je traite une fuite ? »* → *« le score
baisse, c'est tout l'intérêt du geste. »*

### 5. La vulgarisation — 1 min 30

**Écran** : le finding « Sessions / cookies compromis ».

Lire la phrase à l'écran, telle quelle :

> « Un cookie de session a été volé : c'est le jeton que votre navigateur
> garde après une connexion réussie, pour ne pas redemander le mot de passe à
> chaque page. Avec ce jeton, un attaquant entre dans le compte **sans avoir
> besoin du mot de passe ni du code de double authentification**. »

**Différenciateur n°2** : *« C'est écrit pour un dirigeant, pas pour un
analyste. Et c'est déterministe : aucun appel IA, donc affiché
instantanément et toujours identique. »*

Pointer l'encart « À faire » juste en dessous.

### 6. La corrélation de réutilisation — 2 min

**Écran** : le finding portant le badge « Réutilisation possible — à vérifier ».

> « Cette adresse professionnelle apparaît dans la fuite d'un service qui
> n'est pas le vôtre. Nous ne testons aucun mot de passe nulle part — donc
> nous ne dirons jamais que le compte est compromis. Nous disons :
> réutilisation **possible**, à vérifier. »

**Différenciateur n°3, et le point de crédibilité de toute la démo** :

> *« La différence entre "possible" et "confirmé" n'est pas de la prudence
> commerciale, c'est de l'honnêteté technique. Un outil qui vous dirait
> "compromis" sans l'avoir vérifié vous ferait perdre du temps sur de faux
> positifs. »*

### 7. La révélation du secret — 2 min

**Écran** : bouton « Révéler le mot de passe » sur ce même finding.

> « Et voici comment on lève l'hypothèse. »

**Geste** : cliquer → la modale s'ouvre.

Pointer le bandeau de traçabilité **avant** de saisir quoi que ce soit :

> « Cet accès est tracé : qui, quand, depuis quelle adresse. »

Saisir le mot de passe, valider. **Attendre** — la vérification prend ~1,5 s
et affiche « Vérification de votre identité… ».

> « Ce délai est volontaire : le mot de passe du compte est revérifié à chaque
> révélation. Un jeton de session volé ne suffit pas. »

Le secret s'affiche avec un compte à rebours.

> « Il disparaît tout seul au bout de 30 secondes. Le dirigeant peut
> maintenant vérifier si ce mot de passe est réutilisé sur ses accès
> professionnels — c'était l'hypothèse de tout à l'heure. »

**Le cycle de vie complet, en une phrase** : *« chiffré à l'ingestion,
révélable sous conditions, tracé, et effacé automatiquement au bout de 90
jours — seule la valeur disparaît, l'historique de la fuite reste. »*

### 8. Le secret purgé — 30 s

**Écran** : le finding portant « Mot de passe effacé le … ».

> « Voici à quoi ressemble une fuite dont le secret a été purgé. On garde la
> trace de l'incident, on ne garde plus la valeur. C'est notre réponse à la
> question RGPD : nous ne constituons pas une base de mots de passe. »

---

## Remise à zéro entre deux démos

```bash
docker compose exec web python manage.py seed_demo_tenant --reset
```

Remet les fuites, statuts, scores et la synthèse dans leur état initial
(~5 secondes). **À faire systématiquement** : l'étape 3 marque un signal
traité, l'étape 7 écrit une ligne d'audit.

Rafraîchir la page ensuite (`Ctrl+F5`).

---

## Si ça casse en direct

| Symptôme | Réaction |
|---|---|
| Page bloquée sur les squelettes de chargement | Ne pas attendre : `Ctrl+F5`. Si ça persiste, redémarrer le serveur Vite (état de rechargement à chaud incohérent — déjà rencontré, sans rapport avec les données). |
| La révélation renvoie « Trop de tentatives » | Rate limit atteint (5/min) — normal après plusieurs répétitions. **Le dire** : *« c'est la protection anti-extraction qui se déclenche, elle fait exactement son travail. »* Puis passer à l'étape suivante. |
| Le bandeau « Analyse » a disparu | Le seed n'a pas été rejoué. Continuer sans : la page est complète sans lui, c'est même un argument. |
| Une page renvoie une erreur | Ne pas déboguer devant le client. Basculer sur `/compromissions`, qui montre la même matière autrement. |

**Règle générale** : ne jamais ouvrir la console du navigateur ni un terminal
pendant la démo. Si quelque chose ne marche pas, le dire simplement, passer à
la suite, et y revenir après.

---

## Ce qu'il ne faut pas promettre

Points à ne **pas** affirmer, faute de les avoir vérifiés en conditions
réelles à ce jour :

- **le webhook temps réel** : implémenté et testé avec des charges simulées,
  mais jamais validé de bout en bout contre l'API réelle (il faut une URL
  publique, donc un déploiement — voir `docs/deployment_runbook.md`) ;
- **les volumes de détection réels** : le tenant de démo est seedé, il ne
  reflète pas ce que Breachsense remonterait sur un domaine donné ;
- **l'envoi d'emails en production** : la météo quotidienne et les alertes
  fonctionnent en local et en test, pas encore sur un vrai SMTP de production.

Formulation honnête si la question vient : *« c'est implémenté et testé, mais
je ne l'ai pas encore vu tourner en production — je préfère vous le dire. »*
