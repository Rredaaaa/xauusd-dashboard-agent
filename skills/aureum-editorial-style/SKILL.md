---
name: aureum-editorial-style
description: Regles de langue trader pour transformer les sorties du dashboard en explications claires et exploitables.
category: editorial
---

# Aureum Editorial Style

## But

Remplacer les phrases vagues par des explications actionnables.

Chaque bloc visible doit repondre a:

1. Fait concret: que s'est-il passe?
2. Preuve/source: d'ou vient l'information?
3. Confirmation marche: prix, oil, DXY, taux, volume confirment-ils?
4. Impact XAU/USD: bullish, bearish, mixte, neutre?
5. Action trader: attendre, surveiller, invalider, valider, refuser.

## Phrases interdites seules

Ne jamais afficher ces phrases sans precision concrete:

- "Le theme existe"
- "Le risque reste actif"
- "Contexte favorable"
- "Flux mitigés"
- "Prudence"
- "Ne confirme pas"
- "Le marche reste vulnerable"
- "Signal fragile"
- "Actualites qui ne contredisent pas"

## Format d'alerte attendu

Structure:

```text
Fait: ...
Confirmation: ...
Impact XAU/USD: ...
Action: ...
```

Version courte dashboard:

```text
Iran/Hormuz surveille, mais WTI/Brent reculent. Le marche ne price pas encore un choc petrole. Impact gold: pas de confirmation refuge; attendre confirmation oil/DXY.
```

## Mauvais exemple

```text
Le theme Iran/Hormuz existe, mais le petrole ne confirme pas un choc.
```

Problemes:
- "theme" ne veut rien dire pour l'utilisateur;
- aucun fait concret;
- aucune source;
- aucune action;
- phrase coupee possible dans l'UI.

## Bon exemple

```text
Plusieurs titres mentionnent Iran/Hormuz, mais WTI et Brent reculent. Le marche ne valide donc pas encore un choc d'offre petrole. Impact XAU/USD: prudence, la prime refuge n'est pas confirmee. Action: attendre oil/DXY ou une cassure technique avant de valider un trade.
```

## Regles UI

- Le dashboard principal doit etre court.
- Les details vont dans Inspector.
- Une carte ne doit pas repeter le meme texte qu'une autre carte.
- Une alerte doit avoir une conclusion exploitable.
- Ne pas mettre de jargon sans definition.

## Tests a ajouter

Verifier que les sorties principales ne contiennent pas:
- "theme existe";
- "flux mitiges" sans detail;
- "contexte favorable" sans preuve;
- "prudence" seule.

Ajouter des tests unitaires sur `ExplanationLayer`.

## Phase 23 Contract

### Role

Transformer toute phrase visible en explication claire, sourcee et actionnable.

### Inputs

- Faits structures;
- chiffres marche;
- source et tier;
- decision ou statut;
- contraintes UI.

### Outputs

- Phrase courte dashboard;
- detail Inspector si necessaire;
- validation `validate_phrase`;
- liste des formulations refusees.

### Methodologie

1. Identifier le fait.
2. Ajouter preuve ou chiffre.
3. Nommer confirmation/invalidation.
4. Expliquer impact XAU/USD.
5. Donner action trader.
6. Refuser les formulations interdites.

### Limites

- Ne pas inventer de source.
- Ne pas cacher l'incertitude.
- Ne pas utiliser une phrase elegante mais inutile.

### Bons exemples

- `WTI -2.1% et Brent -1.8%: le marche ne price pas un choc oil. Action: WAIT refuge.`

### Mauvais exemples

- `Le theme existe.`
- `Prudence.`
