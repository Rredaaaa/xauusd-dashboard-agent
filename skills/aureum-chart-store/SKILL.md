---
name: aureum-chart-store
description: Specification Chart Store OHLC multi-timeframe pour alimenter Technical et Elliott sans dependre d'un broker.
category: data
---

# Aureum Chart Store

## But

Donner une vraie charte aux agents techniques, surtout Elliott.

Elliott ne doit pas compter des vagues sur quelques closes. Il a besoin de OHLC multi-timeframe.

## Timeframes requis

- M5: timing d'entree;
- M15: structure intraday;
- H1: sous-vagues principales;
- H4: vague superieure;
- D1: tendance de fond.

## Format bougie

```text
timestamp
open
high
low
close
volume
source
timeframe
fetched_at
quality_flags
```

## Regles produit

- Ne pas mentionner de broker dans l'interface.
- Le dashboard principal affiche "Charte Elliott: M15/H1/H4" et pas la plomberie source.
- Les details source vont dans Inspector.
- Si historique insuffisant: Elliott retourne `UNCLEAR` et non scorant.

## Qualite

Le Chart Store doit detecter:
- gaps;
- bougies manquantes;
- timestamp incoherent;
- timezone;
- doublons;
- dernier update trop vieux;
- source indisponible.

## Resampling

Si source M1 disponible:
- construire M5/M15/H1/H4/D1 localement;
- conserver OHLC correct:
  - open premier;
  - high max;
  - low min;
  - close dernier;
  - volume somme si disponible.

## Inspector

Afficher:
- timeframes disponibles;
- nombre de bougies;
- dernier timestamp;
- freshness;
- source quality;
- gaps detectes.

## Tests

- resampling M1 -> M5;
- detection gap;
- stale chart;
- OHLC incomplet;
- fallback source;
- Elliott refuse si moins de bougies minimales.
