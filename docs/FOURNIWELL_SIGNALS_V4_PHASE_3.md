# Fourniwell Signals v4 - Phase 3

Date: 2026-05-13

## Objectif

Remplacer le flux news bruyant par un flux exploitable: sources meilleures, filtrage agressif, tri par publication reelle et affichage uniquement des titres recents avec impact XAU/USD.

## Livrables

- Ajout des sources officielles:
  - White House;
  - Federal Reserve speeches;
  - Federal Reserve monetary policy;
  - BLS;
  - Treasury;
  - WGC.
- Ajout des canaux rapides:
  - AP business;
  - AP top news;
  - CNBC markets;
  - recherches ciblees Reuters, Bloomberg, AP et CNBC via Google News RSS.
- Filtrage amont:
  - rejet MSN, FXEmpire, LiteFinance, Moomoo, CoinMarketCap, Traders Union, Startup Fortune, Barchart, Benzinga;
  - rejet forecasts, predictions, outlook, next week, next month, analysis today, technical analysis, how to trade;
  - rejet des titres trop vieux: 48h pour medias, 7 jours pour officiel;
  - rejet des headlines neutres hors sources fortes.
- Deduplication renforcee:
  - cle normalisee;
  - prefixe commun;
  - similarite Jaccard >= 0.65.
- News Flow trie par publication reelle, puis impact et tier source.
- Affichage conserve:
  - titre;
  - source;
  - heure;
  - resume concret;
  - impact XAU/USD;
  - badge bullish/bearish.

## Impact utilisateur

La page News ne doit plus afficher les vieux articles d'opinion ou les predictions generiques. Si aucune headline exploitable n'est disponible, le dashboard affiche clairement qu'aucune news bullish ou bearish recente n'est exploitable.

## Verification

- `python3 -m py_compile xauusd_agent.py`
- `python3 -m unittest discover tests`

