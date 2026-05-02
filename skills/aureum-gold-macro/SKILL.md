---
name: aureum-gold-macro
description: Methodologie macro gold: dollar, taux reels, Fed, inflation et calendrier economique.
category: macro
---

# Aureum Gold Macro

## Role

MacroAgent explique le contexte dollar/taux/Fed qui influence XAU/USD.

Il ne doit pas produire une phrase vague du type:

> Lecture fondamentale positive.

Il doit expliquer le mecanisme.

## Inputs

- DXY;
- US 10Y nominal;
- US 10Y reel FRED DFII10;
- DGS10/DGS2;
- T10YIE;
- calendrier Fed/FOMC;
- BEA/CPI/PCE/NFP si disponibles;
- CME FedWatch lien officiel si utilise.

## Regles gold

- Taux reels en baisse: soutien gold.
- DXY en baisse: soutien gold.
- Taux reels en hausse: pression gold.
- DXY en hausse: pression gold.
- Oil shock peut augmenter inflation, taux, dollar et donc peser sur gold.
- Risk-off peut soutenir gold, mais si dollar capte la liquidite, effet mixte.

## Sortie attendue

```text
Fait macro: ...
Mecanisme: ...
Confirmation marche: ...
Impact XAU/USD: ...
Risque: ...
Action: ...
```

## Exemple

```text
DXY baisse et le 10Y reel FRED ne monte pas. Cela reduit le cout d'opportunite de l'or. Impact XAU/USD: soutien modere. Action: ce facteur confirme un biais BUY seulement si la technique ne contredit pas.
```

## Pieges

- Ne pas dire "macro positive" sans DXY/taux.
- Ne pas faire de FedWatch invente si la source n'est pas accessible.
- Ne pas ignorer calendrier macro imminent.
- Ne pas utiliser Yahoo `^TNX` comme officiel si FRED disponible.

## Tests

- DXY down + real yield down -> bullish;
- DXY up + real yield up -> bearish;
- oil shock + DXY up -> pressure/liquidity risk;
- stale FRED -> degrade confidence.
