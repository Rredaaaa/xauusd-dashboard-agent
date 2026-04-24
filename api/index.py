from __future__ import annotations

import sys
import traceback
from pathlib import Path
from typing import Literal

from fastapi import FastAPI, Query
from fastapi.responses import HTMLResponse, JSONResponse

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from api.xauusd import build_cloud_payload  # noqa: E402
from xauusd_agent import iso_now  # noqa: E402

app = FastAPI(title="XAUUSD Dashboard Agent")


def dashboard_file():
    for path in (Path(__file__).with_name("dashboard.html"), ROOT / "public" / "index.html"):
        if path.exists():
            return HTMLResponse(path.read_text(encoding="utf-8"))
    return HTMLResponse("<h1>XAU/USD Dashboard</h1><p>Dashboard HTML introuvable.</p>", status_code=500)


@app.get("/", include_in_schema=False)
def home():
    return dashboard_file()


@app.get("/api/xauusd")
def xauusd(mode: Literal["quick", "full"] = Query(default="quick")):
    try:
        payload = build_cloud_payload(mode=mode)
        return JSONResponse(
            payload,
            headers={"Cache-Control": "no-store, max-age=0"},
        )
    except Exception as exc:  # pragma: no cover - Vercel runtime branch
        return JSONResponse(
            {
                "error": "Service temporairement indisponible",
                "message": str(exc),
                "generated_at": iso_now(),
                "trace": traceback.format_exc(limit=2),
                "note": "Rechargez la page. Les sources marche peuvent parfois refuser une requete.",
            },
            status_code=503,
            headers={"Cache-Control": "no-store, max-age=0"},
        )


@app.get("/{path:path}", include_in_schema=False)
def fallback(path: str):
    if path.startswith("api/"):
        return JSONResponse({"error": "Not found"}, status_code=404)
    return dashboard_file()
