# Agent XAUUSD

Ce projet cree un agent simple qui :

- recupere le spot `XAU/USD` depuis Investing.com
- suit aussi le `DXY` et le rendement US 10Y
- collecte des actualites recentes liees a l'or, au dollar et a la Fed
- calcule un biais heuristique haussier / baissier / neutre
- peut ajouter une synthese IA si vous fournissez `OPENAI_API_KEY` et `OPENAI_MODEL`

## Installation

```powershell
python -m venv .venv
.\\.venv\\Scripts\\Activate.ps1
pip install -r requirements.txt
Copy-Item .env.example .env
```

Ensuite, editez `.env` seulement si vous voulez activer la synthese IA.

## Lancer l'agent

Double-clic sans terminal charge :

```powershell
.\Lancer-Agent-XAUUSD.bat
```

Le batch genere automatiquement :

- `reports\xauusd_dashboard.html`
- `reports\xauusd_data.json`
- `reports\xauusd_report.md`

Puis il ouvre le dashboard HTML dans votre navigateur.

Execution simple en console :

```powershell
python .\\xauusd_agent.py
```

Generer seulement le dashboard HTML :

```powershell
python .\\xauusd_agent.py --quiet --dashboard .\\reports\\xauusd_dashboard.html --data-json .\\reports\\xauusd_data.json --save .\\reports\\xauusd_report.md
```

Sauvegarder le rapport dans un fichier :

```powershell
python .\\xauusd_agent.py --save .\\reports\\xauusd_report.md
```

Mode surveillance toutes les 15 minutes :

```powershell
.\Surveiller-Agent-XAUUSD-15min.bat
```

Ce mode met a jour les fichiers dans `reports\` et le dashboard HTML se recharge automatiquement dans le navigateur.

Sortie JSON exploitable par un autre systeme :

```powershell
python .\\xauusd_agent.py --json
```

## Ce que fait l'agent

1. Il lit le spot `XAU/USD` depuis Investing.com.
2. Il recupere les headlines via Google News RSS.
3. Il lit aussi le `DXY` et le 10 ans US pour le contexte macro.
4. Il produit un score heuristique.
5. Si OpenAI est configure, il demande une synthese concise en francais.

## Limites importantes

- Le prix de l'or vient d'Investing.com, tandis que certains indicateurs macro secondaires restent alimentes par Yahoo Finance.
- Les headlines ne remplacent pas un calendrier macro ou un flux temps reel institutionnel.
- Le score heuristique est une aide a la lecture, pas un signal garanti.
- Ce projet ne fournit pas de conseil financier personnalise.
