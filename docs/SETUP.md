# Installation et Lancement

Ce guide permet a un nouveau collaborateur de lancer le projet depuis zero sur Windows.

## Prerequis

- Python 3.11 ou plus recent.
- Git.
- Un navigateur web.
- Connexion internet pour les sources marche.

## Installation

Depuis le dossier du projet:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
Copy-Item .env.example .env
```

La cle OpenAI est optionnelle. Le dashboard fonctionne sans elle.

## Lancement Simple

Double-cliquer sur:

```text
Lancer-Agent-XAUUSD.bat
```

Le script:

- ferme les anciennes instances du serveur dashboard;
- lance un serveur local sur `http://127.0.0.1:8787/`;
- ouvre le navigateur.

## Lancement Manuel

```powershell
python .\xauusd_agent.py --serve-dashboard --quiet --host 127.0.0.1 --port 8787 --live-refresh-seconds 10 --full-refresh-seconds 60 --save .\reports\xauusd_report.md --data-json .\reports\xauusd_data.json --dashboard .\reports\xauusd_dashboard.html
```

## Generation Sans Serveur

```powershell
python .\xauusd_agent.py --quiet --save .\reports\xauusd_report.md --data-json .\reports\xauusd_data.json --dashboard .\reports\xauusd_dashboard.html
```

## Tests

```powershell
python -B -m unittest discover -s tests -v
```
