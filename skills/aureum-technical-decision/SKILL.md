---
name: aureum-technical-decision
description: Technical Decision Engine v3: remplace Elliott par une lecture structure, indicateurs, niveaux, volatilite et confirmations.
category: technical
---

# Aureum Technical Decision

## But

Remplacer Elliott par un moteur technique explicable et testable.

Le moteur ne doit pas deviner une vague. Il doit dire:
- quelle structure est visible;
- quel trigger manque ou confirme;
- quelle invalidation rend le setup faux;
- pourquoi le trade est exploitable, surveille ou refuse.

## Inputs techniques

- Chart Store OHLC M5/M15/H1/H4/D1;
- prix live XAU/USD;
- niveaux jour/veille/session;
- EMA 20/50/100/200;
- RSI7/RSI14;
- MACD ligne/signal/histogramme;
- ATR14 et range du jour;
- volume proxy futures;
- confirmations DXY, US10Y, real yield, WTI/Brent, Silver, GDX/GDXJ, VIX/GVZ;
- Preflight status.

## Blocs d'analyse

1. Market Structure:
   - swing highs / swing lows;
   - HH/HL;
   - LH/LL;
   - BOS;
   - CHoCH;
   - retest;
   - range high / range low;
   - premium / discount zone.
2. Trend:
   - EMA 20/50/100/200;
   - pente EMA;
   - alignement M15/H1/H4/D1;
   - prix au-dessus ou sous EMA 50/200.
3. Momentum:
   - RSI7/RSI14;
   - MACD;
   - divergence RSI/prix;
   - acceleration/deceleration.
4. Volatility:
   - ATR14;
   - ATR percentile;
   - range du jour vs ATR;
   - compression/expansion;
   - volume spike.
5. Levels:
   - high/low du jour;
   - high/low veille;
   - open;
   - Asia/London/NY high/low;
   - VWAP si disponible;
   - pivots P/R1/R2/S1/S2.
6. Liquidity:
   - sweep de high/low recent;
   - fausse cassure;
   - retour dans range;
   - distance au prochain niveau.

## Statuts

- `WATCH_BUY`: setup haussier en preparation, trigger non confirme.
- `BUY`: trigger haussier confirme, invalidation claire, RR acceptable et Preflight non bloquant.
- `WATCH_SELL`: setup baissier en preparation, trigger non confirme.
- `SELL`: trigger baissier confirme, invalidation claire, RR acceptable et Preflight non bloquant.
- `WAIT`: range sale, contradiction forte, volatilite anormale, source bloquante ou prix trop loin.

## Regles produit

- Un score technique seul ne suffit jamais.
- Pas de `BUY` ou `SELL` sans trigger, invalidation et niveau.
- `WATCH_*` n'est pas un trade.
- La charte utilisateur principale doit etre TradingView.
- Le Chart Store sert au calcul et a l'Inspector.
- Elliott ne doit pas etre utilise.

## Phase 23 Contract

### Role

Produire une decision technique auditable sans Elliott.

### Inputs

- ChartStore;
- indicateurs techniques;
- niveaux;
- confirmations cross-market;
- Preflight status;
- contexte de volatilite.

### Outputs

- status technique;
- structure;
- trigger;
- invalidation;
- entry zone;
- SL;
- TP1/TP2/TP3;
- raisons;
- contradictions.

### Methodologie

1. Verifier Preflight et Chart Store.
2. Determiner la structure: trend, breakout, range, pullback ou reversal.
3. Calculer trend, momentum, volatilite et niveaux.
4. Verifier confirmations inter-marches.
5. Produire `WATCH`, `BUY`, `SELL` ou `WAIT`.
6. Refuser tout trade sans trigger/invalidation/RR.

### Limites

- Ne pas predire la direction sans trigger.
- Ne pas remplacer le Risk Manager.
- Ne pas utiliser Elliott.
- Ne pas cacher une contradiction macro/geopolitique.

### Bons exemples

- `WATCH_SELL: range high rejete, MACD baisse, trigger cloture M15 sous support, DXY doit rester ferme.`
- `WAIT: prix au milieu du range, ATR faible et DXY/US10Y contradictoires.`

### Mauvais exemples

- `BUY parce que score technique 61/100.`
- `SELL sans niveau d'invalidation.`
- `Vague 3 commence.`
