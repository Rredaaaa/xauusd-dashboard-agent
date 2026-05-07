# Guide utilisateur Aureum Flux Terminal

## Objectif

Aureum Flux Terminal aide a lire rapidement le marche `XAU/USD`:

- direction live probable: `BUY`, `SELL` ou `WAIT`;
- score global et raisons;
- SL/TP proposes;
- sources et agents qui valident ou contredisent;
- Trade Plans historises si un signal est exploitable.

Le terminal est un outil d'analyse. Il ne remplace pas le jugement du trader.

## Onglets

### Dashboard

Vue de synthese:

- prix live;
- decision globale;
- regime actif;
- confidence;
- alerte;
- Orchestrateur v2;
- Trade Tracker.

La carte `Position conseillee` montre le signal live. Elle peut changer.

### Market

Vue marche:

- spot XAU/USD;
- IG Weekend Gold quand disponible;
- chandelles 5 minutes;
- support/resistance;
- correlations inter-marches;
- regime politique/petrole;
- COT CFTC;
- ETF flows WGC/GLD/IAU.

### Decision

Vue "pourquoi":

- synthese prioritaire;
- lecture des scores;
- Orchestrateur v2;
- Quality Gate;
- contradictions entre agents;
- Data Feed Governance.

### Technical

Vue technique:

- EMA 20/50/100/200;
- RSI7;
- MACD 5/34/5;
- volume;
- scenarios hausse/baisse/attente;
- agents techniques, dont Elliott Wave Agent.

Note: Elliott Wave est encore un agent passif experimental. Depuis la Phase 26, son poids est `0.00` dans l'orchestrateur: il ne peut pas changer la decision `BUY`, `SELL` ou `WAIT`. Le Chart Store OHLC livre en Phase 25 sert seulement de base technique au futur Elliott Engine v3.

### Macro

Vue macro:

- DXY;
- taux US;
- FRED DGS10/DGS2/T10YIE/DFII10;
- calendrier Fed/BEA;
- MacroAgent.

### Geopolitics & Flows

Vue risque externe:

- geopolitique;
- regime de volatilite;
- Hormuz/Oil Shock;
- ETF flows;
- Event Facts;
- Trump / White House;
- headlines expliquees.

### Inspector

Vue d'audit:

- sources actives;
- dernier refresh;
- sources missing/stale/weak;
- agents actifs;
- sorties recentes des agents;
- trades crees;
- outcomes des trades;
- data quality score;
- Decision Gate et Trade Gate.

Cet onglet sert a comprendre pourquoi une decision ou un trade existe.

### Reports

Vue exports:

- rapport Markdown;
- payload JSON;
- inventaire agents;
- Source Registry;
- Trade Ledger;
- Inspector.

## Signal live vs Trade Plan

### Signal live

Le signal live est calcule a chaque refresh. Il depend du prix, des sources, du regime, des agents et de l'Orchestrateur v2. Il peut passer de `BUY` a `WAIT`, ou de `SELL` a `WAIT`, si le contexte change.

### Trade Plan

Un Trade Plan est cree uniquement quand le Trade Quality Gate valide le signal. Il fige:

- date de creation;
- direction;
- entry/reference price;
- zone d'entree;
- SL;
- TP1/TP2/TP3;
- agents validant;
- agents contradictoires;
- sources;
- regime;
- raisons d'invalidation;
- outcome.

Le Trade Plan est stocke dans:

```text
reports/trade_ledger.jsonl
```

Il n'est pas modifie retroactivement par le signal live. Si le prix atteint SL ou TP, une nouvelle ligne append-only met a jour son outcome.

## Outcomes possibles

- `open`: trade encore ouvert.
- `partial`: TP1 touche.
- `win`: TP2 ou TP3 touche.
- `loss`: SL touche.
- `expired`: validite depassee.
- `invalidated`: invalidation contextuelle ou manuelle future.

## Audit log

Chaque generation ajoute une ligne dans:

```text
reports/audit_log.jsonl
```

Ce fichier trace:

- decision;
- regime;
- data quality;
- issues sources;
- sorties agents;
- gate trades;
- trades.

## Regles de prudence

- `BUY` ou `SELL` ne veut pas dire entrer au marche sans verification.
- `WAIT` veut dire que le terminal refuse de valider une direction exploitable.
- La v3.0 ajoutera des statuts intermediaires `WATCH_BUY` et `WATCH_SELL` pour afficher les setups a surveiller sans forcer un trade.
- Un regime Hormuz/Oil Shock peut inverser la lecture classique geopolitique -> gold.
- Si le petrole capte la liquidite et que le dollar monte, gold peut baisser malgre le risque geopolitique.
- Le spread, l'heure, la volatilite et le calendrier macro doivent etre verifies avant toute decision.
