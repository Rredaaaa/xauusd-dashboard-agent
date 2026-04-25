# Architecture

Le projet est actuellement concentre dans `xauusd_agent.py` pour rester simple a lancer sur Windows.

## Modules Logiques

- Collecte marche: prix spot XAU/USD, DXY, 10Y US nominal, 10Y reel FRED DFII10, bougies proxy.
- Confirmations cross-asset gratuites: DXY, 10Y reel FRED, USD/JPY, silver futures, GDX/GDXJ, AUD/USD, USD/CHF, TIP, S&P 500, GVZ et VIX.
- Collecte news: Google News RSS et categories macro/geopolitique/flux.
- Analyse fondamentale: dollar, taux, prix, headlines.
- Analyse technique: EMA 20/50/100/200, RSI7, MACD 5/34/5, volume et alignement multi-timeframe.
- Analyse geopolitique: risk-off, banques centrales, flux physiques, ETF, COT, VIX.
- Mode event: detection gratuite de regime volatil via GVZ, VIX, volume proxy et mouvement court terme.
- Rendu: rapport Markdown, JSON, dashboard HTML.
- Serveur live: `http.server.ThreadingHTTPServer`.

## Fichiers Generes

Le dossier `reports/` recoit:

- `xauusd_dashboard.html`
- `xauusd_data.json`
- `xauusd_report.md`

Ces fichiers sont ignores par Git car ils changent a chaque execution.

## Points D'extension

- Brancher une API OHLC spot XAU/USD plus precise.
- Ajouter une source structuree pour calendrier economique.
- Ajouter une source structuree pour COT, ETF flows et open interest.
- Decomposer `xauusd_agent.py` en package Python si le projet grandit.
