from __future__ import annotations

import json
import sys
import traceback
from http.server import BaseHTTPRequestHandler
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlparse

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from xauusd_agent import (  # noqa: E402
    TradeRecommendation,
    align_proxy_points_to_spot,
    analyze_market,
    build_executive_summary,
    build_fundamental_recommendation,
    build_payload,
    build_technical_recommendation,
    fetch_investing_xauusd_snapshot,
    fetch_news,
    fetch_symbol_snapshot,
    fetch_technical_timeframes,
    iso_now,
)


def fallback_technical_recommendation(price: float, change_pct: float) -> TradeRecommendation:
    verdict = "BUY" if change_pct >= 0 else "SELL"
    risk_unit = max(price * 0.002, 8.0)

    if verdict == "BUY":
        stop_loss = price - risk_unit
        take_profit_1 = price + risk_unit
        take_profit_2 = price + (risk_unit * 2)
    else:
        stop_loss = price + risk_unit
        take_profit_1 = price - risk_unit
        take_profit_2 = price - (risk_unit * 2)

    return TradeRecommendation(
        mode="Technique",
        verdict=verdict,
        score=50,
        summary=(
            "Lecture technique reduite: les timeframes complets ne sont pas encore disponibles "
            "sur cette requete, donc le signal reste prudent."
        ),
        reasons=[
            "Fallback technique base sur le mouvement spot court terme.",
            "Attendre le chargement complet pour confirmer EMA, RSI, MACD et volumes.",
        ],
        stop_loss=stop_loss,
        take_profit_1=take_profit_1,
        take_profit_2=take_profit_2,
        source_note="Fallback web lorsque la recuperation multi-timeframes prend trop longtemps.",
    )


def build_cloud_payload(mode: str = "quick", top_news: int = 8) -> dict[str, Any]:
    warnings: list[str] = []

    gold = fetch_investing_xauusd_snapshot(include_historical=mode == "full")
    dxy = fetch_symbol_snapshot("DX-Y.NYB", "US Dollar Index", interval="1d", data_range="1mo")
    us10y = fetch_symbol_snapshot("^TNX", "US 10Y", interval="1d", data_range="1mo")

    news = []
    if mode == "full":
        try:
            news = fetch_news(top_news)
        except Exception as exc:  # pragma: no cover - network branch
            warnings.append(f"Actualites indisponibles temporairement: {exc}")

    analysis = analyze_market(gold, dxy, us10y, news)
    geopolitical_analysis = analysis.geopolitical

    technical_readings = []
    try:
        technical_readings, proxy_price, points_5m = fetch_technical_timeframes()
        gold.intraday_points = align_proxy_points_to_spot(points_5m, gold.price)
        technical_recommendation = build_technical_recommendation(gold, technical_readings, proxy_price)
    except Exception as exc:  # pragma: no cover - network branch
        warnings.append(f"Technique multi-timeframes indisponible temporairement: {exc}")
        technical_recommendation = fallback_technical_recommendation(gold.price, gold.change_pct)

    atr_15m = next(
        (reading.atr14 for reading in technical_readings if reading.timeframe == "15m"),
        max(gold.price * 0.002, 8.0),
    )
    fundamental_recommendation = build_fundamental_recommendation(gold, dxy, us10y, analysis, atr_15m)
    executive_summary = build_executive_summary(
        fundamental_recommendation,
        technical_recommendation,
        geopolitical_analysis,
    )

    payload = build_payload(
        gold,
        dxy,
        us10y,
        news,
        analysis,
        geopolitical_analysis=geopolitical_analysis,
        fundamental_recommendation=fundamental_recommendation,
        technical_recommendation=technical_recommendation,
        technical_timeframes=technical_readings,
    )
    payload["executive_summary"] = executive_summary
    payload["cloud"] = {
        "mode": mode,
        "warnings": warnings,
        "refreshed_at": iso_now(),
    }
    return payload


class handler(BaseHTTPRequestHandler):
    def do_OPTIONS(self) -> None:
        self.send_response(204)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()

    def do_GET(self) -> None:
        query = parse_qs(urlparse(self.path).query)
        requested_mode = (query.get("mode", ["quick"])[0] or "quick").lower()
        mode = "full" if requested_mode == "full" else "quick"

        try:
            payload = build_cloud_payload(mode=mode)
            self._send_json(200, payload)
        except Exception as exc:  # pragma: no cover - serverless runtime branch
            self._send_json(
                503,
                {
                    "error": "Service temporairement indisponible",
                    "message": str(exc),
                    "generated_at": iso_now(),
                    "trace": traceback.format_exc(limit=2),
                    "note": "Rechargez la page. Les sources marche peuvent parfois refuser une requete.",
                },
            )

    def _send_json(self, status_code: int, payload: dict[str, Any]) -> None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status_code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Cache-Control", "no-store, max-age=0")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)
