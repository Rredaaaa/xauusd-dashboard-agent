---
name: aureum-trade-quality-gate
description: Regles de validation trade exploitable, separation signal live, setup surveille et TradePlan fige.
category: risk
---

# Aureum Trade Quality Gate

## Role

Empecher le terminal de creer un trade faible tout en evitant de cacher les setups utiles.

## Trois niveaux

1. Biais:
   - direction probable;
   - pas assez propre pour setup.

2. Setup surveille:
   - direction et trigger connus;
   - manque confirmation ou contexte.

3. Trade exploitable:
   - entry zone;
   - SL;
   - TP;
   - invalidation;
   - expiration;
   - risk/reward;
   - sources OK.

## Conditions minimales TradePlan

- direction `BUY` ou `SELL`;
- Preflight non bloquant;
- data quality exploitable, meme degradee si le prix principal est frais;
- source prix fraiche;
- invalidation claire;
- SL/TP calculables;
- risk/reward minimum;
- au moins deux confirmations;
- contradictions sous seuil;
- regime non bloquant;
- pas de news faible seule comme declencheur.

Un warning ne suffit pas a refuser un TradePlan. Le gate doit separer:

- hard block: pas de direction, prix principal absent/stale, data quality trop faible, RR insuffisant, regime extreme, contradiction directionnelle majeure;
- advisory: source secondaire stale, data quality degradee, news weak, mode event modere.

Si seuls des advisory sont presents, le TradePlan peut etre cree avec confiance reduite et raisons visibles.

## Raisons de refus

Le terminal doit afficher ce qui manque:

- score insuffisant;
- source bloquante stale;
- contradiction agents;
- trigger pas confirme;
- structure technique unclear;
- macro contradictoire;
- oil/DXY non confirme;
- risk/reward insuffisant.

## TradePlan append-only

Quand un trade est cree:
- ne jamais le modifier retroactivement;
- append new outcome;
- conserver sources, agents, scenario, SL/TP.

## Exemple refusal utile

```text
Trade refuse. Biais SELL surveille, mais pas de cassure M15 et DXY ne confirme pas encore. Action: attendre cloture sous support ou invalider si retour au-dessus resistance.
```

## Tests

- WATCH ne cree pas trade actif;
- TRADE cree ledger append-only;
- SL touche -> loss;
- TP touche -> win/partial;
- duplicate trade cooldown;
- source prix stale bloque trade;
- source secondaire stale degrade confidence sans bloquer seule.

## Phase 23 Contract

### Role

Separar biais, setup surveille et TradePlan fige pour eviter les faux signaux exploitables.

### Inputs

- direction candidate;
- entry zone;
- SL/TP;
- RR;
- source quality;
- confirmations;
- active trades.

### Outputs

- gate status;
- missing requirements;
- TradePlan si valide;
- reason visible.

### Methodologie

1. Verifier direction BUY/SELL.
2. Verifier SL/TP et RR.
3. Verifier confirmations.
4. Verifier source quality en separant blockers et warnings.
5. Bloquer duplicate/cooldown.
6. Ecrire ledger append-only seulement si TRADE.

### Limites

- WATCH ne cree pas trade actif.
- TradePlan ne se modifie pas apres creation.
- Une headline seule ne suffit jamais.
- ElliottWaveAgent, RiskManagerAgent et OrchestratorAgent ne comptent pas comme contradictions directionnelles pour verrouiller un trade.

### Bons exemples

- `Trade refuse: WATCH_SELL valide, mais entry non touchee et DXY sous seuil.`
- `Trade valide avec warning: SELL 63/100, prix frais, deux agents decisionnels alignes, WGC ETF stale donc confidence reduite.`

### Mauvais exemples

- Recalculer SL/TP d'un trade deja verrouille.
