---
name: aureum-project-context
description: Contexte complet de reprise Aureum Flux Terminal pour Claude. A lire avant toute phase v3.0.
category: project
---

# Aureum Flux Project Context

## Mission

Aureum Flux Terminal est un dashboard local XAU/USD. Il aide l'utilisateur a lire le marche, pas a trader automatiquement.

Objectif final:
- decision claire `BUY`, `SELL`, `WAIT`, puis v3 `WATCH_BUY` / `WATCH_SELL`;
- explication concrete du pourquoi;
- SL/TP seulement quand le Quality Gate valide un trade exploitable;
- historique append-only des trades et signaux;
- sources auditees dans Inspector.

## Etat actuel

La v2.0 est terminee apres Phase 18:
- dashboard multi-vues;
- design structurel refait;
- Inspector;
- Orchestrateur v2;
- Trade Ledger;
- agents passifs;
- sources FRED, CFTC, WGC/ETF, IG Weekend, WTI/Brent, Event Facts, Trump/Political Statements.

La suite est v3.0:
- Phase 19: audit documentation;
- Phase 20: audit editorial phrase par phrase;
- Phase 21: Explanation Layer;
- Phase 22: News Facts v3;
- Phase 24: Data Routing / Preflight;
- Phase 25: Chart Store OHLC;
- Phase 26: Elliott quarantine;
- Phase 27A: Elliott Removal + TradingView Chart;
- Phase 27B: Technical Decision Engine;
- Phase 28-34: Scenario, Orchestrator, Trade Tracker, Replay, Settings, Reports, QA.

## Regles non negociables

1. Aucune phase ne commence sans validation explicite utilisateur.
2. Avant phase: verifier Git/GitHub.
3. Apres phase: tests, commit, push.
4. Ne jamais lancer de trading automatique.
5. Ne pas mentionner de broker specifique dans l'interface.
6. Ne pas forcer un trade pour reduire `WAIT`.
7. Ne pas inclure Elliott dans le raisonnement utilisateur tant qu'il n'est pas refonde et explicitement revalide.
8. Les details techniques de source restent dans Inspector.
9. Le dashboard principal doit afficher le resultat utile, pas toute la plomberie.

## Probleme principal v3

Le terminal affiche encore des phrases trop vagues. Exemple mauvais:

> Le theme Iran/Hormuz existe, mais le petrole ne confirme pas un choc.

Le terminal doit parler comme un analyste senior a un trader:

> Plusieurs titres mentionnent Iran/Hormuz, mais WTI et Brent reculent. Le marche ne price donc pas encore un choc petrole. Impact XAU/USD: prudence, pas de confirmation refuge. Action: attendre confirmation oil/DXY avant de valider un trade.

## Direction produit

Aureum Flux doit separer:
- `MARKET_BIAS`: direction probable;
- `WATCH_SETUP`: setup surveille, pas encore tradable;
- `TRADE_SETUP`: trade exploitable;
- `NO_TRADE`: aucune opportunite propre.

Le terminal doit etre capable de dire:

> Aucun trade exploitable, mais setup SELL surveille si cassure M15 sous support avec DXY confirme.

## Fichiers importants

- `xauusd_agent.py`: monolithe actuel.
- `tests/test_xauusd_agent.py`: tests existants.
- `docs/AUREUM_FLUX_TERMINAL_V3_PLAN.md`: roadmap officielle v3.
- `reports/trade_ledger.jsonl`: ledger local ignore Git.
- `reports/audit_log.jsonl`: audit local ignore Git.

## Inspiration externe

Repo analyse: `HKUDS/Vibe-Trading`.

A reprendre:
- skills par domaine;
- data routing;
- preflight;
- swarm presets;
- replay/backtest;
- shadow account;
- settings;
- report generator.

A ne pas reprendre:
- UI React complete;
- multi-marche generaliste;
- Elliott simple du repo tel quel;
- strategy generator universel.

## Decision produit Phase 27

Elliott est archive pour la v3.0 active:
- Phase 27A le retire du dashboard, payload, Inspector, rapports et orchestrateur;
- il ne doit plus etre affiche comme agent, preuve, contradiction ou raison de decision;
- la charte principale doit devenir une vraie charte TradingView;
- le Chart Store reste en Inspector pour l'audit des donnees OHLC;
- Phase 27B cree un `TechnicalDecisionEngine` base sur structure, indicateurs, niveaux, volatilite et confirmations.

Indicateurs techniques cibles:
- Market Structure: swing highs/lows, HH/HL, LH/LL, BOS, CHoCH, retest, range high/low;
- Trend: EMA 20/50/100/200, pente EMA, alignement M15/H1/H4/D1;
- Momentum: RSI7/RSI14, MACD, divergence RSI/prix;
- Volatility: ATR14, range du jour vs ATR, compression/expansion, volume spike;
- Levels: high/low jour et veille, open, sessions Asia/London/NY, VWAP si disponible, pivots;
- Liquidity: sweep, fausse cassure, retour dans range;
- Cross confirmation: DXY, US10Y, real yield, WTI/Brent, Silver, GDX/GDXJ, VIX/GVZ.

## Phase 23 Contract

### Role

Servir de contexte de reprise global avant toute phase v3.0.

### Inputs

- Roadmap officielle;
- etat Git/GitHub;
- historique des phases;
- contraintes utilisateur;
- docs projet.

### Outputs

- orientation de phase;
- rappel des regles non negociables;
- fichiers a lire;
- risques a surveiller.

### Methodologie

1. Lire le plan v3.
2. Verifier phase courante.
3. Verifier Git/GitHub.
4. Identifier la prochaine action autorisee.
5. Ne jamais sauter une phase sans accord explicite.

### Limites

- Ce skill ne remplace pas la roadmap.
- Il ne donne pas de logique trading.
- Il ne doit pas justifier une modification hors phase.

### Bons exemples

- `Phase 24 peut commencer seulement apres validation de Phase 23, git clean et origin/main sync.`
- `Phase 27A peut commencer seulement apres validation utilisateur et doit supprimer Elliott visible avant tout nouveau moteur technique.`

### Mauvais exemples

- Reintroduire Elliott dans le dashboard ou le scoring.
- Remplacer TradingView par une charte interne principale.
- Modifier le moteur alors que la phase demande seulement la documentation.
