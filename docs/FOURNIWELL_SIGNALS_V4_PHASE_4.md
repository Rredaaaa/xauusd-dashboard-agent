# Fourniwell Signals v4 - Phase 4

Date: 2026-05-13

## Objectif

Rendre chaque agent plus utile, mesurable et moins bruyant avant les phases suivantes de reaction news, niveaux de trade et strategies.

## Livrables

- `PriceAgent` devient `PriceActionAgent`.
  - lecture range journalier;
  - niveau psychologique le plus proche;
  - pivots Camarilla simples;
  - etat prix: breakout, breakdown, pullback, range, consolidation, reversal;
  - score et confidence dynamiques.
- `TechnicalAgent` conserve le cap confidence 85, baisse sa confidence si:
  - pas de trigger exploitable;
  - contradictions intra-timeframe.
- `MacroAgent` expose:
  - fraicheur FRED;
  - preuves DXY, DGS10, DGS2, T10YIE, DFII10 quand disponibles;
  - veto high-impact deja actif depuis Phase 1.
- `GeopoliticalOilShockAgent` devient directionnel:
  - Hormuz / Oil Shock -> SELL;
  - Safe-Haven Gold -> BUY;
  - De-escalation / Oil Relief -> SELL;
  - Dollar Liquidity Squeeze -> SELL;
  - Normal Macro -> NEUTRAL.
- `SentimentNewsAgent` pondere par source tier et fraicheur, et reste neutralise si le flux est faible ou ancien.
- `CorrelationAgent` affiche un verdict net confirmations/contradictions et une confidence dynamique.
- `FlowPositioningAgent` ajoute la divergence COT/ETF.
- `EventFactsAgent` ne score que les faits qualifies:
  - tier <= 2;
  - confidence >= 60;
  - pas opinion;
  - pas rumeur.
- `TrumpPoliticalStatementsAgent` devient directionnel selon theme et score.
- `RiskManagerAgent` lit le ledger, expose RR TP1, exposition active, losses recentes et peut retourner `OK`, `CAUTION` ou `BLOCK`.

## Compatibilite

`PriceAgent` reste accepte comme alias de configuration et dans quelques donnees historiques, mais le produit actif affiche `PriceActionAgent`.

## Verification

- `python3 -m py_compile xauusd_agent.py`
- `python3 -m unittest discover tests`

