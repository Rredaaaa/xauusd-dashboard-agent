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

`trade_ledger.jsonl` et `audit_log.jsonl` ne doivent pas etre modifies manuellement pendant que le dashboard tourne.
Ils peuvent etre supprimes lorsque le projet doit repartir sur un etat propre apres changement majeur de moteur.

```bash
./Lancer-Agent-XAUUSD.command
```
