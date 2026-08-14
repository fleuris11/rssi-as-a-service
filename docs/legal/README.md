# Textes légaux — état et travail restant

> **Ces textes sont des TRAMES. Ils n'ont pas été rédigés ni relus par un
> professionnel du droit et ne doivent pas être publiés en l'état pour une
> commercialisation.**

Ce document dit ce qui est fait, ce qui reste à faire, et pourquoi la
distinction est traitée de cette façon.

## Principe retenu

Les pages légales sont générées depuis un fichier unique,
[`frontend/src/marketing/legalConfig.js`](../../frontend/src/marketing/legalConfig.js).
Deux natures d'information y cohabitent, traitées différemment :

| Nature | État | Raison |
|---|---|---|
| **Ce que fait le produit** (données transmises, sous-traitants, durées de conservation, mesures de sécurité) | **Complet et exact** | C'est vérifiable dans le code. Ces sections ont été écrites en relisant l'implémentation, pas en recopiant un modèle. |
| **Identité de l'éditeur** (raison sociale, immatriculation, adresse, directeur de publication, hébergeur) | **Vide, à remplir** | Inventer une mention plausible donnerait l'apparence de la conformité sans la substance — et personne ne penserait à la corriger. |

Tant qu'un champ d'identité est vide, la page concernée affiche un bandeau
« Mentions à compléter par l'éditeur » qui les énumère. Le manque est donc
visible, pas dissimulé.

## Ce qui reste à faire

### 1. Remplir `legalConfig.js`

Les champs de `LEGAL_ENTITY` et `HOSTING`, plus le nom et la localisation des
sous-traitants dans `SUBPROCESSORS`. Aucune modification de code n'est
nécessaire : les pages se mettent à jour et les bandeaux disparaissent d'eux-mêmes.

### 2. Faire relire les quatre pages par un juriste

| Page | État | Ce qui manque |
|---|---|---|
| Mentions légales | Trame | Identité de l'éditeur, hébergeur |
| Politique de confidentialité | **Substantiellement complète** | Relecture juridique ; base légale des traitements ; modalités précises d'exercice des droits et délais |
| Conditions générales | **Trame minimale** | Durée, prix et paiement, responsabilité, propriété intellectuelle, droit applicable, juridiction. À rédiger entièrement. |
| Sécurité et traitement des données | **Complète et factuelle** | Relecture pour vérifier qu'aucune formulation ne s'apparente à une garantie |

### 3. Rédiger le contrat de sous-traitance (DPA)

Prévu et annoncé « en cours de finalisation juridique » sur la page de
confidentialité, non rédigé. Doit couvrir au minimum : objet et durée du
traitement, catégories de données et de personnes concernées, obligations du
sous-traitant, liste des sous-traitants ultérieurs et procédure de
notification en cas de changement, mesures de sécurité, sort des données en
fin de contrat, modalités d'audit.

Une fois rédigé, le déposer en PDF et brancher le lien de téléchargement sur
la page de confidentialité.

### 4. Vérifier la cohérence avec la configuration réelle

Les durées de conservation affichées (`RETENTION` dans `legalConfig.js`)
doivent correspondre aux réglages du serveur :

```bash
grep -n "RETENTION_DAYS" backend/config/settings.py
```

À la date de rédaction : 90 jours pour les mots de passe fuités, 365 jours
pour le journal des consultations. **Si ces valeurs changent en production, la
page de confidentialité doit être mise à jour** — elles ne sont pas lues
dynamiquement depuis le serveur, la page publique étant servie sans
authentification.

## Règle de rédaction appliquée

**Nulle part le produit n'est déclaré « conforme au RGPD ».** On décrit ce qui
est fait — chiffrement, cloisonnement, pseudonymisation, durées, traçabilité —
et le lecteur juge. Une auto-déclaration de conformité n'a aucune valeur
juridique et se retourne contre son auteur au premier incident.

De la même façon, la page « Sécurité et traitement des données » comporte une
section **« Ce que le service ne fait pas »** : il ne bloque aucune attaque,
n'installe aucun agent, n'atteste d'aucune conformité, et ne teste jamais un
identifiant. Ces limites sont un argument de crédibilité, pas un aveu.
