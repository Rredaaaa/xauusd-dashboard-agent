#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import copy
import hashlib
import html
import http.server
import io
import json
import os
import re
import sys
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
import zipfile
from dataclasses import asdict, dataclass, field
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

from explanation_layer import (
    ExplanationContext,
    ExplanationLayer,
    render_experimental_agent,
)
from news_facts import (
    NewsFact,
    build_news_fact as _build_news_fact_v3,
    deduplicate_news_facts,
)

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0 Safari/537.36"
    )
}

INVESTING_XAUUSD_URL = "https://www.investing.com/currencies/xau-usd"
INVESTING_XAUUSD_HISTORICAL_URL = "https://www.investing.com/currencies/xau-usd-historical-data"
IG_WEEKEND_GOLD_URL = "https://www.ig.com/en/indices/markets-indices/weekend-gold"
WHITE_HOUSE_NEWS_FEED_URL = "https://www.whitehouse.gov/news/feed/"
TRUMP_TRUTH_SOCIAL_FEED_URL = "https://trumpstruth.org/feed"
TRUMP_NITTER_FEEDS = [
    "https://nitter.net/realDonaldTrump/rss",
    "https://nitter.privacydev.net/realDonaldTrump/rss",
    "https://nitter.poast.org/realDonaldTrump/rss",
]
WHITE_HOUSE_NITTER_FEEDS = [
    "https://nitter.net/WhiteHouse/rss",
    "https://nitter.privacydev.net/WhiteHouse/rss",
    "https://nitter.poast.org/WhiteHouse/rss",
]
AP_BUSINESS_FEED_URL = "https://apnews.com/hub/business?output=rss"
AP_TOP_NEWS_FEED_URL = "https://apnews.com/hub/ap-top-news?output=rss"
CNBC_MARKETS_FEED_URL = "https://www.cnbc.com/id/100003114/device/rss/rss.html"
REUTERS_TOP_NEWS_FEED_URL = "https://feeds.reuters.com/reuters/topNews"
REUTERS_BUSINESS_FEED_URL = "https://feeds.reuters.com/reuters/businessNews"
REUTERS_MARKETS_FEED_URL = "https://feeds.reuters.com/reuters/marketsNews"
BLOOMBERG_MARKETS_FEED_URL = "https://feeds.bloomberg.com/markets/news.rss"
BLS_NEWS_RELEASE_FEED_URL = "https://www.bls.gov/feed/news_release/bls_latest.rss"
BEA_RSS_URL = "https://www.bea.gov/rss.xml"
TREASURY_PRESS_FEED_URL = "https://home.treasury.gov/news/press-releases/rss"
CFTC_PRESS_FEED_URL = "https://www.cftc.gov/PressRoom/PressReleases/RSS"
WGC_NEWS_FEED_URL = "https://www.gold.org/rss.xml"
FED_PRESS_ALL_RSS_URL = "https://www.federalreserve.gov/feeds/press_all.xml"
ECB_PRESS_FEED_URL = "https://www.ecb.europa.eu/rss/press.html"
BOE_NEWS_FEED_URL = "https://www.bankofengland.co.uk/news/news-publications-feed"
BOJ_NEWS_FEED_URL = "https://www.boj.or.jp/en/whatsnew/news_e.xml"

NEWS_QUERIES = [
    ("gold", '"gold news today" OR XAUUSD when:2d'),
    ("macro_fed", '"Fed interest rate decision {month}" gold when:30d'),
    ("macro_cpi", '"US CPI inflation latest data" gold when:30d'),
    ("macro_nfp", '"NFP jobs report latest" gold when:30d'),
    ("geopolitical", '"geopolitical risk gold today" OR (gold war conflict safe haven) when:3d'),
    ("sentiment_cot", '"gold COT report latest commitments of traders" OR "gold futures net long" when:14d'),
    ("sentiment_oi", '"COMEX gold open interest today" OR "gold open interest" when:7d'),
    ("sentiment_etf", '"gold ETF flows today GLD IAU" OR "GLD IAU flows" when:7d'),
    ("events_calendar", '"economic calendar today high impact" gold OR forex when:2d'),
    ("events_fomc", '"FOMC minutes speech today" gold when:7d'),
    ("risk_vix", '"VIX fear greed index today" OR "VIX today" gold when:2d'),
    ("physical_demand", '(China gold demand OR India gold demand OR "central bank gold buying") when:30d'),
]

POLITICAL_STATEMENT_QUERIES = [
    ("political_trump_iran", '(Trump Iran OR "White House" Iran OR Trump Hormuz OR "Strait of Hormuz") oil gold when:7d'),
    ("political_trump_fed", '(Trump Fed OR Trump Powell OR "White House" Federal Reserve) dollar gold rates when:14d'),
    ("political_trump_dollar", '(Trump dollar OR Trump tariffs OR Trump sanctions) gold oil USD when:14d'),
    ("political_confirmed_wire", '(Trump Iran oil gold OR Trump Fed dollar gold) (site:apnews.com OR site:reuters.com) when:14d'),
]

POLITICAL_GOOGLE_FALLBACK_QUERIES = [
    ("political_trump_google_fallback", '(Trump Iran oil gold OR "White House" Iran oil gold OR Trump Hormuz OR "US president" Iran oil market) when:2d'),
    ("political_trump_google_fallback", '(Trump sanctions Iran oil OR Trump Powell rates gold OR "White House" dollar gold) when:2d'),
]

POLITICAL_RSS_FEEDS = [
    ("political_white_house", WHITE_HOUSE_NEWS_FEED_URL),
    ("political_trump_truth", TRUMP_TRUTH_SOCIAL_FEED_URL),
    ("political_trump_nitter", TRUMP_NITTER_FEEDS[0]),
    ("political_white_house_nitter", WHITE_HOUSE_NITTER_FEEDS[0]),
]

OFFICIAL_NEWS_RSS_FEEDS = [
    ("official_white_house", WHITE_HOUSE_NEWS_FEED_URL),
    ("official_fed_speeches", "https://www.federalreserve.gov/feeds/speeches.xml"),
    ("official_fed_monetary", "https://www.federalreserve.gov/feeds/press_monetary.xml"),
    ("official_fed_press_all", FED_PRESS_ALL_RSS_URL),
    ("official_bls", BLS_NEWS_RELEASE_FEED_URL),
    ("official_bea", BEA_RSS_URL),
    ("official_treasury", TREASURY_PRESS_FEED_URL),
    ("official_cftc_press", CFTC_PRESS_FEED_URL),
    ("official_wgc", WGC_NEWS_FEED_URL),
    ("official_ecb", ECB_PRESS_FEED_URL),
    ("official_boe", BOE_NEWS_FEED_URL),
    ("official_boj", BOJ_NEWS_FEED_URL),
]

FAST_NEWS_RSS_FEEDS = [
    ("fast_ap_business", AP_BUSINESS_FEED_URL),
    ("fast_ap_top", AP_TOP_NEWS_FEED_URL),
    ("fast_cnbc_markets", CNBC_MARKETS_FEED_URL),
    ("fast_reuters_top", REUTERS_TOP_NEWS_FEED_URL),
    ("fast_reuters_business", REUTERS_BUSINESS_FEED_URL),
    ("fast_reuters_markets", REUTERS_MARKETS_FEED_URL),
    ("fast_bloomberg_markets", BLOOMBERG_MARKETS_FEED_URL),
]

CRITICAL_FAST_FEEDS = {
    "trump_truth": TRUMP_TRUTH_SOCIAL_FEED_URL,
    "trump_nitter": TRUMP_NITTER_FEEDS[0],
    "white_house_nitter": WHITE_HOUSE_NITTER_FEEDS[0],
    "white_house": WHITE_HOUSE_NEWS_FEED_URL,
    "fed_press_all": FED_PRESS_ALL_RSS_URL,
    "bls": BLS_NEWS_RELEASE_FEED_URL,
    "bea": BEA_RSS_URL,
    "treasury": TREASURY_PRESS_FEED_URL,
    "ecb": ECB_PRESS_FEED_URL,
    "boj": BOJ_NEWS_FEED_URL,
    "reuters_top": REUTERS_TOP_NEWS_FEED_URL,
    "reuters_business": REUTERS_BUSINESS_FEED_URL,
    "bloomberg_markets": BLOOMBERG_MARKETS_FEED_URL,
    "ap_business": AP_BUSINESS_FEED_URL,
    "ap_top": AP_TOP_NEWS_FEED_URL,
}

FAST_NEWS_SEARCH_QUERIES = [
    ("fast_reuters", '(gold OR XAUUSD OR Fed OR Iran OR oil OR dollar) site:reuters.com when:1d'),
    ("fast_bloomberg", '(gold OR XAUUSD OR Fed OR Iran OR oil OR dollar) site:bloomberg.com when:1d'),
    ("fast_ap_search", '(gold OR Federal Reserve OR Iran OR oil OR dollar) site:apnews.com when:1d'),
    ("fast_cnbc_search", '(gold OR XAUUSD OR Fed OR Iran OR oil OR dollar) site:cnbc.com when:1d'),
]

FALLBACK_RSS_FEEDS = [
    ("gold", "https://feeds.finance.yahoo.com/rss/2.0/headline?s=GC=F&region=US&lang=en-US"),
    ("commodities", "https://www.investing.com/rss/commodities.rss"),
    ("markets", "https://www.investing.com/rss/news_25.rss"),
]

FRED_CSV_URL_TEMPLATE = "https://fred.stlouisfed.org/graph/fredgraph.csv?id={series_id}"
FRED_DFII10_CSV_URL = FRED_CSV_URL_TEMPLATE.format(series_id="DFII10")
CFTC_GOLD_CONTRACT_CODE = "088691"
CFTC_GOLD_MARKET_NAME = "GOLD - COMMODITY EXCHANGE INC."
CFTC_DISAGG_CURRENT_URL = "https://www.cftc.gov/dea/newcot/f_disagg.txt"
CFTC_DISAGG_HISTORY_URL_TEMPLATE = "https://www.cftc.gov/files/dea/history/fut_disagg_txt_{year}.zip"
WGC_ETF_FLOWS_PAGE_URL = "https://www.gold.org/goldhub/data/gold-etfs-holdings-and-flows"
WGC_ETF_ARCHIVE_TABLE_URL = "https://fsapi.gold.org/api/v11/charts/etfv2/revised/archive-tablegroup/all?break-cache=27Apr26"
ISHARES_IAU_PAGE_URL = "https://www.blackrock.com/us/financial-professionals/products/239561/"
ISHARES_IAU_DATA_URL = (
    "https://www.blackrock.com/us/financial-professionals/products/239561/"
    "ishares-gold-trust-fund/1527781476618.ajax?fileType=xls&fileName=iShares-Gold-Trust_fund&dataType=fund"
)
FED_FOMC_CALENDAR_URL = "https://www.federalreserve.gov/monetarypolicy/fomccalendars.htm"
FED_SPEECHES_RSS_URL = "https://www.federalreserve.gov/feeds/speeches.xml"
FED_MONETARY_POLICY_RSS_URL = "https://www.federalreserve.gov/feeds/press_monetary.xml"
BEA_RELEASE_SCHEDULE_URL = "https://www.bea.gov/news/schedule"
CME_FEDWATCH_TOOL_URL = "https://www.cmegroup.com/markets/interest-rates/cme-fedwatch-tool.html"
CME_FEDWATCH_API_INFO_URL = "https://www.cmegroup.com/market-data/market-data-api/fedwatch-api.html"
TRADE_LEDGER_PATH = Path("reports") / "trade_ledger.jsonl"
TRADE_GATE_AUDIT_PATH = Path("reports") / "trade_gate_audit.jsonl"
AUDIT_LOG_PATH = Path("reports") / "audit_log.jsonl"
MULTI_STRATEGY_HISTORY_PATH = Path("reports") / "multi_strategy_history.jsonl"
SOURCE_ERRORS_PATH = Path("reports") / "source_errors.jsonl"
FEED_HASH_CACHE_PATH = Path("reports") / "feed_hash_cache.json"
CHART_STORE_CACHE_PATH = Path("reports") / "chart_store_cache.json"
REGIME_STATE_PATH = Path("reports") / "regime_state.json"
SETTINGS_PATH = Path("config") / "aureum_settings.json"
REPORTS_V3_DIR = Path("reports") / "v3"
AUDIT_ROTATION_MAX_BYTES = 2_000_000
AUDIT_ARCHIVE_MAX_FILES = 12
ECB_MEETING_CALENDAR_URL = "https://www.ecb.europa.eu/press/calendars/mgcgc/html/index.en.html"
BOE_MEETING_CALENDAR_URL = "https://www.bankofengland.co.uk/monetary-policy-summary-and-minutes/monetary-policy-summary-and-minutes"
BOJ_MEETING_CALENDAR_URL = "https://www.boj.or.jp/en/mopo/mpmsche_minu/index.htm"
CFTC_DISAGG_MIN_FIELDS = [
    "Market_and_Exchange_Names",
    "As_of_Date_In_Form_YYMMDD",
    "Report_Date_as_YYYY-MM-DD",
    "CFTC_Contract_Market_Code",
    "CFTC_Market_Code",
    "CFTC_Region_Code",
    "CFTC_Commodity_Code",
    "Open_Interest_All",
    "Prod_Merc_Positions_Long_All",
    "Prod_Merc_Positions_Short_All",
    "Swap_Positions_Long_All",
    "Swap__Positions_Short_All",
    "Swap__Positions_Spread_All",
    "M_Money_Positions_Long_All",
    "M_Money_Positions_Short_All",
    "M_Money_Positions_Spread_All",
    "Other_Rept_Positions_Long_All",
    "Other_Rept_Positions_Short_All",
    "Other_Rept_Positions_Spread_All",
    "Tot_Rept_Positions_Long_All",
    "Tot_Rept_Positions_Short_All",
    "NonRept_Positions_Long_All",
    "NonRept_Positions_Short_All",
]
FRED_SERIES_LABELS = {
    "DGS10": "US 10Y Treasury Yield",
    "DGS2": "US 2Y Treasury Yield",
    "DGS3MO": "US 3M Treasury Yield",
    "DGS30": "US 30Y Treasury Yield",
    "T10YIE": "US 10Y Breakeven Inflation",
    "DFII10": "US 10Y Real Yield",
}
CROSS_ASSET_SYMBOLS = {
    "gold_proxy": ("GC=F", "Gold Futures Proxy"),
    "usdjpy": ("JPY=X", "USD/JPY"),
    "silver": ("SI=F", "Silver Futures"),
    "gdx": ("GDX", "Gold Miners ETF"),
    "gdxj": ("GDXJ", "Junior Gold Miners ETF"),
    "audusd": ("AUDUSD=X", "AUD/USD"),
    "usdchf": ("CHF=X", "USD/CHF"),
    "tip": ("TIP", "TIPS ETF"),
    "spx": ("^GSPC", "S&P 500"),
    "gvz": ("^GVZ", "Gold Volatility Index"),
    "vix": ("^VIX", "VIX"),
    "wti": ("CL=F", "WTI Crude Oil"),
    "brent": ("BZ=F", "Brent Crude Oil"),
}
LOCAL_CONTEXT_CACHE_SECONDS = 300
LOCAL_CONTEXT_SNAPSHOT_CACHE: dict[str, tuple[float, SymbolSnapshot | None]] = {}

SYSTEM_PROMPT = """
You are a disciplined XAUUSD market briefing assistant.
Use only the supplied market data and headlines.
Do not invent events, quotes, price levels, or probabilities.
Do not provide personalized financial advice or guaranteed buy/sell calls.
Respond in French.
Keep the analysis concise and practical for a trader.
Return:
1. A one-line directional bias.
2. Three short bullets: bullish case, bearish case, neutral/wait case.
3. A final risk warning sentence.
""".strip()

BULLISH_KEYWORDS = {
    "safe haven": 2,
    "geopolit": 2,
    "war": 2,
    "conflict": 2,
    "attack": 2,
    "attacks": 2,
    "clash": 2,
    "missile": 2,
    "military": 2,
    "militarily": 2,
    "enemy": 1,
    "navy": 2,
    "ships": 2,
    "sanction": 2,
    "sanctions": 2,
    "escalation": 2,
    "escalate": 2,
    "iran nuclear": 3,
    "nuclear weapon": 3,
    "iran tension": 2,
    "iran clash": 2,
    "hormuz": 3,
    "oil shock": 3,
    "oil spike": 2,
    "blockade": 2,
    "attack ship": 3,
    "attack tanker": 3,
    "iran threat": 2,
    "tehran": 1,
    "houthi": 2,
    "red sea": 2,
    "energy supply shock": 2,
    "supply shock": 2,
    "rate cut": 2,
    "fed cut": 3,
    "fed pause": 2,
    "fed signal cut": 3,
    "powell dovish": 3,
    "rate decrease": 2,
    "ease policy": 2,
    "lower fed funds": 2,
    "inflation cool": 2,
    "cpi miss": 2,
    "nfp weak": 2,
    "yield curve invert": 2,
    "cuts": 1,
    "dovish": 2,
    "recession": 1,
    "inflation": 1,
    "weak dollar": 2,
    "dollar falls": 2,
    "lower yields": 2,
    "falling yields": 2,
    "central bank buying": 2,
    "central bank gold": 3,
    "gold buying": 2,
    "china tension": 2,
}

BEARISH_KEYWORDS = {
    "hawkish": -2,
    "higher for longer": -2,
    "rate hike": -2,
    "fed hike": -3,
    "powell hawkish": -3,
    "rate increase": -2,
    "tighten policy": -2,
    "higher fed funds": -2,
    "inflation accelerate": -2,
    "cpi beat": -2,
    "nfp strong": -2,
    "jobs surge": -2,
    "yield surge": -2,
    "dollar surge": -3,
    "dxy rally": -2,
    "treasury sell": -2,
    "strong dollar": -2,
    "dollar strengthens": -2,
    "rising yields": -2,
    "higher yields": -2,
    "risk-on": -1,
    "economic cooperation": -1,
    "market access": -1,
    "increasing investment": -1,
    "open up china": -1,
    "s&p 500 tops": -2,
    "record-breaking run": -1,
    "ai fuels": -1,
    "ceasefire": -1,
    "truce": -1,
    "de-escalation": -2,
    "deescalation": -2,
    "iran deal": -3,
    "iran agreement": -2,
    "iran ceasefire": -3,
    "iran nuclear deal": -3,
    "iran accord": -3,
    "tehran agreement": -3,
    "peace iran": -3,
    "tanker resume": -2,
    "hormuz transit": -2,
    "lpg tanker": -2,
    "oil supply": -1,
}

RISK_OFF_POSITIVE_KEYWORDS = {
    "war",
    "conflict",
    "attack",
    "missile",
    "sanction",
    "escalation",
    "banking crisis",
    "bank run",
    "panic",
    "safe haven",
    "risk-off",
    "geopolitical risk",
}
RISK_OFF_NEGATIVE_KEYWORDS = {
    "ceasefire",
    "truce",
    "deal",
    "peace",
    "de-escalation",
}
CENTRAL_BANK_DOVISH_KEYWORDS = {
    "rate cut",
    "cuts",
    "dovish",
    "easing",
    "pause",
    "cooling inflation",
    "soft cpi",
    "lower inflation",
}
CENTRAL_BANK_HAWKISH_KEYWORDS = {
    "hawkish",
    "higher for longer",
    "rate hike",
    "sticky inflation",
    "hot cpi",
    "strong jobs",
    "higher yields",
}
PHYSICAL_DEMAND_POSITIVE_KEYWORDS = {
    "china gold demand",
    "india gold demand",
    "central bank buying",
    "reserve buying",
    "imports rise",
    "physical demand",
    "festival demand",
}
PHYSICAL_DEMAND_NEGATIVE_KEYWORDS = {
    "weak demand",
    "demand slows",
    "imports fall",
    "jewelry demand weak",
    "outflows",
}
SPECULATORS_LONG_KEYWORDS = {
    "net long",
    "long positions rise",
    "bullish bets",
    "money managers raise",
    "speculators net long",
}
SPECULATORS_SHORT_KEYWORDS = {
    "net short",
    "short positions rise",
    "bearish bets",
    "money managers cut longs",
    "shorts increase",
}
ETF_INFLOW_KEYWORDS = {
    "inflows",
    "holdings rise",
    "added",
    "net inflows",
    "etf demand",
}
ETF_OUTFLOW_KEYWORDS = {
    "outflows",
    "holdings fall",
    "redemptions",
    "net outflows",
}
OPEN_INTEREST_UP_KEYWORDS = {
    "open interest rises",
    "open interest up",
    "open interest increases",
    "positions build",
}
OPEN_INTEREST_DOWN_KEYWORDS = {
    "open interest falls",
    "open interest down",
    "open interest declines",
    "liquidation",
}
VIX_RISK_OFF_KEYWORDS = {
    "vix jumps",
    "vix spikes",
    "fear gauge rises",
    "volatility surges",
    "risk aversion",
}
VIX_RISK_ON_KEYWORDS = {
    "vix falls",
    "fear gauge cools",
    "volatility eases",
    "risk appetite",
}
OIL_SHOCK_KEYWORDS = {
    "hormuz",
    "strait of hormuz",
    "iran",
    "oil shipping",
    "shipping lane",
    "blockade",
    "mine",
    "mines",
    "navy",
    "tanker",
    "sanctions",
    "crude",
    "brent",
    "wti",
}


@dataclass
class PricePoint:
    timestamp: int
    close: float
    high: float | None = None
    low: float | None = None
    open: float | None = None
    volume: int | None = None


@dataclass
class SymbolSnapshot:
    symbol: str
    label: str
    price: float
    previous_close: float
    change_abs: float
    change_pct: float
    period_change_pct: float
    day_high: float | None
    day_low: float | None
    support: float | None
    resistance: float | None
    fetched_at: str
    points: list[PricePoint]
    intraday_points: list[PricePoint] = field(default_factory=list)


@dataclass
class WeekendGoldSnapshot:
    source_name: str
    source_url: str
    sell: float
    buy: float
    mid: float
    spread: float
    change_abs: float | None
    change_pct: float | None
    day_high: float | None
    day_low: float | None
    long_pct: int | None
    short_pct: int | None
    fetched_at: str


@dataclass
class NewsItem:
    title: str
    source: str
    link: str
    published_at: str
    category: str
    score: int
    score_reasons: list[str]
    feed_detected_at: str = ""
    feed_processed_at: str = ""
    source_latency_seconds: float | None = None
    processing_latency_seconds: float | None = None
    feed_hash: str = ""
    is_breaking: bool = False


SOURCE_CATEGORY_TO_LOGICAL: dict[str, str] = {
    "critical_white_house_nitter": "geopolitical",
    "critical_trump_nitter": "geopolitical",
    "critical_trump_truth": "geopolitical",
    "political_trump_truth": "geopolitical",
    "political_trump_nitter": "geopolitical",
    "political_trump_google_fallback": "geopolitical",
    "political_white_house_nitter": "geopolitical",
    "political_trump_iran": "geopolitical",
    "political_netanyahu_iran": "geopolitical",
    "political_white_house": "geopolitical",
    "official_white_house": "geopolitical",
    "fast_reuters": "geopolitical",
    "fast_reuters_top": "geopolitical",
    "fast_reuters_business": "geopolitical",
    "fast_reuters_markets": "geopolitical",
    "fast_bloomberg": "geopolitical",
    "fast_bloomberg_markets": "geopolitical",
    "fast_ap_business": "geopolitical",
    "fast_ap_top": "geopolitical",
    "fast_ap_search": "geopolitical",
    "fast_cnbc_markets": "geopolitical",
    "fast_cnbc_search": "geopolitical",
    "official_fed_speeches": "macro_fed",
    "official_fed_monetary": "macro_fed",
    "official_fed_press_all": "macro_fed",
    "official_treasury": "macro_fed",
    "official_ecb": "macro_fed",
    "official_boe": "macro_fed",
    "official_boj": "macro_fed",
    "political_trump_fed": "macro_fed",
    "political_trump_dollar": "macro_fed",
    "political_confirmed_wire": "geopolitical",
    "official_bls": "macro_cpi",
    "official_bea": "macro_cpi",
    "official_cftc_press": "sentiment_cot",
    "official_wgc": "physical_demand",
}

PRIORITY_NEWS_CATEGORIES: set[str] = {
    "geopolitical",
    "risk_vix",
    "gold",
    "events_fomc",
    "events_calendar",
    "macro_fed",
    "macro_cpi",
    "macro_nfp",
    "sentiment_cot",
    "sentiment_etf",
    "sentiment_oi",
    "physical_demand",
}

CATEGORY_PRIORITY: dict[str, int] = {
    "geopolitical": 0,
    "gold": 1,
    "macro_fed": 2,
    "macro_cpi": 3,
    "macro_nfp": 4,
    "events_fomc": 5,
    "risk_vix": 6,
    "sentiment_cot": 7,
    "sentiment_etf": 8,
    "sentiment_oi": 9,
    "physical_demand": 10,
    "events_calendar": 11,
}


def logical_category(item_or_category: NewsItem | str) -> str:
    """Mappe une categorie source Phase 4.5 vers la categorie metier utilisee par les agents."""
    if isinstance(item_or_category, str):
        return SOURCE_CATEGORY_TO_LOGICAL.get(item_or_category, item_or_category)

    raw_category = item_or_category.category
    text = normalize_title_for_dedupe(item_or_category.title)

    if raw_category in {"official_bls", "official_bea"}:
        if text_contains_any(text, ("jobs", "employment", "payroll", "nfp", "nonfarm", "jobless", "claims")):
            return "macro_nfp"
        if text_contains_any(text, ("cpi", "pce", "inflation", "prices", "price index", "personal income", "outlays")):
            return "macro_cpi"
        return SOURCE_CATEGORY_TO_LOGICAL.get(raw_category, raw_category)

    if raw_category.startswith("fast_") or raw_category.startswith("critical_") or raw_category.startswith("political_"):
        if text_contains_any(text, ("fed", "fomc", "powell", "rate", "rates", "yields", "treasury", "dollar", "tariff", "sanction")):
            return "macro_fed"
        if text_contains_any(text, ("cpi", "pce", "inflation", "prices")):
            return "macro_cpi"
        if text_contains_any(text, ("jobs", "payroll", "employment", "nfp", "nonfarm")):
            return "macro_nfp"
        if text_contains_any(text, ("cot", "commitments of traders", "managed money")):
            return "sentiment_cot"
        if text_contains_any(text, ("etf", "gld", "iau", "inflow", "outflow", "holdings")):
            return "sentiment_etf"
        if text_contains_any(text, ("vix", "volatility", "risk aversion")):
            return "risk_vix"

    return SOURCE_CATEGORY_TO_LOGICAL.get(raw_category, raw_category)


@dataclass
class EventFact:
    title: str
    source: str
    source_url: str
    published_at: str
    category: str
    actors: list[str]
    locations: list[str]
    themes: list[str]
    confirmation_level: str
    market_chain: str
    gold_impact: str
    impact_bias: str
    confidence: int


@dataclass
class PoliticalStatement:
    title: str
    source: str
    source_url: str
    published_at: str
    theme: str
    validation_level: str
    source_tier: int
    gold_impact: str
    oil_impact: str
    usd_impact: str
    market_chain: str
    score: int
    confidence: int


@dataclass
class AnalysisResult:
    bias: str
    score: int
    confidence: int
    reasons: list[str]
    bullish_news: list[NewsItem]
    bearish_news: list[NewsItem]
    neutral_news: list[NewsItem]
    geopolitical: "GeopoliticalAnalysis | None" = None


@dataclass
class GeopoliticalAnalysis:
    score: int
    summary: str
    risk_off_status: str
    central_bank_bias: str
    physical_demand_trend: str
    large_speculators: str
    etf_flows: str
    comex_open_interest: str
    vix_tone: str
    event_watch: list[str]
    reasons: list[str]


@dataclass
class CorrelationSignal:
    instrument: str
    symbol: str
    expected_relation: str
    price: float | None
    change: float | None
    change_unit: str
    corr_30: float | None
    corr_90: float | None
    signal: str
    impact: int
    reason: str


@dataclass
class CrossAssetAnalysis:
    score: int
    status: str
    verdict: str
    summary: str
    confirmations: list[str]
    contradictions: list[str]
    drivers: dict[str, dict[str, Any]]
    signals: list[CorrelationSignal]


@dataclass
class EventModeAnalysis:
    active: bool
    score: int
    status: str
    action: str
    stop_multiplier: float
    reasons: list[str]


@dataclass
class FastNewsEvent:
    event_id: str
    title: str
    source: str
    source_url: str
    published_at: str
    detected_at: str
    processed_at: str
    category: str
    logical_category: str
    source_tier: int
    event_type: str
    direction: str
    score: int
    confidence: int
    validity_minutes: int
    valid_until: str
    latency_seconds: float | None
    is_breaking: bool
    reasons: list[str] = field(default_factory=list)


@dataclass
class PriceReactionSignal:
    direction: str
    confirmation_score: int
    confirms: bool
    fade_trap: bool
    xauusd_change_pct: float
    dxy_change_pct: float
    us10y_change_bps: float
    oil_change_pct: float | None
    checks: list[str] = field(default_factory=list)


@dataclass
class NewsReactionTradePlan:
    status: str
    direction: str
    event_type: str
    title: str
    source: str
    source_url: str
    confidence: int
    validity_minutes: int
    valid_until: str
    entry_type: str
    reference_price: float
    entry_zone_low: float
    entry_zone_high: float
    stop_loss: float
    tp1: float
    tp2: float
    tp3: float
    risk_reward_tp1: float
    risk_reward_tp2: float
    risk_reward_tp3: float
    confirmation_score: int
    latency_seconds: float | None
    created_at: str
    event_id: str
    reasons: list[str] = field(default_factory=list)
    blockers: list[str] = field(default_factory=list)


@dataclass
class SetupCandidate:
    name: str
    status: str
    direction: str
    confidence: int
    confluence_score: int
    conditions_met: list[str]
    entry_zone_low: float
    entry_zone_high: float
    stop_loss: float
    tp1: float
    tp2: float
    tp3: float
    rr_tp1: float
    rr_tp2: float
    rr_tp3: float
    validity_minutes: int
    cooldown_after_loss_minutes: int
    cooldown_after_win_minutes: int
    preferred_session: str
    reasons: list[str]
    blockers: list[str]
    detected_at: str
    metadata: dict[str, Any] = field(default_factory=dict)
    partial_conditions: dict[str, list[dict[str, Any]]] = field(
        default_factory=lambda: {"buy": [], "sell": []}
    )


@dataclass
class StrategySelection:
    status: str
    selected_setup: SetupCandidate | None
    selected_score: int
    session: str
    event_mode_active: bool
    reasons: list[str]
    ranked_candidates: list[dict[str, Any]]
    rejected_candidates: list[dict[str, Any]]


@dataclass
class StrategyShadowIntegration:
    status: str
    final_action: str
    lead_verdict: str
    lead_score: int
    strategy_status: str
    strategy_setup: str
    strategy_direction: str
    strategy_score: int
    alignment: str
    allowed_to_affect_lead: bool
    allowed_to_lock_trade: bool
    reasons: list[str]
    blockers: list[str]


@dataclass
class ReversalSetup:
    horizon: str
    status: str
    direction: str
    tf_signal: str
    tf_context: str
    confluence_score: int
    conditions_met: list[str]
    entry_zone_low: float
    entry_zone_high: float
    stop_loss: float
    tp1: float
    tp2: float
    tp3: float
    risk_reward_tp1: float
    validity_minutes: int
    reasons: list[str]
    blockers: list[str]
    detected_at: str


@dataclass
class MarketRegimeAnalysis:
    name: str
    status: str
    score: int
    gold_impact: str
    summary: str
    reasons: list[str]
    trend: str = "stable"
    confirmed: bool = False
    probabilities: dict[str, int] = field(default_factory=dict)
    component_scores: dict[str, int] = field(default_factory=dict)


@dataclass
class OfficialMacroRates:
    dgs10: SymbolSnapshot | None = None
    dgs2: SymbolSnapshot | None = None
    dgs3m: SymbolSnapshot | None = None
    dgs30: SymbolSnapshot | None = None
    t10yie: SymbolSnapshot | None = None
    dfii10: SymbolSnapshot | None = None
    yahoo_tnx_gap_bps: float | None = None


@dataclass
class CFTCPositioning:
    market: str
    contract_code: str
    report_date: str
    source_url: str
    open_interest: int
    open_interest_change: int
    managed_money_long: int
    managed_money_short: int
    managed_money_spread: int
    managed_money_net: int
    managed_money_net_change: int
    managed_money_net_pct_oi: float
    producer_long: int
    producer_short: int
    producer_net: int
    producer_net_change: int
    swap_long: int
    swap_short: int
    swap_spread: int
    swap_net: int
    swap_net_change: int
    non_reportable_long: int
    non_reportable_short: int
    non_reportable_net: int
    non_reportable_net_change: int
    score: int
    status: str
    summary: str
    managed_money_percentile_1y: float = 50.0
    managed_money_percentile_5y: float = 50.0
    producer_net_percentile_1y: float = 50.0
    producer_net_percentile_5y: float = 50.0


@dataclass
class ETFHoldingRecord:
    fund: str
    ticker: str
    source_name: str
    source_url: str
    as_of_date: str
    holdings_tonnes: float | None
    daily_flow_tonnes: float | None
    weekly_flow_tonnes: float | None
    monthly_flow_tonnes: float | None
    ytd_flow_tonnes: float | None
    flow_usd_mn: float | None
    status: str
    note: str


@dataclass
class ETFFlowsAnalysis:
    as_of_date: str
    source_name: str
    source_url: str
    global_holdings_tonnes: float | None
    global_weekly_demand_tonnes: float | None
    global_monthly_demand_tonnes: float | None
    global_weekly_flows_usd_mn: float | None
    global_monthly_flows_usd_mn: float | None
    score: int
    status: str
    summary: str
    holdings: list[ETFHoldingRecord] = field(default_factory=list)
    source_note: str = ""


@dataclass
class MacroCatalyst:
    title: str
    event_type: str
    scheduled_at: str
    source_name: str
    source_url: str
    impact_level: str
    gold_impact: str
    why_it_matters: str
    status: str
    minutes_to_event: int | None = None
    forecast: str = ""
    previous: str = ""
    actual: str = ""
    expected_gold_bias: str = "NEUTRAL"


@dataclass
class MacroCatalystCalendar:
    generated_at: str
    source_note: str
    fedwatch_status: str
    fedwatch_note: str
    fedwatch_source_url: str
    catalysts: list[MacroCatalyst] = field(default_factory=list)
    high_impact_24h: int = 0
    density_status: str = "normal"
    pre_event_active: bool = False
    pre_event_summary: str = ""


@dataclass
class SourceRegistryEntry:
    source_id: str
    name: str
    category: str
    tier: int
    max_age_minutes: int
    critical: bool
    source_url: str
    allowed_agents: list[str]


@dataclass
class SourceSnapshot:
    source_id: str
    name: str
    category: str
    tier: int
    status: str
    last_update: str | None
    age_minutes: int | None
    value_summary: str
    source_url: str
    critical: bool
    allowed_agents: list[str]


@dataclass
class DataRoute:
    source_id: str
    source_name: str
    category: str
    target_agents: list[str]
    required: bool
    status: str
    mode: str
    message: str


@dataclass
class PreflightCheck:
    generated_at: str
    status: str
    summary: str
    trade_blocked: bool
    blockers: list[str]
    warnings: list[str]
    routes: list[DataRoute] = field(default_factory=list)


@dataclass
class OHLCCandle:
    timestamp: int
    open: float
    high: float
    low: float
    close: float
    volume: int | None
    source: str
    timeframe: str
    fetched_at: str


@dataclass
class ChartTimeframe:
    timeframe: str
    status: str
    candles: list[OHLCCandle] = field(default_factory=list)
    quality_flags: list[str] = field(default_factory=list)
    last_timestamp: int | None = None
    freshness_minutes: int | None = None
    gap_count: int = 0


@dataclass
class ChartStore:
    generated_at: str
    symbol: str
    source: str
    status: str
    summary: str
    timeframes: list[ChartTimeframe] = field(default_factory=list)


@dataclass
class DataQualitySnapshot:
    generated_at: str
    score: int
    status: str
    summary: str
    missing_sources: list[str]
    stale_sources: list[str]
    weak_sources: list[str]
    contradictions: list[str]
    snapshots: list[SourceSnapshot] = field(default_factory=list)
    preflight: PreflightCheck | None = None


@dataclass
class TradePlan:
    trade_id: str
    created_at: str
    updated_at: str
    status: str
    direction: str
    entry_type: str
    reference_price: float
    entry_zone_low: float
    entry_zone_high: float
    stop_loss: float
    tp1: float
    tp2: float
    tp3: float
    risk_reward_tp1: float
    risk_reward_tp2: float
    risk_reward_tp3: float
    max_valid_until: str
    source_signal_id: str
    global_score_at_creation: int
    data_quality_score: int
    confidence_score: int
    market_regime: str
    agents_validating: list[str]
    agents_contradicting: list[str]
    evidence_sources: list[str]
    event_facts_snapshot: list[str]
    technical_snapshot: str
    macro_snapshot: str
    geopolitical_snapshot: str
    elliott_wave_snapshot: str
    invalidation_rules: list[str]
    outcome: str
    outcome_reason: str
    closed_at: str | None = None
    record_type: str = "trade_exploitable"
    scenario_snapshot: str = ""
    useful_agents: list[str] = field(default_factory=list)
    misleading_agents: list[str] = field(default_factory=list)
    missed_condition: str = ""
    post_mortem: str = ""
    r_multiple: float = 0.0
    duration_minutes: int = 0


@dataclass
class TradePostMortem:
    trade_id: str
    direction: str
    outcome: str
    record_type: str
    r_multiple: float
    duration_minutes: int
    useful_agents: list[str]
    misleading_agents: list[str]
    missed_condition: str
    summary: str


@dataclass
class TradeLedgerStats:
    win_rate: float = 0.0
    expectancy_r: float = 0.0
    average_r: float = 0.0
    average_duration_minutes: int = 0
    setup_to_trade_rate: float = 0.0
    trade_to_win_rate: float = 0.0
    total_setups: int = 0
    total_trade_records: int = 0


@dataclass
class TradeLedgerSummary:
    ledger_path: str
    generated_at: str
    quality_gate_status: str
    quality_gate_reasons: list[str]
    active_trades: list[TradePlan] = field(default_factory=list)
    recent_trades: list[TradePlan] = field(default_factory=list)
    total_trades: int = 0
    wins: int = 0
    losses: int = 0
    partials: int = 0
    expired: int = 0
    invalidated: int = 0
    stats: TradeLedgerStats = field(default_factory=TradeLedgerStats)
    post_mortems: list[TradePostMortem] = field(default_factory=list)


@dataclass
class UserSettings:
    active_agents: list[str]
    scoring_mode: str = "balanced"
    minimum_agent_confidence: int = 65
    watch_threshold: int = 50
    trade_threshold: int = 65
    cooldown_minutes: int = 90
    cooldown_after_loss_minutes: int = 240
    cooldown_after_win_minutes: int = 60
    cooldown_after_expired_minutes: int = 60
    max_trades_per_24h: int = 8
    circuit_breaker_after_n_losses: int = 3
    circuit_breaker_window_hours: int = 24
    circuit_breaker_pause_hours: int = 6
    minimum_risk_reward: float = 1.5
    min_data_quality: int = 60
    no_trade_window_minutes_before_high_macro: int = 30
    no_trade_window_minutes_after_high_macro: int = 15
    notifications_enabled: bool = False


@dataclass
class SettingsValidation:
    path: str
    status: str
    warnings: list[str] = field(default_factory=list)
    created_default: bool = False


@dataclass
class ReplayPriceSnapshot:
    timestamp: str
    price: float
    decision_status: str = ""
    decision_score: int = 0


@dataclass
class ReplayTradeResult:
    trade_id: str
    direction: str
    created_at: str
    replay_status: str
    replay_outcome: str
    replay_reason: str
    price_after_1h: float | None = None
    price_after_2h: float | None = None
    price_after_4h: float | None = None
    price_after_24h: float | None = None
    max_favorable_r: float = 0.0
    max_adverse_r: float = 0.0


@dataclass
class ReplayReport:
    generated_at: str
    ledger_path: str
    audit_log_path: str
    snapshots: int
    trades_replayed: int
    results: list[ReplayTradeResult] = field(default_factory=list)
    summary: str = ""


@dataclass
class ReportExport:
    label: str
    path: str
    description: str


@dataclass
class AgentEvidence:
    label: str
    value: str
    source: str = ""


@dataclass
class AgentRisk:
    label: str
    detail: str
    severity: str = "medium"


@dataclass
class AgentResult:
    name: str
    department: str
    bias: str
    score: int
    confidence: int
    summary: str
    evidence: list[AgentEvidence] = field(default_factory=list)
    risks: list[AgentRisk] = field(default_factory=list)
    status: str = "PASSIVE"
    experimental: bool = True


@dataclass
class OrchestratorComponent:
    key: str
    label: str
    score: int
    bias: str
    weight: float
    contribution: float
    confidence: int
    source: str
    reason: str
    weight_reason: str = "Poids de base."


@dataclass
class OrchestratorDecision:
    verdict: str
    score: int
    status: str
    engine: str
    bullish_score: float
    legacy_verdict: str
    legacy_score: int
    top_reasons: list[str]
    counter_reasons: list[str]
    contradictions: list[str]
    quality_gate_reasons: list[str]
    components: list[OrchestratorComponent] = field(default_factory=list)


@dataclass
class BriefingBundle:
    gold: SymbolSnapshot
    dxy: SymbolSnapshot
    us10y: SymbolSnapshot
    news: list[NewsItem]
    analysis: AnalysisResult
    payload: dict[str, Any]
    ai_analysis: str | None
    geopolitical_analysis: GeopoliticalAnalysis | None = None
    fundamental_recommendation: "TradeRecommendation | None" = None
    technical_recommendation: "TradeRecommendation | None" = None
    technical_decision: "TechnicalDecision | None" = None
    scenario_plan: "ScenarioPlan | None" = None
    global_recommendation: "TradeRecommendation | None" = None
    technical_timeframes: list["TechnicalReading"] | None = None
    executive_summary: str = ""
    real_yield: SymbolSnapshot | None = None
    official_macro_rates: OfficialMacroRates | None = None
    cftc_positioning: CFTCPositioning | None = None
    etf_flows_analysis: ETFFlowsAnalysis | None = None
    macro_catalysts: MacroCatalystCalendar | None = None
    data_quality: DataQualitySnapshot | None = None
    cross_asset_analysis: CrossAssetAnalysis | None = None
    event_mode: EventModeAnalysis | None = None
    weekend_gold: WeekendGoldSnapshot | None = None
    market_regime: MarketRegimeAnalysis | None = None
    event_facts: list[EventFact] = field(default_factory=list)
    political_statements: list[PoliticalStatement] = field(default_factory=list)
    agent_results: list[AgentResult] = field(default_factory=list)
    trade_ledger: TradeLedgerSummary | None = None
    orchestrator_decision: OrchestratorDecision | None = None
    chart_store: ChartStore | None = None
    news_reaction_setup: NewsReactionTradePlan | None = None
    reversal_engine: dict[str, ReversalSetup] = field(default_factory=dict)
    strategy_candidates: list[SetupCandidate] = field(default_factory=list)
    strategy_selection: StrategySelection | None = None


@dataclass
class TradeRecommendation:
    mode: str
    verdict: str
    score: int
    summary: str
    reasons: list[str]
    stop_loss: float
    take_profit_1: float
    take_profit_2: float
    source_note: str


@dataclass
class MarketTradeLevels:
    direction: str
    setup_type: str
    entry_zone_low: float
    entry_zone_high: float
    stop_loss: float
    tp1: float
    tp2: float
    tp3: float
    risk_reward_tp1: float
    risk_reward_tp2: float
    risk_reward_tp3: float
    validity_minutes: int
    validity_timeframe: str
    partial_tp1_pct: int
    partial_tp2_pct: int
    partial_tp3_pct: int
    reasons: list[str]


@dataclass
class TechnicalDecision:
    status: str
    direction: str
    structure: str
    score: int
    confidence: int
    trigger: str
    invalidation: str
    entry_zone_low: float
    entry_zone_high: float
    stop_loss: float
    tp1: float
    tp2: float
    tp3: float
    reasons: list[str]
    contradictions: list[str]


@dataclass
class ScenarioPlan:
    status: str
    bias: str
    primary_scenario: str
    alternative_scenario: str
    trigger: str
    confirmation_required: list[str]
    invalidation: str
    action: str
    confidence: int
    validations: list[str]
    contradictions: list[str]


@dataclass
class TechnicalReading:
    timeframe: str
    close: float
    ema20: float
    ema50: float
    ema100: float
    ema200: float
    rsi7: float
    macd_line: float
    macd_signal: float
    macd_histogram: float
    volume_ratio: float
    atr14: float
    score: float
    verdict: str
    reasons: list[str]


def load_env_file(path: Path) -> None:
    if not path.exists():
        return

    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip("'").strip('"')
        if key and key not in os.environ:
            os.environ[key] = value


def http_get_text(url: str, timeout: int = 8) -> str:
    request = urllib.request.Request(url, headers=HEADERS)
    last_error: Exception | None = None
    for attempt in range(2):
        try:
            with urllib.request.urlopen(request, timeout=timeout) as response:
                return response.read().decode("utf-8", "ignore")
        except urllib.error.HTTPError as exc:
            last_error = exc
            if exc.code not in {429, 500, 502, 503, 504} or attempt == 1:
                raise
        except urllib.error.URLError as exc:
            last_error = exc
            if attempt == 1:
                raise
        time.sleep(1.0 * (attempt + 1))
    raise RuntimeError(f"Echec HTTP pour {url}: {last_error}")


def append_source_error(
    source_id: str,
    url: str,
    error: Exception | str,
    criticality: str = "medium",
    path: Path = SOURCE_ERRORS_PATH,
) -> None:
    entry = {
        "timestamp": iso_now(),
        "source_id": source_id,
        "url": url,
        "error": str(error),
        "criticality": criticality,
    }
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        rotate_jsonl_file(path)
        with path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(entry, ensure_ascii=False, sort_keys=True) + "\n")
    except Exception:
        pass


def load_feed_hash_cache(path: Path = FEED_HASH_CACHE_PATH) -> dict[str, str]:
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}
    return {str(key): str(value) for key, value in data.items()} if isinstance(data, dict) else {}


def recent_source_error_warnings(path: Path = SOURCE_ERRORS_PATH, limit: int = 80) -> list[str]:
    if not path.exists():
        return []
    try:
        lines = path.read_text(encoding="utf-8").splitlines()[-limit:]
    except Exception:
        return []
    errors: list[dict[str, Any]] = []
    for line in lines:
        try:
            item = json.loads(line)
        except Exception:
            continue
        if isinstance(item, dict):
            errors.append(item)
    source_ids = {str(item.get("source_id", "")) for item in errors}
    warnings: list[str] = []
    if any("trump" in source_id for source_id in source_ids) and any("white_house" in source_id for source_id in source_ids):
        warnings.append("Trump/White House feeds degradés: fallback Google News/Reuters requis pour statements politiques.")
    high_errors = [item for item in errors if item.get("criticality") == "high"]
    if len(high_errors) >= 3:
        warnings.append(f"{len(high_errors)} erreurs feed critiques recentes dans source_errors.jsonl.")
    return warnings[:3]


def save_feed_hash_cache(cache: dict[str, str], path: Path = FEED_HASH_CACHE_PATH) -> None:
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(cache, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")
    except Exception:
        pass


def stable_news_hash(title: str, link: str, published_at: str = "") -> str:
    base = f"{normalize_title_for_dedupe(title)}|{link.strip()}|{published_at[:16]}"
    return hashlib.sha1(base.encode("utf-8")).hexdigest()[:16]


def fetch_rss_root(source_id: str, url: str, timeout: int = 8, criticality: str = "medium") -> ET.Element | None:
    try:
        return ET.fromstring(http_get_text(url, timeout=timeout).lstrip("\ufeff"))
    except Exception as exc:
        append_source_error(source_id, url, exc, criticality=criticality)
        return None


def fetch_nitter_feed_with_fallback(account: str, mirrors: list[str]) -> tuple[str, ET.Element] | None:
    for mirror_url in mirrors:
        root = fetch_rss_root(f"nitter_{account}", mirror_url, timeout=4, criticality="high")
        if root is not None:
            return mirror_url, root
    append_source_error(f"nitter_{account}", ",".join(mirrors), "all_nitter_mirrors_down", criticality="high")
    return None


def google_news_search_url(query: str) -> str:
    encoded_query = urllib.parse.quote(query, safe='()":')
    return f"https://news.google.com/rss/search?q={encoded_query}&hl=en-US&gl=US&ceid=US:en"


def http_get_json(url: str) -> dict[str, Any]:
    return json.loads(http_get_text(url))


def http_get_next_data(url: str) -> dict[str, Any]:
    text = http_get_text(url)
    match = re.search(
        r'<script id="__NEXT_DATA__" type="application/json">(.*?)</script>',
        text,
        re.DOTALL,
    )
    if not match:
        raise RuntimeError(f"Impossible de lire les donnees internes de la page {url}.")
    return json.loads(match.group(1))


def compact_whitespace(value: str) -> str:
    return re.sub(r"\s+", " ", value).strip()


def strip_source_suffix(title: str, source: str) -> str:
    suffix = f" - {source}".strip()
    if source and title.endswith(suffix):
        return title[: -len(suffix)].strip()
    return title


def normalize_title_for_dedupe(title: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", title.lower()).strip()


WEAK_NEWS_SOURCES = (
    "msn",
    "fxempire",
    "litefinance",
    "moomoo",
    "coinmarketcap",
    "traders union",
    "startup fortune",
    "barchart",
    "benzinga",
)

LOW_VALUE_HEADLINE_PATTERNS = (
    "forecast",
    "prediction",
    "price prediction",
    "outlook",
    "next week",
    "next month",
    "analysis today",
    "technical analysis",
    "how to trade",
    "what to expect",
    "could hit",
    "may hit",
    "might hit",
    "expert predicts",
)

NEWS_NOISE_PATTERNS = (
    "rt @",
    "rt by @",
    "r to @",
    "🇺🇸🇨🇳",
    "🇨🇳🇺🇸",
    "national hospital week",
    "presidential message",
    "the courage to build",
    "a powerful arrival",
    "history in motion",
    "ceremony plays",
    "arrival ceremony",
    "star-spangled banner",
    "it's an honor",
    "if you'd like to see",
    "sorry that happened",
    "state banquet",
    "delivers remarks at the state banquet",
    "reflecting pool",
    "washington monument",
    "lincoln memorial",
    "law enforcement",
    "nominations sent",
    "first lady",
    "foster youth",
    "peace officers memorial",
    "police week",
    "signed into law",
    "america's moms",
    "support for families",
    "termination of enforcement actions",
    "approval of related applications",
)


def news_source_identity(source: str, link: str = "") -> str:
    text = f"{source} {link}".lower()
    if "trumpstruth.org" in text or "truth social" in text:
        return "Truth Social"
    if "nitter" in text and "realdonaldtrump" in text:
        return "Nitter Trump"
    if "nitter" in text and "whitehouse" in text:
        return "Nitter White House"
    if "whitehouse.gov" in text:
        return "White House"
    if "federalreserve.gov" in text:
        return "Federal Reserve"
    if "bls.gov" in text:
        return "BLS"
    if "ecb.europa.eu" in text:
        return "ECB"
    if "bankofengland.co.uk" in text:
        return "Bank of England"
    if "boj.or.jp" in text:
        return "Bank of Japan"
    if "home.treasury.gov" in text or "treasury.gov" in text:
        return "US Treasury"
    if "bea.gov" in text:
        return "BEA"
    if "cftc.gov" in text:
        return "CFTC"
    if "gold.org" in text:
        return "World Gold Council"
    if "apnews.com" in text or "associated press" in text:
        return "Associated Press"
    if "reuters.com" in text or "reuters" in text:
        return "Reuters"
    if "bloomberg.com" in text or "bloomberg" in text:
        return "Bloomberg"
    if "cnbc.com" in text or "cnbc" in text:
        return "CNBC"
    return compact_whitespace(source) or "RSS"


def news_source_tier(source: str, link: str = "") -> int:
    text = f"{source} {link}".lower()
    if any(token in text for token in ("whitehouse.gov", "truth social", "trumpstruth.org", "nitter trump", "nitter white house", "federalreserve.gov", "bls.gov", "treasury.gov", "bea.gov", "cftc.gov", "gold.org", "ecb.europa.eu", "bankofengland.co.uk", "boj.or.jp")):
        return 1
    if any(token in text for token in ("reuters", "apnews.com", "associated press", "bloomberg", "wsj", "financial times")):
        return 2
    if any(token in text for token in ("cnbc", "marketwatch", "kitco", "forexlive", "investing.com", "yahoo finance")):
        return 3
    if any(token in text for token in WEAK_NEWS_SOURCES):
        return 5
    return 4


def headline_age_minutes(item: NewsItem, now: datetime | None = None) -> float | None:
    published = parse_iso_datetime(item.published_at)
    if published is None:
        return None
    reference = now or datetime.now(timezone.utc)
    return max(0.0, (reference - published).total_seconds() / 60)


def should_skip_headline(title: str, source: str) -> bool:
    text = f"{title} {source}".lower()
    blocked_patterns = [
        "chart image",
        "tradingview",
        "forexcom:xauusd",
        "nostradamus",
        "check prediction here",
        "horoscope",
        *WEAK_NEWS_SOURCES,
        *LOW_VALUE_HEADLINE_PATTERNS,
        *NEWS_NOISE_PATTERNS,
    ]
    return any(pattern in text for pattern in blocked_patterns)


def is_news_item_exploitable(item: NewsItem, now: datetime | None = None) -> bool:
    if should_skip_headline(item.title, item.source):
        return False
    tier = news_source_tier(item.source, item.link)
    if tier >= 4:
        return False
    age = headline_age_minutes(item, now=now)
    if age is None:
        return False
    max_age = 7 * 24 * 60 if tier == 1 else 48 * 60
    if age > max_age:
        return False
    if item.score == 0 and tier > 2:
        return False
    return True


def news_similarity(left: str, right: str) -> float:
    left_tokens = set(normalize_title_for_dedupe(left).split())
    right_tokens = set(normalize_title_for_dedupe(right).split())
    if not left_tokens or not right_tokens:
        return 0.0
    intersection = len(left_tokens & right_tokens)
    union = len(left_tokens | right_tokens)
    return intersection / union if union else 0.0


def is_duplicate_news_title(title: str, seen_titles: set[str], threshold: float = 0.65) -> bool:
    normalized = normalize_title_for_dedupe(title)
    if not normalized:
        return True
    if normalized in seen_titles:
        return True
    prefix = " ".join(normalized.split()[:7])
    for seen in seen_titles:
        if prefix and seen.startswith(prefix):
            return True
        if news_similarity(normalized, seen) >= threshold:
            return True
    return False


def keyword_matches(text: str, keyword: str) -> bool:
    normalized_text = re.sub(r"[^a-z0-9]+", " ", text.lower()).strip()
    normalized_keyword = re.sub(r"[^a-z0-9]+", " ", keyword.lower()).strip()
    if keyword == "geopolit":
        return "geopolit" in normalized_text
    pattern = rf"(?<![a-z0-9]){re.escape(normalized_keyword)}(?![a-z0-9])"
    return re.search(pattern, normalized_text) is not None


def iso_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


SOURCE_REGISTRY: dict[str, SourceRegistryEntry] = {
    "investing_xauusd": SourceRegistryEntry("investing_xauusd", "Investing.com XAU/USD", "price", 2, 30, True, INVESTING_XAUUSD_URL, ["PriceActionAgent", "RiskManagerAgent"]),
    "ig_weekend_gold": SourceRegistryEntry("ig_weekend_gold", "IG Weekend Gold", "price", 3, 120, False, IG_WEEKEND_GOLD_URL, ["PriceActionAgent", "RiskManagerAgent"]),
    "fred_dgs10": SourceRegistryEntry("fred_dgs10", "FRED DGS10", "rates", 1, 10080, True, FRED_CSV_URL_TEMPLATE.format(series_id="DGS10"), ["MacroAgent", "RiskManagerAgent"]),
    "fred_dgs2": SourceRegistryEntry("fred_dgs2", "FRED DGS2", "rates", 1, 10080, False, FRED_CSV_URL_TEMPLATE.format(series_id="DGS2"), ["MacroAgent"]),
    "fred_dgs3m": SourceRegistryEntry("fred_dgs3m", "FRED DGS3MO", "rates", 1, 10080, False, FRED_CSV_URL_TEMPLATE.format(series_id="DGS3MO"), ["MacroAgent"]),
    "fred_dgs30": SourceRegistryEntry("fred_dgs30", "FRED DGS30", "rates", 1, 10080, False, FRED_CSV_URL_TEMPLATE.format(series_id="DGS30"), ["MacroAgent"]),
    "fred_t10yie": SourceRegistryEntry("fred_t10yie", "FRED T10YIE", "macro", 1, 10080, False, FRED_CSV_URL_TEMPLATE.format(series_id="T10YIE"), ["MacroAgent"]),
    "fred_dfii10": SourceRegistryEntry("fred_dfii10", "FRED DFII10", "rates", 1, 10080, True, FRED_DFII10_CSV_URL, ["MacroAgent", "RiskManagerAgent"]),
    "cftc_cot_gold": SourceRegistryEntry("cftc_cot_gold", "CFTC COT Gold", "flows", 1, 14400, True, CFTC_DISAGG_CURRENT_URL, ["FlowPositioningAgent", "RiskManagerAgent"]),
    "wgc_etf_flows": SourceRegistryEntry("wgc_etf_flows", "World Gold Council ETF flows", "flows", 1, 14400, True, WGC_ETF_FLOWS_PAGE_URL, ["FlowPositioningAgent", "CorrelationAgent"]),
    "macro_catalysts": SourceRegistryEntry("macro_catalysts", "Fed/BEA Macro Catalysts", "macro", 1, 1440, True, FED_FOMC_CALENDAR_URL, ["MacroAgent", "RiskManagerAgent"]),
    "google_news_rss": SourceRegistryEntry("google_news_rss", "Google News RSS / fallback feeds", "news", 5, 2880, False, "https://news.google.com/rss", ["SentimentNewsAgent", "EventFactsAgent"]),
    "white_house_feed": SourceRegistryEntry("white_house_feed", "White House News feed", "political_statements", 1, 10080, False, WHITE_HOUSE_NEWS_FEED_URL, ["TrumpPoliticalStatementsAgent"]),
    "news_official_feeds": SourceRegistryEntry("news_official_feeds", "Official news feeds", "news", 1, 1440, False, WHITE_HOUSE_NEWS_FEED_URL, ["SentimentNewsAgent", "EventFactsAgent", "TrumpPoliticalStatementsAgent"]),
    "news_fast_feeds": SourceRegistryEntry("news_fast_feeds", "AP/CNBC/Reuters/Bloomberg direct news feeds", "news", 2, 120, False, CNBC_MARKETS_FEED_URL, ["SentimentNewsAgent", "EventFactsAgent"]),
    "critical_fast_feeds": SourceRegistryEntry("critical_fast_feeds", "Critical fast feeds", "news", 1, 30, False, TRUMP_TRUTH_SOCIAL_FEED_URL, ["SentimentNewsAgent", "EventFactsAgent", "TrumpPoliticalStatementsAgent"]),
    "cross_asset_yahoo": SourceRegistryEntry("cross_asset_yahoo", "Yahoo cross-assets", "technical", 2, 240, True, "https://finance.yahoo.com/", ["CorrelationAgent", "PriceActionAgent"]),
    "oil_context": SourceRegistryEntry("oil_context", "WTI/Brent oil context", "oil", 2, 240, False, "https://finance.yahoo.com/", ["GeopoliticalOilShockAgent", "RiskManagerAgent"]),
    "chart_store_ohlc": SourceRegistryEntry("chart_store_ohlc", "Chart Store OHLC", "chart", 2, 240, False, "https://finance.yahoo.com/quote/GC=F/", ["TechnicalAgent"]),
}


HARD_TRADE_BLOCKING_SOURCE_IDS = {"investing_xauusd"}
DECISION_AGENT_NAMES = {
    "PriceActionAgent",
    "PriceAgent",
    "TechnicalAgent",
    "MacroAgent",
    "GeopoliticalOilShockAgent",
    "SentimentNewsAgent",
    "CorrelationAgent",
    "FlowPositioningAgent",
}
AGENT_NAME_ALIASES = {"PriceAgent": "PriceActionAgent"}
ALL_AGENT_NAMES = {
    *(DECISION_AGENT_NAMES - {"PriceAgent"}),
    "EventFactsAgent",
    "TrumpPoliticalStatementsAgent",
    "RiskManagerAgent",
}


def default_user_settings() -> UserSettings:
    return UserSettings(active_agents=sorted(ALL_AGENT_NAMES))


def validate_user_settings(settings: UserSettings, path: Path = SETTINGS_PATH, created_default: bool = False) -> SettingsValidation:
    warnings: list[str] = []
    settings.active_agents = sorted(set(AGENT_NAME_ALIASES.get(agent, agent) for agent in settings.active_agents))
    allowed_modes = {"conservative", "balanced", "aggressive_controlled"}
    if settings.scoring_mode not in allowed_modes:
        warnings.append(f"scoring_mode inconnu: {settings.scoring_mode}; fallback balanced.")
        settings.scoring_mode = "balanced"
    settings.minimum_agent_confidence = max(65, min(100, int(settings.minimum_agent_confidence)))
    settings.watch_threshold = max(0, min(100, int(settings.watch_threshold)))
    settings.trade_threshold = max(65, min(100, int(settings.trade_threshold)))
    settings.cooldown_minutes = max(0, min(1440, int(settings.cooldown_minutes)))
    settings.cooldown_after_loss_minutes = max(240, min(1440, int(settings.cooldown_after_loss_minutes)))
    settings.cooldown_after_win_minutes = max(60, min(1440, int(settings.cooldown_after_win_minutes)))
    settings.cooldown_after_expired_minutes = max(60, min(1440, int(settings.cooldown_after_expired_minutes)))
    settings.max_trades_per_24h = max(1, min(50, int(settings.max_trades_per_24h)))
    settings.circuit_breaker_after_n_losses = max(1, min(20, int(settings.circuit_breaker_after_n_losses)))
    settings.circuit_breaker_window_hours = max(1, min(168, int(settings.circuit_breaker_window_hours)))
    settings.circuit_breaker_pause_hours = max(1, min(72, int(settings.circuit_breaker_pause_hours)))
    settings.minimum_risk_reward = max(1.5, min(5.0, float(settings.minimum_risk_reward)))
    settings.min_data_quality = max(60, min(100, int(settings.min_data_quality)))
    settings.no_trade_window_minutes_before_high_macro = max(0, min(240, int(settings.no_trade_window_minutes_before_high_macro)))
    settings.no_trade_window_minutes_after_high_macro = max(0, min(240, int(settings.no_trade_window_minutes_after_high_macro)))
    unknown_agents = [agent for agent in settings.active_agents if agent not in ALL_AGENT_NAMES]
    if unknown_agents:
        warnings.append("agents inconnus ignores: " + ", ".join(sorted(unknown_agents)))
        settings.active_agents = [agent for agent in settings.active_agents if agent in ALL_AGENT_NAMES]
    if not settings.active_agents:
        warnings.append("aucun agent actif valide; fallback agents par defaut.")
        settings.active_agents = sorted(ALL_AGENT_NAMES)
    if settings.scoring_mode == "conservative":
        settings.trade_threshold = max(settings.trade_threshold, 70)
        settings.minimum_risk_reward = max(settings.minimum_risk_reward, 1.8)
    return SettingsValidation(
        path=str(path),
        status="OK" if not warnings else "WARN",
        warnings=warnings,
        created_default=created_default,
    )


def parse_user_settings(data: dict[str, Any] | None) -> UserSettings:
    defaults = default_user_settings()
    if not isinstance(data, dict):
        return defaults
    return UserSettings(
        active_agents=[str(item) for item in data.get("active_agents", defaults.active_agents)],
        scoring_mode=str(data.get("scoring_mode", defaults.scoring_mode)),
        minimum_agent_confidence=int(data.get("minimum_agent_confidence", defaults.minimum_agent_confidence) or defaults.minimum_agent_confidence),
        watch_threshold=int(data.get("watch_threshold", defaults.watch_threshold) or defaults.watch_threshold),
        trade_threshold=int(data.get("trade_threshold", defaults.trade_threshold) or defaults.trade_threshold),
        cooldown_minutes=int(data.get("cooldown_minutes", defaults.cooldown_minutes) or defaults.cooldown_minutes),
        cooldown_after_loss_minutes=int(data.get("cooldown_after_loss_minutes", defaults.cooldown_after_loss_minutes) or defaults.cooldown_after_loss_minutes),
        cooldown_after_win_minutes=int(data.get("cooldown_after_win_minutes", defaults.cooldown_after_win_minutes) or defaults.cooldown_after_win_minutes),
        cooldown_after_expired_minutes=int(data.get("cooldown_after_expired_minutes", defaults.cooldown_after_expired_minutes) or defaults.cooldown_after_expired_minutes),
        max_trades_per_24h=int(data.get("max_trades_per_24h", defaults.max_trades_per_24h) or defaults.max_trades_per_24h),
        circuit_breaker_after_n_losses=int(data.get("circuit_breaker_after_n_losses", defaults.circuit_breaker_after_n_losses) or defaults.circuit_breaker_after_n_losses),
        circuit_breaker_window_hours=int(data.get("circuit_breaker_window_hours", defaults.circuit_breaker_window_hours) or defaults.circuit_breaker_window_hours),
        circuit_breaker_pause_hours=int(data.get("circuit_breaker_pause_hours", defaults.circuit_breaker_pause_hours) or defaults.circuit_breaker_pause_hours),
        minimum_risk_reward=float(data.get("minimum_risk_reward", defaults.minimum_risk_reward) or defaults.minimum_risk_reward),
        min_data_quality=int(data.get("min_data_quality", defaults.min_data_quality) or defaults.min_data_quality),
        no_trade_window_minutes_before_high_macro=int(data.get("no_trade_window_minutes_before_high_macro", defaults.no_trade_window_minutes_before_high_macro) or defaults.no_trade_window_minutes_before_high_macro),
        no_trade_window_minutes_after_high_macro=int(data.get("no_trade_window_minutes_after_high_macro", defaults.no_trade_window_minutes_after_high_macro) or defaults.no_trade_window_minutes_after_high_macro),
        notifications_enabled=bool(data.get("notifications_enabled", defaults.notifications_enabled)),
    )


def load_user_settings(path: Path = SETTINGS_PATH, create_if_missing: bool = False) -> tuple[UserSettings, SettingsValidation]:
    created_default = False
    if not path.exists():
        settings = default_user_settings()
        if create_if_missing:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(json.dumps(asdict(settings), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
            created_default = True
        validation = validate_user_settings(settings, path=path, created_default=created_default)
        if not created_default:
            validation.warnings.append("settings local absent; defaults utilises en memoire.")
            validation.status = "WARN"
        return settings, validation
    try:
        settings = parse_user_settings(json.loads(path.read_text(encoding="utf-8")))
    except Exception as exc:
        settings = default_user_settings()
        validation = validate_user_settings(settings, path=path)
        validation.status = "WARN"
        validation.warnings.append(f"settings illisible; defaults utilises: {exc}")
        return settings, validation
    return settings, validate_user_settings(settings, path=path)


def save_user_settings(settings: UserSettings, path: Path = SETTINGS_PATH) -> SettingsValidation:
    validation = validate_user_settings(settings, path=path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(asdict(settings), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return validation


def set_agent_enabled(agent_name: str, enabled: bool, path: Path = SETTINGS_PATH) -> tuple[UserSettings, SettingsValidation]:
    if agent_name not in ALL_AGENT_NAMES:
        settings, validation = load_user_settings(path=path, create_if_missing=True)
        validation.status = "WARN"
        validation.warnings.append(f"agent inconnu: {agent_name}")
        return settings, validation
    settings, _validation = load_user_settings(path=path, create_if_missing=True)
    active = set(settings.active_agents)
    if enabled:
        active.add(agent_name)
    else:
        active.discard(agent_name)
    settings.active_agents = sorted(active)
    validation = save_user_settings(settings, path=path)
    return settings, validation


def human_regime_name(name: str | None) -> str:
    mapping = {
        "Hormuz / Oil Shock": "Regime politique / petrole",
        "De-escalation / Oil Relief": "Detente politique / petrole",
        "Dollar Liquidity Squeeze": "Stress dollar / liquidite",
        "Safe-Haven Gold": "Refuge or",
    }
    if not name:
        return "Normal Macro"
    return mapping.get(name, name)


def source_registry_entries() -> list[SourceRegistryEntry]:
    return list(SOURCE_REGISTRY.values())


def age_minutes_from_iso(iso_text: str | None, now: datetime | None = None) -> int | None:
    if not iso_text:
        return None
    parsed = parse_iso_datetime(str(iso_text))
    if parsed is None:
        return None
    reference = now or datetime.now(timezone.utc)
    return max(0, round((reference - parsed).total_seconds() / 60))


def snapshot_status(entry: SourceRegistryEntry, present: bool, age_minutes: int | None) -> str:
    if not present:
        return "missing"
    if age_minutes is not None and age_minutes > entry.max_age_minutes:
        return "stale"
    if entry.tier >= 4:
        return "weak"
    return "ok"


def make_source_snapshot(
    source_id: str,
    present: bool,
    last_update: str | None,
    value_summary: str,
    now: datetime | None = None,
) -> SourceSnapshot:
    entry = SOURCE_REGISTRY[source_id]
    age = age_minutes_from_iso(last_update, now=now)
    status = snapshot_status(entry, present, age)
    return SourceSnapshot(
        source_id=entry.source_id,
        name=entry.name,
        category=entry.category,
        tier=entry.tier,
        status=status,
        last_update=last_update if present else None,
        age_minutes=age if present else None,
        value_summary=value_summary if present else "source absente",
        source_url=entry.source_url,
        critical=entry.critical,
        allowed_agents=entry.allowed_agents,
    )


def data_quality_status(score: int) -> str:
    if score >= 85:
        return "HIGH"
    if score >= 70:
        return "USABLE"
    if score >= 55:
        return "DEGRADED"
    return "WEAK"


class DataRouter:
    def __init__(self, snapshots: list[SourceSnapshot]) -> None:
        self.snapshots = snapshots

    def build_routes(self) -> list[DataRoute]:
        routes: list[DataRoute] = []
        for snapshot in self.snapshots:
            status, mode, message = preflight_route_state(snapshot)
            routes.append(
                DataRoute(
                    source_id=snapshot.source_id,
                    source_name=snapshot.name,
                    category=snapshot.category,
                    target_agents=snapshot.allowed_agents,
                    required=snapshot.critical,
                    status=status,
                    mode=mode,
                    message=message,
                )
            )
        return routes


def preflight_route_state(snapshot: SourceSnapshot) -> tuple[str, str, str]:
    hard_required = snapshot.source_id in HARD_TRADE_BLOCKING_SOURCE_IDS
    if snapshot.status == "ok":
        return "READY", "READY", f"{snapshot.name}: source exploitable pour {', '.join(snapshot.allowed_agents[:2])}."
    if snapshot.status == "stale":
        status = "SOURCE_STALE" if hard_required else "DEGRADED"
        mode = "BLOCKING" if hard_required else "WARNING"
        return status, mode, f"{snapshot.name}: donnees trop anciennes ({snapshot.age_minutes or 'n/a'} min)."
    if snapshot.status == "missing":
        status = "NO_TRADE_DATA" if hard_required else "DEGRADED"
        mode = "BLOCKING" if hard_required else "WARNING"
        return status, mode, f"{snapshot.name}: source absente."
    return "DEGRADED", "WARNING", f"{snapshot.name}: source faible ou a confirmer."


def build_preflight_check(
    snapshots: list[SourceSnapshot],
    data_quality_score: int,
    generated_at: str,
) -> PreflightCheck:
    routes = DataRouter(snapshots).build_routes()
    hard_routes = [route for route in routes if route.source_id in HARD_TRADE_BLOCKING_SOURCE_IDS]
    blockers = [route.message for route in routes if route.mode == "BLOCKING"]
    warnings = [route.message for route in routes if route.mode == "WARNING"]

    price_route = next((route for route in routes if route.source_id == "investing_xauusd"), None)
    if price_route and price_route.status == "SOURCE_STALE":
        status = "SOURCE_STALE"
    elif price_route and price_route.status == "NO_TRADE_DATA":
        status = "NO_TRADE_DATA"
    elif any(route.status == "NO_TRADE_DATA" for route in hard_routes):
        status = "NO_TRADE_DATA"
    elif any(route.status == "SOURCE_STALE" for route in hard_routes):
        status = "SOURCE_STALE"
    elif hard_routes and not any(route.status == "READY" for route in hard_routes):
        status = "OFFLINE"
    elif data_quality_score < 55 or warnings:
        status = "DEGRADED"
    else:
        status = "READY"

    trade_blocked = status in {"OFFLINE", "NO_TRADE_DATA", "SOURCE_STALE"} or data_quality_score < 45
    if status == "READY":
        summary = "Preflight READY: sources critiques exploitables, trade gate autorise cote data."
    elif status == "DEGRADED":
        summary = "Preflight DEGRADED: dashboard consultable, confiance reduite sur les sources secondaires."
    elif status == "SOURCE_STALE":
        summary = "Preflight SOURCE_STALE: au moins une source critique est trop ancienne, trade bloque."
    elif status == "NO_TRADE_DATA":
        summary = "Preflight NO_TRADE_DATA: une source critique manque, aucun nouveau trade ne doit etre cree."
    else:
        summary = "Preflight OFFLINE: les sources critiques ne suffisent pas pour analyser un setup."

    return PreflightCheck(
        generated_at=generated_at,
        status=status,
        summary=summary,
        trade_blocked=trade_blocked,
        blockers=blockers[:8],
        warnings=warnings[:8],
        routes=routes,
    )


def parse_trade_plan(data: dict[str, Any]) -> TradePlan:
    return TradePlan(
        trade_id=str(data.get("trade_id", "")),
        created_at=str(data.get("created_at", iso_now())),
        updated_at=str(data.get("updated_at", data.get("created_at", iso_now()))),
        status=str(data.get("status", "pending")),
        direction=str(data.get("direction", "BUY")),
        entry_type=str(data.get("entry_type", "market_reference")),
        reference_price=float(data.get("reference_price", 0.0) or 0.0),
        entry_zone_low=float(data.get("entry_zone_low", 0.0) or 0.0),
        entry_zone_high=float(data.get("entry_zone_high", 0.0) or 0.0),
        stop_loss=float(data.get("stop_loss", 0.0) or 0.0),
        tp1=float(data.get("tp1", 0.0) or 0.0),
        tp2=float(data.get("tp2", 0.0) or 0.0),
        tp3=float(data.get("tp3", 0.0) or 0.0),
        risk_reward_tp1=float(data.get("risk_reward_tp1", 0.0) or 0.0),
        risk_reward_tp2=float(data.get("risk_reward_tp2", 0.0) or 0.0),
        risk_reward_tp3=float(data.get("risk_reward_tp3", 0.0) or 0.0),
        max_valid_until=str(data.get("max_valid_until", iso_now())),
        source_signal_id=str(data.get("source_signal_id", "")),
        global_score_at_creation=int(data.get("global_score_at_creation", 0) or 0),
        data_quality_score=int(data.get("data_quality_score", 0) or 0),
        confidence_score=int(data.get("confidence_score", 0) or 0),
        market_regime=str(data.get("market_regime", "Normal Macro")),
        agents_validating=[str(item) for item in data.get("agents_validating", [])],
        agents_contradicting=[str(item) for item in data.get("agents_contradicting", [])],
        evidence_sources=[str(item) for item in data.get("evidence_sources", [])],
        event_facts_snapshot=[str(item) for item in data.get("event_facts_snapshot", [])],
        technical_snapshot=str(data.get("technical_snapshot", "")),
        macro_snapshot=str(data.get("macro_snapshot", "")),
        geopolitical_snapshot=str(data.get("geopolitical_snapshot", "")),
        elliott_wave_snapshot=str(data.get("elliott_wave_snapshot", "")),
        invalidation_rules=[str(item) for item in data.get("invalidation_rules", [])],
        outcome=str(data.get("outcome", "open")),
        outcome_reason=str(data.get("outcome_reason", "")),
        closed_at=str(data.get("closed_at")) if data.get("closed_at") else None,
        record_type=str(data.get("record_type", "trade_exploitable")),
        scenario_snapshot=str(data.get("scenario_snapshot", "")),
        useful_agents=[str(item) for item in data.get("useful_agents", [])],
        misleading_agents=[str(item) for item in data.get("misleading_agents", [])],
        missed_condition=str(data.get("missed_condition", "")),
        post_mortem=str(data.get("post_mortem", "")),
        r_multiple=float(data.get("r_multiple", 0.0) or 0.0),
        duration_minutes=int(data.get("duration_minutes", 0) or 0),
    )


def load_trade_ledger(path: Path = TRADE_LEDGER_PATH) -> list[TradePlan]:
    if not path.exists():
        return []
    latest_by_id: dict[str, TradePlan] = {}
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        if not raw_line.strip():
            continue
        try:
            plan = parse_trade_plan(json.loads(raw_line))
        except Exception:
            continue
        if plan.trade_id:
            latest_by_id[plan.trade_id] = plan
    return sorted(latest_by_id.values(), key=lambda item: item.created_at, reverse=True)


def trade_plan_public_dict(plan: TradePlan) -> dict[str, Any]:
    payload = asdict(plan)
    payload.pop("elliott_wave_snapshot", None)
    return payload


def trade_ledger_public_dict(ledger: TradeLedgerSummary) -> dict[str, Any]:
    payload = asdict(ledger)
    payload["active_trades"] = [trade_plan_public_dict(plan) for plan in ledger.active_trades]
    payload["recent_trades"] = [trade_plan_public_dict(plan) for plan in ledger.recent_trades]
    payload["plans"] = payload["active_trades"]
    return payload


def append_trade_plan_snapshot(plan: TradePlan, path: Path = TRADE_LEDGER_PATH) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(asdict(plan), ensure_ascii=False, sort_keys=True) + "\n")


def rotate_jsonl_file(path: Path, max_bytes: int = AUDIT_ROTATION_MAX_BYTES, max_archives: int = AUDIT_ARCHIVE_MAX_FILES) -> None:
    if not path.exists() or path.stat().st_size < max_bytes:
        return
    archive_dir = path.parent / "archive"
    archive_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    archive_path = archive_dir / f"{path.stem}.{timestamp}.jsonl"
    path.replace(archive_path)
    archives = sorted(archive_dir.glob(f"{path.stem}.*.jsonl"), key=lambda item: item.stat().st_mtime, reverse=True)
    for old_archive in archives[max_archives:]:
        try:
            old_archive.unlink()
        except OSError:
            pass


def trade_gate_audit_path_for_ledger(path: Path = TRADE_LEDGER_PATH) -> Path:
    if path == TRADE_LEDGER_PATH:
        return TRADE_GATE_AUDIT_PATH
    return path.with_name("trade_gate_audit.jsonl")


def append_trade_gate_audit_event(
    action: str,
    reasons: list[str],
    candidate: TradePlan | None = None,
    path: Path = TRADE_GATE_AUDIT_PATH,
    now: datetime | None = None,
    extra: dict[str, Any] | None = None,
) -> None:
    reference = now or datetime.now(timezone.utc)
    payload: dict[str, Any] = {
        "created_at": reference.replace(microsecond=0).isoformat(),
        "action": action,
        "reasons": reasons[:8],
    }
    if candidate is not None:
        payload.update(
            {
                "trade_id": candidate.trade_id,
                "direction": candidate.direction,
                "status": candidate.status,
                "outcome": candidate.outcome,
                "reference_price": candidate.reference_price,
                "stop_loss": candidate.stop_loss,
                "tp1": candidate.tp1,
                "tp2": candidate.tp2,
                "tp3": candidate.tp3,
                "rr_tp1": candidate.risk_reward_tp1,
                "market_regime": candidate.market_regime,
                "valid_until": candidate.max_valid_until,
            }
        )
    if extra:
        payload.update(extra)
    path.parent.mkdir(parents=True, exist_ok=True)
    rotate_jsonl_file(path)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(payload, ensure_ascii=False, sort_keys=True) + "\n")


def trade_plan_closed(plan: TradePlan) -> bool:
    return plan.status in {"tp2_hit", "tp3_hit", "sl_hit", "expired", "invalidated", "closed_manual"}


def trade_plan_is_active(plan: TradePlan) -> bool:
    if trade_plan_closed(plan):
        return False
    return plan.outcome in {"open", "partial", ""} and plan.status in {"pending", "active", "tp1_hit"}


def compute_risk_reward(direction: str, entry: float, stop_loss: float, target: float) -> float:
    risk = abs(entry - stop_loss)
    reward = abs(target - entry)
    if risk <= 0:
        return 0.0
    return round(reward / risk, 2)


def trade_signal_id(direction: str, market_regime: str, reference_price: float, score: int) -> str:
    base = f"{direction}|{market_regime}|{round(reference_price / 5) * 5:.0f}|{score // 5 * 5}"
    return hashlib.sha1(base.encode("utf-8")).hexdigest()[:12]


def trade_record_type(plan: TradePlan) -> str:
    if plan.status == "expired" or plan.outcome == "expired":
        return "trade_expire"
    if plan.status in {"invalidated", "closed_manual"} or plan.outcome == "invalidated":
        return "trade_invalide"
    if plan.status in {"pending", "watch", "setup"}:
        return "setup_surveille"
    return "trade_exploitable"


def trade_duration_minutes(plan: TradePlan) -> int:
    created = parse_iso_datetime(plan.created_at)
    ended = parse_iso_datetime(plan.closed_at or plan.updated_at)
    if created is None or ended is None:
        return 0
    return max(0, round((ended - created).total_seconds() / 60))


def trade_realized_r(plan: TradePlan) -> float:
    if plan.outcome == "loss" or plan.status == "sl_hit":
        return -1.0
    if plan.outcome == "partial" or plan.status == "tp1_hit":
        return max(0.0, plan.risk_reward_tp1)
    if plan.outcome == "win":
        if plan.status == "tp3_hit":
            return max(plan.risk_reward_tp3, plan.risk_reward_tp2, plan.risk_reward_tp1)
        if plan.status == "tp2_hit":
            return max(plan.risk_reward_tp2, plan.risk_reward_tp1)
        return max(plan.risk_reward_tp1, 1.0)
    return 0.0


def build_trade_post_mortem(plan: TradePlan) -> TradePostMortem:
    record_type = trade_record_type(plan)
    r_multiple = trade_realized_r(plan)
    duration = trade_duration_minutes(plan)
    if plan.outcome == "win":
        useful_agents = plan.agents_validating
        misleading_agents = plan.agents_contradicting
        missed_condition = "Aucune condition manquee majeure detectee."
        summary = f"Win {r_multiple:+.2f}R: direction {plan.direction} confirmee apres {duration} min."
    elif plan.outcome == "partial":
        useful_agents = plan.agents_validating
        misleading_agents = plan.agents_contradicting
        missed_condition = "Le mouvement a atteint TP1 sans extension complete."
        summary = f"Partial {r_multiple:+.2f}R: TP1 touche puis suivi encore ouvert ou incomplet."
    elif plan.outcome == "loss":
        useful_agents = plan.agents_contradicting
        misleading_agents = plan.agents_validating
        missed_condition = "Le SL a ete touche avant validation d'une extension favorable."
        summary = f"Loss {r_multiple:+.2f}R: SL touche apres {duration} min. Agents a revoir: {', '.join(misleading_agents) or 'n/a'}."
    elif plan.outcome == "expired":
        useful_agents = plan.agents_contradicting
        misleading_agents = plan.agents_validating
        missed_condition = "Temps de validite expire sans TP/SL: impulsion insuffisante."
        summary = f"Expired {r_multiple:+.2f}R: le trade n'a pas atteint TP/SL avant expiration."
    elif plan.outcome == "invalidated":
        useful_agents = plan.agents_contradicting
        misleading_agents = plan.agents_validating
        missed_condition = "Regle d'invalidation contextuelle declenchee."
        summary = "Invalidated: le contexte a annule le plan avant outcome prix."
    else:
        useful_agents = plan.agents_validating
        misleading_agents = plan.agents_contradicting
        missed_condition = "Trade encore ouvert."
        summary = "Open: post-mortem final indisponible tant que le plan n'est pas clos."
    return TradePostMortem(
        trade_id=plan.trade_id,
        direction=plan.direction,
        outcome=plan.outcome,
        record_type=record_type,
        r_multiple=round(r_multiple, 2),
        duration_minutes=duration,
        useful_agents=useful_agents[:6],
        misleading_agents=misleading_agents[:6],
        missed_condition=missed_condition,
        summary=summary,
    )


def enrich_trade_plan_v3(plan: TradePlan) -> TradePlan:
    updated = copy.deepcopy(plan)
    post_mortem = build_trade_post_mortem(updated)
    updated.record_type = post_mortem.record_type
    updated.r_multiple = post_mortem.r_multiple
    updated.duration_minutes = post_mortem.duration_minutes
    updated.useful_agents = post_mortem.useful_agents
    updated.misleading_agents = post_mortem.misleading_agents
    updated.missed_condition = post_mortem.missed_condition
    updated.post_mortem = post_mortem.summary
    return updated


def evaluate_trade_plan(plan: TradePlan, current_price: float, now: datetime | None = None) -> TradePlan:
    if trade_plan_closed(plan):
        return enrich_trade_plan_v3(plan)
    reference = now or datetime.now(timezone.utc)
    updated = copy.deepcopy(plan)
    updated.updated_at = reference.replace(microsecond=0).isoformat()
    expiry = parse_iso_datetime(plan.max_valid_until)

    if expiry is not None and reference > expiry:
        updated.status = "expired"
        updated.outcome = "expired"
        updated.outcome_reason = "Expiration automatique: le plan n'a pas atteint TP/SL avant la limite de validite."
        updated.closed_at = updated.updated_at
        return updated

    if plan.direction == "BUY":
        if current_price <= plan.stop_loss:
            updated.status = "sl_hit"
            updated.outcome = "loss"
            updated.outcome_reason = f"SL touche a {plan.stop_loss:.2f}; prix courant {current_price:.2f}."
            updated.closed_at = updated.updated_at
        elif current_price >= plan.tp3:
            updated.status = "tp3_hit"
            updated.outcome = "win"
            updated.outcome_reason = f"TP3 touche a {plan.tp3:.2f}; extension complete."
            updated.closed_at = updated.updated_at
        elif current_price >= plan.tp2:
            updated.status = "tp2_hit"
            updated.outcome = "win"
            updated.outcome_reason = f"TP2 touche a {plan.tp2:.2f}; trade gagnant."
            updated.closed_at = updated.updated_at
        elif current_price >= plan.tp1:
            updated.status = "tp1_hit"
            updated.outcome = "partial"
            updated.outcome_reason = f"TP1 touche a {plan.tp1:.2f}; resultat partiel verrouille."
        else:
            updated.status = "active"
    else:
        if current_price >= plan.stop_loss:
            updated.status = "sl_hit"
            updated.outcome = "loss"
            updated.outcome_reason = f"SL touche a {plan.stop_loss:.2f}; prix courant {current_price:.2f}."
            updated.closed_at = updated.updated_at
        elif current_price <= plan.tp3:
            updated.status = "tp3_hit"
            updated.outcome = "win"
            updated.outcome_reason = f"TP3 touche a {plan.tp3:.2f}; extension complete."
            updated.closed_at = updated.updated_at
        elif current_price <= plan.tp2:
            updated.status = "tp2_hit"
            updated.outcome = "win"
            updated.outcome_reason = f"TP2 touche a {plan.tp2:.2f}; trade gagnant."
            updated.closed_at = updated.updated_at
        elif current_price <= plan.tp1:
            updated.status = "tp1_hit"
            updated.outcome = "partial"
            updated.outcome_reason = f"TP1 touche a {plan.tp1:.2f}; resultat partiel verrouille."
        else:
            updated.status = "active"
    if (
        updated.status == plan.status
        and updated.outcome == plan.outcome
        and updated.outcome_reason == plan.outcome_reason
        and updated.closed_at == plan.closed_at
    ):
        return enrich_trade_plan_v3(plan)
    return enrich_trade_plan_v3(updated)


def trade_outcome_audit_action(plan: TradePlan) -> str:
    if plan.outcome == "win":
        return "trade_won"
    if plan.outcome == "loss":
        return "trade_lost"
    if plan.outcome == "partial":
        return "trade_partial"
    if plan.outcome == "expired":
        return "trade_expired"
    if plan.outcome == "invalidated":
        return "trade_invalidated"
    return "trade_updated"


def update_trade_ledger_outcomes(
    current_price: float,
    path: Path = TRADE_LEDGER_PATH,
    now: datetime | None = None,
) -> list[TradePlan]:
    plans = load_trade_ledger(path)
    updated_plans: list[TradePlan] = []
    for plan in plans:
        updated = evaluate_trade_plan(plan, current_price, now=now)
        if asdict(updated) != asdict(plan):
            append_trade_plan_snapshot(updated, path)
            append_trade_gate_audit_event(
                trade_outcome_audit_action(updated),
                [updated.outcome_reason or updated.post_mortem or "Outcome mis a jour."],
                candidate=updated,
                path=trade_gate_audit_path_for_ledger(path),
                now=now,
                extra={"previous_status": plan.status, "previous_outcome": plan.outcome},
            )
        updated_plans.append(updated)
    return sorted(updated_plans, key=lambda item: item.created_at, reverse=True)


def build_macro_trade_window_reasons(
    macro_catalysts: MacroCatalystCalendar | None,
    settings: UserSettings,
) -> list[str]:
    if macro_catalysts is None:
        return []
    before = settings.no_trade_window_minutes_before_high_macro
    after = settings.no_trade_window_minutes_after_high_macro
    reasons: list[str] = []
    for event in macro_catalysts.catalysts:
        if event.impact_level != "HIGH" or event.minutes_to_event is None:
            continue
        if -after <= event.minutes_to_event <= before:
            reasons.append(
                f"Fenetre macro HIGH: {event.event_type} dans {format_macro_countdown(event.minutes_to_event)}; nouveau trade bloque."
            )
    return reasons[:2]


def regime_direction_contradiction(market_regime: MarketRegimeAnalysis | None, direction: str, threshold: int = 70) -> str | None:
    if market_regime is None or direction not in {"BUY", "SELL"}:
        return None
    score = market_regime.score
    confirmed_enough = score >= threshold or market_regime.confirmed
    if not confirmed_enough:
        return None
    bullish_regimes = {"Safe-Haven Gold", "Stagflation Fear"}
    bearish_regimes = {"Hormuz / Oil Shock", "Dollar Liquidity Squeeze", "De-escalation / Oil Relief", "Risk-On / Carry Trade"}
    if direction == "BUY" and market_regime.name in bearish_regimes:
        return f"Direction BUY contraire au regime fort {market_regime.name} ({score}/100)."
    if direction == "SELL" and market_regime.name in bullish_regimes:
        return f"Direction SELL contraire au regime fort {market_regime.name} ({score}/100)."
    return None


def unique_preserve_order(items: list[str]) -> list[str]:
    seen: set[str] = set()
    unique: list[str] = []
    for item in items:
        if item in seen:
            continue
        seen.add(item)
        unique.append(item)
    return unique


def build_trade_quality_gate(
    gold: SymbolSnapshot,
    global_recommendation: TradeRecommendation,
    data_quality: DataQualitySnapshot | None,
    agent_results: list[AgentResult],
    market_regime: MarketRegimeAnalysis | None,
    macro_catalysts: MacroCatalystCalendar | None = None,
    settings: UserSettings | None = None,
) -> tuple[bool, list[str], list[str], list[str]]:
    hard_reasons: list[str] = []
    advisory_reasons: list[str] = []
    active_settings = settings or default_user_settings()
    validation = validate_user_settings(active_settings)
    if validation.warnings:
        advisory_reasons.extend(validation.warnings[:3])
    trade_threshold = active_settings.trade_threshold
    min_rr = active_settings.minimum_risk_reward
    min_confidence = active_settings.minimum_agent_confidence
    active_agent_names = set(active_settings.active_agents)
    if global_recommendation.verdict not in {"BUY", "SELL"}:
        hard_reasons.append(f"Verdict {global_recommendation.verdict}: aucun trade verrouille sans direction BUY/SELL.")
    decision_agents = [agent for agent in agent_results if agent.name in DECISION_AGENT_NAMES and agent.name in active_agent_names]
    validating = [
        agent.name
        for agent in decision_agents
        if agent.bias == global_recommendation.verdict and agent.confidence >= min_confidence
    ]
    contradicting = [
        agent.name
        for agent in decision_agents
        if agent.bias in {"BUY", "SELL"} and agent.bias != global_recommendation.verdict
    ]

    if global_recommendation.score < trade_threshold:
        hard_reasons.append(f"Score global insuffisant: {global_recommendation.score}/100 < {trade_threshold}.")
    elif global_recommendation.score < trade_threshold + 3:
        advisory_reasons.append(
            f"Score global agressif: {global_recommendation.score}/100; trade autorise seulement si les autres garde-fous restent valides."
        )
    if data_quality is None:
        hard_reasons.append("Data quality indisponible.")
    elif data_quality.preflight and data_quality.preflight.trade_blocked:
        hard_reasons.append(f"Preflight bloquant: {data_quality.preflight.status}.")
    elif data_quality.score < active_settings.min_data_quality:
        hard_reasons.append(f"Data quality trop faible: {data_quality.score}/100 < {active_settings.min_data_quality}.")
    elif data_quality.score < 68:
        advisory_reasons.append(f"Data quality degradee: {data_quality.score}/100; taille et confiance a reduire.")
    if len(validating) < 3:
        hard_reasons.append("Moins de trois agents decisionnels valident la direction avec confiance suffisante.")
    if len(contradicting) >= 3:
        hard_reasons.append("Trop de contradictions entre agents decisionnels.")
    elif contradicting:
        advisory_reasons.append(f"Contradiction presente: {len(contradicting)} agent(s) contre la direction.")
    regime_block = regime_direction_contradiction(market_regime, global_recommendation.verdict)
    if regime_block:
        hard_reasons.append(regime_block)
    if market_regime is not None and market_regime.name == "Hormuz / Oil Shock":
        if market_regime.score >= 70:
            hard_reasons.append("Regime geopolitique/petrole actif >= 70/100: nouveau trade bloque.")
        if global_recommendation.verdict == "BUY":
            hard_reasons.append("Direction BUY contraire au regime petrole/dollar actif: attendre neutralisation du regime.")
    elif market_regime is not None and market_regime.name == "Safe-Haven Gold" and global_recommendation.verdict == "SELL":
        hard_reasons.append("Direction SELL contraire au regime refuge gold: attendre neutralisation du regime.")
    hard_reasons.extend(build_macro_trade_window_reasons(macro_catalysts, active_settings))
    rr1 = compute_risk_reward(
        global_recommendation.verdict,
        gold.price,
        global_recommendation.stop_loss,
        global_recommendation.take_profit_1,
    )
    if rr1 < min_rr:
        hard_reasons.append(f"Risk/reward TP1 insuffisant: {rr1:.2f}R < {min_rr:.2f}R.")
    elif rr1 < min_rr + 0.15:
        advisory_reasons.append(f"Risk/reward TP1 agressif: {rr1:.2f}R; TP2/TP3 doivent compenser.")
    if global_recommendation.stop_loss == global_recommendation.take_profit_1:
        hard_reasons.append("SL/TP non exploitables.")

    allowed = not hard_reasons
    hard_reasons = unique_preserve_order(hard_reasons)
    advisory_reasons = unique_preserve_order(advisory_reasons)
    reasons = [*hard_reasons, *advisory_reasons]
    if allowed:
        reasons.append(
            f"Quality Gate {active_settings.scoring_mode} valide: score, data quality exploitable, majorite decisionnelle et risk/reward permettent un Trade Snapshot."
        )
    return allowed, reasons, validating, contradicting


def normalize_trade_timeframe(value: str) -> str | None:
    compact = value.strip().upper().replace(" ", "")
    aliases = {
        "5M": "M5",
        "M5": "M5",
        "15M": "M15",
        "M15": "M15",
        "1H": "H1",
        "H1": "H1",
        "4H": "H4",
        "H4": "H4",
        "1D": "D1",
        "D1": "D1",
        "DAILY": "D1",
    }
    return aliases.get(compact)


def infer_trade_validity_minutes(
    technical_readings: list[TechnicalReading],
    technical_decision: TechnicalDecision | None = None,
    event_mode: EventModeAnalysis | None = None,
) -> tuple[int, str]:
    timeframe_minutes = {
        "M5": 120,
        "M15": 240,
        "H1": 720,
        "H4": 1440,
        "D1": 4320,
    }
    probe = " ".join(
        [
            technical_decision.trigger if technical_decision else "",
            technical_decision.invalidation if technical_decision else "",
            technical_decision.structure if technical_decision else "",
        ]
    )
    for timeframe in ("M5", "M15", "H1", "H4", "D1"):
        if re.search(rf"(?<![A-Z0-9]){timeframe}(?![A-Z0-9])", probe.upper()):
            minutes = timeframe_minutes[timeframe]
            if event_mode is not None and event_mode.active:
                minutes = max(60, round(minutes * 0.75))
            return minutes, timeframe
    normalized_readings = [normalize_trade_timeframe(reading.timeframe) for reading in technical_readings]
    normalized_readings = [item for item in normalized_readings if item]
    if normalized_readings:
        priority = ["M5", "M15", "H1", "H4", "D1"]
        timeframe = next((item for item in priority if item in normalized_readings), normalized_readings[0])
    else:
        timeframe = "M15"
    minutes = timeframe_minutes[timeframe]
    if event_mode is not None and event_mode.active:
        minutes = max(60, round(minutes * 0.75))
    return minutes, timeframe


def build_trade_plan_from_signal(
    gold: SymbolSnapshot,
    global_recommendation: TradeRecommendation,
    data_quality: DataQualitySnapshot | None,
    agent_results: list[AgentResult],
    market_regime: MarketRegimeAnalysis | None,
    event_facts: list[EventFact],
    technical_readings: list[TechnicalReading],
    now: datetime | None = None,
    macro_catalysts: MacroCatalystCalendar | None = None,
    technical_decision: TechnicalDecision | None = None,
    event_mode: EventModeAnalysis | None = None,
    settings: UserSettings | None = None,
) -> tuple[TradePlan | None, list[str]]:
    reference = now or datetime.now(timezone.utc)
    allowed, reasons, validating, contradicting = build_trade_quality_gate(
        gold,
        global_recommendation,
        data_quality,
        agent_results,
        market_regime,
        macro_catalysts=macro_catalysts,
        settings=settings,
    )
    if not allowed:
        return None, reasons

    direction = global_recommendation.verdict
    entry = gold.price
    if technical_decision is not None and trade_direction_from_text(technical_decision.direction) == direction:
        entry_low = technical_decision.entry_zone_low
        entry_high = technical_decision.entry_zone_high
        stop_loss = technical_decision.stop_loss
        tp1 = technical_decision.tp1
        tp2 = technical_decision.tp2
        tp3 = technical_decision.tp3
        level_reasons = [f"Niveaux repris du TechnicalDecisionEngine v4 ({technical_decision.structure})."]
    else:
        market_levels = build_market_trade_levels(
            gold,
            direction,
            "trend_continuation",
            atr=max(abs(global_recommendation.take_profit_1 - entry), 6.0),
            readings=technical_readings,
            proxy_price=technical_readings[-1].close if technical_readings else None,
            min_rr=(settings or default_user_settings()).minimum_risk_reward,
            event_mode=event_mode,
        )
        entry_low = market_levels.entry_zone_low
        entry_high = market_levels.entry_zone_high
        stop_loss = market_levels.stop_loss
        tp1 = market_levels.tp1
        tp2 = market_levels.tp2
        tp3 = market_levels.tp3
        level_reasons = market_levels.reasons[:2]
    min_rr = (settings or default_user_settings()).minimum_risk_reward
    rr1 = compute_risk_reward(direction, entry, stop_loss, tp1)
    if rr1 < min_rr:
        reasons.append(f"Trade refuse: niveaux v4 donnent R/R TP1 {rr1:.2f}R < {min_rr:.2f}R.")
        return None, reasons
    signal_id = trade_signal_id(direction, market_regime.name if market_regime else "Normal Macro", entry, global_recommendation.score)
    technical_snapshot = "; ".join(
        f"{reading.timeframe}:{reading.verdict}/{reading.score:+.1f}"
        for reading in technical_readings[:5]
    )
    validity_minutes, validity_timeframe = infer_trade_validity_minutes(
        technical_readings,
        technical_decision=technical_decision,
        event_mode=event_mode,
    )
    evidence_sources = sorted({
        source
        for agent in agent_results
        for source in [*(evidence.source for evidence in agent.evidence), *(risk.label for risk in agent.risks)]
        if source
    })[:12]
    created_at = reference.replace(microsecond=0).isoformat()
    plan = TradePlan(
        trade_id=f"{created_at.replace(':', '').replace('-', '')}-{signal_id}",
        created_at=created_at,
        updated_at=created_at,
        status="active",
        direction=direction,
        entry_type="market_reference",
        reference_price=round(entry, 2),
        entry_zone_low=round(entry_low, 2),
        entry_zone_high=round(entry_high, 2),
        stop_loss=round(stop_loss, 2),
        tp1=round(tp1, 2),
        tp2=round(tp2, 2),
        tp3=round(tp3, 2),
        risk_reward_tp1=rr1,
        risk_reward_tp2=compute_risk_reward(direction, entry, stop_loss, tp2),
        risk_reward_tp3=compute_risk_reward(direction, entry, stop_loss, tp3),
        max_valid_until=(reference + timedelta(minutes=validity_minutes)).replace(microsecond=0).isoformat(),
        source_signal_id=signal_id,
        global_score_at_creation=global_recommendation.score,
        data_quality_score=data_quality.score if data_quality else 0,
        confidence_score=round(sum(agent.confidence for agent in agent_results) / len(agent_results)) if agent_results else 0,
        market_regime=market_regime.name if market_regime else "Normal Macro",
        agents_validating=validating,
        agents_contradicting=contradicting,
        evidence_sources=evidence_sources,
        event_facts_snapshot=[fact.title for fact in event_facts[:4]],
        technical_snapshot=technical_snapshot,
        macro_snapshot=next((agent.summary for agent in agent_results if agent.name == "MacroAgent"), ""),
        geopolitical_snapshot=next((agent.summary for agent in agent_results if agent.name == "GeopoliticalOilShockAgent"), ""),
        elliott_wave_snapshot="",
        invalidation_rules=[
            f"Invalidation principale si prix touche SL {stop_loss:.2f}.",
            "Invalidation contextuelle si Data Quality passe sous 60/100 ou si un fait Tier 1 contredit le scenario.",
            f"Validite dynamique: {validity_timeframe}, {validity_minutes} minutes.",
            "Sorties partielles: TP1 50%, TP2 30%, TP3 20%.",
            *level_reasons,
        ],
        outcome="open",
        outcome_reason="Trade Snapshot cree par Quality Gate; SL/TP figes.",
        closed_at=None,
    )
    return plan, reasons


def has_recent_similar_trade(
    plans: list[TradePlan],
    candidate: TradePlan,
    cooldown_minutes: int = 90,
    cooldown_after_loss_minutes: int = 240,
    cooldown_after_win_minutes: int = 60,
    cooldown_after_expired_minutes: int = 60,
    now: datetime | None = None,
) -> bool:
    reference = now or datetime.now(timezone.utc)
    for plan in plans:
        if plan.direction != candidate.direction:
            continue
        if not trade_plan_closed(plan):
            if plan.market_regime == candidate.market_regime:
                return True
            continue
        closed_reference = parse_iso_datetime(plan.closed_at or plan.updated_at or plan.created_at)
        if closed_reference is None:
            continue
        if plan.outcome == "loss":
            cooldown = cooldown_after_loss_minutes
        elif plan.outcome == "win":
            cooldown = cooldown_after_win_minutes
        elif plan.outcome == "expired":
            cooldown = cooldown_after_expired_minutes
        else:
            cooldown = cooldown_minutes
        if (reference - closed_reference).total_seconds() <= cooldown * 60:
            return True
    return False


def count_recent_trade_records(plans: list[TradePlan], reference: datetime, hours: int) -> int:
    window_seconds = hours * 3600
    count = 0
    for plan in plans:
        if trade_record_type(plan) == "setup_surveille":
            continue
        created = parse_iso_datetime(plan.created_at)
        if created is not None and 0 <= (reference - created).total_seconds() <= window_seconds:
            count += 1
    return count


def count_recent_losses(plans: list[TradePlan], reference: datetime, hours: int) -> int:
    window_seconds = hours * 3600
    count = 0
    for plan in plans:
        if plan.outcome != "loss" or trade_record_type(plan) == "setup_surveille":
            continue
        closed_reference = parse_iso_datetime(plan.closed_at or plan.updated_at or plan.created_at)
        if closed_reference is not None and 0 <= (reference - closed_reference).total_seconds() <= window_seconds:
            count += 1
    return count


def build_trade_ledger_guard_reasons(
    plans: list[TradePlan],
    settings: UserSettings,
    reference: datetime,
) -> list[str]:
    reasons: list[str] = []
    recent_trade_count = count_recent_trade_records(plans, reference, 24)
    if recent_trade_count >= settings.max_trades_per_24h:
        reasons.append(
            f"Limite journaliere atteinte: {recent_trade_count} trade(s) sur 24h >= {settings.max_trades_per_24h}."
        )
    recent_losses = count_recent_losses(plans, reference, settings.circuit_breaker_window_hours)
    if recent_losses >= settings.circuit_breaker_after_n_losses:
        reasons.append(
            f"Circuit breaker actif: {recent_losses} loss sur {settings.circuit_breaker_window_hours}h; pause {settings.circuit_breaker_pause_hours}h."
        )
    return reasons


def build_trade_ledger_stats(plans: list[TradePlan]) -> TradeLedgerStats:
    enriched = [enrich_trade_plan_v3(plan) for plan in plans]
    setups = [plan for plan in enriched if trade_record_type(plan) == "setup_surveille"]
    trade_records = [plan for plan in enriched if trade_record_type(plan) != "setup_surveille"]
    closed = [plan for plan in trade_records if plan.outcome in {"win", "loss", "partial", "expired", "invalidated"}]
    wins = [plan for plan in closed if plan.outcome == "win"]
    r_values = [trade_realized_r(plan) for plan in closed]
    durations = [trade_duration_minutes(plan) for plan in closed if trade_duration_minutes(plan) > 0]
    setup_base = len(setups) + len(trade_records)
    return TradeLedgerStats(
        win_rate=round((len(wins) / len(closed)) * 100, 1) if closed else 0.0,
        expectancy_r=round(sum(r_values) / len(r_values), 2) if r_values else 0.0,
        average_r=round(sum(r_values) / len(r_values), 2) if r_values else 0.0,
        average_duration_minutes=round(sum(durations) / len(durations)) if durations else 0,
        setup_to_trade_rate=round((len(trade_records) / setup_base) * 100, 1) if setup_base else 0.0,
        trade_to_win_rate=round((len(wins) / len(trade_records)) * 100, 1) if trade_records else 0.0,
        total_setups=len(setups),
        total_trade_records=len(trade_records),
    )


def build_trade_ledger_summary(
    gold: SymbolSnapshot,
    global_recommendation: TradeRecommendation,
    data_quality: DataQualitySnapshot | None,
    agent_results: list[AgentResult],
    market_regime: MarketRegimeAnalysis | None,
    event_facts: list[EventFact],
    technical_readings: list[TechnicalReading],
    path: Path = TRADE_LEDGER_PATH,
    now: datetime | None = None,
    allow_create: bool = True,
    settings: UserSettings | None = None,
    macro_catalysts: MacroCatalystCalendar | None = None,
    technical_decision: TechnicalDecision | None = None,
    event_mode: EventModeAnalysis | None = None,
) -> TradeLedgerSummary:
    reference = now or datetime.now(timezone.utc)
    active_settings = settings or default_user_settings()
    validate_user_settings(active_settings)
    audit_path = trade_gate_audit_path_for_ledger(path)
    plans = update_trade_ledger_outcomes(gold.price, path=path, now=reference)
    candidate, gate_reasons = build_trade_plan_from_signal(
        gold,
        global_recommendation,
        data_quality,
        agent_results,
        market_regime,
        event_facts,
        technical_readings,
        now=reference,
        macro_catalysts=macro_catalysts,
        technical_decision=technical_decision,
        event_mode=event_mode,
        settings=active_settings,
    )
    if candidate is None and allow_create and gate_reasons and global_recommendation.verdict in {"BUY", "SELL"}:
        append_trade_gate_audit_event(
            "trade_refused_gate",
            gate_reasons,
            path=audit_path,
            now=reference,
            extra={
                "verdict": global_recommendation.verdict,
                "score": global_recommendation.score,
                "data_quality_score": data_quality.score if data_quality else 0,
                "market_regime": market_regime.name if market_regime else "Normal Macro",
            },
        )
    if candidate is not None:
        ledger_guard_reasons = build_trade_ledger_guard_reasons(plans, active_settings, reference)
        if ledger_guard_reasons:
            gate_reasons = ledger_guard_reasons
            append_trade_gate_audit_event(
                "trade_refused_ledger_guard",
                gate_reasons,
                candidate=candidate,
                path=audit_path,
                now=reference,
            )
            candidate = None
        elif has_recent_similar_trade(
            plans,
            candidate,
            cooldown_minutes=active_settings.cooldown_minutes,
            cooldown_after_loss_minutes=active_settings.cooldown_after_loss_minutes,
            cooldown_after_win_minutes=active_settings.cooldown_after_win_minutes,
            cooldown_after_expired_minutes=active_settings.cooldown_after_expired_minutes,
            now=reference,
        ):
            gate_reasons = ["Cooldown actif: un trade similaire est deja actif ou trop recent."]
            append_trade_gate_audit_event(
                "trade_refused_cooldown",
                gate_reasons,
                candidate=candidate,
                path=audit_path,
                now=reference,
            )
            candidate = None
        elif allow_create:
            candidate = enrich_trade_plan_v3(candidate)
            append_trade_plan_snapshot(candidate, path)
            append_trade_gate_audit_event(
                "trade_created",
                ["Trade Snapshot cree et verrouille dans le ledger append-only."],
                candidate=candidate,
                path=audit_path,
                now=reference,
            )
            plans = [candidate, *plans]
            gate_reasons = ["Trade Snapshot cree et verrouille dans le ledger append-only."]

    plans = [enrich_trade_plan_v3(plan) for plan in plans]
    active_trades = [plan for plan in plans if trade_plan_is_active(plan)]
    wins = sum(1 for plan in plans if plan.outcome == "win")
    losses = sum(1 for plan in plans if plan.outcome == "loss")
    partials = sum(1 for plan in plans if plan.outcome == "partial")
    expired = sum(1 for plan in plans if plan.outcome == "expired")
    invalidated = sum(1 for plan in plans if plan.outcome == "invalidated" or plan.status == "invalidated")
    post_mortems = [
        build_trade_post_mortem(plan)
        for plan in plans
        if plan.outcome in {"win", "loss", "partial", "expired", "invalidated"}
    ][:10]
    return TradeLedgerSummary(
        ledger_path=str(path),
        generated_at=reference.replace(microsecond=0).isoformat(),
        quality_gate_status="VALIDATED" if candidate is not None and gate_reasons and gate_reasons[0].startswith("Trade Snapshot") else "WAIT",
        quality_gate_reasons=gate_reasons,
        active_trades=active_trades[:5],
        recent_trades=plans[:10],
        total_trades=len(plans),
        wins=wins,
        losses=losses,
        partials=partials,
        expired=expired,
        invalidated=invalidated,
        stats=build_trade_ledger_stats(plans),
        post_mortems=post_mortems,
    )


def load_replay_price_snapshots(path: Path = AUDIT_LOG_PATH) -> list[ReplayPriceSnapshot]:
    if not path.exists():
        return []
    snapshots: list[ReplayPriceSnapshot] = []
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        if not raw_line.strip():
            continue
        try:
            data = json.loads(raw_line)
        except Exception:
            continue
        timestamp = str(data.get("generated_at", ""))
        price = parse_float(data.get("xauusd_price"))
        if not timestamp or price is None:
            continue
        decision = data.get("decision") if isinstance(data.get("decision"), dict) else {}
        snapshots.append(
            ReplayPriceSnapshot(
                timestamp=timestamp,
                price=float(price),
                decision_status=str(decision.get("status", "")),
                decision_score=int(decision.get("score", 0) or 0),
            )
        )
    return sorted(snapshots, key=lambda item: item.timestamp)


def _price_after(plan: TradePlan, snapshots: list[ReplayPriceSnapshot], hours: int) -> float | None:
    created = parse_iso_datetime(plan.created_at)
    if created is None:
        return None
    target = created + timedelta(hours=hours)
    candidates = [
        snapshot
        for snapshot in snapshots
        if (parse_iso_datetime(snapshot.timestamp) is not None and parse_iso_datetime(snapshot.timestamp) >= target)
    ]
    return candidates[0].price if candidates else None


def _r_distance(plan: TradePlan, price: float) -> float:
    risk = abs(plan.reference_price - plan.stop_loss)
    if risk <= 0:
        return 0.0
    if plan.direction == "BUY":
        return (price - plan.reference_price) / risk
    return (plan.reference_price - price) / risk


def replay_trade_plan(plan: TradePlan, snapshots: list[ReplayPriceSnapshot]) -> ReplayTradeResult:
    created = parse_iso_datetime(plan.created_at)
    replay_snapshots = [
        snapshot
        for snapshot in snapshots
        if created is None or (parse_iso_datetime(snapshot.timestamp) is not None and parse_iso_datetime(snapshot.timestamp) >= created)
    ]
    replayed = enrich_trade_plan_v3(plan)
    for snapshot in replay_snapshots:
        replayed = evaluate_trade_plan(replayed, snapshot.price, now=parse_iso_datetime(snapshot.timestamp))
        if trade_plan_closed(replayed):
            break
    r_values = [_r_distance(plan, snapshot.price) for snapshot in replay_snapshots]
    return ReplayTradeResult(
        trade_id=plan.trade_id,
        direction=plan.direction,
        created_at=plan.created_at,
        replay_status=replayed.status,
        replay_outcome=replayed.outcome,
        replay_reason=replayed.outcome_reason or "Aucun outcome final detecte dans les snapshots disponibles.",
        price_after_1h=_price_after(plan, replay_snapshots, 1),
        price_after_2h=_price_after(plan, replay_snapshots, 2),
        price_after_4h=_price_after(plan, replay_snapshots, 4),
        price_after_24h=_price_after(plan, replay_snapshots, 24),
        max_favorable_r=round(max(r_values), 2) if r_values else 0.0,
        max_adverse_r=round(min(r_values), 2) if r_values else 0.0,
    )


def build_replay_report(
    ledger_path: Path = TRADE_LEDGER_PATH,
    audit_log_path: Path = AUDIT_LOG_PATH,
) -> ReplayReport:
    plans = load_trade_ledger(ledger_path)
    snapshots = load_replay_price_snapshots(audit_log_path)
    results = [replay_trade_plan(plan, snapshots) for plan in plans]
    closed = [result for result in results if result.replay_outcome in {"win", "loss", "partial", "expired", "invalidated"}]
    wins = sum(1 for result in closed if result.replay_outcome == "win")
    losses = sum(1 for result in closed if result.replay_outcome == "loss")
    summary = (
        f"Replay v3: {len(results)} trade(s) rejoue(s), {len(snapshots)} snapshot(s), "
        f"{wins} win(s), {losses} loss(es)."
        if results
        else f"Replay v3: aucun trade a rejouer, {len(snapshots)} snapshot(s) disponible(s)."
    )
    return ReplayReport(
        generated_at=iso_now(),
        ledger_path=str(ledger_path),
        audit_log_path=str(audit_log_path),
        snapshots=len(snapshots),
        trades_replayed=len(results),
        results=results,
        summary=summary,
    )


def render_replay_report_markdown(report: ReplayReport) -> str:
    lines = [
        "# Aureum Flux Replay v3",
        "",
        f"Genere a {report.generated_at}",
        "",
        report.summary,
        "",
        f"- Ledger: {report.ledger_path}",
        f"- Audit log: {report.audit_log_path}",
        f"- Snapshots: {report.snapshots}",
        "",
        "## Trades rejoues",
    ]
    if not report.results:
        lines.append("Aucun trade historise a rejouer.")
    for result in report.results:
        levels = [
            f"1h={format_number(result.price_after_1h)}",
            f"2h={format_number(result.price_after_2h)}",
            f"4h={format_number(result.price_after_4h)}",
            f"24h={format_number(result.price_after_24h)}",
        ]
        lines.extend(
            [
                "",
                f"### {result.trade_id}",
                f"- Direction: {result.direction}",
                f"- Cree: {result.created_at}",
                f"- Replay outcome: {result.replay_outcome} / {result.replay_status}",
                f"- R favorable/adverse: {result.max_favorable_r:+.2f}R / {result.max_adverse_r:+.2f}R",
                f"- Prix apres: {', '.join(levels)}",
                f"- Pourquoi: {result.replay_reason}",
            ]
        )
    return "\n".join(lines) + "\n"


def build_monitoring_inspector_payload(
    generated_at: str,
    data_quality: DataQualitySnapshot | None,
    agent_results: list[AgentResult],
    trade_ledger: TradeLedgerSummary | None,
    orchestrator_decision: OrchestratorDecision | None,
    global_recommendation: TradeRecommendation | None,
    market_regime: MarketRegimeAnalysis | None,
    chart_store: ChartStore | None = None,
    strategy_candidates: list[SetupCandidate] | None = None,
    strategy_selection: StrategySelection | None = None,
) -> dict[str, Any]:
    snapshots = data_quality.snapshots if data_quality else []
    source_issues = [snapshot for snapshot in snapshots if snapshot.status != "ok"]
    active_agents = [agent for agent in agent_results if agent.status in {"ACTIVE", "PASSIVE"}]
    agent_outputs = [
        {
            "name": agent.name,
            "department": agent.department,
            "status": agent.status,
            "bias": agent.bias,
            "score": agent.score,
            "confidence": agent.confidence,
            "summary": agent.summary,
            "evidence_count": len(agent.evidence),
            "risk_count": len(agent.risks),
        }
        for agent in agent_results[:16]
    ]
    trade_rows = []
    if trade_ledger:
        seen_trade_ids: set[str] = set()
        for plan in [*trade_ledger.active_trades, *trade_ledger.recent_trades]:
            if plan.trade_id in seen_trade_ids:
                continue
            seen_trade_ids.add(plan.trade_id)
            trade_rows.append(
                {
                    "trade_id": plan.trade_id,
                    "created_at": plan.created_at,
                    "direction": plan.direction,
                    "status": plan.status,
                    "outcome": plan.outcome,
                    "entry": plan.reference_price,
                    "stop_loss": plan.stop_loss,
                    "tp1": plan.tp1,
                    "tp2": plan.tp2,
                    "tp3": plan.tp3,
                    "outcome_reason": plan.outcome_reason,
                    "record_type": plan.record_type,
                    "r_multiple": plan.r_multiple,
                    "duration_minutes": plan.duration_minutes,
                    "post_mortem": plan.post_mortem,
                }
            )

    preflight = data_quality.preflight if data_quality else None
    chart_timeframes = chart_store.timeframes if chart_store else []
    strategy_shadow = build_strategy_shadow_integration(global_recommendation, strategy_selection)

    return {
        "generated_at": generated_at,
        "last_refresh": data_quality.generated_at if data_quality else generated_at,
        "data_quality_score": data_quality.score if data_quality else 0,
        "data_quality_status": data_quality.status if data_quality else "UNAVAILABLE",
        "source_counts": {
            "total": len(snapshots),
            "active": sum(1 for snapshot in snapshots if snapshot.status == "ok"),
            "missing": len(data_quality.missing_sources) if data_quality else 0,
            "stale": len(data_quality.stale_sources) if data_quality else 0,
            "weak": len(data_quality.weak_sources) if data_quality else 0,
            "issues": len(source_issues),
        },
        "source_issues": [
            {
                "source_id": snapshot.source_id,
                "name": snapshot.name,
                "status": snapshot.status,
                "category": snapshot.category,
                "critical": snapshot.critical,
                "last_update": snapshot.last_update,
                "age_minutes": snapshot.age_minutes,
                "value_summary": snapshot.value_summary,
            }
            for snapshot in source_issues
        ],
        "preflight": {
            "status": preflight.status if preflight else "UNAVAILABLE",
            "summary": preflight.summary if preflight else "Preflight indisponible.",
            "trade_blocked": preflight.trade_blocked if preflight else True,
            "blockers": preflight.blockers if preflight else [],
            "warnings": preflight.warnings if preflight else [],
            "route_count": len(preflight.routes) if preflight else 0,
        },
        "chart_store": {
            "status": chart_store.status if chart_store else "UNAVAILABLE",
            "summary": chart_store.summary if chart_store else "Chart Store indisponible.",
            "timeframes": [
                {
                    "timeframe": item.timeframe,
                    "status": item.status,
                    "candles": len(item.candles),
                    "last_timestamp": item.last_timestamp,
                    "freshness_minutes": item.freshness_minutes,
                    "gap_count": item.gap_count,
                    "quality_flags": item.quality_flags,
                }
                for item in chart_timeframes
            ],
        },
        "agents": {
            "total": len(agent_results),
            "active": len(active_agents),
            "experimental": sum(1 for agent in agent_results if agent.experimental),
            "outputs": agent_outputs,
        },
        "decision": {
            "verdict": global_recommendation.verdict if global_recommendation else "UNAVAILABLE",
            "score": global_recommendation.score if global_recommendation else 0,
            "summary": global_recommendation.summary if global_recommendation else "",
            "engine": orchestrator_decision.engine if orchestrator_decision else "legacy",
            "gate_status": orchestrator_decision.status if orchestrator_decision else "UNAVAILABLE",
            "quality_gate_reasons": orchestrator_decision.quality_gate_reasons if orchestrator_decision else [],
        },
        "regime": {
            "name": market_regime.name if market_regime else "Normal Macro",
            "status": market_regime.status if market_regime else "NORMAL",
            "score": market_regime.score if market_regime else 0,
        },
        "trades": {
            "ledger_path": trade_ledger.ledger_path if trade_ledger else str(TRADE_LEDGER_PATH),
            "quality_gate_status": trade_ledger.quality_gate_status if trade_ledger else "UNAVAILABLE",
            "quality_gate_reasons": trade_ledger.quality_gate_reasons if trade_ledger else [],
            "active": len(trade_ledger.active_trades) if trade_ledger else 0,
            "total": trade_ledger.total_trades if trade_ledger else 0,
            "wins": trade_ledger.wins if trade_ledger else 0,
            "losses": trade_ledger.losses if trade_ledger else 0,
            "partials": trade_ledger.partials if trade_ledger else 0,
            "expired": trade_ledger.expired if trade_ledger else 0,
            "invalidated": trade_ledger.invalidated if trade_ledger else 0,
            "stats": asdict(trade_ledger.stats) if trade_ledger else asdict(TradeLedgerStats()),
            "post_mortems": [asdict(item) for item in trade_ledger.post_mortems] if trade_ledger else [],
            "rows": trade_rows[:12],
        },
        "strategy": {
            "status": strategy_selection.status if strategy_selection else "UNAVAILABLE",
            "session": strategy_selection.session if strategy_selection else detect_current_session(),
            "event_mode_active": strategy_selection.event_mode_active if strategy_selection else False,
            "selected_score": strategy_selection.selected_score if strategy_selection else 0,
            "selected_setup": asdict(strategy_selection.selected_setup) if strategy_selection and strategy_selection.selected_setup else None,
            "reasons": strategy_selection.reasons if strategy_selection else [],
            "ranked_candidates": strategy_selection.ranked_candidates if strategy_selection else [],
            "rejected_candidates": strategy_selection.rejected_candidates if strategy_selection else [],
            "candidate_count": len(strategy_candidates or []),
            "raw_candidates": [asdict(candidate) for candidate in (strategy_candidates or [])],
        },
        "strategy_shadow": asdict(strategy_shadow),
    }


def build_audit_log_snapshot(bundle: BriefingBundle) -> dict[str, Any]:
    generated_at = str(bundle.payload.get("generated_at", iso_now()))
    inspector = build_monitoring_inspector_payload(
        generated_at,
        bundle.data_quality,
        bundle.agent_results,
        bundle.trade_ledger,
        bundle.orchestrator_decision,
        bundle.global_recommendation,
        bundle.market_regime,
        bundle.chart_store,
        bundle.strategy_candidates,
        bundle.strategy_selection,
    )
    return {
        "generated_at": generated_at,
        "xauusd_price": round(bundle.gold.price, 2),
        "xauusd_change_pct": round(bundle.gold.change_pct, 2),
        "decision": inspector["decision"],
        "regime": inspector["regime"],
        "data_quality": {
            "score": inspector["data_quality_score"],
            "status": inspector["data_quality_status"],
            "sources": inspector["source_counts"],
            "issues": inspector["source_issues"][:8],
            "preflight": inspector["preflight"],
        },
        "chart_store": inspector["chart_store"],
        "agents": inspector["agents"]["outputs"],
        "trades": inspector["trades"],
        "strategy": inspector["strategy"],
        "strategy_shadow": inspector["strategy_shadow"],
    }


def append_audit_log_snapshot(
    bundle: BriefingBundle,
    path: Path = AUDIT_LOG_PATH,
) -> dict[str, Any]:
    entry = build_audit_log_snapshot(bundle)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(entry, ensure_ascii=False, sort_keys=True) + "\n")
    return entry


def append_audit_log_safely(bundle: BriefingBundle, path: Path = AUDIT_LOG_PATH) -> None:
    try:
        append_audit_log_snapshot(bundle, path=path)
    except Exception as exc:
        bundle.payload.setdefault("monitoring_warnings", []).append(f"audit_log_write_failed: {exc}")


def latest_iso(values: list[str | None]) -> str | None:
    parsed_values = [(parse_iso_datetime(value), value) for value in values if value]
    valid = [(parsed, value) for parsed, value in parsed_values if parsed is not None]
    if not valid:
        return None
    return max(valid, key=lambda item: item[0] or datetime.min.replace(tzinfo=timezone.utc))[1]


def build_data_quality_snapshot(
    gold: SymbolSnapshot,
    dxy: SymbolSnapshot,
    us10y: SymbolSnapshot,
    news: list[NewsItem],
    real_yield: SymbolSnapshot | None = None,
    official_macro_rates: OfficialMacroRates | None = None,
    cftc_positioning: CFTCPositioning | None = None,
    etf_flows_analysis: ETFFlowsAnalysis | None = None,
    macro_catalysts: MacroCatalystCalendar | None = None,
    cross_asset_analysis: CrossAssetAnalysis | None = None,
    weekend_gold: WeekendGoldSnapshot | None = None,
    market_regime: MarketRegimeAnalysis | None = None,
    political_statements: list[PoliticalStatement] | None = None,
    chart_store: ChartStore | None = None,
    now: datetime | None = None,
) -> DataQualitySnapshot:
    reference = now or datetime.now(timezone.utc)
    latest_news = latest_iso([item.published_at for item in news])
    latest_political = latest_iso([item.published_at for item in political_statements or []])
    latest_macro = latest_iso([item.scheduled_at for item in (macro_catalysts.catalysts if macro_catalysts else [])])

    snapshots = [
        make_source_snapshot("investing_xauusd", gold.price > 0, gold.fetched_at, f"spot {format_number(gold.price)}", now=reference),
        make_source_snapshot("ig_weekend_gold", weekend_gold is not None, weekend_gold.fetched_at if weekend_gold else None, f"mid {format_number(weekend_gold.mid if weekend_gold else None)}", now=reference),
        make_source_snapshot(
            "fred_dgs10",
            bool(official_macro_rates and official_macro_rates.dgs10),
            official_macro_rates.dgs10.fetched_at if official_macro_rates and official_macro_rates.dgs10 else None,
            f"10Y {format_number(official_macro_rates.dgs10.price if official_macro_rates and official_macro_rates.dgs10 else None, 2, '%')}",
            now=reference,
        ),
        make_source_snapshot(
            "fred_dgs2",
            bool(official_macro_rates and official_macro_rates.dgs2),
            official_macro_rates.dgs2.fetched_at if official_macro_rates and official_macro_rates.dgs2 else None,
            f"2Y {format_number(official_macro_rates.dgs2.price if official_macro_rates and official_macro_rates.dgs2 else None, 2, '%')}",
            now=reference,
        ),
        make_source_snapshot(
            "fred_dgs3m",
            bool(official_macro_rates and official_macro_rates.dgs3m),
            official_macro_rates.dgs3m.fetched_at if official_macro_rates and official_macro_rates.dgs3m else None,
            f"3M {format_number(official_macro_rates.dgs3m.price if official_macro_rates and official_macro_rates.dgs3m else None, 2, '%')}",
            now=reference,
        ),
        make_source_snapshot(
            "fred_dgs30",
            bool(official_macro_rates and official_macro_rates.dgs30),
            official_macro_rates.dgs30.fetched_at if official_macro_rates and official_macro_rates.dgs30 else None,
            f"30Y {format_number(official_macro_rates.dgs30.price if official_macro_rates and official_macro_rates.dgs30 else None, 2, '%')}",
            now=reference,
        ),
        make_source_snapshot(
            "fred_t10yie",
            bool(official_macro_rates and official_macro_rates.t10yie),
            official_macro_rates.t10yie.fetched_at if official_macro_rates and official_macro_rates.t10yie else None,
            f"breakeven {format_number(official_macro_rates.t10yie.price if official_macro_rates and official_macro_rates.t10yie else None, 2, '%')}",
            now=reference,
        ),
        make_source_snapshot("fred_dfii10", real_yield is not None, real_yield.fetched_at if real_yield else None, f"real yield {format_number(real_yield.price if real_yield else None, 2, '%')}", now=reference),
        make_source_snapshot("cftc_cot_gold", cftc_positioning is not None, f"{cftc_positioning.report_date}T21:30:00+00:00" if cftc_positioning else None, cftc_positioning.summary if cftc_positioning else "", now=reference),
        make_source_snapshot("wgc_etf_flows", etf_flows_analysis is not None, f"{etf_flows_analysis.as_of_date}T21:30:00+00:00" if etf_flows_analysis and etf_flows_analysis.as_of_date else None, etf_flows_analysis.summary if etf_flows_analysis else "", now=reference),
        make_source_snapshot("macro_catalysts", macro_catalysts is not None and bool(macro_catalysts.catalysts), macro_catalysts.generated_at if macro_catalysts else None, f"{len(macro_catalysts.catalysts) if macro_catalysts else 0} events", now=reference),
        make_source_snapshot("google_news_rss", bool(news), latest_news, f"{len(news)} headlines dedup", now=reference),
        make_source_snapshot("white_house_feed", bool(political_statements), latest_political, f"{len(political_statements or [])} statements", now=reference),
        make_source_snapshot("news_official_feeds", any(news_source_tier(item.source, item.link) == 1 for item in news), latest_news, "White House/Fed/BLS/Treasury/BEA/CFTC/WGC", now=reference),
        make_source_snapshot("news_fast_feeds", any(news_source_tier(item.source, item.link) <= 2 for item in news), latest_news, "AP/CNBC/Reuters/Bloomberg", now=reference),
        make_source_snapshot(
            "critical_fast_feeds",
            any(item.category.startswith("critical_") or item.source in {"Truth Social", "Nitter Trump", "Nitter White House"} for item in news),
            latest_news,
            "Trump/White House/Fed/AP/Reuters/Bloomberg critical feeds",
            now=reference,
        ),
        make_source_snapshot("cross_asset_yahoo", cross_asset_analysis is not None, gold.fetched_at, cross_asset_analysis.summary if cross_asset_analysis else "", now=reference),
        make_source_snapshot("oil_context", market_regime is not None, gold.fetched_at, market_regime.summary if market_regime else "", now=reference),
        make_source_snapshot(
            "chart_store_ohlc",
            chart_store is not None and chart_store.status != "OFFLINE",
            chart_store.generated_at if chart_store else None,
            chart_store.summary if chart_store else "Chart Store indisponible",
            now=reference,
        ),
    ]

    missing = [snap.name for snap in snapshots if snap.status == "missing" and snap.critical]
    stale = [snap.name for snap in snapshots if snap.status == "stale" and snap.critical]
    weak = [snap.name for snap in snapshots if snap.status == "weak"]
    contradictions = []
    if cross_asset_analysis and cross_asset_analysis.contradictions:
        contradictions.extend(cross_asset_analysis.contradictions[:3])
    if cftc_positioning and etf_flows_analysis and cftc_positioning.score >= 60 and etf_flows_analysis.score <= 40:
        contradictions.append("CFTC positioning bullish mais ETF flows officiels en sorties.")
    if cftc_positioning and etf_flows_analysis and cftc_positioning.score <= 40 and etf_flows_analysis.score >= 60:
        contradictions.append("CFTC positioning bearish mais ETF flows officiels en entrees.")
    contradictions.extend(recent_source_error_warnings())

    criticality_weight = {
        "price": 3.0,
        "rates": 3.0,
        "flows": 3.0,
        "macro": 2.5,
        "chart": 2.0,
        "technical": 2.0,
        "oil": 1.5,
        "political_statements": 1.5,
        "news": 1.0,
    }
    missing_penalty = sum(18 * criticality_weight.get(snap.category, 1.0) for snap in snapshots if snap.status == "missing" and snap.critical)
    stale_penalty = sum(12 * criticality_weight.get(snap.category, 1.0) for snap in snapshots if snap.status == "stale" and snap.critical)
    weak_penalty = sum(4 * max(0.5, 5 - snap.tier) for snap in snapshots if snap.status == "weak")
    score = 100
    score -= round(missing_penalty)
    score -= round(stale_penalty)
    score -= round(weak_penalty)
    score -= min(18, 6 * len(contradictions))
    score = clamp_score(score)
    status = data_quality_status(score)
    summary = (
        f"Data quality {status} {score}/100: "
        f"{len(missing)} critique(s) absente(s), {len(stale)} critique(s) stale, "
        f"{len(weak)} source(s) faible(s), {len(contradictions)} contradiction(s)."
    )
    generated_at = reference.replace(microsecond=0).isoformat()
    preflight = build_preflight_check(snapshots, score, generated_at)
    return DataQualitySnapshot(
        generated_at=generated_at,
        score=score,
        status=status,
        summary=summary,
        missing_sources=missing,
        stale_sources=stale,
        weak_sources=weak,
        contradictions=contradictions,
        snapshots=snapshots,
        preflight=preflight,
    )


def current_month_name_en() -> str:
    months = [
        "January",
        "February",
        "March",
        "April",
        "May",
        "June",
        "July",
        "August",
        "September",
        "October",
        "November",
        "December",
    ]
    return months[datetime.now().astimezone().month - 1]


def compute_support_resistance(points: list[PricePoint], lookback: int = 24) -> tuple[float | None, float | None]:
    recent_points = points[-lookback:]
    lows = [point.low for point in recent_points if point.low is not None]
    highs = [point.high for point in recent_points if point.high is not None]
    closes = [point.close for point in recent_points if point.close is not None]
    if not closes and not lows and not highs:
        return None, None
    support = min(lows) if lows else min(closes)
    resistance = max(highs) if highs else max(closes)
    return support, resistance


def parse_float(value: Any) -> float | None:
    if value is None or value == "":
        return None
    if isinstance(value, (int, float)):
        return float(value)
    cleaned = str(value).replace(",", "").strip()
    return float(cleaned) if cleaned else None


def parse_epoch_millis_to_iso(value: Any) -> str:
    if value is None or value == "":
        return iso_now()
    return datetime.fromtimestamp(int(str(value)) / 1000, tz=timezone.utc).replace(microsecond=0).isoformat()


def build_investing_points(rows: list[dict[str, Any]], limit: int = 30) -> list[PricePoint]:
    points: list[PricePoint] = []
    ordered_rows = list(reversed(rows[:limit]))

    for row in ordered_rows:
        close = parse_float(row.get("last_closeRaw") or row.get("last_close"))
        if close is None:
            continue

        points.append(
            PricePoint(
                timestamp=int(row.get("rowDateRaw") or 0),
                close=close,
                high=parse_float(row.get("last_maxRaw") or row.get("last_max")),
                low=parse_float(row.get("last_minRaw") or row.get("last_min")),
                open=parse_float(row.get("last_openRaw") or row.get("last_open")),
                volume=int(row.get("volumeRaw") or 0) if row.get("volumeRaw") not in (None, "") else None,
            )
        )

    return points


def fetch_investing_xauusd_snapshot(include_historical: bool = True) -> SymbolSnapshot:
    overview_data = http_get_next_data(INVESTING_XAUUSD_URL)
    overview_state = overview_data["props"]["pageProps"]["state"]
    instrument = overview_state["currencyStore"]["instrument"]
    price = instrument["price"]

    points: list[PricePoint] = []
    if include_historical:
        historical_data = http_get_next_data(INVESTING_XAUUSD_HISTORICAL_URL)
        historical_state = historical_data["props"]["pageProps"]["state"]
        historical_rows = historical_state["historicalDataStore"]["historicalData"]["data"]
        points = build_investing_points(historical_rows, limit=30)

    current_price = parse_float(price.get("last"))
    previous_close = parse_float(price.get("lastClose"))
    if current_price is None or previous_close is None:
        raise RuntimeError("Investing.com n'a pas retourne le prix spot XAU/USD attendu.")

    change_abs = parse_float(price.get("change")) or (current_price - previous_close)
    change_pct = parse_float(price.get("changePcr"))
    if change_pct is None:
        change_pct = (change_abs / previous_close) * 100 if previous_close else 0.0

    if len(points) >= 2:
        period_reference = points[0].close
        period_change_pct = ((current_price - period_reference) / period_reference) * 100 if period_reference else 0.0
    else:
        period_change_pct = change_pct
        points = [
            PricePoint(timestamp=int(time.time()) - 86400, close=previous_close),
            PricePoint(timestamp=int(time.time()), close=current_price),
        ]

    support, resistance = compute_support_resistance(points, lookback=min(20, len(points)))

    return SymbolSnapshot(
        symbol="XAU/USD",
        label="XAU/USD Spot",
        price=current_price,
        previous_close=previous_close,
        change_abs=change_abs,
        change_pct=change_pct,
        period_change_pct=period_change_pct,
        day_high=parse_float(price.get("high")),
        day_low=parse_float(price.get("low")),
        support=support,
        resistance=resistance,
        fetched_at=parse_epoch_millis_to_iso(price.get("lastUpdateTime")),
        points=points,
    )


def strip_html_to_text(text: str) -> str:
    without_scripts = re.sub(r"<script\b[^>]*>.*?</script>", " ", text, flags=re.DOTALL | re.IGNORECASE)
    without_styles = re.sub(r"<style\b[^>]*>.*?</style>", " ", without_scripts, flags=re.DOTALL | re.IGNORECASE)
    without_tags = re.sub(r"<[^>]+>", " ", without_styles)
    return compact_whitespace(html.unescape(without_tags))


def parse_ig_weekend_gold_snapshot(page_text: str) -> WeekendGoldSnapshot:
    text = strip_html_to_text(page_text)
    price_match = re.search(
        r"Weekend Gold\s+FFIH5.*?SELL\s+([\d,.]+)\s+BUY\s+([\d,.]+)\s+"
        r"([+-]?[\d,.]+)\s*\(\s*([+-]?[\d,.]+)\s*%\s*\).*?"
        r"High:\s*([\d,.]+)\s+Low:\s*([\d,.]+)",
        text,
        flags=re.IGNORECASE,
    )
    if not price_match:
        raise RuntimeError("Impossible de lire les prix IG Weekend Gold.")

    sell = parse_float(price_match.group(1))
    buy = parse_float(price_match.group(2))
    change_abs = parse_float(price_match.group(3))
    change_pct = parse_float(price_match.group(4))
    day_high = parse_float(price_match.group(5))
    day_low = parse_float(price_match.group(6))
    if sell is None or buy is None:
        raise RuntimeError("Prix IG Weekend Gold incomplets.")

    sentiment_match = re.search(r"Long\s+Short\s+(\d+)%\s+(\d+)%\s+\d+% of client accounts are", text, flags=re.IGNORECASE)
    long_pct = int(sentiment_match.group(1)) if sentiment_match else None
    short_pct = int(sentiment_match.group(2)) if sentiment_match else None

    return WeekendGoldSnapshot(
        source_name="IG Weekend Gold",
        source_url=IG_WEEKEND_GOLD_URL,
        sell=sell,
        buy=buy,
        mid=(sell + buy) / 2,
        spread=buy - sell,
        change_abs=change_abs,
        change_pct=change_pct,
        day_high=day_high,
        day_low=day_low,
        long_pct=long_pct,
        short_pct=short_pct,
        fetched_at=iso_now(),
    )


def fetch_ig_weekend_gold_snapshot() -> WeekendGoldSnapshot | None:
    try:
        return parse_ig_weekend_gold_snapshot(http_get_text(IG_WEEKEND_GOLD_URL))
    except Exception:
        return None


def fetch_symbol_snapshot(symbol: str, label: str, interval: str, data_range: str) -> SymbolSnapshot:
    encoded_symbol = urllib.parse.quote(symbol, safe="")
    url = f"https://query1.finance.yahoo.com/v8/finance/chart/{encoded_symbol}?interval={interval}&range={data_range}"
    payload = http_get_json(url)
    result = payload["chart"]["result"][0]
    meta = result["meta"]
    timestamps = result.get("timestamp") or []
    quote = (result.get("indicators") or {}).get("quote", [{}])[0]
    closes = quote.get("close") or []
    highs = quote.get("high") or []
    lows = quote.get("low") or []
    opens = quote.get("open") or []
    volumes = quote.get("volume") or []

    points: list[PricePoint] = []
    for index, timestamp in enumerate(timestamps):
        close = closes[index] if index < len(closes) else None
        if close is None:
            continue
        points.append(
            PricePoint(
                timestamp=timestamp,
                close=float(close),
                high=float(highs[index]) if index < len(highs) and highs[index] is not None else None,
                low=float(lows[index]) if index < len(lows) and lows[index] is not None else None,
                open=float(opens[index]) if index < len(opens) and opens[index] is not None else None,
                volume=int(volumes[index]) if index < len(volumes) and volumes[index] is not None else None,
            )
        )

    if len(points) < 2:
        raise RuntimeError(f"Not enough market data returned for {symbol}.")

    price = float(meta.get("regularMarketPrice") or points[-1].close)
    previous_close_source = meta.get("previousClose") or meta.get("regularMarketPreviousClose")
    previous_close = float(previous_close_source if previous_close_source is not None else points[-2].close)
    change_abs = price - previous_close
    change_pct = (change_abs / previous_close) * 100 if previous_close else 0.0
    period_reference = points[0].close
    period_change_pct = ((price - period_reference) / period_reference) * 100 if period_reference else 0.0
    support, resistance = compute_support_resistance(points)

    day_high = meta.get("regularMarketDayHigh")
    day_low = meta.get("regularMarketDayLow")

    return SymbolSnapshot(
        symbol=symbol,
        label=label,
        price=price,
        previous_close=previous_close,
        change_abs=change_abs,
        change_pct=change_pct,
        period_change_pct=period_change_pct,
        day_high=float(day_high) if day_high is not None else None,
        day_low=float(day_low) if day_low is not None else None,
        support=support,
        resistance=resistance,
        fetched_at=iso_now(),
        points=points,
    )


def fetch_optional_symbol_snapshot(symbol: str, label: str, interval: str, data_range: str) -> SymbolSnapshot | None:
    try:
        return fetch_symbol_snapshot(symbol, label, interval, data_range)
    except Exception:
        return None


def parse_fred_date_to_timestamp(date_text: str) -> int:
    return int(datetime.strptime(date_text, "%Y-%m-%d").replace(tzinfo=timezone.utc).timestamp())


def fetch_fred_series_snapshot(series_id: str, label: str | None = None) -> SymbolSnapshot | None:
    url = FRED_CSV_URL_TEMPLATE.format(series_id=urllib.parse.quote(series_id))
    try:
        with urllib.request.urlopen(url, timeout=15) as response:
            csv_text = response.read().decode("utf-8", "ignore")
    except Exception:
        return None

    points: list[PricePoint] = []
    for raw_line in csv_text.splitlines()[1:]:
        if "," not in raw_line:
            continue
        date_text, value_text = raw_line.split(",", 1)
        value = parse_float(value_text)
        if value is None:
            continue
        try:
            timestamp = parse_fred_date_to_timestamp(date_text)
        except ValueError:
            continue
        points.append(PricePoint(timestamp=timestamp, close=value))

    if len(points) < 2:
        return None

    recent_points = points[-120:]
    current = recent_points[-1].close
    previous = recent_points[-2].close
    support, resistance = compute_support_resistance(recent_points, lookback=min(60, len(recent_points)))

    return SymbolSnapshot(
        symbol=series_id,
        label=label or FRED_SERIES_LABELS.get(series_id, series_id),
        price=current,
        previous_close=previous,
        change_abs=current - previous,
        change_pct=((current - previous) / abs(previous) * 100) if previous else 0.0,
        period_change_pct=((current - recent_points[0].close) / abs(recent_points[0].close) * 100)
        if recent_points[0].close
        else 0.0,
        day_high=max(point.close for point in recent_points[-20:]),
        day_low=min(point.close for point in recent_points[-20:]),
        support=support,
        resistance=resistance,
        fetched_at=iso_now(),
        points=recent_points,
    )


def fetch_real_yield_snapshot() -> SymbolSnapshot | None:
    return fetch_fred_series_snapshot("DFII10", FRED_SERIES_LABELS["DFII10"])


def build_official_macro_rates(
    dgs10: SymbolSnapshot | None,
    dgs2: SymbolSnapshot | None = None,
    dgs3m: SymbolSnapshot | None = None,
    dgs30: SymbolSnapshot | None = None,
    t10yie: SymbolSnapshot | None = None,
    dfii10: SymbolSnapshot | None = None,
    yahoo_us10y: SymbolSnapshot | None = None,
) -> OfficialMacroRates:
    # Backward compatibility with the pre-Phase-4.5 call shape:
    # (dgs10, dgs2, t10yie, dfii10, yahoo_us10y).
    if yahoo_us10y is None and t10yie is not None and t10yie.symbol == "^TNX":
        yahoo_us10y = t10yie
        t10yie = dgs3m
        if dgs30 is not None and dgs30.symbol == "DFII10":
            dfii10 = dgs30
            dgs30 = None
        dgs3m = None
    gap_bps = None
    if dgs10 is not None and yahoo_us10y is not None:
        gap_bps = (yahoo_us10y.price - dgs10.price) * 100
    return OfficialMacroRates(
        dgs10=dgs10,
        dgs2=dgs2,
        dgs3m=dgs3m,
        dgs30=dgs30,
        t10yie=t10yie,
        dfii10=dfii10,
        yahoo_tnx_gap_bps=gap_bps,
    )


def parse_int_field(row: dict[str, str], field_name: str) -> int:
    value = row.get(field_name, "")
    try:
        return int(str(value).replace(",", "").strip() or "0")
    except ValueError:
        return 0


def percentile_rank(value: float, history: list[float]) -> float:
    valid = [item for item in history if item is not None]
    if not valid:
        return 50.0
    below_or_equal = sum(1 for item in valid if item <= value)
    return round((below_or_equal / len(valid)) * 100, 1)


def parse_cftc_disagg_history_text(text: str) -> list[dict[str, str]]:
    rows = list(csv.DictReader(io.StringIO(text)))
    return [
        row
        for row in rows
        if row.get("CFTC_Contract_Market_Code", "").strip() == CFTC_GOLD_CONTRACT_CODE
        or row.get("Market_and_Exchange_Names", "").strip() == CFTC_GOLD_MARKET_NAME
    ]


def parse_cftc_disagg_current_text(text: str) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for raw_row in csv.reader(io.StringIO(text)):
        if len(raw_row) < len(CFTC_DISAGG_MIN_FIELDS):
            continue
        row = dict(zip(CFTC_DISAGG_MIN_FIELDS, raw_row[: len(CFTC_DISAGG_MIN_FIELDS)]))
        if row.get("CFTC_Contract_Market_Code", "").strip() == CFTC_GOLD_CONTRACT_CODE:
            rows.append(row)
    return rows


def cftc_net(row: dict[str, str], long_field: str, short_field: str) -> int:
    return parse_int_field(row, long_field) - parse_int_field(row, short_field)


def build_cftc_positioning_from_rows(
    rows: list[dict[str, str]],
    source_url: str,
) -> CFTCPositioning | None:
    valid_rows = [row for row in rows if row.get("Report_Date_as_YYYY-MM-DD")]
    valid_rows.sort(key=lambda row: row.get("Report_Date_as_YYYY-MM-DD", ""))
    if not valid_rows:
        return None

    latest = valid_rows[-1]
    previous = valid_rows[-2] if len(valid_rows) >= 2 else None

    open_interest = parse_int_field(latest, "Open_Interest_All")
    previous_open_interest = parse_int_field(previous, "Open_Interest_All") if previous else open_interest
    open_interest_change = open_interest - previous_open_interest

    managed_money_long = parse_int_field(latest, "M_Money_Positions_Long_All")
    managed_money_short = parse_int_field(latest, "M_Money_Positions_Short_All")
    managed_money_spread = parse_int_field(latest, "M_Money_Positions_Spread_All")
    managed_money_net = managed_money_long - managed_money_short
    previous_managed_money_net = (
        cftc_net(previous, "M_Money_Positions_Long_All", "M_Money_Positions_Short_All")
        if previous
        else managed_money_net
    )
    managed_money_net_change = managed_money_net - previous_managed_money_net
    managed_money_net_pct_oi = (managed_money_net / open_interest * 100) if open_interest else 0.0

    producer_long = parse_int_field(latest, "Prod_Merc_Positions_Long_All")
    producer_short = parse_int_field(latest, "Prod_Merc_Positions_Short_All")
    producer_net = producer_long - producer_short
    previous_producer_net = (
        cftc_net(previous, "Prod_Merc_Positions_Long_All", "Prod_Merc_Positions_Short_All")
        if previous
        else producer_net
    )

    swap_long = parse_int_field(latest, "Swap_Positions_Long_All")
    swap_short = parse_int_field(latest, "Swap__Positions_Short_All")
    swap_spread = parse_int_field(latest, "Swap__Positions_Spread_All")
    swap_net = swap_long - swap_short
    previous_swap_net = (
        cftc_net(previous, "Swap_Positions_Long_All", "Swap__Positions_Short_All")
        if previous
        else swap_net
    )

    non_reportable_long = parse_int_field(latest, "NonRept_Positions_Long_All")
    non_reportable_short = parse_int_field(latest, "NonRept_Positions_Short_All")
    non_reportable_net = non_reportable_long - non_reportable_short
    previous_non_reportable_net = (
        cftc_net(previous, "NonRept_Positions_Long_All", "NonRept_Positions_Short_All")
        if previous
        else non_reportable_net
    )

    managed_history = [cftc_net(row, "M_Money_Positions_Long_All", "M_Money_Positions_Short_All") for row in valid_rows]
    producer_history = [cftc_net(row, "Prod_Merc_Positions_Long_All", "Prod_Merc_Positions_Short_All") for row in valid_rows]
    managed_percentile_1y = percentile_rank(managed_money_net, managed_history[-52:])
    managed_percentile_5y = percentile_rank(managed_money_net, managed_history[-260:])
    producer_percentile_1y = percentile_rank(producer_net, producer_history[-52:])
    producer_percentile_5y = percentile_rank(producer_net, producer_history[-260:])

    net_pct_component = clamp(managed_money_net_pct_oi * 1.4, -18, 18)
    weekly_component = clamp((managed_money_net_change / open_interest * 220) if open_interest else 0, -12, 12)
    oi_component = clamp((open_interest_change / open_interest * 120) if open_interest else 0, -5, 5)
    crowding_component = -10 if managed_percentile_1y >= 90 else 8 if managed_percentile_1y <= 10 else 0
    producer_component = -8 if producer_percentile_1y <= 10 else 6 if producer_percentile_1y >= 90 else 0
    score = clamp_score(50 + (net_pct_component * 0.55) + weekly_component + oi_component + crowding_component + producer_component)

    if score >= 62:
        status = "bullish positioning"
    elif score <= 38:
        status = "bearish positioning"
    elif abs(managed_money_net_pct_oi) >= 28:
        status = "crowded positioning"
    else:
        status = "neutral positioning"

    direction = "acheteurs nets" if managed_money_net >= 0 else "vendeurs nets"
    change_text = "augmente" if managed_money_net_change > 0 else "baisse" if managed_money_net_change < 0 else "stable"
    summary = (
        f"Managed Money {direction} de {managed_money_net:+,} contrats "
        f"({managed_money_net_pct_oi:+.1f}% de l'open interest); variation hebdo {change_text} "
        f"de {managed_money_net_change:+,} contrats. Producers/Merchants net {producer_net:+,} "
        f"(percentile 1 an {producer_percentile_1y:.0f}/100)."
    )

    return CFTCPositioning(
        market=latest.get("Market_and_Exchange_Names", CFTC_GOLD_MARKET_NAME).strip(),
        contract_code=latest.get("CFTC_Contract_Market_Code", CFTC_GOLD_CONTRACT_CODE).strip(),
        report_date=latest.get("Report_Date_as_YYYY-MM-DD", ""),
        source_url=source_url,
        open_interest=open_interest,
        open_interest_change=open_interest_change,
        managed_money_long=managed_money_long,
        managed_money_short=managed_money_short,
        managed_money_spread=managed_money_spread,
        managed_money_net=managed_money_net,
        managed_money_net_change=managed_money_net_change,
        managed_money_net_pct_oi=round(managed_money_net_pct_oi, 2),
        producer_long=producer_long,
        producer_short=producer_short,
        producer_net=producer_net,
        producer_net_change=producer_net - previous_producer_net,
        swap_long=swap_long,
        swap_short=swap_short,
        swap_spread=swap_spread,
        swap_net=swap_net,
        swap_net_change=swap_net - previous_swap_net,
        non_reportable_long=non_reportable_long,
        non_reportable_short=non_reportable_short,
        non_reportable_net=non_reportable_net,
        non_reportable_net_change=non_reportable_net - previous_non_reportable_net,
        score=score,
        status=status,
        summary=summary,
        managed_money_percentile_1y=managed_percentile_1y,
        managed_money_percentile_5y=managed_percentile_5y,
        producer_net_percentile_1y=producer_percentile_1y,
        producer_net_percentile_5y=producer_percentile_5y,
    )


def fetch_cftc_gold_positioning() -> CFTCPositioning | None:
    year = datetime.now(timezone.utc).year
    history_url = CFTC_DISAGG_HISTORY_URL_TEMPLATE.format(year=year)
    try:
        req = urllib.request.Request(history_url, headers=HEADERS)
        with urllib.request.urlopen(req, timeout=20) as response:
            archive = zipfile.ZipFile(io.BytesIO(response.read()))
        file_name = archive.namelist()[0]
        text = archive.read(file_name).decode("latin-1", "ignore")
        positioning = build_cftc_positioning_from_rows(parse_cftc_disagg_history_text(text), history_url)
        if positioning is not None:
            return positioning
    except Exception:
        pass

    try:
        current_text = http_get_text(CFTC_DISAGG_CURRENT_URL)
        return build_cftc_positioning_from_rows(parse_cftc_disagg_current_text(current_text), CFTC_DISAGG_CURRENT_URL)
    except Exception:
        return None


def parse_etf_number(value: Any) -> float | None:
    if value in (None, "", "--"):
        return None
    try:
        return float(str(value).replace(",", "").strip())
    except (TypeError, ValueError):
        return None


def classify_etf_flow(weekly_flow: float | None, monthly_flow: float | None = None) -> str:
    primary = weekly_flow if weekly_flow is not None else monthly_flow
    if primary is None:
        return "unknown"
    if primary >= 1.0:
        return "inflows"
    if primary <= -1.0:
        return "outflows"
    return "flat"


def clean_wgc_columns(row: list[Any]) -> list[Any]:
    return [compact_whitespace(html.unescape(str(value))) for value in row]


def wgc_numeric_rows(period_payload: dict[str, Any] | None) -> list[list[str]]:
    if not isinstance(period_payload, dict):
        return []
    data = period_payload.get("data")
    if not isinstance(data, dict):
        return []
    rows: list[list[str]] = []
    for key, value in data.items():
        if str(key).isdigit() and isinstance(value, list):
            rows.append(clean_wgc_columns(value))
    return rows


def find_wgc_total_row(archive_data: dict[str, Any], period: str) -> list[str] | None:
    regional = archive_data.get("regional", {})
    period_payload = regional.get(period) if isinstance(regional, dict) else None
    for row in wgc_numeric_rows(period_payload):
        if row and row[0].lower() == "total":
            return row
    return None


def find_wgc_fund_row(archive_data: dict[str, Any], fund_name: str, period: str) -> list[str] | None:
    fund_name_lower = fund_name.lower()
    for group_name in ("top10_ca", "bottom10_ca"):
        group = archive_data.get(group_name, {})
        period_payload = group.get(period) if isinstance(group, dict) else None
        for row in wgc_numeric_rows(period_payload):
            if row and row[0].lower() == fund_name_lower:
                return row
    return None


def wgc_as_of_date(archive_data: dict[str, Any], period: str = "Weekly") -> str:
    regional = archive_data.get("regional", {})
    payload = regional.get(period) if isinstance(regional, dict) else None
    if isinstance(payload, dict):
        return str(payload.get("asOfDate") or payload.get("periodTitle") or "")
    return ""


def build_wgc_etf_holding_record(
    archive_data: dict[str, Any],
    fund_name: str,
    ticker: str,
    fallback_source_url: str = WGC_ETF_ARCHIVE_TABLE_URL,
) -> ETFHoldingRecord | None:
    weekly = find_wgc_fund_row(archive_data, fund_name, "Weekly")
    monthly = find_wgc_fund_row(archive_data, fund_name, "Monthly")
    ytd = find_wgc_fund_row(archive_data, fund_name, "Year to date")
    source_row = weekly or monthly or ytd
    if not source_row:
        return None

    holdings_tonnes = parse_etf_number(source_row[3] if len(source_row) > 3 else None)
    weekly_flow = parse_etf_number(weekly[4] if weekly and len(weekly) > 4 else None)
    monthly_flow = parse_etf_number(monthly[4] if monthly and len(monthly) > 4 else None)
    ytd_flow = parse_etf_number(ytd[4] if ytd and len(ytd) > 4 else None)
    flow_usd_mn = parse_etf_number((weekly or monthly or ytd)[2] if len(weekly or monthly or ytd) > 2 else None)
    return ETFHoldingRecord(
        fund=fund_name,
        ticker=ticker,
        source_name="World Gold Council ETF archive",
        source_url=fallback_source_url,
        as_of_date=wgc_as_of_date(archive_data),
        holdings_tonnes=round(holdings_tonnes, 2) if holdings_tonnes is not None else None,
        daily_flow_tonnes=None,
        weekly_flow_tonnes=round(weekly_flow, 2) if weekly_flow is not None else None,
        monthly_flow_tonnes=round(monthly_flow, 2) if monthly_flow is not None else None,
        ytd_flow_tonnes=round(ytd_flow, 2) if ytd_flow is not None else None,
        flow_usd_mn=round(flow_usd_mn, 1) if flow_usd_mn is not None else None,
        status=classify_etf_flow(weekly_flow, monthly_flow),
        note="Flux fund-specific WGC: demande en tonnes et flows USD; si le fonds n'est pas top/bottom hebdo, le mensuel/YTD sert de fallback.",
    )


def html_to_plain_text(text: str) -> str:
    return compact_whitespace(re.sub(r"<[^>]+>", " ", html.unescape(text)))


def extract_blackrock_metric(plain_text: str, label: str) -> tuple[str, float] | None:
    pattern = rf"{re.escape(label)}\s+as of\s+([A-Za-z]{{3}}\s+\d{{1,2}},\s+\d{{4}})\s+\$?([0-9,.\-]+)"
    match = re.search(pattern, plain_text)
    if not match:
        return None
    value = parse_etf_number(match.group(2))
    if value is None:
        return None
    return match.group(1), value


def parse_blackrock_spreadsheet_rows(xml_text: str) -> list[list[str]]:
    rows: list[list[str]] = []
    for row_text in re.findall(r"<ss:Row[^>]*>(.*?)</ss:Row>", xml_text, re.DOTALL):
        cells = [
            compact_whitespace(html.unescape(re.sub(r"<[^>]+>", "", cell)))
            for cell in re.findall(r"<ss:Data[^>]*>(.*?)</ss:Data>", row_text, re.DOTALL)
        ]
        if cells:
            rows.append(cells)
    return rows


def parse_ishares_iau_official_data(page_html: str, spreadsheet_xml: str) -> ETFHoldingRecord | None:
    plain = html_to_plain_text(page_html)
    tonnes_metric = extract_blackrock_metric(plain, "Tonnes in Trust")
    ounces_metric = extract_blackrock_metric(plain, "Ounces in Trust")
    shares_metric = extract_blackrock_metric(plain, "Shares Outstanding")
    if tonnes_metric is None and ounces_metric is None:
        return None

    as_of_date = tonnes_metric[0] if tonnes_metric else ounces_metric[0] if ounces_metric else shares_metric[0]
    holdings_tonnes = tonnes_metric[1] if tonnes_metric else (ounces_metric[1] / 32150.7465686 if ounces_metric else None)

    share_rows: list[tuple[str, float]] = []
    for row in parse_blackrock_spreadsheet_rows(spreadsheet_xml):
        if len(row) >= 4 and re.match(r"^[A-Za-z]{3}\s+\d{1,2},\s+\d{4}$", row[0]):
            shares = parse_etf_number(row[3])
            if shares is not None:
                share_rows.append((row[0], shares))

    daily_flow = None
    weekly_flow = None
    if holdings_tonnes is not None and share_rows:
        latest_shares = share_rows[0][1]
        tonnes_per_share = holdings_tonnes / latest_shares if latest_shares else None
        if tonnes_per_share is not None and len(share_rows) >= 2:
            daily_flow = (share_rows[0][1] - share_rows[1][1]) * tonnes_per_share
        if tonnes_per_share is not None:
            target_index = min(5, len(share_rows) - 1)
            if target_index > 0:
                weekly_flow = (share_rows[0][1] - share_rows[target_index][1]) * tonnes_per_share

    return ETFHoldingRecord(
        fund="iShares Gold Trust",
        ticker="IAU",
        source_name="BlackRock iShares official page",
        source_url=ISHARES_IAU_PAGE_URL,
        as_of_date=as_of_date or "",
        holdings_tonnes=round(holdings_tonnes, 2) if holdings_tonnes is not None else None,
        daily_flow_tonnes=round(daily_flow, 2) if daily_flow is not None else None,
        weekly_flow_tonnes=round(weekly_flow, 2) if weekly_flow is not None else None,
        monthly_flow_tonnes=None,
        ytd_flow_tonnes=None,
        flow_usd_mn=None,
        status=classify_etf_flow(weekly_flow, daily_flow),
        note="Flux estime par variation des shares outstanding BlackRock; holdings Tonnes/Ounces in Trust officiels.",
    )


def merge_etf_holding_records(records: list[ETFHoldingRecord]) -> list[ETFHoldingRecord]:
    merged: dict[str, ETFHoldingRecord] = {}
    for record in records:
        existing = merged.get(record.ticker)
        if existing is None:
            merged[record.ticker] = record
            continue
        if record.source_name.startswith("BlackRock"):
            record.monthly_flow_tonnes = existing.monthly_flow_tonnes
            record.ytd_flow_tonnes = existing.ytd_flow_tonnes
            record.flow_usd_mn = existing.flow_usd_mn
            record.note = f"{record.note} WGC conserve les flux mensuels/YTD si disponibles."
            merged[record.ticker] = record
        elif existing.source_name.startswith("BlackRock"):
            existing.monthly_flow_tonnes = record.monthly_flow_tonnes
            existing.ytd_flow_tonnes = record.ytd_flow_tonnes
            existing.flow_usd_mn = record.flow_usd_mn
        else:
            merged[record.ticker] = record
    return list(merged.values())


def build_wgc_etf_flows_analysis(archive_data: dict[str, Any]) -> ETFFlowsAnalysis | None:
    weekly_total = find_wgc_total_row(archive_data, "Weekly")
    monthly_total = find_wgc_total_row(archive_data, "Monthly")
    ytd_total = find_wgc_total_row(archive_data, "Year to date")
    if not weekly_total and not monthly_total and not ytd_total:
        return None

    source_total = weekly_total or monthly_total or ytd_total or []
    global_holdings = parse_etf_number(source_total[3] if len(source_total) > 3 else None)
    weekly_flow_usd = parse_etf_number(weekly_total[2] if weekly_total and len(weekly_total) > 2 else None)
    weekly_demand = parse_etf_number(weekly_total[4] if weekly_total and len(weekly_total) > 4 else None)
    monthly_flow_usd = parse_etf_number(monthly_total[2] if monthly_total and len(monthly_total) > 2 else None)
    monthly_demand = parse_etf_number(monthly_total[4] if monthly_total and len(monthly_total) > 4 else None)

    score = clamp_score(
        50
        + clamp((weekly_demand or 0.0) * 1.1, -16, 16)
        + clamp((monthly_demand or 0.0) * 0.18, -14, 14)
    )
    status = classify_etf_flow(weekly_demand, monthly_demand)
    if status == "inflows":
        flow_word = "entrees"
    elif status == "outflows":
        flow_word = "sorties"
    else:
        flow_word = "flux mixtes"
    summary = (
        f"WGC ETF: {flow_word} sur la semaine "
        f"({weekly_demand:+.1f}t, {weekly_flow_usd:+.0f} M$) et mois "
        f"({monthly_demand:+.1f}t, {monthly_flow_usd:+.0f} M$)."
        if weekly_demand is not None and monthly_demand is not None and weekly_flow_usd is not None and monthly_flow_usd is not None
        else "WGC ETF: flux officiels disponibles mais partiels."
    )
    holdings = [
        record
        for record in (
            build_wgc_etf_holding_record(archive_data, "SPDR Gold Shares", "GLD"),
            build_wgc_etf_holding_record(archive_data, "iShares Gold Trust", "IAU"),
        )
        if record is not None
    ]
    return ETFFlowsAnalysis(
        as_of_date=wgc_as_of_date(archive_data),
        source_name="World Gold Council ETF holdings and flows",
        source_url=WGC_ETF_FLOWS_PAGE_URL,
        global_holdings_tonnes=round(global_holdings, 2) if global_holdings is not None else None,
        global_weekly_demand_tonnes=round(weekly_demand, 2) if weekly_demand is not None else None,
        global_monthly_demand_tonnes=round(monthly_demand, 2) if monthly_demand is not None else None,
        global_weekly_flows_usd_mn=round(weekly_flow_usd, 1) if weekly_flow_usd is not None else None,
        global_monthly_flows_usd_mn=round(monthly_flow_usd, 1) if monthly_flow_usd is not None else None,
        score=score,
        status=status,
        summary=summary,
        holdings=holdings,
        source_note="WGC agrège plus de 100 produits gold-backed ETF; sources WGC: Bloomberg, company filings, ICE Benchmark Administration.",
    )


def fetch_ishares_iau_holding_record() -> ETFHoldingRecord | None:
    try:
        page_html = http_get_text(ISHARES_IAU_PAGE_URL)
        spreadsheet_xml = http_get_text(ISHARES_IAU_DATA_URL)
        return parse_ishares_iau_official_data(page_html, spreadsheet_xml)
    except Exception:
        return None


def fetch_etf_flows_analysis() -> ETFFlowsAnalysis | None:
    try:
        payload = http_get_json(WGC_ETF_ARCHIVE_TABLE_URL)
        archive_data = payload.get("chartData", {}).get("data", {})
        analysis = build_wgc_etf_flows_analysis(archive_data)
    except Exception:
        analysis = None

    iau_record = fetch_ishares_iau_holding_record()
    if analysis is None:
        if iau_record is None:
            return None
        return ETFFlowsAnalysis(
            as_of_date=iau_record.as_of_date,
            source_name="BlackRock iShares official page",
            source_url=ISHARES_IAU_PAGE_URL,
            global_holdings_tonnes=None,
            global_weekly_demand_tonnes=iau_record.weekly_flow_tonnes,
            global_monthly_demand_tonnes=None,
            global_weekly_flows_usd_mn=None,
            global_monthly_flows_usd_mn=None,
            score=clamp_score(50 + clamp((iau_record.weekly_flow_tonnes or 0.0) * 2.0, -12, 12)),
            status=iau_record.status,
            summary=f"IAU officiel: holdings {format_number(iau_record.holdings_tonnes, 2, 't')}, flux hebdo estime {format_signed_tonnes(iau_record.weekly_flow_tonnes)}.",
            holdings=[iau_record],
            source_note="Fallback IAU BlackRock; WGC ETF global indisponible.",
        )

    if iau_record is not None:
        analysis.holdings = merge_etf_holding_records([*analysis.holdings, iau_record])
    return analysis


MONTH_NAME_TO_NUMBER = {
    "january": 1,
    "february": 2,
    "march": 3,
    "april": 4,
    "may": 5,
    "june": 6,
    "july": 7,
    "august": 8,
    "september": 9,
    "october": 10,
    "november": 11,
    "december": 12,
}


def eastern_release_datetime_to_utc(year: int, month: int, day: int, hour: int = 8, minute: int = 30) -> str:
    eastern = ZoneInfo("America/New_York")
    return datetime(year, month, day, hour, minute, tzinfo=eastern).astimezone(timezone.utc).isoformat()


def fomc_statement_datetime_to_utc(year: int, month: int, day: int, hour: int = 14, minute: int = 0) -> str:
    eastern = ZoneInfo("America/New_York")
    return datetime(year, month, day, hour, minute, tzinfo=eastern).astimezone(timezone.utc).isoformat()


def parse_iso_datetime(iso_text: str) -> datetime | None:
    try:
        return datetime.fromisoformat(iso_text.replace("Z", "+00:00")).astimezone(timezone.utc)
    except ValueError:
        return None


def macro_event_minutes_to_event(scheduled_at: str, now: datetime | None = None) -> int | None:
    scheduled = parse_iso_datetime(scheduled_at)
    if scheduled is None:
        return None
    reference = now or datetime.now(timezone.utc)
    return round((scheduled - reference).total_seconds() / 60)


def macro_catalyst_status(minutes_to_event: int | None) -> str:
    if minutes_to_event is None:
        return "date inconnue"
    if minutes_to_event < -120:
        return "publie"
    if minutes_to_event < 0:
        return "en cours"
    if minutes_to_event <= 24 * 60:
        return "dans 24h"
    if minutes_to_event <= 7 * 24 * 60:
        return "cette semaine"
    return "a venir"


def format_macro_countdown(minutes: int | None) -> str:
    if minutes is None:
        return "date n/a"
    if minutes < 0:
        elapsed = abs(minutes)
        if elapsed < 60:
            return f"publie il y a {elapsed} min"
        hours = elapsed // 60
        if hours < 48:
            return f"publie il y a {hours}h"
        return f"publie il y a {hours // 24}j"
    if minutes < 60:
        return f"dans {minutes} min"
    hours = minutes // 60
    if hours < 48:
        return f"dans {hours}h"
    days = hours // 24
    return f"dans {days}j {hours % 24}h"


def classify_macro_gold_impact(event_type: str, title: str) -> tuple[str, str, str]:
    text = f"{event_type} {title}".lower()
    if text_contains_any(text, ("fomc", "fed", "powell", "speech", "minutes")):
        return (
            "HIGH",
            "Impact gold depend de la trajectoire des taux reels et du dollar apres le message Fed.",
            "Un message hawkish peut monter USD/taux et peser sur l'or; un message dovish peut detendre les taux reels et soutenir l'or.",
        )
    if text_contains_any(text, ("personal income", "outlays", "pce", "inflation")):
        return (
            "HIGH",
            "PCE/inflation est cle pour les anticipations de baisse de taux Fed et les taux reels.",
            "Inflation plus forte que prevu peut soutenir USD/taux et freiner gold; inflation plus faible peut soutenir gold via taux reels plus bas.",
        )
    if text_contains_any(text, ("gross domestic product", "gdp", "retail sales", "trade")):
        return (
            "MEDIUM",
            "La croissance US change le pricing dollar/taux et donc le cout d'opportunite de l'or.",
            "Donnee forte favorise souvent USD/taux; donnee faible favorise parfois refuge et baisse de taux, selon reaction du dollar.",
        )
    return (
        "MEDIUM",
        "Catalyseur macro a surveiller pour son impact sur USD, taux et volatilite.",
        "Le gold reagit surtout si la surprise modifie les taux reels, le dollar ou la demande refuge.",
    )


def build_macro_catalyst(
    title: str,
    event_type: str,
    scheduled_at: str,
    source_name: str,
    source_url: str,
    now: datetime | None = None,
) -> MacroCatalyst:
    minutes = macro_event_minutes_to_event(scheduled_at, now=now)
    impact_level, gold_impact, why = classify_macro_gold_impact(event_type, title)
    return MacroCatalyst(
        title=clean_display_text(title),
        event_type=clean_display_text(event_type),
        scheduled_at=scheduled_at,
        source_name=source_name,
        source_url=source_url,
        impact_level=impact_level,
        gold_impact=gold_impact,
        why_it_matters=why,
        status=macro_catalyst_status(minutes),
        minutes_to_event=minutes,
    )


def parse_fomc_calendar_events(html_text: str, now: datetime | None = None) -> list[MacroCatalyst]:
    events: list[MacroCatalyst] = []
    sections = [
        (int(match.group(1)), match.group(2))
        for match in re.finditer(
            r'<h4><a[^>]*>\s*(20\d{2})\s+FOMC Meetings\s*</a></h4></div>(.*?)(?=<div class="panel panel-default"><div class="panel-heading"><h4><a|\Z)',
            html_text,
            flags=re.IGNORECASE | re.DOTALL,
        )
    ]
    if not sections:
        clean_text = html.unescape(re.sub(r"<[^>]+>", " ", html_text))
        clean_text = re.sub(r"\s+", " ", clean_text)
        fallback_year_match = re.search(r"\b(20\d{2})\s+FOMC Meetings\b", clean_text)
        fallback_year = int(fallback_year_match.group(1)) if fallback_year_match else datetime.now(timezone.utc).year
        sections = [(fallback_year, clean_text)]

    for year, section_html in sections:
        parsed_rows: list[tuple[str, str, str | None, str | None]] = []
        for row in re.finditer(
            r'fomc-meeting__month[^>]*>\s*<strong>\s*([^<]+)\s*</strong>.*?'
            r'fomc-meeting__date[^>]*>\s*([^<]+)\s*</div>',
            section_html,
            flags=re.IGNORECASE | re.DOTALL,
        ):
            month_name = html.unescape(row.group(1)).strip()
            date_text = html.unescape(row.group(2)).strip()
            date_match = re.match(r"(\d{1,2})(?:-(\d{1,2}))?(\*)?", date_text)
            if date_match:
                parsed_rows.append((month_name, date_match.group(1), date_match.group(2), date_match.group(3)))

        if not parsed_rows:
            clean_section = html.unescape(re.sub(r"<[^>]+>", " ", section_html))
            clean_section = re.sub(r"\s+", " ", clean_section)
            parsed_rows.extend(
                match.groups()
                for match in re.finditer(
                    r"\b(January|February|March|April|May|June|July|August|September|October|November|December)\s+"
                    r"(\d{1,2})(?:-(\d{1,2}))?(\*)?",
                    clean_section,
                    flags=re.IGNORECASE,
                )
            )

        for month_name, start_day, end_day, projection in parsed_rows:
            month = MONTH_NAME_TO_NUMBER.get(month_name.lower())
            if month is None:
                continue
            decision_day = int(end_day or start_day)
            try:
                statement_at = fomc_statement_datetime_to_utc(year, month, decision_day)
            except ValueError:
                continue
            events.append(
                build_macro_catalyst(
                    title=f"FOMC decision {month_name.title()} {decision_day}, {year}",
                    event_type="FOMC decision",
                    scheduled_at=statement_at,
                    source_name="Federal Reserve FOMC calendar",
                    source_url=FED_FOMC_CALENDAR_URL,
                    now=now,
                )
            )
            if projection:
                events.append(
                    build_macro_catalyst(
                        title=f"FOMC press conference and projections {month_name.title()} {decision_day}, {year}",
                        event_type="FOMC projections",
                        scheduled_at=fomc_statement_datetime_to_utc(year, month, decision_day, hour=14, minute=30),
                        source_name="Federal Reserve FOMC calendar",
                        source_url=FED_FOMC_CALENDAR_URL,
                        now=now,
                    )
                )
            minutes_at = parse_iso_datetime(statement_at)
            if minutes_at is not None:
                events.append(
                    build_macro_catalyst(
                        title=f"FOMC minutes for {month_name.title()} meeting",
                        event_type="FOMC minutes",
                        scheduled_at=(minutes_at + timedelta(days=21)).isoformat(),
                        source_name="Federal Reserve FOMC calendar",
                        source_url=FED_FOMC_CALENDAR_URL,
                        now=now,
                    )
                )
    return events


def fallback_fomc_calendar_events(now: datetime | None = None) -> list[MacroCatalyst]:
    schedule = [
        (2026, 6, 17, True),
        (2026, 7, 29, False),
        (2026, 9, 16, True),
        (2026, 10, 28, False),
        (2026, 12, 9, True),
    ]
    events = []
    for year, month, day, projection in schedule:
        events.append(
            build_macro_catalyst(
                title=f"FOMC decision {year}-{month:02d}-{day:02d}",
                event_type="FOMC decision",
                scheduled_at=fomc_statement_datetime_to_utc(year, month, day),
                source_name="Federal Reserve FOMC calendar",
                source_url=FED_FOMC_CALENDAR_URL,
                now=now,
            )
        )
        if projection:
            events.append(
                build_macro_catalyst(
                    title=f"FOMC projections {year}-{month:02d}-{day:02d}",
                    event_type="FOMC projections",
                    scheduled_at=fomc_statement_datetime_to_utc(year, month, day, hour=14, minute=30),
                    source_name="Federal Reserve FOMC calendar",
                    source_url=FED_FOMC_CALENDAR_URL,
                    now=now,
                )
            )
    return events


def central_bank_calendar_events(now: datetime | None = None) -> list[MacroCatalyst]:
    schedules = [
        ("ECB rate decision", "European Central Bank calendar", ECB_MEETING_CALENDAR_URL, [(2026, 6, 4), (2026, 7, 23), (2026, 9, 10), (2026, 10, 29), (2026, 12, 17)]),
        ("BOE rate decision", "Bank of England MPC calendar", BOE_MEETING_CALENDAR_URL, [(2026, 6, 18), (2026, 8, 6), (2026, 9, 17), (2026, 11, 5), (2026, 12, 17)]),
        ("BOJ monetary policy decision", "Bank of Japan MPM calendar", BOJ_MEETING_CALENDAR_URL, [(2026, 6, 16), (2026, 7, 31), (2026, 9, 18), (2026, 10, 30), (2026, 12, 18)]),
    ]
    events: list[MacroCatalyst] = []
    for event_type, source_name, source_url, dates in schedules:
        for year, month, day in dates:
            scheduled_at = datetime(year, month, day, 11, 45, tzinfo=timezone.utc).isoformat()
            events.append(
                build_macro_catalyst(
                    title=f"{event_type} {year}-{month:02d}-{day:02d}",
                    event_type=event_type,
                    scheduled_at=scheduled_at,
                    source_name=source_name,
                    source_url=source_url,
                    now=now,
                )
            )
    return events


def parse_bea_release_schedule(html_text: str, now: datetime | None = None) -> list[MacroCatalyst]:
    rows = re.findall(r"<tr[^>]*>(.*?)</tr>", html_text, flags=re.IGNORECASE | re.DOTALL)
    events: list[MacroCatalyst] = []
    for row in rows:
        cell_text = html.unescape(re.sub(r"<[^>]+>", " ", row))
        cell_text = re.sub(r"\s+", " ", cell_text).strip()
        if not cell_text:
            continue
        if not text_contains_any(cell_text, ("gross domestic product", "personal income", "outlays", "pce", "retail sales", "international trade")):
            continue
        date_match = re.search(
            r"\b(January|February|March|April|May|June|July|August|September|October|November|December)\s+"
            r"(\d{1,2}),\s+(20\d{2})\s+(\d{1,2}):(\d{2})\s*(AM|PM)\b",
            cell_text,
            flags=re.IGNORECASE,
        )
        year_from_title = re.search(r"\b(20\d{2})\b", cell_text)
        if not date_match:
            date_match = re.search(
                r"\b(January|February|March|April|May|June|July|August|September|October|November|December)\s+"
                r"(\d{1,2})\s+(\d{1,2}):(\d{2})\s*(AM|PM)\b",
                cell_text,
                flags=re.IGNORECASE,
            )
            if date_match:
                month_name, day, hour, minute, meridiem = date_match.groups()
                year = year_from_title.group(1) if year_from_title else str((now or datetime.now(timezone.utc)).year)
            else:
                continue
        else:
            month_name, day, year, hour, minute, meridiem = date_match.groups()
        month = MONTH_NAME_TO_NUMBER.get(month_name.lower())
        if month is None:
            continue
        release_hour = int(hour)
        if meridiem.upper() == "PM" and release_hour != 12:
            release_hour += 12
        if meridiem.upper() == "AM" and release_hour == 12:
            release_hour = 0
        title = re.sub(re.escape(date_match.group(0)), "", cell_text).strip(" -|")
        title = re.sub(r"^(N\s*ews|R\s*elease|A\s*dvisory)\s+", "", title, flags=re.IGNORECASE).strip()
        title = title or "BEA macro release"
        try:
            scheduled_at = eastern_release_datetime_to_utc(int(year), month, int(day), release_hour, int(minute))
        except ValueError:
            continue
        events.append(
            build_macro_catalyst(
                title=title,
                event_type="BEA macro release",
                scheduled_at=scheduled_at,
                source_name="BEA news release schedule",
                source_url=BEA_RELEASE_SCHEDULE_URL,
                now=now,
            )
        )
    return events


def parse_fed_rss_events(xml_text: str, feed_name: str, source_url: str, now: datetime | None = None) -> list[MacroCatalyst]:
    try:
        root = ET.fromstring(xml_text.lstrip("\ufeff"))
    except ET.ParseError:
        return []
    events: list[MacroCatalyst] = []
    for item in root.findall(".//item")[:12]:
        title = clean_display_text(item.findtext("title", default="Federal Reserve update"))
        published_raw = item.findtext("pubDate", default="")
        try:
            published_dt = parsedate_to_datetime(published_raw).astimezone(timezone.utc)
        except (TypeError, ValueError):
            published_dt = datetime.now(timezone.utc)
        link = item.findtext("link", default=source_url)
        event_type = "Fed speech" if "speech" in feed_name.lower() else "Fed monetary policy"
        events.append(
            build_macro_catalyst(
                title=title,
                event_type=event_type,
                scheduled_at=published_dt.isoformat(),
                source_name=feed_name,
                source_url=link or source_url,
                now=now,
            )
        )
    return events


def dedupe_macro_catalysts(catalysts: list[MacroCatalyst]) -> list[MacroCatalyst]:
    seen: set[tuple[str, str]] = set()
    deduped: list[MacroCatalyst] = []
    for catalyst in catalysts:
        key = (catalyst.title.lower(), catalyst.scheduled_at[:16])
        if key in seen:
            continue
        seen.add(key)
        deduped.append(catalyst)
    return deduped


def build_macro_catalyst_calendar(now: datetime | None = None) -> MacroCatalystCalendar:
    reference = now or datetime.now(timezone.utc)
    catalysts: list[MacroCatalyst] = []
    source_notes: list[str] = []

    try:
        fomc_html = http_get_text(FED_FOMC_CALENDAR_URL)
        catalysts.extend(parse_fomc_calendar_events(fomc_html, now=reference))
        source_notes.append("Fed FOMC calendar official.")
    except Exception:
        catalysts.extend(fallback_fomc_calendar_events(now=reference))
        source_notes.append("Fed FOMC calendar fallback local 2026 active.")

    try:
        bea_html = http_get_text(BEA_RELEASE_SCHEDULE_URL)
        bea_events = parse_bea_release_schedule(bea_html, now=reference)
        catalysts.extend(bea_events)
        source_notes.append(f"BEA release schedule official ({len(bea_events)} event(s)).")
    except Exception:
        source_notes.append("BEA release schedule indisponible.")

    try:
        catalysts.extend(parse_fed_rss_events(http_get_text(FED_SPEECHES_RSS_URL), "Federal Reserve speeches RSS", FED_SPEECHES_RSS_URL, now=reference))
        catalysts.extend(parse_fed_rss_events(http_get_text(FED_MONETARY_POLICY_RSS_URL), "Federal Reserve monetary policy RSS", FED_MONETARY_POLICY_RSS_URL, now=reference))
        source_notes.append("Fed RSS speeches/monetary policy official.")
    except Exception:
        source_notes.append("Fed RSS indisponible.")

    catalysts.extend(central_bank_calendar_events(now=reference))
    source_notes.append("Calendriers ECB/BOE/BOJ planifies charges.")

    catalysts = dedupe_macro_catalysts(catalysts)
    catalysts.sort(key=lambda item: (item.minutes_to_event is None, abs(item.minutes_to_event or 10**9)))
    upcoming = [item for item in catalysts if item.minutes_to_event is None or item.minutes_to_event >= -24 * 60]
    selected = upcoming[:10] if upcoming else catalysts[:10]
    high_impact_24h = sum(
        1
        for item in selected
        if item.impact_level == "HIGH" and item.minutes_to_event is not None and -60 <= item.minutes_to_event <= 24 * 60
    )
    density_status = "high_density" if high_impact_24h >= 3 else "elevated" if high_impact_24h >= 2 else "normal"
    pre_event = next(
        (
            item
            for item in selected
            if item.impact_level == "HIGH" and item.minutes_to_event is not None and 0 <= item.minutes_to_event <= 60
        ),
        None,
    )

    return MacroCatalystCalendar(
        generated_at=reference.isoformat(),
        source_note=" ".join(source_notes),
        fedwatch_status="linked_only",
        fedwatch_note=(
            "CME FedWatch est garde comme source officielle externe. "
            "Aucune probabilite de taux n'est inventee tant qu'une API officielle accessible n'est pas disponible."
        ),
        fedwatch_source_url=CME_FEDWATCH_TOOL_URL,
        catalysts=selected,
        high_impact_24h=high_impact_24h,
        density_status=density_status,
        pre_event_active=pre_event is not None,
        pre_event_summary=(
            f"Pre-event HIGH actif: {pre_event.event_type} {format_macro_countdown(pre_event.minutes_to_event)}."
            if pre_event
            else "Aucun pre-event HIGH dans 60 minutes."
        ),
    )


def align_proxy_points_to_spot(points: list[PricePoint], spot_price: float) -> list[PricePoint]:
    if not points:
        return []

    proxy_price = points[-1].close
    offset = spot_price - proxy_price
    aligned_points: list[PricePoint] = []
    for point in points:
        aligned_points.append(
            PricePoint(
                timestamp=point.timestamp,
                close=point.close + offset,
                high=(point.high + offset) if point.high is not None else point.close + offset,
                low=(point.low + offset) if point.low is not None else point.close + offset,
                open=(point.open + offset) if point.open is not None else point.close + offset,
                volume=point.volume,
            )
        )

    last_point = aligned_points[-1]
    last_point.close = spot_price
    last_point.high = max(last_point.high if last_point.high is not None else spot_price, spot_price)
    last_point.low = min(last_point.low if last_point.low is not None else spot_price, spot_price)
    return aligned_points


def aggregate_points(points: list[PricePoint], bucket_seconds: int) -> list[PricePoint]:
    buckets: dict[int, PricePoint] = {}

    for point in sorted(points, key=lambda item: item.timestamp):
        bucket_key = point.timestamp - (point.timestamp % bucket_seconds)
        if bucket_key not in buckets:
            buckets[bucket_key] = PricePoint(
                timestamp=bucket_key,
                open=point.open if point.open is not None else point.close,
                high=point.high if point.high is not None else point.close,
                low=point.low if point.low is not None else point.close,
                close=point.close,
                volume=point.volume or 0,
            )
            continue

        bucket = buckets[bucket_key]
        bucket.close = point.close
        bucket.high = max(
            bucket.high if bucket.high is not None else point.close,
            point.high if point.high is not None else point.close,
        )
        bucket.low = min(
            bucket.low if bucket.low is not None else point.close,
            point.low if point.low is not None else point.close,
        )
        bucket.volume = (bucket.volume or 0) + (point.volume or 0)

    return [buckets[key] for key in sorted(buckets.keys())]


CHART_TIMEFRAME_SECONDS = {
    "M1": 60,
    "M5": 5 * 60,
    "M15": 15 * 60,
    "H1": 60 * 60,
    "H4": 4 * 60 * 60,
    "D1": 24 * 60 * 60,
}

CHART_MIN_CANDLES = {
    "M5": 50,
    "M15": 50,
    "H1": 80,
    "H4": 50,
    "D1": 120,
}

CHART_MAX_AGE_MINUTES = {
    "M5": 60,
    "M15": 90,
    "H1": 240,
    "H4": 720,
    "D1": 4320,
}


def price_points_to_candles(
    points: list[PricePoint],
    timeframe: str,
    source: str,
    fetched_at: str,
) -> list[OHLCCandle]:
    candles_by_timestamp: dict[int, OHLCCandle] = {}
    for point in sorted(points, key=lambda item: item.timestamp):
        open_price = point.open if point.open is not None else point.close
        high_price = point.high if point.high is not None else point.close
        low_price = point.low if point.low is not None else point.close
        candles_by_timestamp[point.timestamp] = OHLCCandle(
            timestamp=point.timestamp,
            open=float(open_price),
            high=float(high_price),
            low=float(low_price),
            close=float(point.close),
            volume=point.volume,
            source=source,
            timeframe=timeframe,
            fetched_at=fetched_at,
        )
    return [candles_by_timestamp[key] for key in sorted(candles_by_timestamp.keys())]


def detect_chart_gaps(candles: list[OHLCCandle], timeframe: str) -> int:
    expected = CHART_TIMEFRAME_SECONDS.get(timeframe)
    if not expected or len(candles) < 2:
        return 0
    gap_count = 0
    previous = candles[0]
    for candle in candles[1:]:
        if candle.timestamp - previous.timestamp > expected * 2.5:
            gap_count += 1
        previous = candle
    return gap_count


def resample_candles(candles: list[OHLCCandle], target_timeframe: str) -> list[OHLCCandle]:
    bucket_seconds = CHART_TIMEFRAME_SECONDS[target_timeframe]
    buckets: dict[int, list[OHLCCandle]] = {}
    for candle in sorted(candles, key=lambda item: item.timestamp):
        bucket_key = candle.timestamp - (candle.timestamp % bucket_seconds)
        buckets.setdefault(bucket_key, []).append(candle)

    resampled: list[OHLCCandle] = []
    for timestamp in sorted(buckets.keys()):
        bucket = buckets[timestamp]
        first = bucket[0]
        last = bucket[-1]
        volumes = [item.volume for item in bucket if item.volume is not None]
        resampled.append(
            OHLCCandle(
                timestamp=timestamp,
                open=first.open,
                high=max(item.high for item in bucket),
                low=min(item.low for item in bucket),
                close=last.close,
                volume=sum(volumes) if volumes else None,
                source=first.source,
                timeframe=target_timeframe,
                fetched_at=last.fetched_at,
            )
        )
    return resampled


def build_chart_timeframe(
    timeframe: str,
    points: list[PricePoint],
    source: str,
    fetched_at: str,
    now: datetime | None = None,
) -> ChartTimeframe:
    candles = price_points_to_candles(points, timeframe, source, fetched_at)
    freshness = age_minutes_from_iso(fetched_at, now=now)
    gap_count = detect_chart_gaps(candles, timeframe)
    quality_flags: list[str] = []
    min_candles = CHART_MIN_CANDLES.get(timeframe, 20)
    max_age = CHART_MAX_AGE_MINUTES.get(timeframe, 240)

    if not candles:
        return ChartTimeframe(timeframe=timeframe, status="OFFLINE", quality_flags=["source indisponible"])
    if len(candles) < min_candles:
        quality_flags.append(f"historique insuffisant: {len(candles)}/{min_candles} bougies")
    if freshness is not None and freshness > max_age:
        quality_flags.append(f"stale: {freshness} min > {max_age} min")
    if gap_count:
        quality_flags.append(f"{gap_count} gap(s) detecte(s)")

    if any(flag.startswith("stale") for flag in quality_flags):
        status = "STALE"
    elif len(candles) < min_candles:
        status = "INSUFFICIENT_HISTORY"
    else:
        status = "READY"

    return ChartTimeframe(
        timeframe=timeframe,
        status=status,
        candles=candles,
        quality_flags=quality_flags,
        last_timestamp=candles[-1].timestamp,
        freshness_minutes=freshness,
        gap_count=gap_count,
    )


def build_chart_store(
    points_by_timeframe: dict[str, list[PricePoint]],
    source: str,
    fetched_at: str,
    now: datetime | None = None,
) -> ChartStore:
    generated_at = (now or datetime.now(timezone.utc)).replace(microsecond=0).isoformat()
    timeframe_order = ["M5", "M15", "H1", "H4", "D1"]
    timeframes = [
        build_chart_timeframe(timeframe, points_by_timeframe.get(timeframe, []), source, fetched_at, now=now)
        for timeframe in timeframe_order
    ]
    ready = [item for item in timeframes if item.status == "READY"]
    insufficient = [item for item in timeframes if item.status == "INSUFFICIENT_HISTORY"]
    stale = [item for item in timeframes if item.status == "STALE"]
    offline = [item for item in timeframes if item.status == "OFFLINE"]
    if len(offline) == len(timeframes):
        status = "OFFLINE"
    elif stale:
        status = "STALE"
    elif insufficient:
        status = "INSUFFICIENT_HISTORY"
    elif len(ready) == len(timeframes):
        status = "READY"
    else:
        status = "DEGRADED"
    summary = (
        f"Chart Store {status}: {len(ready)}/{len(timeframes)} timeframe(s) READY; "
        f"{sum(item.gap_count for item in timeframes)} gap(s) detecte(s)."
    )
    return ChartStore(
        generated_at=generated_at,
        symbol="XAU/USD",
        source=source,
        status=status,
        summary=summary,
        timeframes=timeframes,
    )


def persist_chart_store_cache_safely(chart_store: ChartStore, path: Path = CHART_STORE_CACHE_PATH) -> None:
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(asdict(chart_store), ensure_ascii=False, indent=2), encoding="utf-8")
    except Exception:
        return


def ema_series(values: list[float], period: int) -> list[float | None]:
    if len(values) < period:
        return [None] * len(values)

    alpha = 2 / (period + 1)
    initial = sum(values[:period]) / period
    result: list[float | None] = [None] * (period - 1) + [initial]
    ema_value = initial

    for value in values[period:]:
        ema_value = ((value - ema_value) * alpha) + ema_value
        result.append(ema_value)

    return result


def sma_last(values: list[float], period: int) -> float | None:
    if len(values) < period:
        return None
    return sum(values[-period:]) / period


def rsi_series(values: list[float], period: int = 7) -> list[float | None]:
    if len(values) < period + 1:
        return [None] * len(values)

    deltas = [values[index] - values[index - 1] for index in range(1, len(values))]
    gains = [max(delta, 0.0) for delta in deltas]
    losses = [abs(min(delta, 0.0)) for delta in deltas]

    avg_gain = sum(gains[:period]) / period
    avg_loss = sum(losses[:period]) / period
    result: list[float | None] = [None] * period

    rs = avg_gain / avg_loss if avg_loss else float("inf")
    result.append(100 - (100 / (1 + rs)))

    for index in range(period, len(deltas)):
        avg_gain = ((avg_gain * (period - 1)) + gains[index]) / period
        avg_loss = ((avg_loss * (period - 1)) + losses[index]) / period
        rs = avg_gain / avg_loss if avg_loss else float("inf")
        result.append(100 - (100 / (1 + rs)))

    return result


def macd_with_sma_signal(values: list[float], fast_period: int = 5, slow_period: int = 34, signal_period: int = 5) -> tuple[float, float, float]:
    fast = ema_series(values, fast_period)
    slow = ema_series(values, slow_period)
    macd_line_series: list[float | None] = []

    for fast_value, slow_value in zip(fast, slow):
        if fast_value is None or slow_value is None:
            macd_line_series.append(None)
        else:
            macd_line_series.append(fast_value - slow_value)

    macd_values = [value for value in macd_line_series if value is not None]
    if len(macd_values) < signal_period:
        raise RuntimeError("Pas assez de donnees pour calculer la MACD.")

    macd_line = macd_values[-1]
    signal = sma_last(macd_values, signal_period)
    if signal is None:
        raise RuntimeError("Pas assez de donnees pour calculer le signal MACD.")

    return macd_line, signal, macd_line - signal


def atr_series(points: list[PricePoint], period: int = 14) -> list[float | None]:
    if len(points) < period + 1:
        return [None] * len(points)

    true_ranges: list[float] = []
    for index, point in enumerate(points):
        high = point.high if point.high is not None else point.close
        low = point.low if point.low is not None else point.close
        if index == 0:
            true_ranges.append(high - low)
            continue
        previous_close = points[index - 1].close
        true_ranges.append(
            max(
                high - low,
                abs(high - previous_close),
                abs(low - previous_close),
            )
        )

    initial = sum(true_ranges[1: period + 1]) / period
    result: list[float | None] = [None] * period + [initial]
    atr_value = initial

    for tr in true_ranges[period + 1:]:
        atr_value = ((atr_value * (period - 1)) + tr) / period
        result.append(atr_value)

    return result


def volume_ratio(points: list[PricePoint], lookback: int = 20) -> float:
    volumes = [float(point.volume or 0) for point in points if point.volume not in (None, 0)]
    if len(volumes) < lookback + 1:
        return 1.0
    average = sum(volumes[-(lookback + 1):-1]) / lookback
    if average == 0:
        return 1.0
    return volumes[-1] / average


def compute_price_change_pct(points: list[PricePoint]) -> float:
    if len(points) < 2 or points[-2].close == 0:
        return 0.0
    return ((points[-1].close - points[-2].close) / points[-2].close) * 100


def build_technical_reading(timeframe: str, points: list[PricePoint]) -> TechnicalReading:
    closes = [point.close for point in points]
    if len(closes) < 210:
        raise RuntimeError(f"Pas assez de donnees pour le timeframe {timeframe}.")

    ema20 = ema_series(closes, 20)[-1]
    ema50 = ema_series(closes, 50)[-1]
    ema100 = ema_series(closes, 100)[-1]
    ema200 = ema_series(closes, 200)[-1]
    rsi7 = rsi_series(closes, 7)[-1]
    atr14 = atr_series(points, 14)[-1]

    if None in (ema20, ema50, ema100, ema200, rsi7, atr14):
        raise RuntimeError(f"Indicateurs incomplets pour le timeframe {timeframe}.")

    macd_line, macd_signal, macd_histogram = macd_with_sma_signal(closes, fast_period=5, slow_period=34, signal_period=5)
    last_close = closes[-1]
    latest_change_pct = compute_price_change_pct(points)
    latest_volume_ratio = volume_ratio(points)

    score = 0.0
    reasons: list[str] = []

    for label, ema_value in [("EMA20", ema20), ("EMA50", ema50), ("EMA100", ema100), ("EMA200", ema200)]:
        if last_close > ema_value:
            score += 0.75
            reasons.append(f"{label} soutient le prix")
        else:
            score -= 0.75
            reasons.append(f"{label} agit en resistance")

    if ema20 > ema50 > ema100 > ema200:
        score += 2.0
        reasons.append("Empilement EMA haussier")
    elif ema20 < ema50 < ema100 < ema200:
        score -= 2.0
        reasons.append("Empilement EMA baissier")

    if rsi7 >= 85:
        score -= 1.0
        reasons.append("RSI7 en zone de surachat")
    elif rsi7 >= 50:
        score += 1.5
        reasons.append("RSI7 au-dessus de 50")
    elif rsi7 <= 15:
        score += 0.5
        reasons.append("RSI7 en zone d'epuisement vendeur")
    else:
        score -= 1.5
        reasons.append("RSI7 sous 50")

    if macd_histogram > 0:
        score += 2.0
        reasons.append("MACD 5/34/5 positive")
    else:
        score -= 2.0
        reasons.append("MACD 5/34/5 negative")

    if macd_line > 0:
        score += 0.5
    else:
        score -= 0.5

    if latest_volume_ratio >= 1.15:
        if latest_change_pct >= 0:
            score += 1.0
            reasons.append("Volume acheteur au-dessus de la moyenne")
        else:
            score -= 1.0
            reasons.append("Volume vendeur au-dessus de la moyenne")
    elif latest_volume_ratio <= 0.85:
        reasons.append("Volume en retrait")
    else:
        reasons.append("Volume proche de la moyenne")

    verdict = "BUY" if score >= 0 else "SELL"
    return TechnicalReading(
        timeframe=timeframe,
        close=last_close,
        ema20=float(ema20),
        ema50=float(ema50),
        ema100=float(ema100),
        ema200=float(ema200),
        rsi7=float(rsi7),
        macd_line=macd_line,
        macd_signal=macd_signal,
        macd_histogram=macd_histogram,
        volume_ratio=latest_volume_ratio,
        atr14=float(atr14),
        score=score,
        verdict=verdict,
        reasons=reasons[:5],
    )


def fetch_technical_timeframes() -> tuple[list[TechnicalReading], float, list[PricePoint], ChartStore]:
    points_5m = fetch_symbol_snapshot("GC=F", "Gold futures 5m", interval="5m", data_range="5d").points
    points_15m = fetch_symbol_snapshot("GC=F", "Gold futures 15m", interval="15m", data_range="10d").points
    points_1h = fetch_symbol_snapshot("GC=F", "Gold futures 1h", interval="60m", data_range="6mo").points
    points_1d = fetch_symbol_snapshot("GC=F", "Gold futures 1d", interval="1d", data_range="2y").points
    points_4h = aggregate_points(points_1h, bucket_seconds=4 * 60 * 60)
    fetched_at = iso_now()
    chart_store = build_chart_store(
        {
            "M5": points_5m,
            "M15": points_15m,
            "H1": points_1h,
            "H4": points_4h,
            "D1": points_1d,
        },
        source="Yahoo Finance GC=F proxy",
        fetched_at=fetched_at,
    )
    persist_chart_store_cache_safely(chart_store)

    timeframe_map = [
        ("1D", points_1d),
        ("4H", points_4h),
        ("1H", points_1h),
        ("15m", points_15m),
        ("5m", points_5m),
    ]
    readings = [build_technical_reading(timeframe, points) for timeframe, points in timeframe_map]
    proxy_current_price = points_15m[-1].close
    return readings, proxy_current_price, points_5m, chart_store


def adjust_proxy_level_to_spot(level: float, spot_price: float, proxy_price: float) -> float:
    return level + (spot_price - proxy_price)


def clamp(value: float, lower: float, upper: float) -> float:
    return max(lower, min(upper, value))


def build_trade_levels(price: float, atr: float, verdict: str, stop_multiplier: float, tp1_multiplier: float, tp2_multiplier: float) -> tuple[float, float, float]:
    if verdict == "BUY":
        return (
            price - (atr * stop_multiplier),
            price + (atr * tp1_multiplier),
            price + (atr * tp2_multiplier),
        )
    return (
        price + (atr * stop_multiplier),
        price - (atr * tp1_multiplier),
        price - (atr * tp2_multiplier),
    )


def psychological_levels_around(price: float, atr: float, depth: int = 8) -> tuple[list[float], list[float]]:
    step = 25.0 if atr >= 10.0 else 50.0
    anchor = (price // step) * step
    levels = sorted({round(anchor + step * offset, 2) for offset in range(-depth, depth + 1)})
    below = [level for level in levels if level < price]
    above = [level for level in levels if level > price]
    return below, above


def trade_setup_from_structure(structure: str, direction: str = "BUY") -> str:
    text = structure.lower()
    if "breakout" in text or "breakdown" in text or "cassure" in text:
        return "breakout"
    if "range" in text:
        return "range"
    if "reversal" in text or "pivot" in text or "rejet" in text:
        return "pivot_rejection"
    if "pullback" in text:
        return "trend_continuation"
    if "mean" in text or "extreme" in text:
        return "mean_reversion"
    return "trend_continuation" if direction in {"BUY", "SELL"} else "range"


def setup_level_profile(setup_type: str) -> tuple[float, float, float, float]:
    profiles = {
        "trend_continuation": (0.85, 1.65, 2.65, 4.00),
        "breakout": (0.95, 1.80, 3.00, 4.60),
        "range": (0.70, 1.50, 2.20, 3.00),
        "mean_reversion": (0.75, 1.55, 2.30, 3.20),
        "pivot_rejection": (0.80, 1.60, 2.45, 3.50),
        "news_reaction": (0.72, 1.65, 2.65, 4.00),
        "reversal_scalp": (0.55, 1.55, 2.40, 3.30),
        "reversal_intraday": (0.65, 1.60, 2.50, 3.60),
        "reversal_swing": (0.75, 1.70, 2.65, 4.00),
    }
    return profiles.get(setup_type, profiles["trend_continuation"])


def sorted_unique_levels(levels: list[float], price: float, direction: str) -> list[float]:
    clean = sorted({round(level, 2) for level in levels if level and level > 0})
    if direction == "BUY":
        return [level for level in clean if level > price]
    return sorted([level for level in clean if level < price], reverse=True)


def market_structure_reference_levels(
    gold: SymbolSnapshot,
    atr: float,
    readings: list[TechnicalReading] | None = None,
    proxy_price: float | None = None,
) -> tuple[list[float], list[float], list[str]]:
    levels = price_action_levels(gold)
    lower = [
        levels.get("support"),
        levels.get("camarilla_s3"),
        levels.get("camarilla_s4"),
        gold.day_low,
        gold.support,
    ]
    upper = [
        levels.get("resistance"),
        levels.get("camarilla_r3"),
        levels.get("camarilla_r4"),
        gold.day_high,
        gold.resistance,
    ]
    reasons = ["Niveaux marche: support/resistance jour + pivots Camarilla."]
    swing = detect_recent_swing_levels(gold.intraday_points or gold.points)
    if swing.get("status") == "ok":
        lower.append(float(swing["swing_low"]))
        upper.append(float(swing["swing_high"]))
        reasons.append(str(swing["summary"]))
    psych_below, psych_above = psychological_levels_around(gold.price, atr)
    lower.extend(psych_below[-3:])
    upper.extend(psych_above[:3])
    reasons.append("Niveaux psychologiques: 00/50, avec 25 en volatilite elevee.")
    if readings and proxy_price is not None:
        ema_values: list[float] = []
        for reading in readings:
            if reading.timeframe in {"4H", "1H", "15m"}:
                ema_values.extend([reading.ema20, reading.ema50, reading.ema100, reading.ema200])
        adjusted = [adjust_proxy_level_to_spot(value, gold.price, proxy_price) for value in ema_values if value > 0]
        lower.extend([value for value in adjusted if value < gold.price])
        upper.extend([value for value in adjusted if value > gold.price])
        reasons.append("Niveaux EMA H1/H4/M15 ajustes du proxy GC=F vers le spot.")
    return (
        sorted({round(level, 2) for level in lower if level is not None and level > 0}),
        sorted({round(level, 2) for level in upper if level is not None and level > 0}),
        reasons,
    )


def ensure_target_sequence(direction: str, entry: float, stop_loss: float, targets: list[float], min_rr: float = 1.5) -> tuple[float, float, float, float, float, float]:
    risk = max(abs(entry - stop_loss), 1.0)
    if direction == "BUY":
        min_targets = [entry + risk * min_rr, entry + risk * 2.35, entry + risk * 3.35]
        selected: list[float] = []
        for fallback in min_targets:
            candidate = next((target for target in targets if target >= fallback), fallback)
            selected.append(max(candidate, fallback))
        tp1, tp2, tp3 = selected
        if not (stop_loss < entry < tp1 < tp2 < tp3):
            tp1, tp2, tp3 = min_targets
    else:
        min_targets = [entry - risk * min_rr, entry - risk * 2.35, entry - risk * 3.35]
        selected = []
        for fallback in min_targets:
            candidate = next((target for target in targets if target <= fallback), fallback)
            selected.append(min(candidate, fallback))
        tp1, tp2, tp3 = selected
        if not (stop_loss > entry > tp1 > tp2 > tp3):
            tp1, tp2, tp3 = min_targets
    rr1 = compute_risk_reward(direction, entry, stop_loss, tp1)
    rr2 = compute_risk_reward(direction, entry, stop_loss, tp2)
    rr3 = compute_risk_reward(direction, entry, stop_loss, tp3)
    return round(tp1, 2), round(tp2, 2), round(tp3, 2), rr1, rr2, rr3


def build_market_trade_levels(
    gold: SymbolSnapshot,
    direction: str,
    setup_type: str,
    atr: float,
    readings: list[TechnicalReading] | None = None,
    proxy_price: float | None = None,
    min_rr: float = 1.5,
    event_mode: EventModeAnalysis | None = None,
) -> MarketTradeLevels:
    direction = "BUY" if "BUY" in direction.upper() else "SELL"
    setup_type = setup_type or "trend_continuation"
    entry = gold.price
    atr = max(atr, 3.0)
    if event_mode is not None and event_mode.active:
        atr *= max(1.0, event_mode.stop_multiplier)
    stop_mult, tp1_mult, tp2_mult, tp3_mult = setup_level_profile(setup_type)
    lower_levels, upper_levels, reasons = market_structure_reference_levels(gold, atr, readings, proxy_price)
    min_risk = max(atr * stop_mult, 3.0)
    buffer = max(atr * 0.18, 1.5)
    if direction == "BUY":
        below = [level for level in lower_levels if level < entry]
        structural_stop = (max(below) - buffer) if below else entry - min_risk
        stop_loss = min(structural_stop, entry - min_risk)
        candidate_targets = sorted_unique_levels(upper_levels + [entry + atr * tp1_mult, entry + atr * tp2_mult, entry + atr * tp3_mult], entry, "BUY")
    else:
        above = [level for level in upper_levels if level > entry]
        structural_stop = (min(above) + buffer) if above else entry + min_risk
        stop_loss = max(structural_stop, entry + min_risk)
        candidate_targets = sorted_unique_levels(lower_levels + [entry - atr * tp1_mult, entry - atr * tp2_mult, entry - atr * tp3_mult], entry, "SELL")
    tp1, tp2, tp3, rr1, rr2, rr3 = ensure_target_sequence(direction, entry, stop_loss, candidate_targets, min_rr=min_rr)
    risk = abs(entry - stop_loss)
    entry_padding = max(1.0, min(risk * 0.16, atr * 0.35))
    validity_map = {
        "news_reaction": (30, "NEWS"),
        "reversal_scalp": (30, "M5"),
        "reversal_intraday": (90, "M15"),
        "reversal_swing": (720, "H1"),
        "breakout": (240, "M15"),
        "range": (120, "M5"),
        "mean_reversion": (240, "M15"),
        "pivot_rejection": (720, "H1"),
        "trend_continuation": (720, "H1"),
    }
    validity_minutes, validity_timeframe = validity_map.get(setup_type, (240, "M15"))
    if event_mode is not None and event_mode.active:
        validity_minutes = max(30, round(validity_minutes * 0.75))
    reasons.append(
        f"Setup {setup_type}: risque {risk:.2f}, TP partiels 50/30/20, R/R TP1 {rr1:.2f}."
    )
    return MarketTradeLevels(
        direction=direction,
        setup_type=setup_type,
        entry_zone_low=round(entry - entry_padding, 2),
        entry_zone_high=round(entry + entry_padding, 2),
        stop_loss=round(stop_loss, 2),
        tp1=tp1,
        tp2=tp2,
        tp3=tp3,
        risk_reward_tp1=rr1,
        risk_reward_tp2=rr2,
        risk_reward_tp3=rr3,
        validity_minutes=validity_minutes,
        validity_timeframe=validity_timeframe,
        partial_tp1_pct=50,
        partial_tp2_pct=30,
        partial_tp3_pct=20,
        reasons=reasons[:6],
    )


def reading_for_timeframe(readings: list[TechnicalReading], timeframe: str) -> TechnicalReading | None:
    aliases = {
        "M5": "5m",
        "M15": "15m",
        "H1": "1H",
        "H4": "4H",
        "D1": "1D",
    }
    target = aliases.get(timeframe, timeframe)
    return next((reading for reading in readings if reading.timeframe == target), None)


def candles_for_timeframe(chart_store: ChartStore | None, timeframe: str) -> list[OHLCCandle]:
    if chart_store is None:
        return []
    aliases = {
        "5m": "M5",
        "15m": "M15",
        "1H": "H1",
        "4H": "H4",
        "1D": "D1",
    }
    target = aliases.get(timeframe, timeframe)
    for item in chart_store.timeframes:
        if item.timeframe == target and item.status == "READY":
            return item.candles
    return []


def detect_rsi_divergence(closes: list[float], rsi_values: list[float | None], window: int = 8) -> dict[str, Any] | None:
    paired = [
        (float(close), float(rsi))
        for close, rsi in zip(closes[-window:], rsi_values[-window:])
        if rsi is not None
    ]
    if len(paired) < 5:
        return None
    prices = [item[0] for item in paired]
    rsis = [item[1] for item in paired]
    latest_index = len(paired) - 1
    latest_price = prices[-1]
    latest_rsi = rsis[-1]
    previous_prices = prices[:-1]
    previous_rsis = rsis[:-1]
    if not previous_prices:
        return None

    previous_low_index = min(range(len(previous_prices)), key=lambda index: previous_prices[index])
    previous_high_index = max(range(len(previous_prices)), key=lambda index: previous_prices[index])
    previous_low_price = previous_prices[previous_low_index]
    previous_high_price = previous_prices[previous_high_index]
    previous_low_rsi = previous_rsis[previous_low_index]
    previous_high_rsi = previous_rsis[previous_high_index]

    if latest_price < previous_low_price and latest_rsi > previous_low_rsi:
        strength = min(1.0, ((previous_low_price - latest_price) / max(abs(previous_low_price), 1.0) * 100) + ((latest_rsi - previous_low_rsi) / 20))
        return {"direction": "BUY", "strength": round(strength, 2), "latest_index": latest_index}
    if latest_price > previous_high_price and latest_rsi < previous_high_rsi:
        strength = min(1.0, ((latest_price - previous_high_price) / max(abs(previous_high_price), 1.0) * 100) + ((previous_high_rsi - latest_rsi) / 20))
        return {"direction": "SELL", "strength": round(strength, 2), "latest_index": latest_index}
    return None


def reversal_no_trade(
    horizon: str,
    direction: str,
    tf_signal: str,
    tf_context: str,
    validity_minutes: int,
    reason: str,
    confluence_score: int = 0,
    detected_at: str | None = None,
    blockers: list[str] | None = None,
) -> ReversalSetup:
    return ReversalSetup(
        horizon=horizon,
        status="NO_REVERSAL_TRADE",
        direction=direction if direction in {"BUY", "SELL"} else "NEUTRAL",
        tf_signal=tf_signal,
        tf_context=tf_context,
        confluence_score=confluence_score,
        conditions_met=[],
        entry_zone_low=0.0,
        entry_zone_high=0.0,
        stop_loss=0.0,
        tp1=0.0,
        tp2=0.0,
        tp3=0.0,
        risk_reward_tp1=0.0,
        validity_minutes=validity_minutes,
        reasons=[reason],
        blockers=blockers or [],
        detected_at=detected_at or iso_now(),
    )


def check_reversal_conditions(
    direction: str,
    reading: TechnicalReading,
    candles: list[OHLCCandle],
    gold: SymbolSnapshot,
) -> list[dict[str, Any]]:
    if len(candles) < 12:
        return [
            {"name": "history", "met": False, "reason": "Historique OHLC insuffisant pour detecter un retournement."}
        ]
    closes = [candle.close for candle in candles]
    rsi_values = rsi_series(closes, 7)
    divergence = detect_rsi_divergence(closes, rsi_values, window=8)
    last = candles[-1]
    previous = candles[-13:-1]
    swing_low = min(candle.low for candle in previous)
    swing_high = max(candle.high for candle in previous)
    range_position = price_range_position(gold)
    if direction == "BUY":
        return [
            {"name": "rsi_extreme", "met": reading.rsi7 <= 18, "reason": f"RSI7 {reading.rsi7:.1f} en survente extreme."},
            {"name": "divergence", "met": bool(divergence and divergence["direction"] == "BUY"), "reason": "Divergence bullish: prix plus bas, RSI plus haut."},
            {"name": "swing_rejection", "met": last.low <= swing_low and last.close > swing_low, "reason": f"Rejet du swing low {swing_low:.2f}, cloture {last.close:.2f} au-dessus."},
            {"name": "volume_spike", "met": reading.volume_ratio > 1.5, "reason": f"Volume proxy {reading.volume_ratio:.2f}x moyenne."},
            {"name": "range_position", "met": range_position <= 20, "reason": f"Prix dans les {range_position:.0f}% inferieurs du range jour."},
        ]
    return [
        {"name": "rsi_extreme", "met": reading.rsi7 >= 82, "reason": f"RSI7 {reading.rsi7:.1f} en surachat extreme."},
        {"name": "divergence", "met": bool(divergence and divergence["direction"] == "SELL"), "reason": "Divergence bearish: prix plus haut, RSI plus bas."},
        {"name": "swing_rejection", "met": last.high >= swing_high and last.close < swing_high, "reason": f"Rejet du swing high {swing_high:.2f}, cloture {last.close:.2f} en dessous."},
        {"name": "volume_spike", "met": reading.volume_ratio > 1.5, "reason": f"Volume proxy {reading.volume_ratio:.2f}x moyenne."},
        {"name": "range_position", "met": range_position >= 80, "reason": f"Prix dans les {100 - range_position:.0f}% superieurs du range jour."},
    ]


def check_reversal_context_filter(
    direction: str,
    context_reading: TechnicalReading | None,
    context_candles: list[OHLCCandle],
) -> str | None:
    if context_reading is None:
        return "Timeframe contexte indisponible."
    closes = [candle.close for candle in context_candles]
    rsi_values = [value for value in rsi_series(closes, 7) if value is not None]
    recent = rsi_values[-5:]
    if direction == "BUY" and context_reading.rsi7 <= 25 and len(recent) >= 5 and all(value <= 30 for value in recent):
        return f"Contexte {context_reading.timeframe} encore en tendance baissiere forte."
    if direction == "SELL" and context_reading.rsi7 >= 75 and len(recent) >= 5 and all(value >= 70 for value in recent):
        return f"Contexte {context_reading.timeframe} encore en tendance haussiere forte."
    return None


def detect_reversal_setup(
    horizon: str,
    tf_signal: str,
    tf_context: str,
    gold: SymbolSnapshot,
    readings: list[TechnicalReading],
    chart_store: ChartStore | None,
    validity_minutes: int,
    now: datetime | None = None,
) -> ReversalSetup:
    detected_at = (now or datetime.now(timezone.utc)).replace(microsecond=0).isoformat()
    signal_reading = reading_for_timeframe(readings, tf_signal)
    context_reading = reading_for_timeframe(readings, tf_context)
    signal_candles = candles_for_timeframe(chart_store, tf_signal)
    context_candles = candles_for_timeframe(chart_store, tf_context)
    if signal_reading is None or not signal_candles:
        return reversal_no_trade(horizon, "NEUTRAL", tf_signal, tf_context, validity_minutes, "Donnees signal indisponibles.", detected_at=detected_at)

    buy_conditions = check_reversal_conditions("BUY", signal_reading, signal_candles, gold)
    sell_conditions = check_reversal_conditions("SELL", signal_reading, signal_candles, gold)
    buy_met = [item for item in buy_conditions if item["met"]]
    sell_met = [item for item in sell_conditions if item["met"]]
    if len(buy_met) >= 3 and len(buy_met) > len(sell_met):
        direction = "BUY"
        selected = buy_met
        all_selected = buy_conditions
    elif len(sell_met) >= 3 and len(sell_met) > len(buy_met):
        direction = "SELL"
        selected = sell_met
        all_selected = sell_conditions
    else:
        best = max(len(buy_met), len(sell_met))
        reason = f"Conditions reversal insuffisantes: BUY {len(buy_met)}/5, SELL {len(sell_met)}/5."
        return reversal_no_trade(horizon, "NEUTRAL", tf_signal, tf_context, validity_minutes, reason, confluence_score=best, detected_at=detected_at)

    context_blocker = check_reversal_context_filter(direction, context_reading, context_candles)
    if context_blocker:
        return reversal_no_trade(horizon, direction, tf_signal, tf_context, validity_minutes, context_blocker, confluence_score=len(selected), detected_at=detected_at, blockers=[context_blocker])

    setup_type = f"reversal_{horizon}"
    levels = build_market_trade_levels(
        gold,
        direction,
        setup_type,
        atr=max(signal_reading.atr14, 3.0),
        readings=readings,
        proxy_price=signal_reading.close,
        min_rr=1.5,
    )
    condition_names = [item["name"] for item in selected]
    can_trade = len(selected) >= 4 or (
        len(selected) >= 3
        and {"divergence", "swing_rejection"}.issubset(set(condition_names))
        and levels.risk_reward_tp1 >= 1.8
    )
    if not can_trade:
        reason = f"Setup incomplet: {len(selected)}/5 conditions, divergence/rejet/RR pas assez forts."
        return reversal_no_trade(horizon, direction, tf_signal, tf_context, validity_minutes, reason, confluence_score=len(selected), detected_at=detected_at)
    if levels.risk_reward_tp1 < 1.5:
        reason = f"R/R TP1 insuffisant: {levels.risk_reward_tp1:.2f}R."
        return reversal_no_trade(horizon, direction, tf_signal, tf_context, validity_minutes, reason, confluence_score=len(selected), detected_at=detected_at, blockers=[reason])

    return ReversalSetup(
        horizon=horizon,
        status=f"REVERSAL_{direction}",
        direction=direction,
        tf_signal=tf_signal,
        tf_context=tf_context,
        confluence_score=len(selected),
        conditions_met=condition_names,
        entry_zone_low=levels.entry_zone_low,
        entry_zone_high=levels.entry_zone_high,
        stop_loss=levels.stop_loss,
        tp1=levels.tp1,
        tp2=levels.tp2,
        tp3=levels.tp3,
        risk_reward_tp1=levels.risk_reward_tp1,
        validity_minutes=validity_minutes,
        reasons=[item["reason"] for item in all_selected if item["met"]][:5],
        blockers=[],
        detected_at=detected_at,
    )


def build_reversal_engine(
    gold: SymbolSnapshot,
    readings: list[TechnicalReading],
    chart_store: ChartStore | None,
    now: datetime | None = None,
) -> dict[str, ReversalSetup]:
    return {
        "scalp": detect_reversal_setup("scalp", "5m", "15m", gold, readings, chart_store, 30, now=now),
        "intraday": detect_reversal_setup("intraday", "15m", "1H", gold, readings, chart_store, 90, now=now),
        "swing": detect_reversal_setup("swing", "1H", "4H", gold, readings, chart_store, 720, now=now),
    }


def build_mtf_alignment_note(readings: list[TechnicalReading], verdict: str) -> tuple[int, str]:
    higher_timeframes = [reading for reading in readings if reading.timeframe in {"1D", "4H", "1H"}]
    if not higher_timeframes:
        return 50, "Alignement multi-timeframe indisponible."

    aligned = [reading.timeframe for reading in higher_timeframes if reading.verdict == verdict]
    conflicting = [reading.timeframe for reading in higher_timeframes if reading.verdict != verdict]
    score = round((len(aligned) / len(higher_timeframes)) * 100)

    if score >= 67:
        return score, f"Alignement multi-timeframe valide: {', '.join(aligned)} confirment le {verdict}."
    if score <= 33:
        return score, f"Signal fragile: timeframes superieurs en contradiction ({', '.join(conflicting)})."
    return score, f"Alignement partiel: {', '.join(aligned) or 'aucun'} confirme, {', '.join(conflicting) or 'aucun'} contredit."


def build_fundamental_recommendation(
    gold: SymbolSnapshot,
    dxy: SymbolSnapshot,
    us10y: SymbolSnapshot,
    analysis: AnalysisResult,
    atr_15m: float,
    real_yield: SymbolSnapshot | None = None,
    cross_asset: CrossAssetAnalysis | None = None,
    event_mode: EventModeAnalysis | None = None,
) -> TradeRecommendation:
    bullish_score = 50.0
    reasons: list[str] = []

    if gold.change_pct >= 0:
        bullish_score += 10
        reasons.append("Le spot XAU/USD tient au-dessus de la cloture precedente.")
    else:
        bullish_score -= 10
        reasons.append("Le spot XAU/USD reste sous pression face a la cloture precedente.")

    if gold.period_change_pct >= 0:
        bullish_score += 8
        reasons.append("La dynamique courte du spot reste orientee positivement.")
    else:
        bullish_score -= 8
        reasons.append("La dynamique courte du spot reste negative.")

    if dxy.change_pct < 0:
        bullish_score += clamp(abs(dxy.change_pct) * 16, 6, 18)
        reasons.append("Le DXY recule, ce qui soutient l'or.")
    else:
        bullish_score -= clamp(abs(dxy.change_pct) * 16, 6, 18)
        reasons.append("Le DXY remonte, ce qui freine l'or.")

    yield_change_bps = us10y.change_abs * 100
    if yield_change_bps < 0:
        bullish_score += clamp(abs(yield_change_bps) * 1.4, 6, 18)
        reasons.append("Les rendements US se detendent, favorable au metal jaune.")
    else:
        bullish_score -= clamp(abs(yield_change_bps) * 1.4, 6, 18)
        reasons.append("Les rendements US montent, ce qui penalise l'or.")

    if real_yield is not None:
        real_yield_change_bps = real_yield.change_abs * 100
        if real_yield_change_bps < 0:
            bullish_score += clamp(abs(real_yield_change_bps) * 2.2, 5, 18)
            reasons.append("Le 10Y reel FRED baisse, driver macro majeur favorable a l'or.")
        elif real_yield_change_bps > 0:
            bullish_score -= clamp(abs(real_yield_change_bps) * 2.2, 5, 18)
            reasons.append("Le 10Y reel FRED monte, ce qui durcit le contexte pour l'or.")

    if cross_asset is not None:
        cross_tilt = clamp((cross_asset.score - 50) / 2.0, -14, 14)
        bullish_score += cross_tilt
        if cross_tilt > 0:
            reasons.append("Les confirmations cross-asset soutiennent le biais haussier de l'or.")
        elif cross_tilt < 0:
            reasons.append("Les confirmations cross-asset contredisent le biais haussier de l'or.")
        else:
            reasons.append("Les confirmations cross-asset restent neutres.")

    news_tilt = clamp((analysis.score * 4), -16, 16)
    bullish_score += news_tilt
    if news_tilt >= 0:
        reasons.append("Le flux d'actualites garde un biais globalement favorable.")
    else:
        reasons.append("Le flux d'actualites reste plutot defavorable.")

    if analysis.geopolitical is not None:
        geo_tilt = clamp((analysis.geopolitical.score - 50) / 2.5, -10, 10)
        bullish_score += geo_tilt
        if geo_tilt > 0:
            reasons.append("Le bloc geopolitique/sentiment/flux reste globalement favorable a l'or.")
        elif geo_tilt < 0:
            reasons.append("Le bloc geopolitique/sentiment/flux ne soutient pas clairement l'or.")
        else:
            reasons.append("Le bloc geopolitique/sentiment/flux reste equilibre.")

    mid_range = ((gold.day_high or gold.price) + (gold.day_low or gold.price)) / 2
    if gold.price >= mid_range:
        bullish_score += 5
        reasons.append("Le prix travaille dans la moitie haute du range du jour.")
    else:
        bullish_score -= 5
        reasons.append("Le prix reste dans la moitie basse du range du jour.")

    bullish_score = clamp(bullish_score, 0, 100)
    verdict = "BUY" if bullish_score >= 50 else "SELL"
    conviction = bullish_score if verdict == "BUY" else 100 - bullish_score
    score = round(clamp(conviction, 55, 90))
    event_multiplier = event_mode.stop_multiplier if event_mode is not None else 1.0
    stop_loss, tp1, tp2 = build_trade_levels(
        gold.price,
        atr=max(atr_15m, 6.0) * event_multiplier,
        verdict=verdict,
        stop_multiplier=1.15,
        tp1_multiplier=1.0,
        tp2_multiplier=2.0,
    )

    if event_mode is not None and event_mode.active:
        score = min(score, 62)
        reasons.insert(0, f"Mode event actif ({event_mode.score}/100): eviter une entree impulsive.")

    summary = (
        (
            f"Fundamentaux intraday positifs or: DXY {dxy.change_pct:+.2f}%, "
            f"DGS10 {yield_change_bps:+.1f} bps. News flow score {analysis.score:+d}, sans contradiction majeure."
        )
        if verdict == "BUY"
        else (
            f"Fundamentaux intraday defensifs or: DXY {dxy.change_pct:+.2f}%, "
            f"DGS10 {yield_change_bps:+.1f} bps. Pas d'avantage macro pour un achat sans confirmation technique."
        )
    )

    return TradeRecommendation(
        mode="Fondamental",
        verdict=verdict,
        score=score,
        summary=summary,
        reasons=reasons[:6],
        stop_loss=stop_loss,
        take_profit_1=tp1,
        take_profit_2=tp2,
        source_note="Spot XAU/USD Investing.com + DXY/10Y nominal + 10Y reel FRED + cross-assets gratuits + actualites.",
    )


def build_technical_recommendation(
    spot: SymbolSnapshot,
    readings: list[TechnicalReading],
    proxy_price: float,
    event_mode: EventModeAnalysis | None = None,
) -> TradeRecommendation:
    weights = {"1D": 0.28, "4H": 0.24, "1H": 0.20, "15m": 0.18, "5m": 0.10}
    weighted_score = 0.0
    reasons: list[str] = []
    atr_15m = next(reading.atr14 for reading in readings if reading.timeframe == "15m")

    for reading in readings:
        normalized = clamp(reading.score / 8.0, -1.0, 1.0)
        weighted_score += normalized * weights[reading.timeframe]
        reasons.append(
            f"{reading.timeframe}: {reading.verdict} avec RSI7 {reading.rsi7:.1f}, MACD {reading.macd_histogram:+.2f}, volume x{reading.volume_ratio:.2f}."
        )

    verdict = "BUY" if weighted_score >= 0 else "SELL"
    score = round(clamp(55 + (abs(weighted_score) * 30), 55, 88))
    alignment_score, alignment_note = build_mtf_alignment_note(readings, verdict)
    reasons.insert(0, alignment_note)
    if alignment_score <= 33:
        score = max(55, score - 12)
    elif alignment_score >= 67:
        score = min(90, score + 5)

    support_15m = next(reading for reading in readings if reading.timeframe == "15m")
    resistance_4h = next(reading for reading in readings if reading.timeframe == "4H")

    event_multiplier = event_mode.stop_multiplier if event_mode is not None else 1.0
    atr_for_levels = max(atr_15m, 6.0) * event_multiplier
    stop_loss, tp1, tp2 = build_trade_levels(
        spot.price,
        atr=atr_for_levels,
        verdict=verdict,
        stop_multiplier=1.0,
        tp1_multiplier=1.1,
        tp2_multiplier=2.1,
    )

    support_proxy = min(support_15m.ema20, support_15m.ema50, support_15m.ema100, support_15m.ema200)
    resistance_proxy = max(resistance_4h.ema20, resistance_4h.ema50, resistance_4h.ema100, resistance_4h.ema200)
    adjusted_support = adjust_proxy_level_to_spot(support_proxy, spot.price, proxy_price)
    adjusted_resistance = adjust_proxy_level_to_spot(resistance_proxy, spot.price, proxy_price)

    if verdict == "BUY":
        stop_loss = min(stop_loss, adjusted_support - (atr_for_levels * 0.35))
        tp1 = max(tp1, spot.day_high or tp1)
        tp2 = max(tp2, adjusted_resistance)
        summary = (
            f"Structure technique BUY: spot {spot.price:.2f} au-dessus support {adjusted_support:.2f}, "
            f"resistance majeure {adjusted_resistance:.2f}. Continuation valable tant que le prix tient au-dessus du support."
        )
    else:
        stop_loss = max(stop_loss, adjusted_resistance + (atr_for_levels * 0.35))
        tp1 = min(tp1, spot.day_low or tp1)
        tp2 = min(tp2, adjusted_support)
        summary = (
            f"Structure technique SELL: spot {spot.price:.2f} sous resistance {adjusted_resistance:.2f}, "
            f"support majeur {adjusted_support:.2f}. Pivot bear si cassure {adjusted_support:.2f}."
        )

    if event_mode is not None and event_mode.active:
        score = min(score, 62)
        reasons.insert(0, f"Mode event actif ({event_mode.score}/100): signal technique a traiter en attente/confirmation.")
        summary = f"{summary} Regime volatil: attendre une confirmation par cassure et clotures avant entree."

    return TradeRecommendation(
        mode="Technique",
        verdict=verdict,
        score=score,
        summary=summary,
        reasons=reasons,
        stop_loss=stop_loss,
        take_profit_1=tp1,
        take_profit_2=tp2,
        source_note="Indicateurs calcules sur GC=F (proxy futures COMEX) pour obtenir les bougies multi-timeframes et le volume, puis alignes sur le spot XAU/USD.",
    )


def classify_technical_structure(readings: list[TechnicalReading], direction: str, weighted_score: float) -> str:
    higher = [reading for reading in readings if reading.timeframe in {"1D", "4H", "1H"}]
    lower = [reading for reading in readings if reading.timeframe in {"15m", "5m"}]
    higher_aligned = sum(1 for reading in higher if reading.verdict == direction)
    lower_aligned = sum(1 for reading in lower if reading.verdict == direction)

    if abs(weighted_score) < 0.14:
        return "range"
    if higher and higher_aligned == len(higher) and lower and lower_aligned == len(lower):
        return "trend"
    if higher and higher_aligned >= 2 and lower and lower_aligned == 0:
        return "pullback"
    if higher and higher_aligned <= 1 and lower and lower_aligned == len(lower):
        return "reversal"
    if abs(weighted_score) >= 0.38:
        return "breakout"
    return "trend"


def build_technical_decision(
    spot: SymbolSnapshot,
    readings: list[TechnicalReading],
    proxy_price: float,
    cross_asset: CrossAssetAnalysis | None = None,
    event_mode: EventModeAnalysis | None = None,
    data_quality: DataQualitySnapshot | None = None,
) -> TechnicalDecision:
    if not readings:
        price = spot.price
        return TechnicalDecision(
            status="WAIT",
            direction="WAIT",
            structure="no_data",
            score=0,
            confidence=0,
            trigger="Aucune entree: matrice technique multi-timeframe indisponible.",
            invalidation="Reprendre seulement quand les donnees OHLC sont disponibles.",
            entry_zone_low=price,
            entry_zone_high=price,
            stop_loss=price,
            tp1=price,
            tp2=price,
            tp3=price,
            reasons=[],
            contradictions=["Aucune lecture EMA/RSI/MACD/ATR exploitable."],
        )

    weights = {"1D": 0.28, "4H": 0.24, "1H": 0.20, "15m": 0.18, "5m": 0.10}
    weighted_score = sum(
        clamp(reading.score / 8.0, -1.0, 1.0) * weights.get(reading.timeframe, 0.0)
        for reading in readings
    )
    raw_direction = "BUY" if weighted_score >= 0 else "SELL"
    alignment_score, alignment_note = build_mtf_alignment_note(readings, raw_direction)
    structure = classify_technical_structure(readings, raw_direction, weighted_score)
    atr_15m = next((reading.atr14 for reading in readings if reading.timeframe == "15m"), readings[-1].atr14)
    setup_type = trade_setup_from_structure(structure, raw_direction)
    market_levels = build_market_trade_levels(
        spot,
        raw_direction,
        setup_type,
        atr=max(atr_15m, 6.0),
        readings=readings,
        proxy_price=proxy_price,
        min_rr=1.5,
        event_mode=event_mode,
    )
    if raw_direction == "BUY":
        trigger_level = max(spot.resistance or spot.price, market_levels.entry_zone_high)
        invalidation_level = min(spot.support or market_levels.stop_loss, market_levels.stop_loss)
        trigger = f"BUY seulement si cloture M15 au-dessus de {trigger_level:.2f} avec RSI > 50 et MACD histogramme positif."
        invalidation = f"Invalidation BUY si cloture M15 sous {invalidation_level:.2f} ou si DXY/10Y reprennent fortement."
    else:
        trigger_level = min(spot.support or spot.price, market_levels.entry_zone_low)
        invalidation_level = max(spot.resistance or market_levels.stop_loss, market_levels.stop_loss)
        trigger = f"SELL seulement si cloture M15 sous {trigger_level:.2f} avec RSI < 50 et MACD histogramme negatif."
        invalidation = f"Invalidation SELL si cloture M15 au-dessus de {invalidation_level:.2f} ou si l'or repasse en refuge confirme."

    strength = abs(weighted_score)
    score = clamp_score(50 + strength * 35 + (alignment_score - 50) * 0.22)
    confidence = min(85, clamp_score(48 + alignment_score * 0.30 + min(strength * 45, 22)))
    contradictions: list[str] = []
    reasons = [
        alignment_note,
        f"Structure detectee: {structure}. Score technique brut {weighted_score:+.2f}.",
        *market_levels.reasons[:3],
    ]

    for reading in readings:
        reasons.append(
            f"{reading.timeframe}: {reading.verdict}, RSI7 {reading.rsi7:.1f}, MACD hist {reading.macd_histogram:+.2f}, ATR14 {reading.atr14:.2f}."
        )

    if alignment_score < 67:
        contradictions.append("Alignement multi-timeframe incomplet: pas de trade direct sans cassure confirmee.")
    if cross_asset is not None:
        if raw_direction == "BUY" and cross_asset.verdict == "SELL":
            contradictions.append("Cross-assets contre le BUY gold: attendre une confirmation prix plus forte.")
        elif raw_direction == "SELL" and cross_asset.verdict == "BUY":
            contradictions.append("Cross-assets contre le SELL gold: attendre une confirmation prix plus forte.")
        else:
            reasons.append(f"Cross-assets: {cross_asset.verdict} / {cross_asset.score}/100.")
    if event_mode is not None and event_mode.active:
        contradictions.append(f"Regime volatil actif {event_mode.score}/100: entree directe degradee en watch.")
    if data_quality is not None and data_quality.preflight and data_quality.preflight.trade_blocked:
        contradictions.append("Preflight sources bloque le trade: donnees critiques insuffisantes.")

    if score < 58 or strength < 0.12:
        direction = "WAIT"
        status = "WAIT"
    elif contradictions:
        direction = f"WATCH_{raw_direction}"
        status = "WATCH"
    else:
        direction = raw_direction
        status = "TRADE_READY"

    return TechnicalDecision(
        status=status,
        direction=direction,
        structure=structure,
        score=score,
        confidence=confidence,
        trigger=trigger,
        invalidation=invalidation,
        entry_zone_low=market_levels.entry_zone_low,
        entry_zone_high=market_levels.entry_zone_high,
        stop_loss=market_levels.stop_loss,
        tp1=market_levels.tp1,
        tp2=market_levels.tp2,
        tp3=market_levels.tp3,
        reasons=reasons[:7],
        contradictions=contradictions[:5],
    )


def normalize_scenario_bias(direction: str, fallback: str = "WAIT") -> str:
    upper = (direction or fallback).upper()
    if upper in {"BUY", "WATCH_BUY", "TRADE_BUY"}:
        return "BUY"
    if upper in {"SELL", "WATCH_SELL", "TRADE_SELL"}:
        return "SELL"
    return fallback if fallback in {"BUY", "SELL"} else "WAIT"


def build_scenario_plan(
    gold: SymbolSnapshot,
    technical_decision: TechnicalDecision | None,
    global_recommendation: TradeRecommendation | None,
    fundamental_recommendation: TradeRecommendation | None = None,
    cross_asset: CrossAssetAnalysis | None = None,
    market_regime: MarketRegimeAnalysis | None = None,
    event_facts: list[EventFact] | None = None,
    data_quality: DataQualitySnapshot | None = None,
) -> ScenarioPlan:
    event_facts = event_facts or []
    technical = technical_decision or TechnicalDecision(
        status="WAIT",
        direction="WAIT",
        structure="no_data",
        score=0,
        confidence=0,
        trigger="Aucun trigger technique disponible.",
        invalidation="Aucune invalidation exploitable sans donnees techniques.",
        entry_zone_low=gold.price,
        entry_zone_high=gold.price,
        stop_loss=gold.price,
        tp1=gold.price,
        tp2=gold.price,
        tp3=gold.price,
        reasons=[],
        contradictions=["TechnicalDecisionEngine indisponible."],
    )
    fallback_bias = (
        global_recommendation.verdict
        if global_recommendation and global_recommendation.verdict in {"BUY", "SELL"}
        else "WAIT"
    )
    bias = normalize_scenario_bias(technical.direction, fallback_bias)
    validations: list[str] = []
    contradictions: list[str] = list(technical.contradictions[:4])
    confirmations = [technical.trigger]

    if fundamental_recommendation is not None:
        if bias in {"BUY", "SELL"} and fundamental_recommendation.verdict == bias:
            validations.append(f"Macro/Fondamental confirme {bias} ({fundamental_recommendation.score}/100).")
        elif bias in {"BUY", "SELL"}:
            contradictions.append(f"Macro/Fondamental contredit {bias}: {fundamental_recommendation.verdict} {fundamental_recommendation.score}/100.")
    if cross_asset is not None:
        if bias in {"BUY", "SELL"} and cross_asset.verdict == bias:
            validations.append(f"Cross-assets confirment {bias} ({cross_asset.score}/100).")
        elif bias in {"BUY", "SELL"} and cross_asset.verdict in {"BUY", "SELL"}:
            contradictions.append(f"Cross-assets contredisent {bias}: {cross_asset.verdict} {cross_asset.score}/100.")
        confirmations.append("Verifier que DXY, 10Y reel, Silver/GDX et oil ne contredisent pas le trigger.")
    if market_regime is not None:
        validations.append(f"Regime actif: {market_regime.name} / {market_regime.status} ({market_regime.score}/100).")
        if market_regime.status == "ACTIF" and "Oil Shock" in market_regime.name:
            confirmations.append("En regime oil/dollar, confirmer que WTI/Brent et DXY ne captent pas toute la liquidite.")
    if event_facts:
        fact = event_facts[0]
        confirmations.append(f"News trigger: {fact.title[:110]} ({fact.source}, confiance {fact.confidence}/100).")
        if bias in {"BUY", "SELL"} and fact.impact_bias.upper() == bias:
            validations.append(f"NewsFact confirme {bias}: {fact.gold_impact}")
        elif bias in {"BUY", "SELL"} and fact.impact_bias.upper() in {"BUY", "SELL"}:
            contradictions.append(f"NewsFact contredit {bias}: {fact.gold_impact}")
    if data_quality is not None and data_quality.preflight and data_quality.preflight.trade_blocked:
        contradictions.append("Preflight bloque le trade: le scenario reste informatif seulement.")

    if bias == "BUY":
        primary = (
            f"Scenario principal: {technical.structure} haussier surveille. "
            f"Zone utile {technical.entry_zone_low:.2f}-{technical.entry_zone_high:.2f}; "
            f"le setup devient exploitable seulement si le trigger technique se confirme."
        )
        alternative = (
            f"Scenario alternatif: echec sous resistance ou retour sous {technical.stop_loss:.2f}; "
            "le marche repasse en attente ou bascule en pression vendeuse."
        )
    elif bias == "SELL":
        primary = (
            f"Scenario principal: {technical.structure} baissier surveille. "
            f"Zone utile {technical.entry_zone_low:.2f}-{technical.entry_zone_high:.2f}; "
            f"le setup devient exploitable seulement si le support cede avec confirmation."
        )
        alternative = (
            f"Scenario alternatif: reprise au-dessus de {technical.stop_loss:.2f}; "
            "le SELL est annule et le marche revient en attente."
        )
    else:
        primary = (
            f"Scenario principal: attente. Prix {gold.price:.2f}, structure {technical.structure}; "
            "aucune direction n'a assez de confirmations pour verrouiller un trade."
        )
        alternative = (
            "Scenario alternatif: surveiller la premiere cassure propre du range avec confirmation DXY/10Y et momentum M15."
        )

    if technical.direction in {"BUY", "SELL"} and not contradictions:
        status = f"TRADE_{technical.direction}"
        action = "PREPARE_TRADE"
    elif bias == "BUY":
        status = "WATCH_BUY"
        action = "SURVEILLER_BUY"
    elif bias == "SELL":
        status = "WATCH_SELL"
        action = "SURVEILLER_SELL"
    else:
        status = "WAIT"
        action = "NO_TRADE"

    confidence = clamp_score(
        (technical.confidence * 0.45)
        + ((global_recommendation.score if global_recommendation else 50) * 0.25)
        + ((fundamental_recommendation.score if fundamental_recommendation else 50) * 0.15)
        + ((cross_asset.score if cross_asset else 50) * 0.15)
        - (len(contradictions) * 4)
    )

    return ScenarioPlan(
        status=status,
        bias=bias,
        primary_scenario=primary,
        alternative_scenario=alternative,
        trigger=technical.trigger,
        confirmation_required=confirmations[:5],
        invalidation=technical.invalidation,
        action=action,
        confidence=confidence,
        validations=validations[:5],
        contradictions=contradictions[:6],
    )


def recommendation_bullish_score(recommendation: TradeRecommendation) -> float:
    if recommendation.verdict.upper() == "BUY":
        return float(recommendation.score)
    return float(100 - recommendation.score)


def collect_directional_levels(
    price: float,
    verdict: str,
    recommendations: list[TradeRecommendation],
) -> tuple[list[float], list[float], list[float]]:
    stop_losses: list[float] = []
    take_profit_1: list[float] = []
    take_profit_2: list[float] = []

    for recommendation in recommendations:
        if recommendation.verdict != verdict:
            continue
        if verdict == "BUY":
            if recommendation.stop_loss < price:
                stop_losses.append(recommendation.stop_loss)
            if recommendation.take_profit_1 > price:
                take_profit_1.append(recommendation.take_profit_1)
            if recommendation.take_profit_2 > price:
                take_profit_2.append(recommendation.take_profit_2)
        else:
            if recommendation.stop_loss > price:
                stop_losses.append(recommendation.stop_loss)
            if recommendation.take_profit_1 < price:
                take_profit_1.append(recommendation.take_profit_1)
            if recommendation.take_profit_2 < price:
                take_profit_2.append(recommendation.take_profit_2)

    return stop_losses, take_profit_1, take_profit_2


def average_or_default(values: list[float], default: float) -> float:
    return sum(values) / len(values) if values else default


def build_global_recommendation(
    gold: SymbolSnapshot,
    analysis: AnalysisResult,
    fundamental: TradeRecommendation,
    technical: TradeRecommendation,
    geopolitical: GeopoliticalAnalysis | None = None,
    cross_asset: CrossAssetAnalysis | None = None,
    event_mode: EventModeAnalysis | None = None,
) -> TradeRecommendation:
    fundamental_bullish = recommendation_bullish_score(fundamental)
    technical_bullish = recommendation_bullish_score(technical)
    geopolitical_bullish = float(geopolitical.score) if geopolitical is not None else 50.0
    cross_asset_bullish = float(cross_asset.score) if cross_asset is not None else 50.0
    heuristic_bullish = clamp(50 + (analysis.score * 4), 0, 100)

    bullish_score = (
        technical_bullish * 0.34
        + fundamental_bullish * 0.28
        + geopolitical_bullish * 0.16
        + cross_asset_bullish * 0.14
        + heuristic_bullish * 0.08
    )
    verdict = "BUY" if bullish_score >= 50 else "SELL"
    conviction = bullish_score if verdict == "BUY" else 100 - bullish_score
    score = round(clamp(conviction, 52, 92))

    setup_type = "trend_continuation" if fundamental.verdict == technical.verdict == verdict else "pivot_rejection"
    market_levels = build_market_trade_levels(
        gold,
        verdict,
        setup_type,
        atr=max(abs(fundamental.take_profit_1 - gold.price), abs(technical.take_profit_1 - gold.price), 6.0),
        min_rr=1.5,
        event_mode=event_mode,
    )
    stop_loss = market_levels.stop_loss
    tp1 = market_levels.tp1
    tp2 = market_levels.tp2

    reasons = [
        f"Technique {technical.verdict} a {technical.score}/100.",
        f"Fondamental {fundamental.verdict} a {fundamental.score}/100.",
        f"Niveaux v4 {market_levels.setup_type}: SL/TP bases sur structure, pivots, psychologiques et R/R TP1 {market_levels.risk_reward_tp1:.2f}R.",
    ]
    if geopolitical is not None:
        reasons.append(f"Geopolitique/sentiment/flux a {geopolitical.score}/100.")
    if cross_asset is not None:
        reasons.append(f"Confluence inter-marches a {cross_asset.score}/100 ({cross_asset.status}).")
    reasons.append(f"Biais heuristique global: {format_bias_label(analysis.bias)} ({analysis.score:+d}).")

    if fundamental.verdict == technical.verdict == verdict:
        summary = f"Signal global aligne: le fondamental et la technique pointent tous les deux vers {verdict}."
    elif verdict == technical.verdict:
        summary = f"Signal global {verdict}: la technique domine, avec validation partielle du contexte global."
    elif verdict == fundamental.verdict:
        summary = f"Signal global {verdict}: le contexte fondamental domine, mais le timing technique demande prudence."
    else:
        summary = f"Signal global {verdict}: la moyenne des scores penche de ce cote, mais la confluence reste partagee."

    if event_mode is not None and event_mode.active:
        score = min(score, 62)
        summary = f"{summary} Mode event actif: attendre une confirmation propre avant toute entree aggressive."
        reasons.insert(0, f"Mode event actif ({event_mode.score}/100): risque de volatilite eleve.")

    return TradeRecommendation(
        mode="Global",
        verdict=verdict,
        score=score,
        summary=summary,
        reasons=reasons[:6],
        stop_loss=stop_loss,
        take_profit_1=tp1,
        take_profit_2=tp2,
        source_note="Score global pondere: technique, fondamental, geopolitique/sentiment/flux, correlations et biais heuristique.",
    )


def build_executive_summary(
    fundamental: TradeRecommendation,
    technical: TradeRecommendation,
    geopolitical: GeopoliticalAnalysis | None = None,
) -> str:
    if fundamental.verdict == technical.verdict:
        alignment = (
            f"Fondamental et technique alignes en {fundamental.verdict}: signal directionnel coherent."
        )
    elif fundamental.verdict == "BUY":
        alignment = (
            "Fondamental BUY, technique SELL: pas d'entree macro tant que le pivot technique n'est pas casse a la hausse."
        )
    else:
        alignment = (
            "Fondamental SELL, technique BUY: rebonds vendables tant que macro reste defavorable a l'or."
        )

    geo_lines: list[str] = []
    if geopolitical:
        if geopolitical.risk_off_status == "actif":
            geo_lines.append(
                "Risk-off geopolitique mesurable: demande de couverture or maintenue tant que VIX reste eleve."
            )
        elif geopolitical.risk_off_status == "en reflux":
            geo_lines.append(
                "Stress geopolitique en reflux: soutien refuge en retrait, surveiller VIX et TIP."
            )

        if geopolitical.central_bank_bias == "restrictif":
            geo_lines.append(
                "Banques centrales restrictives: choc energie ou inflation pourrait retarder les baisses de taux."
            )
        elif geopolitical.central_bank_bias == "accommodant":
            geo_lines.append(
                "Banques centrales accommodantes: dollar et rendements moins agressifs, biais favorable a l'or."
            )
        else:
            geo_lines.append(
                "Banques centrales mitigees: ni catalyseur haussier net, ni catalyseur baissier net pour l'or."
            )

        if geopolitical.large_speculators == "net long":
            geo_lines.append(
                "Les speculators sont deja plutot acheteurs, ce qui soutient le fond mais limite un peu l'effet surprise."
            )
        elif geopolitical.large_speculators == "net short":
            geo_lines.append(
                "Les speculators restent defensifs, donc tout choc haussier peut forcer des rachats de shorts."
            )

    score_line = f"Scores du moment: fondamental {fundamental.score}/100, technique {technical.score}/100"
    if geopolitical:
        score_line += f", geopolitique {geopolitical.score}/100."
    else:
        score_line += "."

    details = " ".join(geo_lines)
    if details:
        return f"{alignment} {details} {score_line}"
    return f"{alignment} {score_line}"


def score_headline_v2(title: str, source: str = "", category: str = "", link: str = "") -> tuple[int, list[str]]:
    text = title.lower()
    if should_skip_headline(title, source):
        return 0, ["noise_filter"]

    raw_score = 0.0
    reasons: list[str] = []

    for keyword, weight in BULLISH_KEYWORDS.items():
        if keyword_matches(text, keyword):
            raw_score += weight
            reasons.append(f"bullish:{keyword}")

    for keyword, weight in BEARISH_KEYWORDS.items():
        if keyword_matches(text, keyword):
            raw_score += weight
            reasons.append(f"bearish:{keyword}")

    if text_contains_any(text, ("reject", "rejects", "denies", "refuses", "walks away", "fails to agree")):
        if text_contains_any(text, ("deal", "agreement", "accord", "ceasefire", "truce", "nuclear")):
            raw_score = abs(raw_score) if raw_score else 2
            reasons.append("negation_inversion")

    source_tier = news_source_tier(source, link)
    if raw_score != 0:
        if source_tier == 1:
            raw_score *= 1.5
            reasons.append("tier_1_official")
        elif source_tier == 2:
            raw_score *= 1.2
            reasons.append("tier_2_agency")

        logical = logical_category(category)
        if logical in {"geopolitical", "macro_fed", "macro_cpi", "macro_nfp"}:
            raw_score *= 1.3
            reasons.append(f"category_bonus_{logical}")

    score = round(raw_score)
    return max(-5, min(5, score)), reasons


def score_headline(title: str) -> tuple[int, list[str]]:
    return score_headline_v2(title)


def append_rss_items(
    root: ET.Element,
    category: str,
    items: list[NewsItem],
    seen_titles: set[str],
    result_limit: int,
    feed_hash_cache: dict[str, str] | None = None,
    detected_at: str | None = None,
) -> None:
    channel_title = compact_whitespace(root.findtext("./channel/title", default="RSS"))
    detected_iso = detected_at or iso_now()
    detected_dt = parse_iso_datetime(detected_iso) or datetime.now(timezone.utc)
    for item in root.findall("./channel/item"):
        link = compact_whitespace(item.findtext("link", default=""))
        source = news_source_identity(compact_whitespace(item.findtext("source", default="")) or channel_title, link)
        raw_title = compact_whitespace(item.findtext("title", default=""))
        title = strip_source_suffix(raw_title, source)
        dedupe_key = normalize_title_for_dedupe(title)
        if not title or is_duplicate_news_title(title, seen_titles) or should_skip_headline(title, source):
            continue

        score, reasons = score_headline_v2(title, source, category, link)
        published_raw = item.findtext("pubDate", default="")
        try:
            published_at = (
                parsedate_to_datetime(published_raw).astimezone(timezone.utc).replace(microsecond=0).isoformat()
                if published_raw
                else iso_now()
            )
        except Exception:
            published_at = iso_now()
        processed_at = iso_now()
        published_dt = parse_iso_datetime(published_at)
        processed_dt = parse_iso_datetime(processed_at) or datetime.now(timezone.utc)
        source_latency = (
            max(0.0, (detected_dt - published_dt).total_seconds())
            if published_dt is not None
            else None
        )
        processing_latency = max(0.0, (processed_dt - detected_dt).total_seconds())
        feed_hash = stable_news_hash(title, link, published_at)
        cache_key = f"{category}:{feed_hash}"
        is_breaking = bool(feed_hash_cache is not None and feed_hash_cache.get(cache_key) != feed_hash)
        if feed_hash_cache is not None:
            feed_hash_cache[cache_key] = feed_hash

        items.append(
            NewsItem(
                title=title,
                source=source,
                link=link,
                published_at=published_at,
                category=category,
                score=score,
                score_reasons=reasons,
                feed_detected_at=detected_iso,
                feed_processed_at=processed_at,
                source_latency_seconds=round(source_latency, 3) if source_latency is not None else None,
                processing_latency_seconds=round(processing_latency, 3),
                feed_hash=feed_hash,
                is_breaking=is_breaking,
            )
        )
        seen_titles.add(dedupe_key)
        if len(items) >= result_limit:
            return


def fetch_news(top_n: int) -> list[NewsItem]:
    items: list[NewsItem] = []
    seen_titles: set[str] = set()
    feed_hash_cache = load_feed_hash_cache()
    month_name = current_month_name_en()
    result_limit = max(top_n, 24)
    deadline = time.time() + 22
    reference = datetime.now(timezone.utc)

    for category, mirrors in (
        ("critical_trump_nitter", TRUMP_NITTER_FEEDS),
        ("critical_white_house_nitter", WHITE_HOUSE_NITTER_FEEDS),
    ):
        if time.time() >= deadline:
            break
        fallback = fetch_nitter_feed_with_fallback(category, mirrors)
        if fallback is None:
            continue
        _, root = fallback
        append_rss_items(root, category, items, seen_titles, result_limit * 2, feed_hash_cache=feed_hash_cache)

    for category, url in [*OFFICIAL_NEWS_RSS_FEEDS, *FAST_NEWS_RSS_FEEDS]:
        if time.time() >= deadline:
            break
        root = fetch_rss_root(category, url, criticality="high" if category in CRITICAL_FAST_FEEDS else "medium")
        if root is None:
            continue
        append_rss_items(root, category, items, seen_titles, result_limit * 2, feed_hash_cache=feed_hash_cache)

    for category, query_template in [*FAST_NEWS_SEARCH_QUERIES, *NEWS_QUERIES]:
        if time.time() >= deadline:
            break
        query = query_template.format(month=month_name)
        encoded_query = urllib.parse.quote(query, safe='()":')
        url = (
            "https://news.google.com/rss/search"
            f"?q={encoded_query}&hl=en-US&gl=US&ceid=US:en"
        )
        root = fetch_rss_root(category, url, timeout=6, criticality="low")
        if root is None:
            continue

        append_rss_items(root, category, items, seen_titles, result_limit, feed_hash_cache=feed_hash_cache)
        usable = [item for item in items if is_news_item_exploitable(item, now=reference)]
        if len(usable) >= result_limit:
            usable.sort(key=lambda item: (abs(item.score), -news_source_tier(item.source, item.link), parse_iso_sort_key(item.published_at)), reverse=True)
            save_feed_hash_cache(feed_hash_cache)
            return usable[:result_limit]

    usable = [item for item in items if is_news_item_exploitable(item, now=reference)]
    if len(usable) < top_n:
        for category, url in FALLBACK_RSS_FEEDS:
            root = fetch_rss_root(category, url, timeout=6, criticality="low")
            if root is None:
                continue
            append_rss_items(root, category, items, seen_titles, result_limit, feed_hash_cache=feed_hash_cache)
            if len(items) >= result_limit:
                break

    usable = [item for item in items if is_news_item_exploitable(item, now=reference)]
    usable.sort(key=lambda item: (abs(item.score), -news_source_tier(item.source, item.link), parse_iso_sort_key(item.published_at)), reverse=True)
    save_feed_hash_cache(feed_hash_cache)
    return usable[:result_limit]


def merge_news_items(primary: list[NewsItem], extra: list[NewsItem], limit: int) -> list[NewsItem]:
    merged: list[NewsItem] = []
    seen: set[str] = set()
    reference = datetime.now(timezone.utc)
    for item in primary + extra:
        key = normalize_title_for_dedupe(item.title)
        if not key or is_duplicate_news_title(item.title, seen) or not is_news_item_exploitable(item, now=reference):
            continue
        seen.add(key)
        merged.append(item)
    merged.sort(key=lambda item: (abs(item.score), -news_source_tier(item.source, item.link), parse_iso_sort_key(item.published_at)), reverse=True)
    return merged[:limit]


def political_source_tier(item: NewsItem) -> int:
    return news_source_tier(item.source, item.link)


def fetch_political_statement_news(limit: int = 12) -> list[NewsItem]:
    items: list[NewsItem] = []
    seen_titles: set[str] = set()
    feed_hash_cache = load_feed_hash_cache()
    result_limit = max(limit, 12)
    deadline = time.time() + 12
    direct_feed_ok = False

    for category, mirrors in (
        ("political_trump_nitter", TRUMP_NITTER_FEEDS),
        ("political_white_house_nitter", WHITE_HOUSE_NITTER_FEEDS),
    ):
        if time.time() >= deadline:
            break
        fallback = fetch_nitter_feed_with_fallback(category, mirrors)
        if fallback is None:
            continue
        direct_feed_ok = True
        _, root = fallback
        append_rss_items(root, category, items, seen_titles, result_limit, feed_hash_cache=feed_hash_cache)
        items = keep_political_statement_candidates(items)
        seen_titles = {normalize_title_for_dedupe(item.title) for item in items}

    for category, url in POLITICAL_RSS_FEEDS:
        if time.time() >= deadline:
            break
        root = fetch_rss_root(category, url, timeout=5, criticality="high")
        if root is None:
            continue
        direct_feed_ok = True
        append_rss_items(root, category, items, seen_titles, result_limit, feed_hash_cache=feed_hash_cache)
        items = keep_political_statement_candidates(items)
        seen_titles = {normalize_title_for_dedupe(item.title) for item in items}

    if not direct_feed_ok:
        append_source_error(
            "trump_political_direct_feeds",
            ",".join([TRUMP_TRUTH_SOCIAL_FEED_URL, WHITE_HOUSE_NEWS_FEED_URL, *TRUMP_NITTER_FEEDS, *WHITE_HOUSE_NITTER_FEEDS]),
            "all_trump_white_house_direct_feeds_down",
            criticality="high",
        )
        for category, query in POLITICAL_GOOGLE_FALLBACK_QUERIES:
            if time.time() >= deadline or len(items) >= result_limit:
                break
            root = fetch_rss_root(category, google_news_search_url(query), timeout=6, criticality="low")
            if root is None:
                continue
            append_rss_items(root, category, items, seen_titles, result_limit, feed_hash_cache=feed_hash_cache)
            items = keep_political_statement_candidates(items)
            seen_titles = {normalize_title_for_dedupe(item.title) for item in items}
        if not items:
            append_source_error(
                "trump_political_google_fallback",
                " | ".join(query for _category, query in POLITICAL_GOOGLE_FALLBACK_QUERIES),
                "google_news_fallback_returned_no_political_statement",
                criticality="medium",
            )

    for category, query in POLITICAL_STATEMENT_QUERIES:
        if time.time() >= deadline or len(items) >= result_limit:
            break
        url = google_news_search_url(query)
        root = fetch_rss_root(category, url, timeout=6, criticality="low")
        if root is None:
            continue
        append_rss_items(root, category, items, seen_titles, result_limit, feed_hash_cache=feed_hash_cache)
        items = keep_political_statement_candidates(items)
        seen_titles = {normalize_title_for_dedupe(item.title) for item in items}

    save_feed_hash_cache(feed_hash_cache)
    items.sort(key=lambda item: (-political_source_tier(item), abs(item.score), item.published_at), reverse=True)
    return items[:result_limit]


def build_market_reasons(gold: SymbolSnapshot, dxy: SymbolSnapshot, us10y: SymbolSnapshot) -> tuple[int, list[str]]:
    score = 0
    reasons: list[str] = []

    if gold.change_pct >= 0.30:
        score += 2
        reasons.append(f"L'or traite au-dessus de la cloture precedente ({gold.change_pct:+.2f}%).")
    elif gold.change_pct <= -0.30:
        score -= 2
        reasons.append(f"L'or traite sous la cloture precedente ({gold.change_pct:+.2f}%).")

    if gold.period_change_pct >= 1.00:
        score += 1
        reasons.append(f"La tendance courte reste constructive sur la fenetre observee ({gold.period_change_pct:+.2f}%).")
    elif gold.period_change_pct <= -1.00:
        score -= 1
        reasons.append(f"La tendance courte reste fragile sur la fenetre observee ({gold.period_change_pct:+.2f}%).")

    if dxy.change_pct <= -0.20:
        score += 2
        reasons.append(f"Le DXY recule ({dxy.change_pct:+.2f}%), ce qui soutient souvent l'or.")
    elif dxy.change_pct >= 0.20:
        score -= 2
        reasons.append(f"Le DXY remonte ({dxy.change_pct:+.2f}%), ce qui pese souvent sur l'or.")

    us10y_change_bps = (us10y.change_abs * 100)
    if us10y_change_bps <= -3:
        score += 2
        reasons.append(f"Le 10 ans US baisse d'environ {us10y_change_bps:+.1f} bps, un support pour l'or.")
    elif us10y_change_bps >= 3:
        score -= 2
        reasons.append(f"Le 10 ans US monte d'environ {us10y_change_bps:+.1f} bps, un vent contraire pour l'or.")

    return score, reasons


def snapshot_driver(snapshot: SymbolSnapshot | None) -> dict[str, Any]:
    if snapshot is None:
        return {"available": False}
    return {
        "available": True,
        "symbol": snapshot.symbol,
        "label": snapshot.label,
        "price": round(snapshot.price, 4),
        "change_pct": round(snapshot.change_pct, 2),
        "change_abs": round(snapshot.change_abs, 4),
        "last_update": snapshot.fetched_at,
    }


def average_close(points: list[PricePoint], lookback: int) -> float | None:
    closes = [point.close for point in points[-lookback:] if point.close is not None]
    if not closes:
        return None
    return sum(closes) / len(closes)


def series_changes(points: list[PricePoint], lookback: int, absolute: bool = False) -> list[float]:
    closes = [point.close for point in points if point.close is not None]
    if len(closes) < lookback + 1:
        return []

    selected = closes[-(lookback + 1):]
    changes: list[float] = []
    for previous, current in zip(selected, selected[1:]):
        if absolute:
            changes.append(current - previous)
        elif previous:
            changes.append(((current - previous) / abs(previous)) * 100)
    return changes


def pearson_correlation(left: list[float], right: list[float]) -> float | None:
    size = min(len(left), len(right))
    if size < 8:
        return None

    left_values = left[-size:]
    right_values = right[-size:]
    left_mean = sum(left_values) / size
    right_mean = sum(right_values) / size
    left_centered = [value - left_mean for value in left_values]
    right_centered = [value - right_mean for value in right_values]
    numerator = sum(a * b for a, b in zip(left_centered, right_centered))
    left_denominator = sum(value * value for value in left_centered) ** 0.5
    right_denominator = sum(value * value for value in right_centered) ** 0.5
    denominator = left_denominator * right_denominator
    if denominator == 0:
        return None
    return numerator / denominator


def rolling_correlation(
    gold_proxy: SymbolSnapshot | None,
    other: SymbolSnapshot | None,
    lookback: int,
    other_absolute: bool = False,
) -> float | None:
    if gold_proxy is None or other is None:
        return None
    gold_changes = series_changes(gold_proxy.points, lookback)
    other_changes = series_changes(other.points, lookback, absolute=other_absolute)
    correlation = pearson_correlation(gold_changes, other_changes)
    return round(correlation, 2) if correlation is not None else None


def correlation_multiplier(expected_relation: str, corr_30: float | None, corr_90: float | None) -> tuple[float, str]:
    values = [value for value in (corr_30, corr_90) if value is not None]
    if not values:
        return 0.60, "Correlation historique insuffisante: poids reduit."

    expected_sign = -1 if expected_relation == "inverse" else 1
    aligned_correlation = expected_sign * (sum(values) / len(values))
    if aligned_correlation >= 0.45:
        return 1.00, "Correlation historique forte: poids complet."
    if aligned_correlation >= 0.20:
        return 0.75, "Correlation historique correcte: poids partiel."
    if aligned_correlation >= 0.05:
        return 0.50, "Correlation historique faible mais dans le bon sens: poids reduit."
    if aligned_correlation >= -0.10:
        return 0.25, "Correlation historique tres faible: poids minimal."
    return 0.00, "Correlation historique contraire a la relation attendue: signal non score."


def make_correlation_signal(
    key: str,
    instrument: str,
    symbol: str,
    expected_relation: str,
    snapshot: SymbolSnapshot | None,
    gold_proxy: SymbolSnapshot | None,
    weight: int,
    threshold: float,
    change_unit: str = "%",
    use_bps: bool = False,
) -> tuple[CorrelationSignal, float, str | None, str | None]:
    if snapshot is None:
        signal = CorrelationSignal(
            instrument=instrument,
            symbol=symbol,
            expected_relation=expected_relation,
            price=None,
            change=None,
            change_unit=change_unit,
            corr_30=None,
            corr_90=None,
            signal="INDISPONIBLE",
            impact=0,
            reason="Source indisponible pour cette verification.",
        )
        return signal, 0.0, None, None

    change = snapshot.change_abs * 100 if use_bps else snapshot.change_pct
    corr_30 = rolling_correlation(gold_proxy, snapshot, 30, other_absolute=use_bps)
    corr_90 = rolling_correlation(gold_proxy, snapshot, 90, other_absolute=use_bps)

    signal_value = "NEUTRE"
    impact = 0
    if expected_relation == "inverse":
        if change <= -threshold:
            signal_value = "BUY"
            impact = weight
        elif change >= threshold:
            signal_value = "SELL"
            impact = -weight
    else:
        if change >= threshold:
            signal_value = "BUY"
            impact = weight
        elif change <= -threshold:
            signal_value = "SELL"
            impact = -weight

    multiplier, correlation_note = correlation_multiplier(expected_relation, corr_30, corr_90)
    effective_impact = int(round(impact * multiplier)) if impact else 0
    relation_text = "inverse" if expected_relation == "inverse" else "positive"
    if signal_value == "BUY":
        reason = (
            f"{instrument} confirme plutot un biais BUY gold ({change:+.2f}{change_unit}, "
            f"relation {relation_text}, poids {effective_impact:+d}). {correlation_note}"
        )
        confirmation = reason if effective_impact > 0 else None
        contradiction = None
    elif signal_value == "SELL":
        reason = (
            f"{instrument} confirme plutot un biais SELL gold ({change:+.2f}{change_unit}, "
            f"relation {relation_text}, poids {effective_impact:+d}). {correlation_note}"
        )
        confirmation = None
        contradiction = reason if effective_impact < 0 else None
    else:
        reason = f"{instrument} reste neutre pour l'or ({change:+.2f}{change_unit})."
        confirmation = None
        contradiction = None

    signal = CorrelationSignal(
        instrument=instrument,
        symbol=symbol,
        expected_relation=expected_relation,
        price=round(snapshot.price, 4),
        change=round(change, 2),
        change_unit=change_unit,
        corr_30=corr_30,
        corr_90=corr_90,
        signal=signal_value,
        impact=effective_impact,
        reason=reason,
    )
    return signal, float(effective_impact), confirmation, contradiction


def build_cross_asset_analysis(
    dxy: SymbolSnapshot,
    real_yield: SymbolSnapshot | None,
    usdjpy: SymbolSnapshot | None,
    silver: SymbolSnapshot | None,
    gvz: SymbolSnapshot | None,
    vix: SymbolSnapshot | None,
    gold_proxy: SymbolSnapshot | None = None,
    gdx: SymbolSnapshot | None = None,
    gdxj: SymbolSnapshot | None = None,
    audusd: SymbolSnapshot | None = None,
    usdchf: SymbolSnapshot | None = None,
    tip: SymbolSnapshot | None = None,
    spx: SymbolSnapshot | None = None,
    wti: SymbolSnapshot | None = None,
    brent: SymbolSnapshot | None = None,
) -> CrossAssetAnalysis:
    score = 50.0
    confirmations: list[str] = []
    contradictions: list[str] = []
    drivers = {
        "gold_proxy": snapshot_driver(gold_proxy),
        "dxy": snapshot_driver(dxy),
        "real_yield_10y": snapshot_driver(real_yield),
        "usdjpy": snapshot_driver(usdjpy),
        "silver": snapshot_driver(silver),
        "gdx": snapshot_driver(gdx),
        "gdxj": snapshot_driver(gdxj),
        "audusd": snapshot_driver(audusd),
        "usdchf": snapshot_driver(usdchf),
        "tip": snapshot_driver(tip),
        "spx": snapshot_driver(spx),
        "gvz": snapshot_driver(gvz),
        "vix": snapshot_driver(vix),
        "wti": snapshot_driver(wti),
        "brent": snapshot_driver(brent),
    }

    specs = [
        ("dxy", "DXY", dxy.symbol, "inverse", dxy, 14, 0.10, "%", False),
        ("real_yield_10y", "10Y reel FRED", "DFII10", "inverse", real_yield, 18, 1.0, " bps", True),
        ("usdjpy", "USD/JPY", CROSS_ASSET_SYMBOLS["usdjpy"][0], "inverse", usdjpy, 8, 0.10, "%", False),
        ("silver", "Silver", CROSS_ASSET_SYMBOLS["silver"][0], "positive", silver, 9, 0.10, "%", False),
        ("gdx", "GDX miners", CROSS_ASSET_SYMBOLS["gdx"][0], "positive", gdx, 8, 0.15, "%", False),
        ("gdxj", "GDXJ juniors", CROSS_ASSET_SYMBOLS["gdxj"][0], "positive", gdxj, 6, 0.20, "%", False),
        ("audusd", "AUD/USD", CROSS_ASSET_SYMBOLS["audusd"][0], "positive", audusd, 5, 0.10, "%", False),
        ("usdchf", "USD/CHF", CROSS_ASSET_SYMBOLS["usdchf"][0], "inverse", usdchf, 5, 0.10, "%", False),
        ("tip", "TIP ETF", CROSS_ASSET_SYMBOLS["tip"][0], "positive", tip, 5, 0.10, "%", False),
        ("spx", "S&P 500", CROSS_ASSET_SYMBOLS["spx"][0], "inverse", spx, 4, 0.25, "%", False),
        ("gvz", "GVZ", CROSS_ASSET_SYMBOLS["gvz"][0], "positive", gvz, 5, 5.0, "%", False),
        ("vix", "VIX", CROSS_ASSET_SYMBOLS["vix"][0], "positive", vix, 4, 5.0, "%", False),
    ]

    signals: list[CorrelationSignal] = []
    for key, instrument, symbol, relation, snapshot, weight, threshold, unit, use_bps in specs:
        signal, impact, confirmation, contradiction = make_correlation_signal(
            key,
            instrument,
            symbol,
            relation,
            snapshot,
            gold_proxy,
            weight,
            threshold,
            change_unit=unit,
            use_bps=use_bps,
        )
        signals.append(signal)
        score += impact
        if confirmation:
            confirmations.append(confirmation)
        if contradiction:
            contradictions.append(contradiction)

    if gvz is not None:
        gvz_average = average_close(gvz.points, 20)
        if gvz_average:
            drivers["gvz"]["avg20"] = round(gvz_average, 2)
            drivers["gvz"]["ratio_to_avg20"] = round(gvz.price / gvz_average, 2)

    score_int = round(clamp(score, 0, 100))
    if score_int >= 70:
        status = "favorable"
        verdict = "BUY renforce"
        summary = "Les correlations renforcent le BUY gold: dollar/taux reels/refuges/metaux ou miners convergent suffisamment."
    elif score_int >= 55:
        status = "plutot favorable"
        verdict = "BUY accepte"
        summary = "Les correlations soutiennent le gold, mais pas assez pour oublier le prix et le timing technique."
    elif score_int <= 30:
        status = "defavorable"
        verdict = "SELL renforce"
        summary = "Les correlations renforcent un biais SELL gold ou rejettent clairement un BUY impulsif."
    elif score_int <= 45:
        status = "plutot defavorable"
        verdict = "BUY fragile"
        summary = (
            f"Cross-assets divergents (score {score_int}/100): seuil de validation BUY non atteint. "
            f"Confirmations attendues: DXY en baisse, GDX/silver en hausse, real yield en baisse."
        )
    else:
        status = "mitige"
        verdict = "neutre"
        summary = (
            f"Cross-assets equilibres (score {score_int}/100): pas d'avantage directionnel. "
            f"Exiger une cassure technique propre avant d'agir."
        )

    return CrossAssetAnalysis(
        score=score_int,
        status=status,
        verdict=verdict,
        summary=summary,
        confirmations=confirmations[:5],
        contradictions=contradictions[:5],
        drivers=drivers,
        signals=signals,
    )


def build_event_mode_analysis(
    gold: SymbolSnapshot,
    readings: list[TechnicalReading],
    gvz: SymbolSnapshot | None,
    vix: SymbolSnapshot | None,
    macro_catalysts: MacroCatalystCalendar | None = None,
) -> EventModeAnalysis:
    score = 0.0
    reasons: list[str] = []

    max_volume_ratio = max((reading.volume_ratio for reading in readings), default=0.0)
    if max_volume_ratio >= 2.0:
        score += 35
        reasons.append(f"Volume proxy tres eleve: x{max_volume_ratio:.2f} vs moyenne.")
    elif max_volume_ratio >= 1.5:
        score += 20
        reasons.append(f"Volume proxy au-dessus de la normale: x{max_volume_ratio:.2f}.")

    if gvz is not None:
        gvz_average = average_close(gvz.points, 20)
        if gvz_average:
            gvz_ratio = gvz.price / gvz_average
            if gvz_ratio >= 1.35:
                score += 35
                reasons.append(f"GVZ tres eleve vs moyenne 20j: x{gvz_ratio:.2f}.")
            elif gvz_ratio >= 1.15:
                score += 20
                reasons.append(f"GVZ au-dessus de sa moyenne 20j: x{gvz_ratio:.2f}.")

    if vix is not None and vix.change_pct >= 10:
        score += 18
        reasons.append(f"VIX en acceleration ({vix.change_pct:+.2f}%).")

    if macro_catalysts is not None:
        if macro_catalysts.pre_event_active:
            score += 30
            reasons.append(macro_catalysts.pre_event_summary)
        if macro_catalysts.density_status in {"elevated", "high_density"}:
            score += 12 if macro_catalysts.density_status == "elevated" else 22
            reasons.append(f"Densite macro {macro_catalysts.density_status}: {macro_catalysts.high_impact_24h} event(s) HIGH sur 24h.")

    intraday_points = gold.intraday_points or gold.points
    if len(intraday_points) >= 4:
        reference = intraday_points[-4].close
        if reference:
            short_move = ((gold.price - reference) / reference) * 100
            if abs(short_move) >= 0.35:
                score += 30
                reasons.append(f"Deplacement court terme violent sur XAU/USD ({short_move:+.2f}%).")
            elif abs(short_move) >= 0.20:
                score += 15
                reasons.append(f"Deplacement court terme notable sur XAU/USD ({short_move:+.2f}%).")

    score_int = round(clamp(score, 0, 100))
    active = score_int >= 45 or max_volume_ratio >= 2.0 or bool(macro_catalysts and macro_catalysts.pre_event_active)
    if active:
        return EventModeAnalysis(
            active=True,
            score=score_int,
            status="ACTIF",
            action="Gel prudent des nouvelles entrees: attendre stabilisation ou confirmation forte.",
            stop_multiplier=1.5,
            reasons=reasons[:5],
        )

    return EventModeAnalysis(
        active=False,
        score=score_int,
        status="normal",
        action="Pas de gel automatique: appliquer le plan de risque habituel.",
        stop_multiplier=1.0,
        reasons=reasons[:5] or ["Volatilite et volumes dans un regime exploitable."],
    )


def count_oil_shock_headlines(news: list[NewsItem]) -> int:
    count = 0
    for item in news:
        text = f"{item.title} {' '.join(item.score_reasons)}".lower()
        if any(keyword_matches(text, keyword) for keyword in OIL_SHOCK_KEYWORDS):
            count += 1
    return count


def finalize_market_regime(regime: MarketRegimeAnalysis, path: Path = REGIME_STATE_PATH) -> MarketRegimeAnalysis:
    try:
        if path.exists():
            data = json.loads(path.read_text(encoding="utf-8"))
            history = [str(item) for item in data.get("history", [])] if isinstance(data, dict) else []
        else:
            history = []
        history = (history + [regime.name])[-3:]
        if len(history) == 3 and len(set(history)) == 1 and regime.name != "Normal Macro":
            regime.confirmed = True
            if "Regime confirme par persistance 3 snapshots consecutifs." not in regime.reasons:
                regime.reasons.append("Regime confirme par persistance 3 snapshots consecutifs.")
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps({"updated_at": iso_now(), "current": regime.name, "history": history, "probabilities": regime.probabilities}, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
    except Exception:
        pass
    return regime


def build_market_regime_analysis(
    gold: SymbolSnapshot,
    dxy: SymbolSnapshot,
    us10y: SymbolSnapshot,
    news: list[NewsItem],
    wti: SymbolSnapshot | None = None,
    brent: SymbolSnapshot | None = None,
    event_mode: EventModeAnalysis | None = None,
) -> MarketRegimeAnalysis:
    oil_shock_headlines = count_oil_shock_headlines(news)
    oil_changes = [snapshot.change_pct for snapshot in (wti, brent) if snapshot is not None]
    oil_change = max(oil_changes, default=0.0)
    oil_available = bool(oil_changes)
    dxy_strong = dxy.change_pct >= 0.20
    dxy_weak = dxy.change_pct <= -0.20
    yields_up = (us10y.change_abs * 100) >= 3
    yields_down = (us10y.change_abs * 100) <= -3
    gold_weak = gold.change_pct <= -0.20
    gold_strong = gold.change_pct >= 0.20

    oil_shock_score = 0.0
    reasons: list[str] = []
    if oil_shock_headlines:
        oil_shock_score += min(35, 15 + (oil_shock_headlines * 8))
        reasons.append(f"{oil_shock_headlines} headline(s) liees a Iran/Hormuz/petrole detectees.")
    if oil_available and oil_change >= 1.0:
        oil_shock_score += 25
        reasons.append(f"WTI/Brent montent nettement: variation max {oil_change:+.2f}%.")
    elif oil_available and oil_change >= 0.35:
        oil_shock_score += 12
        reasons.append(f"WTI/Brent gardent une prime de risque: variation max {oil_change:+.2f}%.")
    elif oil_available:
        reasons.append(
            f"WTI/Brent ne confirment pas un choc petrole tant que la variation reste sous +1.0% sur 1h "
            f"(actuel {oil_change:+.2f}%)."
        )
    else:
        reasons.append("WTI/Brent indisponibles: regime oil shock moins fiable.")

    if dxy_strong:
        oil_shock_score += 12
        reasons.append(f"DXY en hausse ({dxy.change_pct:+.2f}%): recherche de liquidite dollar possible.")
    if yields_up:
        oil_shock_score += 8
        reasons.append(f"10Y US en hausse ({us10y.change_abs * 100:+.1f} bps): choc inflation/taux possible.")
    if gold_weak:
        oil_shock_score += 15
        reasons.append(f"Gold recule ({gold.change_pct:+.2f}%) pendant le stress: flux pas automatiquement refuge.")
    if event_mode is not None and event_mode.active:
        oil_shock_score += 6
        reasons.append(
            f"Mode event actif (score {event_mode.score}/100): exposition or reduite tant que la volatilite reste elevee."
        )

    oil_shock_score = round(clamp(oil_shock_score, 0, 100))
    safe_haven_score = round(clamp((45 if oil_shock_headlines else 25) + (18 if gold_strong else 0) + (10 if dxy_weak else 0) + (8 if yields_down else 0), 0, 100))
    dollar_squeeze_score = round(clamp((42 if dxy_strong and gold_weak else 0) + abs(dxy.change_pct) * 12 + abs(gold.change_pct) * 8, 0, 100))
    risk_on_score = round(clamp((35 if dxy_weak else 0) + (25 if yields_down else 0) + (18 if gold_weak else 0), 0, 100))
    stagflation_score = round(clamp((28 if gold_strong else 0) + (28 if yields_up else 0) + (22 if dxy_strong else 0) + (12 if oil_change >= 0.35 else 0), 0, 100))
    deesc_score = round(clamp((45 if oil_shock_headlines and oil_change <= -0.35 else 0) + oil_shock_headlines * 5, 0, 100))
    probabilities = {
        "Hormuz / Oil Shock": oil_shock_score,
        "Safe-Haven Gold": safe_haven_score,
        "Dollar Liquidity Squeeze": dollar_squeeze_score,
        "Risk-On / Carry Trade": risk_on_score,
        "Stagflation Fear": stagflation_score,
        "De-escalation / Oil Relief": deesc_score,
        "Normal Macro": max(0, 100 - max(oil_shock_score, safe_haven_score, dollar_squeeze_score, risk_on_score, stagflation_score, deesc_score)),
    }
    component_scores = {
        "oil_shock_headlines": min(100, oil_shock_headlines * 20),
        "oil_change": round(clamp(oil_change * 18, -100, 100)),
        "dxy_change": round(clamp(dxy.change_pct * 50, -100, 100)),
        "yields_change_bps": round(clamp(us10y.change_abs * 100 * 8, -100, 100)),
        "gold_change": round(clamp(gold.change_pct * 40, -100, 100)),
    }
    regime_trend = "escalade" if oil_shock_score >= 70 or stagflation_score >= 70 else "accalmie" if deesc_score >= 50 or risk_on_score >= 65 else "stable"
    if oil_shock_score >= 58:
        return finalize_market_regime(MarketRegimeAnalysis(
            name="Hormuz / Oil Shock",
            status="ACTIF",
            score=oil_shock_score,
            gold_impact="mixte/baissier court terme",
            summary=(
                "Regime Hormuz/Oil Shock detecte: la tension politique soutient d'abord oil et dollar. "
                "Gold peut etre vendu pour liquidite tant que Brent/WTI, DXY ou les taux dominent."
            ),
            reasons=reasons[:6],
            trend=regime_trend,
            confirmed=oil_shock_score >= 70,
            probabilities=probabilities,
            component_scores=component_scores,
        ))

    if oil_shock_headlines and oil_change <= -0.35:
        deesc_ctx = ExplanationContext(
            fact=f"{oil_shock_headlines} headline(s) Iran/Hormuz/petrole detectees mais oil recule",
            evidence=f"WTI/Brent: variation max {oil_change:+.2f}%, DXY {dxy.change_pct:+.2f}%",
            confirmation=(
                "necessiterait WTI > +1.0% sur 1h ou DXY > +0.50% pour confirmer un choc"
            ),
            impact="prime de risque qui sort de l'or si oil et volatilite se detendent",
            action="WATCH_SELL gold tant que oil baisse, sinon NO_TRADE refuge",
        )
        return finalize_market_regime(MarketRegimeAnalysis(
            name="De-escalation / Oil Relief",
            status="SURVEILLANCE",
            score=round(clamp(45 + oil_shock_headlines * 5, 0, 100)),
            gold_impact="prime de risque en reflux",
            summary=ExplanationLayer.geopolitical_regime(deesc_ctx),
            reasons=reasons[:6],
            trend="accalmie",
            confirmed=deesc_score >= 60,
            probabilities=probabilities,
            component_scores=component_scores,
        ))

    if stagflation_score >= 65:
        return finalize_market_regime(MarketRegimeAnalysis(
            name="Stagflation Fear",
            status="ACTIF",
            score=stagflation_score,
            gold_impact="haussier mais volatil",
            summary=(
                "Regime Stagflation Fear: gold monte avec dollar et rendements. "
                "Le marche price une inflation/stress reel qui depasse le simple effet taux."
            ),
            reasons=reasons[:6]
            + [
                f"Gold {gold.change_pct:+.2f}%, DXY {dxy.change_pct:+.2f}%, 10Y {us10y.change_abs * 100:+.1f} bps: combinaison stagflation potentielle."
            ],
            trend=regime_trend,
            confirmed=stagflation_score >= 75,
            probabilities=probabilities,
            component_scores=component_scores,
        ))

    if risk_on_score >= 65:
        return finalize_market_regime(MarketRegimeAnalysis(
            name="Risk-On / Carry Trade",
            status="ACTIF",
            score=risk_on_score,
            gold_impact="baissier/defensif",
            summary=(
                "Regime Risk-On / Carry Trade: dollar et rendements se detendent mais gold ne capte pas le flux. "
                "Le capital favorise les actifs de risque plutot que la couverture or."
            ),
            reasons=reasons[:6]
            + [
                f"DXY {dxy.change_pct:+.2f}%, 10Y {us10y.change_abs * 100:+.1f} bps, gold {gold.change_pct:+.2f}%."
            ],
            trend="accalmie",
            confirmed=risk_on_score >= 75,
            probabilities=probabilities,
            component_scores=component_scores,
        ))

    if dxy_strong and gold_weak:
        return finalize_market_regime(MarketRegimeAnalysis(
            name="Dollar Liquidity Squeeze",
            status="ACTIF",
            score=round(clamp(52 + abs(dxy.change_pct) * 10 + abs(gold.change_pct) * 8, 0, 100)),
            gold_impact="baissier court terme",
            summary=(
                "Le marche cherche surtout de la liquidite dollar: gold peut baisser meme si le contexte reste stressant."
            ),
            reasons=reasons[:6] or [f"DXY monte ({dxy.change_pct:+.2f}%) pendant que gold recule ({gold.change_pct:+.2f}%)."],
            trend=regime_trend,
            confirmed=dollar_squeeze_score >= 70,
            probabilities=probabilities,
            component_scores=component_scores,
        ))

    if oil_shock_headlines and gold_strong and not dxy_strong:
        return finalize_market_regime(MarketRegimeAnalysis(
            name="Safe-Haven Gold",
            status="ACTIF",
            score=round(clamp(55 + oil_shock_headlines * 5 + max(gold.change_pct, 0) * 8, 0, 100)),
            gold_impact="haussier",
            summary=(
                "Le risque politique se transmet surtout par la demande de couverture sur l'or: gold confirme mieux que dollar/oil."
            ),
            reasons=reasons[:6] or ["Gold confirme le role refuge pendant que le dollar ne domine pas."],
            trend=regime_trend,
            confirmed=safe_haven_score >= 70,
            probabilities=probabilities,
            component_scores=component_scores,
        ))

    return finalize_market_regime(MarketRegimeAnalysis(
        name="Normal Macro",
        status="NORMAL",
        score=oil_shock_score,
        gold_impact="neutre",
        summary="Pas de regime Hormuz/Oil Shock confirme: le gold reste surtout pilote par DXY, taux, technique et headlines.",
        reasons=reasons[:6] or ["Aucun choc petrole/geopolitique suffisamment confirme."],
        trend="stable",
        confirmed=False,
        probabilities=probabilities,
        component_scores=component_scores,
    ))


def normalize_agent_bias(verdict: str) -> str:
    upper = verdict.upper()
    if "BUY" in upper or "BULL" in upper or "HAUS" in upper:
        return "BUY"
    if "SELL" in upper or "BEAR" in upper or "BAISS" in upper:
        return "SELL"
    if "CAUTION" in upper or "PRUD" in upper or "WAIT" in upper:
        return "CAUTION"
    return "NEUTRAL"


def score_to_bias(score: int, buy_threshold: int = 56, sell_threshold: int = 44) -> str:
    if score >= buy_threshold:
        return "BUY"
    if score <= sell_threshold:
        return "SELL"
    return "NEUTRAL"


def clamp_score(value: float) -> int:
    return round(clamp(value, 0, 100))


def price_range_position(gold: SymbolSnapshot) -> float:
    if gold.day_high <= gold.day_low:
        return 50.0
    return clamp(((gold.price - gold.day_low) / (gold.day_high - gold.day_low)) * 100, 0, 100)


def nearest_psychological_level(price: float, step: float = 25.0) -> tuple[float, float]:
    if step <= 0:
        return price, 0.0
    level = round(price / step) * step
    return level, price - level


def price_action_levels(gold: SymbolSnapshot) -> dict[str, float]:
    high = gold.day_high or max(gold.price, gold.previous_close)
    low = gold.day_low or min(gold.price, gold.previous_close)
    close = gold.previous_close or gold.price
    day_range = max(high - low, 1.0)
    return {
        "support": round(gold.support or low, 2),
        "resistance": round(gold.resistance or high, 2),
        "camarilla_s3": round(close - day_range * 1.1 / 4, 2),
        "camarilla_r3": round(close + day_range * 1.1 / 4, 2),
        "camarilla_s4": round(close - day_range * 1.1 / 2, 2),
        "camarilla_r4": round(close + day_range * 1.1 / 2, 2),
    }


def detect_recent_swing_levels(points: list[PricePoint], source: str = "proxy GC=F") -> dict[str, Any]:
    if len(points) < 18:
        return {"status": "insufficient", "summary": "Historique intraday insuffisant pour swing M15."}
    candles_5m = price_points_to_candles(points, "M5", source, iso_now())
    candles = resample_candles(candles_5m, "M15") if candles_5m else []
    if len(candles) < 8:
        return {"status": "insufficient", "summary": "Bougies M15 insuffisantes pour swing."}
    recent = candles[-12:]
    swing_high = max(candle.high for candle in recent)
    swing_low = min(candle.low for candle in recent)
    last_close = recent[-1].close
    if last_close > swing_high:
        structure = "breakout"
    elif last_close < swing_low:
        structure = "breakdown"
    elif last_close >= swing_high - (swing_high - swing_low) * 0.25:
        structure = "pression resistance"
    elif last_close <= swing_low + (swing_high - swing_low) * 0.25:
        structure = "pression support"
    else:
        structure = "range intraday"
    return {
        "status": "ok",
        "swing_high": round(swing_high, 2),
        "swing_low": round(swing_low, 2),
        "last_close": round(last_close, 2),
        "structure": structure,
        "summary": f"M15 {structure}: swing high {swing_high:.2f}, swing low {swing_low:.2f}, close {last_close:.2f}.",
    }


def classify_price_action_state(gold: SymbolSnapshot) -> tuple[str, int, list[str]]:
    position = price_range_position(gold)
    levels = price_action_levels(gold)
    psych_level, psych_distance = nearest_psychological_level(gold.price)
    reasons: list[str] = [
        f"Position range jour {position:.0f}/100.",
        f"Niveau psychologique proche {psych_level:.0f}, distance {psych_distance:+.2f}.",
    ]
    score = 50 + gold.change_pct * 16 + gold.period_change_pct * 5
    state = "range"
    if gold.price > levels["resistance"] and gold.change_pct > 0:
        state = "breakout"
        score += 10
        reasons.append("Prix au-dessus resistance jour: breakout potentiel.")
    elif gold.price < levels["support"] and gold.change_pct < 0:
        state = "breakdown"
        score -= 10
        reasons.append("Prix sous support jour: breakdown potentiel.")
    elif position >= 80 and gold.change_pct < 0:
        state = "reversal"
        score -= 8
        reasons.append("Rejet potentiel depuis le haut du range.")
    elif position <= 20 and gold.change_pct > 0:
        state = "reversal"
        score += 8
        reasons.append("Rebond potentiel depuis le bas du range.")
    elif abs(psych_distance) <= 3:
        state = "consolidation"
        reasons.append("Prix colle a un niveau rond: consolidation probable.")
    elif gold.change_pct > 0 and 35 <= position <= 75:
        state = "pullback"
        score += 4
        reasons.append("Pullback haussier dans le range.")
    elif gold.change_pct < 0 and 25 <= position <= 65:
        state = "pullback"
        score -= 4
        reasons.append("Pullback baissier dans le range.")
    return state, clamp_score(score), reasons


def geopolitical_agent_bias_from_regime(market_regime: MarketRegimeAnalysis | None) -> str:
    if market_regime is None:
        return "NEUTRAL"
    mapping = {
        "Hormuz / Oil Shock": "SELL",
        "Safe-Haven Gold": "BUY",
        "De-escalation / Oil Relief": "SELL",
        "Dollar Liquidity Squeeze": "SELL",
        "Risk-On / Carry Trade": "SELL",
        "Stagflation Fear": "BUY",
        "Normal Macro": "NEUTRAL",
    }
    return mapping.get(market_regime.name, "NEUTRAL")


def event_fact_direction(fact: NewsFact) -> str:
    impact = fact.impact_bias.upper()
    if impact == "BULLISH":
        return "BUY"
    if impact == "BEARISH":
        return "SELL"
    return "NEUTRAL"


NEWS_REACTION_HIGH_IMPACT_TERMS = (
    "trump",
    "white house",
    "netanyahu",
    "israel",
    "iran",
    "hormuz",
    "strait",
    "tanker",
    "ship",
    "navy",
    "missile",
    "attack",
    "sanction",
    "ceasefire",
    "truce",
    "fed",
    "fomc",
    "powell",
    "cpi",
    "pce",
    "nfp",
    "payroll",
)


def fast_news_event_id(title: str, source: str, published_at: str) -> str:
    seed = f"{source}|{published_at}|{normalize_title_for_dedupe(title)}"
    return hashlib.sha1(seed.encode("utf-8")).hexdigest()[:12]


def event_latency_seconds(published_at: str, reference: datetime) -> float | None:
    published = parse_iso_datetime(published_at)
    if published is None:
        return None
    return max(0.0, (reference - published).total_seconds())


def event_valid_until(published_at: str, reference: datetime, minutes: int) -> str:
    published = parse_iso_datetime(published_at)
    base = published if published is not None else reference
    return (base + timedelta(minutes=minutes)).isoformat()


def classify_news_reaction_event(fact: NewsFact, now: datetime | None = None) -> FastNewsEvent | None:
    reference = now or datetime.now(timezone.utc)
    text = f"{fact.title} {' '.join(fact.themes)} {fact.category} {fact.source}".lower()
    category = logical_category(fact)
    source_tier = int(getattr(fact, "source_tier", news_source_tier(fact.source, fact.source_url)) or 4)
    confidence = int(getattr(fact, "confidence", 50) or 50)
    latency = event_latency_seconds(fact.published_at, reference)
    age_minutes = (latency / 60.0) if latency is not None else None
    fact_type = str(getattr(fact, "fact_type", "unconfirmed_headline"))
    if source_tier > 3 or confidence < 55 or fact_type in {"rumor", "opinion"}:
        return None
    if age_minutes is not None and age_minutes > 30:
        return None
    if not text_contains_any(text, NEWS_REACTION_HIGH_IMPACT_TERMS):
        return None

    event_type = "MARKET_MOVING_NEWS"
    direction = event_fact_direction(fact)
    reasons: list[str] = []
    rejects = text_contains_any(text, ("reject", "rejects", "rejected", "refuse", "refuses", "denies", "failed", "collapse", "breakdown", "no deal"))
    accepts = text_contains_any(text, ("accept", "accepts", "accepted", "agree", "agrees", "agreed", "deal", "ceasefire", "truce", "peace", "reopen"))

    if text_contains_any(text, ("iran", "hormuz", "strait", "tanker", "ship", "navy", "missile", "attack", "blockade", "sanction")):
        if accepts and not rejects:
            event_type = "GEOPOLITICAL_DEESCALATION"
            direction = "SELL"
            reasons.append("Accalmie geopolitique: prime refuge gold susceptible de se detendre.")
        else:
            event_type = "GEOPOLITICAL_ESCALATION"
            direction = "BUY"
            reasons.append("Escalade geopolitique: demande refuge gold possible, a confirmer par XAU/USD et DXY.")
    elif text_contains_any(text, ("fed", "fomc", "powell", "rate", "rates")):
        if text_contains_any(text, ("cut", "cuts", "dovish", "easing", "pause", "slows", "liquidity")):
            event_type = "FED_DOVISH_SURPRISE"
            direction = "BUY"
            reasons.append("Surprise Fed dovish: pression baissiere possible sur DXY/taux, favorable gold.")
        elif text_contains_any(text, ("hike", "hikes", "hawkish", "higher for longer", "inflation risk", "tightening")):
            event_type = "FED_HAWKISH_SURPRISE"
            direction = "SELL"
            reasons.append("Surprise Fed hawkish: DXY/taux peuvent monter, negatif gold.")
    elif text_contains_any(text, ("cpi", "pce", "inflation", "nfp", "payroll", "jobs", "employment")):
        event_type = "MACRO_SURPRISE"
        if text_contains_any(text, ("hot", "hotter", "above forecast", "beats", "strong", "sticky", "accelerates")):
            direction = "SELL"
            reasons.append("Surprise macro chaude: taux/DXY peuvent monter, negatif gold.")
        elif text_contains_any(text, ("cool", "cooler", "below forecast", "misses", "weak", "slows", "disinflation")):
            direction = "BUY"
            reasons.append("Surprise macro faible/dovish: taux/DXY peuvent reculer, favorable gold.")
    elif text_contains_any(text, ("trump", "white house", "netanyahu")):
        event_type = "POLITICAL_STATEMENT"
        if direction == "NEUTRAL":
            direction = "BUY" if text_contains_any(text, ("war", "attack", "sanction", "threat")) else "WAIT"
        reasons.append("Declaration politique detectee: elle doit etre confirmee par le prix avant tout trade.")

    if direction not in {"BUY", "SELL"}:
        return None

    validity = 30 if source_tier <= 2 and confidence >= 75 else 15
    published = parse_iso_datetime(fact.published_at)
    is_breaking = (age_minutes is not None and age_minutes <= 15) or source_tier == 1
    score = clamp_score(confidence + (10 if source_tier <= 2 else 0) + (8 if is_breaking else 0))
    reasons.extend(
        [
            f"Source Tier {source_tier}, confiance {confidence}/100.",
            f"Categorie {category}; signal valable {validity} min.",
        ]
    )
    return FastNewsEvent(
        event_id=fast_news_event_id(fact.title, fact.source, fact.published_at),
        title=fact.title,
        source=fact.source,
        source_url=fact.source_url,
        published_at=fact.published_at,
        detected_at=reference.isoformat(),
        processed_at=reference.isoformat(),
        category=fact.category,
        logical_category=category,
        source_tier=source_tier,
        event_type=event_type,
        direction=direction,
        score=score,
        confidence=min(100, max(confidence, score)),
        validity_minutes=validity,
        valid_until=event_valid_until(fact.published_at, reference, validity),
        latency_seconds=latency,
        is_breaking=is_breaking,
        reasons=reasons,
    )


class FastNewsListener:
    """Filtre les NewsFacts recents pour ne laisser passer que les evenements tradables."""

    def __init__(self, max_age_minutes: int = 30) -> None:
        self.max_age_minutes = max_age_minutes

    def select_events(self, event_facts: list[NewsFact], now: datetime | None = None) -> list[FastNewsEvent]:
        reference = now or datetime.now(timezone.utc)
        events: list[FastNewsEvent] = []
        seen: set[str] = set()
        for fact in event_facts:
            event = classify_news_reaction_event(fact, reference)
            if event is None:
                continue
            age = event.latency_seconds / 60.0 if event.latency_seconds is not None else None
            if age is not None and age > self.max_age_minutes:
                continue
            if event.event_id in seen:
                continue
            seen.add(event.event_id)
            events.append(event)
        return sorted(events, key=lambda item: (item.is_breaking, item.score, item.confidence), reverse=True)


def cross_asset_oil_change_pct(cross_asset: CrossAssetAnalysis | None) -> float | None:
    if cross_asset is None:
        return None
    changes: list[float] = []
    for key in ("wti", "brent"):
        driver = cross_asset.drivers.get(key, {})
        if driver.get("available") and driver.get("change_pct") is not None:
            changes.append(float(driver["change_pct"]))
    if not changes:
        return None
    return max(changes, key=lambda value: abs(value))


def detect_news_reaction_price(
    event: FastNewsEvent,
    gold: SymbolSnapshot,
    dxy: SymbolSnapshot,
    us10y: SymbolSnapshot,
    cross_asset: CrossAssetAnalysis | None,
) -> PriceReactionSignal:
    direction = event.direction
    xau_change = gold.period_change_pct if abs(gold.period_change_pct) >= 0.01 else gold.change_pct
    dxy_change = dxy.period_change_pct if abs(dxy.period_change_pct) >= 0.01 else dxy.change_pct
    us10y_bps = us10y.change_abs * 100
    oil_change = cross_asset_oil_change_pct(cross_asset)
    checks: list[str] = []
    score = 0

    if direction == "BUY":
        if xau_change >= 0.05:
            score += 1
            checks.append(f"XAU/USD confirme BUY ({xau_change:+.2f}%).")
        else:
            checks.append(f"XAU/USD ne confirme pas encore BUY ({xau_change:+.2f}%).")
        if dxy_change <= -0.05:
            score += 1
            checks.append(f"DXY recule ({dxy_change:+.2f}%), favorable gold.")
        else:
            checks.append(f"DXY ne confirme pas BUY ({dxy_change:+.2f}%).")
        if us10y_bps <= -1.0:
            score += 1
            checks.append(f"10Y US recule ({us10y_bps:+.1f} bps).")
        if event.event_type == "GEOPOLITICAL_ESCALATION" and oil_change is not None:
            if oil_change >= 0.30:
                score += 1
                checks.append(f"Oil confirme l'escalade ({oil_change:+.2f}%).")
            else:
                checks.append(f"Oil ne confirme pas l'escalade ({oil_change:+.2f}%).")
    else:
        if xau_change <= -0.05:
            score += 1
            checks.append(f"XAU/USD confirme SELL ({xau_change:+.2f}%).")
        else:
            checks.append(f"XAU/USD ne confirme pas encore SELL ({xau_change:+.2f}%).")
        if dxy_change >= 0.05:
            score += 1
            checks.append(f"DXY monte ({dxy_change:+.2f}%), pression sur gold.")
        else:
            checks.append(f"DXY ne confirme pas SELL ({dxy_change:+.2f}%).")
        if us10y_bps >= 1.0:
            score += 1
            checks.append(f"10Y US monte ({us10y_bps:+.1f} bps).")
        if event.event_type == "GEOPOLITICAL_DEESCALATION" and oil_change is not None:
            if oil_change <= -0.30:
                score += 1
                checks.append(f"Oil confirme l'accalmie ({oil_change:+.2f}%).")
            else:
                checks.append(f"Oil ne confirme pas l'accalmie ({oil_change:+.2f}%).")

    fade_trap = (
        (direction == "BUY" and (xau_change <= -0.10 or dxy_change >= 0.20))
        or (direction == "SELL" and (xau_change >= 0.10 or dxy_change <= -0.20))
    )
    if fade_trap:
        checks.append("Fade trap detecte: la reaction prix contredit la news.")
    confirms = score >= 2 and not fade_trap
    return PriceReactionSignal(
        direction=direction,
        confirmation_score=score,
        confirms=confirms,
        fade_trap=fade_trap,
        xauusd_change_pct=round(xau_change, 3),
        dxy_change_pct=round(dxy_change, 3),
        us10y_change_bps=round(us10y_bps, 2),
        oil_change_pct=round(oil_change, 3) if oil_change is not None else None,
        checks=checks,
    )


def news_reaction_levels(direction: str, price: float, move_pct: float) -> tuple[float, float, float, float, float, float]:
    move_abs = max(abs(price * move_pct / 100.0), price * 0.00075, 3.0)
    risk = max(move_abs * 0.72, 3.0)
    entry_low = price - risk * 0.18
    entry_high = price + risk * 0.18
    if direction == "BUY":
        return (
            round(entry_low, 2),
            round(entry_high, 2),
            round(price - risk, 2),
            round(price + risk * 1.65, 2),
            round(price + risk * 2.65, 2),
            round(price + risk * 4.00, 2),
        )
    return (
        round(entry_low, 2),
        round(entry_high, 2),
        round(price + risk, 2),
        round(price - risk * 1.65, 2),
        round(price - risk * 2.65, 2),
        round(price - risk * 4.00, 2),
    )


def is_weekend_market_window(now: datetime) -> bool:
    return now.weekday() in {5, 6}


def detect_current_session(now: datetime | None = None) -> str:
    reference = now or datetime.now(timezone.utc)
    if is_weekend_market_window(reference):
        return "weekend"
    utc_hour = reference.astimezone(timezone.utc).hour
    if 0 <= utc_hour < 7:
        return "asian"
    if 7 <= utc_hour < 9:
        return "london_open"
    if 9 <= utc_hour < 13:
        return "london_morning"
    if 13 <= utc_hour < 16:
        return "london_ny_overlap"
    if 16 <= utc_hour < 19:
        return "ny_afternoon"
    if 19 <= utc_hour < 21:
        return "ny_close"
    return "off_hours"


def normalize_setup_direction(direction: str) -> str:
    upper = direction.upper()
    if "BUY" in upper:
        return "BUY"
    if "SELL" in upper:
        return "SELL"
    return "NEUTRAL"


def setup_condition(name: str, met: bool, reason: str) -> dict[str, Any]:
    return {"name": name, "met": bool(met), "reason": reason}


def setup_partial_conditions(
    buy: list[dict[str, Any]] | None = None,
    sell: list[dict[str, Any]] | None = None,
) -> dict[str, list[dict[str, Any]]]:
    return {"buy": buy or [], "sell": sell or []}


def news_reaction_status_for_setup(status: str) -> str:
    upper = status.upper()
    if upper == "TRADE_READY":
        return "TRADE_READY"
    if upper == "WATCH":
        return "WATCH"
    if upper == "SUSPENDED":
        return "SUSPENDED"
    return "NO_SETUP_TRADE"


def news_reaction_to_setup_candidate(setup: NewsReactionTradePlan | None) -> SetupCandidate:
    if setup is None:
        reference = iso_now()
        return SetupCandidate(
            name="NewsReactionSetup",
            status="NO_SETUP_TRADE",
            direction="NEUTRAL",
            confidence=0,
            confluence_score=0,
            conditions_met=[],
            entry_zone_low=0.0,
            entry_zone_high=0.0,
            stop_loss=0.0,
            tp1=0.0,
            tp2=0.0,
            tp3=0.0,
            rr_tp1=0.0,
            rr_tp2=0.0,
            rr_tp3=0.0,
            validity_minutes=0,
            cooldown_after_loss_minutes=240,
            cooldown_after_win_minutes=120,
            preferred_session="all",
            reasons=["Aucun evenement news reaction qualifie."],
            blockers=[],
            detected_at=reference,
            metadata={"source": "NewsReactionEngine"},
            partial_conditions=setup_partial_conditions(),
        )
    status = news_reaction_status_for_setup(setup.status)
    conditions = ["fast_news_event"]
    if setup.confirmation_score:
        conditions.append(f"confirmation_score_{setup.confirmation_score}")
    if setup.latency_seconds is not None:
        conditions.append("latency_measured")
    side = "buy" if normalize_setup_direction(setup.direction) == "BUY" else "sell"
    partial_conditions = setup_partial_conditions()
    partial_conditions[side] = [
        setup_condition("fast_news_event", True, "Evenement rapide qualifie par NewsReactionEngine."),
        setup_condition(
            "confirmation_score",
            setup.confirmation_score > 0,
            f"Score confirmation news/prix/cross-assets: {setup.confirmation_score}.",
        ),
        setup_condition(
            "latency_measured",
            setup.latency_seconds is not None,
            "Latence source -> systeme mesuree." if setup.latency_seconds is not None else "Latence non mesuree.",
        ),
    ]
    return SetupCandidate(
        name="NewsReactionSetup",
        status=status,
        direction=normalize_setup_direction(setup.direction),
        confidence=setup.confidence,
        confluence_score=setup.confirmation_score,
        conditions_met=conditions,
        entry_zone_low=setup.entry_zone_low,
        entry_zone_high=setup.entry_zone_high,
        stop_loss=setup.stop_loss,
        tp1=setup.tp1,
        tp2=setup.tp2,
        tp3=setup.tp3,
        rr_tp1=setup.risk_reward_tp1,
        rr_tp2=setup.risk_reward_tp2,
        rr_tp3=setup.risk_reward_tp3,
        validity_minutes=setup.validity_minutes,
        cooldown_after_loss_minutes=240,
        cooldown_after_win_minutes=120,
        preferred_session="all",
        reasons=setup.reasons[:8],
        blockers=setup.blockers[:6],
        detected_at=setup.created_at,
        metadata={
            "event_type": setup.event_type,
            "event_id": setup.event_id,
            "title": setup.title,
            "source": setup.source,
            "source_url": setup.source_url,
            "valid_until": setup.valid_until,
            "latency_seconds": setup.latency_seconds,
            "entry_type": setup.entry_type,
        },
        partial_conditions=partial_conditions,
    )


def no_setup_candidate(
    name: str,
    reason: str,
    preferred_session: str = "all",
    metadata: dict[str, Any] | None = None,
    partial_conditions: dict[str, list[dict[str, Any]]] | None = None,
) -> SetupCandidate:
    return SetupCandidate(
        name=name,
        status="NO_SETUP_TRADE",
        direction="NEUTRAL",
        confidence=0,
        confluence_score=0,
        conditions_met=[],
        entry_zone_low=0.0,
        entry_zone_high=0.0,
        stop_loss=0.0,
        tp1=0.0,
        tp2=0.0,
        tp3=0.0,
        rr_tp1=0.0,
        rr_tp2=0.0,
        rr_tp3=0.0,
        validity_minutes=0,
        cooldown_after_loss_minutes=240,
        cooldown_after_win_minutes=60,
        preferred_session=preferred_session,
        reasons=[reason],
        blockers=[],
        detected_at=iso_now(),
        metadata=metadata or {},
        partial_conditions=partial_conditions or setup_partial_conditions(),
    )


def setup_candidate_from_levels(
    name: str,
    status: str,
    direction: str,
    confidence: int,
    confluence_score: int,
    conditions_met: list[str],
    levels: MarketTradeLevels,
    preferred_session: str,
    reasons: list[str],
    blockers: list[str] | None = None,
    cooldown_after_loss_minutes: int = 240,
    cooldown_after_win_minutes: int = 60,
    metadata: dict[str, Any] | None = None,
    partial_conditions: dict[str, list[dict[str, Any]]] | None = None,
) -> SetupCandidate:
    return SetupCandidate(
        name=name,
        status=status,
        direction=direction,
        confidence=clamp_score(confidence),
        confluence_score=clamp_score(confluence_score),
        conditions_met=conditions_met,
        entry_zone_low=levels.entry_zone_low,
        entry_zone_high=levels.entry_zone_high,
        stop_loss=levels.stop_loss,
        tp1=levels.tp1,
        tp2=levels.tp2,
        tp3=levels.tp3,
        rr_tp1=levels.risk_reward_tp1,
        rr_tp2=levels.risk_reward_tp2,
        rr_tp3=levels.risk_reward_tp3,
        validity_minutes=levels.validity_minutes,
        cooldown_after_loss_minutes=cooldown_after_loss_minutes,
        cooldown_after_win_minutes=cooldown_after_win_minutes,
        preferred_session=preferred_session,
        reasons=(reasons + levels.reasons)[:10],
        blockers=blockers or [],
        detected_at=iso_now(),
        metadata=metadata or {},
        partial_conditions=partial_conditions or setup_partial_conditions(),
    )


def last_candle_rejection(candles: list[OHLCCandle], direction: str, minimum_wick_share: float = 0.45) -> bool:
    if not candles:
        return False
    candle = candles[-1]
    full_range = max(candle.high - candle.low, 0.01)
    lower_wick = min(candle.open, candle.close) - candle.low
    upper_wick = candle.high - max(candle.open, candle.close)
    body = abs(candle.close - candle.open)
    if direction == "BUY":
        return lower_wick / full_range >= minimum_wick_share and candle.close >= candle.open - body * 0.25
    return upper_wick / full_range >= minimum_wick_share and candle.close <= candle.open + body * 0.25


def trend_direction_from_readings(readings: list[TechnicalReading]) -> str:
    relevant = [reading for reading in readings if reading.timeframe in {"1D", "4H", "1H"}]
    buy = sum(1 for reading in relevant if reading.verdict == "BUY")
    sell = sum(1 for reading in relevant if reading.verdict == "SELL")
    if buy >= 2 and buy > sell:
        return "BUY"
    if sell >= 2 and sell > buy:
        return "SELL"
    return "NEUTRAL"


def ema_stack_matches(reading: TechnicalReading | None, direction: str) -> bool:
    if reading is None:
        return False
    if direction == "BUY":
        return reading.ema20 >= reading.ema50 >= reading.ema100 >= reading.ema200
    if direction == "SELL":
        return reading.ema20 <= reading.ema50 <= reading.ema100 <= reading.ema200
    return False


def trend_strength_proxy(reading: TechnicalReading | None) -> float:
    if reading is None:
        return 0.0
    atr = max(reading.atr14, 1.0)
    ema_spread = abs(reading.ema20 - reading.ema200) / atr
    score_strength = abs(reading.score) / 10.0
    volume_boost = max(0.0, reading.volume_ratio - 1.0) * 0.4
    return round(min(5.0, ema_spread + score_strength + volume_boost), 2)


def direction_by_level_proximity(price: float, lower_level: float, upper_level: float, tolerance: float) -> str:
    if abs(price - lower_level) <= tolerance:
        return "BUY"
    if abs(price - upper_level) <= tolerance:
        return "SELL"
    return "NEUTRAL"


def range_bounds_from_candles(candles: list[OHLCCandle]) -> tuple[float, float, int, int]:
    if not candles:
        return 0.0, 0.0, 0, 0
    recent = candles[-24:] if len(candles) >= 24 else candles
    low = min(candle.low for candle in recent)
    high = max(candle.high for candle in recent)
    range_size = max(high - low, 0.01)
    tolerance = max(range_size * 0.08, 1.0)
    low_touches = sum(1 for candle in recent if candle.low <= low + tolerance)
    high_touches = sum(1 for candle in recent if candle.high >= high - tolerance)
    return round(low, 2), round(high, 2), low_touches, high_touches


def asian_range_from_candles(candles: list[OHLCCandle], now: datetime | None = None) -> tuple[float, float]:
    if not candles:
        return 0.0, 0.0
    reference = now or datetime.now(timezone.utc)
    reference_date = reference.astimezone(timezone.utc).date()
    asian = [
        candle
        for candle in candles
        if (stamp := datetime.fromtimestamp(candle.timestamp, timezone.utc)).date() == reference_date
        and 0 <= stamp.hour < 7
    ]
    if len(asian) < 4:
        return 0.0, 0.0
    return round(min(candle.low for candle in asian), 2), round(max(candle.high for candle in asian), 2)


def candidate_status_from_conditions(
    conditions_count: int,
    blockers: list[str],
    ready_threshold: int,
    watch_threshold: int,
) -> str:
    if blockers and conditions_count < ready_threshold:
        return "NO_SETUP_TRADE"
    if conditions_count >= ready_threshold and not blockers:
        return "TRADE_READY"
    if conditions_count >= watch_threshold:
        return "WATCH"
    return "NO_SETUP_TRADE"


def evaluate_pivot_rejection_setup(
    gold: SymbolSnapshot,
    readings: list[TechnicalReading],
    chart_store: ChartStore | None,
    now: datetime | None = None,
) -> SetupCandidate:
    session = detect_current_session(now)
    if session == "weekend":
        return no_setup_candidate(
            "PivotRejectionSetup",
            "Weekend: marche spot ferme, rejet de pivot suspendu.",
            metadata={"session": session},
        )
    h1 = reading_for_timeframe(readings, "H1") or reading_for_timeframe(readings, "M15")
    candles = candles_for_timeframe(chart_store, "1H") or candles_for_timeframe(chart_store, "15m")
    if h1 is None or not candles:
        return no_setup_candidate("PivotRejectionSetup", "Donnees H1/M15 insuffisantes pour tester le rejet de pivot.")

    levels = price_action_levels(gold)
    atr = max(h1.atr14, 3.0)
    tolerance = max(atr * 0.45, 2.5)
    lower_candidates = [levels["camarilla_s3"], levels["camarilla_s4"], levels["support"]]
    upper_candidates = [levels["camarilla_r3"], levels["camarilla_r4"], levels["resistance"]]
    lower = min(lower_candidates, key=lambda level: abs(gold.price - level))
    upper = min(upper_candidates, key=lambda level: abs(gold.price - level))
    direction = direction_by_level_proximity(gold.price, lower, upper, tolerance)
    buy_rejection = last_candle_rejection(candles, "BUY")
    sell_rejection = last_candle_rejection(candles, "SELL")
    day_range = max((gold.day_high or gold.price) - (gold.day_low or gold.price), 1.0)
    buy_partial = [
        setup_condition("near_lower_pivot", abs(gold.price - lower) <= tolerance, f"Distance support/pivot: {abs(gold.price - lower):.2f}, tolerance {tolerance:.2f}."),
        setup_condition("wick_rejection", buy_rejection, "Meche basse de rejet detectee." if buy_rejection else "Pas de meche basse de rejet."),
        setup_condition("day_range_support", gold.day_low is not None and gold.price <= gold.day_low + max(day_range * 0.25, atr), "Prix proche du bas de range journalier."),
        setup_condition("rsi_room", h1.rsi7 <= 45, f"RSI7 {h1.rsi7:.1f} <= 45."),
    ]
    sell_partial = [
        setup_condition("near_upper_pivot", abs(gold.price - upper) <= tolerance, f"Distance resistance/pivot: {abs(gold.price - upper):.2f}, tolerance {tolerance:.2f}."),
        setup_condition("wick_rejection", sell_rejection, "Meche haute de rejet detectee." if sell_rejection else "Pas de meche haute de rejet."),
        setup_condition("day_range_resistance", gold.day_high is not None and gold.price >= gold.day_high - max(day_range * 0.25, atr), "Prix proche du haut de range journalier."),
        setup_condition("rsi_room", h1.rsi7 >= 55, f"RSI7 {h1.rsi7:.1f} >= 55."),
    ]
    partial_conditions = setup_partial_conditions(buy_partial, sell_partial)
    if direction == "NEUTRAL":
        return no_setup_candidate(
            "PivotRejectionSetup",
            "Prix trop loin des pivots Camarilla/support/resistance pour un rejet exploitable.",
            metadata={"distance_to_lower": round(abs(gold.price - lower), 2), "distance_to_upper": round(abs(gold.price - upper), 2)},
            partial_conditions=partial_conditions,
        )

    conditions: list[str] = ["near_pivot"]
    reasons = [f"Prix proche du pivot {direction}: tolerance {tolerance:.2f}."]
    blockers: list[str] = []
    has_rejection = buy_rejection if direction == "BUY" else sell_rejection
    if has_rejection:
        conditions.append("wick_rejection")
        reasons.append("Derniere bougie rejette le niveau avec une meche nette.")
    if gold.day_low is not None and gold.day_high is not None:
        day_range = max(gold.day_high - gold.day_low, 1.0)
        if direction == "BUY" and gold.price <= gold.day_low + max(day_range * 0.25, atr):
            conditions.append("day_range_support")
        if direction == "SELL" and gold.price >= gold.day_high - max(day_range * 0.25, atr):
            conditions.append("day_range_resistance")
    if direction == "BUY" and h1.rsi7 <= 45:
        conditions.append("rsi_room_for_rebound")
    if direction == "SELL" and h1.rsi7 >= 55:
        conditions.append("rsi_room_for_pullback")
    if not has_rejection:
        blockers.append("Pas encore de bougie de rejet claire.")

    status = candidate_status_from_conditions(len(conditions), blockers, 3, 2)
    trade_levels = build_market_trade_levels(gold, direction, "pivot_rejection", atr, readings=readings, min_rr=1.5)
    confidence = 48 + len(conditions) * 10 + (8 if status == "TRADE_READY" else 0)
    return setup_candidate_from_levels(
        "PivotRejectionSetup",
        status,
        direction,
        confidence,
        len(conditions) * 20,
        conditions,
        trade_levels,
        "all",
        reasons,
        blockers if status != "TRADE_READY" else [],
        cooldown_after_loss_minutes=180,
        cooldown_after_win_minutes=60,
        metadata={"levels": levels, "tolerance": round(tolerance, 2), "session": session},
        partial_conditions=partial_conditions,
    )


def evaluate_mean_reversion_setup(
    gold: SymbolSnapshot,
    readings: list[TechnicalReading],
    chart_store: ChartStore | None,
    now: datetime | None = None,
) -> SetupCandidate:
    session = detect_current_session(now)
    if session == "weekend":
        return no_setup_candidate(
            "MeanReversionSetup",
            "Weekend: marche spot ferme, mean reversion suspendue.",
            metadata={"session": session},
        )
    h1 = reading_for_timeframe(readings, "H1")
    candles = candles_for_timeframe(chart_store, "1H") or candles_for_timeframe(chart_store, "15m")
    if h1 is None:
        return no_setup_candidate("MeanReversionSetup", "Lecture H1 indisponible pour la mean reversion.")

    atr = max(h1.atr14, 3.0)
    extension = abs(gold.price - h1.ema20)
    buy_rejection = last_candle_rejection(candles, "BUY", minimum_wick_share=0.40)
    sell_rejection = last_candle_rejection(candles, "SELL", minimum_wick_share=0.40)
    partial_conditions = setup_partial_conditions(
        [
            setup_condition("rsi_oversold", h1.rsi7 <= 25, f"RSI7 H1 {h1.rsi7:.1f} <= 25."),
            setup_condition("ema20_extension", extension >= atr * 1.25, f"Extension EMA20 {extension:.2f} vs seuil {atr * 1.25:.2f}."),
            setup_condition("rejection_candle", buy_rejection, "Bougie de rejet acheteur detectee."),
            setup_condition("macd_fade_proxy", h1.macd_histogram > -0.6, f"MACD histogramme {h1.macd_histogram:.2f} > -0.60."),
        ],
        [
            setup_condition("rsi_overbought", h1.rsi7 >= 75, f"RSI7 H1 {h1.rsi7:.1f} >= 75."),
            setup_condition("ema20_extension", extension >= atr * 1.25, f"Extension EMA20 {extension:.2f} vs seuil {atr * 1.25:.2f}."),
            setup_condition("rejection_candle", sell_rejection, "Bougie de rejet vendeur detectee."),
            setup_condition("macd_fade_proxy", h1.macd_histogram < 0.6, f"MACD histogramme {h1.macd_histogram:.2f} < 0.60."),
        ],
    )
    direction = "NEUTRAL"
    if h1.rsi7 <= 25:
        direction = "BUY"
    elif h1.rsi7 >= 75:
        direction = "SELL"
    if direction == "NEUTRAL":
        return no_setup_candidate(
            "MeanReversionSetup",
            f"RSI7 H1 {h1.rsi7:.1f}: pas d'extreme mean reversion.",
            partial_conditions=partial_conditions,
        )

    conditions = ["rsi_extreme"]
    reasons = [f"RSI7 H1 {h1.rsi7:.1f} en zone extreme {direction}."]
    if extension >= atr * 1.25:
        conditions.append("ema20_extension")
        reasons.append(f"Ecart au EMA20 H1 {extension:.2f}, soit {extension / atr:.1f} ATR.")
    if (direction == "BUY" and buy_rejection) or (direction == "SELL" and sell_rejection):
        conditions.append("rejection_candle")
    divergence = None
    if len(candles) >= 8:
        closes = [candle.close for candle in candles]
        divergence = detect_rsi_divergence(closes, rsi_series(closes, 7), window=8)
    if divergence and divergence["direction"] == direction:
        conditions.append("rsi_divergence")
        reasons.append("Divergence RSI detectee dans le sens du retour a la moyenne.")
    if (direction == "BUY" and h1.macd_histogram > -0.6) or (direction == "SELL" and h1.macd_histogram < 0.6):
        conditions.append("macd_fade_proxy")

    blockers = [] if len(conditions) >= 3 else ["Mean reversion encore incomplete: attendre rejet/divergence/extension."]
    status = candidate_status_from_conditions(len(conditions), blockers, 3, 2)
    trade_levels = build_market_trade_levels(gold, direction, "mean_reversion", atr, readings=readings, min_rr=1.5)
    return setup_candidate_from_levels(
        "MeanReversionSetup",
        status,
        direction,
        45 + len(conditions) * 11,
        len(conditions) * 18,
        conditions,
        trade_levels,
        "all",
        reasons,
        blockers if status != "TRADE_READY" else [],
        cooldown_after_loss_minutes=360,
        cooldown_after_win_minutes=120,
        metadata={"rsi_h1": round(h1.rsi7, 2), "ema20_extension": round(extension, 2), "session": session},
        partial_conditions=partial_conditions,
    )


def evaluate_range_trading_setup(
    gold: SymbolSnapshot,
    readings: list[TechnicalReading],
    chart_store: ChartStore | None,
    now: datetime | None = None,
) -> SetupCandidate:
    session = detect_current_session(now)
    if session == "weekend":
        return no_setup_candidate(
            "RangeTradingSetup",
            "Weekend: marche spot ferme, range trading suspendu.",
            preferred_session="asian",
            metadata={"session": session},
        )
    h1 = reading_for_timeframe(readings, "H1")
    candles = candles_for_timeframe(chart_store, "1H") or candles_for_timeframe(chart_store, "15m")
    if h1 is None or len(candles) < 12:
        return no_setup_candidate("RangeTradingSetup", "Historique H1/M15 insuffisant pour qualifier un range.")

    low, high, low_touches, high_touches = range_bounds_from_candles(candles)
    range_size = max(high - low, 0.01)
    atr = max(h1.atr14, 3.0)
    tolerance = max(range_size * 0.10, atr * 0.50)
    direction = direction_by_level_proximity(gold.price, low, high, tolerance)
    low_trend = trend_strength_proxy(h1) <= 2.4
    enough_touches = low_touches >= 3 and high_touches >= 3
    buy_rejection = last_candle_rejection(candles, "BUY", minimum_wick_share=0.35)
    sell_rejection = last_candle_rejection(candles, "SELL", minimum_wick_share=0.35)
    partial_conditions = setup_partial_conditions(
        [
            setup_condition("near_lower_range_edge", abs(gold.price - low) <= tolerance, f"Distance bas de range: {abs(gold.price - low):.2f}."),
            setup_condition("low_trend_strength", low_trend, "Force tendance basse compatible range."),
            setup_condition("range_touches", enough_touches, f"Touches bas/haut: {low_touches}/{high_touches}, minimum 3/3."),
            setup_condition("edge_rejection", buy_rejection, "Rejet acheteur sur bord bas detecte."),
            setup_condition("asian_session", session == "asian", f"Session actuelle: {session}."),
        ],
        [
            setup_condition("near_upper_range_edge", abs(gold.price - high) <= tolerance, f"Distance haut de range: {abs(gold.price - high):.2f}."),
            setup_condition("low_trend_strength", low_trend, "Force tendance basse compatible range."),
            setup_condition("range_touches", enough_touches, f"Touches bas/haut: {low_touches}/{high_touches}, minimum 3/3."),
            setup_condition("edge_rejection", sell_rejection, "Rejet vendeur sur bord haut detecte."),
            setup_condition("asian_session", session == "asian", f"Session actuelle: {session}."),
        ],
    )
    if direction == "NEUTRAL":
        return no_setup_candidate(
            "RangeTradingSetup",
            "Prix au milieu du range: pas de bord de range exploitable.",
            preferred_session="asian",
            metadata={"range_low": low, "range_high": high, "tolerance": round(tolerance, 2)},
            partial_conditions=partial_conditions,
        )

    conditions = ["near_range_edge"]
    reasons = [f"Range detecte {low:.2f}/{high:.2f}, prix proche du bord {direction}."]
    blockers: list[str] = []
    if low_trend:
        conditions.append("low_trend_strength")
    else:
        blockers.append("Tendance trop forte: range trading degrade.")
    if enough_touches:
        conditions.append("range_touches")
    if (direction == "BUY" and buy_rejection) or (direction == "SELL" and sell_rejection):
        conditions.append("edge_rejection")
    if session == "asian":
        conditions.append("asian_session")
    status = candidate_status_from_conditions(len(conditions), blockers, 4, 3)
    trade_levels = build_market_trade_levels(gold, direction, "range", atr, readings=readings, min_rr=1.5)
    return setup_candidate_from_levels(
        "RangeTradingSetup",
        status,
        direction,
        42 + len(conditions) * 10,
        len(conditions) * 17,
        conditions,
        trade_levels,
        "asian",
        reasons,
        blockers if status != "TRADE_READY" else [],
        cooldown_after_loss_minutes=180,
        cooldown_after_win_minutes=60,
        metadata={"range_low": low, "range_high": high, "touches": {"low": low_touches, "high": high_touches}},
        partial_conditions=partial_conditions,
    )


def evaluate_trend_continuation_setup(
    gold: SymbolSnapshot,
    readings: list[TechnicalReading],
    chart_store: ChartStore | None,
    event_mode: EventModeAnalysis | None = None,
    now: datetime | None = None,
) -> SetupCandidate:
    session = detect_current_session(now)
    if session == "weekend":
        return no_setup_candidate(
            "TrendContinuationSetup",
            "Weekend: marche spot ferme, continuation de tendance suspendue.",
            preferred_session="london_ny_overlap",
            metadata={"session": session},
        )
    direction = trend_direction_from_readings(readings)
    h1 = reading_for_timeframe(readings, "H1")
    h4 = reading_for_timeframe(readings, "H4")
    d1 = reading_for_timeframe(readings, "D1")
    buy_alignment = sum(1 for reading in readings if reading.timeframe in {"1D", "4H", "1H"} and reading.verdict == "BUY") >= 2
    sell_alignment = sum(1 for reading in readings if reading.timeframe in {"1D", "4H", "1H"} and reading.verdict == "SELL") >= 2
    strength = trend_strength_proxy(h1)
    partial_conditions = setup_partial_conditions(
        [
            setup_condition("multi_timeframe_alignment", buy_alignment, "Au moins 2 timeframes 1D/4H/1H sont BUY."),
            setup_condition("h1_ema_stack", ema_stack_matches(h1, "BUY"), "EMA H1 empilees en tendance BUY."),
            setup_condition("higher_tf_ema_stack", ema_stack_matches(h4, "BUY") or ema_stack_matches(d1, "BUY"), "EMA 4H ou 1D confirme BUY."),
            setup_condition("trend_strength_proxy", strength >= 1.8, f"Force tendance proxy {strength:.2f} >= 1.80."),
            setup_condition("liquid_session", session in {"london_open", "london_morning", "london_ny_overlap", "ny_afternoon"}, f"Session actuelle: {session}."),
        ],
        [
            setup_condition("multi_timeframe_alignment", sell_alignment, "Au moins 2 timeframes 1D/4H/1H sont SELL."),
            setup_condition("h1_ema_stack", ema_stack_matches(h1, "SELL"), "EMA H1 empilees en tendance SELL."),
            setup_condition("higher_tf_ema_stack", ema_stack_matches(h4, "SELL") or ema_stack_matches(d1, "SELL"), "EMA 4H ou 1D confirme SELL."),
            setup_condition("trend_strength_proxy", strength >= 1.8, f"Force tendance proxy {strength:.2f} >= 1.80."),
            setup_condition("liquid_session", session in {"london_open", "london_morning", "london_ny_overlap", "ny_afternoon"}, f"Session actuelle: {session}."),
        ],
    )
    if direction == "NEUTRAL" or h1 is None:
        return no_setup_candidate(
            "TrendContinuationSetup",
            "Alignement 1D/4H/1H insuffisant pour une continuation.",
            partial_conditions=partial_conditions,
        )
    if event_mode is not None and event_mode.active:
        return no_setup_candidate(
            "TrendContinuationSetup",
            "Mode event actif: continuation suspendue avant confirmation post-event.",
            preferred_session="london_ny_overlap",
            metadata={"event_mode": event_mode.status},
            partial_conditions=partial_conditions,
        )

    atr = max(h1.atr14, 3.0)
    conditions = ["multi_timeframe_alignment"]
    reasons = [f"Alignement multi-timeframe {direction}."]
    if ema_stack_matches(h1, direction):
        conditions.append("h1_ema_stack")
    if ema_stack_matches(h4, direction) or ema_stack_matches(d1, direction):
        conditions.append("higher_tf_ema_stack")
    distance_to_pullback = min(abs(gold.price - h1.ema20), abs(gold.price - h1.ema50))
    if distance_to_pullback <= atr * 1.25:
        conditions.append("pullback_to_dynamic_support")
        reasons.append(f"Prix proche EMA20/50 H1 ({distance_to_pullback:.2f}).")
    if strength >= 1.8:
        conditions.append("trend_strength_proxy")
    if session in {"london_open", "london_morning", "london_ny_overlap", "ny_afternoon"}:
        conditions.append("liquid_session")
    blockers = [] if len(conditions) >= 4 else ["Continuation pas assez confirmee: attendre pullback/liquidite/force."]
    status = candidate_status_from_conditions(len(conditions), blockers, 4, 3)
    trade_levels = build_market_trade_levels(gold, direction, "trend_continuation", atr, readings=readings, min_rr=1.5)
    return setup_candidate_from_levels(
        "TrendContinuationSetup",
        status,
        direction,
        45 + len(conditions) * 10,
        len(conditions) * 17,
        conditions,
        trade_levels,
        "london_ny_overlap",
        reasons,
        blockers if status != "TRADE_READY" else [],
        cooldown_after_loss_minutes=240,
        cooldown_after_win_minutes=60,
        metadata={"trend_strength_proxy": strength, "session": session},
        partial_conditions=partial_conditions,
    )


def evaluate_breakout_du_jour_setup(
    gold: SymbolSnapshot,
    readings: list[TechnicalReading],
    chart_store: ChartStore | None,
    now: datetime | None = None,
) -> SetupCandidate:
    session = detect_current_session(now)
    if session == "weekend":
        return no_setup_candidate(
            "BreakoutDuJourSetup",
            "Weekend: marche spot ferme, breakout du jour suspendu.",
            preferred_session="london_open",
            metadata={"session": session},
        )
    m15 = reading_for_timeframe(readings, "M15")
    candles = candles_for_timeframe(chart_store, "15m")
    if m15 is None or len(candles) < 12:
        return no_setup_candidate("BreakoutDuJourSetup", "Donnees M15 insuffisantes pour breakout du jour.", preferred_session="london_open")

    asian_low, asian_high = asian_range_from_candles(candles, now)
    if asian_low == 0.0 and asian_high == 0.0:
        return no_setup_candidate(
            "BreakoutDuJourSetup",
            "Range asiatique indisponible: moins de 4 bougies asiatiques datees aujourd'hui.",
            preferred_session="london_open",
            metadata={"asian_low": asian_low, "asian_high": asian_high, "session": session, "asian_range_valid": False},
            partial_conditions=setup_partial_conditions(
                [setup_condition("asian_range_valid", False, "Moins de 4 bougies asiatiques aujourd'hui.")],
                [setup_condition("asian_range_valid", False, "Moins de 4 bougies asiatiques aujourd'hui.")],
            ),
        )
    last = candles[-1]
    previous = candles[-2] if len(candles) >= 2 else last
    direction = "NEUTRAL"
    if last.close > asian_high and previous.close <= asian_high:
        direction = "BUY"
    elif last.close < asian_low and previous.close >= asian_low:
        direction = "SELL"
    buy_break = last.close > asian_high and previous.close <= asian_high
    sell_break = last.close < asian_low and previous.close >= asian_low
    partial_conditions = setup_partial_conditions(
        [
            setup_condition("asian_range_break", buy_break, f"Cloture M15 {last.close:.2f} > range haut {asian_high:.2f}."),
            setup_condition("volume_expansion", m15.volume_ratio >= 1.5, f"Volume proxy {m15.volume_ratio:.2f} >= 1.50."),
            setup_condition("breakout_session", session in {"london_open", "london_ny_overlap"}, f"Session actuelle: {session}."),
            setup_condition("momentum_confirmed", m15.rsi7 >= 52, f"RSI7 M15 {m15.rsi7:.1f} >= 52."),
        ],
        [
            setup_condition("asian_range_break", sell_break, f"Cloture M15 {last.close:.2f} < range bas {asian_low:.2f}."),
            setup_condition("volume_expansion", m15.volume_ratio >= 1.5, f"Volume proxy {m15.volume_ratio:.2f} >= 1.50."),
            setup_condition("breakout_session", session in {"london_open", "london_ny_overlap"}, f"Session actuelle: {session}."),
            setup_condition("momentum_confirmed", m15.rsi7 <= 48, f"RSI7 M15 {m15.rsi7:.1f} <= 48."),
        ],
    )
    if direction == "NEUTRAL":
        return no_setup_candidate(
            "BreakoutDuJourSetup",
            "Aucune cloture M15 de rupture du range asiatique.",
            preferred_session="london_open",
            metadata={"asian_low": asian_low, "asian_high": asian_high, "session": session},
            partial_conditions=partial_conditions,
        )

    conditions = ["asian_range_break"]
    reasons = [f"Cloture M15 {direction} hors range asiatique {asian_low:.2f}/{asian_high:.2f}."]
    blockers: list[str] = []
    if m15.volume_ratio >= 1.5:
        conditions.append("volume_expansion")
    else:
        blockers.append("Volume proxy insuffisant pour valider la rupture.")
    if session in {"london_open", "london_ny_overlap"}:
        conditions.append("breakout_session")
    else:
        blockers.append("Session peu favorable au breakout du jour.")
    if (direction == "BUY" and m15.rsi7 >= 52) or (direction == "SELL" and m15.rsi7 <= 48):
        conditions.append("momentum_confirmed")
    atr = max(m15.atr14, 3.0)
    trade_levels = build_market_trade_levels(gold, direction, "breakout", atr, readings=readings, min_rr=2.0)
    if trade_levels.risk_reward_tp1 < 2.0:
        blockers.append("R/R TP1 inferieur a 2.0 pour breakout.")
    status = candidate_status_from_conditions(len(conditions), blockers, 3, 2)
    return setup_candidate_from_levels(
        "BreakoutDuJourSetup",
        status,
        direction,
        44 + len(conditions) * 12,
        len(conditions) * 22,
        conditions,
        trade_levels,
        "london_open",
        reasons,
        blockers if status != "TRADE_READY" else [],
        cooldown_after_loss_minutes=240,
        cooldown_after_win_minutes=120,
        metadata={"asian_low": asian_low, "asian_high": asian_high, "session": session},
        partial_conditions=partial_conditions,
    )


def build_strategy_candidates(
    gold: SymbolSnapshot,
    readings: list[TechnicalReading],
    chart_store: ChartStore | None,
    news_reaction_setup: NewsReactionTradePlan | None = None,
    event_mode: EventModeAnalysis | None = None,
    now: datetime | None = None,
) -> list[SetupCandidate]:
    return [
        evaluate_pivot_rejection_setup(gold, readings, chart_store, now=now),
        evaluate_mean_reversion_setup(gold, readings, chart_store, now=now),
        evaluate_range_trading_setup(gold, readings, chart_store, now=now),
        evaluate_trend_continuation_setup(gold, readings, chart_store, event_mode=event_mode, now=now),
        evaluate_breakout_du_jour_setup(gold, readings, chart_store, now=now),
        news_reaction_to_setup_candidate(news_reaction_setup),
    ]


STRATEGY_BASE_PRIORITY = {
    "NewsReactionSetup": 100,
    "TrendContinuationSetup": 82,
    "BreakoutDuJourSetup": 74,
    "RangeTradingSetup": 62,
    "MeanReversionSetup": 54,
    "PivotRejectionSetup": 46,
}


class StrategyCoordinator:
    """Classe les setups Phase 7 sans modifier le verdict final."""

    def __init__(self, min_rr: float = 1.5) -> None:
        self.min_rr = min_rr

    def select(
        self,
        candidates: list[SetupCandidate],
        session: str,
        event_mode: EventModeAnalysis | None = None,
        trade_ledger: TradeLedgerSummary | None = None,
        now: datetime | None = None,
    ) -> StrategySelection:
        reference = now or datetime.now(timezone.utc)
        event_active = bool(event_mode and event_mode.active)
        ranked: list[dict[str, Any]] = []
        rejected: list[dict[str, Any]] = []

        for candidate in candidates:
            score_data = self.score_candidate(candidate, session, event_active, trade_ledger, reference)
            if score_data["eligible"]:
                ranked.append(score_data)
            else:
                rejected.append(score_data)

        ranked.sort(key=lambda item: (item["score"], item["priority"], item["confidence"]), reverse=True)
        if not ranked:
            return StrategySelection(
                status="NO_SETUP_TRADE",
                selected_setup=None,
                selected_score=0,
                session=session,
                event_mode_active=event_active,
                reasons=["Aucune strategie Phase 7 eligible apres priorite, session, R/R et cooldown."],
                ranked_candidates=[],
                rejected_candidates=[self.public_rank(item) for item in rejected],
            )

        winner = ranked[0]
        selected = winner["candidate"]
        status = "TRADE_READY" if selected.status == "TRADE_READY" else "WATCH"
        reasons = [
            f"Setup dominant: {selected.name} {selected.direction} ({winner['score']}/100).",
            f"Priorite {winner['priority']}/100, session {session}, R/R TP1 {selected.rr_tp1:.2f}R.",
        ]
        if event_active:
            reasons.append("Mode event actif: NewsReaction favorisee, continuations mecaniques penalisees.")
        reasons.extend(winner["reasons"][:3])
        public_ranked = [self.public_rank(item) for item in ranked]
        public_rejected = [self.public_rank(item) for item in rejected]
        return StrategySelection(
            status=status,
            selected_setup=selected,
            selected_score=int(winner["score"]),
            session=session,
            event_mode_active=event_active,
            reasons=unique_preserve_order(reasons)[:8],
            ranked_candidates=public_ranked,
            rejected_candidates=public_rejected,
        )

    def score_candidate(
        self,
        candidate: SetupCandidate,
        session: str,
        event_active: bool,
        trade_ledger: TradeLedgerSummary | None,
        reference: datetime,
    ) -> dict[str, Any]:
        priority = STRATEGY_BASE_PRIORITY.get(candidate.name, 30)
        reasons: list[str] = []
        blockers: list[str] = list(candidate.blockers)
        eligible = True

        if candidate.status not in {"TRADE_READY", "WATCH"}:
            eligible = False
            blockers.append(f"Statut {candidate.status}: setup non exploitable.")
        if candidate.direction not in {"BUY", "SELL"}:
            eligible = False
            blockers.append("Direction non exploitable.")
        if session == "weekend" and candidate.name != "NewsReactionSetup":
            eligible = False
            blockers.append("Session weekend: strategie spot suspendue.")
        rr_min = 2.0 if candidate.name == "BreakoutDuJourSetup" else self.min_rr
        if candidate.rr_tp1 < rr_min:
            eligible = False
            blockers.append(f"R/R TP1 {candidate.rr_tp1:.2f}R < minimum {rr_min:.2f}R.")

        cooldown = self.cooldown_reason(candidate, trade_ledger, reference)
        if cooldown:
            eligible = False
            blockers.append(cooldown)

        session_bonus = self.session_bonus(candidate, session)
        status_bonus = 14 if candidate.status == "TRADE_READY" else 2
        rr_bonus = min(12, max(0, (candidate.rr_tp1 - rr_min) * 8))
        event_bonus = 0
        if event_active and candidate.name == "NewsReactionSetup":
            event_bonus = 18
            reasons.append("NewsReaction prioritaire en mode event.")
        elif event_active and candidate.name in {"TrendContinuationSetup", "BreakoutDuJourSetup"}:
            event_bonus = -10
            reasons.append("Mode event: setup directionnel mecanique penalise.")

        raw_score = (
            priority * 0.24
            + candidate.confidence * 0.30
            + candidate.confluence_score * 0.22
            + status_bonus
            + session_bonus
            + rr_bonus
            + event_bonus
            - len(candidate.blockers) * 4
        )
        score = clamp_score(raw_score)
        if session_bonus > 0:
            reasons.append(f"Session compatible: {session}.")
        if candidate.rr_tp1 >= rr_min:
            reasons.append(f"R/R TP1 valide: {candidate.rr_tp1:.2f}R.")
        if candidate.conditions_met:
            reasons.append(f"{len(candidate.conditions_met)} condition(s) validee(s).")

        return {
            "candidate": candidate,
            "name": candidate.name,
            "status": candidate.status,
            "direction": candidate.direction,
            "score": score,
            "priority": priority,
            "confidence": candidate.confidence,
            "confluence_score": candidate.confluence_score,
            "rr_tp1": candidate.rr_tp1,
            "session_bonus": session_bonus,
            "eligible": eligible,
            "reasons": unique_preserve_order(reasons),
            "blockers": unique_preserve_order(blockers),
        }

    def session_bonus(self, candidate: SetupCandidate, session: str) -> int:
        if candidate.name == "NewsReactionSetup":
            return 10
        if candidate.name == "TrendContinuationSetup" and session == "london_ny_overlap":
            return 14
        if candidate.name == "BreakoutDuJourSetup" and session in {"london_open", "london_ny_overlap"}:
            return 14
        if candidate.name == "RangeTradingSetup" and session == "asian":
            return 14
        if candidate.preferred_session in {"all", session}:
            return 8
        return 0

    def cooldown_reason(
        self,
        candidate: SetupCandidate,
        trade_ledger: TradeLedgerSummary | None,
        reference: datetime,
    ) -> str | None:
        if trade_ledger is None:
            return None
        for plan in [*trade_ledger.active_trades, *trade_ledger.recent_trades]:
            if plan.direction != candidate.direction:
                continue
            if not trade_plan_closed(plan):
                return f"Trade {plan.direction} deja actif: nouveau setup bloque."
            closed_reference = parse_iso_datetime(plan.closed_at or plan.updated_at or plan.created_at)
            if closed_reference is None:
                continue
            if plan.outcome == "loss":
                cooldown = candidate.cooldown_after_loss_minutes
            elif plan.outcome == "win":
                cooldown = candidate.cooldown_after_win_minutes
            elif plan.outcome == "expired":
                cooldown = 60
            else:
                cooldown = 90
            elapsed_minutes = (reference - closed_reference).total_seconds() / 60.0
            if 0 <= elapsed_minutes <= cooldown:
                return f"Cooldown {candidate.name}: dernier trade {plan.outcome} il y a {elapsed_minutes:.0f} min, attendre {cooldown} min."
        return None

    @staticmethod
    def public_rank(item: dict[str, Any]) -> dict[str, Any]:
        return {
            "name": item["name"],
            "status": item["status"],
            "direction": item["direction"],
            "score": item["score"],
            "priority": item["priority"],
            "confidence": item["confidence"],
            "confluence_score": item["confluence_score"],
            "rr_tp1": item["rr_tp1"],
            "session_bonus": item["session_bonus"],
            "eligible": item["eligible"],
            "reasons": item["reasons"],
            "blockers": item["blockers"],
        }


def build_strategy_selection(
    candidates: list[SetupCandidate],
    event_mode: EventModeAnalysis | None = None,
    trade_ledger: TradeLedgerSummary | None = None,
    now: datetime | None = None,
    min_rr: float = 1.5,
) -> StrategySelection:
    session = detect_current_session(now)
    return StrategyCoordinator(min_rr=min_rr).select(
        candidates,
        session=session,
        event_mode=event_mode,
        trade_ledger=trade_ledger,
        now=now,
    )


def build_strategy_shadow_integration(
    global_recommendation: TradeRecommendation | None,
    strategy_selection: StrategySelection | None,
) -> StrategyShadowIntegration:
    lead_verdict = global_recommendation.verdict if global_recommendation else "UNAVAILABLE"
    lead_score = global_recommendation.score if global_recommendation else 0
    lead_direction = normalize_scenario_bias(lead_verdict, fallback="WAIT")
    selected = strategy_selection.selected_setup if strategy_selection else None
    strategy_status = strategy_selection.status if strategy_selection else "UNAVAILABLE"
    strategy_setup = selected.name if selected else "none"
    strategy_direction = selected.direction if selected else "NEUTRAL"
    strategy_score = strategy_selection.selected_score if strategy_selection else 0

    blockers = [
        "Phase 7E shadow: le multi-strategy ne modifie pas le chef de file avant calibration Phase 7.5.",
        "Phase 7E shadow: aucun trade lock ne peut etre cree depuis ce signal.",
    ]
    reasons: list[str] = []
    if selected is None:
        alignment = "NO_SETUP"
        status = "SHADOW_NO_SETUP"
        final_action = "LOG_ONLY"
        reasons.append("Aucun setup dominant multi-strategy pour ce snapshot.")
    elif lead_direction in {"BUY", "SELL"} and strategy_direction == lead_direction:
        alignment = "ALIGNED"
        status = "SHADOW_CONFIRMS_LEAD" if strategy_status == "TRADE_READY" else "SHADOW_SUPPORTS_WATCH"
        final_action = "LOG_ONLY_READY_FOR_7_5" if strategy_status == "TRADE_READY" else "LOG_ONLY_WATCH"
        reasons.append(f"Le setup {strategy_setup} confirme le chef de file {lead_direction}.")
    elif lead_direction in {"BUY", "SELL"} and strategy_direction in {"BUY", "SELL"}:
        alignment = "CONFLICT"
        status = "SHADOW_CONFLICT"
        final_action = "LOG_ONLY_CONFLICT"
        reasons.append(f"Le setup {strategy_setup} {strategy_direction} contredit le chef de file {lead_direction}.")
    elif strategy_direction in {"BUY", "SELL"}:
        alignment = "LEAD_NOT_DIRECTIONAL"
        status = "SHADOW_SETUP_WITHOUT_LEAD"
        final_action = "LOG_ONLY_NEEDS_CALIBRATION"
        reasons.append(f"Le multi-strategy voit {strategy_setup} {strategy_direction}, mais le chef de file reste {lead_verdict}.")
    else:
        alignment = "NO_DIRECTION"
        status = "SHADOW_NO_DIRECTION"
        final_action = "LOG_ONLY"
        reasons.append("Ni le chef de file ni le multi-strategy ne donnent une direction exploitable.")

    if strategy_selection and strategy_selection.reasons:
        reasons.extend(strategy_selection.reasons[:3])
    return StrategyShadowIntegration(
        status=status,
        final_action=final_action,
        lead_verdict=lead_verdict,
        lead_score=lead_score,
        strategy_status=strategy_status,
        strategy_setup=strategy_setup,
        strategy_direction=strategy_direction,
        strategy_score=strategy_score,
        alignment=alignment,
        allowed_to_affect_lead=False,
        allowed_to_lock_trade=False,
        reasons=unique_preserve_order(reasons)[:8],
        blockers=blockers,
    )


def append_multi_strategy_history(
    gold: SymbolSnapshot,
    candidates: list[SetupCandidate],
    selection: StrategySelection,
    path: Path = MULTI_STRATEGY_HISTORY_PATH,
    now: datetime | None = None,
) -> None:
    try:
        reference = now or datetime.now(timezone.utc)
        path.parent.mkdir(parents=True, exist_ok=True)
        rotate_jsonl_file(path)
        selected = selection.selected_setup
        row = {
            "timestamp": reference.isoformat(),
            "spot": round(gold.price, 2),
            "session": selection.session,
            "status": selection.status,
            "selected_score": selection.selected_score,
            "selected_setup": selected.name if selected else None,
            "selected_direction": selected.direction if selected else "NEUTRAL",
            "event_mode_active": selection.event_mode_active,
            "candidate_count": len(candidates),
            "ranked_count": len(selection.ranked_candidates),
            "rejected_count": len(selection.rejected_candidates),
            "candidates": [
                {
                    "name": candidate.name,
                    "status": candidate.status,
                    "direction": candidate.direction,
                    "confidence": candidate.confidence,
                    "confluence_score": candidate.confluence_score,
                    "rr_tp1": candidate.rr_tp1,
                    "conditions_met": candidate.conditions_met,
                    "blockers": candidate.blockers,
                }
                for candidate in candidates
            ],
            "reasons": selection.reasons,
        }
        with path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(row, ensure_ascii=True) + "\n")
    except Exception:
        return


def build_news_reaction_trade_plan(
    event: FastNewsEvent,
    reaction: PriceReactionSignal,
    gold: SymbolSnapshot,
    data_quality: DataQualitySnapshot | None = None,
    now: datetime | None = None,
) -> NewsReactionTradePlan:
    reference = now or datetime.now(timezone.utc)
    blockers: list[str] = []
    reasons = list(event.reasons) + list(reaction.checks)
    if is_weekend_market_window(reference):
        blockers.append("Marche spot ferme: signal news conserve en surveillance, pas en trade exploitable.")
    if data_quality is not None and data_quality.preflight and data_quality.preflight.trade_blocked:
        blockers.append("Preflight sources bloque le trade: donnees critiques insuffisantes.")
    if not reaction.confirms:
        blockers.append("La news ne suffit pas: confirmation prix/cross-assets insuffisante.")
    if reaction.fade_trap:
        blockers.append("Fade trap: le prix contredit la direction attendue.")

    entry_low, entry_high, stop_loss, tp1, tp2, tp3 = news_reaction_levels(
        event.direction,
        gold.price,
        reaction.xauusd_change_pct,
    )
    risk = abs(gold.price - stop_loss) or 1.0
    rr1 = abs(tp1 - gold.price) / risk
    rr2 = abs(tp2 - gold.price) / risk
    rr3 = abs(tp3 - gold.price) / risk
    status = "TRADE_READY" if not blockers else "WATCH" if reaction.confirmation_score >= 1 else "NO_TRADE"
    if blockers and any("Marche spot ferme" in blocker or "Preflight" in blocker for blocker in blockers):
        status = "SUSPENDED"
    return NewsReactionTradePlan(
        status=status,
        direction=event.direction if status == "TRADE_READY" else f"WATCH_{event.direction}" if status == "WATCH" else "WAIT",
        event_type=event.event_type,
        title=event.title,
        source=event.source,
        source_url=event.source_url,
        confidence=min(100, max(event.confidence, 50 + reaction.confirmation_score * 12)),
        validity_minutes=event.validity_minutes,
        valid_until=event.valid_until,
        entry_type="NEWS_REACTION",
        reference_price=round(gold.price, 2),
        entry_zone_low=entry_low,
        entry_zone_high=entry_high,
        stop_loss=stop_loss,
        tp1=tp1,
        tp2=tp2,
        tp3=tp3,
        risk_reward_tp1=round(rr1, 2),
        risk_reward_tp2=round(rr2, 2),
        risk_reward_tp3=round(rr3, 2),
        confirmation_score=reaction.confirmation_score,
        latency_seconds=event.latency_seconds,
        created_at=reference.isoformat(),
        event_id=event.event_id,
        reasons=reasons[:8],
        blockers=blockers[:6],
    )


def empty_news_reaction_plan(now: datetime | None = None) -> NewsReactionTradePlan:
    reference = now or datetime.now(timezone.utc)
    return NewsReactionTradePlan(
        status="NO_EVENT",
        direction="WAIT",
        event_type="NO_FAST_EVENT",
        title="Aucune news recente qualifiee",
        source="FastNewsListener",
        source_url="",
        confidence=0,
        validity_minutes=0,
        valid_until=reference.isoformat(),
        entry_type="NEWS_REACTION",
        reference_price=0.0,
        entry_zone_low=0.0,
        entry_zone_high=0.0,
        stop_loss=0.0,
        tp1=0.0,
        tp2=0.0,
        tp3=0.0,
        risk_reward_tp1=0.0,
        risk_reward_tp2=0.0,
        risk_reward_tp3=0.0,
        confirmation_score=0,
        latency_seconds=None,
        created_at=reference.isoformat(),
        event_id="NO_EVENT",
        reasons=["Aucune headline Tier 1-3 recente et directionnelle dans la fenetre 30 minutes."],
        blockers=[],
    )


def build_news_reaction_engine(
    event_facts: list[NewsFact],
    gold: SymbolSnapshot,
    dxy: SymbolSnapshot,
    us10y: SymbolSnapshot,
    cross_asset: CrossAssetAnalysis | None = None,
    data_quality: DataQualitySnapshot | None = None,
    now: datetime | None = None,
) -> NewsReactionTradePlan:
    reference = now or datetime.now(timezone.utc)
    listener = FastNewsListener(max_age_minutes=30)
    events = listener.select_events(event_facts, reference)
    if not events:
        return empty_news_reaction_plan(reference)
    directions = {event.direction for event in events[:3]}
    if len(directions) > 1:
        top = events[0]
        return NewsReactionTradePlan(
            status="SUSPENDED",
            direction="WAIT",
            event_type="MULTI_EVENT_COLLISION",
            title=top.title,
            source=top.source,
            source_url=top.source_url,
            confidence=top.confidence,
            validity_minutes=10,
            valid_until=(reference + timedelta(minutes=10)).isoformat(),
            entry_type="NEWS_REACTION",
            reference_price=round(gold.price, 2),
            entry_zone_low=round(gold.price, 2),
            entry_zone_high=round(gold.price, 2),
            stop_loss=round(gold.price, 2),
            tp1=round(gold.price, 2),
            tp2=round(gold.price, 2),
            tp3=round(gold.price, 2),
            risk_reward_tp1=0.0,
            risk_reward_tp2=0.0,
            risk_reward_tp3=0.0,
            confirmation_score=0,
            latency_seconds=top.latency_seconds,
            created_at=reference.isoformat(),
            event_id=top.event_id,
            reasons=[f"Collision multi-event: directions detectees {', '.join(sorted(directions))}."],
            blockers=["Suspension 10 minutes: plusieurs news recentes donnent des directions opposees."],
        )
    top_event = events[0]
    reaction = detect_news_reaction_price(top_event, gold, dxy, us10y, cross_asset)
    return build_news_reaction_trade_plan(top_event, reaction, gold, data_quality=data_quality, now=reference)


def top_news_titles(news: list[NewsItem], categories: set[str] | None = None, limit: int = 2) -> str:
    selected_categories = {logical_category(category) for category in categories} if categories else None
    selected = [
        clean_display_text(item.title)
        for item in news
        if selected_categories is None or logical_category(item) in selected_categories
    ][:limit]
    return " | ".join(selected) if selected else "aucun titre exploitable"


def sentiment_news_scoring_status(
    news: list[NewsItem],
    now: datetime | None = None,
) -> tuple[bool, str, int]:
    if not news:
        return False, "SentimentNewsAgent neutralise: aucune headline exploitable.", 0
    reference = now or datetime.now(timezone.utc)
    ages: list[float] = []
    tiers: list[int] = []
    for item in news:
        published = parse_iso_datetime(item.published_at)
        if published is not None:
            ages.append(max(0.0, (reference - published).total_seconds() / 60))
        tiers.append(political_source_tier(item))
    median_age = sorted(ages)[len(ages) // 2] if ages else None
    best_tier = min(tiers) if tiers else 4
    if best_tier > 2:
        return False, "SentimentNewsAgent neutralise: aucune source Tier 1-2 recente dans le flux.", 0
    if median_age is None or median_age > 60:
        age_label = "inconnue" if median_age is None else f"{median_age:.0f} min"
        return False, f"SentimentNewsAgent neutralise: age median du flux {age_label} > 60 min.", 0
    return True, f"Flux news scorant: meilleure source Tier {best_tier}, age median {median_age:.0f} min.", 65


def build_passive_agent_results(
    gold: SymbolSnapshot,
    dxy: SymbolSnapshot,
    us10y: SymbolSnapshot,
    news: list[NewsItem],
    analysis: AnalysisResult,
    geopolitical_analysis: GeopoliticalAnalysis | None = None,
    fundamental_recommendation: TradeRecommendation | None = None,
    technical_recommendation: TradeRecommendation | None = None,
    technical_decision: TechnicalDecision | None = None,
    scenario_plan: ScenarioPlan | None = None,
    global_recommendation: TradeRecommendation | None = None,
    technical_timeframes: list[TechnicalReading] | None = None,
    real_yield: SymbolSnapshot | None = None,
    official_macro_rates: OfficialMacroRates | None = None,
    cftc_positioning: CFTCPositioning | None = None,
    etf_flows_analysis: ETFFlowsAnalysis | None = None,
    macro_catalysts: MacroCatalystCalendar | None = None,
    data_quality: DataQualitySnapshot | None = None,
    cross_asset_analysis: CrossAssetAnalysis | None = None,
    event_mode: EventModeAnalysis | None = None,
    weekend_gold: WeekendGoldSnapshot | None = None,
    market_regime: MarketRegimeAnalysis | None = None,
    event_facts: list[EventFact] | None = None,
    political_statements: list[PoliticalStatement] | None = None,
) -> list[AgentResult]:
    readings = technical_timeframes or []
    agents: list[AgentResult] = []
    primary_fact = event_facts[0] if event_facts else None
    data_quality_score = data_quality.score if data_quality else 50
    data_quality_evidence = AgentEvidence(
        "Data quality",
        f"{data_quality.status} {data_quality.score}/100" if data_quality else "indisponible",
        "SourceRegistry",
    )
    data_quality_risks = (
        [
            AgentRisk(
                "Data quality",
                f"Sources critiques faibles: missing={len(data_quality.missing_sources)}, stale={len(data_quality.stale_sources)}.",
                "high" if data_quality.score < 70 else "medium",
            )
        ]
        if data_quality and (data_quality.missing_sources or data_quality.stale_sources or data_quality.score < 70)
        else []
    )

    price_state, price_score, price_reasons = classify_price_action_state(gold)
    price_levels = price_action_levels(gold)
    swing_levels = detect_recent_swing_levels(gold.intraday_points or gold.points)
    range_position = price_range_position(gold)
    psych_level, psych_distance = nearest_psychological_level(gold.price)
    price_risks = []
    if weekend_gold is not None:
        price_risks.append(AgentRisk("Proxy week-end", "IG Weekend Gold reste indicatif et distinct du spot semaine.", "medium"))
    agents.append(
        AgentResult(
            name="PriceActionAgent",
            department="Market",
            bias=score_to_bias(price_score),
            score=price_score,
            confidence=76 if gold.price and gold.day_high > gold.day_low else 55 if gold.price else 35,
            summary=f"PriceActionAgent: etat {price_state}, position range {range_position:.0f}/100, niveau rond {psych_level:.0f} ({psych_distance:+.2f}).",
            evidence=[
                AgentEvidence("Spot XAU/USD", f"{gold.price:.2f} ({gold.change_pct:+.2f}%)", "Investing.com XAU/USD"),
                AgentEvidence(
                    "Niveaux cles",
                    (
                        f"S {price_levels['support']:.2f}, R {price_levels['resistance']:.2f}, "
                        f"Camarilla S3/R3 {price_levels['camarilla_s3']:.2f}/{price_levels['camarilla_r3']:.2f}"
                    ),
                    "PriceAction v4",
                ),
                AgentEvidence("Structure prix", "; ".join(price_reasons[:3]), "PriceAction v4"),
                AgentEvidence("Swing M15", str(swing_levels.get("summary", "indisponible")), "Chart Store OHLC"),
                data_quality_evidence,
            ],
            risks=price_risks,
        )
    )

    technical_score = technical_decision.score if technical_decision else (technical_recommendation.score if technical_recommendation else 50)
    technical_bias = (
        technical_decision.direction
        if technical_decision and technical_decision.direction in {"BUY", "SELL", "WATCH_BUY", "WATCH_SELL", "WAIT"}
        else (technical_recommendation.verdict if technical_recommendation else "NEUTRAL")
    )
    technical_summary = (
        f"TechnicalDecisionEngine: {technical_decision.direction} / {technical_decision.structure}. {technical_decision.trigger}"
        if technical_decision
        else (technical_recommendation.summary if technical_recommendation else "Lecture technique passive indisponible.")
    )
    technical_contradiction_penalty = len(technical_decision.contradictions) * 8 if technical_decision else 0
    technical_trigger_ok = bool(
        technical_decision
        and technical_decision.trigger
        and any(token in technical_decision.trigger.lower() for token in ("m5", "m15", "h1", "cloture", "close", "au-dessus", "sous"))
    )
    technical_confidence = technical_decision.confidence if technical_decision else (70 if readings else 45)
    technical_confidence = min(85, max(0, technical_confidence - technical_contradiction_penalty - (0 if technical_trigger_ok else 12)))
    agents.append(
        AgentResult(
            name="TechnicalAgent",
            department="Technical",
            bias=normalize_agent_bias(technical_bias),
            score=technical_score,
            confidence=technical_confidence,
            summary=technical_summary,
            evidence=[
                AgentEvidence("Timeframes", f"{len(readings)} lectures EMA/RSI/MACD/volume", "GC=F proxy + spot XAU/USD"),
                AgentEvidence("Decision", technical_decision.direction if technical_decision else "n/a", "TechnicalDecisionEngine"),
                AgentEvidence("Raisons", "; ".join((technical_decision.reasons if technical_decision else (technical_recommendation.reasons if technical_recommendation else []))[:3]) or "aucune raison technique"),
            ],
            risks=(
                [AgentRisk("Contradictions", "; ".join(technical_decision.contradictions[:2]), "medium")]
                if technical_decision and technical_decision.contradictions
                else ([] if readings else [AgentRisk("Technique", "Aucune matrice multi-timeframe disponible.", "high")])
            ),
        )
    )

    official_10y = official_macro_rates.dgs10 if official_macro_rates and official_macro_rates.dgs10 else us10y
    macro_score = fundamental_recommendation.score if fundamental_recommendation else clamp_score(50 - dxy.change_pct * 18 - official_10y.change_abs * 600)
    macro_evidence = [
        AgentEvidence("DXY", f"{dxy.price:.2f} ({dxy.change_pct:+.2f}%)", "Yahoo Finance"),
        AgentEvidence("10Y US officiel", f"{official_10y.price:.2f}% ({official_10y.change_abs * 100:+.1f} bps)", "FRED DGS10" if official_macro_rates and official_macro_rates.dgs10 else "Yahoo Finance"),
    ]
    if official_macro_rates and official_macro_rates.dgs2 is not None:
        macro_evidence.append(AgentEvidence("2Y US officiel", f"{official_macro_rates.dgs2.price:.2f}% ({official_macro_rates.dgs2.change_abs * 100:+.1f} bps)", "FRED DGS2"))
    if official_macro_rates and official_macro_rates.dgs3m is not None:
        macro_evidence.append(AgentEvidence("3M US officiel", f"{official_macro_rates.dgs3m.price:.2f}% ({official_macro_rates.dgs3m.change_abs * 100:+.1f} bps)", "FRED DGS3MO"))
    if official_macro_rates and official_macro_rates.dgs30 is not None:
        macro_evidence.append(AgentEvidence("30Y US officiel", f"{official_macro_rates.dgs30.price:.2f}% ({official_macro_rates.dgs30.change_abs * 100:+.1f} bps)", "FRED DGS30"))
    if official_macro_rates and official_macro_rates.t10yie is not None:
        macro_evidence.append(AgentEvidence("Breakeven 10Y", f"{official_macro_rates.t10yie.price:.2f}% ({official_macro_rates.t10yie.change_abs * 100:+.1f} bps)", "FRED T10YIE"))
    if real_yield is not None and len(macro_evidence) < 4:
        macro_evidence.append(AgentEvidence("10Y reel", f"{real_yield.price:.2f}% ({real_yield.change_abs * 100:+.1f} bps)", "FRED DFII10"))
    next_macro = next(
        (event for event in (macro_catalysts.catalysts if macro_catalysts else []) if event.minutes_to_event is None or event.minutes_to_event >= 0),
        None,
    )
    if next_macro is not None:
        macro_evidence.append(
            AgentEvidence(
                "Prochain catalyseur",
                f"{next_macro.title} ({format_macro_countdown(next_macro.minutes_to_event)})",
                next_macro.source_name,
            )
        )
    if macro_catalysts is not None:
        macro_evidence.append(
            AgentEvidence(
                "Densite macro",
                f"{macro_catalysts.density_status}: {macro_catalysts.high_impact_24h} HIGH / 24h; {macro_catalysts.pre_event_summary}",
                "MacroCatalystCalendar",
            )
        )
    macro_freshness_age = headline_age_minutes(
        NewsItem("", "FRED", "", official_10y.fetched_at, "macro", 0, []),
    )
    macro_freshness_penalty = 0 if macro_freshness_age is not None and macro_freshness_age <= 7 * 24 * 60 else 15
    macro_confidence = 78 if official_macro_rates and official_macro_rates.dgs10 else 68 if real_yield is not None else 55
    macro_confidence = max(35, macro_confidence - macro_freshness_penalty)
    macro_evidence.append(
        AgentEvidence(
            "Fraicheur FRED",
            f"{macro_freshness_age/1440:.1f} jour(s)" if macro_freshness_age is not None else "inconnue",
            "FRED DGS10",
        )
    )
    agents.append(
        AgentResult(
            name="MacroAgent",
            department="Macro",
            bias=normalize_agent_bias(fundamental_recommendation.verdict if fundamental_recommendation else score_to_bias(macro_score)),
            score=macro_score,
            confidence=macro_confidence,
            summary=(fundamental_recommendation.summary if fundamental_recommendation else "Lecture macro passive basee sur dollar et taux."),
            evidence=macro_evidence,
            risks=(
                [] if official_macro_rates and official_macro_rates.dgs10 else [AgentRisk("Source taux", "FRED DGS10 indisponible, fallback actif.", "medium")]
            ) + data_quality_risks,
        )
    )

    regime_score = market_regime.score if market_regime else 50
    agents.append(
        AgentResult(
            name="GeopoliticalOilShockAgent",
            department="Geopolitics & Flows",
            bias=geopolitical_agent_bias_from_regime(market_regime),
            score=regime_score,
            confidence=min(88, 52 + round(regime_score * 0.35)) if market_regime else 45,
            summary=market_regime.summary if market_regime else "Regime geopolitique/petrole indisponible.",
            evidence=[
                AgentEvidence("Regime", market_regime.name if market_regime else "indisponible", "Headlines + WTI/Brent"),
                AgentEvidence("Fait detecte", primary_fact.title if primary_fact else "aucun fait structure", primary_fact.source if primary_fact else ""),
                AgentEvidence("Pourquoi", "; ".join((market_regime.reasons if market_regime else [])[:3]) or "aucune raison dominante"),
            ],
            risks=[AgentRisk("Oil shock", "Le regime peut inverser le lien geopolitique -> gold si oil/dollar captent la liquidite.", "high")],
        )
    )

    sentiment_scorable, sentiment_status_reason, sentiment_confidence_floor = sentiment_news_scoring_status(news)
    fresh_news = [item for item in news if is_news_item_exploitable(item)]
    weighted_sentiment = 0.0
    weight_total = 0.0
    for item in fresh_news[:12]:
        tier = news_source_tier(item.source, item.link)
        age = headline_age_minutes(item) or 9999
        tier_weight = {1: 1.4, 2: 1.2, 3: 0.8, 4: 0.4}.get(tier, 0.0)
        freshness_weight = 1.0 if age <= 60 else 0.7 if age <= 360 else 0.35
        weight = tier_weight * freshness_weight
        weighted_sentiment += item.score * weight
        weight_total += weight
    weighted_news_score = weighted_sentiment / weight_total if weight_total else 0.0
    sentiment_score = clamp_score(50 + weighted_news_score * 8) if sentiment_scorable else 50
    sentiment_confidence = max(analysis.confidence, sentiment_confidence_floor, round(min(85, 45 + weight_total * 8))) if sentiment_scorable else 0
    agents.append(
        AgentResult(
            name="SentimentNewsAgent",
            department="Geopolitics & Flows",
            bias=score_to_bias(sentiment_score),
            score=sentiment_score,
            confidence=sentiment_confidence,
            summary=heuristic_decision_sentence(analysis) if sentiment_scorable else sentiment_status_reason,
            evidence=[
                AgentEvidence("Headlines", top_news_titles(news, limit=2), "RSS/Google News"),
                AgentEvidence("Score headlines", f"{weighted_news_score:+.2f} pondere tier/fraicheur" if sentiment_scorable else "neutralise", "News Flow v4"),
                AgentEvidence("Faits structures", str(len(event_facts or [])), "EventFact"),
                data_quality_evidence,
            ],
            risks=[AgentRisk("Bruit news", "Les titres peuvent etre redondants ou en retard sur le prix.", "medium")] + data_quality_risks,
        )
    )

    correlation_score = cross_asset_analysis.score if cross_asset_analysis else 50
    correlation_confirmations = len(cross_asset_analysis.confirmations) if cross_asset_analysis else 0
    correlation_contradictions = len(cross_asset_analysis.contradictions) if cross_asset_analysis else 0
    correlation_evidence = [
        AgentEvidence("Verdict net", f"{correlation_confirmations} confirmation(s) / {correlation_contradictions} contradiction(s)", "CrossAsset v4"),
        AgentEvidence("Confirmations", "; ".join((cross_asset_analysis.confirmations if cross_asset_analysis else [])[:2]) or "aucune confirmation nette"),
        AgentEvidence("Contradictions", "; ".join((cross_asset_analysis.contradictions if cross_asset_analysis else [])[:2]) or "aucune contradiction nette"),
    ]
    if etf_flows_analysis is not None:
        correlation_evidence.append(
            AgentEvidence(
                "ETF flows",
                f"{etf_flows_analysis.status} {format_signed_tonnes(etf_flows_analysis.global_weekly_demand_tonnes)} hebdo",
                etf_flows_analysis.source_name,
            )
        )
    agents.append(
        AgentResult(
            name="CorrelationAgent",
            department="Market",
            bias=normalize_agent_bias(cross_asset_analysis.verdict if cross_asset_analysis else "NEUTRAL"),
            score=correlation_score,
            confidence=min(88, 48 + (correlation_confirmations + correlation_contradictions) * 7) if cross_asset_analysis else 40,
            summary=cross_asset_analysis.summary if cross_asset_analysis else "Confluence inter-marches indisponible.",
            evidence=correlation_evidence,
            risks=[AgentRisk("Correlation", "Une correlation court terme peut casser pendant un regime special.", "medium")],
        )
    )

    flow_components: list[int] = []
    if cftc_positioning is not None:
        flow_components.append(cftc_positioning.score)
    if etf_flows_analysis is not None:
        flow_components.append(etf_flows_analysis.score)
    if not flow_components and geopolitical_analysis is not None:
        flow_components.append(geopolitical_analysis.score)
    flow_score = round(sum(flow_components) / len(flow_components)) if flow_components else 50
    flow_summary_parts = []
    if cftc_positioning is not None:
        flow_summary_parts.append(cftc_positioning.summary)
    if etf_flows_analysis is not None:
        flow_summary_parts.append(etf_flows_analysis.summary)
    flow_summary = " ".join(flow_summary_parts) or (
        geopolitical_analysis.summary if geopolitical_analysis else "Flux et positionnement indisponibles."
    )
    flow_confidence = 88 if cftc_positioning and etf_flows_analysis else 82 if cftc_positioning else 72 if etf_flows_analysis else 55
    flow_evidence = [
        AgentEvidence(
            "Managed Money",
            f"{cftc_positioning.managed_money_net:+,} ({cftc_positioning.managed_money_net_change:+,} hebdo)"
            if cftc_positioning
            else geopolitical_analysis.large_speculators
            if geopolitical_analysis
            else "indisponible",
            "CFTC COT officiel" if cftc_positioning else "News/COT proxy",
        ),
        AgentEvidence(
            "Open interest",
            f"{cftc_positioning.open_interest:,} ({cftc_positioning.open_interest_change:+,} hebdo)"
            if cftc_positioning
            else geopolitical_analysis.comex_open_interest
            if geopolitical_analysis
            else "indisponible",
            "CFTC COT officiel" if cftc_positioning else "News/OI proxy",
        ),
    ]
    flow_risks = [
        AgentRisk(
            "Frequence COT",
            "Le COT officiel est hebdomadaire; les ETF sont plus frequents mais cadrent les flux de fond, pas l'entree intraday.",
            "medium",
        )
    ]
    if cftc_positioning is not None:
        flow_evidence.append(
            AgentEvidence(
                "Producers/Merchants",
                (
                    f"net {cftc_positioning.producer_net:+,} ({cftc_positioning.producer_net_change:+,} hebdo), "
                    f"percentile 1a {cftc_positioning.producer_net_percentile_1y:.0f}/100"
                ),
                "CFTC COT officiel",
            )
        )
        if cftc_positioning.managed_money_percentile_1y >= 90:
            flow_risks.append(AgentRisk("Crowding Managed Money", "Managed Money dans le top 10% annuel: risque de retournement/prise de profit.", "medium"))
        if cftc_positioning.producer_net_percentile_1y <= 10:
            flow_risks.append(AgentRisk("Hedgers extremes", "Producers/Merchants tres vendeurs nets: signal de prudence contrarienne.", "medium"))
    if etf_flows_analysis is not None:
        flow_evidence.append(
            AgentEvidence(
                "ETF officiels",
                f"{etf_flows_analysis.status}: {format_signed_tonnes(etf_flows_analysis.global_weekly_demand_tonnes)} hebdo / {format_signed_tonnes(etf_flows_analysis.global_monthly_demand_tonnes)} mensuel",
                etf_flows_analysis.source_name,
            )
        )
    if cftc_positioning is not None and etf_flows_analysis is not None:
        cot_side = "BUY" if cftc_positioning.score >= 56 else "SELL" if cftc_positioning.score <= 44 else "NEUTRAL"
        etf_side = "BUY" if etf_flows_analysis.score >= 56 else "SELL" if etf_flows_analysis.score <= 44 else "NEUTRAL"
        flow_evidence.append(AgentEvidence("Divergence COT/ETF", f"COT {cot_side}, ETF {etf_side}", "CFTC + WGC"))
        if cot_side != "NEUTRAL" and etf_side != "NEUTRAL" and cot_side != etf_side:
            flow_risks.append(AgentRisk("Divergence COT/ETF", "Les specs futures et les ETF ne valident pas la meme direction.", "high"))
    agents.append(
        AgentResult(
            name="FlowPositioningAgent",
            department="Geopolitics & Flows",
            bias=score_to_bias(flow_score),
            score=flow_score,
            confidence=flow_confidence,
            summary=flow_summary,
            evidence=flow_evidence,
            risks=flow_risks,
        )
    )

    qualified_facts = [
        fact
        for fact in (event_facts or [])
        if getattr(fact, "source_tier", 4) <= 2
        and fact.confidence >= 60
        and getattr(fact, "fact_type", "confirmed_fact") not in {"opinion", "rumor"}
    ]
    if qualified_facts:
        fact_weights = [max(1, fact.confidence) for fact in qualified_facts]
        event_score = clamp_score(sum(fact.confidence * weight for fact, weight in zip(qualified_facts, fact_weights)) / sum(fact_weights))
        buy_votes = sum(1 for fact in qualified_facts if event_fact_direction(fact) == "BUY")
        sell_votes = sum(1 for fact in qualified_facts if event_fact_direction(fact) == "SELL")
        event_bias = "BUY" if buy_votes > sell_votes else "SELL" if sell_votes > buy_votes else "CAUTION"
        primary_fact = sorted(
            qualified_facts,
            key=lambda fact: (
                getattr(fact, "source_tier", 4),
                -fact.confidence,
                -getattr(getattr(fact, "market_confirmation", None), "confirmation_score", 0),
            ),
        )[0]
        event_summary = f"{len(qualified_facts)} fait(s) qualifies Tier<=2; source principale: {primary_fact.source}."
        event_confidence = round(sum(fact.confidence for fact in qualified_facts) / len(qualified_facts))
    else:
        event_score = 45
        event_bias = "NEUTRAL"
        event_summary = "Aucun fait qualifie Tier<=2 avec confidence >=60."
        event_confidence = 0
    agents.append(
        AgentResult(
            name="EventFactsAgent",
            department="Geopolitics & Flows",
            bias=event_bias,
            score=event_score,
            confidence=event_confidence,
            summary=event_summary,
            evidence=[
                AgentEvidence("Fait principal", primary_fact.title if primary_fact else "indisponible", primary_fact.source if primary_fact else ""),
                AgentEvidence(
                    "Confirmation",
                    f"{primary_fact.confirmation_level}, marche {getattr(getattr(primary_fact, 'market_confirmation', None), 'confirmation_score', 0)}/4" if primary_fact else "indisponible",
                    "EventFact",
                ),
                AgentEvidence("Chaine marche", primary_fact.market_chain if primary_fact else "indisponible", "EventFact"),
            ],
            risks=[AgentRisk("Filtre v4", "Opinions, rumeurs, sources faibles et faits non recents sont exclus du score.", "medium")],
        )
    )

    political_items = political_statements or []
    trump_news = [item for item in news if text_contains_any(item.title, ("trump", "white house", "president", "tariff", "sanction"))]
    primary_statement = political_items[0] if political_items else None
    political_score = (
        clamp_score(50 + (primary_statement.score * 8) + (primary_statement.confidence - 50) / 4)
        if primary_statement
        else 50
    )
    political_bias = score_to_bias(political_score) if primary_statement else "NEUTRAL"
    if primary_statement and primary_statement.theme in {"iran_hormuz_oil", "tariffs_trade"} and primary_statement.score <= 0:
        political_bias = "SELL"
    elif primary_statement and primary_statement.theme == "fed_pressure" and primary_statement.score >= 0:
        political_bias = "BUY"
    agents.append(
        AgentResult(
            name="TrumpPoliticalStatementsAgent",
            department="Geopolitics & Flows",
            bias=political_bias,
            score=political_score,
            confidence=primary_statement.confidence if primary_statement else 0,
            summary=(
                f"Declaration politique sourcee detectee: {primary_statement.theme}; source tier {primary_statement.source_tier}, validation {primary_statement.validation_level}."
                if primary_statement
                else "Declaration politique detectee dans les headlines; impact a confirmer par source primaire."
                if trump_news
                else "Aucune declaration Trump/politique exploitable detectee dans les donnees actuelles."
            ),
            evidence=[
                AgentEvidence(
                    "Declaration principale",
                    primary_statement.title if primary_statement else top_news_titles(trump_news, limit=2),
                    primary_statement.source if primary_statement else "Headlines actuelles",
                ),
                AgentEvidence(
                    "Validation",
                    primary_statement.validation_level if primary_statement else "a confirmer",
                    f"Tier {primary_statement.source_tier}" if primary_statement else "Phase 8",
                ),
                AgentEvidence(
                    "Chaine marche",
                    primary_statement.market_chain if primary_statement else "impact politique a confirmer par source primaire",
                    "PoliticalStatements",
                ),
                AgentEvidence(
                    "Verbal vs action",
                    "Score fort seulement si la declaration est reliee a sanctions, decision officielle, militaire, tarifaire ou reaction oil/DXY.",
                    "PoliticalStatements v4.5",
                ),
            ],
            risks=[
                AgentRisk(
                    "Filtre source",
                    "Les citations non officielles ou non confirmees restent en surveillance et ne declenchent pas seules un trade.",
                    "high",
                )
            ],
        )
    )

    risk_score = global_recommendation.score if global_recommendation else 50
    risk_reasons = []
    if event_mode and event_mode.active:
        risk_reasons.append("Mode event actif")
    if market_regime and market_regime.name != "Normal Macro":
        risk_reasons.append(market_regime.name)
    next_high_macro = next(
        (
            event
            for event in (macro_catalysts.catalysts if macro_catalysts else [])
            if event.impact_level == "HIGH"
            and event.minutes_to_event is not None
            and 0 <= event.minutes_to_event <= 48 * 60
        ),
        None,
    )
    if next_high_macro is not None:
        risk_reasons.append(f"Macro high impact proche: {next_high_macro.event_type}")
    if data_quality and data_quality.score < 70:
        risk_reasons.append(f"Data quality degradee {data_quality.score}/100")
    ledger_plans = load_trade_ledger()
    active_ledger_trades = [plan for plan in ledger_plans if trade_plan_is_active(plan)]
    recent_losses = count_recent_losses(ledger_plans, datetime.now(timezone.utc), 24)
    rr_tp1 = (
        compute_risk_reward(
            global_recommendation.verdict,
            gold.price,
            global_recommendation.stop_loss,
            global_recommendation.take_profit_1,
        )
        if global_recommendation and global_recommendation.verdict in {"BUY", "SELL"}
        else 0.0
    )
    if rr_tp1 and rr_tp1 < 1.5:
        risk_reasons.append(f"RR TP1 insuffisant {rr_tp1:.2f}R")
    if active_ledger_trades:
        risk_reasons.append(f"Exposition active: {len(active_ledger_trades)} trade(s)")
    if recent_losses >= 2:
        risk_reasons.append(f"Drawdown recent: {recent_losses} loss/24h")
    risk_manager_bias = "BLOCK" if recent_losses >= 3 else "CAUTION" if risk_reasons else "OK"
    risk_manager_score = 0 if risk_manager_bias == "BLOCK" else 50 if risk_manager_bias == "CAUTION" else 100
    agents.append(
        AgentResult(
            name="RiskManagerAgent",
            department="Decision",
            bias=risk_manager_bias,
            score=risk_manager_score if global_recommendation else risk_score,
            confidence=82 if ledger_plans else 65,
            summary=(
                f"RiskManager: regime {market_regime.name if market_regime else 'inconnu'}, "
                f"data quality {data_quality.score if data_quality else 0}/100. "
                f"RR TP1 {rr_tp1:.2f}R, exposition {len(active_ledger_trades)}. "
                f"Alertes actives: {', '.join(risk_reasons) if risk_reasons else 'aucune majeure'}."
            ),
            evidence=[
                AgentEvidence("Decision officielle", f"{global_recommendation.verdict} {global_recommendation.score}/100" if global_recommendation else "indisponible", "Scoring actuel"),
                AgentEvidence("R/R TP1", f"{rr_tp1:.2f}R", "Trade levels"),
                AgentEvidence("Exposition ledger", f"{len(active_ledger_trades)} actif(s), {recent_losses} loss/24h", "reports/trade_ledger.jsonl"),
                AgentEvidence("Alertes risque", "; ".join(risk_reasons) if risk_reasons else "aucune alerte majeure", "Event/regime"),
                data_quality_evidence,
            ],
            risks=[AgentRisk("Execution", "La lecture agent ne constitue pas un ordre; elle surveille les risques autour du plan.", "high")] + data_quality_risks,
        )
    )

    return agents


def build_agent_contradictions(agent_results: list[AgentResult]) -> list[str]:
    scorant_agents = [agent for agent in agent_results if agent.status != "OFF"]
    buy_agents = [agent.name for agent in scorant_agents if agent.bias == "BUY"]
    sell_agents = [agent.name for agent in scorant_agents if agent.bias == "SELL"]
    caution_agents = [agent.name for agent in scorant_agents if agent.bias == "CAUTION"]
    contradictions: list[str] = []
    if buy_agents and sell_agents:
        contradictions.append(f"BUY vs SELL: {', '.join(buy_agents[:3])} contre {', '.join(sell_agents[:3])}.")
    if caution_agents:
        contradictions.append(f"Vigilance active: {', '.join(caution_agents[:4])}.")
    weak_confidence = [agent.name for agent in scorant_agents if agent.confidence < 45]
    if weak_confidence:
        contradictions.append(f"Confiance faible: {', '.join(weak_confidence[:4])}.")
    return contradictions


def agent_by_name(agent_results: list[AgentResult], name: str) -> AgentResult | None:
    return next((agent for agent in agent_results if agent.name == name), None)


def agent_bullish_score(agent: AgentResult | None, direct_score: bool = False) -> int:
    if agent is None:
        return 50
    if agent.status == "OFF":
        return 50
    if direct_score:
        return clamp_score(agent.score)
    if agent.bias == "BUY":
        return clamp_score(agent.score)
    if agent.bias == "SELL":
        return clamp_score(100 - agent.score)
    return 50


def apply_user_settings_to_agents(agent_results: list[AgentResult], settings: UserSettings | None) -> list[AgentResult]:
    active_names = set((settings or default_user_settings()).active_agents)
    updated: list[AgentResult] = []
    for agent in agent_results:
        if agent.name in active_names:
            updated.append(agent)
            continue
        updated.append(
            AgentResult(
                name=agent.name,
                department=agent.department,
                bias="OFF",
                score=50,
                confidence=0,
                summary="Agent desactive dans les reglages locaux; il ne participe pas au scoring actif.",
                evidence=agent.evidence[:2],
                risks=[],
                status="OFF",
                experimental=agent.experimental,
            )
        )
    return updated


def component_bias(score: int) -> str:
    return score_to_bias(score, buy_threshold=56, sell_threshold=44)


def build_agent_component(
    key: str,
    label: str,
    agent: AgentResult | None,
    weight: float,
    direct_score: bool = False,
    weight_reason: str = "Poids de base.",
) -> OrchestratorComponent:
    score = agent_bullish_score(agent, direct_score=direct_score)
    source = agent.name if agent else "indisponible"
    reason = agent.summary if agent else f"{label} indisponible; score neutre applique."
    confidence = agent.confidence if agent else 35
    return OrchestratorComponent(
        key=key,
        label=label,
        score=score,
        bias=component_bias(score),
        weight=weight,
        contribution=round(score * weight, 2),
        confidence=confidence,
        source=source,
        reason=reason,
        weight_reason=weight_reason,
    )


def normalize_orchestrator_weights(weights: dict[str, float], target_total: float = 1.0) -> dict[str, float]:
    cleaned = {key: max(0.02, value) for key, value in weights.items()}
    total = sum(cleaned.values()) or target_total
    return {key: round((value / total) * target_total, 4) for key, value in cleaned.items()}


def build_dynamic_orchestrator_weights(
    technical_agent: AgentResult | None,
    data_quality: DataQualitySnapshot | None,
    market_regime: MarketRegimeAnalysis | None,
    event_mode: EventModeAnalysis | None,
) -> tuple[dict[str, float], dict[str, list[str]]]:
    weights = {
        "technical": 0.18,
        "macro": 0.18,
        "geopolitical_oil": 0.14,
        "cross_assets": 0.12,
        "flows": 0.10,
        "regime": 0.10,
        "data_quality": 0.08,
    }
    reasons: dict[str, list[str]] = {key: [] for key in weights}

    def adjust(key: str, delta: float, reason: str) -> None:
        weights[key] = weights.get(key, 0.0) + delta
        reasons.setdefault(key, []).append(reason)

    regime_name = market_regime.name if market_regime else "Normal Macro"
    regime_status = market_regime.status if market_regime else "NORMAL"
    is_geopolitical_regime = regime_name != "Normal Macro" or regime_status == "ACTIF"

    if not is_geopolitical_regime:
        adjust("technical", 0.03, "Regime normal: technique plus importante.")
        adjust("macro", 0.03, "Regime normal: macro plus importante.")
        adjust("geopolitical_oil", -0.02, "Regime normal: geopolitique/oil reduit.")
        adjust("regime", -0.01, "Regime normal: regime moins dominant.")
    else:
        adjust("geopolitical_oil", 0.06, "Regime geopolitique: oil/geopolitics prioritaire.")
        adjust("regime", 0.04, "Regime geopolitique: contexte regime prioritaire.")
        adjust("flows", 0.02, "Regime geopolitique: flux/positionnement surveilles.")
        adjust("macro", -0.02, "Regime geopolitique: macro reduite face au risque event.")
        adjust("technical", -0.01, "Regime geopolitique: technique confirmera, mais ne domine pas seule.")
        if regime_name == "Hormuz / Oil Shock":
            adjust("geopolitical_oil", 0.03, "Hormuz/Oil Shock: oil shock prioritaire.")
            adjust("regime", 0.02, "Hormuz/Oil Shock: regime decisionnel augmente.")
        if market_regime is not None and market_regime.confirmed:
            adjust("regime", 0.04, "Regime confirme par persistance/probabilite: poids regime augmente.")
        if regime_name == "Stagflation Fear":
            adjust("macro", 0.03, "Stagflation Fear: macro/taux/inflation prioritaire.")
            adjust("geopolitical_oil", 0.02, "Stagflation Fear: energie et stress prix surveilles.")
        if regime_name == "Risk-On / Carry Trade":
            adjust("cross_assets", 0.03, "Risk-On/Carry: cross-assets prioritaire.")

    if data_quality is None:
        adjust("data_quality", 0.04, "Data quality indisponible: poids gouvernance augmente.")
        adjust("flows", -0.02, "Sources degradees: flows reduits.")
        adjust("cross_assets", -0.02, "Sources degradees: cross-assets reduits.")
    elif data_quality.preflight and data_quality.preflight.trade_blocked:
        adjust("data_quality", 0.06, f"Preflight bloquant {data_quality.preflight.status}: gouvernance prioritaire.")
        adjust("technical", -0.03, "Preflight bloquant: technique reduite.")
        adjust("flows", -0.03, "Preflight bloquant: flows reduits.")
        adjust("cross_assets", -0.02, "Preflight bloquant: cross-assets reduits.")
    elif data_quality.score < 70:
        adjust("data_quality", 0.03, f"Data quality degradee {data_quality.score}/100: gouvernance augmente.")
        adjust("flows", -0.02, "Source degradee: flows reduits.")
        adjust("cross_assets", -0.02, "Source degradee: cross-assets reduits.")
        adjust("geopolitical_oil", -0.01, "Source degradee: geopolitique/oil reduit.")

    if event_mode is not None and event_mode.active:
        adjust("regime", 0.02, "Mode event actif: regime execution augmente.")
        adjust("technical", -0.01, "Mode event actif: technique reduite tant que volatilite instable.")

    if technical_agent is None:
        adjust("technical", -0.04, "TechnicalDecisionEngine indisponible: poids technique reduit.")
    elif technical_agent.bias in {"BUY", "SELL"} and technical_agent.score >= 66 and technical_agent.confidence >= 62:
        adjust("technical", 0.06, "Structure technique confirmee: poids technique augmente.")
    elif technical_agent.bias in {"CAUTION", "NEUTRAL"} or technical_agent.score < 58 or technical_agent.confidence < 55:
        adjust("technical", -0.05, "Structure technique contradictoire ou faible: poids technique reduit.")

    for key in reasons:
        if not reasons[key]:
            reasons[key].append("Poids de base conserve.")

    return normalize_orchestrator_weights(weights), reasons


def regime_directional_score(market_regime: MarketRegimeAnalysis | None) -> tuple[int, str, str]:
    if market_regime is None:
        return 50, "NEUTRAL", "Regime indisponible; score neutre."
    if market_regime.name == "Safe-Haven Gold":
        score = clamp_score(50 + market_regime.score * 0.35)
    elif market_regime.name in {"Hormuz / Oil Shock", "Dollar Liquidity Squeeze"}:
        score = clamp_score(50 - market_regime.score * 0.35)
    elif market_regime.name == "Risk-On / Carry Trade":
        score = clamp_score(50 - market_regime.score * 0.25)
    elif market_regime.name == "Stagflation Fear":
        score = clamp_score(50 + market_regime.score * 0.25)
    elif market_regime.name == "De-escalation / Oil Relief":
        score = clamp_score(50 - market_regime.score * 0.18)
    else:
        score = 50
    return score, component_bias(score), market_regime.summary


def build_regime_component(
    market_regime: MarketRegimeAnalysis | None,
    event_mode: EventModeAnalysis | None,
    weight: float,
    weight_reason: str = "Poids de base.",
) -> OrchestratorComponent:
    score, bias, reason = regime_directional_score(market_regime)
    if event_mode is not None and event_mode.active:
        reason = f"{reason} Mode event actif: le regime impose un risque execution renforce."
    return OrchestratorComponent(
        key="regime",
        label="Regime",
        score=score,
        bias=bias,
        weight=weight,
        contribution=round(score * weight, 2),
        confidence=70 if market_regime else 40,
        source=market_regime.name if market_regime else "RegimeContext",
        reason=reason,
        weight_reason=weight_reason,
    )


def build_data_quality_component(
    data_quality: DataQualitySnapshot | None,
    weight: float,
    weight_reason: str = "Poids de base.",
) -> OrchestratorComponent:
    quality_score = data_quality.score if data_quality else 50
    return OrchestratorComponent(
        key="data_quality",
        label="Data quality",
        score=quality_score,
        bias="OK" if quality_score >= 75 else "CAUTION" if quality_score < 70 else "NEUTRAL",
        weight=weight,
        contribution=round(50 * weight, 2),
        confidence=quality_score,
        source="SourceRegistry",
        reason=data_quality.summary if data_quality else "Data quality indisponible; score neutre.",
        weight_reason=weight_reason,
    )


def summarize_trade_history_calibration(ledger_path: Path = TRADE_LEDGER_PATH) -> tuple[list[str], list[str]]:
    plans = load_trade_ledger(ledger_path)
    closed = [plan for plan in plans if plan.outcome in {"win", "loss", "partial", "expired", "invalidated"}]
    if not closed:
        return [], ["Historique Trade Ledger encore insuffisant pour calibrer les poids."]
    wins = sum(1 for plan in closed if plan.outcome == "win")
    losses = sum(1 for plan in closed if plan.outcome == "loss")
    partials = sum(1 for plan in closed if plan.outcome == "partial")
    if wins >= losses:
        return [f"Calibration ledger: {wins} win(s), {losses} loss(es), {partials} partial(s)."], []
    return [], [f"Calibration ledger prudente: {losses} perte(s) contre {wins} win(s)."]


def estimate_orchestrator_risk_reward(
    gold: SymbolSnapshot,
    verdict: str,
    legacy_recommendation: TradeRecommendation,
    technical_decision: TechnicalDecision | None,
) -> tuple[float, str]:
    direction = "BUY" if "BUY" in verdict else "SELL" if "SELL" in verdict else "WAIT"
    if direction == "WAIT":
        return 0.0, "Pas de direction: risk/reward non evalue."
    if technical_decision is not None and direction in technical_decision.direction:
        stop_loss = technical_decision.stop_loss
        tp1 = technical_decision.tp1
        source = "TechnicalDecisionEngine"
    else:
        stop_loss = legacy_recommendation.stop_loss
        tp1 = legacy_recommendation.take_profit_1
        source = "Legacy global levels"
    risk = abs(gold.price - stop_loss)
    reward = abs(tp1 - gold.price)
    if risk <= 0.01:
        return 0.0, f"Risk/reward invalide depuis {source}: stop confondu avec le prix."
    return reward / risk, f"Risk/reward TP1 {reward / risk:.2f} depuis {source}."


def build_orchestrator_quality_gate(
    verdict: str,
    score: int,
    gold: SymbolSnapshot,
    legacy_recommendation: TradeRecommendation,
    components: list[OrchestratorComponent],
    contradictions: list[str],
    data_quality: DataQualitySnapshot | None,
    event_mode: EventModeAnalysis | None,
    market_regime: MarketRegimeAnalysis | None,
    technical_decision: TechnicalDecision | None = None,
) -> tuple[str, list[str]]:
    hard_reasons: list[str] = []
    advisory_reasons: list[str] = []
    trade_blockers: list[str] = []
    directional_components = [component for component in components if component.key != "data_quality" and component.weight > 0]
    strong_buy = [component.label for component in directional_components if component.score >= 62]
    strong_sell = [component.label for component in directional_components if component.score <= 38]
    direction = "BUY" if verdict == "BUY" else "SELL" if verdict == "SELL" else "WAIT"
    supporting_components = [
        component
        for component in directional_components
        if (direction == "BUY" and component.score >= 56)
        or (direction == "SELL" and component.score <= 44)
    ]
    opposing_components = [
        component
        for component in directional_components
        if (direction == "BUY" and component.score <= 44)
        or (direction == "SELL" and component.score >= 56)
    ]
    if strong_buy and strong_sell:
        hard_reasons.append(f"Contradiction forte: {', '.join(strong_buy[:3])} contre {', '.join(strong_sell[:3])}.")
    directional_contradictions = [item for item in contradictions if item.startswith("BUY vs SELL")]
    if directional_contradictions:
        advisory_reasons.extend(directional_contradictions[:2])
    if len(directional_contradictions) >= 2:
        hard_reasons.append("Contradictions directionnelles multiples: WAIT force avant trade.")
    if data_quality is None:
        hard_reasons.append("Data quality indisponible: NO_TRADE.")
    elif data_quality.preflight and data_quality.preflight.trade_blocked:
        hard_reasons.append(f"Preflight bloquant: {data_quality.preflight.status}.")
    elif data_quality.score < 60:
        hard_reasons.append(f"Data quality trop faible: {data_quality.score}/100 < 60.")
    elif data_quality.score < 68:
        trade_blockers.append(f"Source quality limitee: {data_quality.score}/100; trade bloque mais setup surveillable.")
    if event_mode is not None and event_mode.active:
        if event_mode.score >= 75:
            trade_blockers.append(f"Mode event extreme ({event_mode.score}/100): pas de TRADE_* automatique.")
        else:
            advisory_reasons.append(f"Mode event surveille ({event_mode.score}/100): confirmation d'entree exigee.")
    regime_block = regime_direction_contradiction(market_regime, direction)
    if regime_block:
        trade_blockers.append(regime_block)
    if market_regime is not None and market_regime.name == "Hormuz / Oil Shock":
        if market_regime.score >= 70:
            trade_blockers.append("Regime geopolitique/petrole >= 70/100: setup seulement, pas de TRADE_* automatique.")
        elif market_regime.score >= 60:
            advisory_reasons.append("Regime geopolitique/petrole surveille: reduire confiance et taille.")
        if direction == "BUY":
            trade_blockers.append("BUY contraire au regime petrole/dollar actif.")
    elif market_regime is not None and market_regime.name == "Safe-Haven Gold" and direction == "SELL":
        trade_blockers.append("SELL contraire au regime refuge gold actif.")
    if verdict in {"BUY", "SELL"} and score < 65:
        trade_blockers.append(f"Score orchestrateur insuffisant pour TRADE_*: {score}/100 < 65.")
    elif verdict in {"BUY", "SELL"} and score < 68:
        advisory_reasons.append(f"Score orchestrateur agressif: {score}/100; validation maintenue seulement avec confirmations.")
    if direction in {"BUY", "SELL"} and len(supporting_components) < 3:
        trade_blockers.append("Confirmation insuffisante: moins de trois composants decisionnels soutiennent la direction.")
    if technical_decision is None:
        trade_blockers.append("TechnicalDecisionEngine absent: pas de trigger/invalidation exploitable.")
    elif direction in {"BUY", "SELL"}:
        has_invalidation = bool(technical_decision.invalidation.strip()) and abs(technical_decision.stop_loss - gold.price) > 0.01
        if direction not in technical_decision.direction:
            trade_blockers.append(f"Technique ne confirme pas {direction}: {technical_decision.direction}.")
        if not has_invalidation:
            trade_blockers.append("Setup sans invalidation technique claire.")
    rr, rr_reason = estimate_orchestrator_risk_reward(gold, verdict, legacy_recommendation, technical_decision)
    if direction in {"BUY", "SELL"}:
        if rr < 1.50:
            trade_blockers.append(f"Risk/reward minimum non atteint: {rr:.2f} < 1.50.")
        elif rr < 1.65:
            advisory_reasons.append(f"Risk/reward agressif: {rr:.2f}; trade plus petit ou TP2 necessaire.")
        else:
            advisory_reasons.append(rr_reason)
    if verdict == "WAIT":
        hard_reasons.append("Zone centrale: aucune direction n'a assez d'avantage.")
    if hard_reasons:
        status = "NO_TRADE" if any("Preflight bloquant" in reason or "Data quality" in reason for reason in hard_reasons) else "WAIT"
        return status, unique_preserve_order([*hard_reasons, *advisory_reasons])[:7]
    if verdict == "BUY":
        status = "WATCH_BUY" if trade_blockers else "TRADE_BUY"
    elif verdict == "SELL":
        status = "WATCH_SELL" if trade_blockers else "TRADE_SELL"
    else:
        status = "WAIT"
    if trade_blockers:
        return status, unique_preserve_order([*trade_blockers, *advisory_reasons, "Quality Gate v3: setup surveille, pas de trade verrouille."])[:7]
    return status, unique_preserve_order([*advisory_reasons, "Quality Gate v3 valide: trigger, sources, confirmations et risk/reward autorisent TRADE_*."])[:7]


def build_orchestrator_decision(
    gold: SymbolSnapshot,
    legacy_recommendation: TradeRecommendation,
    agent_results: list[AgentResult],
    data_quality: DataQualitySnapshot | None = None,
    market_regime: MarketRegimeAnalysis | None = None,
    event_mode: EventModeAnalysis | None = None,
    technical_decision: TechnicalDecision | None = None,
) -> tuple[TradeRecommendation, OrchestratorDecision]:
    technical = agent_by_name(agent_results, "TechnicalAgent")
    macro = agent_by_name(agent_results, "MacroAgent")
    geopolitical = agent_by_name(agent_results, "GeopoliticalOilShockAgent")
    cross_assets = agent_by_name(agent_results, "CorrelationAgent")
    flows = agent_by_name(agent_results, "FlowPositioningAgent")
    weights, weight_reasons = build_dynamic_orchestrator_weights(
        technical,
        data_quality,
        market_regime,
        event_mode,
    )

    def weight_reason(key: str) -> str:
        return " ".join(weight_reasons.get(key, ["Poids de base conserve."]))

    components = [
        build_agent_component("technical", "Technique", technical, weights["technical"], weight_reason=weight_reason("technical")),
        build_agent_component("macro", "Macro", macro, weights["macro"], weight_reason=weight_reason("macro")),
        build_agent_component("geopolitical_oil", "Geopolitique/Oil", geopolitical, weights["geopolitical_oil"], weight_reason=weight_reason("geopolitical_oil")),
        build_agent_component("cross_assets", "Cross-assets", cross_assets, weights["cross_assets"], direct_score=True, weight_reason=weight_reason("cross_assets")),
        build_agent_component("flows", "Flows", flows, weights["flows"], direct_score=True, weight_reason=weight_reason("flows")),
        build_regime_component(market_regime, event_mode, weights["regime"], weight_reason=weight_reason("regime")),
        build_data_quality_component(data_quality, weights["data_quality"], weight_reason=weight_reason("data_quality")),
    ]
    total_weight = sum(component.weight for component in components)
    bullish_score = round(sum(component.contribution for component in components) / total_weight, 2)
    if bullish_score >= 54:
        verdict = "BUY"
        conviction = bullish_score
    elif bullish_score <= 46:
        verdict = "SELL"
        conviction = 100 - bullish_score
    else:
        verdict = "WAIT"
        conviction = 50 + abs(bullish_score - 50)
    score = clamp_score(50 + (abs(bullish_score - 50) * 1.55))

    contradictions = build_agent_contradictions(agent_results)
    gate_status, gate_reasons = build_orchestrator_quality_gate(
        verdict,
        score,
        gold,
        legacy_recommendation,
        components,
        contradictions,
        data_quality,
        event_mode,
        market_regime,
        technical_decision=technical_decision,
    )
    if gate_status in {"WAIT", "NO_TRADE"}:
        verdict = gate_status
        score = min(score, 59)
    elif gate_status in {"WATCH_BUY", "WATCH_SELL"}:
        verdict = gate_status

    context_direction = (
        "BUY"
        if "BUY" in verdict
        else "SELL"
        if "SELL" in verdict
        else "BUY"
        if bullish_score >= 50
        else "SELL"
    )
    direction_is_buy = context_direction == "BUY"
    supportive = [
        component
        for component in components
        if component.key != "data_quality" and component.weight > 0
        if (component.score >= 55 if direction_is_buy else component.score <= 45)
    ]
    counter = [
        component
        for component in components
        if component.key != "data_quality" and component.weight > 0
        if (component.score <= 45 if direction_is_buy else component.score >= 55)
    ]
    supportive.sort(key=lambda component: abs(component.score - 50), reverse=True)
    counter.sort(key=lambda component: abs(component.score - 50), reverse=True)
    history_reasons, history_counters = summarize_trade_history_calibration()
    top_reasons = [
        f"{component.label}: {component.bias} {component.score}/100 - {component.reason}"
        for component in supportive[:3]
    ] + history_reasons
    counter_reasons = [
        f"{component.label}: {component.bias} {component.score}/100 - {component.reason}"
        for component in counter[:3]
    ] + history_counters

    recommendation_verdict = "BUY" if gate_status == "TRADE_BUY" else "SELL" if gate_status == "TRADE_SELL" else verdict
    level_direction = (
        "BUY"
        if "BUY" in recommendation_verdict
        else "SELL"
        if "SELL" in recommendation_verdict
        else legacy_recommendation.verdict
    )
    if level_direction in {"BUY", "SELL"}:
        orchestrator_levels = build_market_trade_levels(
            gold,
            level_direction,
            "trend_continuation" if gate_status.startswith("TRADE_") else "pivot_rejection",
            atr=max(abs(legacy_recommendation.take_profit_1 - gold.price), 6.0),
            min_rr=1.5,
            event_mode=event_mode,
        )
        stop_loss, tp1, tp2 = orchestrator_levels.stop_loss, orchestrator_levels.tp1, orchestrator_levels.tp2
        top_reasons.append(
            f"Niveaux v4: {orchestrator_levels.setup_type}, R/R TP1 {orchestrator_levels.risk_reward_tp1:.2f}R, sorties 50/30/20."
        )
    else:
        stop_loss, tp1, tp2 = legacy_recommendation.stop_loss, legacy_recommendation.take_profit_1, legacy_recommendation.take_profit_2

    display_verdict = recommendation_verdict if recommendation_verdict in {"BUY", "SELL"} else verdict
    summary = (
        f"Orchestrateur v3 {gate_status}: score pondere {bullish_score:.1f}/100, "
        f"reference initiale {legacy_recommendation.verdict} {legacy_recommendation.score}/100. "
        + ("Trade exploitable." if gate_status.startswith("TRADE_") else "Setup surveille." if gate_status.startswith("WATCH_") else "Pas de trade.")
    )
    recommendation = TradeRecommendation(
        mode="Global v3",
        verdict=display_verdict,
        score=score,
        summary=summary,
        reasons=(top_reasons[:3] + [f"Contre-signal: {item}" for item in counter_reasons[:3]] + gate_reasons)[:8],
        stop_loss=stop_loss,
        take_profit_1=tp1,
        take_profit_2=tp2,
        source_note="Orchestrateur v3: poids dynamiques, SourceRegistry, regime, contradictions, scenario et Quality Gate.",
    )
    decision = OrchestratorDecision(
        verdict=display_verdict,
        score=score,
        status=gate_status,
        engine="orchestrator_v3_dynamic",
        bullish_score=bullish_score,
        legacy_verdict=legacy_recommendation.verdict,
        legacy_score=legacy_recommendation.score,
        top_reasons=top_reasons[:4],
        counter_reasons=counter_reasons[:4],
        contradictions=contradictions[:5],
        quality_gate_reasons=gate_reasons,
        components=components,
    )
    return recommendation, decision


def update_orchestrator_agent(agent_results: list[AgentResult], decision: OrchestratorDecision) -> list[AgentResult]:
    updated: list[AgentResult] = []
    for agent in agent_results:
        if agent.name != "OrchestratorAgent":
            updated.append(agent)
            continue
        updated.append(
            AgentResult(
                name=agent.name,
                department=agent.department,
                bias=normalize_agent_bias(decision.verdict),
                score=decision.score,
                confidence=82 if decision.status.startswith("TRADE_") else 72 if decision.status.startswith("WATCH_") else 64,
                summary=(
                    f"Orchestrateur v3 actif: verdict {decision.verdict} {decision.score}/100; "
                    f"reference initiale {decision.legacy_verdict} {decision.legacy_score}/100."
                ),
                evidence=[
                    AgentEvidence("Moteur", decision.engine, "Phase 29"),
                    AgentEvidence("Score pondere", f"{decision.bullish_score:.1f}/100", "Agents ponderes"),
                    AgentEvidence("Quality Gate", decision.status, "Orchestrator v3"),
                ],
                risks=[AgentRisk("Gate", reason, "high" if decision.status in {"WAIT", "NO_TRADE"} else "medium" if decision.status.startswith("WATCH_") else "low") for reason in decision.quality_gate_reasons[:3]],
                status="ACTIVE",
                experimental=False,
            )
        )
    return updated


def parse_agent_results(entries: list[dict[str, Any]]) -> list[AgentResult]:
    results: list[AgentResult] = []
    for entry in entries:
        evidence = [
            AgentEvidence(
                label=str(item.get("label", "")),
                value=str(item.get("value", "")),
                source=str(item.get("source", "")),
            )
            for item in entry.get("evidence", [])
            if isinstance(item, dict)
        ]
        risks = [
            AgentRisk(
                label=str(item.get("label", "")),
                detail=str(item.get("detail", "")),
                severity=str(item.get("severity", "medium")),
            )
            for item in entry.get("risks", [])
            if isinstance(item, dict)
        ]
        results.append(
            AgentResult(
                name=str(entry.get("name", "UnknownAgent")),
                department=str(entry.get("department", "Decision")),
                bias=str(entry.get("bias", "NEUTRAL")),
                score=int(entry.get("score", 50) or 50),
                confidence=int(entry.get("confidence", 50) or 50),
                summary=str(entry.get("summary", "")),
                evidence=evidence,
                risks=risks,
                status=str(entry.get("status", "PASSIVE")),
                experimental=bool(entry.get("experimental", True)),
            )
        )
    return results


def classify_bias(score: int) -> str:
    if score >= 5:
        return "bullish"
    if score >= 2:
        return "slightly bullish"
    if score <= -5:
        return "bearish"
    if score <= -2:
        return "slightly bearish"
    return "neutral"


def filter_news_by_categories(news: list[NewsItem], categories: set[str]) -> list[NewsItem]:
    selected = {logical_category(category) for category in categories}
    return [item for item in news if logical_category(item) in selected]


def count_keyword_matches(items: list[NewsItem], keywords: set[str]) -> int:
    total = 0
    for item in items:
        text = f"{item.title} {' '.join(item.score_reasons)}".lower()
        if any(keyword_matches(text, keyword) for keyword in keywords):
            total += 1
    return total


def resolve_signal_label(
    positive_hits: int,
    negative_hits: int,
    positive_label: str,
    negative_label: str,
    neutral_label: str,
) -> str:
    if positive_hits > negative_hits and positive_hits > 0:
        return positive_label
    if negative_hits > positive_hits and negative_hits > 0:
        return negative_label
    return neutral_label


def build_geopolitical_analysis(
    news: list[NewsItem],
    cftc_positioning: CFTCPositioning | None = None,
    etf_flows_analysis: ETFFlowsAnalysis | None = None,
) -> GeopoliticalAnalysis:
    risk_items = filter_news_by_categories(news, {"geopolitical", "risk_vix"})
    central_bank_items = filter_news_by_categories(news, {"macro_fed", "macro_cpi", "macro_nfp", "events_fomc"})
    physical_items = filter_news_by_categories(news, {"physical_demand", "gold"})
    spec_items = filter_news_by_categories(news, {"sentiment_cot"})
    etf_items = filter_news_by_categories(news, {"sentiment_etf"})
    open_interest_items = filter_news_by_categories(news, {"sentiment_oi"})
    vix_items = filter_news_by_categories(news, {"risk_vix"})
    event_items = filter_news_by_categories(
        news,
        {"events_calendar", "events_fomc", "macro_fed", "macro_cpi", "macro_nfp", "geopolitical", "risk_vix", "gold"},
    )

    risk_off_pos = count_keyword_matches(risk_items, RISK_OFF_POSITIVE_KEYWORDS)
    risk_off_neg = count_keyword_matches(risk_items, RISK_OFF_NEGATIVE_KEYWORDS)
    central_bank_dovish = count_keyword_matches(central_bank_items, CENTRAL_BANK_DOVISH_KEYWORDS)
    central_bank_hawkish = count_keyword_matches(central_bank_items, CENTRAL_BANK_HAWKISH_KEYWORDS)
    physical_pos = count_keyword_matches(physical_items, PHYSICAL_DEMAND_POSITIVE_KEYWORDS)
    physical_neg = count_keyword_matches(physical_items, PHYSICAL_DEMAND_NEGATIVE_KEYWORDS)
    specs_long = count_keyword_matches(spec_items, SPECULATORS_LONG_KEYWORDS)
    specs_short = count_keyword_matches(spec_items, SPECULATORS_SHORT_KEYWORDS)
    etf_inflows = count_keyword_matches(etf_items, ETF_INFLOW_KEYWORDS)
    etf_outflows = count_keyword_matches(etf_items, ETF_OUTFLOW_KEYWORDS)
    oi_up = count_keyword_matches(open_interest_items, OPEN_INTEREST_UP_KEYWORDS)
    oi_down = count_keyword_matches(open_interest_items, OPEN_INTEREST_DOWN_KEYWORDS)
    vix_risk_off = count_keyword_matches(vix_items, VIX_RISK_OFF_KEYWORDS)
    vix_risk_on = count_keyword_matches(vix_items, VIX_RISK_ON_KEYWORDS)

    risk_off_status = resolve_signal_label(risk_off_pos, risk_off_neg, "actif", "en reflux", "mixte")
    central_bank_bias = resolve_signal_label(
        central_bank_dovish,
        central_bank_hawkish,
        "accommodant",
        "restrictif",
        "mitige",
    )
    physical_demand_trend = resolve_signal_label(
        physical_pos,
        physical_neg,
        "achats en hausse",
        "achats en ralentissement",
        "flux physiques mixtes",
    )
    large_speculators = resolve_signal_label(
        specs_long,
        specs_short,
        "net long",
        "net short",
        "positionnement mixte",
    )
    etf_flows = resolve_signal_label(
        etf_inflows,
        etf_outflows,
        "inflows",
        "outflows",
        "flux mixtes",
    )
    comex_open_interest = resolve_signal_label(
        oi_up,
        oi_down,
        "en hausse",
        "en baisse",
        "sans tendance nette",
    )
    vix_tone = resolve_signal_label(
        vix_risk_off,
        vix_risk_on,
        "risk-off",
        "risk-on",
        "neutre",
    )

    score = 50
    reasons: list[str] = []

    if risk_off_status == "actif":
        score += 14
        reasons.append("Evenement risk-off actif detecte via les headlines geopolitiques ou de stress.")
    elif risk_off_status == "en reflux":
        score -= 8
        reasons.append("Le stress geopol ou bancaire semble plutot se calmer.")
    else:
        reasons.append("Le risque geopol reste present mais sans signal unique de panique durable.")

    if central_bank_bias == "accommodant":
        score += 10
        reasons.append("Le ton des banques centrales ressort plutot accommodant pour l'or.")
    elif central_bank_bias == "restrictif":
        score -= 10
        reasons.append("Le ton des banques centrales ressort plutot restrictif.")
    else:
        reasons.append("Le ton des banques centrales reste mitige.")

    if physical_demand_trend == "achats en hausse":
        score += 8
        reasons.append("La demande physique Chine/Inde/banques centrales parait constructive.")
    elif physical_demand_trend == "achats en ralentissement":
        score -= 8
        reasons.append("La demande physique parait moins porteuse.")
    else:
        reasons.append("La demande physique reste mixte dans les headlines recuperees.")

    if cftc_positioning is None:
        if large_speculators == "net long":
            score += 6
            reasons.append("Les large speculators ressortent plutot net long sur les Gold Futures.")
        elif large_speculators == "net short":
            score -= 6
            reasons.append("Les large speculators ressortent plutot net short.")
        else:
            reasons.append("Le positionnement COT des large speculators reste peu lisible.")

    if etf_flows_analysis is not None:
        etf_flows = (
            f"{etf_flows_analysis.status} "
            f"({format_signed_tonnes(etf_flows_analysis.global_weekly_demand_tonnes)} hebdo, "
            f"{format_signed_tonnes(etf_flows_analysis.global_monthly_demand_tonnes)} mensuel)"
        )
        etf_tilt = round(clamp((etf_flows_analysis.score - 50) / 4, -8, 8))
        score += etf_tilt
        reasons.append(f"ETF officiels {etf_flows_analysis.as_of_date}: {etf_flows_analysis.summary}")
    elif etf_flows == "inflows":
        score += 6
        reasons.append("Les flux ETF GLD/IAU paraissent orientes en entrees.")
    elif etf_flows == "outflows":
        score -= 6
        reasons.append("Les flux ETF GLD/IAU paraissent orientes en sorties.")
    else:
        reasons.append("Les flux ETF restent mixtes.")

    if cftc_positioning is None:
        if comex_open_interest == "en hausse":
            score += 4
            reasons.append("L'open interest COMEX monte, signe d'engagement croissant.")
        elif comex_open_interest == "en baisse":
            score -= 4
            reasons.append("L'open interest COMEX recule, signe possible de de-risking.")
        else:
            reasons.append("L'open interest COMEX ne donne pas encore de direction propre.")

    if cftc_positioning is not None:
        managed_label = (
            "net long"
            if cftc_positioning.managed_money_net > 0
            else "net short"
            if cftc_positioning.managed_money_net < 0
            else "neutre"
        )
        large_speculators = (
            f"Managed Money {managed_label} "
            f"({cftc_positioning.managed_money_net:+,}, {cftc_positioning.managed_money_net_change:+,} hebdo)"
        )
        comex_open_interest = (
            f"{cftc_positioning.open_interest:,} contrats "
            f"({cftc_positioning.open_interest_change:+,} hebdo)"
        )
        cot_tilt = round(clamp((cftc_positioning.score - 50) / 5, -8, 8))
        score += cot_tilt
        reasons.append(f"COT officiel CFTC {cftc_positioning.report_date}: {cftc_positioning.summary}")

    if vix_tone == "risk-off":
        score += 5
        reasons.append("Le VIX/fear gauge penche vers l'aversion au risque.")
    elif vix_tone == "risk-on":
        score -= 5
        reasons.append(
            "Le VIX/fear gauge ne confirme pas un besoin fort de couverture tant qu'il reste sous le seuil 20."
        )
    else:
        reasons.append("Le VIX reste neutre.")

    event_watch = [item.title for item in sorted(event_items, key=lambda item: item.published_at, reverse=True)[:5]]
    score = round(clamp(score, 20, 85))

    if score >= 60:
        summary = (
            "Le cadrage geopolitique et les flux restent plutot porteurs pour l'or: "
            "risk-off present ou latent, ton des banques centrales moins hostile et soutien des flux."
        )
    elif score <= 45:
        summary = (
            "Le cadrage geopolitique et les flux ne soutiennent pas clairement l'or: "
            "stress limite, ton monetaire plus restrictif ou flux moins favorables."
        )
    else:
        summary = (
            "Le cadrage geopolitique reste melange: quelques elements risk-off existent, "
            "mais les flux et la macro ne convergent pas encore assez."
        )

    return GeopoliticalAnalysis(
        score=score,
        summary=summary,
        risk_off_status=risk_off_status,
        central_bank_bias=central_bank_bias,
        physical_demand_trend=physical_demand_trend,
        large_speculators=large_speculators,
        etf_flows=etf_flows,
        comex_open_interest=comex_open_interest,
        vix_tone=vix_tone,
        event_watch=event_watch,
        reasons=reasons[:7],
    )


def analyze_market(
    gold: SymbolSnapshot,
    dxy: SymbolSnapshot,
    us10y: SymbolSnapshot,
    news: list[NewsItem],
    real_yield: SymbolSnapshot | None = None,
    cross_asset: CrossAssetAnalysis | None = None,
    event_mode: EventModeAnalysis | None = None,
    market_regime: MarketRegimeAnalysis | None = None,
    cftc_positioning: CFTCPositioning | None = None,
    etf_flows_analysis: ETFFlowsAnalysis | None = None,
) -> AnalysisResult:
    market_score, market_reasons = build_market_reasons(gold, dxy, us10y)
    if real_yield is not None:
        real_yield_bps = real_yield.change_abs * 100
        if real_yield_bps <= -1:
            market_score += 2
            market_reasons.append(f"Le 10Y reel FRED baisse ({real_yield_bps:+.1f} bps), soutien important pour l'or.")
        elif real_yield_bps >= 1:
            market_score -= 2
            market_reasons.append(f"Le 10Y reel FRED monte ({real_yield_bps:+.1f} bps), frein important pour l'or.")

    if cross_asset is not None:
        if cross_asset.score >= 62:
            market_score += 2
            market_reasons.append("Les confirmations cross-asset valident plutot le contexte haussier de l'or.")
        elif cross_asset.score <= 38:
            market_score -= 2
            market_reasons.append("Les confirmations cross-asset contredisent le contexte haussier de l'or.")

    if event_mode is not None and event_mode.active:
        market_reasons.append("Mode event actif: les signaux directionnels doivent etre geles ou fortement confirmes.")
    if market_regime is not None and market_regime.name == "Hormuz / Oil Shock":
        market_score -= 2
        market_reasons.append("Regime Hormuz/Oil Shock: la tension politique peut peser sur gold si oil/dollar captent la liquidite.")

    category_scores: dict[str, int] = {}
    for item in news:
        category = logical_category(item)
        category_scores[category] = category_scores.get(category, 0) + item.score

    normalized_news_score = sum(clamp(value, -2, 2) for value in category_scores.values())
    news_score = round(clamp(normalized_news_score / 2, -4, 4))
    geopolitical = build_geopolitical_analysis(
        news,
        cftc_positioning=cftc_positioning,
        etf_flows_analysis=etf_flows_analysis,
    )
    if market_regime is not None:
        if market_regime.name == "Hormuz / Oil Shock" and market_regime.score >= 58:
            geopolitical.score = round(clamp(geopolitical.score - 12, 20, 85))
            geopolitical.summary = (
                "Le risque politique est actif, mais le regime Hormuz/Oil Shock change la transmission: "
                "la prime va d'abord vers oil/dollar et peut peser sur gold a court terme."
            )
            geopolitical.reasons.insert(0, market_regime.summary)
        elif market_regime.name == "Safe-Haven Gold":
            geopolitical.score = round(clamp(geopolitical.score + 8, 20, 85))
            geopolitical.reasons.insert(0, market_regime.summary)
    geopolitical_tilt = round(clamp((geopolitical.score - 50) / 12, -3, 3))
    total_score = market_score + news_score + geopolitical_tilt
    bias = classify_bias(total_score)
    confidence = max(35, min(82, 40 + (abs(total_score) * 4) + (3 if geopolitical.event_watch else 0)))
    if event_mode is not None and event_mode.active:
        confidence = min(confidence, 45)

    bullish_news = [item for item in news if item.score > 0]
    bearish_news = [item for item in news if item.score < 0]
    neutral_news = [item for item in news if item.score == 0]

    reasons = market_reasons[:]
    if news_score > 0:
        reasons.append("Le flux de headlines est legerement favorable a l'or.")
    elif news_score < 0:
        reasons.append("Le flux de headlines penche legerement contre l'or.")
    else:
        reasons.append("Les headlines restent mixtes, sans avantage directionnel net.")

    if geopolitical_tilt > 0:
        reasons.append("Le bloc geopolitique/sentiment/flux ajoute un soutien net a l'or.")
    elif geopolitical_tilt < 0:
        reasons.append("Le bloc geopolitique/sentiment/flux ne renforce pas le dossier haussier.")
    else:
        reasons.append("Le bloc geopolitique/sentiment/flux reste equilibre.")

    return AnalysisResult(
        bias=bias,
        score=total_score,
        confidence=confidence,
        reasons=reasons,
        bullish_news=bullish_news,
        bearish_news=bearish_news,
        neutral_news=neutral_news,
        geopolitical=geopolitical,
    )


def format_price_line(snapshot: SymbolSnapshot, suffix: str = "") -> str:
    extra = f" {suffix}".rstrip()
    return (
        f"- {snapshot.label}: {snapshot.price:.2f}{extra} "
        f"({snapshot.change_pct:+.2f}% vs cloture precedente, "
        f"variation courte {snapshot.period_change_pct:+.2f}%)"
    )


def format_yield_line(snapshot: SymbolSnapshot) -> str:
    return (
        f"- {snapshot.label}: {snapshot.price:.2f}% "
        f"({snapshot.change_abs * 100:+.1f} bps vs cloture precedente, "
        f"variation courte {snapshot.period_change_pct:+.2f}%)"
    )


def clean_display_text(value: str) -> str:
    cleaned = compact_whitespace(value)
    if not cleaned:
        return cleaned
    if any(marker in cleaned for marker in ("â", "Ã", "Â")):
        for source_encoding in ("cp1252", "latin-1"):
            try:
                repaired = cleaned.encode(source_encoding, "ignore").decode("utf-8", "ignore")
            except (UnicodeEncodeError, UnicodeDecodeError):
                continue
            if repaired and repaired != cleaned:
                cleaned = repaired
                break
    replacements = {
        "\u2019": "'",
        "\u2018": "'",
        "\u201c": '"',
        "\u201d": '"',
        "\u2013": "-",
        "\u2014": "-",
        "\u2026": "...",
        "\u00b7": "-",
        "\u00a0": " ",
        "\ufffd": "",
    }
    for old, new in replacements.items():
        cleaned = cleaned.replace(old, new)
    return compact_whitespace(cleaned)


def parse_iso_sort_key(iso_text: str) -> datetime:
    try:
        return datetime.fromisoformat(iso_text.replace("Z", "+00:00"))
    except ValueError:
        return datetime.fromtimestamp(0, tz=timezone.utc)


def headline_sort_key(item: NewsItem) -> tuple[int, int, int, int, float]:
    priority = CATEGORY_PRIORITY.get(logical_category(item), 99)
    impact_boost = -abs(item.score)
    newest_first = -parse_iso_sort_key(item.published_at).timestamp()
    breaking_boost = 0 if item.is_breaking else 1
    source_tier = news_source_tier(item.source, item.link)
    return (priority, impact_boost, breaking_boost, source_tier, newest_first)


def text_contains_any(text: str, patterns: tuple[str, ...]) -> bool:
    return any(keyword_matches(text, pattern) for pattern in patterns)


def explain_headline_reason(item: NewsItem) -> str:
    text = normalize_title_for_dedupe(clean_display_text(item.title))

    if text_contains_any(text, ("iran", "middle east", "war", "conflict", "hormuz", "blockade", "shipping", "ports", "oil", "barrel", "fuel", "liquidity")):
        if text_contains_any(text, ("usd", "dollar", "liquidity")):
            return "La guerre pousse les investisseurs a chercher de la liquidite immediate en dollar, pas seulement des refuges comme l'or."
        if text_contains_any(text, ("oil", "barrel", "fuel", "hormuz", "shipping", "ports", "blockade")):
            return "Le marche craint une perturbation durable du petrole, donc plus d'inflation energie et plus de stress global."
        return (
            "Tension geopolitique elargie: aversion au risque mesurable via VIX et flight-to-quality TIP. "
            "Si VIX progresse et TIP est bid, biais refuge or; sinon attendre confirmation oil/DXY."
        )

    if text_contains_any(text, ("fed", "fomc", "powell", "minutes", "rate", "cut", "cuts", "hike", "higher for longer")):
        return "Cette headline change la lecture du marche sur le calendrier des taux de la Fed."

    if text_contains_any(text, ("cpi", "inflation", "gasoline", "prices rise", "price pressures")):
        return "Cette headline dit si l'inflation se calme ou repart, donc si la Fed peut assouplir ou non."

    if text_contains_any(text, ("jobs", "nfp", "nonfarm", "employment", "payroll")):
        return "Le marche de l'emploi influence directement le dollar, les rendements et les attentes de taux."

    if text_contains_any(text, ("cot", "commitments of traders", "managed money", "speculative")):
        return "Le COT montre si les speculateurs sont deja charges a l'achat ou a la vente."

    if text_contains_any(text, ("open interest", "positions build", "liquidation")):
        return "L'open interest dit si le marche construit de nouvelles positions ou s'il se degonfle."

    if text_contains_any(text, ("etf", "gld", "iau", "holdings", "inflows", "outflows")):
        return "Les flux ETF mesurent si les investisseurs financiers renforcent ou reduisent leur exposition a l'or."

    if text_contains_any(text, ("vix", "fear", "volatility", "risk aversion")):
        return "Le VIX aide a savoir si le marche cherche de la protection."

    return "Cette information ajoute du contexte, meme si elle ne suffit pas seule a declencher un trade."


def explain_headline_gold_impact(item: NewsItem) -> tuple[str, str]:
    text = normalize_title_for_dedupe(clean_display_text(item.title))

    if text_contains_any(text, ("iran", "middle east", "war", "conflict", "hormuz", "oil", "barrel", "fuel", "blockade", "shipping", "ports")):
        if text_contains_any(text, ("usd", "dollar", "liquidity")):
            return (
                "mixte",
                "Le risque geopolitique aide l'or comme refuge, mais la demande de dollars liquides peut freiner la hausse a court terme.",
            )
        if text_contains_any(text, ("oil", "barrel", "fuel", "inflation")):
            return (
                "mixte",
                (
                    "Choc petrole: deux effets opposes pour l'or. Effet inflation -> taux reels potentiellement en hausse "
                    "-> negatif court terme. Effet refuge -> bid possible. Trancher via DFII10 et DXY."
                ),
            )
        return (
            "bullish",
            (
                "Aversion geopolitique mesurable: si VIX progresse et flight-to-quality TIP confirme, "
                "demande de couverture or attendue. Sinon biais a confirmer par DXY et oil."
            ),
        )

    category = logical_category(item)

    if text_contains_any(text, ("fed", "fomc", "powell", "minutes", "rate", "cut", "cuts", "dovish", "pause")) or category == "macro_fed":
        if item.score > 0:
            return ("bullish", "Une Fed percue comme moins restrictive est plutot favorable a l'or.")
        if item.score < 0:
            return ("bearish", "Une Fed plus restrictive soutient le dollar et les rendements, donc pese sur l'or.")
        return ("mixte", "Le message Fed n'est pas assez net pour donner un avantage clair a l'or.")

    if text_contains_any(text, ("cpi", "inflation", "gasoline")) or category == "macro_cpi":
        if item.score > 0:
            return ("bullish", "Une inflation qui se calme peut reduire la pression sur les taux et aider l'or.")
        if item.score < 0:
            return ("bearish", "Une inflation qui repart complique les baisses de taux et peut penaliser l'or.")
        return ("mixte", "L'effet inflation est partage entre theme refuge et risque de Fed plus dure.")

    if text_contains_any(text, ("jobs", "nfp", "nonfarm", "employment", "payroll")) or category == "macro_nfp":
        if item.score > 0:
            return ("bullish", "Un emploi plus faible peut detendre le dollar et les rendements, ce qui aide l'or.")
        if item.score < 0:
            return ("bearish", "Un emploi solide peut renforcer le dollar et retarder les baisses de taux.")
        return ("mixte", "Les chiffres de l'emploi ne donnent pas ici un signal directionnel clair.")

    if text_contains_any(text, ("cot", "managed money", "speculative")) or category == "sentiment_cot":
        return ("info", "Le COT ne bouge pas directement le prix intraday, mais il dit si le marche est deja trop charge.")

    if text_contains_any(text, ("open interest",)) or category == "sentiment_oi":
        return ("info", "L'open interest confirme surtout si le mouvement est alimente par de nouveaux engagements.")

    if text_contains_any(text, ("etf", "gld", "iau")) or category == "sentiment_etf":
        return ("info", "Les flux ETF sont utiles pour le fond de marche, plus que pour un declenchement intraday instantane.")

    if text_contains_any(text, ("vix", "fear", "volatility")) or category == "risk_vix":
        return ("mixte", "Une hausse de la peur soutient la couverture, mais selon le contexte le dollar peut capter une partie de ces flux.")

    if item.score > 0:
        return ("bullish", "Cette headline va plutot dans le sens d'un soutien a l'or.")
    if item.score < 0:
        return ("bearish", "Cette headline ajoute plutot une pression a court terme sur l'or.")
    return ("mixte", "Headline de contexte utile, mais sans impact directionnel propre a elle seule.")


def pick_story_headlines(news: list[NewsItem], limit: int = 6) -> list[NewsItem]:
    selected: list[NewsItem] = []
    seen: set[str] = set()
    preferred_categories = [
        "geopolitical",
        "macro_fed",
        "macro_cpi",
        "macro_nfp",
        "gold",
        "risk_vix",
        "sentiment_cot",
        "sentiment_etf",
        "sentiment_oi",
    ]

    sorted_news = sorted(news, key=headline_sort_key, reverse=False)
    for category in preferred_categories:
        for item in sorted_news:
            if logical_category(item) != category:
                continue
            key = normalize_title_for_dedupe(item.title)
            if key in seen:
                continue
            selected.append(item)
            seen.add(key)
            break
        if len(selected) >= limit:
            return selected[:limit]

    for item in sorted(news, key=lambda current: (abs(current.score), parse_iso_sort_key(current.published_at)), reverse=True):
        key = normalize_title_for_dedupe(item.title)
        if key in seen:
            continue
        selected.append(item)
        seen.add(key)
        if len(selected) >= limit:
            break
    return selected[:limit]


def find_story_for_categories(news: list[NewsItem], *categories: str) -> NewsItem | None:
    selected = {logical_category(category) for category in categories}
    for item in pick_story_headlines(news, limit=max(10, len(selected) * 2)):
        if logical_category(item) in selected:
            return item
    for item in news:
        if logical_category(item) in selected:
            return item
    return None


FACT_ACTOR_KEYWORDS = {
    "Iran": ("iran", "iranian", "tehran"),
    "United States": ("united states", "u.s.", "us ", "usa", "washington", "white house", "trump", "fed", "powell"),
    "Federal Reserve": ("fed", "fomc", "powell", "federal reserve"),
    "Oil market": ("oil", "crude", "wti", "brent", "barrel", "opec"),
    "Gold market": ("gold", "xauusd", "xau/usd", "precious metals"),
    "China": ("china", "chinese", "pboc"),
    "India": ("india", "indian"),
    "ETF investors": ("etf", "gld", "iau", "holdings", "inflows", "outflows"),
    "Futures traders": ("cot", "commitments of traders", "managed money", "open interest", "comex"),
}

FACT_LOCATION_KEYWORDS = {
    "Hormuz": ("hormuz", "strait of hormuz"),
    "Middle East": ("middle east", "gulf", "red sea", "israel", "iran"),
    "United States": ("united states", "u.s.", "usa", "washington"),
    "China": ("china", "beijing"),
    "India": ("india", "mumbai"),
    "COMEX": ("comex", "nymex"),
}

FACT_THEME_KEYWORDS = {
    "Oil shock": ("oil", "crude", "wti", "brent", "barrel", "hormuz", "shipping", "blockade"),
    "War risk": ("war", "conflict", "attack", "missile", "escalation", "sanction", "geopolitical"),
    "Dollar liquidity": ("dollar", "usd", "liquidity", "cash"),
    "Fed policy": ("fed", "fomc", "powell", "rate", "cut", "hike", "higher for longer"),
    "Inflation": ("cpi", "inflation", "prices", "gasoline"),
    "Positioning": ("cot", "managed money", "speculative", "open interest", "positions"),
    "ETF flows": ("etf", "gld", "iau", "holdings", "inflows", "outflows"),
    "Volatility": ("vix", "gvz", "fear", "volatility", "risk aversion"),
}

POLITICAL_THEME_KEYWORDS = {
    "Iran / Hormuz / Oil": ("iran", "hormuz", "oil", "crude", "shipping", "sanction", "missile", "gulf"),
    "Fed / Rates": ("fed", "powell", "rate", "fomc", "interest", "central bank"),
    "Dollar / Liquidity": ("dollar", "usd", "liquidity", "treasury"),
    "Tariffs / Trade": ("tariff", "china", "trade", "import", "export"),
    "Official White House": ("white house", "president trump", "presidential", "statement", "remarks"),
}


def is_political_statement_candidate(item: NewsItem) -> bool:
    text = f"{item.title} {item.source} {item.category}".lower()
    actor_match = text_contains_any(
        text,
        ("trump", "white house", "president trump", "administration", "treasury", "state department"),
    )
    market_trigger = text_contains_any(
        text,
        (
            "iran",
            "hormuz",
            "oil",
            "crude",
            "fed",
            "powell",
            "fomc",
            "rate",
            "dollar",
            "usd",
            "tariff",
            "sanction",
            "trade",
            "china",
            "treasury",
            "yield",
        ),
    )
    return actor_match and market_trigger


def keep_political_statement_candidates(items: list[NewsItem]) -> list[NewsItem]:
    return [item for item in items if is_political_statement_candidate(item)]


def detect_fact_labels(text: str, mapping: dict[str, tuple[str, ...]]) -> list[str]:
    normalized = normalize_title_for_dedupe(text)
    labels = [label for label, keywords in mapping.items() if text_contains_any(normalized, keywords)]
    return labels[:4]


def classify_confirmation_level(item: NewsItem) -> tuple[str, int]:
    source = item.source.lower()
    title = item.title.lower()
    if any(token in source for token in ("white house", "federal reserve", "fred", "cftc", "treasury", "eia")):
        return "source officielle", 88
    if any(token in source for token in ("reuters", "associated press", "ap news", "bloomberg")):
        return "agence/finance majeure", 82
    if any(token in source for token in ("investing", "yahoo", "marketwatch", "cnbc", "economic times")):
        return "media marche connu", 70
    if any(token in title for token in ("report", "data", "minutes", "statement")):
        return "headline a confirmer", 62
    return "source secondaire / a confirmer", 55


def classify_political_theme(item: NewsItem) -> str:
    text = f"{item.title} {item.source}".lower()
    for theme, keywords in POLITICAL_THEME_KEYWORDS.items():
        if text_contains_any(text, keywords):
            return theme
    return "Political context"


def classify_political_validation(item: NewsItem) -> tuple[str, int, int]:
    tier = political_source_tier(item)
    if tier == 1:
        return "official_confirmed", 1, 92
    if tier == 2:
        return "confirmed_secondary", 2, 82
    if tier == 3:
        return "market_media", 3, 68
    return "unconfirmed_headline", 4, 48


def build_political_market_chain(theme: str) -> str:
    if theme == "Iran / Hormuz / Oil":
        return (
            "Declaration politique -> risque Iran/Hormuz/oil -> WTI/Brent peuvent integrer une prime -> "
            "inflation, rendements et dollar peuvent monter -> gold devient mixte: refuge possible, pression liquidite possible."
        )
    if theme == "Fed / Rates":
        return (
            "Declaration politique -> attentes Fed/taux -> rendements reels et DXY bougent -> "
            "gold reagit via cout d'opportunite et credibilite de politique monetaire."
        )
    if theme == "Dollar / Liquidity":
        return (
            "Declaration politique -> lecture dollar/liquidite -> DXY peut attirer les capitaux defensifs -> "
            "gold peut etre freine meme en environnement de risque."
        )
    if theme == "Tariffs / Trade":
        return (
            "Declaration politique -> risque tarifs/inflation/croissance -> marche reprice dollar, taux et risque -> "
            "gold depend de l'equilibre inflation refuge contre dollar fort."
        )
    return (
        "Declaration politique -> contexte de risque mis a jour -> impact gold a confirmer par oil, DXY, taux et prix spot."
    )


def political_impacts(theme: str, item: NewsItem) -> tuple[str, str, str, int]:
    text = item.title.lower()
    if theme == "Iran / Hormuz / Oil":
        if text_contains_any(text, ("ceasefire", "peace", "talks", "deal", "de-escalation")):
            return (
                "baisse possible de la prime refuge si desescalade confirmee.",
                "baissier/moderateur si risque Hormuz recule.",
                "neutre a baissier si demande de liquidite dollar recule.",
                -1,
            )
        return (
            "mixte: refuge or si VIX > seuil, sinon liquidite USD captee par oil/DXY.",
            "haussier or si WTI > +1.0% sur 1h ou Brent > +1.0% sur 1h.",
            "haussier USD si DXY > +0.50% intraday sur message risk-off.",
            -1,
        )
    if theme == "Fed / Rates":
        if text_contains_any(text, ("cut", "lower", "pressure", "fire powell", "replace powell")):
            return (
                "haussier or si le marche price des taux plus bas ou une Fed moins restrictive.",
                "neutre sauf impact inflation/risque.",
                "baissier USD si les taux attendus reculent: DXY sous le pivot du jour.",
                1,
            )
        return (
            "mixte: depend de la reaction des rendements reels.",
            "neutre.",
            "a confirmer par DXY et taux.",
            0,
        )
    if theme == "Dollar / Liquidity":
        return (
            "souvent baissier si la declaration renforce le dollar ou la demande de liquidite USD.",
            "neutre.",
            "haussier pour USD si message pro-dollar ou risk-off.",
            -1,
        )
    if theme == "Tariffs / Trade":
        return (
            "mixte: inflation/refuge bullish, dollar/taux potentiellement bearish.",
            "haussier or si tarifs touchent energie/logistique avec WTI > +1.0% sur 1h.",
            "haussier USD si risque commercial pousse DXY au-dessus du pivot du jour.",
            0,
        )
    return ("impact gold a confirmer.", "impact oil a confirmer.", "impact USD a confirmer.", 0)


def build_political_statement_from_news(item: NewsItem) -> PoliticalStatement:
    theme = classify_political_theme(item)
    validation_level, source_tier, base_confidence = classify_political_validation(item)
    gold_impact, oil_impact, usd_impact, score = political_impacts(theme, item)
    if item.score:
        score += 1 if item.score > 0 else -1
    return PoliticalStatement(
        title=clean_display_text(item.title),
        source=clean_display_text(item.source),
        source_url=item.link,
        published_at=item.published_at,
        theme=theme,
        validation_level=validation_level,
        source_tier=source_tier,
        gold_impact=gold_impact,
        oil_impact=oil_impact,
        usd_impact=usd_impact,
        market_chain=build_political_market_chain(theme),
        score=int(clamp(score, -3, 3)),
        confidence=round(clamp(base_confidence + min(abs(item.score) * 3, 6), 35, 95)),
    )


def build_political_statements(news: list[NewsItem], limit: int = 5) -> list[PoliticalStatement]:
    statements: list[PoliticalStatement] = []
    seen: set[str] = set()
    for item in news:
        if not is_political_statement_candidate(item):
            continue
        key = normalize_title_for_dedupe(item.title)
        if not key or key in seen:
            continue
        seen.add(key)
        statements.append(build_political_statement_from_news(item))
    statements.sort(key=lambda item: (item.source_tier * -1, item.confidence, abs(item.score), item.published_at), reverse=True)
    return statements[:limit]


def build_event_market_chain(themes: list[str], item: NewsItem) -> str:
    if "Oil shock" in themes:
        return (
            "Fait source -> risque petrole/logistique -> WTI/Brent et inflation energie peuvent monter -> "
            "rendements/dollar peuvent capter la liquidite -> gold devient mixte, parfois sous pression court terme."
        )
    if "Dollar liquidity" in themes:
        return (
            "Fait source -> recherche de liquidite dollar -> DXY peut se renforcer -> "
            "gold peut etre vendu temporairement meme si le risque reste defensif."
        )
    if "Fed policy" in themes or "Inflation" in themes:
        return (
            "Fait source -> attentes Fed/inflation changent -> rendements reels et DXY bougent -> "
            "gold reagit surtout via le cout d'opportunite et le dollar."
        )
    if "Positioning" in themes or "ETF flows" in themes:
        return (
            "Fait source -> flux/positionnement institutionnel changent -> conviction de marche augmente ou baisse -> "
            "gold est confirme seulement si prix et volumes suivent."
        )
    if "War risk" in themes:
        return (
            "Fait source -> aversion au risque -> demande de couverture peut soutenir gold -> "
            "mais l'effet reste conditionne par dollar, oil et liquidite."
        )
    return (
        "Fait source -> contexte de marche mis a jour -> impact gold a confirmer par DXY, taux, oil et prix spot."
    )


def build_event_fact_from_news(
    item: NewsItem,
    *,
    wti: SymbolSnapshot | None = None,
    brent: SymbolSnapshot | None = None,
    dxy: SymbolSnapshot | None = None,
    us10y: SymbolSnapshot | None = None,
    gold: SymbolSnapshot | None = None,
) -> NewsFact:
    """Construit un NewsFact v3 a partir d'un NewsItem et des snapshots marche."""
    text = clean_display_text(item.title)
    actors = detect_fact_labels(text, FACT_ACTOR_KEYWORDS) or ["Marche"]
    locations = detect_fact_labels(text, FACT_LOCATION_KEYWORDS) or ["Global"]
    themes = detect_fact_labels(text, FACT_THEME_KEYWORDS) or [item.category.replace("_", " ").title()]
    confirmation_level, base_confidence = classify_confirmation_level(item)
    impact_bias, impact_text = explain_headline_gold_impact(item)
    confidence = round(clamp(base_confidence + min(abs(item.score) * 3, 9), 35, 92))
    return _build_news_fact_v3(
        title=text,
        source=clean_display_text(item.source),
        source_url=item.link,
        published_at=item.published_at,
        category=item.category,
        actors=actors,
        locations=locations,
        themes=themes,
        confirmation_level=confirmation_level,
        market_chain=build_event_market_chain(themes, item),
        gold_impact=impact_text,
        impact_bias=impact_bias,
        confidence=confidence,
        wti_change=wti.change_pct if wti else None,
        brent_change=brent.change_pct if brent else None,
        dxy_change=dxy.change_pct if dxy else None,
        rates_change_bps=(us10y.change_abs * 100) if us10y else None,
        gold_change=gold.change_pct if gold else None,
    )


def build_event_facts(
    news: list[NewsItem],
    limit: int = 6,
    *,
    wti: SymbolSnapshot | None = None,
    brent: SymbolSnapshot | None = None,
    dxy: SymbolSnapshot | None = None,
    us10y: SymbolSnapshot | None = None,
    gold: SymbolSnapshot | None = None,
) -> list[NewsFact]:
    """Construit les NewsFacts v3 avec deduplication semantique et snapshots marche."""
    candidates = [
        item
        for item in pick_story_headlines(news, limit=max(limit * 3, 18))
        if not should_skip_headline(item.title, item.source)
        and news_source_tier(item.source, item.link) <= 3
        and (logical_category(item) in PRIORITY_NEWS_CATEGORIES or abs(item.score) >= 1)
    ]
    raw_facts = [
        build_event_fact_from_news(item, wti=wti, brent=brent, dxy=dxy, us10y=us10y, gold=gold)
        for item in candidates
    ]
    deduped = deduplicate_news_facts(raw_facts, threshold=0.65)
    return deduped[:limit]


def build_information_digest_items(
    gold: SymbolSnapshot,
    dxy: SymbolSnapshot,
    us10y: SymbolSnapshot,
    news: list[NewsItem],
    geopolitical: GeopoliticalAnalysis | None,
) -> list[tuple[str, str, str]]:
    items: list[tuple[str, str, str]] = []
    tape_reason = (
        f"L'or cote {gold.price:.2f}, le DXY fait {dxy.change_pct:+.2f}% et le 10 ans US bouge de "
        f"{us10y.change_abs * 100:+.1f} bps."
    )
    if dxy.change_pct < 0 and us10y.change_abs < 0:
        tape_impact = "Le tandem dollar plus faible + rendements plus bas soutient clairement l'or pour l'instant."
    elif dxy.change_pct > 0 and us10y.change_abs > 0:
        tape_impact = "Dollar et rendements montent ensemble: c'est normalement un frein direct pour l'or."
    else:
        tape_impact = "Les moteurs macro sont melanges, donc l'or ne recoit pas un soutien propre et lineaire."
    items.append(("Tape du jour", tape_reason, tape_impact))

    geo_story = find_story_for_categories(news, "geopolitical", "gold")
    if geo_story:
        _geo_label, geo_impact = explain_headline_gold_impact(geo_story)
        items.append(
            (
                "Geopolitique",
                clean_display_text(geo_story.title),
                f"{explain_headline_reason(geo_story)} {geo_impact}",
            )
        )
    elif geopolitical:
        items.append(
            (
                "Geopolitique",
                f"Risk-off {geopolitical.risk_off_status}, banques centrales {geopolitical.central_bank_bias}.",
                geopolitical.summary,
            )
        )

    macro_story = find_story_for_categories(news, "macro_fed", "macro_cpi", "macro_nfp", "events_fomc")
    if macro_story:
        _macro_label, macro_impact = explain_headline_gold_impact(macro_story)
        items.append(
            (
                "Macro US",
                clean_display_text(macro_story.title),
                f"{explain_headline_reason(macro_story)} {macro_impact}",
            )
        )

    flow_story = find_story_for_categories(news, "sentiment_cot", "sentiment_etf", "sentiment_oi", "physical_demand", "risk_vix")
    if flow_story:
        _flow_label, flow_impact = explain_headline_gold_impact(flow_story)
        items.append(
            (
                "Flux et sentiment",
                clean_display_text(flow_story.title),
                f"{explain_headline_reason(flow_story)} {flow_impact}",
            )
        )
    elif geopolitical:
        items.append(
            (
                "Flux et sentiment",
                (
                    f"Large specs {geopolitical.large_speculators}, ETF {geopolitical.etf_flows}, "
                    f"open interest {geopolitical.comex_open_interest}."
                ),
                "Cela dit si la hausse est construite par de nouveaux acheteurs ou si elle reste surtout defensive."
            )
        )

    return items[:4]


def render_news_lines(items: list[NewsItem], max_items: int) -> list[str]:
    lines: list[str] = []
    for item in pick_story_headlines(items, limit=max_items):
        timestamp = item.published_at.replace("+00:00", "Z")
        impact_label, impact_text = explain_headline_gold_impact(item)
        lines.append(f"- [{clean_display_text(item.source)}] {clean_display_text(item.title)} ({timestamp})")
        lines.append(f"  En clair: {explain_headline_reason(item)}")
        lines.append(f"  Impact sur l'or ({impact_label}): {impact_text}")
        if item.link:
            lines.append(f"  {item.link}")
    return lines


def heuristic_decision_sentence(analysis: AnalysisResult) -> str:
    if analysis.bias == "bullish":
        return (
            "Biais court terme: BUY conditionnel. Declencheur: DXY < seuil intraday et baisse continue des taux US. "
            "Invalidation: rebond DXY ou rendement 10Y au-dessus du pivot du jour."
        )
    if analysis.bias == "slightly bullish":
        return (
            "Biais court terme: WATCH_BUY. Declencheur: cassure de la resistance intraday avec DXY confirme en baisse. "
            "Invalidation: retour sous le pivot M15."
        )
    if analysis.bias == "bearish":
        return (
            "Biais court terme: SELL conditionnel. Declencheur: poursuite hausse rendements US 10Y et DXY au-dessus du pivot. "
            "Invalidation: detente brusque taux/dollar."
        )
    if analysis.bias == "slightly bearish":
        return (
            "Biais court terme: WATCH_SELL. Declencheur: cassure du support intraday avec DXY confirme en hausse. "
            "Invalidation: retour au-dessus du pivot M15."
        )
    return (
        "Biais court terme: NO_TRADE directionnel. Aucun avantage dollar, taux ou structure intraday. "
        "Attendre un seuil franchi sur DXY ou un trigger news."
    )


def call_openai_analysis(payload: dict[str, Any]) -> str | None:
    api_key = os.getenv("OPENAI_API_KEY")
    model = os.getenv("OPENAI_MODEL")
    if not api_key or not model:
        return None

    try:
        from openai import OpenAI
    except ImportError:
        return "Analyse IA indisponible: la librairie 'openai' n'est pas installee."

    try:
        client = OpenAI(api_key=api_key)
        response = client.responses.create(
            model=model,
            input=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {
                    "role": "user",
                    "content": (
                        "Analyse le briefing suivant et genere une synthese prudente.\n\n"
                        f"{json.dumps(payload, ensure_ascii=False, indent=2)}"
                    ),
                },
            ],
        )
        text = getattr(response, "output_text", None)
        if text:
            return text.strip()
        return "Analyse IA indisponible: la reponse n'a pas retourne de texte exploitable."
    except Exception as exc:  # pragma: no cover - network/runtime branch
        return f"Analyse IA indisponible: {exc}"


def macro_rate_payload(snapshot: SymbolSnapshot | None, source: str) -> dict[str, Any] | None:
    if snapshot is None:
        return None
    return {
        "symbol": snapshot.symbol,
        "label": snapshot.label,
        "source": source,
        "price": round(snapshot.price, 3),
        "previous_close": round(snapshot.previous_close, 3),
        "change_bps": round(snapshot.change_abs * 100, 1),
        "last_update": snapshot.fetched_at,
    }


def build_payload(
    gold: SymbolSnapshot,
    dxy: SymbolSnapshot,
    us10y: SymbolSnapshot,
    news: list[NewsItem],
    analysis: AnalysisResult,
    geopolitical_analysis: GeopoliticalAnalysis | None = None,
    fundamental_recommendation: TradeRecommendation | None = None,
    technical_recommendation: TradeRecommendation | None = None,
    technical_decision: TechnicalDecision | None = None,
    scenario_plan: ScenarioPlan | None = None,
    global_recommendation: TradeRecommendation | None = None,
    technical_timeframes: list[TechnicalReading] | None = None,
    real_yield: SymbolSnapshot | None = None,
    official_macro_rates: OfficialMacroRates | None = None,
    cftc_positioning: CFTCPositioning | None = None,
    etf_flows_analysis: ETFFlowsAnalysis | None = None,
    macro_catalysts: MacroCatalystCalendar | None = None,
    data_quality: DataQualitySnapshot | None = None,
    cross_asset_analysis: CrossAssetAnalysis | None = None,
    event_mode: EventModeAnalysis | None = None,
    weekend_gold: WeekendGoldSnapshot | None = None,
    market_regime: MarketRegimeAnalysis | None = None,
    event_facts: list[EventFact] | None = None,
    political_statements: list[PoliticalStatement] | None = None,
    agent_results: list[AgentResult] | None = None,
    trade_ledger: TradeLedgerSummary | None = None,
    orchestrator_decision: OrchestratorDecision | None = None,
    chart_store: ChartStore | None = None,
    news_reaction_setup: NewsReactionTradePlan | None = None,
    reversal_engine: dict[str, ReversalSetup] | None = None,
    strategy_candidates: list[SetupCandidate] | None = None,
    strategy_selection: StrategySelection | None = None,
    settings: UserSettings | None = None,
    settings_validation: SettingsValidation | None = None,
) -> dict[str, Any]:
    payload = {
        "generated_at": iso_now(),
        "market_snapshot": {
            "xauusd_spot": {
                "symbol": gold.symbol,
                "price": round(gold.price, 2),
                "previous_close": round(gold.previous_close, 2),
                "change_pct": round(gold.change_pct, 2),
                "short_term_change_pct": round(gold.period_change_pct, 2),
                "support": round(gold.support, 2) if gold.support is not None else None,
                "resistance": round(gold.resistance, 2) if gold.resistance is not None else None,
                "day_high": round(gold.day_high, 2) if gold.day_high is not None else None,
                "day_low": round(gold.day_low, 2) if gold.day_low is not None else None,
                "recent_closes": [
                    {
                        "timestamp": point.timestamp,
                        "close": round(point.close, 2),
                    }
                    for point in gold.points[-40:]
                ],
                "intraday_candles": [
                    {
                        "timestamp": point.timestamp,
                        "open": round((point.open if point.open is not None else point.close), 2),
                        "high": round((point.high if point.high is not None else point.close), 2),
                        "low": round((point.low if point.low is not None else point.close), 2),
                        "close": round(point.close, 2),
                        "volume": point.volume,
                    }
                    for point in gold.intraday_points[-80:]
                ],
                "last_update": gold.fetched_at,
                "source_name": "Investing.com",
                "source_url": INVESTING_XAUUSD_URL,
            },
            "dxy": {
                "symbol": dxy.symbol,
                "price": round(dxy.price, 3),
                "change_pct": round(dxy.change_pct, 2),
            },
            "us10y_yield": {
                "symbol": us10y.symbol,
                "price": round(us10y.price, 3),
                "change_bps": round(us10y.change_abs * 100, 1),
            },
        },
        "heuristic_bias": {
            "bias": analysis.bias,
            "score": analysis.score,
            "confidence": analysis.confidence,
            "reasons": analysis.reasons,
        },
        "headlines": [
            {
                "title": item.title,
                "source": item.source,
                "published_at": item.published_at,
                "category": item.category,
                "score": item.score,
                "score_reasons": item.score_reasons,
                "link": item.link,
            }
            for item in news
        ],
        "note": (
            "This is an information briefing for research. "
            "It is not personalized financial advice."
        ),
    }

    if fundamental_recommendation:
        payload["fundamental_recommendation"] = asdict(fundamental_recommendation)
    if technical_recommendation:
        payload["technical_recommendation"] = asdict(technical_recommendation)
    if technical_decision:
        payload["technical_decision"] = asdict(technical_decision)
    if scenario_plan:
        payload["scenario_plan"] = asdict(scenario_plan)
    if global_recommendation:
        payload["global_recommendation"] = asdict(global_recommendation)
    if geopolitical_analysis:
        payload["geopolitical_analysis"] = asdict(geopolitical_analysis)
    if technical_timeframes:
        payload["technical_timeframes"] = [asdict(reading) for reading in technical_timeframes]
    if real_yield:
        payload["market_snapshot"]["real_yield_10y"] = {
            "symbol": real_yield.symbol,
            "source": "FRED DFII10",
            "price": round(real_yield.price, 3),
            "change_bps": round(real_yield.change_abs * 100, 1),
            "last_update": real_yield.fetched_at,
        }
    if official_macro_rates:
        payload["market_snapshot"]["official_macro_rates"] = {
            "source": "FRED",
            "dgs10": macro_rate_payload(official_macro_rates.dgs10, "FRED DGS10"),
            "dgs2": macro_rate_payload(official_macro_rates.dgs2, "FRED DGS2"),
            "dgs3m": macro_rate_payload(official_macro_rates.dgs3m, "FRED DGS3MO"),
            "dgs30": macro_rate_payload(official_macro_rates.dgs30, "FRED DGS30"),
            "t10yie": macro_rate_payload(official_macro_rates.t10yie, "FRED T10YIE"),
            "dfii10": macro_rate_payload(official_macro_rates.dfii10, "FRED DFII10"),
            "yahoo_tnx_gap_bps": (
                round(official_macro_rates.yahoo_tnx_gap_bps, 1)
                if official_macro_rates.yahoo_tnx_gap_bps is not None
                else None
            ),
            "policy": "FRED rates are the official macro source; Yahoo ^TNX is kept as a cross-check.",
        }
    if cftc_positioning:
        payload["cftc_positioning"] = asdict(cftc_positioning)
    if etf_flows_analysis:
        payload["etf_flows_analysis"] = asdict(etf_flows_analysis)
    if macro_catalysts:
        payload["macro_catalysts"] = asdict(macro_catalysts)
    if data_quality:
        payload["data_quality"] = asdict(data_quality)
    if chart_store:
        payload["chart_store"] = asdict(chart_store)
    if cross_asset_analysis:
        payload["cross_asset_analysis"] = asdict(cross_asset_analysis)
    if event_mode:
        payload["event_mode"] = asdict(event_mode)
    if market_regime:
        payload["market_regime"] = asdict(market_regime)
    if event_facts:
        payload["event_facts"] = [asdict(fact) for fact in event_facts]
    if political_statements:
        payload["political_statements"] = [asdict(statement) for statement in political_statements]
    if agent_results:
        payload["agent_results"] = [asdict(agent) for agent in agent_results]
    if trade_ledger:
        payload["trade_ledger"] = trade_ledger_public_dict(trade_ledger)
    if orchestrator_decision:
        payload["orchestrator_decision"] = asdict(orchestrator_decision)
    if news_reaction_setup:
        payload["news_reaction_setup"] = asdict(news_reaction_setup)
    if reversal_engine:
        payload["reversal_engine"] = {key: asdict(value) for key, value in reversal_engine.items()}
    if strategy_candidates:
        payload["strategy_candidates"] = [asdict(candidate) for candidate in strategy_candidates]
    if strategy_selection:
        payload["strategy_selection"] = asdict(strategy_selection)
    if global_recommendation or strategy_selection:
        payload["strategy_shadow_integration"] = asdict(
            build_strategy_shadow_integration(global_recommendation, strategy_selection)
        )
    if settings:
        payload["settings"] = asdict(settings)
    if settings_validation:
        payload["settings_validation"] = asdict(settings_validation)
    payload["monitoring_inspector"] = build_monitoring_inspector_payload(
        str(payload["generated_at"]),
        data_quality,
        agent_results or [],
        trade_ledger,
        orchestrator_decision,
        global_recommendation,
        market_regime,
        chart_store,
        strategy_candidates,
        strategy_selection,
    )
    if weekend_gold:
        payload["market_snapshot"]["weekend_gold"] = {
            "symbol": "Weekend Gold",
            "source_name": weekend_gold.source_name,
            "source_url": weekend_gold.source_url,
            "sell": round(weekend_gold.sell, 2),
            "buy": round(weekend_gold.buy, 2),
            "mid": round(weekend_gold.mid, 2),
            "spread": round(weekend_gold.spread, 2),
            "change_abs": round(weekend_gold.change_abs, 2) if weekend_gold.change_abs is not None else None,
            "change_pct": round(weekend_gold.change_pct, 2) if weekend_gold.change_pct is not None else None,
            "day_high": round(weekend_gold.day_high, 2) if weekend_gold.day_high is not None else None,
            "day_low": round(weekend_gold.day_low, 2) if weekend_gold.day_low is not None else None,
            "long_pct": weekend_gold.long_pct,
            "short_pct": weekend_gold.short_pct,
            "last_update": weekend_gold.fetched_at,
            "note": "Prix week-end IG: proxy indicatif, distinct du spot XAU/USD classique.",
        }

    return payload


def build_price_points(entries: list[dict[str, Any]]) -> list[PricePoint]:
    points: list[PricePoint] = []
    for entry in entries:
        close = parse_float(entry.get("close"))
        if close is None:
            continue
        volume_raw = entry.get("volume")
        points.append(
            PricePoint(
                timestamp=int(entry.get("timestamp", 0) or 0),
                close=close,
                high=parse_float(entry.get("high")),
                low=parse_float(entry.get("low")),
                open=parse_float(entry.get("open")),
                volume=int(volume_raw) if volume_raw is not None else None,
            )
        )
    return points


def build_macro_rate_from_payload(data: dict[str, Any] | None, fallback_label: str) -> SymbolSnapshot | None:
    if not isinstance(data, dict) or data.get("price") is None:
        return None
    price = float(data.get("price", 0.0) or 0.0)
    change_bps = float(data.get("change_bps", 0.0) or 0.0)
    previous = float(data.get("previous_close", price - (change_bps / 100.0)) or price)
    return SymbolSnapshot(
        symbol=str(data.get("symbol", "")),
        label=str(data.get("label", fallback_label)),
        price=price,
        previous_close=previous,
        change_abs=price - previous,
        change_pct=((price - previous) / abs(previous) * 100) if previous else 0.0,
        period_change_pct=0.0,
        day_high=None,
        day_low=None,
        support=None,
        resistance=None,
        fetched_at=str(data.get("last_update", iso_now())),
        points=[PricePoint(timestamp=int(time.time()), close=price)],
    )


def build_cftc_positioning_from_payload(data: dict[str, Any] | None) -> CFTCPositioning | None:
    if not isinstance(data, dict):
        return None
    return CFTCPositioning(
        market=str(data.get("market", CFTC_GOLD_MARKET_NAME)),
        contract_code=str(data.get("contract_code", CFTC_GOLD_CONTRACT_CODE)),
        report_date=str(data.get("report_date", "")),
        source_url=str(data.get("source_url", CFTC_DISAGG_CURRENT_URL)),
        open_interest=int(data.get("open_interest", 0) or 0),
        open_interest_change=int(data.get("open_interest_change", 0) or 0),
        managed_money_long=int(data.get("managed_money_long", 0) or 0),
        managed_money_short=int(data.get("managed_money_short", 0) or 0),
        managed_money_spread=int(data.get("managed_money_spread", 0) or 0),
        managed_money_net=int(data.get("managed_money_net", 0) or 0),
        managed_money_net_change=int(data.get("managed_money_net_change", 0) or 0),
        managed_money_net_pct_oi=float(data.get("managed_money_net_pct_oi", 0.0) or 0.0),
        producer_long=int(data.get("producer_long", 0) or 0),
        producer_short=int(data.get("producer_short", 0) or 0),
        producer_net=int(data.get("producer_net", 0) or 0),
        producer_net_change=int(data.get("producer_net_change", 0) or 0),
        swap_long=int(data.get("swap_long", 0) or 0),
        swap_short=int(data.get("swap_short", 0) or 0),
        swap_spread=int(data.get("swap_spread", 0) or 0),
        swap_net=int(data.get("swap_net", 0) or 0),
        swap_net_change=int(data.get("swap_net_change", 0) or 0),
        non_reportable_long=int(data.get("non_reportable_long", 0) or 0),
        non_reportable_short=int(data.get("non_reportable_short", 0) or 0),
        non_reportable_net=int(data.get("non_reportable_net", 0) or 0),
        non_reportable_net_change=int(data.get("non_reportable_net_change", 0) or 0),
        score=int(data.get("score", 50) or 50),
        status=str(data.get("status", "neutral positioning")),
        summary=str(data.get("summary", "COT officiel indisponible.")),
        managed_money_percentile_1y=float(data.get("managed_money_percentile_1y", 50.0) or 50.0),
        managed_money_percentile_5y=float(data.get("managed_money_percentile_5y", 50.0) or 50.0),
        producer_net_percentile_1y=float(data.get("producer_net_percentile_1y", 50.0) or 50.0),
        producer_net_percentile_5y=float(data.get("producer_net_percentile_5y", 50.0) or 50.0),
    )


def build_etf_holding_record_from_payload(data: dict[str, Any]) -> ETFHoldingRecord:
    return ETFHoldingRecord(
        fund=str(data.get("fund", "")),
        ticker=str(data.get("ticker", "")),
        source_name=str(data.get("source_name", "")),
        source_url=str(data.get("source_url", "")),
        as_of_date=str(data.get("as_of_date", "")),
        holdings_tonnes=parse_float(data.get("holdings_tonnes")),
        daily_flow_tonnes=parse_float(data.get("daily_flow_tonnes")),
        weekly_flow_tonnes=parse_float(data.get("weekly_flow_tonnes")),
        monthly_flow_tonnes=parse_float(data.get("monthly_flow_tonnes")),
        ytd_flow_tonnes=parse_float(data.get("ytd_flow_tonnes")),
        flow_usd_mn=parse_float(data.get("flow_usd_mn")),
        status=str(data.get("status", "unknown")),
        note=str(data.get("note", "")),
    )


def build_etf_flows_analysis_from_payload(data: dict[str, Any] | None) -> ETFFlowsAnalysis | None:
    if not isinstance(data, dict):
        return None
    return ETFFlowsAnalysis(
        as_of_date=str(data.get("as_of_date", "")),
        source_name=str(data.get("source_name", "ETF official flows")),
        source_url=str(data.get("source_url", "")),
        global_holdings_tonnes=parse_float(data.get("global_holdings_tonnes")),
        global_weekly_demand_tonnes=parse_float(data.get("global_weekly_demand_tonnes")),
        global_monthly_demand_tonnes=parse_float(data.get("global_monthly_demand_tonnes")),
        global_weekly_flows_usd_mn=parse_float(data.get("global_weekly_flows_usd_mn")),
        global_monthly_flows_usd_mn=parse_float(data.get("global_monthly_flows_usd_mn")),
        score=int(data.get("score", 50) or 50),
        status=str(data.get("status", "unknown")),
        summary=str(data.get("summary", "Flux ETF officiels indisponibles.")),
        holdings=[
            build_etf_holding_record_from_payload(item)
            for item in data.get("holdings", [])
            if isinstance(item, dict)
        ],
        source_note=str(data.get("source_note", "")),
    )


def build_macro_catalyst_from_payload(data: dict[str, Any]) -> MacroCatalyst:
    return MacroCatalyst(
        title=str(data.get("title", "")),
        event_type=str(data.get("event_type", "")),
        scheduled_at=str(data.get("scheduled_at", "")),
        source_name=str(data.get("source_name", "")),
        source_url=str(data.get("source_url", "")),
        impact_level=str(data.get("impact_level", "MEDIUM")),
        gold_impact=str(data.get("gold_impact", "Impact gold a confirmer.")),
        why_it_matters=str(data.get("why_it_matters", "Pourquoi macro indisponible.")),
        status=str(data.get("status", "a venir")),
        minutes_to_event=int(data["minutes_to_event"]) if data.get("minutes_to_event") is not None else None,
        forecast=str(data.get("forecast", "")),
        previous=str(data.get("previous", "")),
        actual=str(data.get("actual", "")),
        expected_gold_bias=str(data.get("expected_gold_bias", "NEUTRAL")).upper(),
    )


def build_macro_catalyst_calendar_from_payload(data: dict[str, Any] | None) -> MacroCatalystCalendar | None:
    if not isinstance(data, dict):
        return None
    return MacroCatalystCalendar(
        generated_at=str(data.get("generated_at", iso_now())),
        source_note=str(data.get("source_note", "")),
        fedwatch_status=str(data.get("fedwatch_status", "linked_only")),
        fedwatch_note=str(data.get("fedwatch_note", "")),
        fedwatch_source_url=str(data.get("fedwatch_source_url", CME_FEDWATCH_TOOL_URL)),
        catalysts=[
            build_macro_catalyst_from_payload(item)
            for item in data.get("catalysts", [])
            if isinstance(item, dict)
        ],
        high_impact_24h=int(data.get("high_impact_24h", 0) or 0),
        density_status=str(data.get("density_status", "normal")),
        pre_event_active=bool(data.get("pre_event_active", False)),
        pre_event_summary=str(data.get("pre_event_summary", "")),
    )


def build_source_snapshot_from_payload(data: dict[str, Any]) -> SourceSnapshot:
    return SourceSnapshot(
        source_id=str(data.get("source_id", "")),
        name=str(data.get("name", "")),
        category=str(data.get("category", "")),
        tier=int(data.get("tier", 4) or 4),
        status=str(data.get("status", "missing")),
        last_update=str(data.get("last_update")) if data.get("last_update") is not None else None,
        age_minutes=int(data["age_minutes"]) if data.get("age_minutes") is not None else None,
        value_summary=str(data.get("value_summary", "")),
        source_url=str(data.get("source_url", "")),
        critical=bool(data.get("critical", False)),
        allowed_agents=[str(item) for item in data.get("allowed_agents", [])],
    )


def build_data_quality_from_payload(data: dict[str, Any] | None) -> DataQualitySnapshot | None:
    if not isinstance(data, dict):
        return None
    return DataQualitySnapshot(
        generated_at=str(data.get("generated_at", iso_now())),
        score=int(data.get("score", 50) or 50),
        status=str(data.get("status", "UNKNOWN")),
        summary=str(data.get("summary", "Data quality indisponible.")),
        missing_sources=[str(item) for item in data.get("missing_sources", [])],
        stale_sources=[str(item) for item in data.get("stale_sources", [])],
        weak_sources=[str(item) for item in data.get("weak_sources", [])],
        contradictions=[str(item) for item in data.get("contradictions", [])],
        snapshots=[
            build_source_snapshot_from_payload(item)
            for item in data.get("snapshots", [])
            if isinstance(item, dict)
        ],
    )


def build_trade_ledger_from_payload(data: dict[str, Any] | None) -> TradeLedgerSummary | None:
    if not isinstance(data, dict):
        return None
    stats_data = data.get("stats") if isinstance(data.get("stats"), dict) else {}
    post_mortems_data = data.get("post_mortems") if isinstance(data.get("post_mortems"), list) else []
    return TradeLedgerSummary(
        ledger_path=str(data.get("ledger_path", str(TRADE_LEDGER_PATH))),
        generated_at=str(data.get("generated_at", iso_now())),
        quality_gate_status=str(data.get("quality_gate_status", "WAIT")),
        quality_gate_reasons=[str(item) for item in data.get("quality_gate_reasons", [])],
        active_trades=[
            parse_trade_plan(item)
            for item in data.get("active_trades", data.get("plans", []))
            if isinstance(item, dict)
        ],
        recent_trades=[
            parse_trade_plan(item)
            for item in data.get("recent_trades", [])
            if isinstance(item, dict)
        ],
        total_trades=int(data.get("total_trades", 0) or 0),
        wins=int(data.get("wins", 0) or 0),
        losses=int(data.get("losses", 0) or 0),
        partials=int(data.get("partials", 0) or 0),
        expired=int(data.get("expired", 0) or 0),
        invalidated=int(data.get("invalidated", 0) or 0),
        stats=TradeLedgerStats(
            win_rate=float(stats_data.get("win_rate", 0.0) or 0.0),
            expectancy_r=float(stats_data.get("expectancy_r", 0.0) or 0.0),
            average_r=float(stats_data.get("average_r", 0.0) or 0.0),
            average_duration_minutes=int(stats_data.get("average_duration_minutes", 0) or 0),
            setup_to_trade_rate=float(stats_data.get("setup_to_trade_rate", 0.0) or 0.0),
            trade_to_win_rate=float(stats_data.get("trade_to_win_rate", 0.0) or 0.0),
            total_setups=int(stats_data.get("total_setups", 0) or 0),
            total_trade_records=int(stats_data.get("total_trade_records", 0) or 0),
        ),
        post_mortems=[
            TradePostMortem(
                trade_id=str(item.get("trade_id", "")),
                direction=str(item.get("direction", "")),
                outcome=str(item.get("outcome", "")),
                record_type=str(item.get("record_type", "")),
                r_multiple=float(item.get("r_multiple", 0.0) or 0.0),
                duration_minutes=int(item.get("duration_minutes", 0) or 0),
                useful_agents=[str(agent) for agent in item.get("useful_agents", [])],
                misleading_agents=[str(agent) for agent in item.get("misleading_agents", [])],
                missed_condition=str(item.get("missed_condition", "")),
                summary=str(item.get("summary", "")),
            )
            for item in post_mortems_data
            if isinstance(item, dict)
        ],
    )


def build_news_reaction_from_payload(data: dict[str, Any] | None) -> NewsReactionTradePlan | None:
    if not isinstance(data, dict):
        return None
    return NewsReactionTradePlan(
        status=str(data.get("status", "NO_EVENT")),
        direction=str(data.get("direction", "WAIT")),
        event_type=str(data.get("event_type", "NO_FAST_EVENT")),
        title=str(data.get("title", "")),
        source=str(data.get("source", "")),
        source_url=str(data.get("source_url", "")),
        confidence=int(data.get("confidence", 0) or 0),
        validity_minutes=int(data.get("validity_minutes", 0) or 0),
        valid_until=str(data.get("valid_until", "")),
        entry_type=str(data.get("entry_type", "NEWS_REACTION")),
        reference_price=float(data.get("reference_price", 0.0) or 0.0),
        entry_zone_low=float(data.get("entry_zone_low", 0.0) or 0.0),
        entry_zone_high=float(data.get("entry_zone_high", 0.0) or 0.0),
        stop_loss=float(data.get("stop_loss", 0.0) or 0.0),
        tp1=float(data.get("tp1", 0.0) or 0.0),
        tp2=float(data.get("tp2", 0.0) or 0.0),
        tp3=float(data.get("tp3", 0.0) or 0.0),
        risk_reward_tp1=float(data.get("risk_reward_tp1", 0.0) or 0.0),
        risk_reward_tp2=float(data.get("risk_reward_tp2", 0.0) or 0.0),
        risk_reward_tp3=float(data.get("risk_reward_tp3", 0.0) or 0.0),
        confirmation_score=int(data.get("confirmation_score", 0) or 0),
        latency_seconds=float(data["latency_seconds"]) if data.get("latency_seconds") is not None else None,
        created_at=str(data.get("created_at", iso_now())),
        event_id=str(data.get("event_id", "NO_EVENT")),
        reasons=[str(item) for item in data.get("reasons", [])],
        blockers=[str(item) for item in data.get("blockers", [])],
    )


def build_reversal_setup_from_payload(data: dict[str, Any]) -> ReversalSetup:
    return ReversalSetup(
        horizon=str(data.get("horizon", "")),
        status=str(data.get("status", "NO_REVERSAL_TRADE")),
        direction=str(data.get("direction", "NEUTRAL")),
        tf_signal=str(data.get("tf_signal", "")),
        tf_context=str(data.get("tf_context", "")),
        confluence_score=int(data.get("confluence_score", 0) or 0),
        conditions_met=[str(item) for item in data.get("conditions_met", [])],
        entry_zone_low=float(data.get("entry_zone_low", 0.0) or 0.0),
        entry_zone_high=float(data.get("entry_zone_high", 0.0) or 0.0),
        stop_loss=float(data.get("stop_loss", 0.0) or 0.0),
        tp1=float(data.get("tp1", 0.0) or 0.0),
        tp2=float(data.get("tp2", 0.0) or 0.0),
        tp3=float(data.get("tp3", 0.0) or 0.0),
        risk_reward_tp1=float(data.get("risk_reward_tp1", 0.0) or 0.0),
        validity_minutes=int(data.get("validity_minutes", 0) or 0),
        reasons=[str(item) for item in data.get("reasons", [])],
        blockers=[str(item) for item in data.get("blockers", [])],
        detected_at=str(data.get("detected_at", iso_now())),
    )


def build_reversal_engine_from_payload(data: dict[str, Any] | None) -> dict[str, ReversalSetup]:
    if not isinstance(data, dict):
        return {}
    setups: dict[str, ReversalSetup] = {}
    for key in ("scalp", "intraday", "swing"):
        item = data.get(key)
        if isinstance(item, dict):
            setups[key] = build_reversal_setup_from_payload(item)
    return setups


def build_orchestrator_component_from_payload(data: dict[str, Any]) -> OrchestratorComponent:
    return OrchestratorComponent(
        key=str(data.get("key", "")),
        label=str(data.get("label", "")),
        score=int(data.get("score", 50) or 50),
        bias=str(data.get("bias", "NEUTRAL")),
        weight=float(data.get("weight", 0.0) or 0.0),
        contribution=float(data.get("contribution", 0.0) or 0.0),
        confidence=int(data.get("confidence", 50) or 50),
        source=str(data.get("source", "")),
        reason=str(data.get("reason", "")),
        weight_reason=str(data.get("weight_reason", "Poids de base.")),
    )


def build_orchestrator_decision_from_payload(data: dict[str, Any] | None) -> OrchestratorDecision | None:
    if not isinstance(data, dict):
        return None
    return OrchestratorDecision(
        verdict=str(data.get("verdict", "WAIT")),
        score=int(data.get("score", 50) or 50),
        status=str(data.get("status", "WAIT")),
        engine=str(data.get("engine", "orchestrator_v3_dynamic")),
        bullish_score=float(data.get("bullish_score", 50.0) or 50.0),
        legacy_verdict=str(data.get("legacy_verdict", "n/a")),
        legacy_score=int(data.get("legacy_score", 50) or 50),
        top_reasons=[str(item) for item in data.get("top_reasons", [])],
        counter_reasons=[str(item) for item in data.get("counter_reasons", [])],
        contradictions=[str(item) for item in data.get("contradictions", [])],
        quality_gate_reasons=[str(item) for item in data.get("quality_gate_reasons", [])],
        components=[
            build_orchestrator_component_from_payload(item)
            for item in data.get("components", [])
            if isinstance(item, dict)
        ],
    )


def build_event_fact_from_payload(data: dict[str, Any]) -> NewsFact:
    return _build_news_fact_v3(
        title=str(data.get("title", "")),
        source=str(data.get("source", "Source inconnue")),
        source_url=str(data.get("source_url", "")),
        published_at=str(data.get("published_at", iso_now())),
        category=str(data.get("category", "gold")),
        actors=list(data.get("actors", [])),
        locations=list(data.get("locations", [])),
        themes=list(data.get("themes", [])),
        confirmation_level=str(data.get("confirmation_level", "source secondaire / a confirmer")),
        market_chain=str(data.get("market_chain", "Chaine marche indisponible.")),
        gold_impact=str(data.get("gold_impact", "Impact gold a confirmer.")),
        impact_bias=str(data.get("impact_bias", "mixte")),
        confidence=int(data.get("confidence", 50) or 50),
    )


def build_political_statement_from_payload(data: dict[str, Any]) -> PoliticalStatement:
    return PoliticalStatement(
        title=str(data.get("title", "")),
        source=str(data.get("source", "Source inconnue")),
        source_url=str(data.get("source_url", "")),
        published_at=str(data.get("published_at", iso_now())),
        theme=str(data.get("theme", "Political context")),
        validation_level=str(data.get("validation_level", "unconfirmed_headline")),
        source_tier=int(data.get("source_tier", 4) or 4),
        gold_impact=str(data.get("gold_impact", "Impact gold a confirmer.")),
        oil_impact=str(data.get("oil_impact", "Impact oil a confirmer.")),
        usd_impact=str(data.get("usd_impact", "Impact USD a confirmer.")),
        market_chain=str(data.get("market_chain", "Chaine marche indisponible.")),
        score=int(data.get("score", 0) or 0),
        confidence=int(data.get("confidence", 50) or 50),
    )


def build_bundle_from_payload(payload: dict[str, Any]) -> BriefingBundle:
    market_snapshot = payload.get("market_snapshot", {})
    gold_data = market_snapshot.get("xauusd_spot", {})
    weekend_gold_data = market_snapshot.get("weekend_gold", {})
    dxy_data = market_snapshot.get("dxy", {})
    us10y_data = market_snapshot.get("us10y_yield", {})
    official_macro_data = market_snapshot.get("official_macro_rates", {})
    cftc_positioning_payload = payload.get("cftc_positioning")
    etf_flows_payload = payload.get("etf_flows_analysis")
    macro_catalysts_payload = payload.get("macro_catalysts")
    data_quality_payload = payload.get("data_quality")
    trade_ledger_payload = payload.get("trade_ledger")
    orchestrator_payload = payload.get("orchestrator_decision")
    heuristic = payload.get("heuristic_bias", {})

    gold_price = float(gold_data.get("price", 0.0) or 0.0)
    gold_previous_close = float(gold_data.get("previous_close", gold_price) or gold_price)
    gold_points = build_price_points(gold_data.get("recent_closes", []))
    intraday_points = build_price_points(gold_data.get("intraday_candles", []))

    dxy_price = float(dxy_data.get("price", 0.0) or 0.0)
    dxy_change_pct = float(dxy_data.get("change_pct", 0.0) or 0.0)
    dxy_previous_close = dxy_price / (1 + (dxy_change_pct / 100)) if dxy_change_pct else dxy_price

    us10y_price = float(us10y_data.get("price", 0.0) or 0.0)
    us10y_change_bps = float(us10y_data.get("change_bps", 0.0) or 0.0)
    us10y_previous_close = us10y_price - (us10y_change_bps / 100.0)

    gold = SymbolSnapshot(
        symbol=str(gold_data.get("symbol", "XAU/USD")),
        label="XAU/USD Spot",
        price=gold_price,
        previous_close=gold_previous_close,
        change_abs=gold_price - gold_previous_close,
        change_pct=float(gold_data.get("change_pct", 0.0) or 0.0),
        period_change_pct=float(gold_data.get("short_term_change_pct", 0.0) or 0.0),
        day_high=parse_float(gold_data.get("day_high")),
        day_low=parse_float(gold_data.get("day_low")),
        support=parse_float(gold_data.get("support")),
        resistance=parse_float(gold_data.get("resistance")),
        fetched_at=str(payload.get("generated_at", iso_now())),
        points=gold_points or [PricePoint(timestamp=int(time.time()), close=gold_price)],
        intraday_points=intraday_points,
    )
    dxy = SymbolSnapshot(
        symbol=str(dxy_data.get("symbol", "DX-Y.NYB")),
        label="US Dollar Index",
        price=dxy_price,
        previous_close=dxy_previous_close,
        change_abs=dxy_price - dxy_previous_close,
        change_pct=dxy_change_pct,
        period_change_pct=dxy_change_pct,
        day_high=None,
        day_low=None,
        support=None,
        resistance=None,
        fetched_at=str(payload.get("generated_at", iso_now())),
        points=[PricePoint(timestamp=int(time.time()), close=dxy_price)],
    )
    us10y = SymbolSnapshot(
        symbol=str(us10y_data.get("symbol", "^TNX")),
        label="US 10Y",
        price=us10y_price,
        previous_close=us10y_previous_close,
        change_abs=us10y_price - us10y_previous_close,
        change_pct=0.0,
        period_change_pct=0.0,
        day_high=None,
        day_low=None,
        support=None,
        resistance=None,
        fetched_at=str(payload.get("generated_at", iso_now())),
        points=[PricePoint(timestamp=int(time.time()), close=us10y_price)],
    )
    weekend_gold = (
        WeekendGoldSnapshot(
            source_name=str(weekend_gold_data.get("source_name", "IG Weekend Gold")),
            source_url=str(weekend_gold_data.get("source_url", IG_WEEKEND_GOLD_URL)),
            sell=float(weekend_gold_data.get("sell", 0.0) or 0.0),
            buy=float(weekend_gold_data.get("buy", 0.0) or 0.0),
            mid=float(weekend_gold_data.get("mid", 0.0) or 0.0),
            spread=float(weekend_gold_data.get("spread", 0.0) or 0.0),
            change_abs=parse_float(weekend_gold_data.get("change_abs")),
            change_pct=parse_float(weekend_gold_data.get("change_pct")),
            day_high=parse_float(weekend_gold_data.get("day_high")),
            day_low=parse_float(weekend_gold_data.get("day_low")),
            long_pct=int(weekend_gold_data["long_pct"]) if weekend_gold_data.get("long_pct") is not None else None,
            short_pct=int(weekend_gold_data["short_pct"]) if weekend_gold_data.get("short_pct") is not None else None,
            fetched_at=str(weekend_gold_data.get("last_update", payload.get("generated_at", iso_now()))),
        )
        if isinstance(weekend_gold_data, dict) and weekend_gold_data.get("sell") and weekend_gold_data.get("buy")
        else None
    )

    news = [
        NewsItem(
            title=str(item.get("title", "")),
            source=str(item.get("source", "Source inconnue")),
            link=str(item.get("link", "")),
            published_at=str(item.get("published_at", iso_now())),
            category=str(item.get("category", "gold")),
            score=int(item.get("score", 0) or 0),
            score_reasons=list(item.get("score_reasons", [])),
        )
        for item in payload.get("headlines", [])
    ]

    geopolitical_payload = payload.get("geopolitical_analysis")
    geopolitical_analysis = (
        GeopoliticalAnalysis(
            score=int(geopolitical_payload.get("score", 50)),
            summary=str(geopolitical_payload.get("summary", "Lecture geopolitique indisponible.")),
            risk_off_status=str(geopolitical_payload.get("risk_off_status", "mitige")),
            central_bank_bias=str(geopolitical_payload.get("central_bank_bias", "mitige")),
            physical_demand_trend=str(geopolitical_payload.get("physical_demand_trend", "mixte")),
            large_speculators=str(geopolitical_payload.get("large_speculators", "mixte")),
            etf_flows=str(geopolitical_payload.get("etf_flows", "mixte")),
            comex_open_interest=str(geopolitical_payload.get("comex_open_interest", "mixte")),
            vix_tone=str(geopolitical_payload.get("vix_tone", "neutre")),
            event_watch=list(geopolitical_payload.get("event_watch", [])),
            reasons=list(geopolitical_payload.get("reasons", [])),
        )
        if isinstance(geopolitical_payload, dict)
        else None
    )
    market_regime_payload = payload.get("market_regime")
    market_regime = (
        MarketRegimeAnalysis(
            name=str(market_regime_payload.get("name", "Normal Macro")),
            status=str(market_regime_payload.get("status", "NORMAL")),
            score=int(market_regime_payload.get("score", 0) or 0),
            gold_impact=str(market_regime_payload.get("gold_impact", "neutre")),
            summary=str(market_regime_payload.get("summary", "Regime de marche indisponible.")),
            reasons=list(market_regime_payload.get("reasons", [])),
            trend=str(market_regime_payload.get("trend", "stable")),
            confirmed=bool(market_regime_payload.get("confirmed", False)),
            probabilities=dict(market_regime_payload.get("probabilities", {})),
            component_scores=dict(market_regime_payload.get("component_scores", {})),
        )
        if isinstance(market_regime_payload, dict)
        else None
    )
    official_macro_rates = (
        OfficialMacroRates(
            dgs10=build_macro_rate_from_payload(official_macro_data.get("dgs10"), FRED_SERIES_LABELS["DGS10"]),
            dgs2=build_macro_rate_from_payload(official_macro_data.get("dgs2"), FRED_SERIES_LABELS["DGS2"]),
            dgs3m=build_macro_rate_from_payload(official_macro_data.get("dgs3m"), FRED_SERIES_LABELS["DGS3MO"]),
            dgs30=build_macro_rate_from_payload(official_macro_data.get("dgs30"), FRED_SERIES_LABELS["DGS30"]),
            t10yie=build_macro_rate_from_payload(official_macro_data.get("t10yie"), FRED_SERIES_LABELS["T10YIE"]),
            dfii10=build_macro_rate_from_payload(official_macro_data.get("dfii10"), FRED_SERIES_LABELS["DFII10"]),
            yahoo_tnx_gap_bps=parse_float(official_macro_data.get("yahoo_tnx_gap_bps")),
        )
        if isinstance(official_macro_data, dict)
        else None
    )
    cftc_positioning = build_cftc_positioning_from_payload(cftc_positioning_payload)
    etf_flows_analysis = build_etf_flows_analysis_from_payload(etf_flows_payload)
    macro_catalysts = build_macro_catalyst_calendar_from_payload(macro_catalysts_payload)
    data_quality = build_data_quality_from_payload(data_quality_payload)
    trade_ledger = build_trade_ledger_from_payload(trade_ledger_payload)
    orchestrator_decision = build_orchestrator_decision_from_payload(orchestrator_payload)

    analysis = AnalysisResult(
        bias=str(heuristic.get("bias", "neutral")),
        score=int(heuristic.get("score", 0) or 0),
        confidence=int(heuristic.get("confidence", 50) or 50),
        reasons=list(heuristic.get("reasons", [])),
        bullish_news=[],
        bearish_news=[],
        neutral_news=[],
        geopolitical=geopolitical_analysis,
    )

    fundamental_payload = payload.get("fundamental_recommendation")
    fundamental_recommendation = (
        TradeRecommendation(
            mode=str(fundamental_payload.get("mode", "Fondamental")),
            verdict=str(fundamental_payload.get("verdict", "BUY")),
            score=int(fundamental_payload.get("score", 50) or 50),
            summary=str(fundamental_payload.get("summary", "Lecture fondamentale indisponible.")),
            reasons=list(fundamental_payload.get("reasons", [])),
            stop_loss=float(fundamental_payload.get("stop_loss", gold_price) or gold_price),
            take_profit_1=float(fundamental_payload.get("take_profit_1", gold_price) or gold_price),
            take_profit_2=float(fundamental_payload.get("take_profit_2", gold_price) or gold_price),
            source_note=str(fundamental_payload.get("source_note", "Snapshot precedent re-utilise.")),
        )
        if isinstance(fundamental_payload, dict)
        else None
    )
    technical_payload = payload.get("technical_recommendation")
    technical_recommendation = (
        TradeRecommendation(
            mode=str(technical_payload.get("mode", "Technique")),
            verdict=str(technical_payload.get("verdict", "BUY")),
            score=int(technical_payload.get("score", 50) or 50),
            summary=str(technical_payload.get("summary", "Lecture technique indisponible.")),
            reasons=list(technical_payload.get("reasons", [])),
            stop_loss=float(technical_payload.get("stop_loss", gold_price) or gold_price),
            take_profit_1=float(technical_payload.get("take_profit_1", gold_price) or gold_price),
            take_profit_2=float(technical_payload.get("take_profit_2", gold_price) or gold_price),
            source_note=str(technical_payload.get("source_note", "Snapshot precedent re-utilise.")),
        )
        if isinstance(technical_payload, dict)
        else None
    )
    technical_decision_payload = payload.get("technical_decision")
    technical_decision = (
        TechnicalDecision(
            status=str(technical_decision_payload.get("status", "WAIT")),
            direction=str(technical_decision_payload.get("direction", "WAIT")),
            structure=str(technical_decision_payload.get("structure", "range")),
            score=int(technical_decision_payload.get("score", 0) or 0),
            confidence=int(technical_decision_payload.get("confidence", 0) or 0),
            trigger=str(technical_decision_payload.get("trigger", "")),
            invalidation=str(technical_decision_payload.get("invalidation", "")),
            entry_zone_low=float(technical_decision_payload.get("entry_zone_low", gold_price) or gold_price),
            entry_zone_high=float(technical_decision_payload.get("entry_zone_high", gold_price) or gold_price),
            stop_loss=float(technical_decision_payload.get("stop_loss", gold_price) or gold_price),
            tp1=float(technical_decision_payload.get("tp1", gold_price) or gold_price),
            tp2=float(technical_decision_payload.get("tp2", gold_price) or gold_price),
            tp3=float(technical_decision_payload.get("tp3", gold_price) or gold_price),
            reasons=list(technical_decision_payload.get("reasons", [])),
            contradictions=list(technical_decision_payload.get("contradictions", [])),
        )
        if isinstance(technical_decision_payload, dict)
        else None
    )
    scenario_payload = payload.get("scenario_plan")
    scenario_plan = (
        ScenarioPlan(
            status=str(scenario_payload.get("status", "WAIT")),
            bias=str(scenario_payload.get("bias", "WAIT")),
            primary_scenario=str(scenario_payload.get("primary_scenario", "")),
            alternative_scenario=str(scenario_payload.get("alternative_scenario", "")),
            trigger=str(scenario_payload.get("trigger", "")),
            confirmation_required=list(scenario_payload.get("confirmation_required", [])),
            invalidation=str(scenario_payload.get("invalidation", "")),
            action=str(scenario_payload.get("action", "NO_TRADE")),
            confidence=int(scenario_payload.get("confidence", 0) or 0),
            validations=list(scenario_payload.get("validations", [])),
            contradictions=list(scenario_payload.get("contradictions", [])),
        )
        if isinstance(scenario_payload, dict)
        else None
    )
    global_payload = payload.get("global_recommendation")
    global_recommendation = (
        TradeRecommendation(
            mode=str(global_payload.get("mode", "Global")),
            verdict=str(global_payload.get("verdict", "BUY")),
            score=int(global_payload.get("score", 50) or 50),
            summary=str(global_payload.get("summary", "Lecture globale indisponible.")),
            reasons=list(global_payload.get("reasons", [])),
            stop_loss=float(global_payload.get("stop_loss", gold_price) or gold_price),
            take_profit_1=float(global_payload.get("take_profit_1", gold_price) or gold_price),
            take_profit_2=float(global_payload.get("take_profit_2", gold_price) or gold_price),
            source_note=str(global_payload.get("source_note", "Snapshot precedent re-utilise.")),
        )
        if isinstance(global_payload, dict)
        else None
    )
    technical_timeframes = [
        TechnicalReading(
            timeframe=str(item.get("timeframe", "")),
            close=float(item.get("close", 0.0) or 0.0),
            ema20=float(item.get("ema20", 0.0) or 0.0),
            ema50=float(item.get("ema50", 0.0) or 0.0),
            ema100=float(item.get("ema100", 0.0) or 0.0),
            ema200=float(item.get("ema200", 0.0) or 0.0),
            rsi7=float(item.get("rsi7", 0.0) or 0.0),
            macd_line=float(item.get("macd_line", 0.0) or 0.0),
            macd_signal=float(item.get("macd_signal", 0.0) or 0.0),
            macd_histogram=float(item.get("macd_histogram", 0.0) or 0.0),
            volume_ratio=float(item.get("volume_ratio", 0.0) or 0.0),
            atr14=float(item.get("atr14", 0.0) or 0.0),
            score=float(item.get("score", 0.0) or 0.0),
            verdict=str(item.get("verdict", "NEUTRAL")),
            reasons=list(item.get("reasons", [])),
        )
        for item in payload.get("technical_timeframes", [])
    ]
    agent_results = parse_agent_results(payload.get("agent_results", []))
    news_reaction_setup = build_news_reaction_from_payload(payload.get("news_reaction_setup"))
    reversal_engine = build_reversal_engine_from_payload(payload.get("reversal_engine"))
    event_facts = [
        build_event_fact_from_payload(item)
        for item in payload.get("event_facts", [])
        if isinstance(item, dict)
    ]
    political_statements = [
        build_political_statement_from_payload(item)
        for item in payload.get("political_statements", [])
        if isinstance(item, dict)
    ]
    if scenario_plan is None:
        scenario_plan = build_scenario_plan(
            gold,
            technical_decision,
            global_recommendation,
            fundamental_recommendation=fundamental_recommendation,
            cross_asset=cross_asset_analysis,
            market_regime=market_regime,
            event_facts=event_facts,
            data_quality=data_quality,
        )
        payload["scenario_plan"] = asdict(scenario_plan)

    return BriefingBundle(
        gold=gold,
        dxy=dxy,
        us10y=us10y,
        news=news,
        analysis=analysis,
        payload=payload,
        ai_analysis=payload.get("ai_summary"),
        geopolitical_analysis=geopolitical_analysis,
        fundamental_recommendation=fundamental_recommendation,
        technical_recommendation=technical_recommendation,
        technical_decision=technical_decision,
        scenario_plan=scenario_plan,
        global_recommendation=global_recommendation,
        technical_timeframes=technical_timeframes,
        executive_summary=str(payload.get("executive_summary", "")),
        official_macro_rates=official_macro_rates,
        cftc_positioning=cftc_positioning,
        etf_flows_analysis=etf_flows_analysis,
        macro_catalysts=macro_catalysts,
        data_quality=data_quality,
        weekend_gold=weekend_gold,
        market_regime=market_regime,
        event_facts=event_facts,
        political_statements=political_statements,
        agent_results=agent_results,
        trade_ledger=trade_ledger,
        orchestrator_decision=orchestrator_decision,
        news_reaction_setup=news_reaction_setup,
        reversal_engine=reversal_engine,
    )


def load_cached_bundle(data_json_path: Path | None = None) -> BriefingBundle | None:
    candidates: list[Path] = []
    if data_json_path is not None:
        candidates.append(data_json_path)
    default_path = Path("reports") / "xauusd_data.json"
    if default_path not in candidates:
        candidates.append(default_path)

    for candidate in candidates:
        if not candidate.exists():
            continue
        try:
            payload = json.loads(candidate.read_text(encoding="utf-8"))
            return build_bundle_from_payload(payload)
        except Exception:
            continue
    return None


def render_report(
    gold: SymbolSnapshot,
    dxy: SymbolSnapshot,
    us10y: SymbolSnapshot,
    news: list[NewsItem],
    analysis: AnalysisResult,
    ai_analysis: str | None,
    geopolitical_analysis: GeopoliticalAnalysis | None = None,
    fundamental_recommendation: TradeRecommendation | None = None,
    technical_recommendation: TradeRecommendation | None = None,
    global_recommendation: TradeRecommendation | None = None,
    executive_summary: str | None = None,
    real_yield: SymbolSnapshot | None = None,
    official_macro_rates: OfficialMacroRates | None = None,
    cftc_positioning: CFTCPositioning | None = None,
    etf_flows_analysis: ETFFlowsAnalysis | None = None,
    macro_catalysts: MacroCatalystCalendar | None = None,
    data_quality: DataQualitySnapshot | None = None,
    cross_asset_analysis: CrossAssetAnalysis | None = None,
    event_mode: EventModeAnalysis | None = None,
    weekend_gold: WeekendGoldSnapshot | None = None,
    market_regime: MarketRegimeAnalysis | None = None,
    event_facts: list[EventFact] | None = None,
    political_statements: list[PoliticalStatement] | None = None,
    agent_results: list[AgentResult] | None = None,
    trade_ledger: TradeLedgerSummary | None = None,
    orchestrator_decision: OrchestratorDecision | None = None,
) -> str:
    support = f"{gold.support:.2f}" if gold.support is not None else "n/a"
    resistance = f"{gold.resistance:.2f}" if gold.resistance is not None else "n/a"
    generated_at = iso_now().replace("+00:00", "Z")

    lines = [
        "# XAU/USD Market Briefing",
        "",
        f"Genere a {generated_at}",
        "",
        "## Resume Executif",
        executive_summary or "Resume indisponible.",
        "",
        "## Snapshot",
        f"- Source prix spot: Investing.com XAU/USD ({INVESTING_XAUUSD_URL})",
        format_price_line(gold),
        format_price_line(dxy),
        format_yield_line(us10y),
        (
            f"- 10Y reel US FRED DFII10: {real_yield.price:.2f}% ({real_yield.change_abs * 100:+.1f} bps)"
            if real_yield
            else "- 10Y reel US FRED DFII10: indisponible"
        ),
        f"- Zone technique courte: support ~ {support} / resistance ~ {resistance}",
        "",
        "## Lecture Rapide",
        f"- Score heuristique: {analysis.score}",
        f"- Confiance heuristique: {analysis.confidence}/100",
        f"- {heuristic_decision_sentence(analysis)}",
    ]

    if weekend_gold:
        weekend_delta = (
            f"{weekend_gold.change_abs:+.2f} / {weekend_gold.change_pct:+.2f}%"
            if weekend_gold.change_abs is not None and weekend_gold.change_pct is not None
            else "variation indisponible"
        )
        spot_gap = weekend_gold.mid - gold.price
        lines.extend(
            [
                "",
                "## Prix Week-end IG",
                f"- Source: {weekend_gold.source_name} ({weekend_gold.source_url})",
                f"- SELL: {weekend_gold.sell:.2f}",
                f"- BUY: {weekend_gold.buy:.2f}",
                f"- Mid indicatif: {weekend_gold.mid:.2f}",
                f"- Spread: {weekend_gold.spread:.2f}",
                f"- Variation IG: {weekend_delta}",
                f"- Ecart mid IG vs spot Investing.com: {spot_gap:+.2f}",
                f"- Range IG: {format_number(weekend_gold.day_low)} / {format_number(weekend_gold.day_high)}",
                "- Note: prix week-end IG indicatif, distinct du spot officiel semaine.",
            ]
        )

    if official_macro_rates:
        lines.extend(["", "## Macro Officiel FRED"])
        fred_rows = [
            ("DGS10", "10Y nominal US", official_macro_rates.dgs10),
            ("DGS2", "2Y nominal US", official_macro_rates.dgs2),
            ("T10YIE", "Inflation breakeven 10Y", official_macro_rates.t10yie),
            ("DFII10", "10Y reel US", official_macro_rates.dfii10),
        ]
        for symbol, label, snapshot in fred_rows:
            if snapshot is not None:
                lines.append(f"- {symbol} {label}: {snapshot.price:.2f}% ({snapshot.change_abs * 100:+.1f} bps) - FRED")
            else:
                lines.append(f"- {symbol} {label}: indisponible")
        if official_macro_rates.yahoo_tnx_gap_bps is not None:
            lines.append(f"- Ecart Yahoo ^TNX vs FRED DGS10: {official_macro_rates.yahoo_tnx_gap_bps:+.1f} bps")
        lines.append("- Politique source: FRED est la source officielle pour les taux; Yahoo ^TNX reste un controle.")

    if cftc_positioning:
        lines.extend(
            [
                "",
                "## COT Officiel CFTC",
                f"- Source: {cftc_positioning.source_url}",
                f"- Rapport: {cftc_positioning.report_date} | {cftc_positioning.market} | code {cftc_positioning.contract_code}",
                f"- Open interest: {cftc_positioning.open_interest:,} ({cftc_positioning.open_interest_change:+,} hebdo)",
                f"- Managed Money net: {cftc_positioning.managed_money_net:+,} ({cftc_positioning.managed_money_net_change:+,} hebdo, {cftc_positioning.managed_money_net_pct_oi:+.1f}% OI)",
                f"- Producer/Merchant net: {cftc_positioning.producer_net:+,} ({cftc_positioning.producer_net_change:+,} hebdo)",
                f"- Swap Dealers net: {cftc_positioning.swap_net:+,} ({cftc_positioning.swap_net_change:+,} hebdo)",
                f"- Non-reportable net: {cftc_positioning.non_reportable_net:+,} ({cftc_positioning.non_reportable_net_change:+,} hebdo)",
                f"- Score positioning: {cftc_positioning.score}/100 ({cftc_positioning.status})",
                f"- Lecture: {cftc_positioning.summary}",
            ]
        )

    if etf_flows_analysis:
        lines.extend(
            [
                "",
                "## ETF Flows Officiels",
                f"- Source: {etf_flows_analysis.source_name} ({etf_flows_analysis.source_url})",
                f"- Date: {etf_flows_analysis.as_of_date}",
                f"- Holdings globales: {format_number(etf_flows_analysis.global_holdings_tonnes, 2, 't')}",
                f"- Flux hebdo global: {format_signed_tonnes(etf_flows_analysis.global_weekly_demand_tonnes)}",
                f"- Flux mensuel global: {format_signed_tonnes(etf_flows_analysis.global_monthly_demand_tonnes)}",
                f"- Score ETF: {etf_flows_analysis.score}/100 ({etf_flows_analysis.status})",
                f"- Lecture: {etf_flows_analysis.summary}",
            ]
        )
        for record in etf_flows_analysis.holdings:
            lines.append(
                f"- {record.ticker}: holdings {format_number(record.holdings_tonnes, 2, 't')}, "
                f"jour {format_signed_tonnes(record.daily_flow_tonnes)}, "
                f"hebdo {format_signed_tonnes(record.weekly_flow_tonnes)}, "
                f"mensuel {format_signed_tonnes(record.monthly_flow_tonnes)}; source {record.source_name}"
            )

    if macro_catalysts:
        lines.extend(
            [
                "",
                "## Macro Catalysts",
                f"- Sources: {macro_catalysts.source_note}",
                f"- FedWatch: {macro_catalysts.fedwatch_status} ({macro_catalysts.fedwatch_source_url})",
                f"- Note FedWatch: {macro_catalysts.fedwatch_note}",
            ]
        )
        for catalyst in macro_catalysts.catalysts[:8]:
            lines.append(
                f"- {catalyst.event_type}: {catalyst.title} | {format_timestamp_for_humans(catalyst.scheduled_at)} "
                f"({format_macro_countdown(catalyst.minutes_to_event)}) | {catalyst.impact_level} | {catalyst.gold_impact}"
            )

    if data_quality:
        lines.extend(
            [
                "",
                "## Data Feed Governance",
                f"- Score qualite: {data_quality.score}/100 ({data_quality.status})",
                f"- Resume: {data_quality.summary}",
                "- Sources missing: " + (", ".join(data_quality.missing_sources) if data_quality.missing_sources else "aucune"),
                "- Sources stale: " + (", ".join(data_quality.stale_sources) if data_quality.stale_sources else "aucune"),
                "- Sources faibles: " + (", ".join(data_quality.weak_sources) if data_quality.weak_sources else "aucune"),
                "- Contradictions: " + ("; ".join(data_quality.contradictions) if data_quality.contradictions else "aucune"),
            ]
        )
        for snapshot in data_quality.snapshots:
            lines.append(
                f"- {snapshot.name}: {snapshot.status}, Tier {snapshot.tier}, categorie {snapshot.category}, "
                f"age {snapshot.age_minutes if snapshot.age_minutes is not None else 'n/a'} min, agents {', '.join(snapshot.allowed_agents[:3])}"
            )

    inspector_payload = build_monitoring_inspector_payload(
        generated_at,
        data_quality,
        agent_results or [],
        trade_ledger,
        orchestrator_decision,
        global_recommendation,
        market_regime,
    )
    lines.extend(
        [
            "",
            "## Monitoring / Audit Inspector",
            f"- Dernier refresh: {inspector_payload['last_refresh']}",
            f"- Data quality: {inspector_payload['data_quality_status']} {inspector_payload['data_quality_score']}/100",
            f"- Sources actives: {inspector_payload['source_counts']['active']} / {inspector_payload['source_counts']['total']}",
            f"- Sources en alerte: {inspector_payload['source_counts']['issues']} (missing {inspector_payload['source_counts']['missing']}, stale {inspector_payload['source_counts']['stale']}, weak {inspector_payload['source_counts']['weak']})",
            f"- Agents actifs: {inspector_payload['agents']['active']} / {inspector_payload['agents']['total']}",
            f"- Trades: actifs {inspector_payload['trades']['active']} / total {inspector_payload['trades']['total']}; gate {inspector_payload['trades']['quality_gate_status']}",
            f"- Audit log append-only: {AUDIT_LOG_PATH}",
        ]
    )
    for issue in inspector_payload["source_issues"][:5]:
        lines.append(f"- Source issue: {issue['name']} status {issue['status']} ({issue['value_summary']})")
    for output in inspector_payload["agents"]["outputs"][:8]:
        lines.append(
            f"- Agent {output['name']}: {output['bias']} {output['score']}/100, "
            f"confiance {output['confidence']}/100, status {output['status']}"
        )

    if orchestrator_decision:
        lines.extend(
            [
                "",
                "## Orchestrateur v3",
                f"- Statut: {orchestrator_decision.status}",
                f"- Verdict: {orchestrator_decision.verdict} {orchestrator_decision.score}/100",
                f"- Bullish score pondere: {orchestrator_decision.bullish_score:.1f}/100",
                f"- Ancien moteur: {orchestrator_decision.legacy_verdict} {orchestrator_decision.legacy_score}/100",
                "- Top raisons: " + ("; ".join(orchestrator_decision.top_reasons) if orchestrator_decision.top_reasons else "n/a"),
                "- Contre-signaux: " + ("; ".join(orchestrator_decision.counter_reasons) if orchestrator_decision.counter_reasons else "n/a"),
                "- Quality Gate: " + ("; ".join(orchestrator_decision.quality_gate_reasons) if orchestrator_decision.quality_gate_reasons else "n/a"),
            ]
        )
        for component in orchestrator_decision.components:
            lines.append(
                f"- {component.label}: {component.bias} {component.score}/100, poids {component.weight:.2f}, "
                f"contribution {component.contribution:.2f}, source {component.source}"
            )

    if trade_ledger:
        lines.extend(
            [
                "",
                "## Trade Ledger / Signal Locking",
                f"- Quality Gate: {trade_ledger.quality_gate_status}",
                f"- Ledger: {trade_ledger.ledger_path}",
                f"- Total: {trade_ledger.total_trades} | wins {trade_ledger.wins} | losses {trade_ledger.losses} | partials {trade_ledger.partials} | expired {trade_ledger.expired}",
                "- Raisons gate: " + ("; ".join(trade_ledger.quality_gate_reasons) if trade_ledger.quality_gate_reasons else "n/a"),
            ]
        )
        for plan in trade_ledger.recent_trades[:6]:
            lines.append(
                f"- {plan.trade_id}: {plan.direction} entry {plan.reference_price:.2f}, SL {plan.stop_loss:.2f}, "
                f"TP {plan.tp1:.2f}/{plan.tp2:.2f}/{plan.tp3:.2f}, status {plan.status}, outcome {plan.outcome}; {plan.outcome_reason}"
            )

    if global_recommendation:
        lines.extend(
            [
                "",
                "## Scoring Global Prioritaire",
                f"- Score: {global_recommendation.score}/100",
                f"- Position conseillee: {global_recommendation.verdict}",
                f"- SL: {global_recommendation.stop_loss:.2f}",
                f"- TP1: {global_recommendation.take_profit_1:.2f}",
                f"- TP2: {global_recommendation.take_profit_2:.2f}",
                f"- Resume: {global_recommendation.summary}",
            ]
        )

    if cross_asset_analysis:
        lines.extend(
            [
                "",
                "## Confirmation Cross-Asset",
                f"- Score: {cross_asset_analysis.score}/100 ({cross_asset_analysis.verdict}, {cross_asset_analysis.status})",
                f"- Lecture: {cross_asset_analysis.summary}",
                "- Confirmations: "
                + ("; ".join(cross_asset_analysis.confirmations) if cross_asset_analysis.confirmations else "aucune confirmation nette"),
                "- Contradictions: "
                + ("; ".join(cross_asset_analysis.contradictions) if cross_asset_analysis.contradictions else "aucune contradiction nette"),
            ]
        )
        for signal in cross_asset_analysis.signals[:8]:
            change = "n/a" if signal.change is None else f"{signal.change:+.2f}{signal.change_unit}"
            corr_30 = "n/a" if signal.corr_30 is None else f"{signal.corr_30:+.2f}"
            lines.append(f"- {signal.instrument}: {signal.signal} | var {change} | corr30 {corr_30} | {signal.reason}")

    if market_regime:
        lines.extend(
            [
                "",
                "## Regime de Marche",
                f"- Regime: {market_regime.name}",
                f"- Statut: {market_regime.status} ({market_regime.score}/100)",
                f"- Impact gold: {market_regime.gold_impact}",
                f"- Lecture: {market_regime.summary}",
            ]
        )
        if market_regime.reasons:
            lines.append("- Pourquoi:")
            for reason in market_regime.reasons:
                lines.append(f"  - {reason}")

    if event_mode:
        lines.extend(
            [
                "",
                "## Mode Event / Volatilite",
                f"- Statut: {event_mode.status} ({event_mode.score}/100)",
                f"- Action: {event_mode.action}",
                "- Raisons: " + "; ".join(event_mode.reasons),
            ]
        )

    if fundamental_recommendation:
        lines.extend(
            [
                "",
                "## Verdict Fondamental",
                f"- Score: {fundamental_recommendation.score}/100",
                f"- Verdict: {fundamental_recommendation.verdict}",
                f"- SL: {fundamental_recommendation.stop_loss:.2f}",
                f"- TP1: {fundamental_recommendation.take_profit_1:.2f}",
                f"- TP2: {fundamental_recommendation.take_profit_2:.2f}",
                f"- Resume: {fundamental_recommendation.summary}",
            ]
        )

    if technical_recommendation:
        lines.extend(
            [
                "",
                "## Verdict Technique",
                f"- Score: {technical_recommendation.score}/100",
                f"- Verdict: {technical_recommendation.verdict}",
                f"- SL: {technical_recommendation.stop_loss:.2f}",
                f"- TP1: {technical_recommendation.take_profit_1:.2f}",
                f"- TP2: {technical_recommendation.take_profit_2:.2f}",
                f"- Resume: {technical_recommendation.summary}",
            ]
        )

    if geopolitical_analysis:
        lines.extend(
            [
                "",
                "## Lecture Geopolitique, Sentiment & Flux",
                f"- Score: {geopolitical_analysis.score}/100",
                f"- Evenement risk-off actif: {geopolitical_analysis.risk_off_status}",
                f"- Sentiment banques centrales: {geopolitical_analysis.central_bank_bias}",
                f"- Achats physiques Chine/Inde/banques centrales: {geopolitical_analysis.physical_demand_trend}",
                f"- Large Speculators sur Gold Futures: {geopolitical_analysis.large_speculators}",
                f"- Flux ETF GLD/IAU: {geopolitical_analysis.etf_flows}",
                f"- Open interest COMEX: {geopolitical_analysis.comex_open_interest}",
                f"- VIX / peur de marche: {geopolitical_analysis.vix_tone}",
                f"- Resume: {geopolitical_analysis.summary}",
            ]
        )
        if geopolitical_analysis.reasons:
            lines.append("- Signaux geopolitiques dominants:")
            for reason in geopolitical_analysis.reasons:
                lines.append(f"  - {reason}")
        if geopolitical_analysis.event_watch:
            lines.append("- Evenements du jour / a surveiller:")
            for event in geopolitical_analysis.event_watch:
                lines.append(f"  - {clean_display_text(event)}")

    if event_facts:
        lines.extend(["", "## Event Facts"])
        for fact in event_facts[:6]:
            lines.append(f"- Fait detecte: {clean_display_text(fact.title)}")
            lines.append(f"  Source: {clean_display_text(fact.source)} ({fact.confirmation_level}, confiance {fact.confidence}/100)")
            lines.append(f"  Acteurs: {', '.join(fact.actors) or 'n/a'} | Lieux: {', '.join(fact.locations) or 'n/a'}")
            lines.append(f"  Themes: {', '.join(fact.themes) or 'n/a'}")
            lines.append(f"  Chaine marche: {fact.market_chain}")
            lines.append(f"  Impact gold ({fact.impact_bias}): {fact.gold_impact}")
            if fact.source_url:
                lines.append(f"  Source URL: {fact.source_url}")

    if political_statements:
        lines.extend(["", "## Trump / White House Political Statements"])
        for statement in political_statements[:5]:
            lines.append(f"- Declaration: {clean_display_text(statement.title)}")
            lines.append(
                f"  Source: {clean_display_text(statement.source)} "
                f"(tier {statement.source_tier}, {statement.validation_level}, confiance {statement.confidence}/100)"
            )
            lines.append(f"  Theme: {statement.theme}")
            lines.append(f"  Chaine marche: {statement.market_chain}")
            lines.append(f"  Impact gold: {statement.gold_impact}")
            lines.append(f"  Impact oil: {statement.oil_impact}")
            lines.append(f"  Impact USD: {statement.usd_impact}")
            if statement.source_url:
                lines.append(f"  Source URL: {statement.source_url}")

    if analysis.reasons:
        lines.append("- Facteurs dominants:")
        for reason in analysis.reasons:
            lines.append(f"  - {reason}")

    if agent_results:
        lines.extend(
            [
                "",
                "## Fondation multi-agents",
                "- Statut: orchestrateur actif; agents sources ponderes et reference initiale conservee en comparaison interne.",
            ]
        )
        for agent in agent_results:
            lines.append(f"- {agent.department} / {agent.name}: {agent.bias} {agent.score}/100, confiance {agent.confidence}/100 - {agent.summary}")
        contradictions = build_agent_contradictions(agent_results)
        if contradictions:
            lines.append("- Contradictions:")
            for contradiction in contradictions:
                lines.append(f"  - {contradiction}")

    lines.extend(["", "## Headlines expliquees"])
    headlines = render_news_lines(news, max_items=8)
    if headlines:
        lines.extend(headlines)
    else:
        lines.append("- Sources headlines indisponibles temporairement. Le rapport continue avec la lecture prix / DXY / taux / geo du moment.")

    if ai_analysis:
        lines.extend(["", "## Synthese IA", ai_analysis])

    lines.extend(
        [
            "",
            "## Avertissement",
            "Ce rapport sert d'aide a la lecture du marche. "
            "Ce n'est pas un conseil financier personnalise ni un signal de trading garanti.",
        ]
    )

    return "\n".join(lines)


def format_bias_label(bias: str) -> str:
    labels = {
        "bullish": "Haussier",
        "slightly bullish": "Haussier modeste",
        "bearish": "Baissier",
        "slightly bearish": "Baissier modeste",
        "neutral": "Neutre",
    }
    return labels.get(bias, bias.title())


def format_bias_class(bias: str) -> str:
    if "bullish" in bias:
        return "bullish"
    if "bearish" in bias:
        return "bearish"
    return "neutral"


def format_timestamp_for_humans(iso_text: str) -> str:
    try:
        dt = datetime.fromisoformat(iso_text.replace("Z", "+00:00"))
        return dt.astimezone().strftime("%d/%m/%Y %H:%M")
    except ValueError:
        return iso_text


def format_headline_tone(score: int) -> tuple[str, str]:
    if score > 0:
        return "positive", "Support pour l'or"
    if score < 0:
        return "negative", "Pression sur l'or"
    return "neutral", "Impact mixte"


def format_number(value: float | None, decimals: int = 2, suffix: str = "") -> str:
    if value is None:
        return "n/a"
    return f"{value:.{decimals}f}{suffix}"


def format_signed_tonnes(value: float | None) -> str:
    if value is None:
        return "n/a"
    return f"{value:+.2f}t"


def render_weekend_gold_proxy(snapshot: WeekendGoldSnapshot | None, spot: SymbolSnapshot) -> str:
    if snapshot is None:
        return ""

    delta_class = (
        "bullish"
        if snapshot.change_pct is not None and snapshot.change_pct > 0
        else "bearish"
        if snapshot.change_pct is not None and snapshot.change_pct < 0
        else "neutral"
    )
    variation = (
        f"{snapshot.change_abs:+.2f} / {snapshot.change_pct:+.2f}%"
        if snapshot.change_abs is not None and snapshot.change_pct is not None
        else "variation n/a"
    )
    sentiment = (
        f"{snapshot.long_pct}% long / {snapshot.short_pct}% short"
        if snapshot.long_pct is not None and snapshot.short_pct is not None
        else "sentiment clients n/a"
    )
    spot_gap = snapshot.mid - spot.price
    return f"""
    <div class="weekend-proxy">
      <div class="weekend-proxy-head">
        <div>
          <div class="section-kicker">Proxy week-end IG</div>
          <strong>{snapshot.mid:.2f}</strong>
        </div>
        <span class="{delta_class}">{variation}</span>
      </div>
      <div class="weekend-grid">
        <div><small>SELL</small><b>{snapshot.sell:.2f}</b></div>
        <div><small>BUY</small><b>{snapshot.buy:.2f}</b></div>
        <div><small>Spread</small><b>{snapshot.spread:.2f}</b></div>
        <div><small>Ecart spot</small><b>{spot_gap:+.2f}</b></div>
      </div>
      <div class="weekend-note">
        Range IG {format_number(snapshot.day_low)} / {format_number(snapshot.day_high)} · {html.escape(sentiment)}.
        Source <a href="{html.escape(snapshot.source_url)}" target="_blank" rel="noopener noreferrer">IG Weekend Gold</a>.
        Prix week-end indicatif, distinct du spot classique.
      </div>
    </div>
    """.strip()


def sparkline_svg(points: list[PricePoint]) -> str:
    closes = [point.close for point in points[-36:] if point.close is not None]
    width = 680
    height = 220
    padding = 18

    if len(closes) < 2:
        return (
            '<svg viewBox="0 0 680 220" role="img" aria-label="Serie indisponible">'
            '<rect width="680" height="220" fill="#fffdf8"></rect>'
            '<text x="340" y="116" text-anchor="middle" fill="#8a5b12" font-size="16"'
            ' font-family="JetBrains Mono, IBM Plex Mono, Courier New, monospace">'
            "Serie de prix indisponible"
            "</text></svg>"
        )

    minimum = min(closes)
    maximum = max(closes)
    spread = maximum - minimum or 1.0
    inner_width = width - (padding * 2)
    inner_height = height - (padding * 2)
    line_color = "#00ff88" if closes[-1] >= closes[0] else "#ff3c5a"

    polyline_points: list[str] = []
    for index, close in enumerate(closes):
        x = padding + (index / (len(closes) - 1)) * inner_width
        y = height - padding - ((close - minimum) / spread) * inner_height
        polyline_points.append(f"{x:.2f},{y:.2f}")

    last_x, last_y = polyline_points[-1].split(",")
    quarter_y = padding + (inner_height * 0.25)
    mid_y = padding + (inner_height * 0.50)
    three_quarter_y = padding + (inner_height * 0.75)

    return f"""
<svg viewBox="0 0 {width} {height}" role="img" aria-label="Evolution recente du prix de l'or">
  <rect width="{width}" height="{height}" fill="#fffdf8"></rect>
  <line x1="{padding}" y1="{padding}" x2="{padding}" y2="{height - padding}" stroke="#e7dccd" stroke-width="1"></line>
  <line x1="{padding}" y1="{quarter_y:.2f}" x2="{width - padding}" y2="{quarter_y:.2f}" stroke="#e7dccd" stroke-width="1"></line>
  <line x1="{padding}" y1="{mid_y:.2f}" x2="{width - padding}" y2="{mid_y:.2f}" stroke="#e7dccd" stroke-width="1"></line>
  <line x1="{padding}" y1="{three_quarter_y:.2f}" x2="{width - padding}" y2="{three_quarter_y:.2f}" stroke="#e7dccd" stroke-width="1"></line>
  <line x1="{padding}" y1="{last_y}" x2="{width - padding}" y2="{last_y}" stroke="#8a5b12" stroke-width="1" stroke-dasharray="6 6" opacity="0.75"></line>
  <polyline fill="none" stroke="{line_color}" stroke-width="3" stroke-linecap="square" stroke-linejoin="miter"
    points="{' '.join(polyline_points)}"></polyline>
  <rect x="{float(last_x) - 3:.2f}" y="{float(last_y) - 3:.2f}" width="6" height="6" fill="#8a5b12"></rect>
</svg>
""".strip()


def candlestick_svg(points: list[PricePoint], current_price: float) -> str:
    candles = [point for point in points[-48:] if point.open is not None]
    width = 940
    height = 320
    padding_left = 18
    padding_right = 74
    padding_top = 16
    padding_bottom = 26

    if len(candles) < 2:
        return (
            '<svg viewBox="0 0 940 320" role="img" aria-label="Bougies indisponibles">'
            '<rect width="940" height="320" fill="#0b0f17"></rect>'
            '<text x="470" y="164" text-anchor="middle" fill="#f3b35c" font-size="16"'
            ' font-family="JetBrains Mono, IBM Plex Mono, Courier New, monospace">'
            "Bougies intraday indisponibles"
            "</text></svg>"
        )

    lows = [point.low if point.low is not None else min(point.open or point.close, point.close) for point in candles]
    highs = [point.high if point.high is not None else max(point.open or point.close, point.close) for point in candles]
    lower_bound = min(min(lows), current_price)
    upper_bound = max(max(highs), current_price)
    spread = upper_bound - lower_bound or 1.0

    inner_width = width - padding_left - padding_right
    inner_height = height - padding_top - padding_bottom
    slot = inner_width / len(candles)
    body_width = max(4.0, min(10.0, slot * 0.55))

    def y_scale(value: float) -> float:
        return padding_top + ((upper_bound - value) / spread) * inner_height

    grid_lines = []
    for fraction in (0.0, 0.25, 0.5, 0.75, 1.0):
        y = padding_top + (inner_height * fraction)
        grid_lines.append(
            f'<line x1="{padding_left}" y1="{y:.2f}" x2="{width - padding_right}" y2="{y:.2f}" stroke="#202a3a" stroke-width="1"></line>'
        )

    candle_nodes: list[str] = []
    for index, candle in enumerate(candles):
        open_price = candle.open if candle.open is not None else candle.close
        close_price = candle.close
        high_price = candle.high if candle.high is not None else max(open_price, close_price)
        low_price = candle.low if candle.low is not None else min(open_price, close_price)
        x_center = padding_left + (index * slot) + (slot / 2)
        wick_top = y_scale(high_price)
        wick_bottom = y_scale(low_price)
        open_y = y_scale(open_price)
        close_y = y_scale(close_price)
        body_top = min(open_y, close_y)
        body_height = max(abs(close_y - open_y), 1.5)
        color = "#00ff88" if close_price >= open_price else "#ff3c5a"
        candle_nodes.append(
            f'<line x1="{x_center:.2f}" y1="{wick_top:.2f}" x2="{x_center:.2f}" y2="{wick_bottom:.2f}" stroke="{color}" stroke-width="1.4"></line>'
            f'<rect x="{(x_center - (body_width / 2)):.2f}" y="{body_top:.2f}" width="{body_width:.2f}" height="{body_height:.2f}" fill="{color}"></rect>'
        )

    price_y = y_scale(current_price)
    label_y = max(padding_top + 12, min(height - padding_bottom - 4, price_y - 6))
    price_line = (
        f'<line x1="{padding_left}" y1="{price_y:.2f}" x2="{width - padding_right}" y2="{price_y:.2f}" '
        'stroke="#f3b35c" stroke-width="1" stroke-dasharray="6 5"></line>'
        f'<rect x="{width - padding_right + 8:.2f}" y="{price_y - 11:.2f}" width="54" height="18" fill="#101722" stroke="#f3b35c" stroke-width="1"></rect>'
        f'<text x="{width - padding_right + 35:.2f}" y="{label_y:.2f}" text-anchor="middle" fill="#f3b35c" font-size="12"'
        ' font-family="JetBrains Mono, IBM Plex Mono, Courier New, monospace">'
        f"{current_price:.2f}</text>"
    )

    return f"""
<svg viewBox="0 0 {width} {height}" role="img" aria-label="Bougies intraday XAU/USD avec ligne de prix en temps reel">
  <rect width="{width}" height="{height}" fill="#0b0f17"></rect>
  {''.join(grid_lines)}
  {''.join(candle_nodes)}
  {price_line}
</svg>
""".strip()


def render_reasons_list(reasons: list[str]) -> str:
    items = "".join(f"<li>{html.escape(reason)}</li>" for reason in reasons)
    return f"<ul class=\"reason-list\">{items}</ul>"


def recommendation_css_class(verdict: str) -> str:
    upper = verdict.upper()
    if upper == "BUY" or upper.endswith("_BUY"):
        return "bullish"
    if upper == "SELL" or upper.endswith("_SELL"):
        return "bearish"
    return "neutral"


def render_trade_levels(recommendation: TradeRecommendation) -> str:
    return (
        '<div class="trade-levels">'
        f'<div><span>SL</span><strong>{recommendation.stop_loss:.2f}</strong></div>'
        f'<div><span>TP1</span><strong>{recommendation.take_profit_1:.2f}</strong></div>'
        f'<div><span>TP2</span><strong>{recommendation.take_profit_2:.2f}</strong></div>'
        "</div>"
    )


def render_trade_compact(recommendation: TradeRecommendation) -> str:
    badge_class = recommendation_css_class(recommendation.verdict)
    return f"""
    <article class="quick-card {badge_class}">
      <div class="quick-card-top">
        <div>
          <div class="section-kicker">{html.escape(recommendation.mode)}</div>
          <strong>{html.escape(recommendation.verdict)}</strong>
        </div>
        <div class="quick-score">{recommendation.score}<small>/100</small></div>
      </div>
      <div class="quick-level-row">
        <span>SL {recommendation.stop_loss:.2f}</span>
        <span>TP1 {recommendation.take_profit_1:.2f}</span>
        <span>TP2 {recommendation.take_profit_2:.2f}</span>
      </div>
    </article>
    """.strip()


def render_trade_card(recommendation: TradeRecommendation) -> str:
    badge_class = recommendation_css_class(recommendation.verdict)
    reasons = "".join(f"<li>{html.escape(reason)}</li>" for reason in recommendation.reasons[:3])
    mode_key = recommendation.mode.lower()
    card_id = "fundamental" if mode_key.startswith("fond") else "technical-card" if mode_key.startswith("tech") else ""
    id_attr = f' id="{card_id}"' if card_id else ""
    source_label = recommendation.source_note.split("+")[0].strip() if recommendation.source_note else "Source locale"
    return f"""
    <article{id_attr} class="trade-card {badge_class} anchor-target">
      <div class="trade-card-head">
        <div>
          <div class="section-kicker">{html.escape(recommendation.mode)}</div>
          <h2>{html.escape(recommendation.mode)} intraday</h2>
        </div>
        <div class="trade-score">{recommendation.score}<small>/100</small></div>
      </div>
      <div class="trade-verdict {badge_class}">{html.escape(recommendation.verdict)}</div>
      <div class="tag-row">
        <span class="source-tag">Source · {html.escape(source_label[:42])}</span>
        <span class="source-tag">Confiance · {recommendation.score}/100</span>
        <span class="source-tag {badge_class}">Live signal</span>
      </div>
      <p class="trade-summary">{html.escape(recommendation.summary)}</p>
      {render_trade_levels(recommendation)}
      <ul class="trade-reasons">{reasons}</ul>
      <div class="trade-footer">
        <span>Verdict: {html.escape(recommendation.verdict)}</span>
        <span>{html.escape(recommendation.source_note)}</span>
      </div>
    </article>
    """.strip()


def render_technical_decision_panel(decision: TechnicalDecision | None) -> str:
    if decision is None:
        return '<div class="empty-state">TechnicalDecisionEngine indisponible.</div>'
    tone = recommendation_css_class(decision.direction)
    reasons = "".join(f"<li>{html.escape(reason)}</li>" for reason in decision.reasons[:5])
    contradictions = "".join(f"<li>{html.escape(item)}</li>" for item in decision.contradictions[:5])
    contradictions_html = (
        f'<div class="technical-decision-block"><strong>Contradictions</strong><ul>{contradictions}</ul></div>'
        if contradictions
        else '<div class="technical-decision-block"><strong>Contradictions</strong><p>Aucune contradiction technique bloquante.</p></div>'
    )
    is_trade_signal = decision.status in {"TRADE_BUY", "TRADE_SELL"} and trade_direction_from_text(decision.direction)
    if is_trade_signal:
        levels_html = f"""
        <div class="trade-levels">
          <div><span>Zone entree</span><strong>{decision.entry_zone_low:.2f} / {decision.entry_zone_high:.2f}</strong></div>
          <div><span>SL</span><strong>{decision.stop_loss:.2f}</strong></div>
          <div><span>TP1</span><strong>{decision.tp1:.2f}</strong></div>
          <div><span>TP2</span><strong>{decision.tp2:.2f}</strong></div>
          <div><span>TP3</span><strong>{decision.tp3:.2f}</strong></div>
        </div>
        """.strip()
    else:
        levels_html = """
        <div class="decision-item">
          <strong>Niveaux non affiches comme trade</strong>
          <span>Le moteur technique est en surveillance. Les SL/TP ne sont publies que lorsque le statut devient TRADE_BUY ou TRADE_SELL.</span>
        </div>
        """.strip()
    return f"""
    <div class="technical-decision-card {tone}">
      <div class="technical-decision-head">
        <div>
          <div class="section-kicker">TechnicalDecisionEngine</div>
          <h3>{html.escape(decision.status)} · {html.escape(decision.structure)}</h3>
        </div>
        <div class="global-score">{decision.score}<small>/100</small></div>
      </div>
      {levels_html}
      <div class="technical-decision-block"><strong>Trigger</strong><p>{html.escape(decision.trigger)}</p></div>
      <div class="technical-decision-block"><strong>Invalidation</strong><p>{html.escape(decision.invalidation)}</p></div>
      <div class="technical-decision-block"><strong>Raisons</strong><ul>{reasons}</ul></div>
      {contradictions_html}
    </div>
    """.strip()


def render_scenario_plan_panel(plan: ScenarioPlan | None) -> str:
    if plan is None:
        return '<div class="empty-state">ScenarioEngine indisponible.</div>'
    tone = recommendation_css_class(plan.status)
    confirmations = "".join(f"<li>{html.escape(item)}</li>" for item in plan.confirmation_required[:5])
    validations = "".join(f"<li>{html.escape(item)}</li>" for item in plan.validations[:5])
    contradictions = "".join(f"<li>{html.escape(item)}</li>" for item in plan.contradictions[:6])
    validations_html = (
        f"<ul>{validations}</ul>" if validations else "<p>Aucune validation externe forte pour le moment.</p>"
    )
    contradictions_html = (
        f"<ul>{contradictions}</ul>" if contradictions else "<p>Aucune contradiction bloquante detectee.</p>"
    )
    return f"""
    <div class="scenario-plan-card {tone}">
      <div class="technical-decision-head">
        <div>
          <div class="section-kicker">ScenarioEngine v3</div>
          <h3>{html.escape(plan.status)} · biais {html.escape(plan.bias)}</h3>
        </div>
        <div class="global-score">{plan.confidence}<small>/100</small></div>
      </div>
      <div class="scenario-plan-grid">
        <div class="technical-decision-block"><strong>Scenario principal</strong><p>{html.escape(plan.primary_scenario)}</p></div>
        <div class="technical-decision-block"><strong>Scenario alternatif</strong><p>{html.escape(plan.alternative_scenario)}</p></div>
      </div>
      <div class="scenario-plan-grid">
        <div class="technical-decision-block"><strong>Declencheur</strong><p>{html.escape(plan.trigger)}</p></div>
        <div class="technical-decision-block"><strong>Invalidation</strong><p>{html.escape(plan.invalidation)}</p></div>
      </div>
      <div class="technical-decision-block"><strong>Confirmations requises</strong><ul>{confirmations}</ul></div>
      <div class="scenario-plan-grid">
        <div class="technical-decision-block"><strong>Validations</strong>{validations_html}</div>
        <div class="technical-decision-block"><strong>Contradictions</strong>{contradictions_html}</div>
      </div>
      <div class="trade-verdict {tone}">{html.escape(plan.action)}</div>
    </div>
    """.strip()


def render_tradingview_chart(symbol: str = "OANDA:XAUUSD", interval: str = "15") -> str:
    query = urllib.parse.urlencode(
        {
            "symbol": symbol,
            "interval": interval,
            "theme": "dark",
            "style": "1",
            "timezone": "Etc/UTC",
            "withdateranges": "1",
            "hide_side_toolbar": "0",
            "allow_symbol_change": "1",
            "save_image": "0",
            "locale": "en",
        }
    )
    src = f"https://www.tradingview.com/widgetembed/?{query}"
    return f"""
    <div class="tradingview-panel" data-provider="TradingView" data-symbol="{html.escape(symbol)}">
      <iframe
        title="TradingView XAU/USD live chart"
        src="{html.escape(src)}"
        loading="lazy"
        referrerpolicy="origin"
        allowtransparency="true"
        scrolling="no">
      </iframe>
      <div class="footer-note">Charte live TradingView. Les niveaux internes restent calcules par Fourniwell Signals et ne remplacent pas la lecture graphique utilisateur.</div>
    </div>
    """.strip()


def render_technical_table(readings: list[TechnicalReading]) -> str:
    rows = []
    for reading in readings:
        rows.append(
            f"""
            <tr>
              <td>{html.escape(reading.timeframe)}</td>
              <td>{reading.close:.2f}</td>
              <td>{reading.ema20:.2f} / {reading.ema50:.2f} / {reading.ema100:.2f} / {reading.ema200:.2f}</td>
              <td>{reading.rsi7:.1f}</td>
              <td>{reading.macd_histogram:+.2f}</td>
              <td>x{reading.volume_ratio:.2f}</td>
              <td class="{recommendation_css_class(reading.verdict)}">{html.escape(reading.verdict)}</td>
            </tr>
            """.strip()
        )
    return (
        '<div class="table-wrap"><table class="technical-table">'
        "<thead><tr><th>TF</th><th>Close</th><th>EMA 20/50/100/200</th><th>RSI7</th><th>MACD hist</th><th>Volume</th><th>Verdict</th></tr></thead>"
        f"<tbody>{''.join(rows)}</tbody></table></div>"
    )


def render_geopolitical_panel(analysis: GeopoliticalAnalysis | None) -> str:
    if analysis is None:
        return '<div class="footer-note">Analyse geopolitique indisponible.</div>'

    status_rows = [
        ("Risk-off", analysis.risk_off_status),
        ("Banques centrales", analysis.central_bank_bias),
        ("Achats physiques", analysis.physical_demand_trend),
        ("Large Specs", analysis.large_speculators),
        ("ETF GLD/IAU", analysis.etf_flows),
        ("Open Interest", analysis.comex_open_interest),
        ("VIX", analysis.vix_tone),
    ]
    status_cells = "".join(
        f'<div class="geo-stat"><strong>{html.escape(label)}</strong><span>{html.escape(value)}</span></div>'
        for label, value in status_rows
    )
    reasons = "".join(f"<li>{html.escape(reason)}</li>" for reason in analysis.reasons[:6]) or "<li>Aucun signal geopol dominant.</li>"
    events = "".join(f"<li>{html.escape(clean_display_text(event))}</li>" for event in analysis.event_watch[:5]) or "<li>Aucun evenement majeur detecte.</li>"
    return (
        f'<div class="metric-footnote" style="margin-top:0;">Score geopol/sentiment/flux: {analysis.score}/100</div>'
        f'<p class="trade-summary" style="margin-top:8px;">{html.escape(analysis.summary)}</p>'
        f'<div class="geo-grid">{status_cells}</div>'
        f'<div class="geo-columns">'
        f'<div><div class="section-kicker">Signaux</div><ul class="reason-list">{reasons}</ul></div>'
        f'<div><div class="section-kicker">Evenements du jour</div><ul class="reason-list">{events}</ul></div>'
        f"</div>"
    )


def render_cftc_positioning_panel(positioning: CFTCPositioning | None) -> str:
    if positioning is None:
        return (
            '<div class="empty-state">'
            "COT officiel CFTC indisponible pour le moment. Le dashboard conserve les proxies headlines, "
            "mais le FlowPositioningAgent attend la source officielle."
            "</div>"
        )

    status_class = "bullish" if positioning.score >= 56 else "bearish" if positioning.score <= 44 else "neutral"

    def row(label: str, net: int, change: int, long_value: int, short_value: int) -> str:
        change_class = "bullish" if change > 0 else "bearish" if change < 0 else "neutral"
        return f"""
        <tr>
          <td>{html.escape(label)}</td>
          <td>{long_value:,}</td>
          <td>{short_value:,}</td>
          <td class="{status_class if label == 'Managed Money' else ''}">{net:+,}</td>
          <td class="{change_class}">{change:+,}</td>
        </tr>
        """.strip()

    rows = [
        row("Managed Money", positioning.managed_money_net, positioning.managed_money_net_change, positioning.managed_money_long, positioning.managed_money_short),
        row("Producer/Merchant", positioning.producer_net, positioning.producer_net_change, positioning.producer_long, positioning.producer_short),
        row("Swap Dealers", positioning.swap_net, positioning.swap_net_change, positioning.swap_long, positioning.swap_short),
        row("Non-reportable", positioning.non_reportable_net, positioning.non_reportable_net_change, positioning.non_reportable_long, positioning.non_reportable_short),
    ]
    source_link = (
        f'<a href="{html.escape(positioning.source_url)}" target="_blank" rel="noopener noreferrer">Source CFTC officielle</a>'
        if positioning.source_url
        else ""
    )
    return f"""
    <div class="trade-verdict {status_class}">{html.escape(positioning.status)} · {positioning.score}/100</div>
    <p class="trade-summary">{html.escape(positioning.summary)}</p>
    <div class="geo-grid">
      <div class="geo-stat"><strong>Rapport</strong><span>{html.escape(positioning.report_date)}</span></div>
      <div class="geo-stat"><strong>Open interest</strong><span>{positioning.open_interest:,} ({positioning.open_interest_change:+,})</span></div>
      <div class="geo-stat"><strong>MM net / OI</strong><span>{positioning.managed_money_net_pct_oi:+.1f}%</span></div>
      <div class="geo-stat"><strong>MM percentile</strong><span>{positioning.managed_money_percentile_1y:.0f}/100</span><small>1 an</small></div>
      <div class="geo-stat"><strong>Producers percentile</strong><span>{positioning.producer_net_percentile_1y:.0f}/100</span><small>1 an</small></div>
      <div class="geo-stat"><strong>Code</strong><span>{html.escape(positioning.contract_code)}</span></div>
    </div>
    <div class="table-wrap">
      <table class="technical-table">
        <thead><tr><th>Categorie</th><th>Long</th><th>Short</th><th>Net</th><th>Var hebdo</th></tr></thead>
        <tbody>{''.join(rows)}</tbody>
      </table>
    </div>
    <div class="metric-footnote">{source_link}</div>
    """.strip()


def render_etf_flows_panel(analysis: ETFFlowsAnalysis | None) -> str:
    if analysis is None:
        return (
            '<div class="empty-state">'
            "ETF flows officiels indisponibles. Le terminal attend WGC/GLD/IAU avant de remplacer les proxies headlines."
            "</div>"
        )

    status_class = "bullish" if analysis.score >= 56 else "bearish" if analysis.score <= 44 else "neutral"
    rows = []
    for record in analysis.holdings:
        record_class = "bullish" if record.status == "inflows" else "bearish" if record.status == "outflows" else "neutral"
        rows.append(
            f"""
            <tr>
              <td><strong>{html.escape(record.ticker)}</strong><br><span class="soft">{html.escape(record.fund)}</span></td>
              <td>{format_number(record.holdings_tonnes, 2, 't')}</td>
              <td class="{record_class}">{format_signed_tonnes(record.daily_flow_tonnes)}</td>
              <td class="{record_class}">{format_signed_tonnes(record.weekly_flow_tonnes)}</td>
              <td class="{record_class}">{format_signed_tonnes(record.monthly_flow_tonnes)}</td>
              <td>{html.escape(record.source_name)}</td>
            </tr>
            """.strip()
        )
    source_link = (
        f'<a href="{html.escape(analysis.source_url)}" target="_blank" rel="noopener noreferrer">Source ETF officielle</a>'
        if analysis.source_url
        else ""
    )
    return f"""
    <div class="trade-verdict {status_class}">{html.escape(analysis.status)} · {analysis.score}/100</div>
    <p class="trade-summary">{html.escape(analysis.summary)}</p>
    <div class="geo-grid">
      <div class="geo-stat"><strong>Date WGC</strong><span>{html.escape(analysis.as_of_date or "n/a")}</span></div>
      <div class="geo-stat"><strong>Holdings globales</strong><span>{format_number(analysis.global_holdings_tonnes, 2, 't')}</span></div>
      <div class="geo-stat"><strong>Flux hebdo</strong><span>{format_signed_tonnes(analysis.global_weekly_demand_tonnes)}</span></div>
      <div class="geo-stat"><strong>Flux mensuel</strong><span>{format_signed_tonnes(analysis.global_monthly_demand_tonnes)}</span></div>
    </div>
    <div class="table-wrap">
      <table class="technical-table">
        <thead><tr><th>ETF</th><th>Holdings</th><th>Jour</th><th>Hebdo</th><th>Mensuel</th><th>Source</th></tr></thead>
        <tbody>{''.join(rows) or '<tr><td colspan="6">Aucun detail GLD/IAU disponible.</td></tr>'}</tbody>
      </table>
    </div>
    <div class="metric-footnote">{html.escape(analysis.source_name)} · {html.escape(analysis.source_note)} {source_link}</div>
    """.strip()


def macro_catalyst_gold_bias(event: MacroCatalyst) -> str:
    explicit = (event.expected_gold_bias or "").upper()
    if explicit in {"BULLISH", "BEARISH"}:
        return explicit
    text = f"{event.gold_impact} {event.why_it_matters} {event.title}".lower()
    bullish_terms = ["baisse de taux", "dovish", "lower yields", "dollar weaker", "support gold", "bullish"]
    bearish_terms = ["higher for longer", "hawkish", "strong dollar", "higher yields", "bearish"]
    if any(term in text for term in bullish_terms):
        return "BULLISH"
    if any(term in text for term in bearish_terms):
        return "BEARISH"
    return "NEUTRAL"


def empty_macro_value(value: str | None) -> str:
    value = (value or "").strip()
    return value if value else "indisponible"


def render_macro_catalysts_panel(calendar: MacroCatalystCalendar | None) -> str:
    if calendar is None:
        return (
            '<div class="empty-state">'
            "Calendrier macro officiel indisponible. Le MacroAgent conserve FRED/DXY/10Y, mais aucun countdown evenementiel n'est actif."
            "</div>"
        )

    next_event = next(
        (event for event in calendar.catalysts if event.minutes_to_event is None or event.minutes_to_event >= 0),
        calendar.catalysts[0] if calendar.catalysts else None,
    )
    top_summary = (
        f"{next_event.event_type}: {next_event.title} · {format_macro_countdown(next_event.minutes_to_event)}"
        if next_event is not None
        else "Aucun evenement macro source."
    )
    rows = []
    for event in calendar.catalysts[:8]:
        bias = macro_catalyst_gold_bias(event)
        status_class = "bullish" if bias == "BULLISH" else "bearish" if bias == "BEARISH" else "neutral"
        rows.append(
            f"""
            <article class="macro-event-row">
              <div class="headline-meta">
                <span>{html.escape(event.source_name)}</span>
                <span>{html.escape(format_timestamp_for_humans(event.scheduled_at))} · {html.escape(format_macro_countdown(event.minutes_to_event))}</span>
              </div>
              <h3>{html.escape(event.title)}</h3>
              <div class="tag-row">
                <span class="source-tag">{html.escape(event.event_type)}</span>
                <span class="source-tag {status_class}">{html.escape(bias)}</span>
                <span class="source-tag">{html.escape(event.impact_level)}</span>
              </div>
              <div class="macro-values">
                <div><strong>Prevision</strong><span>{html.escape(empty_macro_value(event.forecast))}</span></div>
                <div><strong>Ancien</strong><span>{html.escape(empty_macro_value(event.previous))}</span></div>
                <div><strong>Actuel</strong><span>{html.escape(empty_macro_value(event.actual))}</span></div>
              </div>
              <p class="trade-summary"><strong>Impact attendu:</strong> {html.escape(event.gold_impact)}</p>
              <p class="footer-note"><strong>Pourquoi:</strong> {html.escape(event.why_it_matters)}</p>
            </article>
            """.strip()
        )
    fedwatch_link = (
        f'<a href="{html.escape(calendar.fedwatch_source_url)}" target="_blank" rel="noopener noreferrer">CME FedWatch officiel</a>'
        if calendar.fedwatch_source_url
        else "CME FedWatch officiel"
    )
    return f"""
    <div class="trade-verdict neutral">Macro Catalysts · {len(calendar.catalysts)} evenement(s)</div>
    <p class="trade-summary">{html.escape(top_summary)}</p>
    <div class="geo-grid">
      <div class="geo-stat"><strong>Prochain event</strong><span>{html.escape(next_event.event_type if next_event else "n/a")}</span></div>
      <div class="geo-stat"><strong>Countdown</strong><span>{html.escape(format_macro_countdown(next_event.minutes_to_event) if next_event else "n/a")}</span></div>
      <div class="geo-stat"><strong>Densite 24h</strong><span>{html.escape(calendar.density_status)}</span><small>{calendar.high_impact_24h} HIGH</small></div>
      <div class="geo-stat"><strong>Pre-event</strong><span>{'ON' if calendar.pre_event_active else 'OFF'}</span><small>{html.escape(calendar.pre_event_summary)}</small></div>
      <div class="geo-stat"><strong>FedWatch</strong><span>{html.escape(calendar.fedwatch_status)}</span></div>
      <div class="geo-stat"><strong>Refresh</strong><span>{html.escape(format_timestamp_for_humans(calendar.generated_at))}</span></div>
    </div>
    <div class="macro-event-list">{''.join(rows) or '<div class="empty-state">Aucun catalyseur macro disponible.</div>'}</div>
    <div class="metric-footnote">
      {html.escape(calendar.source_note)} {fedwatch_link}. {html.escape(calendar.fedwatch_note)}
    </div>
    """.strip()


def render_data_quality_panel(data_quality: DataQualitySnapshot | None) -> str:
    if data_quality is None:
        return '<div class="empty-state">Data quality indisponible: SourceRegistry non calcule sur ce snapshot.</div>'

    status_class = "bullish" if data_quality.score >= 80 else "neutral" if data_quality.score >= 60 else "bearish"
    preflight = data_quality.preflight
    preflight_class = (
        "bullish"
        if preflight and preflight.status == "READY"
        else "bearish"
        if preflight and preflight.trade_blocked
        else "neutral"
    )
    preflight_html = (
        f"""
        <div class="trade-verdict {preflight_class}">Preflight {html.escape(preflight.status)} · {'trade bloque' if preflight.trade_blocked else 'trade autorise cote data'}</div>
        <p class="footer-note">{html.escape(preflight.summary)}</p>
        """
        if preflight
        else '<div class="trade-verdict neutral">Preflight indisponible</div>'
    )
    rows = []
    for snapshot in data_quality.snapshots:
        row_class = "bullish" if snapshot.status == "ok" else "bearish" if snapshot.status in {"missing", "stale"} else "neutral"
        agents = ", ".join(snapshot.allowed_agents[:3])
        rows.append(
            f"""
            <tr>
              <td><strong>{html.escape(snapshot.name)}</strong><br><span class="soft">{html.escape(snapshot.category)} · Tier {snapshot.tier}</span></td>
              <td class="{row_class}">{html.escape(snapshot.status.upper())}</td>
              <td>{html.escape(format_timestamp_for_humans(snapshot.last_update) if snapshot.last_update else "n/a")}<br><span class="soft">{snapshot.age_minutes if snapshot.age_minutes is not None else "n/a"} min</span></td>
              <td>{html.escape(snapshot.value_summary)}</td>
              <td>{html.escape(agents)}</td>
            </tr>
            """.strip()
        )
    issue_items = data_quality.missing_sources + data_quality.stale_sources + data_quality.weak_sources + data_quality.contradictions
    issues = "".join(f"<li>{html.escape(item)}</li>" for item in issue_items[:8]) or "<li>Aucune faiblesse critique detectee.</li>"
    return f"""
    <div class="trade-verdict {status_class}">Data quality {html.escape(data_quality.status)} · {data_quality.score}/100</div>
    <p class="trade-summary">{html.escape(data_quality.summary)}</p>
    {preflight_html}
    <div class="geo-grid">
      <div class="geo-stat"><strong>Missing</strong><span>{len(data_quality.missing_sources)}</span></div>
      <div class="geo-stat"><strong>Stale</strong><span>{len(data_quality.stale_sources)}</span></div>
      <div class="geo-stat"><strong>Weak</strong><span>{len(data_quality.weak_sources)}</span></div>
      <div class="geo-stat"><strong>Contradictions</strong><span>{len(data_quality.contradictions)}</span></div>
    </div>
    <div class="geo-columns">
      <div><div class="section-kicker">Alertes sources</div><ul class="reason-list">{issues}</ul></div>
      <div><div class="section-kicker">Politique</div><p class="footer-note">Tier 1 = source officielle/primaire, Tier 2 = media ou donnees financieres fiables, Tier 3 = specialiste a verifier, Tier 4 = agregateur/faible. Un signal fort doit etre degrade si une source critique est absente ou stale.</p></div>
    </div>
    <div class="table-wrap">
      <table class="technical-table">
        <thead><tr><th>Source</th><th>Status</th><th>Fraicheur</th><th>Valeur utilisee</th><th>Agents autorises</th></tr></thead>
        <tbody>{''.join(rows)}</tbody>
      </table>
    </div>
    """.strip()


def render_chart_store_panel(chart_store: ChartStore | None) -> str:
    if chart_store is None:
        return '<div class="empty-state">Chart Store indisponible: aucune charte OHLC multi-timeframe chargee.</div>'
    status_class = "bullish" if chart_store.status == "READY" else "bearish" if chart_store.status in {"OFFLINE", "STALE"} else "neutral"
    rows = []
    for item in chart_store.timeframes:
        row_class = "bullish" if item.status == "READY" else "bearish" if item.status in {"OFFLINE", "STALE"} else "neutral"
        flags = "; ".join(item.quality_flags) if item.quality_flags else "aucune alerte"
        rows.append(
            f"""
            <tr>
              <td><strong>{html.escape(item.timeframe)}</strong></td>
              <td class="{row_class}">{html.escape(item.status)}</td>
              <td>{len(item.candles)}</td>
              <td>{html.escape(str(item.last_timestamp if item.last_timestamp is not None else 'n/a'))}</td>
              <td>{html.escape(str(item.freshness_minutes if item.freshness_minutes is not None else 'n/a'))} min</td>
              <td>{item.gap_count}</td>
              <td>{html.escape(flags)}</td>
            </tr>
            """.strip()
        )
    return f"""
    <div class="trade-verdict {status_class}">Chart Store {html.escape(chart_store.status)}</div>
    <p class="trade-summary">{html.escape(chart_store.summary)}</p>
    <div class="geo-grid">
      <div class="geo-stat"><strong>Source</strong><span>{html.escape(chart_store.source)}</span></div>
      <div class="geo-stat"><strong>Timeframes</strong><span>{len(chart_store.timeframes)}</span></div>
      <div class="geo-stat"><strong>Cache local</strong><span>{html.escape(str(CHART_STORE_CACHE_PATH))}</span></div>
    </div>
    <div class="table-wrap">
      <table class="technical-table">
        <thead><tr><th>TF</th><th>Status</th><th>Bougies</th><th>Derniere bougie</th><th>Freshness</th><th>Gaps</th><th>Qualite</th></tr></thead>
        <tbody>{''.join(rows) or '<tr><td colspan="7">Aucun timeframe disponible.</td></tr>'}</tbody>
      </table>
    </div>
    """.strip()


def render_monitoring_inspector_panel(
    generated_at: str,
    data_quality: DataQualitySnapshot | None,
    agent_results: list[AgentResult],
    trade_ledger: TradeLedgerSummary | None,
    orchestrator_decision: OrchestratorDecision | None,
    global_recommendation: TradeRecommendation | None,
    market_regime: MarketRegimeAnalysis | None,
    chart_store: ChartStore | None = None,
    strategy_candidates: list[SetupCandidate] | None = None,
    strategy_selection: StrategySelection | None = None,
) -> str:
    inspector = build_monitoring_inspector_payload(
        generated_at,
        data_quality,
        agent_results,
        trade_ledger,
        orchestrator_decision,
        global_recommendation,
        market_regime,
        chart_store,
        strategy_candidates,
        strategy_selection,
    )
    source_rows = []
    for snapshot in (data_quality.snapshots if data_quality else []):
        row_class = "bullish" if snapshot.status == "ok" else "bearish" if snapshot.status in {"missing", "stale"} else "neutral"
        source_rows.append(
            f"""
            <tr>
              <td><strong>{html.escape(snapshot.name)}</strong><br><span class="soft">{html.escape(snapshot.source_id)}</span></td>
              <td class="{row_class}">{html.escape(snapshot.status.upper())}</td>
              <td>{html.escape(snapshot.category)} · Tier {snapshot.tier}</td>
              <td>{html.escape(format_timestamp_for_humans(snapshot.last_update) if snapshot.last_update else "n/a")}<br><span class="soft">{snapshot.age_minutes if snapshot.age_minutes is not None else "n/a"} min</span></td>
              <td>{html.escape(snapshot.value_summary)}</td>
              <td>{html.escape(", ".join(snapshot.allowed_agents[:4]))}</td>
            </tr>
            """.strip()
        )

    agent_rows = []
    for agent in agent_results[:16]:
        agent_rows.append(
            f"""
            <tr>
              <td><strong>{html.escape(agent.name)}</strong><br><span class="soft">{html.escape(agent.department)}</span></td>
              <td>{html.escape(agent.status)}</td>
              <td class="{agent_css_class(agent.bias)}">{html.escape(agent.bias)} · {agent.score}/100</td>
              <td>{agent.confidence}/100</td>
              <td>{html.escape(agent.summary[:180])}</td>
              <td>{len(agent.evidence)} preuve(s) · {len(agent.risks)} risque(s)</td>
            </tr>
            """.strip()
        )

    trade_rows = []
    seen_trade_ids: set[str] = set()
    if trade_ledger:
        for plan in [*trade_ledger.active_trades, *trade_ledger.recent_trades]:
            if plan.trade_id in seen_trade_ids:
                continue
            seen_trade_ids.add(plan.trade_id)
            trade_rows.append(
                f"""
                <tr>
                  <td><strong>{html.escape(plan.trade_id)}</strong><br><span class="soft">{html.escape(format_timestamp_for_humans(plan.created_at))}</span></td>
                  <td>{html.escape(plan.direction)} @ {plan.reference_price:.2f}</td>
                  <td>SL {plan.stop_loss:.2f}<br>TP1 50% {plan.tp1:.2f}<br>TP2 30% {plan.tp2:.2f}<br>TP3 20% {plan.tp3:.2f}</td>
                  <td class="{trade_status_class(plan.status)}">{html.escape(plan.status)}</td>
                  <td>{html.escape(plan.outcome)}</td>
                  <td>{html.escape(plan.outcome_reason[:160])}</td>
                </tr>
                """.strip()
            )

    source_counts = inspector["source_counts"]
    trades = inspector["trades"]
    decision = inspector["decision"]
    preflight = inspector["preflight"]
    chart_payload = inspector["chart_store"]
    gate_reasons = "".join(f"<li>{html.escape(reason)}</li>" for reason in decision["quality_gate_reasons"][:6]) or "<li>Aucun blocage decisionnel signale.</li>"
    trade_gate_reasons = "".join(f"<li>{html.escape(reason)}</li>" for reason in trades["quality_gate_reasons"][:6]) or "<li>Aucune raison Trade Gate disponible.</li>"
    preflight_items = "".join(f"<li>{html.escape(item)}</li>" for item in [*preflight["blockers"], *preflight["warnings"]][:8]) or "<li>Aucun blocage preflight.</li>"
    source_issues = "".join(
        f"<li>{html.escape(issue['name'])}: {html.escape(issue['status'])} · {html.escape(issue['value_summary'])}</li>"
        for issue in inspector["source_issues"][:8]
    ) or "<li>Aucune source missing/stale/weak detectee.</li>"
    chart_rows = "".join(
        f"""
        <tr>
          <td><strong>{html.escape(item['timeframe'])}</strong></td>
          <td>{html.escape(item['status'])}</td>
          <td>{item['candles']}</td>
          <td>{html.escape(str(item['freshness_minutes'] if item['freshness_minutes'] is not None else 'n/a'))} min</td>
          <td>{item['gap_count']}</td>
          <td>{html.escape('; '.join(item['quality_flags']) if item['quality_flags'] else 'aucune alerte')}</td>
        </tr>
        """.strip()
        for item in chart_payload["timeframes"]
    )
    strategy = inspector["strategy"]
    shadow = inspector["strategy_shadow"]
    selected_setup = strategy["selected_setup"]
    if selected_setup:
        selected_summary = f"""
        <div class="trade-verdict {state_tone_class(strategy['status'])}">Multi-Strategy · {html.escape(strategy['status'])} · {html.escape(selected_setup['name'])} · {html.escape(selected_setup['direction'])} · {strategy['selected_score']}/100</div>
        <p class="trade-summary">{html.escape(' '.join(strategy['reasons'][:2]))}</p>
        <div class="geo-grid">
          <div class="geo-stat"><strong>Session</strong><span>{html.escape(strategy['session'])}</span></div>
          <div class="geo-stat"><strong>Entry zone</strong><span>{selected_setup['entry_zone_low']:.2f} / {selected_setup['entry_zone_high']:.2f}</span></div>
          <div class="geo-stat"><strong>SL</strong><span>{selected_setup['stop_loss']:.2f}</span></div>
          <div class="geo-stat"><strong>TP1 / TP2 / TP3</strong><span>{selected_setup['tp1']:.2f} / {selected_setup['tp2']:.2f} / {selected_setup['tp3']:.2f}</span><small>R/R TP1 {selected_setup['rr_tp1']:.2f}R</small></div>
        </div>
        """.strip()
    else:
        selected_summary = f"""
        <div class="trade-verdict neutral">Multi-Strategy · {html.escape(strategy['status'])}</div>
        <p class="trade-summary">{html.escape('; '.join(strategy['reasons']) if strategy['reasons'] else 'Aucun setup dominant selectionne pour ce snapshot.')}</p>
        """.strip()
    strategy_rows = []
    for item in [*strategy["ranked_candidates"], *strategy["rejected_candidates"]]:
        row_class = "bullish" if item["eligible"] and "BUY" in item["direction"] else "bearish" if item["eligible"] and "SELL" in item["direction"] else "neutral"
        details = "; ".join(item["reasons"][:2] or item["blockers"][:2])
        strategy_rows.append(
            f"""
            <tr>
              <td><strong>{html.escape(item['name'])}</strong><br><span class="soft">{'eligible' if item['eligible'] else 'rejetee'}</span></td>
              <td class="{row_class}">{html.escape(item['direction'])}</td>
              <td>{html.escape(item['status'])}</td>
              <td>{item['score']}/100</td>
              <td>{item['confidence']}/100 · conf. {item['confluence_score']}/100</td>
              <td>{item['rr_tp1']:.2f}R</td>
              <td>{html.escape(details[:220])}</td>
            </tr>
            """.strip()
        )

    return f"""
    <div class="trade-verdict {state_tone_class(decision['gate_status'])}">Inspector · {html.escape(decision['verdict'])} {decision['score']}/100 · Data quality {inspector['data_quality_score']}/100</div>
    <p class="trade-summary">Vue d'audit: elle explique quelles sources alimentent les agents, quel gate bloque ou valide la decision, et quels trades existent dans le ledger.</p>
    <div class="geo-grid">
      <div class="geo-stat"><strong>Dernier refresh</strong><span>{html.escape(format_timestamp_for_humans(inspector['last_refresh']))}</span></div>
      <div class="geo-stat"><strong>Sources actives</strong><span>{source_counts['active']} / {source_counts['total']}</span></div>
      <div class="geo-stat"><strong>Sources en alerte</strong><span>{source_counts['issues']}</span><small>missing {source_counts['missing']} · stale {source_counts['stale']} · weak {source_counts['weak']}</small></div>
      <div class="geo-stat"><strong>Agents actifs</strong><span>{inspector['agents']['active']} / {inspector['agents']['total']}</span></div>
      <div class="geo-stat"><strong>Trades crees</strong><span>{trades['total']}</span><small>actifs {trades['active']} · wins {trades['wins']} · losses {trades['losses']}</small></div>
      <div class="geo-stat"><strong>Preflight</strong><span>{html.escape(preflight['status'])}</span><small>{'trade bloque' if preflight['trade_blocked'] else 'data OK trade'}</small></div>
      <div class="geo-stat"><strong>Chart Store</strong><span>{html.escape(chart_payload['status'])}</span><small>{len(chart_payload['timeframes'])} TF</small></div>
      <div class="geo-stat"><strong>Audit log</strong><span>{html.escape(str(AUDIT_LOG_PATH))}</span><small>append-only JSONL</small></div>
    </div>
    <div class="module-block">
      <div class="section-kicker">Phase 7E · Integration controlee</div>
      <div class="trade-verdict {state_tone_class(shadow['status'])}">Shadow · {html.escape(shadow['status'])} · {html.escape(shadow['alignment'])}</div>
      <p class="trade-summary">{html.escape(' '.join(shadow['reasons'][:2]))}</p>
      <div class="geo-grid">
        <div class="geo-stat"><strong>Chef de file</strong><span>{html.escape(shadow['lead_verdict'])}</span><small>{shadow['lead_score']}/100</small></div>
        <div class="geo-stat"><strong>Setup shadow</strong><span>{html.escape(shadow['strategy_setup'])}</span><small>{html.escape(shadow['strategy_direction'])} · {shadow['strategy_score']}/100</small></div>
        <div class="geo-stat"><strong>Action</strong><span>{html.escape(shadow['final_action'])}</span><small>log only</small></div>
        <div class="geo-stat"><strong>Impact trade</strong><span>0</span><small>lead {str(shadow['allowed_to_affect_lead']).lower()} · lock {str(shadow['allowed_to_lock_trade']).lower()}</small></div>
      </div>
    </div>
    <div class="module-block">
      <div class="section-kicker">Phase 7D · Multi-Strategy Inspector</div>
      {selected_summary}
    </div>
    <div class="table-wrap">
      <table class="technical-table">
        <thead><tr><th>Setup</th><th>Direction</th><th>Status</th><th>Score</th><th>Confiance</th><th>R/R</th><th>Pourquoi</th></tr></thead>
        <tbody>{''.join(strategy_rows) or '<tr><td colspan="7">Aucune candidate multi-strategie disponible.</td></tr>'}</tbody>
      </table>
    </div>
    <div class="geo-columns">
      <div class="module-block">
        <div class="section-kicker">Preflight</div>
        <p class="footer-note">{html.escape(preflight['summary'])}</p>
        <ul class="reason-list">{preflight_items}</ul>
      </div>
      <div class="module-block">
        <div class="section-kicker">Erreurs / sources stale</div>
        <ul class="reason-list">{source_issues}</ul>
      </div>
      <div class="module-block">
        <div class="section-kicker">Decision Gate</div>
        <ul class="reason-list">{gate_reasons}</ul>
      </div>
      <div class="module-block">
        <div class="section-kicker">Trade Gate</div>
        <ul class="reason-list">{trade_gate_reasons}</ul>
      </div>
    </div>
    <div class="table-wrap">
      <table class="technical-table">
        <thead><tr><th>Source</th><th>Status</th><th>Categorie</th><th>Dernier refresh</th><th>Valeur</th><th>Agents</th></tr></thead>
        <tbody>{''.join(source_rows) or '<tr><td colspan="6">Aucune source auditable sur ce snapshot.</td></tr>'}</tbody>
      </table>
    </div>
    <div class="table-wrap">
      <table class="technical-table">
        <thead><tr><th>Chart TF</th><th>Status</th><th>Bougies</th><th>Freshness</th><th>Gaps</th><th>Qualite</th></tr></thead>
        <tbody>{chart_rows or '<tr><td colspan="6">Chart Store indisponible.</td></tr>'}</tbody>
      </table>
    </div>
    <div class="table-wrap">
      <table class="technical-table">
        <thead><tr><th>Agent</th><th>Status</th><th>Sortie</th><th>Confiance</th><th>Resume recent</th><th>Preuves / risques</th></tr></thead>
        <tbody>{''.join(agent_rows) or '<tr><td colspan="6">Aucun agent auditable sur ce snapshot.</td></tr>'}</tbody>
      </table>
    </div>
    <div class="table-wrap">
      <table class="technical-table">
        <thead><tr><th>Trade</th><th>Entry</th><th>SL et sorties partielles</th><th>Status</th><th>Outcome</th><th>Pourquoi</th></tr></thead>
        <tbody>{''.join(trade_rows) or '<tr><td colspan="6">Aucun trade cree dans le ledger.</td></tr>'}</tbody>
      </table>
    </div>
    """.strip()


def trade_status_class(status: str) -> str:
    if status in {"tp1_hit", "tp2_hit", "tp3_hit", "win", "partial"}:
        return "bullish"
    if status in {"sl_hit", "invalidated", "loss"}:
        return "bearish"
    if status in {"expired"}:
        return "caution"
    return "neutral"


def trade_direction_from_text(value: str) -> str:
    upper = (value or "").upper()
    if "BUY" in upper:
        return "BUY"
    if "SELL" in upper:
        return "SELL"
    return ""


def recommendation_levels_are_valid(recommendation: TradeRecommendation | None) -> bool:
    if recommendation is None:
        return False
    direction = trade_direction_from_text(recommendation.verdict)
    if direction == "BUY":
        return recommendation.stop_loss < recommendation.take_profit_1 < recommendation.take_profit_2
    if direction == "SELL":
        return recommendation.stop_loss > recommendation.take_profit_1 > recommendation.take_profit_2
    return False


def trade_plan_levels_are_valid(plan: TradePlan | None) -> bool:
    if plan is None:
        return False
    direction = trade_direction_from_text(plan.direction)
    entry = plan.reference_price
    if direction == "BUY":
        return plan.stop_loss < entry <= plan.tp1 < plan.tp2 < plan.tp3
    if direction == "SELL":
        return plan.stop_loss > entry >= plan.tp1 > plan.tp2 > plan.tp3
    return False


def visible_lead_status(
    global_recommendation: TradeRecommendation,
    orchestrator_decision: OrchestratorDecision | None,
) -> tuple[str, int, str]:
    if orchestrator_decision is not None:
        return orchestrator_decision.status, orchestrator_decision.score, orchestrator_decision.verdict
    return global_recommendation.verdict, global_recommendation.score, global_recommendation.verdict


def find_locked_trade_for_status(trade_ledger: TradeLedgerSummary | None, lead_status: str) -> TradePlan | None:
    direction = trade_direction_from_text(lead_status)
    if trade_ledger is None or direction not in {"BUY", "SELL"}:
        return None
    seen: set[str] = set()
    for plan in [*trade_ledger.active_trades, *trade_ledger.recent_trades]:
        if plan.trade_id in seen:
            continue
        seen.add(plan.trade_id)
        if plan.direction == direction and trade_plan_is_active(plan) and trade_plan_levels_are_valid(plan):
            return plan
    return None


def render_reversal_status(setup: ReversalSetup) -> str:
    if setup.status == "REVERSAL_BUY":
        return "REVERSAL BUY"
    if setup.status == "REVERSAL_SELL":
        return "REVERSAL SELL"
    return "NO REVERSAL TRADE"


def render_reversal_panels(reversal_engine: dict[str, ReversalSetup] | None) -> str:
    labels = [
        ("scalp", "Scalp Reversal"),
        ("intraday", "Intraday Reversal"),
        ("swing", "Swing Reversal"),
    ]
    cards: list[str] = []
    for key, label in labels:
        setup = (reversal_engine or {}).get(key)
        if setup is None:
            setup = reversal_no_trade(
                key,
                "NEUTRAL",
                {"scalp": "5m", "intraday": "15m", "swing": "1H"}[key],
                {"scalp": "15m", "intraday": "1H", "swing": "4H"}[key],
                {"scalp": 30, "intraday": 90, "swing": 720}[key],
                "Moteur reversal indisponible sur ce snapshot.",
            )
        status_label = render_reversal_status(setup)
        tone = "bullish" if setup.status == "REVERSAL_BUY" else "bearish" if setup.status == "REVERSAL_SELL" else "neutral"
        reason_items = "".join(f"<li>{html.escape(reason)}</li>" for reason in setup.reasons[:4])
        if not reason_items:
            reason_items = "<li>Aucune condition de retournement exploitable.</li>"
        levels = ""
        if setup.status in {"REVERSAL_BUY", "REVERSAL_SELL"}:
            levels = f"""
            <div class="trade-levels reversal-levels">
              <div><span>Entry</span><strong>{setup.entry_zone_low:.2f} / {setup.entry_zone_high:.2f}</strong></div>
              <div><span>SL</span><strong>{setup.stop_loss:.2f}</strong></div>
              <div><span>TP1 · 50%</span><strong>{setup.tp1:.2f}</strong></div>
              <div><span>TP2 · 30%</span><strong>{setup.tp2:.2f}</strong></div>
              <div><span>TP3 · 20%</span><strong>{setup.tp3:.2f}</strong></div>
            </div>
            """.strip()
        cards.append(
            f"""
            <div class="reversal-card {tone}">
              <div class="reversal-head">
                <div>
                  <strong>{html.escape(label)}</strong>
                  <span>{html.escape(setup.tf_signal)} avec contexte {html.escape(setup.tf_context)}</span>
                </div>
                <div class="trade-verdict {tone}">{html.escape(status_label)}</div>
              </div>
              <div class="reversal-meta">
                <span>Confluence {setup.confluence_score}/5</span>
                <span>Validite {setup.validity_minutes} min</span>
                <span>R/R TP1 {setup.risk_reward_tp1:.2f}R</span>
              </div>
              {levels}
              <ul class="reversal-reasons">{reason_items}</ul>
            </div>
            """.strip()
        )
    return f'<div class="reversal-grid">{"".join(cards)}</div>'


def render_desk_position_summary(
    global_recommendation: TradeRecommendation,
    orchestrator_decision: OrchestratorDecision | None,
    scenario_plan: ScenarioPlan | None,
    trade_ledger: TradeLedgerSummary | None = None,
) -> str:
    lead_status, lead_score, lead_bias = visible_lead_status(global_recommendation, orchestrator_decision)
    tone = state_tone_class(lead_status)
    trigger = scenario_plan.trigger if scenario_plan else "Attendre une confirmation prix + agents."
    invalidation = scenario_plan.invalidation if scenario_plan else "Signal invalide si les confirmations disparaissent."
    is_trade = lead_status in {"TRADE_BUY", "TRADE_SELL"}
    locked_trade = find_locked_trade_for_status(trade_ledger, lead_status)
    if locked_trade is not None:
        locked_at = format_timestamp_for_humans(locked_trade.created_at)
        level_html = f"""
        <div class="trade-levels trade-locked">
          <div><span>Entry</span><strong>{locked_trade.reference_price:.2f}</strong></div>
          <div><span>SL</span><strong>{locked_trade.stop_loss:.2f}</strong></div>
          <div><span>TP1 · 50%</span><strong>{locked_trade.tp1:.2f}</strong></div>
          <div><span>TP2 · 30%</span><strong>{locked_trade.tp2:.2f}</strong></div>
          <div><span>TP3 · 20%</span><strong>{locked_trade.tp3:.2f}</strong></div>
        </div>
        <p class="trade-summary">Position historisee depuis {html.escape(locked_at)} · R/R TP1 {locked_trade.risk_reward_tp1:.2f}R · ID {html.escape(locked_trade.trade_id)}.</p>
        """.strip()
    elif is_trade:
        level_html = f"""
        <div class="decision-item caution">
          <strong>Aucune position active</strong>
          <span>Le chef de file detecte {html.escape(lead_status)}, mais aucun TradePlan n'est encore historise.</span>
        </div>
        """.strip()
    else:
        level_html = f"""
        <div class="decision-item">
          <strong>Aucune position active</strong>
          <span>Chef de file {html.escape(lead_bias)} · {lead_score}/100.</span>
        </div>
        """.strip()
    return f"""
    <div class="global-position">
      <strong class="{tone}">{html.escape(lead_status)}</strong>
      <span>Chef de file: {html.escape(lead_bias)} · Score {lead_score}/100</span>
    </div>
    {level_html}
    <div class="scenario-plan-grid">
      <div class="technical-decision-block"><strong>Niveau utile</strong><p>{html.escape(trigger)}</p></div>
      <div class="technical-decision-block"><strong>Invalidation</strong><p>{html.escape(invalidation)}</p></div>
    </div>
    """.strip()


def render_signal_locked_panel(
    trade_ledger: TradeLedgerSummary | None,
    global_recommendation: TradeRecommendation,
    orchestrator_decision: OrchestratorDecision | None,
    scenario_plan: ScenarioPlan | None,
) -> str:
    active_valid = [
        plan for plan in (trade_ledger.active_trades if trade_ledger else []) if trade_plan_levels_are_valid(plan)
    ]
    if active_valid:
        plan = active_valid[0]
        return f"""
        <div class="trade-verdict bullish">Signal locked · {html.escape(plan.direction)}</div>
        <div class="trade-levels">
          <div><span>Entry</span><strong>{plan.reference_price:.2f}</strong></div>
          <div><span>SL</span><strong>{plan.stop_loss:.2f}</strong></div>
          <div><span>TP1 · 50%</span><strong>{plan.tp1:.2f}</strong></div>
          <div><span>TP2 · 30%</span><strong>{plan.tp2:.2f}</strong></div>
          <div><span>TP3 · 20%</span><strong>{plan.tp3:.2f}</strong></div>
        </div>
        <p class="footer-note">Plan de sortie: fermer 50% a TP1, 30% a TP2, laisser 20% vers TP3.</p>
        <p class="trade-summary">TradePlan historise: les niveaux restent fixes meme si le signal live change.</p>
        """.strip()
    return f"""
    <div class="trade-verdict neutral">AUCUNE POSITION ACTIVE</div>
    <p class="trade-summary">Aucun TradePlan n'est historise pour le moment.</p>
    """.strip()


def parse_news_sort_key(value: str) -> float:
    if not value:
        return 0.0
    try:
        return parsedate_to_datetime(value).timestamp()
    except Exception:
        pass
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00")).timestamp()
    except Exception:
        return 0.0


def news_impact_from_score(score: float | int | None, fallback: str = "NEUTRAL") -> str:
    if score is None:
        return fallback.upper()
    if score > 0:
        return "BULLISH"
    if score < 0:
        return "BEARISH"
    return fallback.upper()


def summarize_headline_for_user(title: str, source: str, category: str = "") -> str:
    clean_title = compact_whitespace(title)
    clean_source = compact_whitespace(source)
    clean_category = compact_whitespace(category)
    if not clean_title:
        return "Résumé indisponible: le flux ne fournit pas de titre exploitable."
    prefix = f"{clean_source} rapporte" if clean_source else "Le flux rapporte"
    if clean_category:
        return f"{prefix}: {clean_title}. Sujet detecte: {clean_category}."
    return f"{prefix}: {clean_title}."


def news_reason_for_user(item: dict[str, Any]) -> str:
    detail = str(item.get("detail") or "").strip()
    if detail:
        return detail
    impact = str(item.get("impact", "NEUTRAL")).upper()
    if impact == "BULLISH":
        return "Impact XAU/USD: le titre contient un facteur qui peut soutenir l'or, mais il reste a confirmer par le prix et les agents."
    if impact == "BEARISH":
        return "Impact XAU/USD: le titre contient un facteur qui peut peser sur l'or, mais il reste a confirmer par le prix et les agents."
    return "Impact XAU/USD: aucune direction exploitable detectee."


def news_flow_entry_key(item: dict[str, Any]) -> str:
    title = strip_source_suffix(str(item.get("title", "")), str(item.get("source", "")))
    return normalize_title_for_dedupe(title)


def news_flow_kind_priority(kind: str) -> int:
    kind_lower = kind.lower()
    if "political" in kind_lower:
        return 4
    if "fact" in kind_lower:
        return 3
    if "geopolitical" in kind_lower:
        return 2
    return 1


def news_flow_entry_rank(item: dict[str, Any]) -> tuple[int, int, int, float]:
    source_tier = news_source_tier(str(item.get("source", "")), str(item.get("url", "")))
    confidence = int(item.get("confidence", 0) or 0)
    kind = str(item.get("kind", ""))
    published = parse_news_sort_key(str(item.get("published_at", "")))
    return (5 - source_tier, confidence, news_flow_kind_priority(kind), published)


def merge_news_flow_entries(entries: list[dict[str, Any]]) -> list[dict[str, Any]]:
    merged: dict[str, dict[str, Any]] = {}
    ordered_keys: list[str] = []
    for entry in entries:
        key = news_flow_entry_key(entry)
        if not key:
            continue
        matching_key = next(
            (
                existing
                for existing in ordered_keys
                if existing == key
                or existing.startswith(" ".join(key.split()[:7]))
                or key.startswith(" ".join(existing.split()[:7]))
                or news_similarity(existing, key) >= 0.82
            ),
            "",
        )
        target_key = matching_key or key
        kind = str(entry.get("kind", "Headline"))
        if not matching_key:
            copied = dict(entry)
            copied["kinds"] = [kind]
            merged[target_key] = copied
            ordered_keys.append(target_key)
            continue
        current = merged[target_key]
        kinds = unique_preserve_order([*current.get("kinds", [str(current.get("kind", "Headline"))]), kind])
        if news_flow_entry_rank(entry) > news_flow_entry_rank(current):
            replacement = dict(entry)
            replacement["kinds"] = kinds
            merged[target_key] = replacement
        else:
            current["kinds"] = kinds
        merged[target_key]["kind"] = " / ".join(merged[target_key]["kinds"])
        merged[target_key]["confidence"] = max(int(merged[target_key].get("confidence", 0) or 0), int(entry.get("confidence", 0) or 0))
    return list(merged.values())


def news_flow_card_summary(item: dict[str, Any]) -> str:
    summary = str(item.get("summary", "")).strip()
    title_key = normalize_title_for_dedupe(str(item.get("title", "")))
    summary_key = normalize_title_for_dedupe(summary)
    if title_key and title_key in summary_key:
        source = str(item.get("source", "Source inconnue"))
        kind = str(item.get("kind", "Headline"))
        return f"Information sourcee par {source}. Classification: {kind}."
    return summary


def render_news_flow_panel(
    news: list[NewsItem],
    event_facts: list[EventFact],
    political_statements: list[PoliticalStatement],
    limit: int = 12,
) -> str:
    entries: list[dict[str, Any]] = []
    for fact in event_facts:
        impact = getattr(fact, "impact_bias", "NEUTRAL").upper()
        if impact == "NEUTRAL":
            continue
        entries.append(
            {
                "title": fact.title,
                "source": fact.source,
                "published_at": fact.published_at,
                "impact": impact,
                "url": fact.source_url,
                "confidence": fact.confidence,
                "kind": "Fact",
                "summary": summarize_headline_for_user(fact.title, fact.source, ", ".join(fact.themes[:2])),
                "detail": fact.gold_impact,
            }
        )
    for statement in political_statements:
        impact = news_impact_from_score(statement.score)
        if impact == "NEUTRAL":
            continue
        entries.append(
            {
                "title": statement.title,
                "source": statement.source,
                "published_at": statement.published_at,
                "impact": impact,
                "url": statement.source_url,
                "confidence": statement.confidence,
                "kind": "Political",
                "summary": summarize_headline_for_user(statement.title, statement.source, statement.theme),
                "detail": statement.gold_impact,
            }
        )
    for item in news:
        if not is_news_item_exploitable(item):
            continue
        impact = news_impact_from_score(item.score)
        if impact == "NEUTRAL":
            continue
        entries.append(
            {
                "title": item.title,
                "source": item.source,
                "published_at": item.published_at,
                "impact": impact,
                "url": item.link,
                "confidence": min(100, max(30, 50 + abs(item.score) * 5)),
                "kind": logical_category(item) or "Headline",
                "summary": summarize_headline_for_user(item.title, item.source, logical_category(item)),
                "detail": "; ".join(item.score_reasons[:2]),
            }
        )

    entries = merge_news_flow_entries(entries)
    entries.sort(key=lambda item: parse_news_sort_key(str(item["published_at"])), reverse=True)
    cards = []
    for item in entries[:limit]:
        impact = str(item["impact"])
        tone = "bullish" if impact == "BULLISH" else "bearish" if impact == "BEARISH" else "neutral"
        link = (
            f'<a href="{html.escape(str(item["url"]))}" target="_blank" rel="noopener noreferrer">Ouvrir</a>'
            if item.get("url")
            else ""
        )
        cards.append(
            f"""
            <article class="headline-card {tone}">
              <div class="headline-meta">
                <span>{html.escape(str(item["source"]))}</span>
                <span>{html.escape(format_timestamp_for_humans(str(item["published_at"])))}</span>
              </div>
              <h3>{html.escape(str(item["title"]))}</h3>
              <p class="trade-summary"><strong>Résumé:</strong> {html.escape(news_flow_card_summary(item))}</p>
              <p class="footer-note"><strong>Lecture XAU/USD:</strong> {html.escape(news_reason_for_user(item))}</p>
              <div class="tag-row">
                <span class="source-tag {tone}">{impact}</span>
                <span class="source-tag">Confiance {int(item["confidence"])}/100</span>
                <span class="source-tag">{html.escape(str(item["kind"]))}</span>
              </div>
              {link}
            </article>
            """.strip()
        )
    if not cards:
        return '<div class="empty-state">Aucune news bullish ou bearish recente avec impact exploitable. Les headlines neutres restent masquees.</div>'
    return f"""
    <div class="footer-note">Flux trie par heure de publication. Les headlines neutres et le bruit interne sont masques par defaut.</div>
    <div class="headline-grid">{''.join(cards)}</div>
    """.strip()


def render_news_reaction_panel(setup: NewsReactionTradePlan | None) -> str:
    if setup is None:
        setup = empty_news_reaction_plan()
    tone = (
        "bullish"
        if setup.direction in {"BUY", "WATCH_BUY"}
        else "bearish"
        if setup.direction in {"SELL", "WATCH_SELL"}
        else "caution"
        if setup.status in {"WATCH", "SUSPENDED"}
        else "neutral"
    )
    latency = (
        f"{setup.latency_seconds:.0f}s"
        if setup.latency_seconds is not None and setup.latency_seconds < 3600
        else f"{setup.latency_seconds / 60:.0f} min"
        if setup.latency_seconds is not None
        else "n/a"
    )
    if setup.status == "TRADE_READY":
        status_text = "Exploitable maintenant"
        details = f"""
        <div class="trade-levels">
          <div><small>Entry</small><strong>{setup.entry_zone_low:.2f} / {setup.entry_zone_high:.2f}</strong></div>
          <div><small>SL</small><strong>{setup.stop_loss:.2f}</strong></div>
          <div><small>TP1</small><strong>{setup.tp1:.2f}</strong></div>
          <div><small>TP2</small><strong>{setup.tp2:.2f}</strong></div>
          <div><small>TP3</small><strong>{setup.tp3:.2f}</strong></div>
        </div>
        <p class="footer-note">R/R: TP1 {setup.risk_reward_tp1:.2f} · TP2 {setup.risk_reward_tp2:.2f} · TP3 {setup.risk_reward_tp3:.2f}</p>
        """.strip()
    elif setup.status == "NO_EVENT":
        status_text = "Aucun flash exploitable"
        details = '<div class="empty-state">Aucune news recente Tier 1-3 ne justifie un signal NEWS_REACTION.</div>'
    else:
        status_text = "Non exploitable pour le moment"
        blockers = "".join(f"<li>{html.escape(blocker)}</li>" for blocker in setup.blockers) or "<li>Confirmation incomplete.</li>"
        details = f"<ul>{blockers}</ul>"
    reasons = "".join(f"<li>{html.escape(reason)}</li>" for reason in setup.reasons[:5])
    source_link = (
        f'<a href="{html.escape(setup.source_url)}" target="_blank" rel="noopener noreferrer">Ouvrir la source</a>'
        if setup.source_url
        else ""
    )
    return f"""
    <div class="technical-decision-card {tone}">
      <div class="technical-decision-head">
        <div>
          <div class="tag-row">
            <span class="source-tag {tone}">NEWS_REACTION</span>
            <span class="source-tag">{html.escape(setup.status)}</span>
            <span class="source-tag">Latence {html.escape(latency)}</span>
          </div>
          <h3>{html.escape(status_text)}</h3>
          <p class="trade-summary"><strong>{html.escape(setup.direction)}</strong> · {html.escape(setup.event_type)} · confirmation {setup.confirmation_score}/4 · confiance {setup.confidence}/100</p>
        </div>
        <span class="score-badge">{setup.validity_minutes} min</span>
      </div>
      <h3>{html.escape(setup.title)}</h3>
      <p class="footer-note">Source: {html.escape(setup.source)} · valide jusqu'a {html.escape(format_timestamp_for_humans(setup.valid_until))}</p>
      {details}
      <div class="technical-decision-block"><strong>Pourquoi</strong><ul>{reasons}</ul></div>
      {source_link}
    </div>
    """.strip()


def render_agents_scoreboard_panel(agent_results: list[AgentResult], settings_payload: dict[str, Any] | None = None) -> str:
    if not agent_results:
        return '<div class="empty-state">Aucun agent disponible sur ce snapshot.</div>'
    settings = parse_user_settings(settings_payload)
    active_names = set(settings.active_agents)
    rows = []
    for agent in agent_results:
        tone = recommendation_css_class(agent.bias)
        enabled = agent.name in active_names and agent.status != "OFF"
        toggle_label = "ON" if enabled else "OFF"
        toggle_class = "on" if enabled else "off"
        rows.append(
            f"""
            <tr>
              <td>
                <button class="agent-toggle {toggle_class}" type="button" data-agent-toggle="{html.escape(agent.name)}" data-agent-enabled="{'true' if enabled else 'false'}" aria-label="Activer ou desactiver {html.escape(agent.name)}">{toggle_label}</button>
              </td>
              <td><strong>{html.escape(agent.department)}</strong><br><span class="soft">{html.escape(agent.name)}</span></td>
              <td class="{tone}">{html.escape(agent.bias)}</td>
              <td>{agent.score}/100</td>
              <td>{agent.confidence}/100</td>
              <td>{html.escape(agent.summary[:170])}</td>
            </tr>
            """.strip()
        )
    return f"""
    <div class="table-wrap">
      <table class="technical-table">
        <thead><tr><th>Actif</th><th>Departement</th><th>Position</th><th>Score</th><th>Confiance</th><th>Resume</th></tr></thead>
        <tbody>{''.join(rows)}</tbody>
      </table>
    </div>
    """.strip()


def render_trade_tracker_panel(ledger: TradeLedgerSummary | None) -> str:
    if ledger is None:
        return '<div class="empty-state">Trade Ledger indisponible. Aucun trade plan verrouille sur ce snapshot.</div>'

    active_rows = []
    for plan in ledger.active_trades:
        active_rows.append(
            f"""
            <tr>
              <td><strong>{html.escape(plan.direction)}</strong><br><span class="soft">{html.escape(plan.trade_id)}</span></td>
              <td>{plan.reference_price:.2f}<br><span class="soft">{plan.entry_zone_low:.2f} / {plan.entry_zone_high:.2f}</span></td>
              <td>{plan.stop_loss:.2f}</td>
              <td>TP1 50%: {plan.tp1:.2f}<br>TP2 30%: {plan.tp2:.2f}<br>TP3 20%: {plan.tp3:.2f}</td>
              <td class="{trade_status_class(plan.status)}">{html.escape(plan.status)}</td>
              <td>{html.escape(plan.outcome_reason[:120])}</td>
            </tr>
            """.strip()
        )

    recent_rows = []
    for plan in ledger.recent_trades[:8]:
        recent_rows.append(
            f"""
            <tr>
              <td>{html.escape(format_timestamp_for_humans(plan.created_at))}</td>
              <td>{html.escape(plan.direction)}</td>
              <td>{plan.reference_price:.2f}</td>
              <td class="{trade_status_class(plan.status)}">{html.escape(plan.status)}</td>
              <td>{html.escape(plan.outcome)}</td>
              <td>{plan.r_multiple:+.2f}R</td>
              <td>{html.escape(plan.record_type)}</td>
            </tr>
            """.strip()
        )
    post_mortem_rows = []
    for item in ledger.post_mortems[:6]:
        post_mortem_rows.append(
            f"""
            <tr>
              <td><strong>{html.escape(item.direction)}</strong><br><span class="soft">{html.escape(item.trade_id)}</span></td>
              <td class="{trade_status_class(item.outcome)}">{html.escape(item.outcome)}</td>
              <td>{item.r_multiple:+.2f}R</td>
              <td>{item.duration_minutes} min</td>
              <td>{html.escape(item.summary[:180])}</td>
              <td>{html.escape(item.missed_condition[:140])}</td>
            </tr>
            """.strip()
        )

    gate_reasons = "".join(f"<li>{html.escape(reason)}</li>" for reason in ledger.quality_gate_reasons[:6]) or "<li>Quality Gate non evalue.</li>"
    return f"""
    <div class="trade-verdict neutral">Trade Tracker · {html.escape(ledger.quality_gate_status)} · {ledger.total_trades} plan(s)</div>
    <div class="tag-row">
      <span class="source-tag {'bullish' if ledger.active_trades else 'neutral'}">Trade locked · {len(ledger.active_trades)}</span>
      <span class="source-tag">Historique · {ledger.total_trades}</span>
      <span class="source-tag {state_tone_class(ledger.quality_gate_status)}">Gate · {html.escape(ledger.quality_gate_status)}</span>
    </div>
    <p class="trade-summary">Le signal live peut changer, mais chaque TradePlan conserve entry, SL, TP, sources et raison au moment de creation.</p>
    <div class="geo-grid">
      <div class="geo-stat"><strong>Wins</strong><span>{ledger.wins}</span></div>
      <div class="geo-stat"><strong>Losses</strong><span>{ledger.losses}</span></div>
      <div class="geo-stat"><strong>Partials</strong><span>{ledger.partials}</span></div>
      <div class="geo-stat"><strong>Expired</strong><span>{ledger.expired}</span></div>
      <div class="geo-stat"><strong>Win rate</strong><span>{ledger.stats.win_rate:.1f}%</span><small>Trades clos</small></div>
      <div class="geo-stat"><strong>Expectancy</strong><span>{ledger.stats.expectancy_r:+.2f}R</span><small>Moyenne outcomes clos</small></div>
      <div class="geo-stat"><strong>Duree moyenne</strong><span>{ledger.stats.average_duration_minutes} min</span><small>Trades clos</small></div>
      <div class="geo-stat"><strong>Setup -> trade</strong><span>{ledger.stats.setup_to_trade_rate:.1f}%</span><small>{ledger.stats.total_setups} setup(s)</small></div>
    </div>
    <div class="module-block">
      <div class="section-kicker">Quality Gate</div>
      <ul class="reason-list">{gate_reasons}</ul>
      <div class="metric-footnote">Ledger append-only: {html.escape(ledger.ledger_path)}</div>
    </div>
    <div class="table-wrap">
      <table class="technical-table">
        <thead><tr><th>Trade</th><th>Entry / zone</th><th>SL</th><th>Sorties partielles</th><th>Status</th><th>Outcome reason</th></tr></thead>
        <tbody>{''.join(active_rows) or '<tr><td colspan="6">Aucun trade actif verrouille pour le moment.</td></tr>'}</tbody>
      </table>
    </div>
    <div class="table-wrap">
      <table class="technical-table">
        <thead><tr><th>Cree</th><th>Direction</th><th>Entry</th><th>Status</th><th>Outcome</th><th>R</th><th>Type</th></tr></thead>
        <tbody>{''.join(recent_rows) or '<tr><td colspan="7">Historique vide.</td></tr>'}</tbody>
      </table>
    </div>
    <div class="table-wrap">
      <table class="technical-table">
        <thead><tr><th>Trade</th><th>Outcome</th><th>R</th><th>Duree</th><th>Post-mortem</th><th>Condition manquee</th></tr></thead>
        <tbody>{''.join(post_mortem_rows) or '<tr><td colspan="6">Aucun post-mortem disponible pour le moment.</td></tr>'}</tbody>
      </table>
    </div>
    """.strip()


def render_settings_panel(settings_payload: dict[str, Any] | None, validation_payload: dict[str, Any] | None) -> str:
    settings = parse_user_settings(settings_payload)
    validation_status = str((validation_payload or {}).get("status", "OK"))
    validation_warnings = [str(item) for item in (validation_payload or {}).get("warnings", [])]
    warning_items = "".join(f"<li>{html.escape(item)}</li>" for item in validation_warnings) or "<li>Aucun warning settings.</li>"
    active_agents = "".join(f"<span class=\"source-tag\">{html.escape(agent)}</span>" for agent in settings.active_agents)
    return f"""
    <section class="module-block">
      <div class="trade-verdict {state_tone_class(validation_status)}">Settings · {html.escape(validation_status)}</div>
      <p class="trade-summary">Les seuils utilisateur sont lus depuis {html.escape(str(SETTINGS_PATH))}. Modifier ce fichier permet d'ajuster le terminal sans toucher au code.</p>
      <div class="metric-strip">
        <div class="geo-stat"><strong>Mode</strong><span>{html.escape(settings.scoring_mode)}</span><small>Prudent ou agressif controle</small></div>
        <div class="geo-stat"><strong>Trade threshold</strong><span>{settings.trade_threshold}/100</span><small>Score minimal trade</small></div>
        <div class="geo-stat"><strong>WATCH threshold</strong><span>{settings.watch_threshold}/100</span><small>Score minimal surveillance</small></div>
        <div class="geo-stat"><strong>Cooldown</strong><span>{settings.cooldown_minutes} min</span><small>Anti-duplicat ledger</small></div>
        <div class="geo-stat"><strong>Cooldown loss/win/expired</strong><span>{settings.cooldown_after_loss_minutes}/{settings.cooldown_after_win_minutes}/{settings.cooldown_after_expired_minutes} min</span><small>Pause directionnelle</small></div>
        <div class="geo-stat"><strong>Max trades 24h</strong><span>{settings.max_trades_per_24h}</span><small>Circuit breaker</small></div>
        <div class="geo-stat"><strong>Data quality min</strong><span>{settings.min_data_quality}/100</span><small>Blocage trade</small></div>
        <div class="geo-stat"><strong>RR minimum</strong><span>{settings.minimum_risk_reward:.2f}R</span><small>TP1 minimal</small></div>
        <div class="geo-stat"><strong>Notifications</strong><span>{'ON' if settings.notifications_enabled else 'OFF'}</span><small>Reserve phase notification</small></div>
      </div>
      <div class="tag-row">{active_agents}</div>
      <div class="technical-decision-block"><strong>Validation</strong><ul>{warning_items}</ul></div>
    </section>
    """


def render_reports_v3_links_panel(exports_payload: list[dict[str, Any]] | None) -> str:
    exports = exports_payload if isinstance(exports_payload, list) else []
    if not exports:
        return '<div class="empty-state">Les exports v3 seront generes au prochain cycle complet.</div>'
    rows = []
    for export in exports:
        path = str(export.get("path", ""))
        label = str(export.get("label", Path(path).name or "rapport"))
        description = str(export.get("description", "Export local"))
        rows.append(
            f"""
            <tr>
              <td><strong>{html.escape(label)}</strong><br><span class="soft">{html.escape(description)}</span></td>
              <td><a href="{html.escape(path)}" target="_blank" rel="noopener noreferrer">{html.escape(path)}</a></td>
            </tr>
            """.strip()
        )
    return f"""
    <div class="table-wrap">
      <table class="technical-table">
        <thead><tr><th>Rapport</th><th>Chemin local</th></tr></thead>
        <tbody>{''.join(rows)}</tbody>
      </table>
    </div>
    """


def render_orchestrator_decision_panel(decision: OrchestratorDecision | None) -> str:
    if decision is None:
        return '<div class="empty-state">Orchestrateur v3 indisponible sur ce snapshot.</div>'
    rows = "".join(
        f"""
        <tr>
          <td><strong>{html.escape(component.label)}</strong><br><span class="soft">{html.escape(component.source)}</span></td>
          <td class="{recommendation_css_class(component.bias)}">{html.escape(component.bias)}</td>
          <td>{component.score}/100</td>
          <td>{component.weight:.2f}</td>
          <td>{component.contribution:.2f}</td>
          <td>{html.escape(component.reason[:120])}<br><span class="soft">{html.escape(component.weight_reason[:140])}</span></td>
        </tr>
        """.strip()
        for component in decision.components
    )
    top_reasons = "".join(f"<li>{html.escape(reason)}</li>" for reason in decision.top_reasons[:3]) or "<li>Aucune raison dominante.</li>"
    counter_reasons = "".join(f"<li>{html.escape(reason)}</li>" for reason in decision.counter_reasons[:3]) or "<li>Aucun contre-signal majeur.</li>"
    gate_reasons = "".join(f"<li>{html.escape(reason)}</li>" for reason in decision.quality_gate_reasons[:5]) or "<li>Quality Gate non evalue.</li>"
    badge_class = recommendation_css_class(decision.verdict)
    return f"""
    <div class="trade-verdict {badge_class}">Orchestrateur v3 · {html.escape(decision.verdict)} · {decision.score}/100 · {html.escape(decision.status)}</div>
    <div class="tag-row">
      <span class="source-tag">Engine · {html.escape(decision.engine)}</span>
      <span class="source-tag">Legacy · {html.escape(decision.legacy_verdict)} {decision.legacy_score}/100</span>
      <span class="source-tag {state_tone_class(decision.status)}">Decision v3 · {html.escape(decision.status)}</span>
    </div>
    <p class="trade-summary">
      Score pondere bullish {decision.bullish_score:.1f}/100. Ancien moteur:
      {html.escape(decision.legacy_verdict)} {decision.legacy_score}/100.
    </p>
    <div class="geo-grid">
      <div>
        <div class="section-kicker">Top 3 preuves</div>
        <ul class="reason-list">{top_reasons}</ul>
      </div>
      <div>
        <div class="section-kicker">Top 3 contre-signaux</div>
        <ul class="reason-list">{counter_reasons}</ul>
      </div>
      <div>
        <div class="section-kicker">Quality Gate final</div>
        <ul class="reason-list">{gate_reasons}</ul>
      </div>
    </div>
    <div class="table-wrap" style="margin-top:12px;">
      <table class="technical-table">
        <thead><tr><th>Composant</th><th>Biais</th><th>Score</th><th>Poids</th><th>Contribution</th><th>Raison</th></tr></thead>
        <tbody>{rows}</tbody>
      </table>
    </div>
    """.strip()


def state_tone_class(status: str) -> str:
    upper = status.upper()
    if upper in {"OK", "ONLINE", "VALIDATED", "ACTIVE", "LOCKED", "TRADE_BUY", "TRADE_SELL"}:
        return "bullish"
    if upper in {"WAIT", "CAUTION", "STALE", "MISSING", "FORCED", "WATCH_BUY", "WATCH_SELL"}:
        return "caution"
    if upper in {"ERROR", "WEAK", "BLOCKED", "NO_TRADE"}:
        return "bearish"
    return "neutral"


def render_terminal_state_board(
    global_recommendation: TradeRecommendation,
    trade_ledger: TradeLedgerSummary | None,
    data_quality: DataQualitySnapshot | None,
    orchestrator_decision: OrchestratorDecision | None,
    market_regime: MarketRegimeAnalysis | None,
) -> str:
    active_trades = len(trade_ledger.active_trades) if trade_ledger else 0
    source_alerts = 0
    source_status = "OK"
    source_detail = "Sources critiques utilisables"
    if data_quality is not None:
        source_alerts = len(data_quality.missing_sources) + len(data_quality.stale_sources)
        source_status = data_quality.status
        source_detail = f"{data_quality.score}/100 · missing {len(data_quality.missing_sources)} · stale {len(data_quality.stale_sources)}"
    contradiction_count = len(orchestrator_decision.contradictions) if orchestrator_decision else 0
    gate_status = orchestrator_decision.status if orchestrator_decision else "WAIT"
    wait_forced = global_recommendation.verdict in {"WAIT", "NO_TRADE"} or gate_status in {"WAIT", "NO_TRADE"}
    cards = [
        ("Live signal", global_recommendation.verdict, f"{global_recommendation.score}/100 · {global_recommendation.mode}", recommendation_css_class(global_recommendation.verdict)),
        ("Trade locked", "LOCKED" if active_trades else "WAIT", f"{active_trades} trade(s) actif(s)", "bullish" if active_trades else "neutral"),
        ("Sources", "STALE" if source_alerts else source_status, source_detail, "caution" if source_alerts else state_tone_class(source_status)),
        ("Contradictions", "ACTIVE" if contradiction_count else "OK", f"{contradiction_count} contradiction(s)", "caution" if contradiction_count else "bullish"),
        ("Quality gate", "NO_TRADE" if gate_status == "NO_TRADE" else "WAIT force" if wait_forced else gate_status, human_regime_name(market_regime.name if market_regime else "Normal Macro"), state_tone_class(gate_status)),
    ]
    nodes = "".join(
        f"""
        <div class="state-card {tone}">
          <small>{html.escape(label)}</small>
          <strong>{html.escape(status)}</strong>
          <span>{html.escape(detail)}</span>
        </div>
        """.strip()
        for label, status, detail, tone in cards
    )
    return f'<section class="state-board" aria-label="Etats visuels Fourniwell Signals">{nodes}</section>'


def render_cross_asset_panel(analysis: CrossAssetAnalysis | None, real_yield: SymbolSnapshot | None) -> str:
    if analysis is None:
        return '<div class="footer-note">Confirmations cross-asset indisponibles.</div>'

    def signal_class(signal: str) -> str:
        if signal == "BUY":
            return "bullish"
        if signal == "SELL":
            return "bearish"
        return "neutral"

    def format_change(signal: CorrelationSignal) -> str:
        if signal.change is None:
            return "n/a"
        return f"{signal.change:+.2f}{signal.change_unit}"

    def format_corr(value: float | None) -> str:
        return "n/a" if value is None else f"{value:+.2f}"

    def format_price(value: float | None) -> str:
        if value is None:
            return "n/a"
        if abs(value) >= 100:
            return f"{value:.2f}"
        return f"{value:.4f}".rstrip("0").rstrip(".")

    rows = []
    for signal in analysis.signals:
        css_class = signal_class(signal.signal)
        relation = "Inverse gold" if signal.expected_relation == "inverse" else "Suit gold"
        rows.append(
            f"""
            <tr>
              <td><strong>{html.escape(signal.instrument)}</strong><br><small>{html.escape(signal.symbol)}</small></td>
              <td>{html.escape(format_price(signal.price))}</td>
              <td class="{css_class}">{html.escape(format_change(signal))}</td>
              <td>{html.escape(relation)}</td>
              <td>{html.escape(format_corr(signal.corr_30))}</td>
              <td>{html.escape(format_corr(signal.corr_90))}</td>
              <td class="{css_class}"><strong>{html.escape(signal.signal)}</strong></td>
              <td>{signal.impact:+d}</td>
              <td>{html.escape(signal.reason)}</td>
            </tr>
            """.strip()
        )

    table = (
        '<div class="table-wrap"><table class="technical-table">'
        "<thead><tr><th>Instrument</th><th>Prix</th><th>Var</th><th>Relation</th><th>Corr 30j</th><th>Corr 90j</th><th>Signal</th><th>Poids</th><th>Lecture</th></tr></thead>"
        f"<tbody>{''.join(rows)}</tbody></table></div>"
    )

    real_yield_line = (
        f"10Y reel FRED: {real_yield.price:.2f}% ({real_yield.change_abs * 100:+.1f} bps)"
        if real_yield
        else "10Y reel FRED indisponible"
    )
    confirmations = "".join(f"<li>{html.escape(item)}</li>" for item in analysis.confirmations[:5]) or "<li>Aucune confirmation nette.</li>"
    contradictions = "".join(f"<li>{html.escape(item)}</li>" for item in analysis.contradictions[:5]) or "<li>Aucune contradiction nette.</li>"

    return f"""
    <div class="metric-footnote" style="margin-top:0;">Score correlations: {analysis.score}/100 &middot; {html.escape(analysis.verdict)} &middot; {html.escape(analysis.status)}</div>
    <p class="trade-summary" style="margin-top:8px;">{html.escape(analysis.summary)}</p>
    <div class="geo-grid">
      <div class="geo-stat"><strong>Verdict confluence</strong><span>{html.escape(analysis.verdict)}</span></div>
      <div class="geo-stat"><strong>10Y reel</strong><span>{html.escape(real_yield_line)}</span></div>
      <div class="geo-stat"><strong>Methode</strong><span>Relations attendues + variation du jour + correlations 30/90j.</span></div>
      <div class="geo-stat"><strong>Usage</strong><span>Renforce ou rejette le signal principal, sans remplacer le timing technique.</span></div>
    </div>
    {table}
    <div class="geo-columns">
      <div><div class="section-kicker">Confirmations</div><ul class="reason-list">{confirmations}</ul></div>
      <div><div class="section-kicker">Contradictions</div><ul class="reason-list">{contradictions}</ul></div>
    </div>
    """.strip()


def render_official_macro_panel(official_macro_rates: OfficialMacroRates | None, yahoo_us10y: SymbolSnapshot) -> str:
    def rate_cell(title: str, snapshot: SymbolSnapshot | None, source: str) -> str:
        if snapshot is None:
            return f'<div class="geo-stat"><strong>{html.escape(title)}</strong><span>indisponible</span></div>'
        return (
            f'<div class="geo-stat"><strong>{html.escape(title)}</strong>'
            f'<span>{snapshot.price:.2f}% ({snapshot.change_abs * 100:+.1f} bps)</span>'
            f'<small>{html.escape(source)} · {html.escape(format_timestamp_for_humans(snapshot.fetched_at))}</small></div>'
        )

    if official_macro_rates is None:
        return '<div class="footer-note">Bloc macro officiel FRED indisponible.</div>'

    gap_line = (
        f"{official_macro_rates.yahoo_tnx_gap_bps:+.1f} bps"
        if official_macro_rates.yahoo_tnx_gap_bps is not None
        else "indisponible"
    )
    return f"""
    <div class="geo-grid">
      {rate_cell("10Y nominal officiel", official_macro_rates.dgs10, "FRED DGS10")}
      {rate_cell("2Y nominal officiel", official_macro_rates.dgs2, "FRED DGS2")}
      {rate_cell("3M nominal officiel", official_macro_rates.dgs3m, "FRED DGS3MO")}
      {rate_cell("30Y nominal officiel", official_macro_rates.dgs30, "FRED DGS30")}
      {rate_cell("Breakeven inflation 10Y", official_macro_rates.t10yie, "FRED T10YIE")}
      {rate_cell("10Y reel officiel", official_macro_rates.dfii10, "FRED DFII10")}
      <div class="geo-stat"><strong>Controle Yahoo ^TNX</strong><span>{yahoo_us10y.price:.2f}%</span><small>Ecart vs FRED DGS10: {html.escape(gap_line)}</small></div>
      <div class="geo-stat"><strong>Politique source</strong><span>FRED prioritaire pour les taux; Yahoo reste controle de marche.</span></div>
    </div>
    """.strip()


def render_event_mode_panel(event_mode: EventModeAnalysis | None) -> str:
    if event_mode is None:
        return '<div class="footer-note">Mode event indisponible.</div>'

    badge_class = "bearish" if event_mode.active else "bullish"
    reasons = "".join(f"<li>{html.escape(reason)}</li>" for reason in event_mode.reasons[:5])
    return f"""
    <div class="trade-verdict {badge_class}">{html.escape(event_mode.status)} · {event_mode.score}/100</div>
    <p class="trade-summary">{html.escape(event_mode.action)}</p>
    <ul class="reason-list">{reasons}</ul>
    <div class="metric-footnote">Multiplicateur SL en regime event: x{event_mode.stop_multiplier:.1f}</div>
    """.strip()


def _trader_action_badge(action: str) -> str:
    colors = {
        "WATCH_BUY": "bull",
        "WATCH_SELL": "bear",
        "NO_TRADE": "muted",
        "WAIT": "muted",
    }
    css = colors.get(action, "muted")
    return f'<span class="badge badge-{css}">{html.escape(action)}</span>'


def render_event_facts_panel(event_facts: list[NewsFact]) -> str:
    cards: list[str] = []
    for fact in event_facts[:6]:
        tone_class = "bullish" if fact.impact_bias == "bullish" else "bearish" if fact.impact_bias == "bearish" else "neutral"
        source_link = (
            f'<a href="{html.escape(fact.source_url)}" target="_blank" rel="noopener noreferrer">Source</a>'
            if fact.source_url else ""
        )
        # Confirmation marche — affichage compact (NewsFact v3 uniquement)
        mc = getattr(fact, "market_confirmation", None)
        mc_html = (
            f'<p class="news-fact-confirmation">{html.escape(mc.summary)}</p>'
            if mc and mc.summary else ""
        )
        trader_action = getattr(fact, "trader_action", "WAIT")
        trader_action_detail = getattr(fact, "trader_action_detail", "")
        why_it_matters = getattr(fact, "why_it_matters", "")
        source_tier_label = getattr(fact, "source_tier_label", "")
        fact_type_label = getattr(fact, "fact_type_label", fact.confirmation_level)

        # Acteurs lisibles
        actors_str = html.escape(", ".join(fact.actors)) if fact.actors else ""

        cards.append(
            f"""
            <article class="headline-brief {tone_class}">
              <div class="headline-brief-top">
                <div class="headline-brief-source">
                  {html.escape(fact.source)}
                  {f'<span class="source-tier">{html.escape(source_tier_label)}</span>' if source_tier_label else ''}
                </div>
                <div class="headline-brief-time">{html.escape(format_timestamp_for_humans(fact.published_at))}</div>
              </div>
              <div class="section-kicker">
                {html.escape(fact_type_label)} · confiance {fact.confidence}/100
                {f'· {html.escape(actors_str)}' if actors_str else ''}
              </div>
              <h3>{html.escape(fact.title)}</h3>
              {f'<p class="news-fact-why"><strong>Pourquoi:</strong> {html.escape(why_it_matters)}</p>' if why_it_matters else ''}
              {mc_html}
              <p class="news-fact-impact"><strong>Impact or:</strong> {html.escape(fact.gold_impact)}</p>
              <div class="news-fact-action">
                {_trader_action_badge(trader_action)}
                {f'<span class="action-detail">{html.escape(trader_action_detail)}</span>' if trader_action_detail else ''}
              </div>
              {f'<div class="news-fact-link">{source_link}</div>' if source_link else ''}
            </article>
            """.strip()
        )

    if not cards:
        return (
            '<div class="empty-state">'
            "Aucun fait structure detecte. Headlines disponibles dans le bloc suivant."
            "</div>"
        )
    return '<div class="headline-grid">' + "".join(cards) + "</div>"


def render_political_statements_panel(statements: list[PoliticalStatement]) -> str:
    cards: list[str] = []
    for statement in statements[:5]:
        tone_class = "bullish" if statement.score > 0 else "bearish" if statement.score < 0 else "neutral"
        source_link = (
            f'<a href="{html.escape(statement.source_url)}" target="_blank" rel="noopener noreferrer">Ouvrir la source</a>'
            if statement.source_url
            else ""
        )
        cards.append(
            f"""
            <article class="headline-brief {tone_class}">
              <div class="headline-brief-top">
                <div class="headline-brief-source">{html.escape(statement.source)}</div>
                <div class="headline-brief-time">{html.escape(format_timestamp_for_humans(statement.published_at))}</div>
              </div>
              <div class="section-kicker">{html.escape(statement.theme)} · tier {statement.source_tier} · {html.escape(statement.validation_level)} · confiance {statement.confidence}/100</div>
              <h3>{html.escape(statement.title)}</h3>
              <p><strong>Chaine marche:</strong> {html.escape(statement.market_chain)}</p>
              <p><strong>Impact gold:</strong> {html.escape(statement.gold_impact)}</p>
              <p><strong>Impact oil:</strong> {html.escape(statement.oil_impact)}</p>
              <p><strong>Impact USD:</strong> {html.escape(statement.usd_impact)}</p>
              {source_link}
            </article>
            """.strip()
        )

    if not cards:
        return (
            '<div class="empty-state">'
            "Aucune declaration politique sourcee detectee pour le moment. "
            "L'agent reste en veille anti-rumeur."
            "</div>"
        )
    return '<div class="headline-grid">' + "".join(cards) + "</div>"


def render_market_regime_panel(regime: MarketRegimeAnalysis | None, cross_asset: CrossAssetAnalysis | None = None) -> str:
    if regime is None:
        return '<div class="footer-note">Regime de marche indisponible.</div>'

    display_name = human_regime_name(regime.name)
    badge_class = "bearish" if regime.name in {"Hormuz / Oil Shock", "Dollar Liquidity Squeeze"} else "bullish" if regime.name == "Safe-Haven Gold" else "neutral"
    reasons = "".join(f"<li>{html.escape(reason)}</li>" for reason in regime.reasons[:5]) or "<li>Aucune raison dominante.</li>"
    drivers = cross_asset.drivers if cross_asset else {}

    def oil_cell(key: str, label: str) -> str:
        driver = drivers.get(key, {})
        if not driver.get("available"):
            return f'<div class="geo-stat"><strong>{label}</strong><span>indisponible</span></div>'
        return (
            f'<div class="geo-stat"><strong>{label}</strong>'
            f'<span>{driver.get("price", "n/a")} · {driver.get("change_pct", 0):+.2f}%</span></div>'
        )

    return f"""
    <div class="trade-verdict {badge_class}">{html.escape(display_name)} · {regime.score}/100</div>
    <p class="trade-summary">{html.escape(regime.summary)}</p>
    <div class="geo-grid">
      <div class="geo-stat"><strong>Statut</strong><span>{html.escape(regime.status)}</span></div>
      <div class="geo-stat"><strong>Impact gold</strong><span>{html.escape(regime.gold_impact)}</span></div>
      {oil_cell("wti", "WTI")}
      {oil_cell("brent", "Brent")}
    </div>
    <div class="section-kicker" style="margin-top:10px;">Pourquoi ce regime</div>
    <ul class="reason-list">{reasons}</ul>
    """.strip()


def agent_css_class(bias: str) -> str:
    upper = bias.upper()
    if upper == "BUY":
        return "bullish"
    if upper == "SELL":
        return "bearish"
    if upper == "CAUTION":
        return "caution"
    return "neutral"


def render_agent_card(agent: AgentResult) -> str:
    badge_class = agent_css_class(agent.bias)
    evidence_items = "".join(
        f"<li><strong>{html.escape(item.label)}</strong>: {html.escape(item.value)}"
        + (f" <small>{html.escape(item.source)}</small>" if item.source else "")
        + "</li>"
        for item in agent.evidence[:3]
    )
    risk_items = "".join(
        f"<li><strong>{html.escape(risk.label)}</strong>: {html.escape(risk.detail)}</li>"
        for risk in agent.risks[:2]
    )
    risk_block = f'<ul class="agent-risk-list">{risk_items}</ul>' if risk_items else '<div class="agent-muted">Aucun risque specifique signale.</div>'
    return f"""
    <article class="agent-card {badge_class}">
      <div class="agent-card-top">
        <div>
          <div class="section-kicker">{html.escape(agent.department)}</div>
          <h3>{html.escape(agent.name)}</h3>
        </div>
        <div class="agent-score">{agent.score}<small>/100</small></div>
      </div>
      <div class="agent-badge {badge_class}">{html.escape(agent.bias)} · {html.escape(agent.status)}</div>
      <p>{html.escape(agent.summary)}</p>
      <div class="agent-confidence">Confiance {agent.confidence}/100</div>
      <ul class="agent-evidence-list">{evidence_items}</ul>
      {risk_block}
    </article>
    """.strip()


def render_agent_department_panel(agent_results: list[AgentResult], department: str, limit: int | None = None) -> str:
    agents = [agent for agent in agent_results if agent.department == department]
    if limit is not None:
        agents = agents[:limit]
    if not agents:
        return '<div class="empty-state">Agents passifs indisponibles pour ce departement.</div>'
    return '<div class="agent-grid">' + "".join(render_agent_card(agent) for agent in agents) + "</div>"


def render_agent_contradictions(agent_results: list[AgentResult]) -> str:
    contradictions = build_agent_contradictions(agent_results)
    if not contradictions:
        contradictions = ["Aucune contradiction majeure entre agents passifs."]
    items = "".join(f"<li>{html.escape(item)}</li>" for item in contradictions[:5])
    return f'<ul class="agent-risk-list">{items}</ul>'


def render_headlines_grid(news: list[NewsItem]) -> str:
    cards: list[str] = []
    for item in news[:8]:
        tone_class, tone_label = format_headline_tone(item.score)
        cards.append(
            f"""
            <article class="headline-card {tone_class}">
              <div class="headline-meta">
                <span class="headline-source">{html.escape(item.source)}</span>
                <span class="headline-tag">{html.escape(tone_label)}</span>
              </div>
              <h3>{html.escape(item.title)}</h3>
              <p>{html.escape(format_timestamp_for_humans(item.published_at))}</p>
              <a href="{html.escape(item.link)}" target="_blank" rel="noopener noreferrer">Ouvrir la source</a>
            </article>
            """.strip()
        )

    if not cards:
        return '<div class="empty-state">Aucune actualite exploitable n\'a ete recuperee.</div>'
    return "".join(cards)


def render_ai_summary(ai_analysis: str | None) -> str:
    if not ai_analysis:
        return ""
    escaped = html.escape(ai_analysis).replace("\n", "<br>")
    return (
        '<section class="panel ai-panel span-12">'
        '<div class="section-kicker">Synthese IA</div>'
        '<div class="terminal-line">'
        '<span class="prompt">&gt;</span>'
        '<span class="terminal-tag">MODEL</span>'
        f'<div class="ai-copy">{escaped}</div>'
        "</div>"
        "</section>"
    )


def build_what_happens_now_lines(
    gold: SymbolSnapshot,
    dxy: SymbolSnapshot,
    us10y: SymbolSnapshot,
    news: list[NewsItem],
    fundamental: TradeRecommendation,
    technical: TradeRecommendation,
    geopolitical: GeopoliticalAnalysis | None,
) -> list[tuple[str, str]]:
    lines: list[tuple[str, str]] = []

    price_direction = "monte" if gold.change_pct >= 0 else "baisse"
    macro_push = "soutiennent" if dxy.change_pct < 0 and us10y.change_abs < 0 else "freinent" if dxy.change_pct > 0 and us10y.change_abs > 0 else "se compensent"
    lines.append(
        (
            "Tape du marche",
            f"L'or {price_direction} a {gold.price:.2f}, pendant que le DXY fait {dxy.change_pct:+.2f}% et que le 10 ans US bouge de {us10y.change_abs * 100:+.1f} bps. "
            f"En clair: le dollar et les taux {macro_push} l'or aujourd'hui.",
        )
    )

    geo_story = find_story_for_categories(news, "geopolitical", "gold")
    if geo_story is not None:
        _impact_label, impact_text = explain_headline_gold_impact(geo_story)
        lines.append(
            (
                "Headline clef",
                f"{clean_display_text(geo_story.title)}. {explain_headline_reason(geo_story)} {impact_text}",
            )
        )

    if geopolitical is not None:
        if geopolitical.risk_off_status == "actif":
            geo_sentence = (
                "Risk-off geopolitique en cours. Soutien refuge or possible, mais une partie des capitaux peut filer "
                "vers le dollar pour chercher de la liquidite. Trancher via DXY et VIX."
            )
        elif geopolitical.risk_off_status == "en reflux":
            geo_sentence = (
                "Stress geopolitique en reflux. Soutien refuge or qui se reduit, surveiller un retour de la demande "
                "de couverture si VIX se retend."
            )
        else:
            geo_sentence = (
                "Fond geopolitique mixte: stress mesurable mais aucun signal unique dominant. Direction or "
                "depend de la prochaine confirmation oil/DXY/VIX."
            )
        lines.append(("Geopolitique", geo_sentence))

        if geopolitical.central_bank_bias == "accommodant":
            central_bank_sentence = "Le message banques centrales est plutot favorable a l'or: le marche voit plus facilement un assouplissement qu'un nouveau durcissement."
        elif geopolitical.central_bank_bias == "restrictif":
            central_bank_sentence = "Le message banques centrales reste plutot dur: cela soutient le dollar et limite le potentiel haussier immediat de l'or."
        else:
            central_bank_sentence = "Le message banques centrales est mitige: pas assez dovish pour declencher une hausse propre, pas assez hawkish non plus pour casser brutalement l'or."
        lines.append(("Banques centrales", central_bank_sentence))

    if fundamental.verdict == technical.verdict:
        alignment_sentence = (
            f"Le fondamental et la technique sont alignes en {fundamental.verdict}. "
            f"Le plan intraday est donc plus simple a executer tant que le contexte ne change pas."
        )
    else:
        alignment_sentence = (
            f"Le fondamental dit {fundamental.verdict} mais la technique dit {technical.verdict}. "
            "Cela veut dire que le contexte de fond n'est pas suffisant pour garantir une hausse propre: le marche reste vulnerable aux contre-pieds et aux retours de volatilite."
        )
    lines.append(("Lecture intraday", alignment_sentence))

    return lines


def render_what_happens_now(lines: list[tuple[str, str]]) -> str:
    blocks = []
    for title, text in lines:
        blocks.append(
            f"""
            <div class="story-row">
              <div class="story-label">{html.escape(title)}</div>
              <div class="story-text">{html.escape(text)}</div>
            </div>
            """.strip()
        )
    return "".join(blocks)


def render_information_digest(items: list[tuple[str, str, str]]) -> str:
    blocks: list[str] = []
    for label, title, explanation in items:
        blocks.append(
            f"""
            <article class="digest-card">
              <div class="digest-tag">{html.escape(label)}</div>
              <h3>{html.escape(title)}</h3>
              <p>{html.escape(explanation)}</p>
            </article>
            """.strip()
        )
    if not blocks:
        return '<div class="empty-state">Aucun resume d\'informations exploitable pour le moment.</div>'
    return "".join(blocks)


def render_headline_reason_cards(news: list[NewsItem], limit: int = 6) -> str:
    cards: list[str] = []
    for item in pick_story_headlines(news, limit=limit):
        impact_label, impact_text = explain_headline_gold_impact(item)
        tone_class = "bullish" if impact_label == "bullish" else "bearish" if impact_label == "bearish" else "neutral"
        cards.append(
            f"""
            <article class="headline-brief {tone_class}">
              <div class="headline-brief-top">
                <div class="headline-brief-source">{html.escape(clean_display_text(item.source))}</div>
                <div class="headline-brief-time">{html.escape(format_timestamp_for_humans(item.published_at))}</div>
              </div>
              <h3>{html.escape(clean_display_text(item.title))}</h3>
              <p><strong>Ce que cela veut dire:</strong> {html.escape(explain_headline_reason(item))}</p>
              <p><strong>Impact sur l'or:</strong> {html.escape(impact_text)}</p>
              <a href="{html.escape(item.link)}" target="_blank" rel="noopener noreferrer">Ouvrir la source</a>
            </article>
            """.strip()
        )

    if not cards:
        return (
            '<div class="empty-state">'
            "Sources headlines indisponibles temporairement. Le dashboard continue avec le prix, "
            "le DXY, les taux et le dernier cadrage geo/sentiment disponible."
            "</div>"
        )
    return "".join(cards)


def render_dashboard(
    bundle: BriefingBundle,
    live_client: bool = False,
    fragment_endpoint: str = "/fragment",
    poll_seconds: int = 10,
) -> str:
    document = render_dashboard_clarity_v2(bundle, live_client, fragment_endpoint, poll_seconds)
    return (
        document.replace("Hormuz / Oil Shock", "Regime politique / petrole")
        .replace("Hormuz/Oil Shock", "regime politique / petrole")
        .replace("hormuz-oil-shock", "political-oil")
        .replace("Oil shock", "stress petrole")
        .replace("Oil Shock", "stress petrole")
        .replace("oil shock", "stress petrole")
    )

def render_dashboard_clarity_v2(
    bundle: BriefingBundle,
    live_client: bool = False,
    fragment_endpoint: str = "/fragment",
    poll_seconds: int = 10,
) -> str:
    gold = bundle.gold
    dxy = bundle.dxy
    us10y = bundle.us10y
    analysis = bundle.analysis
    ai_analysis = bundle.ai_analysis
    geopolitical_analysis = bundle.geopolitical_analysis or analysis.geopolitical
    technical_readings = bundle.technical_timeframes or []
    real_yield = bundle.real_yield
    official_macro_rates = bundle.official_macro_rates
    cftc_positioning = bundle.cftc_positioning
    etf_flows_analysis = bundle.etf_flows_analysis
    macro_catalysts = bundle.macro_catalysts
    data_quality = bundle.data_quality
    cross_asset_analysis = bundle.cross_asset_analysis
    event_mode = bundle.event_mode
    weekend_gold = bundle.weekend_gold
    market_regime = bundle.market_regime
    event_facts = bundle.event_facts
    political_statements = bundle.political_statements
    trade_ledger = bundle.trade_ledger
    orchestrator_decision = bundle.orchestrator_decision
    chart_store = bundle.chart_store
    news_reaction_setup = bundle.news_reaction_setup
    technical_decision = bundle.technical_decision
    scenario_plan = bundle.scenario_plan
    tradingview_chart = render_tradingview_chart(interval="15")
    confidence_width = max(8, min(100, analysis.confidence))
    generated_at = format_timestamp_for_humans(bundle.payload["generated_at"])
    settings_payload = bundle.payload.get("settings") if isinstance(bundle.payload.get("settings"), dict) else None
    settings_validation_payload = (
        bundle.payload.get("settings_validation") if isinstance(bundle.payload.get("settings_validation"), dict) else None
    )
    reports_v3_payload = bundle.payload.get("reports_v3") if isinstance(bundle.payload.get("reports_v3"), list) else None

    fundamental = bundle.fundamental_recommendation or TradeRecommendation(
        mode="Fondamental",
        verdict="BUY" if analysis.score >= 0 else "SELL",
        score=max(50, min(100, 50 + (abs(analysis.score) * 5))),
        summary=heuristic_decision_sentence(analysis),
        reasons=analysis.reasons[:4],
        stop_loss=gold.price - 10,
        take_profit_1=gold.price + 10,
        take_profit_2=gold.price + 20,
        source_note="Mode de secours du dashboard.",
    )
    technical = bundle.technical_recommendation or TradeRecommendation(
        mode="Technique",
        verdict="BUY",
        score=50,
        summary="Technique indisponible.",
        reasons=["Lecture technique indisponible."],
        stop_loss=gold.price - 10,
        take_profit_1=gold.price + 10,
        take_profit_2=gold.price + 20,
        source_note="Mode de secours du dashboard.",
    )
    if technical_decision is None:
        technical_decision = build_technical_decision(
            gold,
            technical_readings,
            gold.price,
            cross_asset=cross_asset_analysis,
            event_mode=event_mode,
            data_quality=data_quality,
        )
    global_recommendation = bundle.global_recommendation or build_global_recommendation(
        gold,
        analysis,
        fundamental,
        technical,
        geopolitical=geopolitical_analysis,
        cross_asset=cross_asset_analysis,
        event_mode=event_mode,
    )
    if scenario_plan is None:
        scenario_plan = build_scenario_plan(
            gold,
            technical_decision,
            global_recommendation,
            fundamental_recommendation=fundamental,
            cross_asset=cross_asset_analysis,
            market_regime=market_regime,
            event_facts=event_facts,
            data_quality=data_quality,
        )
    if news_reaction_setup is None:
        news_reaction_setup = build_news_reaction_engine(
            event_facts,
            gold,
            dxy,
            us10y,
            cross_asset=cross_asset_analysis,
            data_quality=data_quality,
        )
    reversal_engine = bundle.reversal_engine or build_reversal_engine(gold, technical_readings, chart_store)
    active_settings = parse_user_settings(settings_payload)
    strategy_candidates = bundle.strategy_candidates or build_strategy_candidates(
        gold,
        technical_readings,
        chart_store,
        news_reaction_setup=news_reaction_setup,
        event_mode=event_mode,
    )
    strategy_selection = bundle.strategy_selection or build_strategy_selection(
        strategy_candidates,
        event_mode=event_mode,
        trade_ledger=trade_ledger,
        min_rr=active_settings.minimum_risk_reward,
    )
    agent_results = bundle.agent_results or build_passive_agent_results(
        gold,
        dxy,
        us10y,
        bundle.news,
        analysis,
        geopolitical_analysis=geopolitical_analysis,
        fundamental_recommendation=fundamental,
        technical_recommendation=technical,
        technical_decision=technical_decision,
        global_recommendation=global_recommendation,
        technical_timeframes=technical_readings,
        real_yield=real_yield,
        official_macro_rates=official_macro_rates,
        cftc_positioning=cftc_positioning,
        etf_flows_analysis=etf_flows_analysis,
        macro_catalysts=macro_catalysts,
        data_quality=data_quality,
        cross_asset_analysis=cross_asset_analysis,
        event_mode=event_mode,
        weekend_gold=weekend_gold,
        market_regime=market_regime,
        event_facts=event_facts,
        political_statements=political_statements,
    )
    executive_summary = bundle.executive_summary or build_executive_summary(fundamental, technical, geopolitical_analysis)

    price_class = "bullish" if gold.change_pct > 0 else "bearish" if gold.change_pct < 0 else "neutral"
    dxy_class = "bullish" if dxy.change_pct < 0 else "bearish" if dxy.change_pct > 0 else "neutral"
    us10y_class = "bullish" if us10y.change_abs < 0 else "bearish" if us10y.change_abs > 0 else "neutral"
    real_yield_class = (
        "bullish"
        if real_yield is not None and real_yield.change_abs < 0
        else "bearish"
        if real_yield is not None and real_yield.change_abs > 0
        else "neutral"
    )
    geo_class = (
        "bullish"
        if geopolitical_analysis is not None and geopolitical_analysis.score >= 55
        else "bearish"
        if geopolitical_analysis is not None and geopolitical_analysis.score <= 45
        else "neutral"
    )
    story_lines = build_what_happens_now_lines(
        gold,
        dxy,
        us10y,
        bundle.news,
        fundamental,
        technical,
        geopolitical_analysis,
    )
    digest_items = build_information_digest_items(gold, dxy, us10y, bundle.news, geopolitical_analysis)
    raw_regime_name = market_regime.name if market_regime is not None else "Normal Macro"
    regime_name = human_regime_name(raw_regime_name)
    regime_status = market_regime.status if market_regime is not None else "NORMAL"
    regime_alert = (
        "political-oil"
        if market_regime is not None and raw_regime_name == "Hormuz / Oil Shock"
        else "ig-weekend"
        if weekend_gold is not None
        else "none"
    )
    regime_summary = market_regime.summary if market_regime is not None else "Pas de regime special confirme."
    banner_class = recommendation_css_class(global_recommendation.verdict)
    active_trades = len(trade_ledger.active_trades) if trade_ledger else 0
    data_quality_score = data_quality.score if data_quality else 0
    data_quality_status = data_quality.status if data_quality else "N/A"
    lead_status, lead_score, lead_bias = visible_lead_status(global_recommendation, orchestrator_decision)
    lead_class = state_tone_class(lead_status)
    locked_status = "LOCKED" if active_trades else "NO LOCK"
    locked_class = "bullish" if active_trades else "neutral"
    news_reaction_class = (
        "bullish"
        if news_reaction_setup.direction in {"BUY", "WATCH_BUY"}
        else "bearish"
        if news_reaction_setup.direction in {"SELL", "WATCH_SELL"}
        else "caution"
        if news_reaction_setup.status in {"WATCH", "SUSPENDED"}
        else "neutral"
    )

    if weekend_gold is not None:
        weekend_delta_class = (
            "bullish"
            if weekend_gold.change_pct is not None and weekend_gold.change_pct > 0
            else "bearish"
            if weekend_gold.change_pct is not None and weekend_gold.change_pct < 0
            else "neutral"
        )
        weekend_variation = (
            f"{weekend_gold.change_abs:+.2f} / {weekend_gold.change_pct:+.2f}%"
            if weekend_gold.change_abs is not None and weekend_gold.change_pct is not None
            else "variation n/a"
        )
        weekend_gold_cell = f"""
          <div class="live-cell weekend-live-cell">
            <small>IG Weekend</small>
            <strong class="{weekend_delta_class}">{weekend_gold.mid:.2f}</strong>
            <span>Sell {weekend_gold.sell:.2f} · Buy {weekend_gold.buy:.2f} · Spread {weekend_gold.spread:.2f}</span>
            <span class="live-cell-note">{html.escape(weekend_variation)} · ecart spot {weekend_gold.mid - gold.price:+.2f}</span>
          </div>
        """.strip()
    else:
        weekend_gold_cell = ""

    def nav_links(css_class: str) -> str:
        items = [
            ("desk", "Desk"),
            ("agents", "Agents"),
            ("news", "News Flow"),
            ("reports", "Reports"),
            ("inspector", "Inspector"),
        ]
        return "".join(
            f'<a class="{css_class}{" active" if key == "desk" else ""}" href="#{key}" data-tab-target="{key}" aria-selected="{"true" if key == "desk" else "false"}">{html.escape(label)}</a>'
            for key, label in items
        )

    meta_refresh = "" if live_client else '  <meta http-equiv="refresh" content="60">\n'
    refresh_enabled = "true" if live_client else "false"
    live_script = f"""
  <script>
    (() => {{
      const app = document.getElementById("dashboard-app");
      const storageKey = "aureumFlux.activeTab";
      const defaultTab = "desk";
      const allowedTabs = new Set(["desk", "agents", "news", "reports", "inspector"]);
      const refreshEnabled = {refresh_enabled};
      let busy = false;

      function getRequestedTab() {{
        const hashTab = window.location.hash ? window.location.hash.replace("#", "") : "";
        const storedTab = window.localStorage.getItem(storageKey) || "";
        const requested = hashTab || storedTab || defaultTab;
        return allowedTabs.has(requested) ? requested : defaultTab;
      }}

      function setActiveTab(tab, persist = true) {{
        const requestedTab = allowedTabs.has(tab || "") ? tab : defaultTab;
        const view = document.querySelector(`[data-tab-view="${{requestedTab}}"]`);
        const activeTab = view ? requestedTab : defaultTab;
        document.querySelectorAll("[data-tab-view]").forEach((element) => {{
          element.classList.toggle("active", element.dataset.tabView === activeTab);
        }});
        document.querySelectorAll("[data-tab-target]").forEach((element) => {{
          const isActive = element.dataset.tabTarget === activeTab;
          element.classList.toggle("active", isActive);
          element.setAttribute("aria-selected", isActive ? "true" : "false");
        }});
        if (persist) {{
          window.localStorage.setItem(storageKey, activeTab);
        }}
      }}

      function applyStoredTab() {{
        setActiveTab(getRequestedTab(), true);
      }}

      document.addEventListener("click", (event) => {{
        const agentToggle = event.target.closest("[data-agent-toggle]");
        if (agentToggle) {{
          event.preventDefault();
          toggleAgent(agentToggle.dataset.agentToggle, agentToggle.dataset.agentEnabled !== "true");
          return;
        }}
        const trigger = event.target.closest("[data-tab-target]");
        if (!trigger) return;
        event.preventDefault();
        setActiveTab(trigger.dataset.tabTarget, true);
      }});

      window.addEventListener("hashchange", () => {{
        setActiveTab(getRequestedTab(), true);
      }});

      async function refreshLive() {{
        if (!app || !refreshEnabled) return;
        if (busy) return;
        busy = true;
        try {{
          const response = await fetch("{fragment_endpoint}?_ts=" + Date.now(), {{ cache: "no-store" }});
          if (!response.ok) return;
          app.innerHTML = await response.text();
          applyStoredTab();
        }} catch (_error) {{
        }} finally {{
          busy = false;
        }}
      }}
      async function toggleAgent(agentName, enabled) {{
        if (!agentName) return;
        try {{
          const response = await fetch("/api/settings", {{
            method: "POST",
            headers: {{ "Content-Type": "application/json" }},
            body: JSON.stringify({{ action: "set_agent_enabled", agent: agentName, enabled }})
          }});
          if (!response.ok) return;
          if (refreshEnabled) {{
            await refreshLive();
          }} else {{
            window.location.reload();
          }}
        }} catch (_error) {{
        }}
      }}
      applyStoredTab();
      if (refreshEnabled) {{
        window.setInterval(refreshLive, {max(5, poll_seconds) * 1000});
      }}
    }})();
  </script>
""".rstrip()

    return f"""<!doctype html>
<html lang="fr">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
{meta_refresh}  <meta name="color-scheme" content="dark">
  <title>Dashboard XAUUSD</title>
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
  <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800;900&family=Space+Grotesk:wght@500;700&display=swap" rel="stylesheet">
  <style>
    :root {{
      --bg: #020617;
      --rail: #050a17;
      --panel: #0b1222;
      --panel-2: #111827;
      --panel-3: #151e31;
      --text: #e5e7f5;
      --soft: #9aa4b8;
      --muted: #313a50;
      --line: #263247;
      --bull: #4edea3;
      --bear: #ffb4ab;
      --amber: #d4af37;
      --gold: #f2ca50;
      --blue: #8ab4ff;
    }}
    * {{ box-sizing: border-box; }}
    html, body {{
      margin: 0;
      min-height: 100vh;
      color: var(--text);
      background: var(--bg);
      font-family: Inter, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
      overflow-x: hidden;
      scroll-behavior: smooth;
    }}
    body {{
      background: linear-gradient(180deg, #020617 0%, #071020 58%, #020617 100%);
    }}
    a {{ color: var(--blue); text-decoration: none; }}
    a:hover {{ text-decoration: underline; }}
    h1, h2, h3, p {{ margin: 0; }}
    .page {{ min-height: 100vh; width: 100%; }}
    .terminal-shell {{
      display: grid;
      grid-template-columns: 270px minmax(0, 1fr);
      min-height: 100vh;
      min-width: 0;
      max-width: 100%;
    }}
    .side-rail {{
      position: sticky;
      top: 0;
      height: 100vh;
      padding: 24px 18px;
      background: var(--rail);
      border-right: 1px solid var(--line);
    }}
    .brand {{
      color: var(--amber);
      font-family: "Space Grotesk", monospace;
      font-size: 26px;
      font-weight: 900;
      line-height: 0.95;
      text-transform: uppercase;
      text-shadow: 0 0 16px rgba(212, 175, 55, 0.24);
    }}
    .rail-card {{
      margin-top: 28px;
      padding: 15px;
      border: 1px solid rgba(212, 175, 55, 0.22);
      border-radius: 8px;
      background: rgba(17, 24, 39, 0.72);
    }}
    .rail-card strong {{
      display: block;
      color: var(--text);
      font-family: "Space Grotesk", monospace;
      font-size: 13px;
      letter-spacing: 0.14em;
      text-transform: uppercase;
    }}
    .rail-card span {{ display: block; margin-top: 6px; color: var(--soft); font-size: 13px; }}
    .rail-status {{
      margin-top: 12px;
      padding: 8px 10px;
      border: 1px solid rgba(78, 222, 163, 0.34);
      border-radius: 5px;
      color: var(--bull);
      background: rgba(78, 222, 163, 0.08);
      font-family: "Space Grotesk", monospace;
      font-size: 11px;
      font-weight: 800;
      letter-spacing: 0.14em;
      text-transform: uppercase;
    }}
    .rail-nav {{ display: grid; gap: 6px; margin-top: 28px; }}
    .rail-link {{
      display: block;
      padding: 12px 12px 12px 14px;
      border-left: 3px solid transparent;
      border-radius: 0 6px 6px 0;
      color: var(--soft);
      font-family: "Space Grotesk", monospace;
      font-size: 12px;
      font-weight: 800;
      letter-spacing: 0.14em;
      text-transform: uppercase;
      text-decoration: none;
      cursor: pointer;
    }}
    .rail-link:hover {{ color: var(--text); background: rgba(255, 255, 255, 0.04); text-decoration: none; }}
    .rail-link.active {{ color: var(--amber); border-left-color: var(--amber); background: rgba(212, 175, 55, 0.1); }}
    .workspace {{
      min-width: 0;
      max-width: 1680px;
      width: 100%;
      margin: 0 auto;
      padding: 18px 26px 30px;
      overflow-x: hidden;
    }}
    .topbar {{
      position: sticky;
      top: 0;
      z-index: 4;
      display: flex;
      justify-content: space-between;
      align-items: center;
      gap: 16px;
      min-height: 58px;
      min-width: 0;
      margin: -18px -26px 22px;
      padding: 0 26px;
      border-bottom: 1px solid var(--line);
      background: rgba(2, 6, 23, 0.88);
      backdrop-filter: blur(16px);
    }}
    .topbar-brand {{
      color: var(--amber);
      font-family: "Space Grotesk", monospace;
      font-size: 17px;
      font-weight: 900;
      white-space: nowrap;
    }}
    .top-status {{
      display: flex;
      flex-wrap: wrap;
      justify-content: flex-end;
      align-items: center;
      gap: 8px;
      min-width: 0;
      max-width: 100%;
      overflow-x: auto;
      scrollbar-width: none;
    }}
    .top-status::-webkit-scrollbar {{ display: none; }}
    .status-pill {{
      display: inline-flex;
      align-items: center;
      min-height: 30px;
      padding: 6px 9px;
      border: 1px solid var(--line);
      border-radius: 999px;
      color: var(--soft);
      background: rgba(17, 24, 39, 0.72);
      font-family: "Space Grotesk", monospace;
      font-size: 11px;
      font-weight: 800;
      letter-spacing: 0.08em;
      text-transform: uppercase;
      white-space: nowrap;
    }}
    .status-pill.bullish {{ color: var(--bull); border-color: rgba(78, 222, 163, 0.34); }}
    .status-pill.bearish {{ color: var(--bear); border-color: rgba(255, 180, 171, 0.34); }}
    .status-pill.caution {{ color: var(--amber); border-color: rgba(212, 175, 55, 0.36); }}
    .mobile-nav {{ display: none; }}
    .top-nav {{ display: none; min-width: 0; }}
    .terminal-header {{
      display: flex;
      justify-content: space-between;
      align-items: flex-end;
      gap: 16px;
      margin-bottom: 16px;
    }}
    .terminal-header > div {{ min-width: 0; max-width: 100%; }}
    .terminal-header h1 {{
      color: var(--text);
      font-size: clamp(30px, 4vw, 52px);
      line-height: 1;
      font-weight: 900;
      letter-spacing: 0;
      overflow-wrap: anywhere;
    }}
    .terminal-header p {{ margin-top: 8px; color: var(--soft); font-size: 14px; }}
    .section-kicker {{
      color: var(--amber);
      font-family: "Space Grotesk", monospace;
      font-size: 11px;
      font-weight: 900;
      letter-spacing: 0.18em;
      text-transform: uppercase;
    }}
    .sync-pill {{
      flex: 0 0 auto;
      padding: 9px 12px;
      border: 1px solid rgba(78, 222, 163, 0.28);
      border-radius: 999px;
      color: var(--bull);
      background: rgba(78, 222, 163, 0.08);
      font-family: "Space Grotesk", monospace;
      font-size: 11px;
      font-weight: 900;
      letter-spacing: 0.14em;
      text-transform: uppercase;
    }}
    .tab-view {{ display: none; min-width: 0; }}
    .tab-view.active {{ display: block; }}
    .view-header {{
      display: flex;
      justify-content: space-between;
      align-items: flex-end;
      gap: 16px;
      margin: 8px 0 14px;
    }}
    .view-header h2 {{ font-size: 26px; line-height: 1.1; }}
    .view-header p {{ margin-top: 5px; color: var(--soft); font-size: 13px; line-height: 1.5; }}
    .panel,
    .summary-box,
    .quick-card,
    .metric-chip,
    .level-chip,
    .story-row,
    .digest-card,
    .headline-card,
    .headline-brief,
    .scenario,
    .decision-item,
    .global-signal {{
      border: 1px solid var(--line);
      border-radius: 8px;
      background: var(--panel);
      min-width: 0;
    }}
    .panel,
    .summary-box {{ padding: 16px; }}
    .panel h2,
    .summary-box h2 {{ color: var(--text); font-size: 22px; line-height: 1.18; margin-top: 4px; margin-bottom: 8px; }}
    .layout-desk,
    .layout-agents,
    .layout-news,
    .layout-inspector,
    .layout-reports {{
      display: grid;
      grid-template-columns: minmax(0, 1fr);
      gap: 14px;
      align-items: start;
      min-width: 0;
    }}
    .layout-desk {{ grid-template-columns: repeat(12, minmax(0, 1fr)); }}
    .layout-desk .span-4 {{ grid-column: span 4; }}
    .layout-desk .span-6 {{ grid-column: span 6; }}
    .layout-desk .span-8 {{ grid-column: span 8; }}
    .layout-desk .span-12 {{ grid-column: 1 / -1; }}
    .span-3,
    .span-4,
    .span-5,
    .span-6,
    .span-7,
    .span-8,
    .span-12 {{ grid-column: 1 / -1; }}
    .global-live-strip {{
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(170px, 1fr));
      gap: 10px;
      margin-bottom: 12px;
      padding: 10px;
      border: 1px solid rgba(212, 175, 55, 0.28);
      border-radius: 10px;
      background: rgba(11, 18, 34, 0.9);
    }}
    .live-cell,
    .state-card,
    .geo-stat {{
      min-width: 0;
      padding: 11px;
      border: 1px solid var(--line);
      border-radius: 7px;
      background: var(--panel-2);
    }}
    .live-cell small,
    .state-card small,
    .geo-stat strong,
    .metric-chip strong,
    .level-chip strong {{
      display: block;
      color: var(--amber);
      font-family: "Space Grotesk", monospace;
      font-size: 10px;
      font-weight: 900;
      letter-spacing: 0.1em;
      text-transform: uppercase;
      margin-bottom: 5px;
    }}
    .live-cell strong,
    .state-card strong,
    .metric-chip span,
    .level-chip span {{
      display: block;
      color: var(--text);
      font-family: "Space Grotesk", monospace;
      font-size: 20px;
      line-height: 1.15;
      overflow-wrap: anywhere;
    }}
    .live-cell span,
    .state-card span,
    .geo-stat span,
    .geo-stat small,
    .metric-chip small {{
      display: block;
      color: var(--soft);
      font-size: 12px;
      line-height: 1.4;
      overflow-wrap: anywhere;
    }}
    .live-cell-note {{ margin-top: 4px; font-size: 11px; }}
    .weekend-live-cell {{ border-color: rgba(212, 175, 55, 0.42); background: rgba(212, 175, 55, 0.06); }}
    .state-board {{ display: grid; grid-template-columns: minmax(0, 1fr); gap: 10px; margin-bottom: 14px; }}
    .state-card {{ border-left: 4px solid var(--blue); }}
    .state-card.bullish {{ border-left-color: var(--bull); }}
    .state-card.bearish {{ border-left-color: var(--bear); }}
    .state-card.caution {{ border-left-color: var(--amber); }}
    .decision-hero {{
      padding: 18px;
      border: 1px solid rgba(212, 175, 55, 0.34);
      border-radius: 10px;
      background: linear-gradient(135deg, rgba(212, 175, 55, 0.1), rgba(11, 18, 34, 0.94) 42%);
    }}
    .ticker-symbol {{ color: var(--amber); font-family: "Space Grotesk", monospace; font-size: 12px; letter-spacing: 0.14em; text-transform: uppercase; }}
    .ticker-row {{ display: flex; flex-wrap: wrap; align-items: baseline; gap: 14px; margin: 8px 0 6px; }}
    .ticker-price {{ font-family: "Space Grotesk", monospace; font-size: clamp(42px, 7vw, 86px); font-weight: 900; line-height: 0.95; }}
    .ticker-delta {{ font-family: "Space Grotesk", monospace; font-size: 24px; font-weight: 900; }}
    .ticker-meta {{ color: var(--soft); font-size: 13px; line-height: 1.55; }}
    .global-position {{ display: flex; flex-wrap: wrap; align-items: baseline; gap: 12px; margin-top: 10px; }}
    .global-position strong {{ font-family: "Space Grotesk", monospace; font-size: clamp(34px, 5vw, 58px); line-height: 1; }}
    .global-position span {{ color: var(--soft); font-size: 14px; line-height: 1.45; }}
    .global-score {{ color: var(--amber); font-family: "Space Grotesk", monospace; font-size: 34px; font-weight: 900; white-space: nowrap; }}
    .global-score small {{ color: var(--soft); font-size: 14px; }}
    .global-summary,
    .trade-summary,
    .story-text,
    .headline-brief p,
    .footer-note {{ color: var(--text); font-size: 13px; line-height: 1.58; }}
    .metric-strip,
    .metrics-grid,
    .trade-levels,
    .key-levels,
    .geo-grid,
    .scenario-grid,
    .decision-grid,
    .digest-grid,
    .headline-grid,
    .agent-grid,
    .geo-columns {{ display: grid; gap: 10px; min-width: 0; }}
    .metric-strip {{ grid-template-columns: repeat(auto-fit, minmax(155px, 1fr)); margin-top: 12px; }}
    .metrics-grid {{ grid-template-columns: minmax(0, 1fr); margin-top: 10px; }}
    .trade-levels {{ grid-template-columns: repeat(auto-fit, minmax(110px, 1fr)); margin-top: 10px; }}
    .key-levels {{ grid-template-columns: minmax(0, 1fr); margin-top: 10px; }}
    .geo-grid {{ grid-template-columns: minmax(0, 1fr); margin-top: 10px; }}
    .geo-columns {{ grid-template-columns: minmax(0, 1fr); margin-top: 10px; }}
    .scenario-grid {{ grid-template-columns: minmax(0, 1fr); }}
    .scenario-stack {{ grid-template-columns: 1fr; }}
    .digest-grid {{ grid-template-columns: minmax(0, 1fr); margin-top: 10px; }}
    .headline-grid {{ grid-template-columns: minmax(0, 1fr); margin-top: 10px; }}
    .agent-grid {{ grid-template-columns: minmax(0, 1fr); margin-top: 12px; }}
    .trade-card {{
      border-left: 5px solid var(--muted);
      background: var(--panel);
      min-width: 0;
    }}
    .trade-card.bullish {{ border-left-color: rgba(78, 222, 163, 0.75); }}
    .trade-card.bearish {{ border-left-color: rgba(255, 180, 171, 0.75); }}
    .trade-card-head {{ display: flex; justify-content: space-between; gap: 12px; align-items: flex-start; margin-bottom: 8px; }}
    .trade-card h2 {{ color: var(--text); font-size: 20px; line-height: 1.2; margin-top: 2px; }}
    .trade-score {{ color: var(--amber); font-family: "Space Grotesk", monospace; font-size: 28px; font-weight: 900; white-space: nowrap; }}
    .trade-score small {{ color: var(--soft); font-size: 14px; }}
    .trade-verdict {{
      display: inline-flex;
      max-width: 100%;
      padding: 6px 10px;
      border: 1px solid var(--line);
      border-radius: 5px;
      background: var(--panel-2);
      font-family: "Space Grotesk", monospace;
      font-size: 13px;
      font-weight: 900;
      letter-spacing: 0.08em;
      text-transform: uppercase;
      margin-bottom: 8px;
      overflow-wrap: anywhere;
    }}
    .tag-row {{ display: flex; flex-wrap: wrap; gap: 6px; margin: 0 0 9px; }}
    .source-tag {{
      display: inline-flex;
      align-items: center;
      min-height: 24px;
      max-width: 100%;
      padding: 4px 7px;
      border: 1px solid rgba(45, 52, 73, 0.9);
      border-radius: 999px;
      color: var(--soft);
      background: rgba(6, 14, 32, 0.62);
      font-family: "Space Grotesk", monospace;
      font-size: 10px;
      font-weight: 800;
      letter-spacing: 0.07em;
      text-transform: uppercase;
      overflow-wrap: anywhere;
    }}
    .source-tag.bullish {{ color: var(--bull); border-color: rgba(78, 222, 163, 0.34); }}
    .source-tag.bearish {{ color: var(--bear); border-color: rgba(255, 180, 171, 0.34); }}
    .source-tag.caution {{ color: var(--amber); border-color: rgba(212, 175, 55, 0.34); }}
    .source-tag.neutral {{ color: var(--blue); border-color: rgba(138, 180, 255, 0.34); }}
    .source-tag.OK {{ color: var(--bull); border-color: rgba(78, 222, 163, 0.34); }}
    .trade-levels div,
    .metric-chip,
    .level-chip {{ padding: 11px; border: 1px solid var(--line); border-radius: 7px; background: var(--panel-2); }}
    .trade-levels span {{ display: block; color: var(--amber); font-family: "Space Grotesk", monospace; font-size: 10px; font-weight: 900; letter-spacing: 0.1em; text-transform: uppercase; }}
    .trade-levels strong {{ display: block; margin-top: 4px; font-size: 20px; font-family: "Space Grotesk", monospace; color: var(--text); overflow-wrap: anywhere; }}
    .trade-reasons,
    .reason-list,
    .agent-evidence-list,
    .agent-risk-list {{ margin: 8px 0 0; padding-left: 18px; color: var(--text); font-size: 12px; line-height: 1.55; }}
    .trade-footer {{ margin-top: 10px; padding-top: 10px; border-top: 1px solid var(--line); display: grid; gap: 4px; color: var(--soft); font-size: 12px; line-height: 1.45; }}
    .summary-box .lead {{ color: var(--text); font-size: 14px; line-height: 1.6; margin-bottom: 10px; }}
    .story-row,
    .digest-card,
    .decision-item,
    .scenario {{ padding: 12px; }}
    .story-label,
    .digest-tag {{ color: var(--amber); font-family: "Space Grotesk", monospace; font-size: 10px; font-weight: 900; letter-spacing: 0.1em; text-transform: uppercase; margin-bottom: 6px; }}
    .decision-item strong {{ display: block; font-size: 15px; margin-bottom: 5px; }}
    .decision-item span {{ color: var(--soft); font-size: 13px; line-height: 1.58; }}
    .agent-card {{ padding: 13px; border: 1px solid var(--line); border-top: 3px solid var(--blue); border-radius: 7px; background: var(--panel-2); min-width: 0; }}
    .agent-card.bullish {{ border-top-color: var(--bull); }}
    .agent-card.bearish {{ border-top-color: var(--bear); }}
    .agent-card.caution {{ border-top-color: var(--amber); }}
    .agent-card-top {{ display: flex; justify-content: space-between; gap: 12px; align-items: flex-start; margin-bottom: 8px; }}
    .agent-card h3 {{ font-size: 15px; line-height: 1.3; color: var(--text); }}
    .agent-score {{ flex: 0 0 auto; color: var(--gold); font-family: "Space Grotesk", monospace; font-size: 20px; font-weight: 900; }}
    .agent-score small {{ color: var(--soft); font-size: 11px; }}
    .agent-badge {{
      display: inline-flex;
      margin-bottom: 8px;
      padding: 4px 7px;
      border: 1px solid var(--line);
      border-radius: 4px;
      font-family: "Space Grotesk", monospace;
      font-size: 11px;
      font-weight: 800;
      letter-spacing: 0.07em;
      text-transform: uppercase;
    }}
    .agent-badge.bullish {{ color: var(--bull); border-color: rgba(78, 222, 163, 0.35); }}
    .agent-badge.bearish {{ color: var(--bear); border-color: rgba(255, 180, 171, 0.35); }}
    .agent-badge.caution {{ color: var(--amber); border-color: rgba(212, 175, 55, 0.35); }}
    .agent-badge.neutral {{ color: var(--blue); border-color: rgba(138, 180, 255, 0.35); }}
    .agent-card p,
    .agent-muted {{ color: var(--soft); font-size: 12px; line-height: 1.55; }}
    .agent-confidence {{ margin-top: 8px; color: var(--text); font-size: 12px; font-weight: 800; }}
    .agent-evidence-list small {{ display: block; color: var(--amber); font-size: 10px; margin-top: 2px; }}
    .confidence-bar {{ height: 10px; margin-top: 10px; background: #172033; border-radius: 999px; overflow: hidden; }}
    .confidence-bar span {{ display: block; width: {confidence_width}%; height: 100%; background: linear-gradient(90deg, var(--amber), var(--bull)); }}
    .chart-wrap {{ margin-top: 10px; border: 1px solid var(--line); border-radius: 7px; overflow: hidden; background: #060e20; }}
    .chart-wrap svg {{ display: block; width: 100%; height: auto; }}
    .tradingview-panel {{ margin-top: 10px; border: 1px solid var(--line); border-radius: 7px; overflow: hidden; background: #060e20; min-height: 560px; }}
    .tradingview-panel iframe {{ display: block; width: 100%; height: 520px; border: 0; }}
    .tradingview-panel .footer-note {{ padding: 10px 12px; border-top: 1px solid var(--line); }}
    .technical-decision-card {{ border: 1px solid var(--line); border-left: 5px solid var(--line); border-radius: 7px; padding: 14px; background: var(--panel-2); }}
    .reversal-grid {{ display: grid; grid-template-columns: minmax(0, 1fr); gap: 10px; margin-top: 10px; }}
    .reversal-card {{ padding: 14px; border: 1px solid var(--line); border-left: 5px solid var(--line); border-radius: 8px; background: var(--panel-2); min-width: 0; }}
    .reversal-card.bullish {{ border-left-color: rgba(78, 222, 163, 0.72); }}
    .reversal-card.bearish {{ border-left-color: rgba(255, 180, 171, 0.72); }}
    .reversal-card.neutral {{ border-left-color: rgba(138, 180, 255, 0.72); }}
    .reversal-head {{ display: flex; align-items: flex-start; justify-content: space-between; gap: 12px; margin-bottom: 10px; }}
    .reversal-head strong {{ display: block; font-size: 16px; color: var(--text); }}
    .reversal-head span,
    .reversal-meta span {{ color: var(--soft); font-size: 12px; }}
    .reversal-meta {{ display: flex; flex-wrap: wrap; gap: 8px; margin-bottom: 10px; }}
    .reversal-meta span {{ padding: 5px 8px; border: 1px solid var(--line); border-radius: 999px; background: rgba(6, 14, 32, 0.55); }}
    .reversal-reasons {{ margin: 10px 0 0; padding-left: 18px; color: var(--soft); font-size: 13px; line-height: 1.5; }}
    .scenario-plan-card {{ border: 1px solid var(--line); border-left: 5px solid var(--line); border-radius: 7px; padding: 14px; background: var(--panel-2); }}
    .technical-decision-card.bullish {{ border-left-color: rgba(78, 222, 163, 0.72); }}
    .technical-decision-card.bearish {{ border-left-color: rgba(255, 180, 171, 0.72); }}
    .technical-decision-card.neutral {{ border-left-color: rgba(138, 180, 255, 0.72); }}
    .scenario-plan-card.bullish {{ border-left-color: rgba(78, 222, 163, 0.72); }}
    .scenario-plan-card.bearish {{ border-left-color: rgba(255, 180, 171, 0.72); }}
    .scenario-plan-card.neutral {{ border-left-color: rgba(138, 180, 255, 0.72); }}
    .scenario-plan-card.caution {{ border-left-color: rgba(212, 175, 55, 0.72); }}
    .scenario-plan-grid {{ display: grid; grid-template-columns: minmax(0, 1fr); gap: 10px; min-width: 0; }}
    .agent-toggle {{
      min-width: 54px;
      min-height: 30px;
      border: 1px solid var(--line);
      border-radius: 999px;
      background: rgba(15, 23, 42, 0.95);
      color: var(--soft);
      font-family: "Space Grotesk", monospace;
      font-size: 11px;
      font-weight: 900;
      letter-spacing: 0.08em;
      cursor: pointer;
    }}
    .agent-toggle.on {{ color: var(--bull); border-color: rgba(78, 222, 163, 0.45); background: rgba(78, 222, 163, 0.08); }}
    .agent-toggle.off {{ color: var(--bear); border-color: rgba(255, 180, 171, 0.45); background: rgba(255, 180, 171, 0.08); }}
    .macro-event-list {{ display: grid; grid-template-columns: minmax(0, 1fr); gap: 10px; margin-top: 10px; }}
    .macro-event-row {{ padding: 13px; border: 1px solid var(--line); border-radius: 8px; background: var(--panel-2); }}
    .macro-event-row h3 {{ margin: 8px 0; font-size: 17px; line-height: 1.35; }}
    .macro-values {{ display: grid; grid-template-columns: minmax(0, 1fr); gap: 8px; margin: 10px 0; }}
    .macro-values div {{ padding: 10px; border: 1px solid var(--line); border-radius: 7px; background: rgba(6, 14, 32, 0.6); }}
    .macro-values strong {{ display: block; color: var(--amber); font-family: "Space Grotesk", monospace; font-size: 10px; letter-spacing: 0.1em; text-transform: uppercase; margin-bottom: 4px; }}
    .macro-values span {{ color: var(--text); font-size: 13px; }}
    .technical-decision-head {{ display: flex; justify-content: space-between; gap: 12px; align-items: start; margin-bottom: 10px; }}
    .technical-decision-head h3 {{ margin-top: 2px; font-size: 20px; }}
    .technical-decision-block {{ margin-top: 12px; color: var(--text); }}
    .technical-decision-block strong {{ display: block; color: var(--amber); font-family: "Space Grotesk", monospace; font-size: 11px; letter-spacing: 0.1em; text-transform: uppercase; margin-bottom: 4px; }}
    .technical-decision-block p,
    .technical-decision-block li {{ color: var(--soft); font-size: 13px; line-height: 1.5; }}
    .technical-decision-block ul {{ padding-left: 18px; }}
    .headline-brief {{ padding: 13px; border-left: 5px solid var(--line); }}
    .headline-brief.bullish {{ border-left-color: rgba(78, 222, 163, 0.65); }}
    .headline-brief.bearish {{ border-left-color: rgba(255, 180, 171, 0.65); }}
    .headline-brief.neutral {{ border-left-color: rgba(212, 175, 55, 0.52); }}
    .headline-brief-top {{ display: flex; justify-content: space-between; gap: 10px; margin-bottom: 8px; color: var(--soft); font-size: 12px; }}
    .headline-brief h3,
    .digest-card h3 {{ font-size: 15px; line-height: 1.38; margin-bottom: 7px; color: var(--text); }}
    .headline-brief p + p {{ margin-top: 8px; }}
    .headline-brief a {{ display: inline-block; margin-top: 10px; font-size: 13px; }}
    .table-wrap {{ overflow-x: auto; margin-top: 10px; border: 1px solid var(--line); border-radius: 7px; background: var(--panel-2); }}
    .technical-table {{ width: 100%; min-width: 860px; border-collapse: collapse; }}
    .technical-table th,
    .technical-table td {{ padding: 10px 11px; border-bottom: 1px solid var(--line); text-align: left; font-size: 12px; color: var(--text); vertical-align: top; }}
    .technical-table th {{ background: #0f172a; color: var(--amber); font-family: "Space Grotesk", monospace; font-size: 10px; letter-spacing: 0.1em; text-transform: uppercase; }}
    .technical-table small,
    .soft {{ color: var(--soft); font-size: 11px; }}
    .scenario.positive h3 {{ color: var(--bull); }}
    .scenario.negative h3 {{ color: var(--bear); }}
    .scenario.neutral h3 {{ color: var(--amber); }}
    .terminal-line {{ display: grid; grid-template-columns: auto auto minmax(0, 1fr); gap: 10px; align-items: start; margin-top: 10px; }}
    .prompt {{ color: var(--bull); font-weight: 800; }}
    .terminal-tag {{ color: var(--amber); font-size: 12px; letter-spacing: 0.08em; text-transform: uppercase; }}
    .ai-copy {{ color: var(--text); line-height: 1.58; font-size: 13px; }}
    .module-block {{ margin-top: 10px; }}
    .empty-state {{ color: var(--soft); font-size: 14px; padding: 10px 0; }}
    .bullish {{ color: var(--bull); }}
    .bearish {{ color: var(--bear); }}
    .neutral {{ color: var(--soft); }}
    .caution {{ color: var(--amber); }}
    @media (max-width: 1280px) {{
      .terminal-shell {{ grid-template-columns: 240px minmax(0, 1fr); }}
      .global-live-strip,
      .state-board {{ grid-template-columns: repeat(2, minmax(0, 1fr)); }}
      .span-3,
      .span-4,
      .span-5,
      .span-6,
      .span-7,
      .span-8 {{ grid-column: span 12; }}
      .metric-strip {{ grid-template-columns: repeat(2, minmax(0, 1fr)); }}
    }}
    @media (max-width: 900px) {{
      .page,
      .terminal-shell,
      .workspace {{ width: 100vw; max-width: 100vw; }}
      .terminal-shell {{ grid-template-columns: minmax(0, 1fr); overflow-x: hidden; }}
      .side-rail {{ display: none; }}
      .workspace {{ padding: 14px 10px 20px; }}
      .topbar {{ margin: -14px -10px 14px; padding: 10px; align-items: flex-start; flex-direction: column; }}
      .topbar-brand,
      .top-nav,
      .top-status {{ max-width: 100%; }}
      .top-status {{ width: 100%; min-width: 0; justify-content: flex-start; flex-wrap: nowrap; padding-bottom: 2px; }}
      .status-pill {{ flex: 0 0 auto; }}
      .top-nav {{ display: flex; width: 100%; min-width: 0; gap: 6px; overflow-x: auto; padding-bottom: 2px; scrollbar-width: none; }}
      .top-nav::-webkit-scrollbar {{ display: none; }}
      .top-nav a {{
        flex: 0 0 auto;
        padding: 8px 9px;
        border: 1px solid var(--line);
        border-radius: 6px;
        color: var(--soft);
        font-family: "Space Grotesk", monospace;
        font-size: 11px;
        font-weight: 800;
        letter-spacing: 0.08em;
        text-transform: uppercase;
        text-decoration: none;
      }}
      .top-nav a.active {{ color: var(--amber); border-color: rgba(212, 175, 55, 0.42); background: rgba(212, 175, 55, 0.08); }}
      .terminal-header {{ align-items: flex-start; flex-direction: column; }}
      .terminal-header h1 {{ max-width: 100%; font-size: 28px; line-height: 1.05; }}
      .sync-pill {{ white-space: normal; }}
      .global-live-strip,
      .state-board,
      .metric-strip,
      .trade-levels,
      .key-levels,
      .scenario-grid,
      .scenario-plan-grid,
      .geo-columns {{ grid-template-columns: 1fr; }}
      .ticker-row {{ flex-direction: column; align-items: flex-start; }}
      .ticker-price {{ font-size: 48px; }}
      .technical-table {{ min-width: 720px; }}
    }}
  </style>
</head>
<body>
  <main class="page" id="dashboard-app">
    <div class="terminal-shell">
      <aside class="side-rail">
        <div class="brand">FOURNIWELL<br>SIGNALS</div>
        <div class="rail-card">
          <strong>Terminal XAUUSD</strong>
          <span>Gold/USD intraday intelligence</span>
          <div class="rail-status">Live analysis</div>
        </div>
        <nav class="rail-nav" aria-label="Sections dashboard">
          {nav_links("rail-link")}
        </nav>
      </aside>
      <div class="workspace">
        <header class="topbar">
          <div class="topbar-brand">FOURNIWELL SIGNALS</div>
          <nav class="top-nav" aria-label="Navigation mobile">
            {nav_links("top-nav-link")}
          </nav>
          <div class="top-status">
            <span class="status-pill {price_class}">XAU {gold.price:.2f} / {gold.change_pct:+.2f}%</span>
            <span class="status-pill {lead_class}">Chef de file {html.escape(lead_status)} {lead_score}/100</span>
            <span class="status-pill {locked_class}">{locked_status}</span>
            <span class="status-pill">{html.escape(generated_at)}</span>
          </div>
        </header>

        <section class="terminal-header">
          <div>
            <div class="section-kicker">Institutional analytics package</div>
            <h1>Fourniwell Signals Trading Desk</h1>
            <p>Prix, chef de file, biais, charte live et signal locked. Les details internes restent dans Inspector.</p>
          </div>
          <div class="sync-pill">Ready for export</div>
        </section>

        <section class="global-live-strip {banner_class}" data-verdict="{html.escape(lead_status)}" data-regime="{html.escape(regime_name)}" data-alert="{html.escape(regime_alert)}">
          <div class="live-cell">
            <small>XAU/USD live</small>
            <strong class="{price_class}">{gold.price:.2f}</strong>
            <span>{gold.change_abs:+.2f} / {gold.change_pct:+.2f}%</span>
          </div>
          <div class="live-cell">
            <small>Chef de file</small>
            <strong class="{lead_class}">{html.escape(lead_status)}</strong>
            <span>{html.escape(lead_bias)} · {lead_score}/100</span>
          </div>
          <div class="live-cell">
            <small>Biais</small>
            <strong>{html.escape(format_bias_label(analysis.bias))}</strong>
            <span>Confiance {analysis.confidence}/100</span>
          </div>
          <div class="live-cell">
            <small>Signal locked</small>
            <strong class="{locked_class}">{locked_status}</strong>
            <span>{active_trades} trade(s) actif(s)</span>
          </div>
          <div class="live-cell">
            <small>News Reaction</small>
            <strong class="{news_reaction_class}">{html.escape(news_reaction_setup.status)}</strong>
            <span>{html.escape(news_reaction_setup.direction)} · {news_reaction_setup.confirmation_score}/4</span>
          </div>
          {weekend_gold_cell}
          <div class="live-cell">
            <small>Refresh</small>
            <strong>{html.escape(generated_at)}</strong>
            <span>Sources {data_quality_score}/100 · {html.escape(data_quality_status)}</span>
          </div>
        </section>

        <section class="tab-view active" id="desk" data-tab-view="desk">
          <div class="view-header">
            <div><div class="section-kicker">Desk</div><h2>Decision exploitable et charte live</h2><p>La premiere page ne montre que ce qui sert a decider: prix, chef de file, biais, TradingView et signal locked.</p></div>
          </div>
          <section class="layout-desk">
            <article class="decision-hero span-8">
              <div class="ticker-symbol">XAU/USD spot | live</div>
              <div class="ticker-row">
                <div class="ticker-price {price_class}">{gold.price:.2f}</div>
                <div class="ticker-delta {price_class}">{gold.change_abs:+.2f} / {gold.change_pct:+.2f}%</div>
              </div>
              <div class="ticker-meta">
                Mis a jour {html.escape(generated_at)} · Source prix spot: <a href="{INVESTING_XAUUSD_URL}" target="_blank" rel="noopener noreferrer">Investing.com XAU/USD</a><br>
                Range du jour: {format_number(gold.day_low)} / {format_number(gold.day_high)}
              </div>
              {render_desk_position_summary(global_recommendation, orchestrator_decision, scenario_plan, trade_ledger)}
              <div class="metric-strip">
                <div class="metric-chip"><strong>Biais</strong><span class="{price_class}">{format_bias_label(analysis.bias)}</span><small>Lecture globale du moment</small></div>
                <div class="metric-chip"><strong>Confiance</strong><span>{analysis.confidence}/100</span><div class="confidence-bar"><span></span></div></div>
                <div class="metric-chip"><strong>DXY</strong><span class="{dxy_class}">{dxy.price:.2f}</span><small>{dxy.change_pct:+.2f}% aujourd'hui</small></div>
                <div class="metric-chip"><strong>10Y US</strong><span class="{us10y_class}">{us10y.price:.2f}%</span><small>{us10y.change_abs * 100:+.1f} bps aujourd'hui</small></div>
              </div>
            </article>
            <article class="panel span-4">
              <div class="section-kicker">Signal locked</div>
              <h2>Position historisee</h2>
              {render_signal_locked_panel(trade_ledger, global_recommendation, orchestrator_decision, scenario_plan)}
            </article>
            <article class="panel span-12">
              <div class="section-kicker">Reversal Engine</div>
              <h2>Scalp, Intraday, Swing</h2>
              {render_reversal_panels(reversal_engine)}
            </article>
            <article class="panel span-12">
              <div class="section-kicker">Charte live TradingView</div>
              <h2>XAU/USD live chart</h2>
              {tradingview_chart}
            </article>
          </section>
        </section>

        <section class="tab-view" id="agents" data-tab-view="agents">
          <div class="view-header"><div><div class="section-kicker">Agents</div><h2>Scoring et position de chaque agent</h2><p>Cette page montre qui pousse BUY, SELL, WATCH ou WAIT. Les details techniques restent en bas ou dans Inspector.</p></div></div>
          <section class="layout-agents">
            <article class="panel span-12"><div class="section-kicker">Scoreboard</div><h2>Positions agents</h2>{render_agents_scoreboard_panel(agent_results, settings_payload)}</article>
            <article class="panel span-12"><div class="section-kicker">Orchestrateur v3</div><h2>Vote final, poids et contre-signaux</h2>{render_orchestrator_decision_panel(orchestrator_decision)}</article>
            <article class="panel span-6"><div class="section-kicker">Scenario Engine v3</div><h2>Scenario, declencheur et invalidation</h2>{render_scenario_plan_panel(scenario_plan)}</article>
            <article class="panel span-6"><div class="section-kicker">Data Feed Governance</div><h2>Qualite, fraicheur et fiabilite des sources</h2>{render_data_quality_panel(data_quality)}</article>
            <article class="panel span-12"><div class="section-kicker">Contradictions</div><h2>Conflits entre agents</h2>{render_agent_contradictions(agent_results)}</article>
          </section>
        </section>

        <section class="tab-view" id="news" data-tab-view="news">
          <div class="view-header"><div><div class="section-kicker">News Flow</div><h2>Flux d'informations utiles</h2><p>Titres recents, source, heure et impact. Les headlines neutres, chaines internes et textes d'audit sont masques.</p></div></div>
          <section class="layout-news">
            <article class="panel span-12"><div class="section-kicker">News Reaction Engine</div><h2>Evenement rapide</h2>{render_news_reaction_panel(news_reaction_setup)}</article>
            <article class="panel span-12"><div class="section-kicker">Flux trie</div><h2>News avec impact XAU/USD</h2>{render_news_flow_panel(bundle.news, event_facts, political_statements)}</article>
            <article class="panel span-12"><div class="section-kicker">Macro Catalysts</div><h2>Calendrier a surveiller</h2>{render_macro_catalysts_panel(macro_catalysts)}</article>
            <article class="panel span-12"><div class="section-kicker">COT officiel CFTC</div><h2>Positionnement Gold Futures COMEX</h2>{render_cftc_positioning_panel(cftc_positioning)}</article>
            <article class="panel span-12"><div class="section-kicker">WGC / ETF gold flows</div><h2>Flux ETF or officiels</h2>{render_etf_flows_panel(etf_flows_analysis)}</article>
          </section>
        </section>

        <section class="tab-view" id="inspector" data-tab-view="inspector">
          <div class="view-header"><div><div class="section-kicker">Inspector</div><h2>Audit sources, agents, gates et trades</h2><p>Tout ce qui explique pourquoi une decision ou un trade existe.</p></div></div>
          <section class="layout-inspector">
            <article class="panel span-12"><div class="section-kicker">Monitoring / Audit / Inspector</div><h2>Flux, sources, agents et trades</h2>{render_monitoring_inspector_panel(generated_at, data_quality, agent_results, trade_ledger, orchestrator_decision, global_recommendation, market_regime, chart_store, strategy_candidates, strategy_selection)}</article>
            <article class="panel span-12"><div class="section-kicker">Source Registry</div><h2>Gouvernance des flux d'information</h2>{render_data_quality_panel(data_quality)}</article>
            <article class="panel span-12"><div class="section-kicker">Regime interne</div><h2>Mode politique / petrole / dollar</h2>{render_market_regime_panel(market_regime, cross_asset_analysis)}</article>
            <article class="panel span-12"><div class="section-kicker">Event Facts</div><h2>Faits detectes, sources et chaines marche</h2>{render_event_facts_panel(event_facts)}</article>
            <article class="panel span-12"><div class="section-kicker">Political Statements</div><h2>Declarations politiques sourcees</h2>{render_political_statements_panel(political_statements)}</article>
            <article class="panel span-12"><div class="section-kicker">News Reaction Engine</div><h2>Details latence et blocages</h2>{render_news_reaction_panel(news_reaction_setup)}</article>
            <article class="panel span-12"><div class="section-kicker">Confluence inter-marches</div><h2>Cross-assets, DXY, taux reels et confirmations</h2>{render_cross_asset_panel(cross_asset_analysis, real_yield)}</article>
            <article class="panel span-12"><div class="section-kicker">COT officiel CFTC</div><h2>Positionnement Gold Futures COMEX</h2>{render_cftc_positioning_panel(cftc_positioning)}</article>
            <article class="panel span-12"><div class="section-kicker">ETF flows officiels</div><h2>WGC + GLD + IAU</h2>{render_etf_flows_panel(etf_flows_analysis)}</article>
            <article class="panel span-12"><div class="section-kicker">Bloc macro officiel</div><h2>FRED DGS10 | DGS2 | T10YIE | DFII10</h2>{render_official_macro_panel(official_macro_rates, us10y)}</article>
            <article class="panel span-12"><div class="section-kicker">Chart Store OHLC</div><h2>Diagnostic donnees OHLC internes</h2>{render_chart_store_panel(chart_store)}</article>
            <article class="panel span-12"><div class="section-kicker">Settings</div><h2>Controle utilisateur</h2>{render_settings_panel(settings_payload, settings_validation_payload)}</article>
            <article class="panel span-12"><div class="section-kicker">Fondation multi-agents passive</div><h2>Inventaire agents</h2>{render_agent_department_panel(agent_results, "Market")}{render_agent_department_panel(agent_results, "Decision")}{render_agent_department_panel(agent_results, "Technical")}{render_agent_department_panel(agent_results, "Macro")}{render_agent_department_panel(agent_results, "Geopolitics & Flows")}</article>
          </section>
        </section>

        <section class="tab-view" id="reports" data-tab-view="reports">
          <div class="view-header"><div><div class="section-kicker">Reports</div><h2>Exports et documentation locale</h2><p>Les rapports restent simples: chemins, donnees et avertissement.</p></div></div>
          <section class="layout-reports">
            {render_ai_summary(ai_analysis)}
            <article class="panel span-6"><div class="section-kicker">Exports</div><h2>Rapports disponibles</h2><div class="decision-grid"><div class="decision-item"><strong>Markdown</strong><span>Le rapport principal est genere dans reports/xauusd_report.md.</span></div><div class="decision-item"><strong>JSON</strong><span>Le payload structure est genere dans reports/xauusd_data.json.</span></div><div class="decision-item"><strong>Dernier calcul</strong><span>{html.escape(generated_at)}</span></div></div></article>
            <article class="panel span-6"><div class="section-kicker">Avertissement</div><h2>Usage</h2><div class="footer-note">Ce dashboard aide a lire le marche rapidement. Il ne constitue pas un conseil financier personnalise. Un TradePlan historise ne doit pas etre confondu avec le signal live.</div></article>
            <article class="panel span-12"><div class="section-kicker">Reports v3</div><h2>Rapports generes</h2>{render_reports_v3_links_panel(reports_v3_payload)}</article>
            <article class="panel span-12"><div class="section-kicker">Trade Ledger</div><h2>Historique des TradePlan verrouilles</h2>{render_trade_tracker_panel(trade_ledger)}</article>
          </section>
        </section>
      </div>
    </div>
  </main>
{live_script}
</body>
</html>"""

def extract_dashboard_main_inner(html_document: str) -> str:
    marker = '<main class="page" id="dashboard-app">'
    start = html_document.find(marker)
    if start < 0:
        raise RuntimeError("Impossible de localiser le conteneur principal du dashboard.")
    start += len(marker)
    end = html_document.find("</main>", start)
    if end < 0:
        raise RuntimeError("Impossible de localiser la fin du conteneur principal du dashboard.")
    return html_document[start:end]


def fetch_local_free_context(
    gold: SymbolSnapshot,
    dxy: SymbolSnapshot,
    us10y: SymbolSnapshot,
    news: list[NewsItem],
    technical_readings: list[TechnicalReading],
    macro_catalysts: MacroCatalystCalendar | None = None,
) -> tuple[
    SymbolSnapshot | None,
    OfficialMacroRates,
    CrossAssetAnalysis,
    EventModeAnalysis,
    MarketRegimeAnalysis,
    SymbolSnapshot | None,
    SymbolSnapshot | None,
]:
    def cached_snapshot(key: str, loader: Any) -> SymbolSnapshot | None:
        now = time.time()
        cached = LOCAL_CONTEXT_SNAPSHOT_CACHE.get(key)
        if cached and (now - cached[0]) < LOCAL_CONTEXT_CACHE_SECONDS:
            return copy.deepcopy(cached[1])
        snapshot = loader()
        LOCAL_CONTEXT_SNAPSHOT_CACHE[key] = (now, copy.deepcopy(snapshot))
        return snapshot

    dgs10 = cached_snapshot("fred_dgs10", lambda: fetch_fred_series_snapshot("DGS10", FRED_SERIES_LABELS["DGS10"]))
    dgs2 = cached_snapshot("fred_dgs2", lambda: fetch_fred_series_snapshot("DGS2", FRED_SERIES_LABELS["DGS2"]))
    dgs3m = cached_snapshot("fred_dgs3m", lambda: fetch_fred_series_snapshot("DGS3MO", FRED_SERIES_LABELS["DGS3MO"]))
    dgs30 = cached_snapshot("fred_dgs30", lambda: fetch_fred_series_snapshot("DGS30", FRED_SERIES_LABELS["DGS30"]))
    breakeven_10y = cached_snapshot("fred_t10yie", lambda: fetch_fred_series_snapshot("T10YIE", FRED_SERIES_LABELS["T10YIE"]))
    real_yield = cached_snapshot("fred_dfii10", fetch_real_yield_snapshot)
    official_macro_rates = build_official_macro_rates(dgs10, dgs2, dgs3m, dgs30, breakeven_10y, real_yield, us10y)
    dxy_cross = cached_snapshot(
        "dxy_cross",
        lambda: fetch_optional_symbol_snapshot("DX-Y.NYB", "US Dollar Index", interval="1d", data_range="6mo"),
    )
    gold_proxy = cached_snapshot(
        "gold_proxy",
        lambda: fetch_optional_symbol_snapshot(*CROSS_ASSET_SYMBOLS["gold_proxy"], interval="1d", data_range="6mo"),
    )
    usdjpy = cached_snapshot(
        "usdjpy",
        lambda: fetch_optional_symbol_snapshot(*CROSS_ASSET_SYMBOLS["usdjpy"], interval="1d", data_range="6mo"),
    )
    silver = cached_snapshot(
        "silver",
        lambda: fetch_optional_symbol_snapshot(*CROSS_ASSET_SYMBOLS["silver"], interval="1d", data_range="6mo"),
    )
    gdx = cached_snapshot(
        "gdx",
        lambda: fetch_optional_symbol_snapshot(*CROSS_ASSET_SYMBOLS["gdx"], interval="1d", data_range="6mo"),
    )
    gdxj = cached_snapshot(
        "gdxj",
        lambda: fetch_optional_symbol_snapshot(*CROSS_ASSET_SYMBOLS["gdxj"], interval="1d", data_range="6mo"),
    )
    audusd = cached_snapshot(
        "audusd",
        lambda: fetch_optional_symbol_snapshot(*CROSS_ASSET_SYMBOLS["audusd"], interval="1d", data_range="6mo"),
    )
    usdchf = cached_snapshot(
        "usdchf",
        lambda: fetch_optional_symbol_snapshot(*CROSS_ASSET_SYMBOLS["usdchf"], interval="1d", data_range="6mo"),
    )
    tip = cached_snapshot(
        "tip",
        lambda: fetch_optional_symbol_snapshot(*CROSS_ASSET_SYMBOLS["tip"], interval="1d", data_range="6mo"),
    )
    spx = cached_snapshot(
        "spx",
        lambda: fetch_optional_symbol_snapshot(*CROSS_ASSET_SYMBOLS["spx"], interval="1d", data_range="6mo"),
    )
    gvz = cached_snapshot(
        "gvz",
        lambda: fetch_optional_symbol_snapshot(*CROSS_ASSET_SYMBOLS["gvz"], interval="1d", data_range="6mo"),
    )
    vix = cached_snapshot(
        "vix",
        lambda: fetch_optional_symbol_snapshot(*CROSS_ASSET_SYMBOLS["vix"], interval="1d", data_range="6mo"),
    )
    wti = cached_snapshot(
        "wti",
        lambda: fetch_optional_symbol_snapshot(*CROSS_ASSET_SYMBOLS["wti"], interval="1d", data_range="6mo"),
    )
    brent = cached_snapshot(
        "brent",
        lambda: fetch_optional_symbol_snapshot(*CROSS_ASSET_SYMBOLS["brent"], interval="1d", data_range="6mo"),
    )
    cross_asset = build_cross_asset_analysis(
        dxy_cross or dxy,
        real_yield,
        usdjpy,
        silver,
        gvz,
        vix,
        gold_proxy=gold_proxy,
        gdx=gdx,
        gdxj=gdxj,
        audusd=audusd,
        usdchf=usdchf,
        tip=tip,
        spx=spx,
        wti=wti,
        brent=brent,
    )
    event_mode = build_event_mode_analysis(gold, technical_readings, gvz, vix, macro_catalysts)
    market_regime = build_market_regime_analysis(gold, dxy, us10y, news, wti=wti, brent=brent, event_mode=event_mode)
    return real_yield, official_macro_rates, cross_asset, event_mode, market_regime, wti, brent


def build_live_bundle(base_bundle: BriefingBundle) -> BriefingBundle:
    user_settings, settings_validation = load_user_settings(create_if_missing=True)
    live_bundle = copy.deepcopy(base_bundle)
    gold = fetch_investing_xauusd_snapshot(include_historical=False)
    weekend_gold = fetch_ig_weekend_gold_snapshot()
    dxy = fetch_symbol_snapshot("DX-Y.NYB", "US Dollar Index", interval="1d", data_range="1mo")
    us10y = fetch_symbol_snapshot("^TNX", "US 10Y", interval="1d", data_range="1mo")
    technical_readings, proxy_price, points_5m, chart_store = fetch_technical_timeframes()
    gold.intraday_points = align_proxy_points_to_spot(points_5m, gold.price)
    real_yield, official_macro_rates, cross_asset_analysis, event_mode, market_regime, wti, brent = fetch_local_free_context(
        gold,
        dxy,
        us10y,
        live_bundle.news,
        technical_readings,
        live_bundle.macro_catalysts,
    )
    analysis = analyze_market(
        gold,
        dxy,
        us10y,
        live_bundle.news,
        real_yield=real_yield,
        cross_asset=cross_asset_analysis,
        event_mode=event_mode,
        market_regime=market_regime,
        cftc_positioning=live_bundle.cftc_positioning,
        etf_flows_analysis=live_bundle.etf_flows_analysis,
    )
    geopolitical_analysis = analysis.geopolitical
    event_facts = build_event_facts(
        live_bundle.news, wti=wti, brent=brent, dxy=dxy, us10y=us10y, gold=gold
    )
    political_statements = live_bundle.political_statements
    data_quality = build_data_quality_snapshot(
        gold,
        dxy,
        us10y,
        live_bundle.news,
        real_yield=real_yield,
        official_macro_rates=official_macro_rates,
        cftc_positioning=live_bundle.cftc_positioning,
        etf_flows_analysis=live_bundle.etf_flows_analysis,
        macro_catalysts=live_bundle.macro_catalysts,
        cross_asset_analysis=cross_asset_analysis,
        weekend_gold=weekend_gold,
        market_regime=market_regime,
        political_statements=political_statements,
        chart_store=chart_store,
    )
    atr_15m = next(reading.atr14 for reading in technical_readings if reading.timeframe == "15m")
    fundamental_recommendation = build_fundamental_recommendation(
        gold,
        dxy,
        us10y,
        analysis,
        atr_15m,
        real_yield=real_yield,
        cross_asset=cross_asset_analysis,
        event_mode=event_mode,
    )
    technical_recommendation = build_technical_recommendation(
        gold,
        technical_readings,
        proxy_price,
        event_mode=event_mode,
    )
    technical_decision = build_technical_decision(
        gold,
        technical_readings,
        proxy_price,
        cross_asset=cross_asset_analysis,
        event_mode=event_mode,
        data_quality=data_quality,
    )
    global_recommendation = build_global_recommendation(
        gold,
        analysis,
        fundamental_recommendation,
        technical_recommendation,
        geopolitical=geopolitical_analysis,
        cross_asset=cross_asset_analysis,
        event_mode=event_mode,
    )
    executive_summary = build_executive_summary(
        fundamental_recommendation,
        technical_recommendation,
        geopolitical_analysis,
    )
    agent_results = build_passive_agent_results(
        gold,
        dxy,
        us10y,
        live_bundle.news,
        analysis,
        geopolitical_analysis=geopolitical_analysis,
        fundamental_recommendation=fundamental_recommendation,
        technical_recommendation=technical_recommendation,
        technical_decision=technical_decision,
        global_recommendation=global_recommendation,
        technical_timeframes=technical_readings,
        real_yield=real_yield,
        official_macro_rates=official_macro_rates,
        cftc_positioning=live_bundle.cftc_positioning,
        etf_flows_analysis=live_bundle.etf_flows_analysis,
        macro_catalysts=live_bundle.macro_catalysts,
        data_quality=data_quality,
        cross_asset_analysis=cross_asset_analysis,
        event_mode=event_mode,
        weekend_gold=weekend_gold,
        market_regime=market_regime,
        event_facts=event_facts,
        political_statements=political_statements,
    )
    agent_results = apply_user_settings_to_agents(agent_results, user_settings)
    legacy_global_recommendation = global_recommendation
    global_recommendation, orchestrator_decision = build_orchestrator_decision(
        gold,
        legacy_global_recommendation,
        agent_results,
        data_quality=data_quality,
        market_regime=market_regime,
        event_mode=event_mode,
        technical_decision=technical_decision,
    )
    agent_results = update_orchestrator_agent(agent_results, orchestrator_decision)
    agent_results = apply_user_settings_to_agents(agent_results, user_settings)
    scenario_plan = build_scenario_plan(
        gold,
        technical_decision,
        global_recommendation,
        fundamental_recommendation=fundamental_recommendation,
        cross_asset=cross_asset_analysis,
        market_regime=market_regime,
        event_facts=event_facts,
        data_quality=data_quality,
    )
    news_reaction_setup = build_news_reaction_engine(
        event_facts,
        gold,
        dxy,
        us10y,
        cross_asset=cross_asset_analysis,
        data_quality=data_quality,
    )
    reversal_engine = build_reversal_engine(gold, technical_readings, chart_store)
    trade_ledger = build_trade_ledger_summary(
        gold,
        global_recommendation,
        data_quality,
        agent_results,
        market_regime,
        event_facts,
        technical_readings,
        settings=user_settings,
        macro_catalysts=live_bundle.macro_catalysts,
        technical_decision=technical_decision,
        event_mode=event_mode,
    )
    strategy_candidates = build_strategy_candidates(
        gold,
        technical_readings,
        chart_store,
        news_reaction_setup=news_reaction_setup,
        event_mode=event_mode,
    )
    strategy_selection = build_strategy_selection(
        strategy_candidates,
        event_mode=event_mode,
        trade_ledger=trade_ledger,
        min_rr=user_settings.minimum_risk_reward,
    )
    append_multi_strategy_history(gold, strategy_candidates, strategy_selection)
    payload = build_payload(
        gold,
        dxy,
        us10y,
        live_bundle.news,
        analysis,
        geopolitical_analysis=geopolitical_analysis,
        fundamental_recommendation=fundamental_recommendation,
        technical_recommendation=technical_recommendation,
        technical_decision=technical_decision,
        scenario_plan=scenario_plan,
        global_recommendation=global_recommendation,
        technical_timeframes=technical_readings,
        real_yield=real_yield,
        official_macro_rates=official_macro_rates,
        cftc_positioning=live_bundle.cftc_positioning,
        etf_flows_analysis=live_bundle.etf_flows_analysis,
        macro_catalysts=live_bundle.macro_catalysts,
        data_quality=data_quality,
        cross_asset_analysis=cross_asset_analysis,
        event_mode=event_mode,
        weekend_gold=weekend_gold,
        market_regime=market_regime,
        event_facts=event_facts,
        political_statements=political_statements,
        agent_results=agent_results,
        trade_ledger=trade_ledger,
        orchestrator_decision=orchestrator_decision,
        chart_store=chart_store,
        news_reaction_setup=news_reaction_setup,
        reversal_engine=reversal_engine,
        strategy_candidates=strategy_candidates,
        strategy_selection=strategy_selection,
        settings=user_settings,
        settings_validation=settings_validation,
    )
    payload["executive_summary"] = executive_summary
    if live_bundle.ai_analysis:
        payload["ai_summary"] = live_bundle.ai_analysis

    live_bundle.gold = gold
    live_bundle.dxy = dxy
    live_bundle.us10y = us10y
    live_bundle.analysis = analysis
    live_bundle.payload = payload
    live_bundle.geopolitical_analysis = geopolitical_analysis
    live_bundle.fundamental_recommendation = fundamental_recommendation
    live_bundle.technical_recommendation = technical_recommendation
    live_bundle.technical_decision = technical_decision
    live_bundle.scenario_plan = scenario_plan
    live_bundle.global_recommendation = global_recommendation
    live_bundle.technical_timeframes = technical_readings
    live_bundle.executive_summary = executive_summary
    live_bundle.real_yield = real_yield
    live_bundle.official_macro_rates = official_macro_rates
    live_bundle.cftc_positioning = live_bundle.cftc_positioning
    live_bundle.etf_flows_analysis = live_bundle.etf_flows_analysis
    live_bundle.macro_catalysts = live_bundle.macro_catalysts
    live_bundle.data_quality = data_quality
    live_bundle.cross_asset_analysis = cross_asset_analysis
    live_bundle.event_mode = event_mode
    live_bundle.weekend_gold = weekend_gold
    live_bundle.market_regime = market_regime
    live_bundle.event_facts = event_facts
    live_bundle.political_statements = political_statements
    live_bundle.agent_results = agent_results
    live_bundle.trade_ledger = trade_ledger
    live_bundle.orchestrator_decision = orchestrator_decision
    live_bundle.chart_store = chart_store
    live_bundle.news_reaction_setup = news_reaction_setup
    live_bundle.reversal_engine = reversal_engine
    live_bundle.strategy_candidates = strategy_candidates
    live_bundle.strategy_selection = strategy_selection
    return live_bundle


def build_briefing(top_news: int, include_ai: bool = True) -> BriefingBundle:
    user_settings, settings_validation = load_user_settings(create_if_missing=True)
    gold = fetch_investing_xauusd_snapshot(include_historical=True)
    weekend_gold = fetch_ig_weekend_gold_snapshot()
    dxy = fetch_symbol_snapshot("DX-Y.NYB", "US Dollar Index", interval="1d", data_range="1mo")
    us10y = fetch_symbol_snapshot("^TNX", "US 10Y", interval="1d", data_range="1mo")
    news = fetch_news(top_news)
    political_news = fetch_political_statement_news(limit=max(8, top_news))
    news = merge_news_items(news, political_news, max(top_news, 24))
    cftc_positioning = fetch_cftc_gold_positioning()
    etf_flows_analysis = fetch_etf_flows_analysis()
    macro_catalysts = build_macro_catalyst_calendar()
    technical_readings, proxy_price, points_5m, chart_store = fetch_technical_timeframes()
    gold.intraday_points = align_proxy_points_to_spot(points_5m, gold.price)
    real_yield, official_macro_rates, cross_asset_analysis, event_mode, market_regime, wti, brent = fetch_local_free_context(
        gold,
        dxy,
        us10y,
        news,
        technical_readings,
        macro_catalysts,
    )
    analysis = analyze_market(
        gold,
        dxy,
        us10y,
        news,
        real_yield=real_yield,
        cross_asset=cross_asset_analysis,
        event_mode=event_mode,
        market_regime=market_regime,
        cftc_positioning=cftc_positioning,
        etf_flows_analysis=etf_flows_analysis,
    )
    geopolitical_analysis = analysis.geopolitical
    event_facts = build_event_facts(news, wti=wti, brent=brent, dxy=dxy, us10y=us10y, gold=gold)
    political_statements = build_political_statements(news)
    data_quality = build_data_quality_snapshot(
        gold,
        dxy,
        us10y,
        news,
        real_yield=real_yield,
        official_macro_rates=official_macro_rates,
        cftc_positioning=cftc_positioning,
        etf_flows_analysis=etf_flows_analysis,
        macro_catalysts=macro_catalysts,
        cross_asset_analysis=cross_asset_analysis,
        weekend_gold=weekend_gold,
        market_regime=market_regime,
        political_statements=political_statements,
        chart_store=chart_store,
    )
    atr_15m = next(reading.atr14 for reading in technical_readings if reading.timeframe == "15m")
    fundamental_recommendation = build_fundamental_recommendation(
        gold,
        dxy,
        us10y,
        analysis,
        atr_15m,
        real_yield=real_yield,
        cross_asset=cross_asset_analysis,
        event_mode=event_mode,
    )
    technical_recommendation = build_technical_recommendation(
        gold,
        technical_readings,
        proxy_price,
        event_mode=event_mode,
    )
    technical_decision = build_technical_decision(
        gold,
        technical_readings,
        proxy_price,
        cross_asset=cross_asset_analysis,
        event_mode=event_mode,
        data_quality=data_quality,
    )
    global_recommendation = build_global_recommendation(
        gold,
        analysis,
        fundamental_recommendation,
        technical_recommendation,
        geopolitical=geopolitical_analysis,
        cross_asset=cross_asset_analysis,
        event_mode=event_mode,
    )
    executive_summary = build_executive_summary(
        fundamental_recommendation,
        technical_recommendation,
        geopolitical_analysis,
    )
    agent_results = build_passive_agent_results(
        gold,
        dxy,
        us10y,
        news,
        analysis,
        geopolitical_analysis=geopolitical_analysis,
        fundamental_recommendation=fundamental_recommendation,
        technical_recommendation=technical_recommendation,
        technical_decision=technical_decision,
        global_recommendation=global_recommendation,
        technical_timeframes=technical_readings,
        real_yield=real_yield,
        official_macro_rates=official_macro_rates,
        cftc_positioning=cftc_positioning,
        etf_flows_analysis=etf_flows_analysis,
        macro_catalysts=macro_catalysts,
        data_quality=data_quality,
        cross_asset_analysis=cross_asset_analysis,
        event_mode=event_mode,
        weekend_gold=weekend_gold,
        market_regime=market_regime,
        event_facts=event_facts,
        political_statements=political_statements,
    )
    agent_results = apply_user_settings_to_agents(agent_results, user_settings)
    legacy_global_recommendation = global_recommendation
    global_recommendation, orchestrator_decision = build_orchestrator_decision(
        gold,
        legacy_global_recommendation,
        agent_results,
        data_quality=data_quality,
        market_regime=market_regime,
        event_mode=event_mode,
        technical_decision=technical_decision,
    )
    agent_results = update_orchestrator_agent(agent_results, orchestrator_decision)
    agent_results = apply_user_settings_to_agents(agent_results, user_settings)
    scenario_plan = build_scenario_plan(
        gold,
        technical_decision,
        global_recommendation,
        fundamental_recommendation=fundamental_recommendation,
        cross_asset=cross_asset_analysis,
        market_regime=market_regime,
        event_facts=event_facts,
        data_quality=data_quality,
    )
    news_reaction_setup = build_news_reaction_engine(
        event_facts,
        gold,
        dxy,
        us10y,
        cross_asset=cross_asset_analysis,
        data_quality=data_quality,
    )
    reversal_engine = build_reversal_engine(gold, technical_readings, chart_store)
    trade_ledger = build_trade_ledger_summary(
        gold,
        global_recommendation,
        data_quality,
        agent_results,
        market_regime,
        event_facts,
        technical_readings,
        settings=user_settings,
        macro_catalysts=macro_catalysts,
        technical_decision=technical_decision,
        event_mode=event_mode,
    )
    strategy_candidates = build_strategy_candidates(
        gold,
        technical_readings,
        chart_store,
        news_reaction_setup=news_reaction_setup,
        event_mode=event_mode,
    )
    strategy_selection = build_strategy_selection(
        strategy_candidates,
        event_mode=event_mode,
        trade_ledger=trade_ledger,
        min_rr=user_settings.minimum_risk_reward,
    )
    append_multi_strategy_history(gold, strategy_candidates, strategy_selection)
    payload = build_payload(
        gold,
        dxy,
        us10y,
        news,
        analysis,
        geopolitical_analysis=geopolitical_analysis,
        fundamental_recommendation=fundamental_recommendation,
        technical_recommendation=technical_recommendation,
        technical_decision=technical_decision,
        scenario_plan=scenario_plan,
        global_recommendation=global_recommendation,
        technical_timeframes=technical_readings,
        real_yield=real_yield,
        official_macro_rates=official_macro_rates,
        cftc_positioning=cftc_positioning,
        etf_flows_analysis=etf_flows_analysis,
        macro_catalysts=macro_catalysts,
        data_quality=data_quality,
        cross_asset_analysis=cross_asset_analysis,
        event_mode=event_mode,
        weekend_gold=weekend_gold,
        market_regime=market_regime,
        event_facts=event_facts,
        political_statements=political_statements,
        agent_results=agent_results,
        trade_ledger=trade_ledger,
        orchestrator_decision=orchestrator_decision,
        chart_store=chart_store,
        news_reaction_setup=news_reaction_setup,
        reversal_engine=reversal_engine,
        strategy_candidates=strategy_candidates,
        strategy_selection=strategy_selection,
        settings=user_settings,
        settings_validation=settings_validation,
    )
    payload["executive_summary"] = executive_summary
    ai_analysis = call_openai_analysis(payload) if include_ai else None

    if ai_analysis:
        payload["ai_summary"] = ai_analysis

    return BriefingBundle(
        gold=gold,
        dxy=dxy,
        us10y=us10y,
        news=news,
        analysis=analysis,
        payload=payload,
        ai_analysis=ai_analysis,
        geopolitical_analysis=geopolitical_analysis,
        fundamental_recommendation=fundamental_recommendation,
        technical_recommendation=technical_recommendation,
        technical_decision=technical_decision,
        scenario_plan=scenario_plan,
        global_recommendation=global_recommendation,
        technical_timeframes=technical_readings,
        executive_summary=executive_summary,
        real_yield=real_yield,
        official_macro_rates=official_macro_rates,
        cftc_positioning=cftc_positioning,
        etf_flows_analysis=etf_flows_analysis,
        macro_catalysts=macro_catalysts,
        data_quality=data_quality,
        cross_asset_analysis=cross_asset_analysis,
        event_mode=event_mode,
        weekend_gold=weekend_gold,
        market_regime=market_regime,
        event_facts=event_facts,
        political_statements=political_statements,
        agent_results=agent_results,
        trade_ledger=trade_ledger,
        orchestrator_decision=orchestrator_decision,
        chart_store=chart_store,
        news_reaction_setup=news_reaction_setup,
        reversal_engine=reversal_engine,
        strategy_candidates=strategy_candidates,
        strategy_selection=strategy_selection,
    )


def write_text_file(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def render_artifacts(
    bundle: BriefingBundle,
    include_dashboard: bool,
    live_client: bool = False,
    fragment_endpoint: str = "/fragment",
    poll_seconds: int = 10,
) -> tuple[str, str, str | None]:
    report = render_report(
        bundle.gold,
        bundle.dxy,
        bundle.us10y,
        bundle.news,
        bundle.analysis,
        bundle.ai_analysis,
        bundle.geopolitical_analysis,
        bundle.fundamental_recommendation,
        bundle.technical_recommendation,
        bundle.global_recommendation,
        bundle.executive_summary,
        bundle.real_yield,
        bundle.official_macro_rates,
        bundle.cftc_positioning,
        bundle.etf_flows_analysis,
        bundle.macro_catalysts,
        bundle.data_quality,
        bundle.cross_asset_analysis,
        bundle.event_mode,
        bundle.weekend_gold,
        bundle.market_regime,
        bundle.event_facts,
        bundle.political_statements,
        bundle.agent_results,
        bundle.trade_ledger,
        bundle.orchestrator_decision,
    )
    json_report = json.dumps(bundle.payload, ensure_ascii=False, indent=2)
    html_dashboard = (
        render_dashboard(
            bundle,
            live_client=live_client,
            fragment_endpoint=fragment_endpoint,
            poll_seconds=poll_seconds,
        )
        if include_dashboard
        else None
    )
    return report, json_report, html_dashboard


def render_signal_report_markdown(bundle: BriefingBundle) -> str:
    recommendation = bundle.global_recommendation
    decision = bundle.orchestrator_decision
    scenario = bundle.scenario_plan
    lines = [
        "# Aureum Flux Signal Report",
        "",
        f"Genere a {iso_now()}",
        "",
        f"- Prix XAU/USD: {bundle.gold.price:.2f} ({bundle.gold.change_pct:+.2f}%)",
        f"- Chef de file: {decision.status if decision else 'WAIT'} {decision.score if decision else 0}/100",
        f"- Verdict live: {recommendation.verdict if recommendation else 'WAIT'}",
        f"- Score live: {recommendation.score if recommendation else 0}/100",
    ]
    if scenario:
        lines.extend(
            [
                "",
                "## Scenario",
                f"- Statut: {scenario.status}",
                f"- Biais: {scenario.bias}",
                f"- Declencheur: {scenario.trigger}",
                f"- Invalidation: {scenario.invalidation}",
                f"- Action: {scenario.action}",
            ]
        )
    if recommendation:
        levels_ok = recommendation_levels_are_valid(recommendation)
        lines.extend(
            [
                "",
                "## Niveaux",
                f"- Niveaux exploitables: {'oui' if levels_ok else 'non'}",
                f"- SL: {recommendation.stop_loss:.2f}",
                f"- TP1: {recommendation.take_profit_1:.2f}",
                f"- TP2: {recommendation.take_profit_2:.2f}",
                "- Resume: " + recommendation.summary,
            ]
        )
    return "\n".join(lines) + "\n"


def render_news_audit_markdown(bundle: BriefingBundle) -> str:
    lines = [
        "# Aureum Flux News Audit",
        "",
        f"Genere a {iso_now()}",
        "",
        "## News Flow",
    ]
    for item in sorted(bundle.news, key=lambda news_item: news_item.published_at, reverse=True)[:30]:
        lines.append(f"- {item.published_at} | {item.source} | score {item.score:+d} | {item.title}")
    lines.extend(["", "## Event Facts"])
    if not bundle.event_facts:
        lines.append("Aucun EventFact structure disponible.")
    for fact in bundle.event_facts[:20]:
        lines.append(
            f"- {fact.published_at} | {fact.source} | {fact.impact_bias.upper()} | "
            f"{fact.trader_action} | {fact.title}"
        )
    return "\n".join(lines) + "\n"


def render_source_quality_audit_markdown(bundle: BriefingBundle) -> str:
    data_quality = bundle.data_quality
    lines = [
        "# Aureum Flux Source Quality Audit",
        "",
        f"Genere a {iso_now()}",
        "",
    ]
    if data_quality is None:
        lines.append("Data Quality indisponible.")
        return "\n".join(lines) + "\n"
    lines.extend(
        [
            f"- Statut: {data_quality.status}",
            f"- Score: {data_quality.score}/100",
            f"- Resume: {data_quality.summary}",
            "",
            "## Sources",
        ]
    )
    for snapshot in data_quality.snapshots:
        lines.append(
            f"- {snapshot.name}: {snapshot.status}, tier {snapshot.tier}, "
            f"age {snapshot.age_minutes if snapshot.age_minutes is not None else 'n/a'} min, "
            f"critique {'oui' if snapshot.critical else 'non'}."
        )
    return "\n".join(lines) + "\n"


def render_trade_report_markdown(ledger: TradeLedgerSummary | None) -> str:
    lines = ["# Aureum Flux Trade Report", "", f"Genere a {iso_now()}", ""]
    if ledger is None:
        lines.append("Trade Ledger indisponible.")
        return "\n".join(lines) + "\n"
    lines.extend(
        [
            f"- Gate: {ledger.quality_gate_status}",
            f"- Total: {ledger.total_trades}",
            f"- Wins/Losses/Partials/Expired: {ledger.wins}/{ledger.losses}/{ledger.partials}/{ledger.expired}",
            f"- Win rate: {ledger.stats.win_rate:.1f}%",
            f"- Expectancy: {ledger.stats.expectancy_r:+.2f}R",
            "",
            "## Recent Trades",
        ]
    )
    if not ledger.recent_trades:
        lines.append("Aucun TradePlan historise.")
    for plan in ledger.recent_trades:
        lines.append(
            f"- {plan.trade_id}: {plan.direction}, entry {plan.reference_price:.2f}, "
            f"SL {plan.stop_loss:.2f}, TP {plan.tp1:.2f}/{plan.tp2:.2f}/{plan.tp3:.2f}, "
            f"status {plan.status}, outcome {plan.outcome}."
        )
    return "\n".join(lines) + "\n"


def render_reports_index_html(exports: list[ReportExport]) -> str:
    rows = "\n".join(
        f"<li><a href=\"{html.escape(Path(export.path).name)}\">{html.escape(export.label)}</a> - {html.escape(export.description)}</li>"
        for export in exports
        if export.path.endswith((".md", ".json"))
    )
    return (
        "<!doctype html><html lang=\"fr\"><head><meta charset=\"utf-8\">"
        "<title>Aureum Flux Reports v3</title>"
        "<style>body{font-family:-apple-system,BlinkMacSystemFont,Segoe UI,sans-serif;background:#020617;color:#e5e7f5;padding:32px;}"
        "a{color:#8ab4ff}li{margin:10px 0}</style></head><body>"
        "<h1>Aureum Flux Reports v3</h1><ul>"
        f"{rows}"
        "</ul></body></html>"
    )


def write_reports_v3(
    bundle: BriefingBundle,
    main_report: str,
    output_dir: Path = REPORTS_V3_DIR,
) -> list[ReportExport]:
    output_dir.mkdir(parents=True, exist_ok=True)
    replay = build_replay_report()
    files = {
        "daily_report.md": main_report,
        "signal_report.md": render_signal_report_markdown(bundle),
        "trade_report.md": render_trade_report_markdown(bundle.trade_ledger),
        "post_mortem_report.md": render_trade_report_markdown(bundle.trade_ledger),
        "news_audit.md": render_news_audit_markdown(bundle),
        "source_quality_audit.md": render_source_quality_audit_markdown(bundle),
        "replay_report.md": render_replay_report_markdown(replay),
        "replay_report.json": json.dumps(asdict(replay), ensure_ascii=False, indent=2),
    }
    descriptions = {
        "daily_report.md": "Rapport complet du dernier snapshot.",
        "signal_report.md": "Lecture du signal live et du scenario.",
        "trade_report.md": "Historique et statistiques du Trade Ledger.",
        "post_mortem_report.md": "Post-mortem des trades clos.",
        "news_audit.md": "Audit des news et Event Facts.",
        "source_quality_audit.md": "Audit de qualite et fraicheur des sources.",
        "replay_report.md": "Replay markdown des TradePlan via audit_log.",
        "replay_report.json": "Replay structure JSON.",
    }
    exports: list[ReportExport] = []
    for filename, content in files.items():
        path = output_dir / filename
        write_text_file(path, content)
        exports.append(ReportExport(label=filename, path=str(path), description=descriptions[filename]))
    index_path = output_dir / "index.html"
    index_export = ReportExport("index.html", str(index_path), "Index HTML local des exports v3.")
    write_text_file(index_path, render_reports_index_html([*exports, index_export]))
    exports.append(index_export)
    return exports


def persist_artifacts(
    bundle: BriefingBundle,
    save_path: Path | None,
    data_json_path: Path | None,
    dashboard_path: Path | None,
) -> None:
    append_audit_log_safely(bundle)
    report, json_report, html_dashboard = render_artifacts(bundle, include_dashboard=dashboard_path is not None)
    exports = write_reports_v3(bundle, report)
    bundle.payload["reports_v3"] = [asdict(export) for export in exports]
    json_report = json.dumps(bundle.payload, ensure_ascii=False, indent=2)
    if dashboard_path and html_dashboard is not None:
        html_dashboard = render_dashboard(bundle, live_client=False)
    if save_path:
        write_text_file(save_path, report)
    if data_json_path:
        write_text_file(data_json_path, json_report)
    if dashboard_path and html_dashboard is not None:
        write_text_file(dashboard_path, html_dashboard)


class DashboardLiveCache:
    def __init__(
        self,
        top_news: int,
        live_refresh_seconds: int,
        full_refresh_seconds: int,
        save_path: Path | None = None,
        data_json_path: Path | None = None,
        dashboard_path: Path | None = None,
        include_ai: bool = False,
    ) -> None:
        self.top_news = top_news
        self.live_refresh_seconds = max(5, live_refresh_seconds)
        self.full_refresh_seconds = max(self.live_refresh_seconds, full_refresh_seconds)
        self.save_path = save_path
        self.data_json_path = data_json_path
        self.dashboard_path = dashboard_path
        self.include_ai = include_ai
        self.lock = threading.Lock()
        self.full_bundle: BriefingBundle | None = None
        self.latest_bundle: BriefingBundle | None = None
        self.full_refreshed_at = 0.0
        self.latest_refreshed_at = 0.0
        self.refresh_in_progress = False

    def _persist_latest(self, bundle: BriefingBundle, save_report: bool) -> None:
        append_audit_log_safely(bundle)
        if not save_report:
            if self.data_json_path:
                write_text_file(self.data_json_path, json.dumps(bundle.payload, ensure_ascii=False, indent=2))
            return
        report_for_exports: str | None = None
        if save_report and self.save_path:
            report_for_exports = render_report(
                bundle.gold,
                bundle.dxy,
                bundle.us10y,
                bundle.news,
                bundle.analysis,
                bundle.ai_analysis,
                bundle.geopolitical_analysis,
                bundle.fundamental_recommendation,
                bundle.technical_recommendation,
                bundle.global_recommendation,
                bundle.executive_summary,
                bundle.real_yield,
                bundle.official_macro_rates,
                bundle.cftc_positioning,
                bundle.etf_flows_analysis,
                bundle.macro_catalysts,
                bundle.data_quality,
                bundle.cross_asset_analysis,
                bundle.event_mode,
                bundle.weekend_gold,
                bundle.market_regime,
                bundle.event_facts,
                bundle.political_statements,
                bundle.agent_results,
                bundle.trade_ledger,
                bundle.orchestrator_decision,
            )
            write_text_file(self.save_path, report_for_exports)

        if report_for_exports is None:
            report_for_exports, _, _ = render_artifacts(bundle, include_dashboard=False)
        exports = write_reports_v3(bundle, report_for_exports)
        bundle.payload["reports_v3"] = [asdict(export) for export in exports]

        if self.data_json_path:
            write_text_file(self.data_json_path, json.dumps(bundle.payload, ensure_ascii=False, indent=2))

        if self.dashboard_path:
            write_text_file(self.dashboard_path, render_dashboard(bundle, live_client=False))

    def _load_cached_bundle_or_raise(self, original_error: Exception) -> BriefingBundle:
        cached_bundle = load_cached_bundle(self.data_json_path)
        if cached_bundle is None:
            raise original_error
        return cached_bundle

    def _start_background_refresh(self, full_refresh: bool) -> None:
        if self.refresh_in_progress:
            return
        self.refresh_in_progress = True
        thread = threading.Thread(
            target=self._background_refresh,
            args=(full_refresh,),
            daemon=True,
        )
        thread.start()

    def _background_refresh(self, full_refresh: bool) -> None:
        try:
            if full_refresh:
                bundle = build_briefing(self.top_news, include_ai=self.include_ai)
                with self.lock:
                    self.full_bundle = bundle
                    self.latest_bundle = bundle
                    self.full_refreshed_at = time.time()
                    self.latest_refreshed_at = self.full_refreshed_at
                self._persist_latest(bundle, save_report=True)
                return

            with self.lock:
                base_bundle = self.full_bundle
            if base_bundle is None:
                return
            bundle = build_live_bundle(base_bundle)
            with self.lock:
                self.latest_bundle = bundle
                self.latest_refreshed_at = time.time()
            self._persist_latest(bundle, save_report=False)
        except Exception:
            return
        finally:
            with self.lock:
                self.refresh_in_progress = False

    def get_bundle(self) -> BriefingBundle:
        now = time.time()
        with self.lock:
            if self.full_bundle is None or (now - self.full_refreshed_at) >= self.full_refresh_seconds:
                if self.full_bundle is None:
                    cached_bundle = load_cached_bundle(self.data_json_path)
                    if cached_bundle is not None:
                        self.full_bundle = cached_bundle
                        self.latest_bundle = cached_bundle
                        self.full_refreshed_at = now
                        self.latest_refreshed_at = now
                        self._start_background_refresh(full_refresh=True)
                        return cached_bundle
                try:
                    bundle = build_briefing(self.top_news, include_ai=self.include_ai)
                except Exception as exc:
                    bundle = self._load_cached_bundle_or_raise(exc)
                self.full_bundle = bundle
                self.latest_bundle = bundle
                self.full_refreshed_at = now
                self.latest_refreshed_at = now
                self._persist_latest(bundle, save_report=True)
                return bundle

            if self.latest_bundle is None or (now - self.latest_refreshed_at) >= self.live_refresh_seconds:
                if self.latest_bundle is not None:
                    self._start_background_refresh(full_refresh=False)
                    return self.latest_bundle
                return self.full_bundle

            return self.latest_bundle


def serve_dashboard(args: argparse.Namespace) -> int:
    cache = DashboardLiveCache(
        top_news=args.top_news,
        live_refresh_seconds=args.live_refresh_seconds,
        full_refresh_seconds=args.full_refresh_seconds,
        save_path=args.save,
        data_json_path=args.data_json,
        dashboard_path=args.dashboard,
        include_ai=args.live_ai,
    )

    class DashboardRequestHandler(http.server.BaseHTTPRequestHandler):
        def do_POST(self) -> None:  # noqa: N802
            parsed = urllib.parse.urlparse(self.path)
            route = parsed.path or "/"

            if route != "/api/settings":
                self.send_response(404)
                self.send_header("Content-Type", "application/json; charset=utf-8")
                self.end_headers()
                self.wfile.write(json.dumps({"ok": False, "error": "Not Found"}).encode("utf-8"))
                return

            try:
                length = int(self.headers.get("Content-Length", "0") or "0")
                raw_body = self.rfile.read(length).decode("utf-8") if length else "{}"
                body = json.loads(raw_body or "{}")
                action = str(body.get("action", ""))
                if action != "set_agent_enabled":
                    raise ValueError("action settings inconnue")
                agent = str(body.get("agent", ""))
                enabled = bool(body.get("enabled", False))
                settings, validation = set_agent_enabled(agent, enabled)
                cache.latest_bundle = None
                payload = {
                    "ok": True,
                    "settings": asdict(settings),
                    "validation": asdict(validation),
                }
                status_code = 200
            except Exception as exc:
                payload = {"ok": False, "error": str(exc)}
                status_code = 400

            encoded = json.dumps(payload, ensure_ascii=False).encode("utf-8")
            self.send_response(status_code)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Cache-Control", "no-store")
            self.send_header("Content-Length", str(len(encoded)))
            self.end_headers()
            self.wfile.write(encoded)

        def do_GET(self) -> None:  # noqa: N802
            parsed = urllib.parse.urlparse(self.path)
            route = parsed.path or "/"

            if route == "/favicon.ico":
                self.send_response(204)
                self.end_headers()
                return

            try:
                bundle = cache.get_bundle()
            except Exception as exc:
                self.send_response(500)
                self.send_header("Content-Type", "text/plain; charset=utf-8")
                self.end_headers()
                self.wfile.write(f"Erreur de mise a jour du dashboard: {exc}".encode("utf-8"))
                return

            if route in ("/", "/index.html"):
                html_document = render_dashboard(
                    bundle,
                    live_client=True,
                    fragment_endpoint="/fragment",
                    poll_seconds=args.live_refresh_seconds,
                )
                payload = html_document.encode("utf-8")
                self.send_response(200)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.send_header("Cache-Control", "no-store")
                self.send_header("Content-Length", str(len(payload)))
                self.end_headers()
                self.wfile.write(payload)
                return

            if route == "/fragment":
                fragment = extract_dashboard_main_inner(render_dashboard(bundle, live_client=False))
                payload = fragment.encode("utf-8")
                self.send_response(200)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.send_header("Cache-Control", "no-store")
                self.send_header("Content-Length", str(len(payload)))
                self.end_headers()
                self.wfile.write(payload)
                return

            if route == "/api/live.json":
                payload = json.dumps(bundle.payload, ensure_ascii=False).encode("utf-8")
                self.send_response(200)
                self.send_header("Content-Type", "application/json; charset=utf-8")
                self.send_header("Cache-Control", "no-store")
                self.send_header("Content-Length", str(len(payload)))
                self.end_headers()
                self.wfile.write(payload)
                return

            self.send_response(404)
            self.send_header("Content-Type", "text/plain; charset=utf-8")
            self.end_headers()
            self.wfile.write(b"Not Found")

        def log_message(self, format: str, *log_args: Any) -> None:  # noqa: A003
            if not args.quiet:
                super().log_message(format, *log_args)

    try:
        server = http.server.ThreadingHTTPServer((args.host, args.port), DashboardRequestHandler)
    except OSError as exc:
        print(f"Impossible de lancer le serveur du dashboard sur {args.host}:{args.port}: {exc}", file=sys.stderr)
        return 1

    if not args.quiet:
        print(f"Dashboard live disponible sur http://{args.host}:{args.port}/")

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
    return 0


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="XAUUSD market news agent with heuristic analysis and optional OpenAI summary."
    )
    parser.add_argument("--top-news", type=int, default=8, help="Number of headlines to keep in the report.")
    parser.add_argument("--json", action="store_true", help="Print structured JSON instead of markdown.")
    parser.add_argument(
        "--save",
        type=Path,
        default=None,
        help="Optional file path to save the markdown report.",
    )
    parser.add_argument(
        "--dashboard",
        type=Path,
        default=None,
        help="Optional file path to save the HTML dashboard.",
    )
    parser.add_argument(
        "--data-json",
        type=Path,
        default=None,
        help="Optional file path to save the JSON payload.",
    )
    parser.add_argument(
        "--quiet",
        action="store_true",
        help="Do not print the full report to the console.",
    )
    parser.add_argument(
        "--watch-minutes",
        type=int,
        default=0,
        help="Rerun the briefing every N minutes. Default: run once.",
    )
    parser.add_argument(
        "--max-cycles",
        type=int,
        default=0,
        help="Stop after N cycles in watch mode. Default: infinite watch.",
    )
    parser.add_argument(
        "--serve-dashboard",
        action="store_true",
        help="Start a local live dashboard server instead of writing a static HTML file only.",
    )
    parser.add_argument("--host", default="127.0.0.1", help="Host for the live dashboard server.")
    parser.add_argument("--port", type=int, default=8787, help="Port for the live dashboard server.")
    parser.add_argument(
        "--live-refresh-seconds",
        type=int,
        default=10,
        help="Refresh interval in seconds for the live XAU/USD price and candlestick chart.",
    )
    parser.add_argument(
        "--full-refresh-seconds",
        type=int,
        default=60,
        help="Refresh interval in seconds for the broader analysis and recommendations in live mode.",
    )
    parser.add_argument(
        "--live-ai",
        action="store_true",
        help="Allow OpenAI summaries during live server refreshes. Disabled by default to avoid repeated API calls.",
    )
    parser.add_argument(
        "--init-settings",
        action="store_true",
        help="Create config/aureum_settings.json with safe defaults, then exit.",
    )
    parser.add_argument(
        "--replay",
        action="store_true",
        help="Generate a replay report from reports/trade_ledger.jsonl and reports/audit_log.jsonl, then exit.",
    )
    parser.add_argument(
        "--replay-output",
        type=Path,
        default=REPORTS_V3_DIR / "replay_report.md",
        help="Output path for --replay markdown report.",
    )
    return parser.parse_args()


def main() -> int:
    load_env_file(Path(".env"))
    args = parse_args()
    if args.init_settings:
        settings, validation = load_user_settings(create_if_missing=True)
        print(json.dumps({"settings": asdict(settings), "validation": asdict(validation)}, ensure_ascii=False, indent=2))
        return 0
    if args.replay:
        replay = build_replay_report()
        write_text_file(args.replay_output, render_replay_report_markdown(replay))
        print(json.dumps(asdict(replay), ensure_ascii=False, indent=2))
        return 0
    if args.serve_dashboard:
        return serve_dashboard(args)

    cycle = 0

    while True:
        cycle += 1
        try:
            bundle = build_briefing(top_news=args.top_news, include_ai=True)
        except Exception as exc:
            bundle = load_cached_bundle(args.data_json)
            if bundle is None:
                print(f"Erreur lors de la generation du briefing: {exc}", file=sys.stderr)
                return 1
            print(
                f"Sources live indisponibles temporairement, utilisation du dernier snapshot en cache: {exc}",
                file=sys.stderr,
            )

        append_audit_log_safely(bundle)
        report, json_report, html_dashboard = render_artifacts(bundle, include_dashboard=args.dashboard is not None)
        exports = write_reports_v3(bundle, report)
        bundle.payload["reports_v3"] = [asdict(export) for export in exports]
        json_report = json.dumps(bundle.payload, ensure_ascii=False, indent=2)
        if html_dashboard is not None:
            html_dashboard = render_dashboard(bundle, live_client=False)

        if args.save:
            write_text_file(args.save, report)

        if args.data_json:
            write_text_file(args.data_json, json_report)

        if args.dashboard and html_dashboard is not None:
            write_text_file(args.dashboard, html_dashboard)

        if not args.quiet:
            print(json_report if args.json else report)

        if args.watch_minutes <= 0:
            return 0
        if args.max_cycles and cycle >= args.max_cycles:
            return 0

        time.sleep(args.watch_minutes * 60)


if __name__ == "__main__":
    raise SystemExit(main())
