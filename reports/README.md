# Reports

Ce dossier est conserve dans le repo pour que la structure soit presente apres un clone.

Les fichiers suivants sont generes localement et ignores par Git:

- `xauusd_dashboard.html`: dashboard HTML exporte.
- `xauusd_data.json`: payload structure complet.
- `xauusd_report.md`: rapport lisible en Markdown.
- `trade_ledger.jsonl`: Trade Plans historises, append-only.
- `audit_log.jsonl`: snapshots d'audit decision/sources/agents/trades, append-only.
- `chart_store_cache.json`: cache OHLC local.
- `dashboard_server.log`: log local du serveur.
- `v3/daily_report.md`: rapport complet du dernier snapshot.
- `v3/signal_report.md`: rapport court du signal live.
- `v3/trade_report.md`: historique et statistiques Trade Ledger.
- `v3/post_mortem_report.md`: post-mortem des trades clos.
- `v3/news_audit.md`: audit news/Event Facts.
- `v3/source_quality_audit.md`: audit de fraicheur et qualite des sources.
- `v3/replay_report.md` et `v3/replay_report.json`: replay v3.
- `v3/index.html`: index local des exports v3.

`trade_ledger.jsonl` et `audit_log.jsonl` ne doivent pas etre modifies manuellement pendant que le dashboard tourne.
Ils peuvent etre supprimes lorsque le projet doit repartir sur un etat propre apres changement majeur de moteur.

```bash
./Lancer-Agent-XAUUSD.command
python xauusd_agent.py --replay --replay-output reports/v3/replay_report.md
```
