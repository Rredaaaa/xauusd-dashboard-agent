---
name: aureum-scenario-orchestrator
description: Specification Scenario Engine et Orchestrator v3: biais, setup surveille, trade exploitable.
category: orchestration
---

# Aureum Scenario Orchestrator

## Probleme actuel

Le terminal dit souvent `WAIT`, ce qui est prudent mais peu utile.

La v3 doit afficher:
- direction probable;
- setup surveille;
- condition de declenchement;
- raison du refus de trade.

## Statuts v3

- `NO_TRADE`: aucune opportunite propre.
- `MARKET_BIAS_BUY`: biais marche haussier, pas de setup.
- `MARKET_BIAS_SELL`: biais marche baissier, pas de setup.
- `WATCH_BUY`: setup BUY surveille.
- `WATCH_SELL`: setup SELL surveille.
- `TRADE_BUY`: trade BUY exploitable.
- `TRADE_SELL`: trade SELL exploitable.
- `WAIT`: incoherence ou risque trop eleve.

## ScenarioEngine

Statut projet: Phase 28 livree v1.

Produit:
- scenario principal;
- scenario alternatif;
- declencheur;
- invalidation;
- confirmation requise;
- agents qui soutiennent;
- agents qui contredisent.

Implementation v1:
- dataclass `ScenarioPlan`;
- fonction `build_scenario_plan`;
- payload public `scenario_plan`;
- panneau Decision `Scenario Engine v3`;
- tests `WATCH_BUY` et contradiction NewsFact.

## Poids dynamiques

Statut projet: Phase 29 livree v1.

Poids changent selon regime:
- marche normal: macro + technique plus forts;
- geopolitique: oil/geopolitics plus forts;
- structure technique claire: poids technique augmente;
- structure technique contradictoire: poids technique reduit;
- source degradee: poids reduit, pas `WAIT` automatique si ce n'est pas un blocker;
- news non confirmee seule: pas de trade.

Implementation v1:
- moteur `orchestrator_v3_dynamic`;
- poids dynamiques visibles dans Decision par composant;
- `NO_TRADE` si preflight/source critique/data quality bloque;
- `WATCH_BUY` ou `WATCH_SELL` si la direction existe mais qu'un trigger, une invalidation, une confirmation, une source ou le risk/reward manque;
- `TRADE_BUY` ou `TRADE_SELL` seulement si le Quality Gate v3 valide direction, confirmations, invalidation, data quality et risk/reward.

## Exemple

```text
Statut: WATCH_SELL.
Raison: technique et correlations baissieres, mais macro encore favorable gold.
Declencheur: cloture M15 sous support.
Confirmation: DXY ferme + gold rejette resistance.
Invalidation: retour au-dessus resistance.
```

## Regle importante

Un setup surveille n'est pas un trade.  
Il ne doit pas aller dans le Trade Ledger comme trade actif, mais peut aller dans l'historique des setups.

## Tests

- contradiction forte -> WAIT avec raison;
- biais clair mais trigger absent -> WATCH;
- trigger + quality gate OK -> TRADE;
- prix XAU/USD principal stale -> NO_TRADE ou WAIT;
- source secondaire stale -> warning et confidence reduite;
- structure technique contradictoire -> WAIT ou poids reduit.

## Phase 23 Contract

### Role

Assembler les agents en scenario decisionnel lisible: biais, setup, trade ou refus.

### Inputs

- Agent outputs;
- NewsFacts;
- market regime;
- technical context;
- macro context;
- risk manager decision.

### Outputs

- scenario principal;
- scenario alternatif;
- status v3;
- trigger;
- invalidation;
- reasons.

### Methodologie

1. Separar biais marche et trade exploitable.
2. Pondérer selon regime.
3. Identifier contradictions.
4. Generer trigger/invalidation.
5. Deleguer la validation trade au Risk Manager.
6. Separar blockers et warnings avant de forcer `WAIT`.

### Limites

- Ne pas masquer les contradictions.
- Ne pas forcer un trade pour reduire WAIT.
- Ne pas utiliser Elliott comme structure de decision.
- Un score technique sans trigger/invalidation ne vaut pas trade.
- Ne pas transformer chaque warning source en `WAIT`.

### Bons exemples

- `WATCH_SELL: correlations et technique alignes, trade bloque jusqu'a cloture M15 sous support.`

### Mauvais exemples

- `SELL car score global 55/100` sans trigger.
- `BUY car Elliott dit vague 3` sans moteur valide.
- `WAIT car WGC ETF stale` alors que prix, macro, technique et RR sont exploitables.
