# Aureum Flux Terminal

Aureum Flux Terminal est un dashboard local pour lire `XAU/USD` en intraday. Il collecte les prix, sources macro, geopolitique, flux, correlations et agents passifs, puis affiche une decision live `BUY`, `SELL` ou `WAIT` avec niveaux de risque.

A partir de la v3.0, deux statuts intermediaires `WATCH_BUY` et `WATCH_SELL` seront ajoutes pour signaler les setups en surveillance sans forcer un trade. La roadmap v3.0 retire aussi Elliott du parcours utilisateur et le remplace par un `TechnicalDecisionEngine` base sur structure, indicateurs, niveaux, volatilite et confirmations.

Le terminal ne donne pas un conseil financier personnalise. Il sert a structurer la lecture du marche, verifier les sources et historiser les plans de trade quand le Quality Gate l'autorise.

Etat roadmap:
- v2.0 est stabilisee apres la Phase 18;
- la suite officielle est la v3.0, documentee dans [Plan v3.0](docs/AUREUM_FLUX_TERMINAL_V3_PLAN.md).

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

## Lancer sur Windows / RDP

```powershell
.\Lancer-Agent-XAUUSD.bat
```

Generation sans serveur:

```powershell
python .\xauusd_agent.py --quiet --save .\reports\xauusd_report.md --data-json .\reports\xauusd_data.json --dashboard .\reports\xauusd_dashboard.html
```

## Ce que le dashboard affiche

- `Dashboard`: prix live, decision globale, SL/TP, Orchestrateur v2, Trade Tracker.
- `Market`: spot, IG Weekend Gold, vraie charte TradingView cible v3, correlations, regime petrole/politique, COT et ETF flows.
- `Decision`: pourquoi le terminal dit `BUY`, `SELL` ou `WAIT`.
- `Technical`: EMA, RSI, MACD, volume, Chart Store OHLC M5/M15/H1/H4/D1, puis Technical Decision Engine v3. Elliott doit etre retire du dashboard en Phase 27A.
- `Macro`: DXY, FRED DGS10/DGS2/T10YIE/DFII10, calendrier Fed/BEA.
- `Geopolitics & Flows`: faits geopolitique, Trump/White House, news sourcees, flows.
- `Inspector`: audit des sources, Preflight, Chart Store, agents, gates, trades et qualite data.
- `Reports`: exports Markdown/JSON et recapitulatif complet.

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

## Documentation

- [Installation et lancement](docs/SETUP.md)
- [Guide utilisateur](docs/USER_GUIDE.md)
- [Sources et scoring](docs/SOURCES_AND_SCORING.md)
- [Architecture](docs/ARCHITECTURE.md)
- [Plan v2.0](docs/AUREUM_FLUX_TERMINAL_V2_PLAN.md)
- [Plan v3.0](docs/AUREUM_FLUX_TERMINAL_V3_PLAN.md)
- [Skills Aureum pour reprise Claude](skills/README.md)

## Tests

```bash
python3 -m py_compile xauusd_agent.py
python3 -m unittest discover -s tests -v
```

## Limites importantes

- Les scores sont des aides a la decision, pas une certitude de marche.
- Une source peut etre absente, stale ou contradictoire.
- IG Weekend Gold est un proxy week-end, distinct du spot classique.
- Les bougies intraday internes utilisent un proxy futures COMEX aligne sur le spot; la v3.0 doit afficher une vraie charte TradingView dans le dashboard principal.
- Elliott est archive dans la roadmap v3.0 tant qu'il n'existe pas de moteur robuste; il ne doit plus etre presente comme preuve de decision.
- Aucun trade ne doit etre pris sans controle humain du contexte, du spread, de l'heure et du risque.
