---
name: aureum-elliott-wave
description: Specification Elliott Engine v3 pour XAU/USD. A utiliser seulement apres Chart Store et quarantine du scoring.
category: technical
---

# Aureum Elliott Wave

## Etat actuel

L'ElliottWaveAgent v2 est experimental. Il regarde surtout des variations recentes et ne fait pas un vrai comptage de vagues.

Regle:

> Tant que le moteur v3 n'est pas livre, Elliott ne doit pas influencer le scoring.

## Role cible

Elliott devient l'agent de structure:
- ou sommes-nous dans la vague?
- quelle vague superieure?
- quelle sous-vague?
- quel scenario principal?
- quelle invalidation?
- quelle confirmation?
- quels targets Fibonacci?

Les autres agents confirment ou contredisent le declenchement.

## Structures minimales a gerer

- impulsion 1-2-3-4-5;
- correction ABC;
- zigzag 5-3-5;
- flat 3-3-5;
- triangle A-B-C-D-E;
- W-X-Y;
- W-X-Y-X-Z;
- corrections combinatoires;
- sous-vagues internes.

## Regles Elliott

- Vague 2 ne retrace pas 100% de vague 1.
- Vague 3 ne peut pas etre la plus courte.
- Vague 4 ne doit pas chevaucher vague 1 sauf cas valide.
- Une vague C peut etre impulsive 1-2-3-4-5.
- Une correction complexe peut contenir W-X-Y ou W-X-Y-X-Z.
- Toujours fournir scenario alternatif si confiance moyenne.

## WaveScenario

Sortie attendue:

```text
timeframes_used
major_degree
minor_degree
primary_scenario
alternate_scenarios
current_wave
subwave
pattern_type
invalidation_price
confirmation_trigger
fib_targets
confidence
status
```

Statuts:
- `CLEAR_STRUCTURE`;
- `PROBABLE_STRUCTURE`;
- `UNCLEAR`;
- `INSUFFICIENT_HISTORY`;
- `CONFLICTING_TIMEFRAMES`.

## Exemple attendu

```text
Structure: fin possible de vague 2 de 3.
Confirmation: cassure du sommet de sous-vague 1 sur M15 avec impulsion H1.
Invalidation: retour sous le bas de vague 2.
Targets: 1.0 / 1.618 / 2.618 extension vague 1.
Statut: WATCH_BUY, pas TRADE_BUY tant que le declencheur n'est pas confirme.
```

## Ce qu'il ne faut pas faire

- Ne pas dire "vague 3 commence" sans confirmation.
- Ne pas compter Elliott sur une seule timeframe.
- Ne pas donner BUY/SELL si la structure est unclear.
- Ne pas cacher l'alternative.
- Ne pas remplacer le risk manager.

## Tests

- fixtures impulsion bullish;
- fixtures correction ABC;
- fixtures WXY;
- fixtures triangle;
- violation regle vague 2;
- wave 3 shortest invalid;
- insufficient history.

## Phase 23 Contract

### Role

Identifier la structure de vague probable uniquement apres livraison du Chart Store.

### Inputs

- OHLC multi-timeframe;
- pivots valides;
- Fibonacci retracements/extensions;
- confirmations des autres agents;
- source quality.

### Outputs

- `WaveScenario`;
- scenario principal;
- scenario alternatif;
- invalidation;
- trigger;
- targets;
- statut `UNCLEAR` si doute.

### Methodologie

1. Lire D1/H4 pour le degre superieur.
2. Lire H1/M15 pour la sous-vague.
3. Valider les regles Elliott.
4. Calculer Fibonacci.
5. Produire scenario principal et alternatif.
6. Refuser toute conclusion si l'historique est insuffisant.

### Limites

- Ne pas scorer avant Phase 27.
- Ne pas annoncer vague 3 sans trigger.
- Ne pas ignorer corrections complexes WXY/WXYXZ.

### Bons exemples

- `WATCH_BUY: fin possible vague 2 de 3, trigger cassure sommet sous-vague 1, invalidation bas vague 2.`

### Mauvais exemples

- `Vague 3 commence` sans chart store ni trigger.
