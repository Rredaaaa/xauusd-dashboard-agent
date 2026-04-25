# Agent XAUUSD Dashboard

Agent local pour suivre `XAU/USD`, construire un dashboard HTML live et produire un rapport d'aide a la lecture du marche.

Le projet est pense pour etre partage et developpe a deux. Les fichiers de code, documentation, tests et lanceurs sont suivis par Git. Les fichiers generes dans `reports/` restent locaux pour eviter les conflits a chaque lancement.

## Fonctionnalites

- Prix spot `XAU/USD` depuis Investing.com.
- Dashboard local live sur `http://127.0.0.1:8787/`.
- Chandeliers intraday avec ligne de prix live.
- Analyse fondamentale, technique et geopolitique.
- Confirmations gratuites locales: 10Y reel FRED, USD/JPY, silver, GVZ et VIX.
- Mode event volatilite/volume pour signaler les regimes dangereux.
- Scores `/100`, verdict intraday, `SL`, `TP1`, `TP2`.
- Rapport Markdown et payload JSON.
- Mode de repli sur le dernier snapshot si une source externe retourne une erreur temporaire.

## Demarrage Rapide

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
Copy-Item .env.example .env
```

Lancer le dashboard:

```powershell
.\Lancer-Agent-XAUUSD.bat
```

Surveillance continue:

```powershell
.\Surveiller-Agent-XAUUSD-15min.bat
```

Execution console:

```powershell
python .\xauusd_agent.py
```

Generer les artefacts:

```powershell
python .\xauusd_agent.py --quiet --save .\reports\xauusd_report.md --data-json .\reports\xauusd_data.json --dashboard .\reports\xauusd_dashboard.html
```

## Structure

```text
.
|-- xauusd_agent.py                 # Agent, dashboard, serveur live et analyses
|-- Lancer-Agent-XAUUSD.bat         # Lance le dashboard live
|-- Surveiller-Agent-XAUUSD-15min.bat
|-- requirements.txt
|-- .env.example
|-- tests/
|   `-- test_xauusd_agent.py
|-- docs/
|   |-- ARCHITECTURE.md
|   |-- COLLABORATION.md
|   `-- SETUP.md
`-- reports/
    |-- README.md
    `-- .gitkeep
```

## Configuration IA Optionnelle

La synthese IA est optionnelle. Ne publiez jamais `.env`.

```env
OPENAI_API_KEY=your_openai_api_key_here
OPENAI_MODEL=your_model_name_here
```

## Tests

```powershell
python -B -m unittest discover -s tests -v
```

## Collaboration

Avant de modifier:

```powershell
git pull
```

Apres modification:

```powershell
git status
git add .
git commit -m "Description courte"
git push
```

Voir [docs/COLLABORATION.md](docs/COLLABORATION.md) pour le workflow conseille entre Maroc et France.

## Limites

- Les scores sont heuristiques: ils aident a lire le marche, ils ne garantissent pas un trade gagnant.
- Les bougies multi-timeframes utilisent un proxy futures COMEX pour obtenir OHLC/volume puis sont alignees sur le spot.
- Les sources externes peuvent temporairement retourner des erreurs HTTP. Le dashboard garde alors le dernier snapshot disponible.
- Ce projet ne fournit pas de conseil financier personnalise.
