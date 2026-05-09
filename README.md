# Aureum Flux Terminal

Aureum Flux Terminal est un dashboard local pour lire `XAU/USD` en intraday. Il collecte les prix, sources macro, geopolitique, flux, correlations et agents passifs, puis affiche une decision live `BUY`, `SELL`, `WAIT`, `WATCH_BUY`, `WATCH_SELL`, `TRADE_BUY`, `TRADE_SELL` ou `NO_TRADE` avec niveaux de risque.

A partir de la v3.0, `WATCH_BUY` et `WATCH_SELL` signalent les setups en surveillance sans forcer un trade, tandis que `TRADE_BUY` et `TRADE_SELL` exigent validation technique, sources exploitables, invalidation et risk/reward. La roadmap v3.0 retire aussi Elliott du parcours utilisateur et le remplace par un `TechnicalDecisionEngine` base sur structure, indicateurs, niveaux, volatilite et confirmations.

Le terminal ne donne pas un conseil financier personnalise. Il sert a structurer la lecture du marche, verifier les sources et historiser les plans de trade quand le Quality Gate l'autorise.

Etat roadmap:
- la reference officielle est la v3.0, documentee dans [Plan v3.0](docs/AUREUM_FLUX_TERMINAL_V3_PLAN.md);
- le dashboard actif est structure en 5 pages: Desk, Agents, News Flow, Reports et Inspector;
- la Phase 35 corrige l'UX prioritaire: affichage vertical, toggles ON/OFF agents, calendrier macro lisible et resumes news.

## Lancer sur Mac

Depuis le dossier du projet:

```bash
./Lancer-Agent-XAUUSD.command
```

Le dashboard ouvre ou sert:

```text
http://127.0.0.1:8787/
```

Lancement manuel Mac:

```bash
source .venv/bin/activate
python xauusd_agent.py --serve-dashboard --quiet --host 127.0.0.1 --port 8787 \
  --save reports/xauusd_report.md \
  --data-json reports/xauusd_data.json \
  --dashboard reports/xauusd_dashboard.html
```

## Ce que le dashboard affiche

Structure active:

- `Desk`: prix live, chef de file, biais, TradingView, signal locked.
- `Agents`: scoring, poids et positions de tous les agents.
- `News Flow`: informations recentes utiles, triees par date et impact.
- `Reports`: exports, historique de decisions et trades.
- `Inspector`: audit des sources, Preflight, Chart Store, agents, gates, logs et bruit moteur.

Les details internes restent dans `Inspector`. Les pages trader ne doivent pas afficher les chaines marche, textes d'audit, news neutres anciennes ou termes internes.

## Signal live vs Trade Plan

Le signal live peut changer a chaque refresh car le prix, les sources et les agents evoluent.

Un `TradePlan` est different: quand le Quality Gate valide un trade exploitable, le terminal fige l'entree, le SL, les TP, les sources, les agents et la raison de creation dans `reports/trade_ledger.jsonl`. Ce trade historise n'est pas modifie retroactivement par le signal live.

Le scoring distingue maintenant les blocages durs et les warnings. Une source secondaire stale ou une data quality `DEGRADED` reduit la confiance, mais ne doit plus forcer `WAIT` si le prix principal, le risk/reward et les confirmations decisionnelles restent exploitables.

## Fichiers generes

Les fichiers dans `reports/` restent locaux et sont ignores par Git:

- `xauusd_dashboard.html`
- `xauusd_data.json`
- `xauusd_report.md`
- `trade_ledger.jsonl`
- `audit_log.jsonl`
- `v3/`: daily report, signal report, trade report, replay report, news audit et source quality audit.

Le fichier local `config/aureum_settings.json` permet d'ajuster les seuils sans modifier le code. Un exemple suivi par Git est disponible dans `config/aureum_settings.example.json`.

## Replay et settings

Initialiser les settings locaux:

```bash
python xauusd_agent.py --init-settings
```

Generer un replay depuis `trade_ledger.jsonl` et `audit_log.jsonl`:

```bash
python xauusd_agent.py --replay --replay-output reports/v3/replay_report.md
```

## Documentation

- [Installation et lancement](docs/SETUP.md)
- [Guide utilisateur](docs/USER_GUIDE.md)
- [Sources et scoring](docs/SOURCES_AND_SCORING.md)
- [Architecture](docs/ARCHITECTURE.md)
- [Plan v3.0](docs/AUREUM_FLUX_TERMINAL_V3_PLAN.md)
- [Checklist QA v3.0](docs/V3_QA_CHECKLIST.md)
- [Skills Aureum pour reprise assistant](skills/README.md)

## Tests

```bash
python3 -m py_compile xauusd_agent.py
python3 -m unittest discover -s tests -v
```

## Limites importantes

- Les scores sont des aides a la decision, pas une certitude de marche.
- Une source peut etre absente, stale ou contradictoire.
- IG Weekend Gold est un proxy week-end, distinct du spot classique.
- La charte principale utilisateur est TradingView; les bougies internes Chart Store restent un diagnostic de donnees.
- Elliott a ete retire du code actif et des skills; il n'est plus presente comme preuve de decision.
- Aucun trade ne doit etre pris sans controle humain du contexte, du spread, de l'heure et du risque.
