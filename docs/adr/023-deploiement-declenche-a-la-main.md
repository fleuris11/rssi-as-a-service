# ADR-023 — Déploiement automatisé, déclenché à la main

- **Statut** : accepté
- **Date** : 2026-08-25
- **Contexte** : mise en production (voir `docs/deploiement_production.md`)

## Contexte

Le déploiement a d'abord été entièrement manuel : connexion SSH, `git pull`,
reconstruction, vérification à la main. Reproductible, mais lent, et surtout
**non tracé** — rien ne dit après coup qui a déployé quoi, quand, ni pourquoi.

Un déploiement automatique après chaque fusion sur `main` (déploiement continu)
est la réponse habituelle. La question posée ici est de savoir si elle convient
à **cette** production.

Deux particularités pèsent :

1. **La production sert de démonstration commerciale.** L'exploitant y conduit
   des prospects en direct.
2. **Elle sert de support de certification** (RNCP38822). Elle sera montrée à
   un jury, à une date connue à l'avance.

À quoi s'ajoute un fait de rythme : le produit est développé par une seule
personne, par phases de plusieurs jours. La fréquence de livraison ne justifie
pas un automatisme permanent.

## Options

### A. Rester entièrement manuel

Aucun outil à construire. Mais chaque déploiement reste une suite de commandes
tapées, donc oubliables et non tracées — et rien n'empêche de déployer un
commit dont la CI est rouge.

### B. Déploiement continu (automatique après CI verte sur `main`)

La pratique de référence : le code fusionné arrive en production sans geste.
Réduit l'écart entre ce qui est validé et ce qui tourne.

En contrepartie, **la production change sans que personne ne l'ait décidé à ce
moment-là**. Une fusion pendant une démonstration modifie le site sous les yeux
d'un prospect. Le bénéfice attendu — livrer souvent, vite — suppose une
fréquence de livraison que ce projet n'a pas.

### C. Automatisé, déclenché à la main (retenue)

Le déploiement est un workflow complet — récupération, reconstruction,
migrations, vérification externe — mais il ne part **que** sur demande
explicite, avec un motif obligatoire.

## Décision

**Option C.**

L'automatisation apporte l'essentiel de ce qu'on lui demande : reproductibilité,
traçabilité, refus de déployer du rouge, vérification systématique après coup.
Le déclenchement manuel ne retire qu'une chose : le fait que le déploiement
parte **sans qu'on l'ait voulu à cet instant**. C'est précisément ce qu'on veut
conserver ici.

Autrement dit, on ne renonce pas à l'automatisation ; on renonce au
*déclenchement* automatique, et on garde le reste.

### Garde-fous du workflow

| Garde-fou | Raison |
|---|---|
| `workflow_dispatch` uniquement | jamais sur `push` : c'est la décision même de cet ADR |
| **Refus si la CI n'est pas verte** sur le commit visé | `CLAUDE.md` interdit de fusionner sur du rouge ; à plus forte raison de mettre en production |
| Motif obligatoire | apparaît dans le récapitulatif : un journal sans le « pourquoi » ne sert qu'à constater |
| `concurrency` | deux déploiements simultanés se disputeraient le dépôt sur le serveur |
| Empreinte du serveur épinglée (`known_hosts`) | sans elle, un détournement DNS suffirait à livrer le code à un autre serveur |
| Vérification depuis **l'extérieur** | seule mesure qui dise ce qu'un visiteur constate réellement |

### Clé SSH de déploiement

Une clé **dédiée**, distincte de celle du poste de l'exploitant. Elle vit dans
les secrets du dépôt (`DEPLOY_SSH_KEY`), sans phrase de passe — un workflow ne
peut pas en saisir une.

Conséquence assumée : **quiconque peut déclencher un workflow sur ce dépôt peut
déployer.** Sur un dépôt à un seul mainteneur, le risque est celui de la
compromission du compte GitHub — auquel cas le dépôt lui-même est déjà perdu.

**Révocation.** Retirer la ligne correspondante des clés autorisées sur le
serveur suffit à couper l'accès immédiatement, sans toucher à la clé
personnelle de l'exploitant :

```bash
ssh ubuntu@<serveur>
sed -i '/deploiement github-actions/d' ~/.ssh/authorized_keys
grep -c '' ~/.ssh/authorized_keys   # doit décroître de 1
```

Puis supprimer le secret `DEPLOY_SSH_KEY` dans les réglages du dépôt. À faire
si le compte GitHub est compromis, si le dépôt change de mainteneur, ou
périodiquement — une clé de déploiement qui traîne des années est une clé
qu'on a oublié de surveiller.

## Conséquences

- Le déploiement devient traçable : qui, quoi, quand, pourquoi.
- Il devient impossible de mettre en production un commit dont la CI est rouge,
  ce qui n'était pas garanti auparavant.
- L'exploitant garde la maîtrise du moment. En particulier, il peut geler la
  production avant une soutenance sans rien désactiver.
- La vérification post-déploiement est systématique, plus laissée à la
  discipline.

## Perspective d'évolution

Le déploiement continu complet reste la cible, et le passage est peu coûteux :
ajouter un déclencheur `push` sur `main` au workflow existant. Trois conditions
devraient être réunies avant :

1. **La CI verte durablement** — elle est restée rouge deux semaines sans que
   personne ne le voie. Déployer automatiquement dans ces conditions
   propagerait en production ce que la CI aurait dû arrêter.
2. **Un environnement de préproduction**, pour que « ça passe la CI » ne soit
   pas le seul filet avant les vrais clients.
3. **Un retour arrière automatique** en cas d'échec de la vérification externe.
   Aujourd'hui, un déploiement raté laisse la production en l'état et demande
   une intervention.

Tant que ces trois points ne sont pas acquis, le déclenchement manuel n'est pas
un retard sur l'état de l'art : c'est la contrepartie honnête de ce qui manque.
