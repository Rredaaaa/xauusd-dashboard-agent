# Installation et lancement

Ce guide explique comment lancer Fourniwell Signals sur Mac. Le projet s'appelait auparavant Aureum Flux Terminal.

## Prerequis

- Python 3.11 ou plus recent.
- Git.
- Un navigateur web.
- Connexion internet pour les sources marche.

La cle OpenAI est optionnelle. Sans cle, le dashboard fonctionne avec le moteur local et les agents heuristiques.

## Installation Mac

Depuis le dossier du projet:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
cp .env.example .env
```

Lancer avec le fichier Mac:

```bash
./Lancer-Agent-XAUUSD.command
```

Si macOS bloque le fichier:

```bash
chmod +x Lancer-Agent-XAUUSD.command
./Lancer-Agent-XAUUSD.command
```

Lancement manuel Mac:

```bash
source .venv/bin/activate
python xauusd_agent.py --serve-dashboard --quiet --host 127.0.0.1 --port 8787 \
  --live-refresh-seconds 10 \
  --full-refresh-seconds 60 \
  --save reports/xauusd_report.md \
  --data-json reports/xauusd_data.json \
  --dashboard reports/xauusd_dashboard.html
```

URL locale:

```text
http://127.0.0.1:8787/
```

## Generation sans serveur

```bash
python xauusd_agent.py --quiet --save reports/xauusd_report.md --data-json reports/xauusd_data.json --dashboard reports/xauusd_dashboard.html
```

## Settings locaux

Creer le fichier de configuration local:

```bash
python xauusd_agent.py --init-settings
```

Le fichier cree est:

```text
config/aureum_settings.json
```

Il est ignore par Git. Le modele suivi est `config/aureum_settings.example.json`.

Parametres principaux:

- `scoring_mode`: `aggressive_controlled` ou `conservative`;
- `trade_threshold`: score minimal pour transformer un signal en TradePlan;
- `minimum_risk_reward`: RR minimal sur TP1;
- `cooldown_minutes`: anti-doublon Trade Ledger;
- `active_agents`: agents decisionnels pris en compte par le Trade Gate.

## Replay v3

Generer le replay depuis les snapshots locaux:

```bash
python xauusd_agent.py --replay --replay-output reports/v3/replay_report.md
```

Le replay utilise `reports/trade_ledger.jsonl` et `reports/audit_log.jsonl`.

## Tests

```bash
python3 -m py_compile xauusd_agent.py
python3 -m unittest discover -s tests -v
```

## Fichiers locaux

Le dossier `reports/` contient les exports locaux:

- `xauusd_report.md`
- `xauusd_data.json`
- `xauusd_dashboard.html`
- `trade_ledger.jsonl`
- `audit_log.jsonl`
- `v3/`: rapports v3 generes localement.

Ces fichiers ne sont pas pousses sur GitHub.
