# Fourniwell Signals v4 - Phase 7

Statut: Phase 7A, 7B et 7C livrees.

Objectif: remplacer la logique mono-setup par un moteur multi-strategies capable de produire plusieurs candidates auditees avant selection du setup dominant.

## Phase 7A livree

Livree le 2026-05-15.

Contenu:

- modele `SetupCandidate`;
- normalisation des directions;
- adaptation `NewsReactionTradePlan` vers `SetupCandidate`;
- conservation de `ReversalSetup` comme moteur separe;
- aucun branchement du coordinateur dans le dashboard ou dans le verdict final.

## Phase 7B livree

Livree le 2026-05-15.

Contenu:

- `PivotRejectionSetup`;
- `MeanReversionSetup`;
- `RangeTradingSetup`;
- `TrendContinuationSetup`;
- `BreakoutDuJourSetup`;
- `build_strategy_candidates`;
- statuts candidates: `TRADE_READY`, `WATCH`, `NO_SETUP`;
- SL/TP/RR calcules via `MarketTradeLevels`;
- validite et cooldown propres par strategie;
- session preferee par strategie;
- conditions et blockers explicites.

La Phase 7B ne modifie pas encore:

- le chef de file;
- le trade lock;
- le dashboard;
- les poids de l'orchestrateur.

Cette separation etait volontaire: la selection du setup dominant est livree en Phase 7C, sans impact sur le verdict final.

## Strategies livrees

### PivotRejectionSetup

But: capter un rejet de pivot/support/resistance.

Base:

- proximite Camarilla S3/S4 ou R3/R4;
- support/resistance jour;
- rejet par meche;
- position dans le range jour;
- RSI avec marge de rebond ou de repli.

Cooldown:

- apres perte: 180 minutes;
- apres gain: 60 minutes.

### MeanReversionSetup

But: capter un retour a la moyenne apres extension excessive.

Base:

- RSI H1 extreme;
- extension vs EMA20 H1;
- rejet de bougie;
- divergence RSI si disponible;
- proxy MACD fade.

Cooldown:

- apres perte: 360 minutes;
- apres gain: 120 minutes.

### RangeTradingSetup

But: traiter les bords de range, surtout en session asiatique.

Base:

- detection high/low sur les 24 dernieres bougies;
- touches du haut et du bas;
- faible force de tendance;
- rejet du bord de range;
- bonus session asiatique.

Cooldown:

- apres perte: 180 minutes;
- apres gain: 60 minutes.

### TrendContinuationSetup

But: suivre une tendance deja alignee.

Base:

- alignement 1D / 4H / 1H;
- stack EMA H1;
- stack EMA higher timeframe;
- pullback proche EMA20/EMA50;
- force de tendance proxy;
- session liquide.

Regle importante:

- le setup est suspendu si le mode event est actif.

Cooldown:

- apres perte: 240 minutes;
- apres gain: 60 minutes.

### BreakoutDuJourSetup

But: capter la cassure du range asiatique.

Base:

- cloture M15 hors range asiatique;
- volume proxy >= 1.5x;
- session London open ou London/NY overlap;
- momentum RSI dans le sens de la cassure;
- R/R TP1 minimum 2.0.

Cooldown:

- apres perte: 240 minutes;
- apres gain: 120 minutes.

## Tests livres

Fichier: `tests/test_xauusd_agent.py`

Tests ajoutes:

- pivot rejection BUY;
- pivot rejection SELL;
- mean reversion BUY;
- mean reversion SELL;
- range trading bas de range;
- range trading milieu de range refuse;
- trend continuation BUY;
- trend continuation suspendu par event mode;
- breakout du jour BUY;
- breakout du jour hors session;
- builder global des six candidates.

Verification:

- `python -m unittest tests.test_xauusd_agent.Phase7BStrategyCandidateTests`
- `python -m unittest tests/test_xauusd_agent.py`
- `python -m py_compile xauusd_agent.py`

## Prochaine etape

## Phase 7C livree

Livree le 2026-05-15.

Contenu:

- `StrategySelection`;
- `StrategyCoordinator`;
- `build_strategy_selection`;
- ranking des candidates Phase 7B;
- selection d'un setup dominant;
- rejet explicite des candidates non eligibles;
- exposition dans le payload via `strategy_candidates` et `strategy_selection`;
- aucun changement du chef de file, du trade lock ou du dashboard.

Le coordinateur classe les candidates selon:

- statut `TRADE_READY` ou `WATCH`;
- direction exploitable `BUY` ou `SELL`;
- priorite metier;
- compatibilite session;
- score de confiance;
- score de confluence;
- R/R TP1 minimum;
- mode event;
- cooldown lie aux trades recents.

Priorites appliquees:

1. `NewsReactionSetup`;
2. `TrendContinuationSetup`;
3. `BreakoutDuJourSetup`;
4. `RangeTradingSetup`;
5. `MeanReversionSetup`;
6. `PivotRejectionSetup`.

Regles importantes:

- `NewsReactionSetup` recoit un bonus si `event_mode.active`;
- `TrendContinuationSetup` et `BreakoutDuJourSetup` sont penalises si le mode event est actif;
- `BreakoutDuJourSetup` exige `R/R TP1 >= 2.0R`;
- les autres setups exigent le R/R minimum utilisateur;
- un trade actif dans la meme direction bloque une nouvelle selection;
- une perte recente dans la meme direction active le cooldown propre a la candidate.

Tests ajoutes:

- NewsReaction prioritaire en mode event;
- TrendContinuation prioritaire en London/NY overlap hors event;
- Breakout refuse sous 2.0R;
- cooldown apres perte recente;
- aucun setup si toutes les candidates sont du bruit.

Verification:

- `python -m unittest tests.test_xauusd_agent.Phase7CStrategyCoordinatorTests`
- `python -m unittest tests/test_xauusd_agent.py`
- `python -m py_compile xauusd_agent.py`

## Prochaine etape

Phase 7D ou Phase 7.5 selon decision:

- soit brancher prudemment la selection dominante dans l'Inspector uniquement;
- soit passer directement a la Phase 7.5 de calibration/backtest avant tout impact sur le chef de file.
