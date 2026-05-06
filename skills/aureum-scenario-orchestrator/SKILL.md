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

Produit:
- scenario principal;
- scenario alternatif;
- declencheur;
- invalidation;
- confirmation requise;
- agents qui soutiennent;
- agents qui contredisent.

## Poids dynamiques

Poids changent selon regime:
- marche normal: macro + technique plus forts;
- geopolitique: oil/geopolitics plus forts;
- Elliott unclear: poids 0;
- source degradee: poids reduit;
- news non confirmee seule: pas de trade.

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
- source stale critique -> NO_TRADE ou WAIT;
- Elliott unclear -> poids 0.

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

### Limites

- Ne pas masquer les contradictions.
- Ne pas forcer un trade pour reduire WAIT.
- Elliott unclear vaut poids zero.

### Bons exemples

- `WATCH_SELL: correlations et technique alignes, trade bloque jusqu'a cloture M15 sous support.`

### Mauvais exemples

- `SELL car score global 55/100` sans trigger.
