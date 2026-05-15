# Fourniwell Signals v4 - Phase 6

Statut: livree le 2026-05-14.

Objectif: remplacer les SL/TP mecaniques par des niveaux de marche verifiables, avec R/R minimal et sorties partielles.

Patch pre-Phase 7 livre le 2026-05-14:

- `Signal locked`, `Trade Tracker` et Inspector affichent maintenant explicitement `TP1 50%`, `TP2 30%`, `TP3 20%`;
- fallback Google News politique active seulement si Truth Social, White House et tous les mirrors Nitter Trump/WhiteHouse sont indisponibles;
- Phase 7.5 ajoutee a la roadmap juste apres Phase 7 pour calibrer l'Orchestrator par backtest avant l'interface et la production.

Hot-fix P0 livre le 2026-05-15:

- le Desk principal n'affiche plus les SL/TP live de `global_recommendation` comme si c'etait un trade verrouille;
- si un trade ouvert existe, le Desk affiche les niveaux figes du ledger: `reference_price`, `SL`, `TP1 50%`, `TP2 30%`, `TP3 20%`;
- si le statut live est `TRADE_BUY` ou `TRADE_SELL` mais qu'aucun trade locked correspondant n'existe, le Desk affiche un avertissement `Signal live sans trade locked` et masque les niveaux live;
- le payload expose `plans` comme alias de `active_trades` pour compatibilite avec les audits externes;
- `active_trades` est maintenant base sur `outcome=open/partial` et `status=pending/active/tp1_hit`.

Correctif obligatoire suivant, avant Phase 7:

- livrer `ReversalSetup Engine` complet sur les trois horizons `scalp`, `intraday`, `swing`;
- nettoyer le Desk pour retirer le bruit interne (`Orchestrateur v3`, `Quality Gate`, `SURVEILLER_*`, `score pondere`, doublons `Signal live`);
- afficher seulement `REVERSAL BUY`, `REVERSAL SELL` ou `NO REVERSAL TRADE` pour les reversals;
- conserver le chef de file separe du moteur reversal.

Document de reference: `docs/FOURNIWELL_SIGNALS_V4_PRE_PHASE_7_REVERSAL_ENGINE.md`.

## Ce qui est livre

### 1. MarketTradeLevels

Nouveau modele interne:

- direction;
- type de setup;
- entry zone;
- stop loss;
- TP1 / TP2 / TP3;
- R/R de chaque TP;
- validite dynamique;
- repartition partielle 50/30/20;
- raisons de calcul.

### 2. Sources de niveaux

Le moteur utilise maintenant:

- support/resistance du jour;
- pivots Camarilla;
- swing high / swing low M15;
- niveaux psychologiques 00/50;
- niveaux 25 si volatilite elevee;
- EMA H1/H4/M15 ajustees du proxy GC=F vers le spot XAU/USD quand disponibles;
- ATR pour buffer et risque minimal.

### 3. Types de setups

Les niveaux sont adaptes selon:

- `trend_continuation`;
- `range`;
- `breakout`;
- `mean_reversion`;
- `pivot_rejection`;
- `news_reaction`.

### 4. Direction et coherence

Le moteur force l'ordre suivant:

- BUY: `SL < entry < TP1 < TP2 < TP3`;
- SELL: `TP3 < TP2 < TP1 < entry < SL`.

Si les niveaux de marche proches ne donnent pas un R/R suffisant, le moteur elargit le TP1 minimal au lieu de produire un TP absurde.

### 5. Risk/reward

- R/R minimum TP1: `1.50R`;
- tout trade lock est refuse si le TP1 final reste sous le R/R minimum utilisateur;
- `build_trade_quality_gate` conserve le blocage R/R existant;
- `build_trade_plan_from_signal` refait une derniere verification R/R avant verrouillage.

### 6. Validite dynamique

Base livree:

- news reaction: 30 min;
- range: M5 / 2h;
- breakout: M15 / 4h;
- mean reversion: M15 / 4h;
- pivot rejection: H1 / 12h;
- trend continuation: H1 / 12h.

Le trade tracker conserve aussi l'inference existante:

- M5: 2h;
- M15: 4h;
- H1: 12h;
- H4: 24h;
- D1: 72h.

### 7. Integration

Les niveaux v4 sont branches dans:

- `TechnicalDecisionEngine`;
- `build_global_recommendation`;
- `OrchestratorDecision`;
- `build_trade_plan_from_signal`.

Le trade lock prefere les niveaux du `TechnicalDecisionEngine` si sa direction correspond au chef de file. Sinon il reconstruit des niveaux v4 a partir de la structure marche.

## Tests livres

Fichier: `tests/test_xauusd_agent.py`

Tests ajoutes:

- BUY: ordre des niveaux + R/R TP1 >= 1.5;
- SELL: ordre des niveaux + R/R TP1 >= 1.5;
- TechnicalDecision utilise les niveaux marche v4;
- mapping structure -> setup.
- UI: sorties partielles visibles dans les panneaux trade;
- news politique: fallback Google News degrade si tous les feeds directs Trump/WhiteHouse tombent.
- P0 Desk: affichage des niveaux locked depuis le ledger, jamais depuis la recommandation live.

## Critere de reussite Phase 6

- Aucun nouveau TradePlan ne doit etre verrouille avec TP/SL dans le mauvais sens.
- Aucun nouveau TradePlan ne doit passer si R/R TP1 < 1.5.
- Les niveaux visibles sont justifiables par structure, pivots, swing, psychologiques ou ATR.
