---
name: aureum-data-preflight
description: Verifications de sources avant analyse v3.0: availability, freshness, quality, fallback et mode degrade.
category: data
---

# Aureum Data Preflight

## But

Verifier les sources avant que les agents et l'orchestrateur produisent une decision.

Le terminal ne doit pas afficher une conclusion forte si la source bloquante de prix est absente/stale ou si la qualite globale devient trop faible. Une source secondaire stale doit degrader la confiance, pas forcer `WAIT` a elle seule.

## Sources a verifier

- Prix XAU/USD principal;
- IG Weekend Gold si contexte week-end;
- DXY;
- US yields FRED;
- real yield FRED;
- WTI/Brent;
- news feeds;
- Event Facts;
- CFTC COT;
- WGC/GLD/IAU ETF flows;
- Chart Store OHLC quand disponible;
- Trade Ledger;
- Audit Log.

## Status globaux

- `READY`: tout est exploitable.
- `USABLE`: quelques sources secondaires manquent.
- `DEGRADED`: source importante stale ou weak; dashboard consultable et trade encore possible si aucun blocage dur.
- `NO_TRADE_DATA`: le dashboard peut afficher, mais ne doit pas creer de trade.
- `OFFLINE`: sources critiques absentes.

## Sortie SourceQuality

```text
source_id
source_name
tier
last_update
freshness_seconds
status
is_critical
missing
stale
confidence
message_for_inspector
```

## Regles UI

- Dashboard principal: afficher seulement le statut utile.
- Inspector: afficher details complets.
- Decision: expliquer seulement les sources qui changent la decision.

## Exemple

```text
Status: DEGRADED.
Cause: prix XAU exploitable, WGC ETF stale, Google News weak.
Impact: signal possible avec confiance reduite; Inspector affiche les warnings.
```

## Tests

- prix principal missing/stale -> `NO_TRADE_DATA` ou `SOURCE_STALE`;
- source secondaire missing/stale -> `DEGRADED` ou `USABLE`;
- OHLC absent -> TechnicalDecisionEngine `WAIT` ou `NO_TRADE`;
- news weak -> degrade NewsFact confidence.

## Phase 23 Contract

### Role

Verifier les donnees avant tout scoring, affichage decisionnel ou creation de TradePlan.

### Inputs

- SourceRegistry;
- snapshots prix/macro/news/flows;
- timestamps;
- seuils freshness;
- criticite de chaque source.

### Outputs

- `SourceQuality`;
- statut global data;
- blockers trade;
- messages Inspector.

### Methodologie

1. Verifier presence source.
2. Verifier freshness.
3. Verifier coherence simple entre sources.
4. Degrader confidence si une source est faible.
5. Bloquer trade seulement si une source bloquante manque/stale ou si le score data devient trop faible.

### Limites

- Preflight ne remplace pas l'analyse.
- Preflight ne corrige pas les donnees.
- Une source secondaire absente ne doit pas cacher tout le dashboard.

### Bons exemples

- `NO_TRADE_DATA: prix XAU stale 11 min, trade bloque.`
- `DEGRADED: WGC ETF stale, decision intraday disponible avec confidence reduite.`

### Mauvais exemples

- `Tout est OK` sans source ni timestamp.
- Continuer un trade si le prix principal est stale.
