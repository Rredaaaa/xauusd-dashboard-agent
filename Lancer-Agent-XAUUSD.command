#!/bin/zsh
set -e

cd "$(dirname "$0")"

if [ ! -d ".venv" ]; then
  echo "Creation de l'environnement virtuel .venv..."
  /opt/homebrew/bin/python3.12 -m venv .venv 2>/dev/null || python3 -m venv .venv
fi

echo "Activation de .venv..."
source .venv/bin/activate

echo "Installation / verification des dependances..."
python -m pip install -r requirements.txt

echo "Lancement du dashboard XAUUSD..."
echo "URL: http://127.0.0.1:8787/"

python xauusd_agent.py \
  --serve-dashboard \
  --quiet \
  --host 127.0.0.1 \
  --port 8787 \
  --live-refresh-seconds 10 \
  --full-refresh-seconds 60 \
  --save reports/xauusd_report.md \
  --data-json reports/xauusd_data.json \
  --dashboard reports/xauusd_dashboard.html
