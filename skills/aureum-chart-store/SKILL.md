---
name: aureum-chart-store
description: Specification Chart Store OHLC multi-timeframe pour alimenter Technical Decision Engine et Inspector sans dependre d'un broker.
category: data
---

# Aureum Chart Store

## But

Fournir une base OHLC multi-timeframe auditable aux agents techniques.

Le Chart Store n'est pas la charte utilisateur principale.
La v3.0 doit afficher TradingView dans le dashboard principal et garder Chart Store en Inspector pour verifier qualite, gaps, freshness et fallback technique.

## Timeframes requis

- M5: timing d'entree;
- M15: structure intraday;
- H1: structure intraday principale;
- H4: structure superieure;
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
- Le dashboard principal affiche TradingView.
- Le Chart Store est affiche dans Inspector ou comme fallback diagnostic, pas comme charte principale.
- Les details source vont dans Inspector.
- Si historique insuffisant: le Technical Decision Engine retourne `WAIT` ou `NO_TRADE`, pas une conclusion directionnelle forte.

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
- Technical Decision Engine refuse si moins de bougies minimales.

## Phase 23 Contract

### Role

Fournir une base OHLC multi-timeframe fiable pour Technical et l'Inspector.

### Inputs

- Bougies source M1/M5/M15/H1/H4/D1;
- metadata source, timezone, fetched_at;
- seuils freshness et historique minimum.

### Outputs

- ChartStore par timeframe;
- quality flags;
- dernier timestamp fiable;
- statut `READY`, `STALE`, `INSUFFICIENT_HISTORY` ou `OFFLINE`.

### Methodologie

1. Charger les bougies.
2. Normaliser timezone et timestamps.
3. Dedoublonner.
4. Detecter gaps et stale.
5. Resampler si necessaire.
6. Exposer seulement les timeframes valides aux agents.

### Limites

- Ne pas inventer de bougies manquantes.
- Ne pas mentionner de broker dans l'UI principale.
- Ne pas autoriser une decision technique forte si l'historique minimum manque.

### Bons exemples

- `M15 READY: 480 bougies, dernier update 45s, aucun gap critique.`
- `H1 INSUFFICIENT_HISTORY: 42 bougies, TechnicalDecisionEngine bloque en WAIT.`

### Mauvais exemples

- `Charte OK` sans timeframe ni freshness.
- Afficher Chart Store comme charte principale a la place de TradingView.
