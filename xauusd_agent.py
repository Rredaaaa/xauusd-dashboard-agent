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

POLITICAL_RSS_FEEDS = [
    ("political_white_house", WHITE_HOUSE_NEWS_FEED_URL),
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
AUDIT_LOG_PATH = Path("reports") / "audit_log.jsonl"
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
    "rate cut": 2,
    "cuts": 1,
    "dovish": 2,
    "recession": 1,
    "inflation": 1,
    "weak dollar": 2,
    "dollar falls": 2,
    "lower yields": 2,
    "falling yields": 2,
    "central bank buying": 2,
}

BEARISH_KEYWORDS = {
    "hawkish": -2,
    "higher for longer": -2,
    "rate hike": -2,
    "strong dollar": -2,
    "dollar strengthens": -2,
    "rising yields": -2,
    "higher yields": -2,
    "risk-on": -1,
    "ceasefire": -1,
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
class MarketRegimeAnalysis:
    name: str
    status: str
    score: int
    gold_impact: str
    summary: str
    reasons: list[str]


@dataclass
class OfficialMacroRates:
    dgs10: SymbolSnapshot | None = None
    dgs2: SymbolSnapshot | None = None
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


@dataclass
class MacroCatalystCalendar:
    generated_at: str
    source_note: str
    fedwatch_status: str
    fedwatch_note: str
    fedwatch_source_url: str
    catalysts: list[MacroCatalyst] = field(default_factory=list)


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


def http_get_text(url: str) -> str:
    request = urllib.request.Request(url, headers=HEADERS)
    last_error: Exception | None = None
    for attempt in range(2):
        try:
            with urllib.request.urlopen(request, timeout=8) as response:
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


def should_skip_headline(title: str, source: str) -> bool:
    text = f"{title} {source}".lower()
    blocked_patterns = [
        "chart image",
        "tradingview",
        "forexcom:xauusd",
        "nostradamus",
        "check prediction here",
        "horoscope",
    ]
    return any(pattern in text for pattern in blocked_patterns)


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
    "investing_xauusd": SourceRegistryEntry("investing_xauusd", "Investing.com XAU/USD", "price", 2, 30, True, INVESTING_XAUUSD_URL, ["PriceAgent", "RiskManagerAgent", "OrchestratorAgent"]),
    "ig_weekend_gold": SourceRegistryEntry("ig_weekend_gold", "IG Weekend Gold", "price", 2, 120, False, IG_WEEKEND_GOLD_URL, ["PriceAgent", "RiskManagerAgent"]),
    "fred_dgs10": SourceRegistryEntry("fred_dgs10", "FRED DGS10", "rates", 1, 10080, True, FRED_CSV_URL_TEMPLATE.format(series_id="DGS10"), ["MacroAgent", "RiskManagerAgent"]),
    "fred_dgs2": SourceRegistryEntry("fred_dgs2", "FRED DGS2", "rates", 1, 10080, False, FRED_CSV_URL_TEMPLATE.format(series_id="DGS2"), ["MacroAgent"]),
    "fred_t10yie": SourceRegistryEntry("fred_t10yie", "FRED T10YIE", "macro", 1, 10080, False, FRED_CSV_URL_TEMPLATE.format(series_id="T10YIE"), ["MacroAgent"]),
    "fred_dfii10": SourceRegistryEntry("fred_dfii10", "FRED DFII10", "rates", 1, 10080, True, FRED_DFII10_CSV_URL, ["MacroAgent", "RiskManagerAgent"]),
    "cftc_cot_gold": SourceRegistryEntry("cftc_cot_gold", "CFTC COT Gold", "flows", 1, 14400, True, CFTC_DISAGG_CURRENT_URL, ["FlowPositioningAgent", "RiskManagerAgent"]),
    "wgc_etf_flows": SourceRegistryEntry("wgc_etf_flows", "World Gold Council ETF flows", "flows", 1, 14400, True, WGC_ETF_FLOWS_PAGE_URL, ["FlowPositioningAgent", "CorrelationAgent"]),
    "macro_catalysts": SourceRegistryEntry("macro_catalysts", "Fed/BEA Macro Catalysts", "macro", 1, 1440, True, FED_FOMC_CALENDAR_URL, ["MacroAgent", "RiskManagerAgent"]),
    "google_news_rss": SourceRegistryEntry("google_news_rss", "Google News RSS / fallback feeds", "news", 4, 2880, True, "https://news.google.com/rss", ["SentimentNewsAgent", "EventFactsAgent"]),
    "white_house_feed": SourceRegistryEntry("white_house_feed", "White House News feed", "political_statements", 1, 10080, False, WHITE_HOUSE_NEWS_FEED_URL, ["TrumpPoliticalStatementsAgent"]),
    "cross_asset_yahoo": SourceRegistryEntry("cross_asset_yahoo", "Yahoo cross-assets", "technical", 2, 240, True, "https://finance.yahoo.com/", ["CorrelationAgent", "PriceAgent"]),
    "oil_context": SourceRegistryEntry("oil_context", "WTI/Brent oil context", "oil", 2, 240, False, "https://finance.yahoo.com/", ["GeopoliticalOilShockAgent", "RiskManagerAgent"]),
}


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


def append_trade_plan_snapshot(plan: TradePlan, path: Path = TRADE_LEDGER_PATH) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(asdict(plan), ensure_ascii=False, sort_keys=True) + "\n")


def trade_plan_closed(plan: TradePlan) -> bool:
    return plan.status in {"tp2_hit", "tp3_hit", "sl_hit", "expired", "invalidated", "closed_manual"}


def compute_risk_reward(direction: str, entry: float, stop_loss: float, target: float) -> float:
    risk = abs(entry - stop_loss)
    reward = abs(target - entry)
    if risk <= 0:
        return 0.0
    return round(reward / risk, 2)


def trade_signal_id(direction: str, market_regime: str, reference_price: float, score: int) -> str:
    base = f"{direction}|{market_regime}|{round(reference_price / 5) * 5:.0f}|{score // 5 * 5}"
    return hashlib.sha1(base.encode("utf-8")).hexdigest()[:12]


def evaluate_trade_plan(plan: TradePlan, current_price: float, now: datetime | None = None) -> TradePlan:
    if trade_plan_closed(plan):
        return plan
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
        return plan
    return updated


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
        updated_plans.append(updated)
    return sorted(updated_plans, key=lambda item: item.created_at, reverse=True)


def build_trade_quality_gate(
    gold: SymbolSnapshot,
    global_recommendation: TradeRecommendation,
    data_quality: DataQualitySnapshot | None,
    agent_results: list[AgentResult],
    market_regime: MarketRegimeAnalysis | None,
) -> tuple[bool, list[str], list[str], list[str]]:
    reasons: list[str] = []
    if global_recommendation.verdict not in {"BUY", "SELL"}:
        reasons.append(f"Verdict {global_recommendation.verdict}: aucun trade verrouille sans direction BUY/SELL.")
    validating = [
        agent.name
        for agent in agent_results
        if agent.bias == global_recommendation.verdict and agent.confidence >= 50
    ]
    contradicting = [
        agent.name
        for agent in agent_results
        if agent.bias in {"BUY", "SELL"} and agent.bias != global_recommendation.verdict
    ]

    if global_recommendation.score < 60:
        reasons.append(f"Score global insuffisant: {global_recommendation.score}/100 < 60.")
    if data_quality is None:
        reasons.append("Data quality indisponible.")
    elif data_quality.score < 70:
        reasons.append(f"Data quality insuffisante: {data_quality.score}/100 < 70.")
    elif data_quality.missing_sources or data_quality.stale_sources:
        reasons.append("Source critique absente ou stale.")
    if len(validating) < 2:
        reasons.append("Moins de deux agents valident la direction.")
    if len(contradicting) >= 3:
        reasons.append("Trop de contradictions entre agents.")
    if market_regime is not None and market_regime.name == "Hormuz / Oil Shock":
        reasons.append("Regime Hormuz/Oil Shock: trade locking suspendu sans validation manuelle.")
    rr1 = compute_risk_reward(
        global_recommendation.verdict,
        gold.price,
        global_recommendation.stop_loss,
        global_recommendation.take_profit_1,
    )
    if rr1 < 0.8:
        reasons.append(f"Risk/reward TP1 insuffisant: {rr1:.2f}R < 0.80R.")
    if global_recommendation.stop_loss == global_recommendation.take_profit_1:
        reasons.append("SL/TP non exploitables.")

    allowed = not reasons
    if allowed:
        reasons.append("Quality Gate valide: score, data quality, agents et regime permettent un Trade Snapshot.")
    return allowed, reasons, validating, contradicting


def build_trade_plan_from_signal(
    gold: SymbolSnapshot,
    global_recommendation: TradeRecommendation,
    data_quality: DataQualitySnapshot | None,
    agent_results: list[AgentResult],
    market_regime: MarketRegimeAnalysis | None,
    event_facts: list[EventFact],
    technical_readings: list[TechnicalReading],
    now: datetime | None = None,
) -> tuple[TradePlan | None, list[str]]:
    reference = now or datetime.now(timezone.utc)
    allowed, reasons, validating, contradicting = build_trade_quality_gate(
        gold,
        global_recommendation,
        data_quality,
        agent_results,
        market_regime,
    )
    if not allowed:
        return None, reasons

    direction = global_recommendation.verdict
    entry = gold.price
    zone_padding = max(1.0, abs(entry - global_recommendation.stop_loss) * 0.12)
    if direction == "BUY":
        entry_low, entry_high = entry - zone_padding, entry + zone_padding
        tp3 = entry + abs(global_recommendation.take_profit_2 - entry) * 1.618
    else:
        entry_low, entry_high = entry - zone_padding, entry + zone_padding
        tp3 = entry - abs(global_recommendation.take_profit_2 - entry) * 1.618
    signal_id = trade_signal_id(direction, market_regime.name if market_regime else "Normal Macro", entry, global_recommendation.score)
    elliott = next((agent for agent in agent_results if agent.name == "ElliottWaveAgent"), None)
    technical_snapshot = "; ".join(
        f"{reading.timeframe}:{reading.verdict}/{reading.score:+.1f}"
        for reading in technical_readings[:5]
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
        stop_loss=round(global_recommendation.stop_loss, 2),
        tp1=round(global_recommendation.take_profit_1, 2),
        tp2=round(global_recommendation.take_profit_2, 2),
        tp3=round(tp3, 2),
        risk_reward_tp1=compute_risk_reward(direction, entry, global_recommendation.stop_loss, global_recommendation.take_profit_1),
        risk_reward_tp2=compute_risk_reward(direction, entry, global_recommendation.stop_loss, global_recommendation.take_profit_2),
        risk_reward_tp3=compute_risk_reward(direction, entry, global_recommendation.stop_loss, tp3),
        max_valid_until=(reference + timedelta(hours=6)).replace(microsecond=0).isoformat(),
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
        elliott_wave_snapshot=elliott.summary if elliott else "Elliott Wave indisponible.",
        invalidation_rules=[
            f"Invalidation principale si prix touche SL {global_recommendation.stop_loss:.2f}.",
            "Invalidation contextuelle si Data Quality passe sous 55/100 ou si un fait Tier 1 contredit le scenario.",
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
    now: datetime | None = None,
) -> bool:
    reference = now or datetime.now(timezone.utc)
    for plan in plans:
        if plan.direction != candidate.direction or plan.market_regime != candidate.market_regime:
            continue
        if not trade_plan_closed(plan):
            return True
        created = parse_iso_datetime(plan.created_at)
        if created is not None and (reference - created).total_seconds() <= cooldown_minutes * 60:
            return True
    return False


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
) -> TradeLedgerSummary:
    reference = now or datetime.now(timezone.utc)
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
    )
    if candidate is not None:
        if has_recent_similar_trade(plans, candidate, now=reference):
            gate_reasons = ["Cooldown actif: un trade similaire est deja actif ou trop recent."]
        elif allow_create:
            append_trade_plan_snapshot(candidate, path)
            plans = [candidate, *plans]
            gate_reasons = ["Trade Snapshot cree et verrouille dans le ledger append-only."]

    active_statuses = {"pending", "active", "tp1_hit"}
    active_trades = [plan for plan in plans if plan.status in active_statuses]
    wins = sum(1 for plan in plans if plan.outcome == "win")
    losses = sum(1 for plan in plans if plan.outcome == "loss")
    partials = sum(1 for plan in plans if plan.outcome == "partial")
    expired = sum(1 for plan in plans if plan.outcome == "expired")
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
    )


def build_monitoring_inspector_payload(
    generated_at: str,
    data_quality: DataQualitySnapshot | None,
    agent_results: list[AgentResult],
    trade_ledger: TradeLedgerSummary | None,
    orchestrator_decision: OrchestratorDecision | None,
    global_recommendation: TradeRecommendation | None,
    market_regime: MarketRegimeAnalysis | None,
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
                }
            )

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
            "rows": trade_rows[:12],
        },
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
        },
        "agents": inspector["agents"]["outputs"],
        "trades": inspector["trades"],
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
        make_source_snapshot("cross_asset_yahoo", cross_asset_analysis is not None, gold.fetched_at, cross_asset_analysis.summary if cross_asset_analysis else "", now=reference),
        make_source_snapshot("oil_context", market_regime is not None, gold.fetched_at, market_regime.summary if market_regime else "", now=reference),
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

    score = 100
    score -= 18 * len(missing)
    score -= 12 * len(stale)
    score -= 4 * len(weak)
    score -= min(18, 6 * len(contradictions))
    score = clamp_score(score)
    status = data_quality_status(score)
    summary = (
        f"Data quality {status} {score}/100: "
        f"{len(missing)} critique(s) absente(s), {len(stale)} critique(s) stale, "
        f"{len(weak)} source(s) faible(s), {len(contradictions)} contradiction(s)."
    )
    return DataQualitySnapshot(
        generated_at=reference.replace(microsecond=0).isoformat(),
        score=score,
        status=status,
        summary=summary,
        missing_sources=missing,
        stale_sources=stale,
        weak_sources=weak,
        contradictions=contradictions,
        snapshots=snapshots,
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
    dgs2: SymbolSnapshot | None,
    t10yie: SymbolSnapshot | None,
    dfii10: SymbolSnapshot | None,
    yahoo_us10y: SymbolSnapshot | None,
) -> OfficialMacroRates:
    gap_bps = None
    if dgs10 is not None and yahoo_us10y is not None:
        gap_bps = (yahoo_us10y.price - dgs10.price) * 100
    return OfficialMacroRates(
        dgs10=dgs10,
        dgs2=dgs2,
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

    net_pct_component = clamp(managed_money_net_pct_oi * 1.4, -18, 18)
    weekly_component = clamp((managed_money_net_change / open_interest * 220) if open_interest else 0, -12, 12)
    oi_component = clamp((open_interest_change / open_interest * 120) if open_interest else 0, -5, 5)
    score = clamp_score(50 + net_pct_component + weekly_component + oi_component)

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
        f"de {managed_money_net_change:+,} contrats."
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

    catalysts = dedupe_macro_catalysts(catalysts)
    catalysts.sort(key=lambda item: (item.minutes_to_event is None, abs(item.minutes_to_event or 10**9)))
    upcoming = [item for item in catalysts if item.minutes_to_event is None or item.minutes_to_event >= -24 * 60]
    selected = upcoming[:10] if upcoming else catalysts[:10]

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


def fetch_technical_timeframes() -> tuple[list[TechnicalReading], float, list[PricePoint]]:
    points_5m = fetch_symbol_snapshot("GC=F", "Gold futures 5m", interval="5m", data_range="5d").points
    points_15m = fetch_symbol_snapshot("GC=F", "Gold futures 15m", interval="15m", data_range="10d").points
    points_1h = fetch_symbol_snapshot("GC=F", "Gold futures 1h", interval="60m", data_range="6mo").points
    points_1d = fetch_symbol_snapshot("GC=F", "Gold futures 1d", interval="1d", data_range="2y").points
    points_4h = aggregate_points(points_1h, bucket_seconds=4 * 60 * 60)

    timeframe_map = [
        ("1D", points_1d),
        ("4H", points_4h),
        ("1H", points_1h),
        ("15m", points_15m),
        ("5m", points_5m),
    ]
    readings = [build_technical_reading(timeframe, points) for timeframe, points in timeframe_map]
    proxy_current_price = points_15m[-1].close
    return readings, proxy_current_price, points_5m


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
        "Lecture fondamentale intraday positive: dollar et taux se detendent, "
        "avec un flux d'actualites qui ne contredit pas la hausse."
        if verdict == "BUY"
        else "Lecture fondamentale intraday defensive: le contexte macro ne soutient pas assez l'or pour un achat agressif."
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
        summary = "Structure technique intraday constructive: les petits timeframes tirent vers le haut et le plan favorise la continuation."
    else:
        stop_loss = max(stop_loss, adjusted_resistance + (atr_for_levels * 0.35))
        tp1 = min(tp1, spot.day_low or tp1)
        tp2 = min(tp2, adjusted_support)
        summary = "Structure technique intraday fragile: le poids des timeframes superieurs garde un risque vendeur dominant."

    if event_mode is not None and event_mode.active:
        score = min(score, 62)
        reasons.insert(0, f"Mode event actif ({event_mode.score}/100): signal technique a traiter en attente/confirmation.")
        summary = f"{summary} Attention: regime volatil, ne pas chasser le mouvement."

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

    stop_default, tp1_default, tp2_default = build_trade_levels(
        gold.price,
        atr=max(abs(fundamental.take_profit_1 - gold.price), abs(technical.take_profit_1 - gold.price), 6.0),
        verdict=verdict,
        stop_multiplier=1.0,
        tp1_multiplier=1.0,
        tp2_multiplier=2.0,
    )
    stop_losses, take_profit_1, take_profit_2 = collect_directional_levels(
        gold.price,
        verdict,
        [fundamental, technical],
    )
    stop_loss = average_or_default(stop_losses, stop_default)
    tp1 = average_or_default(take_profit_1, tp1_default)
    tp2 = average_or_default(take_profit_2, tp2_default)

    reasons = [
        f"Technique {technical.verdict} a {technical.score}/100.",
        f"Fondamental {fundamental.verdict} a {fundamental.score}/100.",
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
            f"Le fondamental et la technique pointent tous les deux vers {fundamental.verdict}. "
            "Le marche envoie donc un message plus propre que d'habitude."
        )
    elif fundamental.verdict == "BUY":
        alignment = (
            "Le fondamental reste favorable a l'or, mais le graphique intraday ne donne pas encore "
            "un point d'entree assez propre pour suivre ce biais sans prudence."
        )
    else:
        alignment = (
            "La technique reste plus fragile que le contexte macro. Cela veut dire que le marche "
            "peut encore vendre les rebonds meme si le decor de fond n'est pas franchement anti-or."
        )

    geo_lines: list[str] = []
    if geopolitical:
        if geopolitical.risk_off_status == "actif":
            geo_lines.append(
                "Le risque geopolitique reste actif, donc la demande de couverture sur l'or ne disparait pas."
            )
        elif geopolitical.risk_off_status == "en reflux":
            geo_lines.append(
                "Le stress geopolitique se calme un peu, ce qui retire une partie du soutien refuge."
            )

        if geopolitical.central_bank_bias == "restrictif":
            geo_lines.append(
                "En meme temps, le marche craint qu'un choc energie ou une inflation plus tenace retarde les baisses de taux."
            )
        elif geopolitical.central_bank_bias == "accommodant":
            geo_lines.append(
                "Le ton des banques centrales parait moins hostile, ce qui aide l'or via un dollar et des rendements moins agressifs."
            )
        else:
            geo_lines.append(
                "Le message des banques centrales reste partage, donc l'or garde du soutien sans obtenir un feu vert total."
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


def score_headline(title: str) -> tuple[int, list[str]]:
    text = title.lower()
    score = 0
    reasons: list[str] = []

    for keyword, weight in BULLISH_KEYWORDS.items():
        if keyword_matches(text, keyword):
            score += weight
            reasons.append(f"bullish:{keyword}")

    for keyword, weight in BEARISH_KEYWORDS.items():
        if keyword_matches(text, keyword):
            score += weight
            reasons.append(f"bearish:{keyword}")

    return max(-3, min(3, score)), reasons


def append_rss_items(
    root: ET.Element,
    category: str,
    items: list[NewsItem],
    seen_titles: set[str],
    result_limit: int,
) -> None:
    channel_title = compact_whitespace(root.findtext("./channel/title", default="RSS"))
    for item in root.findall("./channel/item"):
        source = compact_whitespace(item.findtext("source", default="")) or channel_title
        raw_title = compact_whitespace(item.findtext("title", default=""))
        title = strip_source_suffix(raw_title, source)
        dedupe_key = normalize_title_for_dedupe(title)
        if not title or dedupe_key in seen_titles or should_skip_headline(title, source):
            continue

        score, reasons = score_headline(title)
        published_raw = item.findtext("pubDate", default="")
        try:
            published_at = (
                parsedate_to_datetime(published_raw).astimezone(timezone.utc).replace(microsecond=0).isoformat()
                if published_raw
                else iso_now()
            )
        except Exception:
            published_at = iso_now()

        items.append(
            NewsItem(
                title=title,
                source=source,
                link=compact_whitespace(item.findtext("link", default="")),
                published_at=published_at,
                category=category,
                score=score,
                score_reasons=reasons,
            )
        )
        seen_titles.add(dedupe_key)
        if len(items) >= result_limit:
            return


def fetch_news(top_n: int) -> list[NewsItem]:
    items: list[NewsItem] = []
    seen_titles: set[str] = set()
    month_name = current_month_name_en()
    result_limit = max(top_n, 24)
    deadline = time.time() + 18

    for category, query_template in NEWS_QUERIES:
        if time.time() >= deadline:
            break
        query = query_template.format(month=month_name)
        encoded_query = urllib.parse.quote(query, safe='()":')
        url = (
            "https://news.google.com/rss/search"
            f"?q={encoded_query}&hl=en-US&gl=US&ceid=US:en"
        )
        try:
            xml_text = http_get_text(url)
            root = ET.fromstring(xml_text)
        except Exception:
            continue

        append_rss_items(root, category, items, seen_titles, result_limit)
        if len(items) >= result_limit:
            items.sort(key=lambda item: (abs(item.score), item.published_at), reverse=True)
            return items[:result_limit]

    if len(items) < top_n:
        for category, url in FALLBACK_RSS_FEEDS:
            try:
                xml_text = http_get_text(url)
                root = ET.fromstring(xml_text)
            except Exception:
                continue
            append_rss_items(root, category, items, seen_titles, result_limit)
            if len(items) >= result_limit:
                break

    items.sort(key=lambda item: (abs(item.score), item.published_at), reverse=True)
    return items[:result_limit]


def merge_news_items(primary: list[NewsItem], extra: list[NewsItem], limit: int) -> list[NewsItem]:
    merged: list[NewsItem] = []
    seen: set[str] = set()
    for item in primary + extra:
        key = normalize_title_for_dedupe(item.title)
        if not key or key in seen:
            continue
        seen.add(key)
        merged.append(item)
    merged.sort(key=lambda item: (abs(item.score), item.published_at), reverse=True)
    return merged[:limit]


def political_source_tier(item: NewsItem) -> int:
    source = item.source.lower()
    link = item.link.lower()
    if "whitehouse.gov" in link or "white house" in source:
        return 1
    if any(token in source for token in ("reuters", "associated press", "ap news", "bloomberg")):
        return 2
    if any(token in source for token in ("cnbc", "marketwatch", "wsj", "bbc", "france 24", "al jazeera")):
        return 3
    return 4


def fetch_political_statement_news(limit: int = 12) -> list[NewsItem]:
    items: list[NewsItem] = []
    seen_titles: set[str] = set()
    result_limit = max(limit, 12)
    deadline = time.time() + 12

    for category, url in POLITICAL_RSS_FEEDS:
        if time.time() >= deadline:
            break
        try:
            root = ET.fromstring(http_get_text(url))
        except Exception:
            continue
        append_rss_items(root, category, items, seen_titles, result_limit)
        items = keep_political_statement_candidates(items)
        seen_titles = {normalize_title_for_dedupe(item.title) for item in items}

    for category, query in POLITICAL_STATEMENT_QUERIES:
        if time.time() >= deadline or len(items) >= result_limit:
            break
        encoded_query = urllib.parse.quote(query, safe='()":')
        url = (
            "https://news.google.com/rss/search"
            f"?q={encoded_query}&hl=en-US&gl=US&ceid=US:en"
        )
        try:
            root = ET.fromstring(http_get_text(url))
        except Exception:
            continue
        append_rss_items(root, category, items, seen_titles, result_limit)
        items = keep_political_statement_candidates(items)
        seen_titles = {normalize_title_for_dedupe(item.title) for item in items}

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
        summary = "Les correlations ne confirment pas assez le BUY gold: prudence ou attente d'une meilleure confluence."
    else:
        status = "mitige"
        verdict = "neutre"
        summary = "Le contexte cross-asset reste partage: mieux vaut exiger un signal technique propre avant d'agir."

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
    active = score_int >= 45 or max_volume_ratio >= 2.0
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
    yields_up = (us10y.change_abs * 100) >= 3
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
        reasons.append(f"WTI/Brent ne confirment pas encore un choc petrole fort ({oil_change:+.2f}%).")
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
        reasons.append("Mode event actif: prudence renforcee sur les entrees gold.")

    oil_shock_score = round(clamp(oil_shock_score, 0, 100))
    if oil_shock_score >= 58:
        return MarketRegimeAnalysis(
            name="Hormuz / Oil Shock",
            status="ACTIF",
            score=oil_shock_score,
            gold_impact="mixte/baissier court terme",
            summary=(
                "Regime Hormuz/Oil Shock detecte: la tension politique soutient d'abord oil et dollar. "
                "Gold peut etre vendu pour liquidite tant que Brent/WTI, DXY ou les taux dominent."
            ),
            reasons=reasons[:6],
        )

    if oil_shock_headlines and oil_change <= -0.35:
        return MarketRegimeAnalysis(
            name="De-escalation / Oil Relief",
            status="SURVEILLANCE",
            score=round(clamp(45 + oil_shock_headlines * 5, 0, 100)),
            gold_impact="prime de risque en reflux",
            summary=(
                "Le theme Iran/Hormuz existe, mais le petrole ne confirme pas un choc. "
                "La prime de risque peut sortir de gold si oil et volatilite se detendent."
            ),
            reasons=reasons[:6],
        )

    if dxy_strong and gold_weak:
        return MarketRegimeAnalysis(
            name="Dollar Liquidity Squeeze",
            status="ACTIF",
            score=round(clamp(52 + abs(dxy.change_pct) * 10 + abs(gold.change_pct) * 8, 0, 100)),
            gold_impact="baissier court terme",
            summary=(
                "Le marche cherche surtout de la liquidite dollar: gold peut baisser meme si le contexte reste stressant."
            ),
            reasons=reasons[:6] or [f"DXY monte ({dxy.change_pct:+.2f}%) pendant que gold recule ({gold.change_pct:+.2f}%)."],
        )

    if oil_shock_headlines and gold_strong and not dxy_strong:
        return MarketRegimeAnalysis(
            name="Safe-Haven Gold",
            status="ACTIF",
            score=round(clamp(55 + oil_shock_headlines * 5 + max(gold.change_pct, 0) * 8, 0, 100)),
            gold_impact="haussier",
            summary=(
                "Le risque politique se transmet surtout par la demande de couverture sur l'or: gold confirme mieux que dollar/oil."
            ),
            reasons=reasons[:6] or ["Gold confirme le role refuge pendant que le dollar ne domine pas."],
        )

    return MarketRegimeAnalysis(
        name="Normal Macro",
        status="NORMAL",
        score=oil_shock_score,
        gold_impact="neutre",
        summary="Pas de regime Hormuz/Oil Shock confirme: le gold reste surtout pilote par DXY, taux, technique et headlines.",
        reasons=reasons[:6] or ["Aucun choc petrole/geopolitique suffisamment confirme."],
    )


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


def top_news_titles(news: list[NewsItem], categories: set[str] | None = None, limit: int = 2) -> str:
    selected = [
        clean_display_text(item.title)
        for item in news
        if categories is None or item.category in categories
    ][:limit]
    return " | ".join(selected) if selected else "aucun titre exploitable"


def build_elliott_wave_agent(gold: SymbolSnapshot) -> AgentResult:
    points = gold.intraday_points or gold.points
    closes = [point.close for point in points if point.close]
    if len(closes) < 8:
        return AgentResult(
            name="ElliottWaveAgent",
            department="Technical",
            bias="NEUTRAL",
            score=50,
            confidence=35,
            summary="Lecture Elliott passive indisponible: pas assez de points pour compter les swings.",
            evidence=[
                AgentEvidence(
                    "Base theorique",
                    "Motive 5 vagues, correction ABC, Fibonacci, avec prudence sur les sequences modernes.",
                    "elliottwave-forecast.com/elliott-wave-theory",
                )
            ],
            risks=[AgentRisk("Donnees", "Historique intraday trop court pour une lecture robuste.", "high")],
        )

    recent = closes[-1]
    reference_13 = closes[-13] if len(closes) >= 13 else closes[0]
    reference_5 = closes[-5]
    medium_change = ((recent - reference_13) / reference_13) * 100 if reference_13 else 0.0
    short_change = ((recent - reference_5) / reference_5) * 100 if reference_5 else 0.0
    absolute_move = abs(medium_change)

    if medium_change > 0.12 and short_change >= -0.08:
        bias = "BUY"
        score = clamp_score(56 + min(18, absolute_move * 8))
        phase = "sequence haussiere incomplete"
        summary = "Lecture Elliott passive: le prix garde une sequence motive haussiere tant que le dernier repli reste contenu."
    elif medium_change < -0.12 and short_change <= 0.08:
        bias = "SELL"
        score = clamp_score(44 - min(18, absolute_move * 8))
        phase = "sequence baissiere incomplete"
        summary = "Lecture Elliott passive: le prix garde une sequence motive baissiere tant que le rebond court reste limite."
    else:
        bias = "NEUTRAL"
        score = 50
        phase = "correction / range probable"
        summary = "Lecture Elliott passive: la structure ressemble davantage a une correction qu'a une impulsion propre."

    return AgentResult(
        name="ElliottWaveAgent",
        department="Technical",
        bias=bias,
        score=score,
        confidence=48 if absolute_move < 0.2 else 58,
        summary=summary,
        evidence=[
            AgentEvidence("Structure", phase, "XAU/USD intraday"),
            AgentEvidence("Variation sequence", f"{medium_change:+.2f}% moyen terme / {short_change:+.2f}% court terme", "Prix"),
            AgentEvidence(
                "Base theorique",
                "Lecture passive inspiree des sequences motive/corrective et ratios Fibonacci.",
                "elliottwave-forecast.com/elliott-wave-theory",
            ),
        ],
        risks=[
            AgentRisk(
                "Validation manuelle",
                "Le comptage Elliott reste experimental et ne doit pas remplacer le verdict officiel.",
                "medium",
            )
        ],
    )


def build_passive_agent_results(
    gold: SymbolSnapshot,
    dxy: SymbolSnapshot,
    us10y: SymbolSnapshot,
    news: list[NewsItem],
    analysis: AnalysisResult,
    geopolitical_analysis: GeopoliticalAnalysis | None = None,
    fundamental_recommendation: TradeRecommendation | None = None,
    technical_recommendation: TradeRecommendation | None = None,
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

    price_score = clamp_score(50 + (gold.change_pct * 18) + (gold.period_change_pct * 6))
    price_risks = []
    if weekend_gold is not None:
        price_risks.append(AgentRisk("Proxy week-end", "IG Weekend Gold reste indicatif et distinct du spot semaine.", "medium"))
    agents.append(
        AgentResult(
            name="PriceAgent",
            department="Market",
            bias=score_to_bias(price_score),
            score=price_score,
            confidence=72 if gold.price else 35,
            summary="Lecture prix passive: spot, variation courte, support/resistance et proxy week-end si disponible.",
            evidence=[
                AgentEvidence("Spot XAU/USD", f"{gold.price:.2f} ({gold.change_pct:+.2f}%)", "Investing.com XAU/USD"),
                AgentEvidence("Support / resistance", f"{format_number(gold.support)} / {format_number(gold.resistance)}", "Calcul local"),
                data_quality_evidence,
            ],
            risks=price_risks,
        )
    )

    technical_score = technical_recommendation.score if technical_recommendation else 50
    agents.append(
        AgentResult(
            name="TechnicalAgent",
            department="Technical",
            bias=normalize_agent_bias(technical_recommendation.verdict if technical_recommendation else "NEUTRAL"),
            score=technical_score,
            confidence=70 if readings else 45,
            summary=(technical_recommendation.summary if technical_recommendation else "Lecture technique passive indisponible."),
            evidence=[
                AgentEvidence("Timeframes", f"{len(readings)} lectures EMA/RSI/MACD/volume", "GC=F proxy + spot XAU/USD"),
                AgentEvidence("Raisons", "; ".join((technical_recommendation.reasons if technical_recommendation else [])[:3]) or "aucune raison technique"),
            ],
            risks=[] if readings else [AgentRisk("Technique", "Aucune matrice multi-timeframe disponible.", "high")],
        )
    )
    agents.append(build_elliott_wave_agent(gold))

    official_10y = official_macro_rates.dgs10 if official_macro_rates and official_macro_rates.dgs10 else us10y
    macro_score = fundamental_recommendation.score if fundamental_recommendation else clamp_score(50 - dxy.change_pct * 18 - official_10y.change_abs * 600)
    macro_evidence = [
        AgentEvidence("DXY", f"{dxy.price:.2f} ({dxy.change_pct:+.2f}%)", "Yahoo Finance"),
        AgentEvidence("10Y US officiel", f"{official_10y.price:.2f}% ({official_10y.change_abs * 100:+.1f} bps)", "FRED DGS10" if official_macro_rates and official_macro_rates.dgs10 else "Yahoo Finance"),
    ]
    if official_macro_rates and official_macro_rates.dgs2 is not None:
        macro_evidence.append(AgentEvidence("2Y US officiel", f"{official_macro_rates.dgs2.price:.2f}% ({official_macro_rates.dgs2.change_abs * 100:+.1f} bps)", "FRED DGS2"))
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
    agents.append(
        AgentResult(
            name="MacroAgent",
            department="Macro",
            bias=normalize_agent_bias(fundamental_recommendation.verdict if fundamental_recommendation else score_to_bias(macro_score)),
            score=macro_score,
            confidence=78 if official_macro_rates and official_macro_rates.dgs10 else 68 if real_yield is not None else 55,
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
            bias="CAUTION" if market_regime and market_regime.name != "Normal Macro" else "NEUTRAL",
            score=regime_score,
            confidence=68 if market_regime else 45,
            summary=market_regime.summary if market_regime else "Regime geopolitique/petrole indisponible.",
            evidence=[
                AgentEvidence("Regime", market_regime.name if market_regime else "indisponible", "Headlines + WTI/Brent"),
                AgentEvidence("Fait detecte", primary_fact.title if primary_fact else "aucun fait structure", primary_fact.source if primary_fact else ""),
                AgentEvidence("Pourquoi", "; ".join((market_regime.reasons if market_regime else [])[:3]) or "aucune raison dominante"),
            ],
            risks=[AgentRisk("Oil shock", "Le regime peut inverser le lien geopolitique -> gold si oil/dollar captent la liquidite.", "high")],
        )
    )

    sentiment_score = clamp_score(50 + analysis.score * 5)
    agents.append(
        AgentResult(
            name="SentimentNewsAgent",
            department="Geopolitics & Flows",
            bias=score_to_bias(sentiment_score),
            score=sentiment_score,
            confidence=analysis.confidence,
            summary=heuristic_decision_sentence(analysis),
            evidence=[
                AgentEvidence("Headlines", top_news_titles(news, limit=2), "RSS/Google News"),
                AgentEvidence("Score headlines", str(analysis.score), "Moteur heuristique local"),
                AgentEvidence("Faits structures", str(len(event_facts or [])), "EventFact"),
                data_quality_evidence,
            ],
            risks=[AgentRisk("Bruit news", "Les titres peuvent etre redondants ou en retard sur le prix.", "medium")] + data_quality_risks,
        )
    )

    correlation_score = cross_asset_analysis.score if cross_asset_analysis else 50
    correlation_evidence = [
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
            confidence=70 if cross_asset_analysis else 40,
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
    if etf_flows_analysis is not None:
        flow_evidence.append(
            AgentEvidence(
                "ETF officiels",
                f"{etf_flows_analysis.status}: {format_signed_tonnes(etf_flows_analysis.global_weekly_demand_tonnes)} hebdo / {format_signed_tonnes(etf_flows_analysis.global_monthly_demand_tonnes)} mensuel",
                etf_flows_analysis.source_name,
            )
        )
    agents.append(
        AgentResult(
            name="FlowPositioningAgent",
            department="Geopolitics & Flows",
            bias=score_to_bias(flow_score),
            score=flow_score,
            confidence=flow_confidence,
            summary=flow_summary,
            evidence=flow_evidence,
            risks=[
                AgentRisk(
                    "Frequence COT",
                    "Le COT officiel est hebdomadaire; les ETF sont plus frequents mais cadrent les flux de fond, pas l'entree intraday.",
                    "medium",
                )
            ],
        )
    )

    agents.append(
        AgentResult(
            name="EventFactsAgent",
            department="Geopolitics & Flows",
            bias="CAUTION" if event_facts else "NEUTRAL",
            score=clamp_score(45 + len(event_facts or []) * 6),
            confidence=primary_fact.confidence if primary_fact else 35,
            summary=(
                f"{len(event_facts)} fait(s) structure(s) detecte(s); source principale: {primary_fact.source}."
                if primary_fact
                else "Aucun fait structure disponible."
            ),
            evidence=[
                AgentEvidence("Fait principal", primary_fact.title if primary_fact else "indisponible", primary_fact.source if primary_fact else ""),
                AgentEvidence("Confirmation", primary_fact.confirmation_level if primary_fact else "indisponible", "EventFact"),
                AgentEvidence("Chaine marche", primary_fact.market_chain if primary_fact else "indisponible", "EventFact"),
            ],
            risks=[AgentRisk("Validation", "Un fait structure reste une lecture de headline: il doit rester source et confirme.", "medium")],
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
    agents.append(
        AgentResult(
            name="TrumpPoliticalStatementsAgent",
            department="Geopolitics & Flows",
            bias="CAUTION" if political_items or trump_news else "NEUTRAL",
            score=political_score,
            confidence=primary_statement.confidence if primary_statement else 45 if trump_news else 30,
            summary=(
                f"Declaration politique sourcee detectee: {primary_statement.theme} ({primary_statement.validation_level})."
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
            ],
            risks=[
                AgentRisk(
                    "Anti-rumeur",
                    "Une declaration politique ne score fortement que si elle est officielle ou confirmee par source fiable.",
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
    agents.append(
        AgentResult(
            name="RiskManagerAgent",
            department="Decision",
            bias="CAUTION" if risk_reasons else "NEUTRAL",
            score=risk_score,
            confidence=72,
            summary="Controle passif du risque: verifie regime, contradictions, SL/TP et prudence execution.",
            evidence=[
                AgentEvidence("Decision officielle", f"{global_recommendation.verdict} {global_recommendation.score}/100" if global_recommendation else "indisponible", "Scoring actuel"),
                AgentEvidence("Alertes risque", "; ".join(risk_reasons) if risk_reasons else "aucune alerte majeure", "Event/regime"),
                data_quality_evidence,
            ],
            risks=[AgentRisk("Execution", "La lecture agent ne constitue pas un ordre; elle surveille les risques autour du plan.", "high")] + data_quality_risks,
        )
    )

    contradictions = build_agent_contradictions(agents)
    orchestrator_risks = [AgentRisk("Contradictions", item, "medium") for item in contradictions[:3]]
    agents.append(
        AgentResult(
            name="OrchestratorAgent",
            department="Decision",
            bias=normalize_agent_bias(global_recommendation.verdict if global_recommendation else "NEUTRAL"),
            score=risk_score,
            confidence=74,
            summary="Orchestrateur passif: compare les agents, signale les contradictions, mais ne remplace pas le verdict officiel.",
            evidence=[
                AgentEvidence("Verdict officiel conserve", global_recommendation.verdict if global_recommendation else "indisponible", "Moteur actuel"),
                AgentEvidence("Agents actifs", f"{len(agents) + 1} lectures passives", "Fondation Phase 5"),
                AgentEvidence("SourceRegistry", f"{data_quality_score}/100", "Phase 12"),
            ],
            risks=orchestrator_risks + data_quality_risks or [AgentRisk("Contradictions", "Aucune contradiction majeure entre agents passifs.", "low")],
        )
    )

    return agents


def build_agent_contradictions(agent_results: list[AgentResult]) -> list[str]:
    buy_agents = [agent.name for agent in agent_results if agent.bias == "BUY"]
    sell_agents = [agent.name for agent in agent_results if agent.bias == "SELL"]
    caution_agents = [agent.name for agent in agent_results if agent.bias == "CAUTION"]
    contradictions: list[str] = []
    if buy_agents and sell_agents:
        contradictions.append(f"BUY vs SELL: {', '.join(buy_agents[:3])} contre {', '.join(sell_agents[:3])}.")
    if caution_agents:
        contradictions.append(f"Prudence active: {', '.join(caution_agents[:4])}.")
    weak_confidence = [agent.name for agent in agent_results if agent.confidence < 45]
    if weak_confidence:
        contradictions.append(f"Confiance faible: {', '.join(weak_confidence[:4])}.")
    return contradictions


def agent_by_name(agent_results: list[AgentResult], name: str) -> AgentResult | None:
    return next((agent for agent in agent_results if agent.name == name), None)


def agent_bullish_score(agent: AgentResult | None, direct_score: bool = False) -> int:
    if agent is None:
        return 50
    if direct_score:
        return clamp_score(agent.score)
    if agent.bias == "BUY":
        return clamp_score(agent.score)
    if agent.bias == "SELL":
        return clamp_score(100 - agent.score)
    return 50


def component_bias(score: int) -> str:
    return score_to_bias(score, buy_threshold=56, sell_threshold=44)


def build_agent_component(
    key: str,
    label: str,
    agent: AgentResult | None,
    weight: float,
    direct_score: bool = False,
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
    )


def regime_directional_score(market_regime: MarketRegimeAnalysis | None) -> tuple[int, str, str]:
    if market_regime is None:
        return 50, "NEUTRAL", "Regime indisponible; score neutre."
    if market_regime.name == "Safe-Haven Gold":
        score = clamp_score(50 + market_regime.score * 0.35)
    elif market_regime.name in {"Hormuz / Oil Shock", "Dollar Liquidity Squeeze"}:
        score = clamp_score(50 - market_regime.score * 0.35)
    elif market_regime.name == "De-escalation / Oil Relief":
        score = clamp_score(50 - market_regime.score * 0.18)
    else:
        score = 50
    return score, component_bias(score), market_regime.summary


def build_regime_component(
    market_regime: MarketRegimeAnalysis | None,
    event_mode: EventModeAnalysis | None,
    weight: float,
) -> OrchestratorComponent:
    score, bias, reason = regime_directional_score(market_regime)
    if event_mode is not None and event_mode.active:
        reason = f"{reason} Mode event actif: le regime impose une prudence execution."
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
    )


def build_data_quality_component(
    data_quality: DataQualitySnapshot | None,
    weight: float,
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


def build_orchestrator_quality_gate(
    verdict: str,
    score: int,
    components: list[OrchestratorComponent],
    contradictions: list[str],
    data_quality: DataQualitySnapshot | None,
    event_mode: EventModeAnalysis | None,
    market_regime: MarketRegimeAnalysis | None,
) -> tuple[str, list[str]]:
    reasons: list[str] = []
    directional_components = [component for component in components if component.key != "data_quality"]
    strong_buy = [component.label for component in directional_components if component.score >= 62]
    strong_sell = [component.label for component in directional_components if component.score <= 38]
    if strong_buy and strong_sell:
        reasons.append(f"Contradiction forte: {', '.join(strong_buy[:3])} contre {', '.join(strong_sell[:3])}.")
    if len(contradictions) >= 2:
        reasons.append("Contradictions agents multiples: WAIT force avant trade.")
    if data_quality is None:
        reasons.append("Data quality indisponible: WAIT.")
    elif data_quality.score < 70:
        reasons.append(f"Data quality insuffisante: {data_quality.score}/100 < 70.")
    if event_mode is not None and event_mode.active:
        reasons.append(f"Mode event actif ({event_mode.score}/100): WAIT execution.")
    if market_regime is not None and market_regime.name == "Hormuz / Oil Shock":
        reasons.append("Regime Hormuz/Oil Shock: WAIT sans validation manuelle.")
    if verdict in {"BUY", "SELL"} and score < 60:
        reasons.append(f"Score orchestrateur insuffisant: {score}/100 < 60.")
    if verdict == "WAIT":
        reasons.append("Zone centrale: aucune direction n'a assez d'avantage.")
    if reasons:
        return "WAIT", reasons[:6]
    return "VALIDATED", ["Quality Gate v2 valide: score, sources et contradictions autorisent la decision."]


def build_orchestrator_decision(
    gold: SymbolSnapshot,
    legacy_recommendation: TradeRecommendation,
    agent_results: list[AgentResult],
    data_quality: DataQualitySnapshot | None = None,
    market_regime: MarketRegimeAnalysis | None = None,
    event_mode: EventModeAnalysis | None = None,
) -> tuple[TradeRecommendation, OrchestratorDecision]:
    weights = {
        "technical": 0.18,
        "elliott": 0.10,
        "macro": 0.18,
        "geopolitical_oil": 0.14,
        "cross_assets": 0.12,
        "flows": 0.10,
        "regime": 0.10,
        "data_quality": 0.08,
    }
    technical = agent_by_name(agent_results, "TechnicalAgent")
    elliott = agent_by_name(agent_results, "ElliottWaveAgent")
    macro = agent_by_name(agent_results, "MacroAgent")
    geopolitical = agent_by_name(agent_results, "GeopoliticalOilShockAgent")
    cross_assets = agent_by_name(agent_results, "CorrelationAgent")
    flows = agent_by_name(agent_results, "FlowPositioningAgent")

    components = [
        build_agent_component("technical", "Technique", technical, weights["technical"]),
        build_agent_component("elliott", "Elliott", elliott, weights["elliott"], direct_score=True),
        build_agent_component("macro", "Macro", macro, weights["macro"]),
        build_agent_component("geopolitical_oil", "Geopolitique/Oil", geopolitical, weights["geopolitical_oil"]),
        build_agent_component("cross_assets", "Cross-assets", cross_assets, weights["cross_assets"], direct_score=True),
        build_agent_component("flows", "Flows", flows, weights["flows"], direct_score=True),
        build_regime_component(market_regime, event_mode, weights["regime"]),
        build_data_quality_component(data_quality, weights["data_quality"]),
    ]
    total_weight = sum(component.weight for component in components)
    bullish_score = round(sum(component.contribution for component in components) / total_weight, 2)
    if bullish_score >= 55:
        verdict = "BUY"
        conviction = bullish_score
    elif bullish_score <= 45:
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
        components,
        contradictions,
        data_quality,
        event_mode,
        market_regime,
    )
    if gate_status == "WAIT":
        verdict = "WAIT"
        score = min(score, 59)

    direction_is_buy = verdict != "SELL"
    supportive = [
        component
        for component in components
        if component.key != "data_quality"
        if (component.score >= 55 if direction_is_buy else component.score <= 45)
    ]
    counter = [
        component
        for component in components
        if component.key != "data_quality"
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

    recommendation_verdict = verdict if verdict in {"BUY", "SELL"} else legacy_recommendation.verdict
    if recommendation_verdict == "BUY":
        stop_loss, tp1, tp2 = build_trade_levels(
            gold.price,
            atr=max(abs(legacy_recommendation.take_profit_1 - gold.price), 6.0),
            verdict="BUY",
            stop_multiplier=1.0,
            tp1_multiplier=1.15,
            tp2_multiplier=2.1,
        )
    elif recommendation_verdict == "SELL":
        stop_loss, tp1, tp2 = build_trade_levels(
            gold.price,
            atr=max(abs(legacy_recommendation.take_profit_1 - gold.price), 6.0),
            verdict="SELL",
            stop_multiplier=1.0,
            tp1_multiplier=1.15,
            tp2_multiplier=2.1,
        )
    else:
        stop_loss, tp1, tp2 = legacy_recommendation.stop_loss, legacy_recommendation.take_profit_1, legacy_recommendation.take_profit_2

    summary = (
        f"Orchestrateur v2 {verdict}: score pondere {bullish_score:.1f}/100, "
        f"ancien moteur {legacy_recommendation.verdict} {legacy_recommendation.score}/100. "
        + ("Quality Gate valide." if gate_status == "VALIDATED" else "WAIT force par Quality Gate.")
    )
    recommendation = TradeRecommendation(
        mode="Global v2",
        verdict=verdict,
        score=score,
        summary=summary,
        reasons=(top_reasons[:3] + [f"Contre-signal: {item}" for item in counter_reasons[:3]] + gate_reasons)[:8],
        stop_loss=stop_loss,
        take_profit_1=tp1,
        take_profit_2=tp2,
        source_note="Orchestrateur v2: agents ponderes, SourceRegistry, regime, contradictions et Trade Ledger.",
    )
    decision = OrchestratorDecision(
        verdict=verdict,
        score=score,
        status=gate_status,
        engine="orchestrator_v2_active",
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
                confidence=78 if decision.status == "VALIDATED" else 64,
                summary=(
                    f"Orchestrateur v2 actif: verdict {decision.verdict} {decision.score}/100; "
                    f"ancien moteur {decision.legacy_verdict} {decision.legacy_score}/100."
                ),
                evidence=[
                    AgentEvidence("Moteur", decision.engine, "Phase 14"),
                    AgentEvidence("Score pondere", f"{decision.bullish_score:.1f}/100", "Agents ponderes"),
                    AgentEvidence("Quality Gate", decision.status, "Orchestrator v2"),
                ],
                risks=[AgentRisk("Gate", reason, "high" if decision.status == "WAIT" else "low") for reason in decision.quality_gate_reasons[:3]],
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
    return [item for item in news if item.category in categories]


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
        reasons.append("Le VIX/fear gauge ne confirme pas un besoin fort de couverture.")
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
        category_scores[item.category] = category_scores.get(item.category, 0) + item.score

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


def headline_sort_key(item: NewsItem) -> tuple[int, datetime]:
    category_priority = {
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
    return (category_priority.get(item.category, 99), parse_iso_sort_key(item.published_at))


def text_contains_any(text: str, patterns: tuple[str, ...]) -> bool:
    return any(keyword_matches(text, pattern) for pattern in patterns)


def explain_headline_reason(item: NewsItem) -> str:
    text = normalize_title_for_dedupe(clean_display_text(item.title))

    if text_contains_any(text, ("iran", "middle east", "war", "conflict", "hormuz", "blockade", "shipping", "ports", "oil", "barrel", "fuel", "liquidity")):
        if text_contains_any(text, ("usd", "dollar", "liquidity")):
            return "La guerre pousse les investisseurs a chercher de la liquidite immediate en dollar, pas seulement des refuges comme l'or."
        if text_contains_any(text, ("oil", "barrel", "fuel", "hormuz", "shipping", "ports", "blockade")):
            return "Le marche craint une perturbation durable du petrole, donc plus d'inflation energie et plus de stress global."
        return "Le conflit brouille les reperes habituels de marche et augmente l'aversion au risque."

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
                "Le choc petrole soutient le theme refuge et inflation pour l'or, mais il peut aussi repousser les baisses de taux de la Fed.",
            )
        return ("bullish", "Plus d'incertitude geopolitique soutient en general la demande de couverture sur l'or.")

    if text_contains_any(text, ("fed", "fomc", "powell", "minutes", "rate", "cut", "cuts", "dovish", "pause")) or item.category == "macro_fed":
        if item.score > 0:
            return ("bullish", "Une Fed percue comme moins restrictive est plutot favorable a l'or.")
        if item.score < 0:
            return ("bearish", "Une Fed plus restrictive soutient le dollar et les rendements, donc pese sur l'or.")
        return ("mixte", "Le message Fed n'est pas assez net pour donner un avantage clair a l'or.")

    if text_contains_any(text, ("cpi", "inflation", "gasoline")) or item.category == "macro_cpi":
        if item.score > 0:
            return ("bullish", "Une inflation qui se calme peut reduire la pression sur les taux et aider l'or.")
        if item.score < 0:
            return ("bearish", "Une inflation qui repart complique les baisses de taux et peut penaliser l'or.")
        return ("mixte", "L'effet inflation est partage entre theme refuge et risque de Fed plus dure.")

    if text_contains_any(text, ("jobs", "nfp", "nonfarm", "employment", "payroll")) or item.category == "macro_nfp":
        if item.score > 0:
            return ("bullish", "Un emploi plus faible peut detendre le dollar et les rendements, ce qui aide l'or.")
        if item.score < 0:
            return ("bearish", "Un emploi solide peut renforcer le dollar et retarder les baisses de taux.")
        return ("mixte", "Les chiffres de l'emploi ne donnent pas ici un signal directionnel clair.")

    if text_contains_any(text, ("cot", "managed money", "speculative")) or item.category == "sentiment_cot":
        return ("info", "Le COT ne bouge pas directement le prix intraday, mais il dit si le marche est deja trop charge.")

    if text_contains_any(text, ("open interest",)) or item.category == "sentiment_oi":
        return ("info", "L'open interest confirme surtout si le mouvement est alimente par de nouveaux engagements.")

    if text_contains_any(text, ("etf", "gld", "iau")) or item.category == "sentiment_etf":
        return ("info", "Les flux ETF sont utiles pour le fond de marche, plus que pour un declenchement intraday instantane.")

    if text_contains_any(text, ("vix", "fear", "volatility")) or item.category == "risk_vix":
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
            if item.category != category:
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
    selected = set(categories)
    for item in pick_story_headlines(news, limit=max(10, len(selected) * 2)):
        if item.category in selected:
            return item
    for item in news:
        if item.category in selected:
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
            "mixte: soutien refuge possible, mais pression possible si oil/USD captent la liquidite.",
            "haussier si sanctions, menaces ou risque maritime augmentent.",
            "haussier possible si le marche cherche du cash dollar.",
            -1,
        )
    if theme == "Fed / Rates":
        if text_contains_any(text, ("cut", "lower", "pressure", "fire powell", "replace powell")):
            return (
                "haussier si le marche price des taux plus bas ou une Fed moins restrictive.",
                "neutre sauf impact inflation/risque.",
                "baissier possible si les taux attendus reculent.",
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
            "legerement haussier si tarifs touchent energie/logistique.",
            "haussier possible si risque commercial soutient le dollar.",
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


def build_event_fact_from_news(item: NewsItem) -> EventFact:
    text = clean_display_text(item.title)
    actors = detect_fact_labels(text, FACT_ACTOR_KEYWORDS) or ["Marche"]
    locations = detect_fact_labels(text, FACT_LOCATION_KEYWORDS) or ["Global"]
    themes = detect_fact_labels(text, FACT_THEME_KEYWORDS) or [item.category.replace("_", " ").title()]
    confirmation_level, base_confidence = classify_confirmation_level(item)
    impact_bias, impact_text = explain_headline_gold_impact(item)
    confidence = round(clamp(base_confidence + min(abs(item.score) * 3, 9), 35, 92))
    return EventFact(
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
    )


def build_event_facts(news: list[NewsItem], limit: int = 6) -> list[EventFact]:
    facts: list[EventFact] = []
    seen: set[str] = set()
    priority_categories = {
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
    }
    candidates = [
        item
        for item in pick_story_headlines(news, limit=max(limit * 3, 12))
        if item.category in priority_categories or abs(item.score) >= 1
    ]
    for item in candidates:
        key = normalize_title_for_dedupe(item.title)
        if not key or key in seen:
            continue
        seen.add(key)
        facts.append(build_event_fact_from_news(item))
        if len(facts) >= limit:
            break
    return facts


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
        return "Biais court terme: haussier, mais a confirmer seulement si le dollar reste mou et les taux poursuivent leur detente."
    if analysis.bias == "slightly bullish":
        return "Biais court terme: legerement haussier, avec besoin d'une confirmation par les news macro et le comportement du DXY."
    if analysis.bias == "bearish":
        return "Biais court terme: baissier, surtout si les rendements US et le dollar reprennent de la force."
    if analysis.bias == "slightly bearish":
        return "Biais court terme: legerement baissier, sans signal de conviction tres eleve."
    return "Biais court terme: neutre, le contexte ne donne pas encore un avantage propre dans un sens."


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
        payload["trade_ledger"] = asdict(trade_ledger)
    if orchestrator_decision:
        payload["orchestrator_decision"] = asdict(orchestrator_decision)
    payload["monitoring_inspector"] = build_monitoring_inspector_payload(
        str(payload["generated_at"]),
        data_quality,
        agent_results or [],
        trade_ledger,
        orchestrator_decision,
        global_recommendation,
        market_regime,
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
    return TradeLedgerSummary(
        ledger_path=str(data.get("ledger_path", str(TRADE_LEDGER_PATH))),
        generated_at=str(data.get("generated_at", iso_now())),
        quality_gate_status=str(data.get("quality_gate_status", "WAIT")),
        quality_gate_reasons=[str(item) for item in data.get("quality_gate_reasons", [])],
        active_trades=[
            parse_trade_plan(item)
            for item in data.get("active_trades", [])
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
    )


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
    )


def build_orchestrator_decision_from_payload(data: dict[str, Any] | None) -> OrchestratorDecision | None:
    if not isinstance(data, dict):
        return None
    return OrchestratorDecision(
        verdict=str(data.get("verdict", "WAIT")),
        score=int(data.get("score", 50) or 50),
        status=str(data.get("status", "WAIT")),
        engine=str(data.get("engine", "orchestrator_v2")),
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


def build_event_fact_from_payload(data: dict[str, Any]) -> EventFact:
    return EventFact(
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
        )
        if isinstance(market_regime_payload, dict)
        else None
    )
    official_macro_rates = (
        OfficialMacroRates(
            dgs10=build_macro_rate_from_payload(official_macro_data.get("dgs10"), FRED_SERIES_LABELS["DGS10"]),
            dgs2=build_macro_rate_from_payload(official_macro_data.get("dgs2"), FRED_SERIES_LABELS["DGS2"]),
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
                "## Orchestrateur v2",
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
                "- Statut: orchestrateur actif depuis Phase 14; agents sources ponderes et ancien moteur conserve en comparaison.",
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
        "slightly bullish": "Legerement haussier",
        "bearish": "Baissier",
        "slightly bearish": "Legerement baissier",
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
    if upper == "BUY":
        return "bullish"
    if upper == "SELL":
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
    <div class="metric-footnote">{html.escape(analysis.source_note)} {source_link}</div>
    """.strip()


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
        status_class = "bearish" if event.impact_level == "HIGH" else "neutral"
        rows.append(
            f"""
            <tr>
              <td><strong>{html.escape(event.event_type)}</strong><br><span class="soft">{html.escape(event.source_name)}</span></td>
              <td>{html.escape(event.title)}</td>
              <td>{html.escape(format_timestamp_for_humans(event.scheduled_at))}<br><span class="soft">{html.escape(format_macro_countdown(event.minutes_to_event))}</span></td>
              <td class="{status_class}">{html.escape(event.impact_level)}</td>
              <td>{html.escape(event.gold_impact)}</td>
            </tr>
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
      <div class="geo-stat"><strong>FedWatch</strong><span>{html.escape(calendar.fedwatch_status)}</span></div>
      <div class="geo-stat"><strong>Refresh</strong><span>{html.escape(format_timestamp_for_humans(calendar.generated_at))}</span></div>
    </div>
    <div class="table-wrap">
      <table class="technical-table">
        <thead><tr><th>Event</th><th>Titre</th><th>Date / countdown</th><th>Impact</th><th>Pourquoi gold</th></tr></thead>
        <tbody>{''.join(rows) or '<tr><td colspan="5">Aucun catalyseur macro disponible.</td></tr>'}</tbody>
      </table>
    </div>
    <div class="metric-footnote">
      {html.escape(calendar.source_note)} {fedwatch_link}. {html.escape(calendar.fedwatch_note)}
    </div>
    """.strip()


def render_data_quality_panel(data_quality: DataQualitySnapshot | None) -> str:
    if data_quality is None:
        return '<div class="empty-state">Data quality indisponible: SourceRegistry non calcule sur ce snapshot.</div>'

    status_class = "bullish" if data_quality.score >= 80 else "neutral" if data_quality.score >= 60 else "bearish"
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


def render_monitoring_inspector_panel(
    generated_at: str,
    data_quality: DataQualitySnapshot | None,
    agent_results: list[AgentResult],
    trade_ledger: TradeLedgerSummary | None,
    orchestrator_decision: OrchestratorDecision | None,
    global_recommendation: TradeRecommendation | None,
    market_regime: MarketRegimeAnalysis | None,
) -> str:
    inspector = build_monitoring_inspector_payload(
        generated_at,
        data_quality,
        agent_results,
        trade_ledger,
        orchestrator_decision,
        global_recommendation,
        market_regime,
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
                  <td>{plan.stop_loss:.2f} / {plan.tp1:.2f} / {plan.tp2:.2f} / {plan.tp3:.2f}</td>
                  <td class="{trade_status_class(plan.status)}">{html.escape(plan.status)}</td>
                  <td>{html.escape(plan.outcome)}</td>
                  <td>{html.escape(plan.outcome_reason[:160])}</td>
                </tr>
                """.strip()
            )

    source_counts = inspector["source_counts"]
    trades = inspector["trades"]
    decision = inspector["decision"]
    gate_reasons = "".join(f"<li>{html.escape(reason)}</li>" for reason in decision["quality_gate_reasons"][:6]) or "<li>Aucun blocage decisionnel signale.</li>"
    trade_gate_reasons = "".join(f"<li>{html.escape(reason)}</li>" for reason in trades["quality_gate_reasons"][:6]) or "<li>Aucune raison Trade Gate disponible.</li>"
    source_issues = "".join(
        f"<li>{html.escape(issue['name'])}: {html.escape(issue['status'])} · {html.escape(issue['value_summary'])}</li>"
        for issue in inspector["source_issues"][:8]
    ) or "<li>Aucune source missing/stale/weak detectee.</li>"

    return f"""
    <div class="trade-verdict {state_tone_class(decision['gate_status'])}">Inspector · {html.escape(decision['verdict'])} {decision['score']}/100 · Data quality {inspector['data_quality_score']}/100</div>
    <p class="trade-summary">Vue d'audit: elle explique quelles sources alimentent les agents, quel gate bloque ou valide la decision, et quels trades existent dans le ledger.</p>
    <div class="geo-grid">
      <div class="geo-stat"><strong>Dernier refresh</strong><span>{html.escape(format_timestamp_for_humans(inspector['last_refresh']))}</span></div>
      <div class="geo-stat"><strong>Sources actives</strong><span>{source_counts['active']} / {source_counts['total']}</span></div>
      <div class="geo-stat"><strong>Sources en alerte</strong><span>{source_counts['issues']}</span><small>missing {source_counts['missing']} · stale {source_counts['stale']} · weak {source_counts['weak']}</small></div>
      <div class="geo-stat"><strong>Agents actifs</strong><span>{inspector['agents']['active']} / {inspector['agents']['total']}</span></div>
      <div class="geo-stat"><strong>Trades crees</strong><span>{trades['total']}</span><small>actifs {trades['active']} · wins {trades['wins']} · losses {trades['losses']}</small></div>
      <div class="geo-stat"><strong>Audit log</strong><span>{html.escape(str(AUDIT_LOG_PATH))}</span><small>append-only JSONL</small></div>
    </div>
    <div class="geo-columns">
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
        <thead><tr><th>Agent</th><th>Status</th><th>Sortie</th><th>Confiance</th><th>Resume recent</th><th>Preuves / risques</th></tr></thead>
        <tbody>{''.join(agent_rows) or '<tr><td colspan="6">Aucun agent auditable sur ce snapshot.</td></tr>'}</tbody>
      </table>
    </div>
    <div class="table-wrap">
      <table class="technical-table">
        <thead><tr><th>Trade</th><th>Entry</th><th>SL / TP1 / TP2 / TP3</th><th>Status</th><th>Outcome</th><th>Pourquoi</th></tr></thead>
        <tbody>{''.join(trade_rows) or '<tr><td colspan="6">Aucun trade cree dans le ledger.</td></tr>'}</tbody>
      </table>
    </div>
    """.strip()


def trade_status_class(status: str) -> str:
    if status in {"tp1_hit", "tp2_hit", "tp3_hit"}:
        return "bullish"
    if status in {"sl_hit", "invalidated"}:
        return "bearish"
    return "neutral"


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
              <td>{plan.tp1:.2f} / {plan.tp2:.2f} / {plan.tp3:.2f}</td>
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
              <td>{html.escape(plan.market_regime)}</td>
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
    </div>
    <div class="module-block">
      <div class="section-kicker">Quality Gate</div>
      <ul class="reason-list">{gate_reasons}</ul>
      <div class="metric-footnote">Ledger append-only: {html.escape(ledger.ledger_path)}</div>
    </div>
    <div class="table-wrap">
      <table class="technical-table">
        <thead><tr><th>Trade</th><th>Entry / zone</th><th>SL</th><th>TP1 / TP2 / TP3</th><th>Status</th><th>Outcome reason</th></tr></thead>
        <tbody>{''.join(active_rows) or '<tr><td colspan="6">Aucun trade actif verrouille pour le moment.</td></tr>'}</tbody>
      </table>
    </div>
    <div class="table-wrap">
      <table class="technical-table">
        <thead><tr><th>Cree</th><th>Direction</th><th>Entry</th><th>Status</th><th>Outcome</th><th>Regime</th></tr></thead>
        <tbody>{''.join(recent_rows) or '<tr><td colspan="6">Historique vide.</td></tr>'}</tbody>
      </table>
    </div>
    """.strip()


def render_orchestrator_decision_panel(decision: OrchestratorDecision | None) -> str:
    if decision is None:
        return '<div class="empty-state">Orchestrateur v2 indisponible sur ce snapshot.</div>'
    rows = "".join(
        f"""
        <tr>
          <td><strong>{html.escape(component.label)}</strong><br><span class="soft">{html.escape(component.source)}</span></td>
          <td class="{recommendation_css_class(component.bias)}">{html.escape(component.bias)}</td>
          <td>{component.score}/100</td>
          <td>{component.weight:.2f}</td>
          <td>{component.contribution:.2f}</td>
          <td>{html.escape(component.reason[:150])}</td>
        </tr>
        """.strip()
        for component in decision.components
    )
    top_reasons = "".join(f"<li>{html.escape(reason)}</li>" for reason in decision.top_reasons[:3]) or "<li>Aucune raison dominante.</li>"
    counter_reasons = "".join(f"<li>{html.escape(reason)}</li>" for reason in decision.counter_reasons[:3]) or "<li>Aucun contre-signal majeur.</li>"
    gate_reasons = "".join(f"<li>{html.escape(reason)}</li>" for reason in decision.quality_gate_reasons[:5]) or "<li>Quality Gate non evalue.</li>"
    badge_class = recommendation_css_class(decision.verdict)
    return f"""
    <div class="trade-verdict {badge_class}">Orchestrateur v2 · {html.escape(decision.verdict)} · {decision.score}/100 · {html.escape(decision.status)}</div>
    <div class="tag-row">
      <span class="source-tag">Engine · {html.escape(decision.engine)}</span>
      <span class="source-tag">Legacy · {html.escape(decision.legacy_verdict)} {decision.legacy_score}/100</span>
      <span class="source-tag {state_tone_class(decision.status)}">Gate · {html.escape(decision.status)}</span>
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
    if upper in {"OK", "ONLINE", "VALIDATED", "ACTIVE", "LOCKED"}:
        return "bullish"
    if upper in {"WAIT", "CAUTION", "STALE", "MISSING", "FORCED"}:
        return "caution"
    if upper in {"ERROR", "WEAK", "BLOCKED"}:
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
    wait_forced = global_recommendation.verdict == "WAIT" or gate_status == "WAIT"
    cards = [
        ("Live signal", global_recommendation.verdict, f"{global_recommendation.score}/100 · {global_recommendation.mode}", recommendation_css_class(global_recommendation.verdict)),
        ("Trade locked", "LOCKED" if active_trades else "WAIT", f"{active_trades} trade(s) actif(s)", "bullish" if active_trades else "neutral"),
        ("Sources", "STALE" if source_alerts else source_status, source_detail, "caution" if source_alerts else state_tone_class(source_status)),
        ("Contradictions", "ACTIVE" if contradiction_count else "OK", f"{contradiction_count} contradiction(s)", "caution" if contradiction_count else "bullish"),
        ("Quality gate", "WAIT force" if wait_forced else gate_status, (market_regime.name if market_regime else "Normal Macro"), "caution" if wait_forced else state_tone_class(gate_status)),
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
    return f'<section class="state-board" aria-label="Etats visuels Aureum Flux">{nodes}</section>'


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


def render_event_facts_panel(event_facts: list[EventFact]) -> str:
    cards: list[str] = []
    for fact in event_facts[:6]:
        tone_class = "bullish" if fact.impact_bias == "bullish" else "bearish" if fact.impact_bias == "bearish" else "neutral"
        source_link = (
            f'<a href="{html.escape(fact.source_url)}" target="_blank" rel="noopener noreferrer">Ouvrir la source</a>'
            if fact.source_url
            else ""
        )
        cards.append(
            f"""
            <article class="headline-brief {tone_class}">
              <div class="headline-brief-top">
                <div class="headline-brief-source">{html.escape(fact.source)}</div>
                <div class="headline-brief-time">{html.escape(format_timestamp_for_humans(fact.published_at))}</div>
              </div>
              <div class="section-kicker">Fait detecte · {html.escape(fact.confirmation_level)} · confiance {fact.confidence}/100</div>
              <h3>{html.escape(fact.title)}</h3>
              <p><strong>Acteurs:</strong> {html.escape(", ".join(fact.actors))}</p>
              <p><strong>Lieux:</strong> {html.escape(", ".join(fact.locations))}</p>
              <p><strong>Themes:</strong> {html.escape(", ".join(fact.themes))}</p>
              <p><strong>Chaine marche:</strong> {html.escape(fact.market_chain)}</p>
              <p><strong>Impact gold:</strong> {html.escape(fact.gold_impact)}</p>
              {source_link}
            </article>
            """.strip()
        )

    if not cards:
        return (
            '<div class="empty-state">'
            "Aucun fait structure detecte pour le moment. Les headlines restent disponibles dans le bloc suivant."
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
    <div class="trade-verdict {badge_class}">{html.escape(regime.name)} · {regime.score}/100</div>
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
                "Le risque geopolitique reste actif. Cela soutient la demande de couverture sur l'or, "
                "mais cela peut aussi envoyer une partie des capitaux vers le dollar pour chercher de la liquidite."
            )
        elif geopolitical.risk_off_status == "en reflux":
            geo_sentence = (
                "Le stress geopolitique se calme un peu. L'or perd alors une partie de son soutien refuge."
            )
        else:
            geo_sentence = (
                "Le fond geopolitique reste brouille: il y a du stress, mais pas un signal unique assez fort pour imposer seul la direction."
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


def build_scenarios(gold: SymbolSnapshot, dxy: SymbolSnapshot, us10y: SymbolSnapshot) -> tuple[str, str, str]:
    support = format_number(gold.support)
    resistance = format_number(gold.resistance)
    dxy_change = f"{dxy.change_pct:+.2f}%"
    yield_change = f"{us10y.change_abs * 100:+.1f} bps"

    bullish_case = (
        f"Scenario hausse: favorable tant que l'or defend la zone {support} "
        f"et que le DXY ({dxy_change}) ainsi que le 10Y US ({yield_change}) ne se retournent pas franchement."
    )
    bearish_case = (
        f"Scenario baisse: le risque augmente si le prix echoue sous {resistance} "
        "et si le dollar ou les rendements US reprennent de la force."
    )
    wait_case = (
        f"Scenario attente: patienter si le prix reste enferme entre {support} et {resistance} "
        "sans catalyseur macro propre."
    )
    return bullish_case, bearish_case, wait_case


def render_dashboard(
    bundle: BriefingBundle,
    live_client: bool = False,
    fragment_endpoint: str = "/fragment",
    poll_seconds: int = 10,
) -> str:
    return render_dashboard_clarity_v2(bundle, live_client, fragment_endpoint, poll_seconds)

    gold = bundle.gold
    dxy = bundle.dxy
    us10y = bundle.us10y
    analysis = bundle.analysis
    ai_analysis = bundle.ai_analysis
    bullish_case, bearish_case, wait_case = build_scenarios(gold, dxy, us10y)
    generated_at = format_timestamp_for_humans(bundle.payload["generated_at"])
    chart_svg = candlestick_svg(gold.intraday_points or gold.points, gold.price)
    confidence_width = max(8, min(100, analysis.confidence))

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
    geopolitical_analysis = bundle.geopolitical_analysis or analysis.geopolitical
    technical_readings = bundle.technical_timeframes or []
    executive_summary = bundle.executive_summary or build_executive_summary(fundamental, technical, geopolitical_analysis)
    price_class = "bullish" if gold.change_pct > 0 else "bearish" if gold.change_pct < 0 else "neutral"
    dxy_class = "bullish" if dxy.change_pct < 0 else "bearish" if dxy.change_pct > 0 else "neutral"
    us10y_class = "bullish" if us10y.change_abs < 0 else "bearish" if us10y.change_abs > 0 else "neutral"
    bias_class = format_bias_class(analysis.bias)
    bias_label = format_bias_label(analysis.bias).upper()
    geo_class = (
        "bullish"
        if geopolitical_analysis is not None and geopolitical_analysis.score >= 55
        else "bearish"
        if geopolitical_analysis is not None and geopolitical_analysis.score <= 45
        else "neutral"
    )
    meta_refresh = "" if live_client else '  <meta http-equiv="refresh" content="60">\n'
    live_script = ""
    if live_client:
        live_script = f"""
  <script>
    (() => {{
      const app = document.getElementById("dashboard-app");
      if (!app) return;
      let busy = false;
      async function refreshLive() {{
        if (busy) return;
        busy = true;
        try {{
          const response = await fetch("{fragment_endpoint}?_ts=" + Date.now(), {{ cache: "no-store" }});
          if (!response.ok) return;
          app.innerHTML = await response.text();
        }} catch (_error) {{
          // Keep the last successful snapshot on screen if the refresh fails.
        }} finally {{
          busy = false;
        }}
      }}
      window.setInterval(refreshLive, {max(5, poll_seconds) * 1000});
    }})();
  </script>
""".rstrip()

    try:
        local_dt = datetime.fromisoformat(bundle.payload["generated_at"].replace("Z", "+00:00")).astimezone()
        hour = local_dt.hour
        if 6 <= hour < 12:
            session_label = "EUROPE"
        elif 12 <= hour < 18:
            session_label = "EUROPE/US"
        elif 18 <= hour < 23:
            session_label = "US"
        else:
            session_label = "ASIA/OFF"
    except ValueError:
        session_label = "LIVE"

    technical_matrix = (
        render_technical_table(technical_readings)
        if technical_readings
        else '<div class="footer-note">Lecture technique indisponible.</div>'
    )

    return f"""<!doctype html>
<html lang="fr">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
{meta_refresh}  <meta name="color-scheme" content="dark">
  <title>Dashboard XAUUSD</title>
  <style>
    :root {{
      --bg: #0a0b0d;
      --panel: #0d0f12;
      --panel-alt: #08090b;
      --terminal: #050607;
      --grid: #1a1d24;
      --text: #c8c8c8;
      --bull: #00ff88;
      --bear: #ff3c5a;
      --amber: #f5a623;
      --muted: #2a2d35;
      --soft: #8f96a3;
    }}

    * {{
      box-sizing: border-box;
      border-radius: 0 !important;
      box-shadow: none !important;
      font-family: "JetBrains Mono", "IBM Plex Mono", "Courier New", monospace;
    }}
    html, body {{
      margin: 0;
      min-height: 100vh;
      background: var(--bg);
      color: var(--text);
    }}
    body::before {{
      content: "";
      position: fixed;
      inset: 0;
      pointer-events: none;
      opacity: 0.08;
      background: repeating-linear-gradient(
        to bottom,
        rgba(255, 255, 255, 0.08) 0,
        rgba(255, 255, 255, 0.08) 1px,
        transparent 1px,
        transparent 4px
      );
    }}
    a {{
      color: var(--amber);
      text-decoration: none;
    }}
    a:hover {{
      text-decoration: underline;
    }}
    h1, h2, h3, p {{
      margin: 0;
    }}
    .page {{
      position: relative;
      z-index: 1;
      width: min(1600px, calc(100% - 10px));
      margin: 5px auto;
      background: var(--muted);
      border: 1px solid var(--muted);
    }}
    .hero,
    .panel,
    .trade-card,
    .quick-card,
    .executive-panel,
    .ticker-panel,
    .status-cell {{
      background: var(--panel);
      border: 1px solid var(--muted);
      padding: 10px 12px;
    }}
    .hero {{
      border: none;
      padding: 0;
      background: var(--muted);
    }}
    .hero-header,
    .hero-summary-strip,
    .quick-decision-grid,
    .top-grid,
    .trade-grid,
    .content-grid,
    .scenario-grid,
    .key-levels,
    .trade-levels {{
      display: grid;
      gap: 1px;
      background: var(--muted);
    }}
    .hero-summary-strip {{
      grid-template-columns: repeat(4, minmax(0, 1fr));
    }}
    .quick-decision-grid {{
      grid-template-columns: repeat(2, minmax(0, 1fr));
    }}
    .top-grid {{
      grid-template-columns: minmax(0, 2fr) minmax(320px, 0.8fr);
    }}
    .trade-grid {{
      grid-template-columns: repeat(2, minmax(0, 1fr));
    }}
    .content-grid {{
      grid-template-columns: repeat(12, minmax(0, 1fr));
      margin-top: 1px;
    }}
    .span-4 {{ grid-column: span 4; }}
    .span-5 {{ grid-column: span 5; }}
    .span-6 {{ grid-column: span 6; }}
    .span-7 {{ grid-column: span 7; }}
    .span-12 {{ grid-column: span 12; }}
    .section-kicker,
    .eyebrow {{
      color: var(--amber);
      font-size: 11px;
      letter-spacing: 0.16em;
      text-transform: uppercase;
      margin-bottom: 8px;
    }}
    .ticker-panel {{
      min-height: 210px;
      display: flex;
      flex-direction: column;
      justify-content: space-between;
    }}
    .ticker-symbol {{
      color: var(--amber);
      font-size: 20px;
      letter-spacing: 0.12em;
      text-transform: uppercase;
      margin-bottom: 10px;
    }}
    .ticker-row {{
      display: flex;
      flex-wrap: wrap;
      align-items: flex-end;
      gap: 14px;
    }}
    .ticker-price {{
      font-size: clamp(50px, 7vw, 82px);
      font-weight: 700;
      line-height: 0.95;
      letter-spacing: -0.06em;
      white-space: nowrap;
    }}
    .ticker-price.bullish,
    .metric-delta.positive,
    .trade-card.bullish .trade-verdict,
    .quick-card.bullish strong,
    .signal-badge.bullish,
    .status-value.bullish,
    .technical-table .bullish,
    .positive h3 {{
      color: var(--bull);
    }}
    .ticker-price.bearish,
    .metric-delta.negative,
    .trade-card.bearish .trade-verdict,
    .quick-card.bearish strong,
    .signal-badge.bearish,
    .status-value.bearish,
    .technical-table .bearish,
    .negative h3 {{
      color: var(--bear);
    }}
    .ticker-price.neutral,
    .metric-delta.neutral,
    .status-value.neutral,
    .neutral h3 {{
      color: var(--text);
    }}
    .ticker-cursor {{
      display: inline-block;
      width: 12px;
      height: 0.95em;
      margin-left: 8px;
      background: currentColor;
      vertical-align: text-bottom;
      animation: blink 1s steps(1) infinite;
    }}
    @keyframes blink {{
      50% {{ opacity: 0; }}
    }}
    .ticker-delta {{
      font-size: 24px;
      font-weight: 700;
      white-space: nowrap;
      padding-bottom: 8px;
    }}
    .ticker-meta {{
      margin-top: 10px;
      color: var(--soft);
      font-size: 11px;
      letter-spacing: 0.12em;
      text-transform: uppercase;
      line-height: 1.7;
    }}
    .status-cell {{
      display: flex;
      flex-direction: column;
      justify-content: space-between;
      min-height: 68px;
      background: var(--terminal);
    }}
    .status-value {{
      font-size: 20px;
      font-weight: 700;
      text-transform: uppercase;
      line-height: 1.25;
    }}
    .status-value.small {{
      font-size: 14px;
      color: var(--text);
    }}
    .confidence-bar {{
      height: 8px;
      margin-top: 8px;
      background: var(--grid);
      border: 1px solid var(--muted);
    }}
    .confidence-bar span {{
      display: block;
      width: {confidence_width}%;
      height: 100%;
      background: var(--amber);
    }}
    .quick-card {{
      min-height: 124px;
      background: var(--panel-alt);
      border-top: 2px solid var(--muted);
    }}
    .quick-card.bullish {{ border-top-color: var(--bull); }}
    .quick-card.bearish {{ border-top-color: var(--bear); }}
    .quick-card-top {{
      display: flex;
      justify-content: space-between;
      gap: 10px;
      margin-bottom: 10px;
      align-items: flex-start;
    }}
    .quick-card-top strong {{
      display: inline-block;
      font-size: 30px;
      letter-spacing: 0.08em;
      text-transform: uppercase;
    }}
    .quick-score {{
      color: var(--amber);
      font-size: 38px;
      font-weight: 700;
      line-height: 1;
      white-space: nowrap;
    }}
    .quick-score small {{
      font-size: 15px;
      color: var(--soft);
      margin-left: 4px;
    }}
    .quick-level-row {{
      display: grid;
      grid-template-columns: repeat(3, minmax(0, 1fr));
      gap: 1px;
      background: var(--muted);
    }}
    .quick-level-row span {{
      display: block;
      padding: 8px 10px;
      background: var(--panel);
      color: var(--text);
      font-size: 12px;
      letter-spacing: 0.08em;
      text-transform: uppercase;
    }}
    .trade-card {{
      min-height: 100%;
      background: var(--panel-alt);
      border-left: 3px solid var(--muted);
    }}
    .trade-card.bullish {{ border-left-color: var(--bull); }}
    .trade-card.bearish {{ border-left-color: var(--bear); }}
    .trade-card-head {{
      display: grid;
      grid-template-columns: 1fr auto;
      gap: 10px;
      align-items: start;
      margin-bottom: 10px;
    }}
    .trade-card h2,
    .metric-card h2,
    .scenario h3 {{
      color: var(--amber);
      font-size: 14px;
      letter-spacing: 0.12em;
      text-transform: uppercase;
    }}
    .trade-score {{
      color: var(--amber);
      font-size: 36px;
      font-weight: 700;
      line-height: 1;
      white-space: nowrap;
    }}
    .trade-score small {{
      font-size: 15px;
      color: var(--soft);
      margin-left: 4px;
    }}
    .trade-verdict {{
      margin-bottom: 10px;
      font-size: 22px;
      font-weight: 700;
      text-transform: uppercase;
      letter-spacing: 0.1em;
    }}
    .trade-summary,
    .footer-note,
    .metric-footnote,
    .scenario p,
    .terminal-text,
    .ai-copy {{
      color: var(--text);
      line-height: 1.65;
      font-size: 14px;
    }}
    .trade-levels {{
      grid-template-columns: repeat(3, minmax(0, 1fr));
      margin: 10px 0;
    }}
    .trade-levels div {{
      background: var(--panel);
      border: 1px solid var(--muted);
      padding: 8px 10px;
    }}
    .trade-levels span,
    .trade-footer,
    .level-chip strong,
    .metric-footnote,
    .footer-note {{
      font-size: 11px;
      letter-spacing: 0.08em;
      text-transform: uppercase;
    }}
    .trade-levels strong,
    .metric-value,
    .level-chip span {{
      display: block;
      margin-top: 4px;
      font-size: 26px;
      font-weight: 700;
      line-height: 1.1;
      color: var(--text);
    }}
    .trade-reasons,
    .reason-list {{
      margin: 0;
      padding-left: 18px;
      color: var(--text);
      line-height: 1.55;
      font-size: 13px;
    }}
    .trade-footer {{
      margin-top: 10px;
      padding-top: 10px;
      border-top: 1px solid var(--muted);
      color: var(--soft);
      display: flex;
      flex-direction: column;
      gap: 6px;
    }}
    .executive-panel {{
      background: var(--terminal);
      min-height: 100%;
    }}
    .terminal-line {{
      display: grid;
      grid-template-columns: auto auto 1fr;
      gap: 10px;
      align-items: start;
      padding: 6px 0;
      border-top: 1px solid rgba(42, 45, 53, 0.55);
    }}
    .terminal-line:first-of-type {{
      border-top: none;
    }}
    .prompt {{
      color: var(--bull);
      font-weight: 700;
    }}
    .terminal-tag {{
      color: var(--amber);
      font-size: 12px;
      letter-spacing: 0.12em;
      text-transform: uppercase;
      white-space: nowrap;
    }}
    .terminal-text a {{
      text-transform: none;
    }}
    .metric-card {{
      min-height: 0;
    }}
    .metric-value {{
      font-size: 34px;
      letter-spacing: -0.04em;
      color: var(--text);
    }}
    .metric-delta {{
      margin-top: 6px;
      font-size: 16px;
      font-weight: 700;
      letter-spacing: 0.06em;
      text-transform: uppercase;
    }}
    .metric-footnote {{
      color: var(--soft);
      margin-top: 10px;
      line-height: 1.7;
    }}
    .chart-wrap {{
      margin-top: 10px;
      border: 1px solid var(--muted);
      background: #0d0f12;
    }}
    .chart-wrap svg {{
      display: block;
      width: 100%;
      height: auto;
    }}
    .key-levels {{
      grid-template-columns: repeat(3, minmax(0, 1fr));
      margin-top: 1px;
    }}
    .level-chip {{
      background: var(--panel-alt);
      border: 1px solid var(--muted);
      padding: 8px 10px;
    }}
    .level-chip strong {{
      color: var(--amber);
    }}
    .scenario-grid {{
      grid-template-columns: repeat(3, minmax(0, 1fr));
      margin-top: 10px;
    }}
    .scenario {{
      background: var(--panel-alt);
      border-top: 2px solid var(--muted);
      padding: 10px 12px;
      min-height: 0;
    }}
    .scenario.positive {{ border-top-color: var(--bull); }}
    .scenario.negative {{ border-top-color: var(--bear); }}
    .scenario.neutral {{ border-top-color: var(--amber); }}
    .scenario p {{
      margin-top: 8px;
    }}
    .table-wrap {{
      overflow-x: auto;
      border: 1px solid var(--muted);
      background: #0d0f12;
    }}
    .technical-table {{
      width: 100%;
      min-width: 860px;
      border-collapse: collapse;
    }}
    .technical-table th,
    .technical-table td {{
      padding: 10px 12px;
      text-align: left;
      border-bottom: 1px solid var(--muted);
      font-size: 13px;
    }}
    .technical-table th {{
      color: var(--amber);
      background: #0b0d10;
      letter-spacing: 0.12em;
      text-transform: uppercase;
      font-size: 11px;
    }}
    .technical-table tr:nth-child(even) td {{
      background: rgba(8, 9, 11, 0.65);
    }}
    .geo-grid {{
      display: grid;
      grid-template-columns: repeat(4, minmax(0, 1fr));
      gap: 1px;
      margin-top: 10px;
      background: var(--muted);
    }}
    .geo-stat {{
      background: var(--panel-alt);
      border: 1px solid var(--muted);
      padding: 8px 10px;
      min-height: 72px;
    }}
    .geo-stat strong {{
      display: block;
      color: var(--amber);
      font-size: 11px;
      letter-spacing: 0.08em;
      text-transform: uppercase;
      margin-bottom: 6px;
    }}
    .geo-stat span {{
      display: block;
      color: var(--text);
      font-size: 16px;
      text-transform: uppercase;
      line-height: 1.35;
    }}
    .geo-columns {{
      display: grid;
      grid-template-columns: repeat(2, minmax(0, 1fr));
      gap: 12px;
      margin-top: 12px;
    }}
    .ai-panel {{
      background: var(--terminal);
    }}
    @media (max-width: 1180px) {{
      .hero-header,
      .top-grid,
      .trade-grid,
      .scenario-grid,
      .geo-grid,
      .geo-columns {{
        grid-template-columns: 1fr;
      }}
      .span-4,
      .span-5,
      .span-6,
      .span-7,
      .span-12 {{
        grid-column: span 12;
      }}
    }}
    @media (max-width: 900px) {{
      .hero-summary-strip,
      .quick-decision-grid,
      .key-levels,
      .trade-levels {{
        grid-template-columns: 1fr;
      }}
      .ticker-row {{
        flex-direction: column;
        align-items: flex-start;
      }}
      .terminal-line {{
        grid-template-columns: auto 1fr;
      }}
      .terminal-tag {{
        grid-column: 2;
      }}
      .terminal-text,
      .ai-copy {{
        grid-column: 1 / -1;
        padding-left: 22px;
      }}
    }}
  </style>
</head>
<body>
  <main class="page" id="dashboard-app">
    <section class="hero">
      <div class="hero-header">
        <div class="ticker-panel">
          <div class="section-kicker">Instrument · Timeframe · Session</div>
          <div class="ticker-symbol">XAU/USD SPOT · INTRADAY · {session_label}</div>
          <div class="ticker-row">
            <div class="ticker-price {price_class}">{gold.price:.2f}<span class="ticker-cursor"></span></div>
            <div class="ticker-delta {price_class}">{gold.change_abs:+.2f} / {gold.change_pct:+.2f}%</div>
          </div>
          <div class="ticker-meta">
            Updated {html.escape(generated_at)} · Range {format_number(gold.day_low)} / {format_number(gold.day_high)} ·
            Source <a href="{INVESTING_XAUUSD_URL}" target="_blank" rel="noopener noreferrer">Investing.com XAU/USD</a>
          </div>
        </div>
      </div>
      <div class="quick-decision-grid">
        {render_trade_compact(fundamental)}
        {render_trade_compact(technical)}
      </div>
      <div class="hero-summary-strip">
        <div class="status-cell">
          <div class="section-kicker">Bias</div>
          <div class="status-value {bias_class}">{html.escape(bias_label)}</div>
        </div>
        <div class="status-cell">
          <div class="section-kicker">Confidence</div>
          <div class="status-value">{analysis.confidence}/100</div>
          <div class="confidence-bar"><span></span></div>
        </div>
        <div class="status-cell">
          <div class="section-kicker">News Score</div>
          <div class="status-value small">{analysis.score:+d} · {html.escape(generated_at)}</div>
        </div>
        <div class="status-cell">
          <div class="section-kicker">Geo Score</div>
          <div class="status-value {geo_class}">
            {f"{geopolitical_analysis.score}/100" if geopolitical_analysis else "N/A"}
          </div>
        </div>
      </div>
      <div class="top-grid">
        <div class="trade-grid">
          {render_trade_card(fundamental)}
          {render_trade_card(technical)}
        </div>
        <aside class="executive-panel">
          <div class="section-kicker">Agent Chat</div>
          <div class="terminal-line">
            <span class="prompt">&gt;</span>
            <span class="terminal-tag">EXEC</span>
            <div class="terminal-text">{html.escape(executive_summary)}</div>
          </div>
          <div class="terminal-line">
            <span class="prompt">&gt;</span>
            <span class="terminal-tag">FUND</span>
            <div class="terminal-text">{html.escape(fundamental.summary)}</div>
          </div>
          <div class="terminal-line">
            <span class="prompt">&gt;</span>
            <span class="terminal-tag">TECH</span>
            <div class="terminal-text">{html.escape(technical.summary)}</div>
          </div>
          <div class="terminal-line">
            <span class="prompt">&gt;</span>
            <span class="terminal-tag">GEO</span>
            <div class="terminal-text">{html.escape(geopolitical_analysis.summary if geopolitical_analysis else "Lecture geopolitique indisponible.")}</div>
          </div>
          <div class="terminal-line">
            <span class="prompt">&gt;</span>
            <span class="terminal-tag">NOTE</span>
            <div class="terminal-text">Pas conseil financier personnalise.</div>
          </div>
        </aside>
      </div>
    </section>

    <section class="content-grid">
      <article class="panel metric-card span-4">
        <div class="section-kicker">Spot Price</div>
        <h2>XAU/USD Spot</h2>
        <div class="metric-value">{gold.price:.2f}</div>
        <div class="metric-delta {price_class}">{gold.change_pct:+.2f}% vs close</div>
        <div class="metric-footnote">
          Tendance courte {gold.period_change_pct:+.2f}%<br>
          Support {format_number(gold.support)} · Resistance {format_number(gold.resistance)}
        </div>
      </article>
      <article class="panel metric-card span-4">
        <div class="section-kicker">Dollar Index</div>
        <h2>DXY</h2>
        <div class="metric-value">{dxy.price:.2f}</div>
        <div class="metric-delta {dxy_class}">{dxy.change_pct:+.2f}% session</div>
        <div class="metric-footnote">
          Un DXY en baisse soutient souvent l'or.<br>
          Etat actuel {"favorable" if dxy.change_pct < 0 else "sous pression"}.
        </div>
      </article>
      <article class="panel metric-card span-4">
        <div class="section-kicker">US Yield</div>
        <h2>10Y US</h2>
        <div class="metric-value">{us10y.price:.2f}%</div>
        <div class="metric-delta {us10y_class}">{us10y.change_abs * 100:+.1f} bps</div>
        <div class="metric-footnote">
          Des rendements plus bas aident souvent l'or.<br>
          Variation courte {us10y.period_change_pct:+.2f}%.
        </div>
      </article>

      <article class="panel span-7">
        <div class="section-kicker">Instrument · Chart · Intraday</div>
        <h2>5m Candles + Live Price Line</h2>
        <div class="chart-wrap">{chart_svg}</div>
        <div class="metric-footnote" style="margin-top:8px;">
          Bougies 5 minutes proxy GC=F alignees sur le spot XAU/USD. Ligne ambre = prix spot en temps reel.
        </div>
        <div class="key-levels">
          <div class="level-chip"><strong>Support</strong><span>{format_number(gold.support)}</span></div>
          <div class="level-chip"><strong>Resistance</strong><span>{format_number(gold.resistance)}</span></div>
          <div class="level-chip"><strong>Last</strong><span>{format_number(gold.price)}</span></div>
        </div>
      </article>

      <article class="panel span-5">
        <div class="section-kicker">Fundamental Drivers</div>
        <h2>Macro Context</h2>
        {render_reasons_list(fundamental.reasons)}
      </article>

      <article class="panel span-12">
        <div class="section-kicker">Geo Politics / Sentiment / Flow</div>
        <h2>Risk-off / Banques centrales / Flux physiques / COT / ETF / VIX</h2>
        {render_geopolitical_panel(geopolitical_analysis)}
      </article>

      <article class="panel span-12">
        <div class="section-kicker">COT officiel CFTC</div>
        <h2>Positionnement Gold Futures COMEX</h2>
        {render_cftc_positioning_panel(cftc_positioning)}
      </article>

      <article class="panel span-12">
        <div class="section-kicker">Technical Matrix</div>
        <h2>EMA 20/50/100/200 · RSI7 · MACD 5/34/5 · Volume Proxy</h2>
        {technical_matrix}
      </article>

      <article class="panel span-12">
        <div class="section-kicker">Execution Scenarios</div>
        <h2>Scenario hausse · baisse · attente</h2>
        <div class="scenario-grid">
          <div class="scenario positive">
            <h3>Scenario hausse</h3>
            <p>{html.escape(bullish_case)}</p>
          </div>
          <div class="scenario negative">
            <h3>Scenario baisse</h3>
            <p>{html.escape(bearish_case)}</p>
          </div>
          <div class="scenario neutral">
            <h3>Scenario attente</h3>
            <p>{html.escape(wait_case)}</p>
          </div>
        </div>
      </article>

      {render_ai_summary(ai_analysis)}

      <section class="panel span-12">
        <div class="section-kicker">Disclaimer</div>
        <div class="footer-note">
          Ce dashboard fournit un cadre d'analyse intraday avec verdict BUY ou SELL, SL et TP.
          Il ne constitue pas un conseil financier personnalise.
        </div>
      </section>
    </section>
  </main>
{live_script}
</body>
</html>"""


def render_dashboard_clarity(
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
    chart_svg = candlestick_svg(gold.intraday_points or gold.points, gold.price)
    confidence_width = max(8, min(100, analysis.confidence))
    bullish_case, bearish_case, wait_case = build_scenarios(gold, dxy, us10y)
    generated_at = format_timestamp_for_humans(bundle.payload["generated_at"])

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
    global_recommendation = bundle.global_recommendation or build_global_recommendation(
        gold,
        analysis,
        fundamental,
        technical,
        geopolitical=geopolitical_analysis,
        cross_asset=cross_asset_analysis,
        event_mode=event_mode,
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
        global_recommendation=global_recommendation,
        technical_timeframes=technical_readings,
        real_yield=real_yield,
        official_macro_rates=official_macro_rates,
        cftc_positioning=cftc_positioning,
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
    technical_matrix = (
        render_technical_table(technical_readings)
        if technical_readings
        else '<div class="footer-note">Lecture technique indisponible.</div>'
    )
    regime_name = market_regime.name if market_regime is not None else "Normal Macro"
    regime_status = market_regime.status if market_regime is not None else "NORMAL"
    regime_alert = (
        "hormuz-oil-shock"
        if market_regime is not None and market_regime.name == "Hormuz / Oil Shock"
        else "ig-weekend"
        if weekend_gold is not None
        else "none"
    )
    regime_summary = market_regime.summary if market_regime is not None else "Pas de regime special confirme."
    banner_class = recommendation_css_class(global_recommendation.verdict)

    meta_refresh = "" if live_client else '  <meta http-equiv="refresh" content="60">\n'
    refresh_enabled = "true" if live_client else "false"
    live_script = f"""
  <script>
    (() => {{
      const app = document.getElementById("dashboard-app");
      const storageKey = "aureumFlux.activeTab";
      const defaultTab = "dashboard";
      const refreshEnabled = {refresh_enabled};
      let busy = false;

      function getRequestedTab() {{
        const hashTab = window.location.hash ? window.location.hash.replace("#", "") : "";
        const storedTab = window.localStorage.getItem(storageKey) || "";
        return hashTab || storedTab || defaultTab;
      }}

      function setActiveTab(tab, persist = true) {{
        const requestedTab = tab || defaultTab;
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
      --bg-2: #060e20;
      --panel: rgba(15, 23, 42, 0.76);
      --panel-alt: rgba(19, 27, 46, 0.9);
      --panel-bright: #222a3d;
      --text: #dae2fd;
      --soft: #9aa4b8;
      --muted: #2d3449;
      --line: #1e293b;
      --bull: #4edea3;
      --bear: #ffb4ab;
      --amber: #d4af37;
      --gold: #f2ca50;
      --blue: #8ab4ff;
    }}
    * {{
      box-sizing: border-box;
    }}
    html, body {{
      margin: 0;
      min-height: 100vh;
      background: var(--bg);
      color: var(--text);
      font-family: Inter, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
    }}
    body {{
      background:
        radial-gradient(circle at 18% 0%, rgba(212, 175, 55, 0.11), transparent 27%),
        radial-gradient(circle at 96% 12%, rgba(78, 222, 163, 0.08), transparent 22%),
        linear-gradient(180deg, #020617 0%, #071020 45%, #020617 100%);
    }}
    a {{
      color: var(--blue);
      text-decoration: none;
    }}
    a:hover {{
      text-decoration: underline;
    }}
    h1, h2, h3, p {{
      margin: 0;
    }}
    .page {{
      width: 100%;
      min-height: 100vh;
      margin: 0;
    }}
    .terminal-shell {{
      display: grid;
      grid-template-columns: 260px minmax(0, 1fr);
      min-height: 100vh;
    }}
    .side-rail {{
      position: sticky;
      top: 0;
      height: 100vh;
      padding: 22px 16px;
      border-right: 1px solid var(--line);
      background: rgba(2, 6, 23, 0.88);
      backdrop-filter: blur(18px);
    }}
    .brand {{
      color: var(--amber);
      font-size: 24px;
      font-weight: 900;
      line-height: 1;
      letter-spacing: -0.04em;
      text-transform: uppercase;
      text-shadow: 0 0 16px rgba(212, 175, 55, 0.35);
    }}
    .rail-card {{
      margin-top: 28px;
      padding: 14px;
      border: 1px solid rgba(153, 144, 124, 0.34);
      border-radius: 8px;
      background: rgba(19, 27, 46, 0.72);
    }}
    .rail-card strong {{
      display: block;
      color: var(--text);
      font-size: 13px;
      letter-spacing: 0.16em;
      text-transform: uppercase;
    }}
    .rail-card span {{
      display: block;
      margin-top: 6px;
      color: var(--soft);
      font-size: 13px;
    }}
    .rail-status {{
      margin-top: 12px;
      padding: 9px 10px;
      border: 1px solid rgba(78, 222, 163, 0.32);
      border-radius: 4px;
      color: var(--bull);
      font-family: "Space Grotesk", monospace;
      font-size: 11px;
      font-weight: 700;
      letter-spacing: 0.18em;
      text-transform: uppercase;
      background: rgba(78, 222, 163, 0.08);
    }}
    .rail-nav {{
      display: grid;
      gap: 6px;
      margin-top: 28px;
    }}
    .rail-link {{
      padding: 13px 14px;
      border-left: 3px solid transparent;
      border-radius: 0 5px 5px 0;
      color: var(--soft);
      font-family: "Space Grotesk", monospace;
      font-size: 12px;
      font-weight: 700;
      letter-spacing: 0.18em;
      text-transform: uppercase;
    }}
    .rail-link.active {{
      color: var(--amber);
      border-left-color: var(--amber);
      background: rgba(212, 175, 55, 0.08);
    }}
    .workspace {{
      min-width: 0;
      padding: 22px 24px 28px;
    }}
    .topbar {{
      display: flex;
      justify-content: space-between;
      align-items: center;
      gap: 16px;
      min-height: 58px;
      margin: -22px -24px 22px;
      padding: 0 24px;
      border-bottom: 1px solid var(--line);
      background: rgba(2, 6, 23, 0.72);
      backdrop-filter: blur(18px);
    }}
    .topbar-left {{
      display: flex;
      align-items: center;
      min-width: 0;
      gap: 18px;
    }}
    .topbar-brand {{
      color: var(--amber);
      font-family: "Space Grotesk", monospace;
      font-size: 18px;
      font-weight: 800;
      letter-spacing: 0;
      white-space: nowrap;
      text-shadow: 0 0 16px rgba(212, 175, 55, 0.32);
    }}
    .top-nav {{
      display: flex;
      align-items: center;
      gap: 4px;
      min-width: 0;
      overflow-x: auto;
      scrollbar-width: none;
    }}
    .top-nav::-webkit-scrollbar {{
      display: none;
    }}
    .top-nav a {{
      flex: 0 0 auto;
      min-height: 34px;
      padding: 10px 9px 8px;
      border-bottom: 2px solid transparent;
      color: var(--soft);
      font-family: "Space Grotesk", monospace;
      font-size: 11px;
      font-weight: 700;
      letter-spacing: 0.08em;
      text-transform: uppercase;
      text-decoration: none;
    }}
    .top-nav a:hover {{
      color: var(--text);
      text-decoration: none;
    }}
    .top-nav a.active {{
      color: var(--amber);
      border-bottom-color: var(--amber);
    }}
    .topbar-title {{
      color: var(--amber);
      font-family: "Space Grotesk", monospace;
      font-size: 12px;
      font-weight: 700;
      letter-spacing: 0.26em;
      text-transform: uppercase;
    }}
      .topbar-meta {{
        white-space: normal;
        line-height: 1.35;
      }}
      .terminal-header h1 {{
        font-size: 28px;
        line-height: 1.05;
      }}
      .terminal-header p {{
        max-width: 100%;
        overflow-wrap: anywhere;
      }}
      .view-tabs {{
        overflow-x: auto;
      }}
      .global-live-strip {{
        width: 100%;
      }}
      .live-cell strong,
      .state-card strong {{
        overflow-wrap: anywhere;
      }}
      color: var(--soft);
      font-family: "Space Grotesk", monospace;
      font-size: 11px;
      letter-spacing: 0.16em;
      text-transform: uppercase;
      white-space: nowrap;
    }}
    .terminal-header {{
      display: flex;
      justify-content: space-between;
      align-items: flex-end;
      gap: 16px;
      margin-bottom: 14px;
    }}
    .terminal-header h1 {{
      color: var(--text);
      font-size: clamp(28px, 3.6vw, 44px);
      font-weight: 800;
      letter-spacing: -0.03em;
    }}
    .terminal-header p {{
      margin-top: 5px;
      color: var(--soft);
      font-size: 13px;
    }}
    .sync-pill {{
      padding: 8px 11px;
      border: 1px solid rgba(78, 222, 163, 0.25);
      border-radius: 999px;
      color: var(--bull);
      background: rgba(78, 222, 163, 0.08);
      font-family: "Space Grotesk", monospace;
      font-size: 10px;
      font-weight: 700;
      letter-spacing: 0.18em;
      text-transform: uppercase;
    }}
    .hero-grid,
    .summary-grid,
    .digest-grid,
    .content-grid,
    .headline-grid,
    .metrics-grid,
    .trade-levels,
    .key-levels,
    .scenario-grid,
    .geo-grid,
    .geo-columns {{
      display: grid;
      gap: 14px;
    }}
    .hero-grid {{
      grid-template-columns: minmax(0, 1.25fr) minmax(320px, 1fr) minmax(320px, 1fr);
      margin-bottom: 14px;
    }}
    .summary-grid {{
      grid-template-columns: minmax(0, 1.25fr) minmax(340px, 0.9fr);
      margin-bottom: 14px;
    }}
    .digest-grid {{
      grid-template-columns: repeat(4, minmax(0, 1fr));
      margin-top: 14px;
    }}
    .content-grid {{
      grid-template-columns: repeat(12, minmax(0, 1fr));
    }}
    .headline-grid {{
      grid-template-columns: repeat(2, minmax(0, 1fr));
    }}
    .metrics-grid {{
      grid-template-columns: repeat(4, minmax(0, 1fr));
      margin-top: 14px;
    }}
    .trade-levels,
    .key-levels {{
      grid-template-columns: repeat(3, minmax(0, 1fr));
    }}
    .scenario-grid {{
      grid-template-columns: repeat(3, minmax(0, 1fr));
    }}
    .geo-grid {{
      grid-template-columns: repeat(4, minmax(0, 1fr));
    }}
    .geo-columns {{
      grid-template-columns: repeat(2, minmax(0, 1fr));
      margin-top: 14px;
    }}
    .panel,
    .trade-card,
    .summary-box,
    .digest-card,
    .headline-brief,
    .story-row,
    .metric-chip,
    .level-chip,
    .weekend-proxy,
    .scenario {{
      background: var(--panel);
      border: 1px solid var(--muted);
      border-radius: 10px;
    }}
    .panel,
    .trade-card {{
      padding: 18px 18px 16px;
    }}
    .span-5 {{ grid-column: span 5; }}
    .span-7 {{ grid-column: span 7; }}
    .span-12 {{ grid-column: span 12; }}
    .section-kicker {{
      color: var(--amber);
      font-size: 11px;
      letter-spacing: 0.12em;
      text-transform: uppercase;
      margin-bottom: 8px;
    }}
    .hero-price {{ background: var(--panel); }}
    .ticker-symbol {{
      color: var(--amber);
      font-size: 13px;
      letter-spacing: 0.12em;
      text-transform: uppercase;
    }}
    .ticker-row {{
      display: flex;
      flex-wrap: wrap;
      align-items: baseline;
      gap: 16px;
      margin-top: 8px;
    }}
    .ticker-price {{
      font-size: clamp(48px, 7vw, 78px);
      font-weight: 700;
      line-height: 0.95;
      letter-spacing: -0.05em;
      white-space: nowrap;
    }}
    .ticker-delta {{
      font-size: 24px;
      font-weight: 700;
    }}
    .ticker-price.bullish,
    .ticker-delta.bullish,
    .bullish,
    .headline-brief.bullish h3 {{
      color: var(--bull);
    }}
    .ticker-price.bearish,
    .ticker-delta.bearish,
    .bearish,
    .headline-brief.bearish h3 {{
      color: var(--bear);
    }}
    .ticker-price.neutral,
    .ticker-delta.neutral,
    .neutral,
    .headline-brief.neutral h3 {{
      color: var(--text);
    }}
    .ticker-cursor {{
      display: inline-block;
      width: 10px;
      height: 0.92em;
      margin-left: 8px;
      background: currentColor;
      vertical-align: text-bottom;
      animation: blink 1s steps(1) infinite;
    }}
    @keyframes blink {{
      50% {{ opacity: 0; }}
    }}
    .ticker-meta {{
      margin-top: 12px;
      color: var(--soft);
      font-size: 12px;
      line-height: 1.7;
    }}
    .metric-chip,
    .level-chip {{
      padding: 12px 14px;
    }}
    .metric-chip strong,
    .level-chip strong {{
      display: block;
      color: var(--amber);
      font-size: 11px;
      letter-spacing: 0.08em;
      text-transform: uppercase;
      margin-bottom: 6px;
    }}
    .metric-chip span,
    .level-chip span {{
      display: block;
      font-size: 24px;
      font-weight: 700;
      color: var(--text);
    }}
    .metric-chip small {{
      display: block;
      margin-top: 6px;
      color: var(--soft);
      font-size: 12px;
      line-height: 1.5;
    }}
    .trade-card {{
      border-top: 6px solid var(--muted);
      background: var(--panel);
    }}
    .trade-card.bullish {{ border-top-color: rgba(19, 138, 82, 0.35); }}
    .trade-card.bearish {{ border-top-color: rgba(201, 59, 59, 0.35); }}
    .trade-card-head {{
      display: flex;
      justify-content: space-between;
      gap: 14px;
      align-items: flex-start;
      margin-bottom: 12px;
    }}
    .trade-card h2 {{
      color: var(--text);
      font-size: 24px;
      margin-top: 2px;
    }}
    .trade-score {{
      color: var(--amber);
      font-size: 34px;
      font-weight: 700;
      white-space: nowrap;
    }}
    .trade-score small {{
      font-size: 15px;
      color: var(--soft);
    }}
    .trade-verdict {{
      display: inline-block;
      padding: 8px 12px;
      background: var(--panel-alt);
      font-size: 15px;
      font-weight: 700;
      letter-spacing: 0.08em;
      text-transform: uppercase;
      margin-bottom: 10px;
    }}
    .trade-summary,
    .story-text,
    .headline-brief p,
    .footer-note {{
      color: var(--text);
      font-size: 14px;
      line-height: 1.7;
    }}
    .trade-levels {{
      margin: 12px 0;
    }}
    .trade-levels div {{
      background: var(--panel-alt);
      border: 1px solid var(--line);
      border-radius: 14px;
      padding: 10px 12px;
    }}
    .trade-levels span {{
      display: block;
      color: var(--amber);
      font-size: 11px;
      text-transform: uppercase;
      letter-spacing: 0.08em;
    }}
    .trade-levels strong {{
      display: block;
      margin-top: 6px;
      font-size: 24px;
      color: var(--text);
    }}
    .trade-reasons,
    .reason-list {{
      margin: 0;
      padding-left: 18px;
      line-height: 1.65;
      font-size: 13px;
      color: var(--text);
    }}
    .trade-footer {{
      margin-top: 12px;
      padding-top: 12px;
      border-top: 1px solid var(--line);
      color: var(--soft);
      font-size: 12px;
      line-height: 1.6;
      display: grid;
      gap: 4px;
    }}
    .summary-box {{ padding: 18px; }}
    .summary-box h2,
    .panel h2 {{
      font-size: 24px;
      color: var(--text);
      margin-bottom: 8px;
    }}
    .summary-box .lead {{
      color: var(--text);
      font-size: 15px;
      line-height: 1.75;
      margin-bottom: 14px;
    }}
    .story-row {{
      padding: 13px 14px;
      margin-top: 10px;
      background: var(--panel-alt);
    }}
    .digest-card {{
      padding: 16px;
      background: var(--panel-alt);
    }}
    .digest-tag {{
      color: var(--amber);
      font-size: 11px;
      letter-spacing: 0.1em;
      text-transform: uppercase;
      margin-bottom: 8px;
    }}
    .digest-card h3 {{
      font-size: 15px;
      line-height: 1.55;
      margin-bottom: 8px;
      color: var(--text);
    }}
    .digest-card p {{
      color: var(--soft);
      font-size: 13px;
      line-height: 1.7;
      margin: 0;
    }}
    .story-label {{
      color: var(--amber);
      font-size: 11px;
      letter-spacing: 0.1em;
      text-transform: uppercase;
      margin-bottom: 6px;
    }}
    .decision-grid {{
      display: grid;
      gap: 12px;
      margin-top: 12px;
    }}
    .decision-item {{
      padding: 14px;
      background: var(--panel-alt);
      border: 1px solid var(--line);
      border-radius: 10px;
    }}
    .decision-item strong {{
      display: block;
      font-size: 15px;
      margin-bottom: 4px;
    }}
    .decision-item span {{
      color: var(--soft);
      font-size: 13px;
      line-height: 1.6;
    }}
    .agent-grid {{
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(240px, 1fr));
      gap: 10px;
      margin-top: 12px;
    }}
    .agent-card {{
      padding: 12px;
      border: 1px solid var(--line);
      border-top: 3px solid var(--line);
      border-radius: 6px;
      background: var(--panel-alt);
      min-width: 0;
    }}
    .agent-card.bullish {{ border-top-color: var(--bull); }}
    .agent-card.bearish {{ border-top-color: var(--bear); }}
    .agent-card.caution {{ border-top-color: var(--amber); }}
    .agent-card.neutral {{ border-top-color: var(--blue); }}
    .agent-card-top {{
      display: flex;
      justify-content: space-between;
      gap: 10px;
      align-items: flex-start;
      margin-bottom: 8px;
    }}
    .agent-card h3 {{
      font-size: 15px;
      line-height: 1.3;
      color: var(--text);
      margin: 0;
    }}
    .agent-score {{
      flex: 0 0 auto;
      color: var(--gold);
      font-family: "Space Grotesk", monospace;
      font-size: 20px;
      font-weight: 800;
    }}
    .agent-score small {{
      color: var(--soft);
      font-size: 11px;
      margin-left: 2px;
    }}
    .agent-badge {{
      display: inline-flex;
      margin-bottom: 8px;
      padding: 4px 7px;
      border: 1px solid var(--line);
      border-radius: 4px;
      font-family: "Space Grotesk", monospace;
      font-size: 11px;
      font-weight: 700;
      letter-spacing: 0.08em;
      text-transform: uppercase;
    }}
    .agent-badge.bullish {{ color: var(--bull); border-color: rgba(78, 222, 163, 0.35); }}
    .agent-badge.bearish {{ color: var(--bear); border-color: rgba(255, 180, 171, 0.35); }}
    .agent-badge.caution {{ color: var(--amber); border-color: rgba(212, 175, 55, 0.35); }}
    .agent-badge.neutral {{ color: var(--blue); border-color: rgba(138, 180, 255, 0.35); }}
    .agent-card p,
    .agent-muted {{
      color: var(--soft);
      font-size: 12px;
      line-height: 1.55;
      margin: 0;
    }}
    .agent-confidence {{
      margin-top: 8px;
      color: var(--text);
      font-size: 12px;
      font-weight: 700;
    }}
    .agent-evidence-list,
    .agent-risk-list {{
      margin: 8px 0 0;
      padding-left: 17px;
      color: var(--soft);
      font-size: 12px;
      line-height: 1.5;
    }}
    .agent-evidence-list strong,
    .agent-risk-list strong {{
      color: var(--text);
    }}
    .agent-evidence-list small {{
      display: block;
      color: var(--amber);
      font-size: 10px;
      margin-top: 2px;
    }}
    .confidence-bar {{
      height: 10px;
      margin-top: 10px;
      background: #eee4d7;
      border-radius: 999px;
      overflow: hidden;
    }}
    .confidence-bar span {{
      display: block;
      width: {confidence_width}%;
      height: 100%;
      background: linear-gradient(90deg, #e7b45e, #8a5b12);
    }}
    .chart-wrap {{
      margin-top: 12px;
      border: 1px solid var(--line);
      border-radius: 10px;
      overflow: hidden;
      background: #fffdf8;
    }}
    .chart-wrap svg {{
      display: block;
      width: 100%;
      height: auto;
    }}
    .headline-brief {{
      padding: 16px;
      border-left: 6px solid var(--line);
    }}
    .headline-brief.bullish {{ border-left-color: rgba(19, 138, 82, 0.35); }}
    .headline-brief.bearish {{ border-left-color: rgba(201, 59, 59, 0.35); }}
    .headline-brief.neutral {{ border-left-color: rgba(138, 91, 18, 0.30); }}
    .headline-brief-top {{
      display: flex;
      justify-content: space-between;
      gap: 12px;
      margin-bottom: 10px;
      color: var(--soft);
      font-size: 12px;
    }}
    .headline-brief h3 {{
      font-size: 17px;
      line-height: 1.5;
      margin-bottom: 10px;
    }}
    .headline-brief p + p {{
      margin-top: 8px;
    }}
    .headline-brief a {{
      display: inline-block;
      margin-top: 10px;
      font-size: 13px;
    }}
    .table-wrap {{
      overflow-x: auto;
      margin-top: 10px;
      border: 1px solid var(--line);
      border-radius: 10px;
      background: #fffdfa;
    }}
    .technical-table {{
      width: 100%;
      min-width: 860px;
      border-collapse: collapse;
    }}
    .technical-table th,
    .technical-table td {{
      padding: 12px 14px;
      border-bottom: 1px solid var(--line);
      text-align: left;
      font-size: 13px;
      color: var(--text);
    }}
    .technical-table th {{
      background: #f7efe2;
      color: var(--amber);
      font-size: 11px;
      letter-spacing: 0.1em;
      text-transform: uppercase;
    }}
    .geo-stat {{
      padding: 12px 14px;
      background: var(--panel-alt);
      border: 1px solid var(--line);
      border-radius: 10px;
    }}
    .geo-stat strong {{
      display: block;
      color: var(--amber);
      font-size: 11px;
      letter-spacing: 0.08em;
      text-transform: uppercase;
      margin-bottom: 6px;
    }}
    .geo-stat span {{
      display: block;
      color: var(--text);
      font-size: 16px;
      line-height: 1.5;
    }}
    .scenario {{
      padding: 16px;
    }}
    .scenario h3 {{
      font-size: 16px;
      margin-bottom: 8px;
    }}
    .scenario.positive h3 {{ color: var(--bull); }}
    .scenario.negative h3 {{ color: var(--bear); }}
    .scenario.neutral h3 {{ color: var(--amber); }}
    .ai-panel {{
      margin-top: 14px;
    }}
    .terminal-line {{
      display: grid;
      grid-template-columns: auto auto 1fr;
      gap: 10px;
      align-items: start;
      margin-top: 10px;
    }}
    .prompt {{
      color: var(--bull);
      font-weight: 700;
    }}
    .terminal-tag {{
      color: var(--amber);
      font-size: 12px;
      letter-spacing: 0.08em;
      text-transform: uppercase;
    }}
    .ai-copy {{
      color: var(--text);
      line-height: 1.7;
      font-size: 14px;
    }}
    .empty-state {{
      color: var(--soft);
      font-size: 14px;
      padding: 10px 0;
    }}
    @media (max-width: 1180px) {{
      .hero-grid,
      .summary-grid,
      .digest-grid,
      .headline-grid,
      .metrics-grid,
      .global-live-strip,
      .scenario-grid,
      .geo-grid,
      .geo-columns {{
        grid-template-columns: 1fr;
      }}
      .span-5,
      .span-7,
      .span-12 {{
        grid-column: span 12;
      }}
    }}
    @media (max-width: 900px) {{
      .page {{
        width: min(100%, calc(100% - 18px));
        margin: 9px auto 18px;
      }}
      .hero-grid,
      .trade-levels,
      .key-levels,
      .weekend-grid {{
        grid-template-columns: 1fr;
      }}
      .ticker-row {{
        flex-direction: column;
        align-items: flex-start;
      }}
    }}
  </style>
</head>
<body>
  <main class="page" id="dashboard-app">
    <div class="terminal-shell">
      <aside class="side-rail">
        <div class="brand">AUREUM<br>FLUX</div>
        <div class="rail-card">
          <strong>Terminal XAUUSD</strong>
          <span>Gold/USD intraday intelligence</span>
          <div class="rail-status">Live analysis</div>
        </div>
        <nav class="rail-nav" aria-label="Sections dashboard">
          <a class="rail-link active" href="#dashboard" data-tab-target="dashboard" aria-selected="true">Dashboard</a>
          <a class="rail-link" href="#market" data-tab-target="market" aria-selected="false">Market</a>
          <a class="rail-link" href="#decision" data-tab-target="decision" aria-selected="false">Decision</a>
          <a class="rail-link" href="#technical" data-tab-target="technical" aria-selected="false">Technical</a>
          <a class="rail-link" href="#macro" data-tab-target="macro" aria-selected="false">Macro</a>
          <a class="rail-link" href="#geopolitics" data-tab-target="geopolitics" aria-selected="false">Geopolitics & Flows</a>
          <a class="rail-link" href="#inspector" data-tab-target="inspector" aria-selected="false">Inspector</a>
          <a class="rail-link" href="#reports" data-tab-target="reports" aria-selected="false">Reports</a>
        </nav>
      </aside>
      <div class="workspace">
        <header class="topbar">
          <div class="topbar-left">
            <div class="topbar-brand">AUREUM FLUX</div>
            <nav class="top-nav" aria-label="Navigation principale">
              <a class="active" href="#dashboard" data-tab-target="dashboard" aria-selected="true">Dashboard</a>
              <a href="#market" data-tab-target="market" aria-selected="false">Market</a>
              <a href="#decision" data-tab-target="decision" aria-selected="false">Decision</a>
              <a href="#technical" data-tab-target="technical" aria-selected="false">Technical</a>
              <a href="#macro" data-tab-target="macro" aria-selected="false">Macro</a>
              <a href="#geopolitics" data-tab-target="geopolitics" aria-selected="false">Geopolitics</a>
              <a href="#inspector" data-tab-target="inspector" aria-selected="false">Inspector</a>
              <a href="#reports" data-tab-target="reports" aria-selected="false">Reports</a>
            </nav>
          </div>
          <div class="topbar-meta">System online | {html.escape(generated_at)}</div>
        </header>
        <section class="terminal-header">
          <div>
            <div class="section-kicker">Institutional analytics package</div>
            <h1>XAU/USD Market <br class="mobile-title-break">Dashboard</h1>
            <p>Scoring global, plan BUY/SELL, niveaux de risque et contexte marche live.</p>
          </div>
          <div class="sync-pill">Ready for export</div>
        </section>
    <section class="hero-grid anchor-target" id="market">
      <article class="panel hero-price">
        <div class="section-kicker">Tableau de bord intraday</div>
        <div class="ticker-symbol">XAU/USD spot | live</div>
        <div class="ticker-row">
          <div class="ticker-price {price_class}">{gold.price:.2f}<span class="ticker-cursor"></span></div>
          <div class="ticker-delta {price_class}">{gold.change_abs:+.2f} / {gold.change_pct:+.2f}%</div>
        </div>
        <div class="ticker-meta">
          Mis a jour {html.escape(generated_at)}<br>
          Source prix spot: <a href="{INVESTING_XAUUSD_URL}" target="_blank" rel="noopener noreferrer">Investing.com XAU/USD</a><br>
          Range du jour: {format_number(gold.day_low)} / {format_number(gold.day_high)}
        </div>
        {render_weekend_gold_proxy(weekend_gold, gold)}
        <div class="global-signal {recommendation_css_class(global_recommendation.verdict)}">
          <div class="global-signal-head">
            <div>
              <div class="section-kicker">Scoring global prioritaire</div>
              <h2>Position conseillee</h2>
            </div>
            <div class="global-score">{global_recommendation.score}<small>/100</small></div>
          </div>
          <div class="global-position">
            <strong class="{recommendation_css_class(global_recommendation.verdict)}">{html.escape(global_recommendation.verdict)}</strong>
            <span>SL {global_recommendation.stop_loss:.2f} | TP1 {global_recommendation.take_profit_1:.2f} | TP2 {global_recommendation.take_profit_2:.2f}</span>
          </div>
          <p class="global-summary">{html.escape(global_recommendation.summary)}</p>
          {render_trade_levels(global_recommendation)}
        </div>
        <div class="metrics-grid">
          <div class="metric-chip">
            <strong>Biais</strong>
            <span class="{price_class}">{format_bias_label(analysis.bias)}</span>
            <small>{heuristic_decision_sentence(analysis)}</small>
          </div>
          <div class="metric-chip">
            <strong>Confiance</strong>
            <span>{analysis.confidence}/100</span>
            <div class="confidence-bar"><span></span></div>
          </div>
          <div class="metric-chip">
            <strong>DXY</strong>
            <span class="{dxy_class}">{dxy.price:.2f}</span>
            <small>{dxy.change_pct:+.2f}% aujourd'hui</small>
          </div>
          <div class="metric-chip">
            <strong>10Y US</strong>
            <span class="{us10y_class}">{us10y.price:.2f}%</span>
            <small>{us10y.change_abs * 100:+.1f} bps aujourd'hui</small>
          </div>
          <div class="metric-chip">
            <strong>10Y reel FRED</strong>
            <span class="{real_yield_class}">{f'{real_yield.price:.2f}%' if real_yield else 'n/a'}</span>
            <small>{f'{real_yield.change_abs * 100:+.1f} bps' if real_yield else 'source indisponible'}</small>
          </div>
        </div>
      </article>

      {render_trade_card(fundamental)}
      {render_trade_card(technical)}
    </section>

    <section class="summary-grid anchor-target" id="scores">
      <article class="summary-box">
        <div class="section-kicker">Ce qui se passe reellement</div>
        <h2>Lecture du jour</h2>
        <p class="lead">{html.escape(executive_summary)}</p>
        {render_what_happens_now(story_lines)}
      </article>

      <article class="summary-box">
        <div class="section-kicker">Pourquoi le modele dit cela</div>
        <h2>Lecture simple</h2>
        <div class="decision-grid">
          <div class="decision-item">
            <strong class="{recommendation_css_class(fundamental.verdict)}">Fondamental: {html.escape(fundamental.verdict)} / {fundamental.score}/100</strong>
            <span>{html.escape(fundamental.summary)}</span>
          </div>
          <div class="decision-item">
            <strong class="{recommendation_css_class(technical.verdict)}">Technique: {html.escape(technical.verdict)} / {technical.score}/100</strong>
            <span>{html.escape(technical.summary)}</span>
          </div>
          <div class="decision-item">
            <strong class="{geo_class}">Geopolitique: {f'{geopolitical_analysis.score}/100' if geopolitical_analysis else 'indisponible'}</strong>
            <span>{html.escape(geopolitical_analysis.summary if geopolitical_analysis else 'Lecture geopolitique indisponible.')}</span>
          </div>
          <div class="decision-item">
            <strong>Ce que cela veut dire pour vous</strong>
            <span>Le mot BUY ou SELL ne veut pas dire “acheter maintenant a tout prix”. Il veut dire “dans le contexte actuel, le scenario dominant penche de ce cote, a condition que le prix respecte les niveaux SL et TP affiches”.</span>
          </div>
        </div>
      </article>
    </section>

    <section class="panel">
      <div class="section-kicker">Actualites expliquees</div>
      <h2>Pourquoi ces infos comptent aujourd'hui</h2>
      <p class="footer-note">Chaque titre ci-dessous est traduit en langage clair avec son impact probable sur l'or, au lieu d'etre affiche brut.</p>
      <div class="headline-grid" style="margin-top:14px;">
        {render_headline_reason_cards(bundle.news, limit=6)}
      </div>
    </section>

    <section class="content-grid" style="margin-top:14px;">
      <article class="panel span-7">
        <div class="section-kicker">Graphe intraday</div>
        <h2>5m chandelles + ligne de prix live</h2>
        <div class="chart-wrap">{chart_svg}</div>
        <div class="footer-note" style="margin-top:10px;">
          Bougies 5 minutes calculees sur le proxy GC=F puis alignees sur le spot XAU/USD.
          La ligne ambre montre le prix spot en temps reel.
        </div>
        <div class="key-levels" style="margin-top:14px;">
          <div class="level-chip"><strong>Support</strong><span>{format_number(gold.support)}</span></div>
          <div class="level-chip"><strong>Resistance</strong><span>{format_number(gold.resistance)}</span></div>
          <div class="level-chip"><strong>Dernier prix</strong><span>{format_number(gold.price)}</span></div>
        </div>
      </article>

      <article class="panel span-5">
        <div class="section-kicker">Contexte geo / sentiment / flux</div>
        <h2>Ce qui soutient ou freine l'or</h2>
        {render_geopolitical_panel(geopolitical_analysis)}
      </article>

      <article class="panel span-12">
        <div class="section-kicker">COT officiel CFTC</div>
        <h2>Positionnement Gold Futures COMEX</h2>
        {render_cftc_positioning_panel(cftc_positioning)}
      </article>

      <article class="panel span-12">
        <div class="section-kicker">Lecture technique detaillee</div>
        <h2>EMA 20/50/100/200 · RSI7 · MACD 5/34/5 · Volume</h2>
        {technical_matrix}
      </article>

      <article class="panel span-12">
        <div class="section-kicker">Scenarios d'execution</div>
        <h2>Comment lire le trade intraday</h2>
        <div class="scenario-grid" style="margin-top:12px;">
          <div class="scenario positive">
            <h3>Scenario hausse</h3>
            <p>{html.escape(bullish_case)}</p>
          </div>
          <div class="scenario negative">
            <h3>Scenario baisse</h3>
            <p>{html.escape(bearish_case)}</p>
          </div>
          <div class="scenario neutral">
            <h3>Scenario attente</h3>
            <p>{html.escape(wait_case)}</p>
          </div>
        </div>
      </article>

      {render_ai_summary(ai_analysis)}

      <section class="panel span-12">
        <div class="section-kicker">Avertissement</div>
        <div class="footer-note">
          Ce dashboard aide a lire le marche rapidement. Il ne constitue pas un conseil financier personnalise.
        </div>
      </section>
    </section>
  </main>
{live_script}
</body>
</html>"""


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
    chart_svg = candlestick_svg(gold.intraday_points or gold.points, gold.price)
    confidence_width = max(8, min(100, analysis.confidence))
    bullish_case, bearish_case, wait_case = build_scenarios(gold, dxy, us10y)
    generated_at = format_timestamp_for_humans(bundle.payload["generated_at"])

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
    global_recommendation = bundle.global_recommendation or build_global_recommendation(
        gold,
        analysis,
        fundamental,
        technical,
        geopolitical=geopolitical_analysis,
        cross_asset=cross_asset_analysis,
        event_mode=event_mode,
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
    technical_matrix = (
        render_technical_table(technical_readings)
        if technical_readings
        else '<div class="footer-note">Lecture technique indisponible.</div>'
    )
    regime_name = market_regime.name if market_regime is not None else "Normal Macro"
    regime_status = market_regime.status if market_regime is not None else "NORMAL"
    regime_alert = (
        "hormuz-oil-shock"
        if market_regime is not None and market_regime.name == "Hormuz / Oil Shock"
        else "ig-weekend"
        if weekend_gold is not None
        else "none"
    )
    regime_summary = market_regime.summary if market_regime is not None else "Pas de regime special confirme."
    banner_class = recommendation_css_class(global_recommendation.verdict)

    meta_refresh = "" if live_client else '  <meta http-equiv="refresh" content="60">\n'
    refresh_enabled = "true" if live_client else "false"
    live_script = f"""
  <script>
    (() => {{
      const app = document.getElementById("dashboard-app");
      const storageKey = "aureumFlux.activeTab";
      const defaultTab = "dashboard";
      const refreshEnabled = {refresh_enabled};
      let busy = false;

      function getRequestedTab() {{
        const hashTab = window.location.hash ? window.location.hash.replace("#", "") : "";
        const storedTab = window.localStorage.getItem(storageKey) || "";
        return hashTab || storedTab || defaultTab;
      }}

      function setActiveTab(tab, persist = true) {{
        const requestedTab = tab || defaultTab;
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
      --bg-2: #060e20;
      --panel: rgba(15, 23, 42, 0.76);
      --panel-alt: rgba(19, 27, 46, 0.9);
      --panel-bright: #222a3d;
      --text: #dae2fd;
      --soft: #9aa4b8;
      --muted: #2d3449;
      --line: #1e293b;
      --bull: #4edea3;
      --bear: #ffb4ab;
      --amber: #d4af37;
      --gold: #f2ca50;
      --blue: #8ab4ff;
    }}
    * {{
      box-sizing: border-box;
    }}
    html, body {{
      margin: 0;
      min-height: 100vh;
      color: var(--text);
      font-family: Inter, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
      background: var(--bg);
      scroll-behavior: smooth;
      overflow-x: hidden;
    }}
    body {{
      background:
        radial-gradient(circle at 18% 0%, rgba(212, 175, 55, 0.11), transparent 27%),
        radial-gradient(circle at 96% 12%, rgba(78, 222, 163, 0.08), transparent 22%),
        linear-gradient(180deg, #020617 0%, #071020 45%, #020617 100%);
    }}
    a {{
      color: var(--blue);
      text-decoration: none;
    }}
    a:hover {{
      text-decoration: underline;
    }}
    h1, h2, h3, p {{
      margin: 0;
    }}
    .page {{
      width: 100%;
      min-height: 100vh;
      margin: 0;
    }}
    .terminal-shell {{
      display: grid;
      grid-template-columns: 260px minmax(0, 1fr);
      min-height: 100vh;
    }}
    .side-rail {{
      position: sticky;
      top: 0;
      height: 100vh;
      padding: 22px 16px;
      border-right: 1px solid var(--line);
      background: rgba(2, 6, 23, 0.9);
      backdrop-filter: blur(18px);
    }}
    .brand {{
      color: var(--amber);
      font-size: 24px;
      font-weight: 900;
      line-height: 1;
      letter-spacing: 0;
      text-transform: uppercase;
      text-shadow: 0 0 16px rgba(212, 175, 55, 0.35);
    }}
    .rail-card {{
      margin-top: 28px;
      padding: 14px;
      border: 1px solid rgba(153, 144, 124, 0.34);
      border-radius: 8px;
      background: rgba(19, 27, 46, 0.72);
    }}
    .rail-card strong {{
      display: block;
      color: var(--text);
      font-size: 13px;
      letter-spacing: 0.16em;
      text-transform: uppercase;
    }}
    .rail-card span {{
      display: block;
      margin-top: 6px;
      color: var(--soft);
      font-size: 13px;
    }}
    .rail-status {{
      margin-top: 12px;
      padding: 9px 10px;
      border: 1px solid rgba(78, 222, 163, 0.32);
      border-radius: 4px;
      color: var(--bull);
      background: rgba(78, 222, 163, 0.08);
      font-family: "Space Grotesk", monospace;
      font-size: 11px;
      font-weight: 700;
      letter-spacing: 0.18em;
      text-transform: uppercase;
    }}
    .rail-nav {{
      display: grid;
      gap: 6px;
      margin-top: 28px;
    }}
    .rail-link {{
      display: block;
      padding: 13px 14px;
      border-left: 3px solid transparent;
      border-radius: 0 5px 5px 0;
      color: var(--soft);
      font-family: "Space Grotesk", monospace;
      font-size: 12px;
      font-weight: 700;
      letter-spacing: 0.18em;
      text-transform: uppercase;
      text-decoration: none;
      cursor: pointer;
    }}
    .rail-link:hover {{
      color: var(--text);
      background: rgba(255, 255, 255, 0.04);
      text-decoration: none;
    }}
    .rail-link.active {{
      color: var(--amber);
      border-left-color: var(--amber);
      background: rgba(212, 175, 55, 0.08);
    }}
    .view-tabs {{
      display: flex;
      flex-wrap: wrap;
      gap: 7px;
      margin: 0 0 14px;
      padding: 8px;
      border: 1px solid rgba(45, 52, 73, 0.78);
      border-radius: 8px;
      background: rgba(6, 14, 32, 0.68);
    }}
    .view-tab {{
      display: inline-flex;
      align-items: center;
      min-height: 34px;
      padding: 8px 10px;
      border: 1px solid transparent;
      border-radius: 5px;
      color: var(--soft);
      font-family: "Space Grotesk", monospace;
      font-size: 11px;
      font-weight: 700;
      letter-spacing: 0.12em;
      text-transform: uppercase;
      text-decoration: none;
    }}
    .view-tab:hover {{
      color: var(--text);
      background: rgba(255, 255, 255, 0.04);
      text-decoration: none;
    }}
    .view-tab.active {{
      color: var(--amber);
      border-color: rgba(212, 175, 55, 0.34);
      background: rgba(212, 175, 55, 0.1);
    }}
    .tab-view {{
      display: none;
    }}
    .tab-view.active {{
      display: block;
    }}
    .global-live-strip {{
      display: grid;
      grid-template-columns: minmax(210px, 1.05fr) repeat(4, minmax(130px, 0.62fr));
      gap: 8px;
      margin-bottom: 14px;
      padding: 10px;
      border: 1px solid rgba(212, 175, 55, 0.28);
      border-radius: 8px;
      background:
        linear-gradient(135deg, rgba(212, 175, 55, 0.1), transparent 42%),
        rgba(15, 23, 42, 0.82);
    }}
    .global-live-strip.bullish {{
      border-color: rgba(78, 222, 163, 0.26);
    }}
    .global-live-strip.bearish {{
      border-color: rgba(255, 180, 171, 0.3);
    }}
    .state-board {{
      display: grid;
      grid-template-columns: repeat(5, minmax(0, 1fr));
      gap: 8px;
      margin: 0 0 14px;
    }}
    .state-card {{
      min-width: 0;
      padding: 10px 11px;
      border: 1px solid rgba(45, 52, 73, 0.86);
      border-left: 4px solid var(--line);
      border-radius: 8px;
      background: rgba(15, 23, 42, 0.78);
    }}
    .state-card.bullish {{ border-left-color: var(--bull); }}
    .state-card.bearish {{ border-left-color: var(--bear); }}
    .state-card.caution {{ border-left-color: var(--amber); }}
    .state-card.neutral {{ border-left-color: var(--blue); }}
    .state-card small {{
      display: block;
      color: var(--soft);
      font-family: "Space Grotesk", monospace;
      font-size: 10px;
      font-weight: 700;
      letter-spacing: 0.12em;
      text-transform: uppercase;
    }}
    .state-card strong {{
      display: block;
      margin-top: 5px;
      color: var(--text);
      font-family: "Space Grotesk", monospace;
      font-size: 16px;
      line-height: 1.15;
      overflow-wrap: anywhere;
    }}
    .state-card span {{
      display: block;
      margin-top: 4px;
      color: var(--soft);
      font-size: 12px;
      line-height: 1.35;
      overflow-wrap: anywhere;
    }}
    .live-cell {{
      min-width: 0;
      padding: 9px 10px;
      border: 1px solid rgba(45, 52, 73, 0.7);
      border-radius: 6px;
      background: rgba(6, 14, 32, 0.5);
    }}
    .live-cell small {{
      display: block;
      color: var(--soft);
      font-family: "Space Grotesk", monospace;
      font-size: 10px;
      font-weight: 700;
      letter-spacing: 0.12em;
      text-transform: uppercase;
    }}
    .live-cell strong {{
      display: block;
      margin-top: 4px;
      color: var(--text);
      font-family: "Space Grotesk", monospace;
      font-size: 18px;
      line-height: 1.15;
    }}
    .live-cell span {{
      display: block;
      margin-top: 3px;
      color: var(--soft);
      font-size: 12px;
      line-height: 1.35;
      overflow-wrap: anywhere;
    }}
    .anchor-target {{
      scroll-margin-top: 72px;
    }}
    .workspace {{
      min-width: 0;
      max-width: 100%;
      overflow-x: hidden;
      padding: 22px 24px 28px;
    }}
    .topbar {{
      display: flex;
      justify-content: space-between;
      align-items: center;
      gap: 16px;
      min-height: 58px;
      margin: -22px -24px 22px;
      padding: 0 24px;
      border-bottom: 1px solid var(--line);
      background: rgba(2, 6, 23, 0.72);
      backdrop-filter: blur(18px);
    }}
    .topbar-left {{
      display: flex;
      align-items: center;
      min-width: 0;
      gap: 18px;
    }}
    .topbar-brand {{
      flex: 0 0 auto;
      color: var(--amber);
      font-family: "Space Grotesk", monospace;
      font-size: 18px;
      font-weight: 800;
      letter-spacing: 0;
      white-space: nowrap;
      text-shadow: 0 0 16px rgba(212, 175, 55, 0.32);
    }}
    .top-nav {{
      display: flex;
      align-items: center;
      gap: 4px;
      min-width: 0;
      overflow-x: auto;
      scrollbar-width: none;
    }}
    .top-nav::-webkit-scrollbar {{
      display: none;
    }}
    .top-nav a {{
      flex: 0 0 auto;
      min-height: 34px;
      padding: 10px 9px 8px;
      border-bottom: 2px solid transparent;
      color: var(--soft);
      font-family: "Space Grotesk", monospace;
      font-size: 11px;
      font-weight: 700;
      letter-spacing: 0.08em;
      text-transform: uppercase;
      text-decoration: none;
    }}
    .top-nav a:hover {{
      color: var(--text);
      text-decoration: none;
    }}
    .top-nav a.active {{
      color: var(--amber);
      border-bottom-color: var(--amber);
    }}
    .topbar-title {{
      color: var(--amber);
      font-family: "Space Grotesk", monospace;
      font-size: 12px;
      font-weight: 700;
      letter-spacing: 0.26em;
      text-transform: uppercase;
    }}
    .topbar-meta {{
      color: var(--soft);
      font-family: "Space Grotesk", monospace;
      font-size: 11px;
      letter-spacing: 0.16em;
      text-transform: uppercase;
    }}
    .terminal-header {{
      display: flex;
      justify-content: space-between;
      align-items: flex-end;
      gap: 16px;
      margin-bottom: 14px;
    }}
    .terminal-header > div {{
      min-width: 0;
      max-width: 100%;
    }}
    .terminal-header h1 {{
      color: var(--text);
      font-size: clamp(28px, 3.6vw, 44px);
      font-weight: 800;
      letter-spacing: 0;
      overflow-wrap: anywhere;
      word-break: break-word;
    }}
    .mobile-title-break {{
      display: none;
    }}
    .terminal-header p {{
      margin-top: 5px;
      color: var(--soft);
      font-size: 13px;
    }}
    .sync-pill {{
      padding: 8px 11px;
      border: 1px solid rgba(78, 222, 163, 0.25);
      border-radius: 999px;
      color: var(--bull);
      background: rgba(78, 222, 163, 0.08);
      font-family: "Space Grotesk", monospace;
      font-size: 10px;
      font-weight: 700;
      letter-spacing: 0.18em;
      text-transform: uppercase;
    }}
    .hero-grid,
    .summary-grid,
    .digest-grid,
    .content-grid,
    .headline-grid,
    .metrics-grid,
    .trade-levels,
    .key-levels,
    .scenario-grid,
    .geo-grid,
    .geo-columns {{
      display: grid;
      gap: 10px;
      min-width: 0;
    }}
    .hero-grid {{
      grid-template-columns: minmax(520px, 1.55fr) minmax(280px, 0.72fr) minmax(280px, 0.72fr);
      margin-bottom: 12px;
    }}
    .summary-grid {{
      grid-template-columns: minmax(0, 1.38fr) minmax(330px, 0.82fr);
      margin-bottom: 10px;
    }}
    .digest-grid {{
      grid-template-columns: repeat(auto-fit, minmax(260px, 1fr));
      margin-top: 10px;
    }}
    .content-grid {{
      grid-template-columns: repeat(12, minmax(0, 1fr));
      margin-top: 10px;
    }}
    .headline-grid {{
      grid-template-columns: repeat(auto-fit, minmax(330px, 1fr));
      margin-top: 10px;
    }}
    .metrics-grid {{
      grid-template-columns: repeat(auto-fit, minmax(150px, 1fr));
      margin-top: 10px;
    }}
    .trade-levels,
    .key-levels {{
      grid-template-columns: repeat(3, minmax(0, 1fr));
    }}
    .scenario-grid {{
      grid-template-columns: repeat(3, minmax(0, 1fr));
    }}
    .geo-grid {{
      grid-template-columns: repeat(auto-fit, minmax(145px, 1fr));
    }}
    .geo-columns {{
      grid-template-columns: repeat(2, minmax(0, 1fr));
      margin-top: 10px;
    }}
    .panel,
    .trade-card,
    .summary-box,
    .digest-card,
    .headline-brief,
    .story-row,
    .metric-chip,
    .level-chip,
    .scenario {{
      background: var(--panel);
      border: 1px solid rgba(45, 52, 73, 0.88);
      border-radius: 8px;
      box-shadow: inset 0 1px 0 rgba(255, 255, 255, 0.025), 0 18px 60px rgba(0, 0, 0, 0.16);
      backdrop-filter: blur(18px);
    }}
    .panel,
    .trade-card,
    .summary-box {{
      padding: 14px;
      min-width: 0;
    }}
    .digest-card {{
      padding: 12px;
      background: var(--panel-alt);
    }}
    .span-5 {{ grid-column: span 5; }}
    .span-7 {{ grid-column: span 7; }}
    .span-12 {{ grid-column: span 12; }}
    .section-kicker {{
      color: var(--amber);
      font-family: "Space Grotesk", monospace;
      font-size: 11px;
      font-weight: 700;
      letter-spacing: 0.2em;
      text-transform: uppercase;
      margin-bottom: 6px;
    }}
    .hero-price {{
      background: linear-gradient(135deg, rgba(15, 23, 42, 0.92), rgba(6, 14, 32, 0.9));
      border-left: 5px solid var(--amber);
    }}
    .ticker-symbol {{
      color: var(--amber);
      font-size: 13px;
      letter-spacing: 0.12em;
      text-transform: uppercase;
    }}
    .ticker-row {{
      display: flex;
      flex-wrap: wrap;
      align-items: baseline;
      gap: 12px;
      margin-top: 6px;
    }}
    .ticker-price {{
      font-size: clamp(46px, 6vw, 74px);
      font-family: "Space Grotesk", monospace;
      font-weight: 700;
      line-height: 0.95;
      letter-spacing: 0;
      white-space: nowrap;
    }}
    .ticker-delta {{
      font-family: "Space Grotesk", monospace;
      font-size: 22px;
      font-weight: 700;
    }}
    .ticker-price.bullish,
    .ticker-delta.bullish,
    .bullish,
    .headline-brief.bullish h3 {{
      color: var(--bull);
    }}
    .ticker-price.bearish,
    .ticker-delta.bearish,
    .bearish,
    .headline-brief.bearish h3 {{
      color: var(--bear);
    }}
    .ticker-price.neutral,
    .ticker-delta.neutral,
    .neutral,
    .headline-brief.neutral h3 {{
      color: var(--text);
    }}
    .ticker-cursor {{
      display: inline-block;
      width: 10px;
      height: 0.92em;
      margin-left: 8px;
      background: currentColor;
      vertical-align: text-bottom;
      animation: blink 1s steps(1) infinite;
    }}
    @keyframes blink {{
      50% {{ opacity: 0; }}
    }}
    .ticker-meta {{
      margin-top: 10px;
      color: var(--soft);
      font-size: 12px;
      line-height: 1.55;
    }}
    .weekend-proxy {{
      margin-top: 12px;
      padding: 12px;
      border-left: 5px solid rgba(212, 175, 55, 0.78);
      background:
        linear-gradient(135deg, rgba(212, 175, 55, 0.12), transparent 46%),
        rgba(19, 27, 46, 0.84);
    }}
    .weekend-proxy-head {{
      display: flex;
      justify-content: space-between;
      gap: 12px;
      align-items: flex-start;
      margin-bottom: 10px;
    }}
    .weekend-proxy-head strong {{
      display: block;
      color: var(--text);
      font-family: "Space Grotesk", monospace;
      font-size: 30px;
      line-height: 1;
    }}
    .weekend-proxy-head span {{
      font-family: "Space Grotesk", monospace;
      font-size: 14px;
      font-weight: 700;
      white-space: nowrap;
    }}
    .weekend-grid {{
      display: grid;
      grid-template-columns: repeat(4, minmax(0, 1fr));
      gap: 8px;
    }}
    .weekend-grid div {{
      min-width: 0;
      padding: 8px;
      border: 1px solid rgba(45, 52, 73, 0.74);
      border-radius: 6px;
      background: rgba(6, 14, 32, 0.48);
    }}
    .weekend-grid small {{
      display: block;
      color: var(--amber);
      font-size: 10px;
      font-weight: 700;
      letter-spacing: 0.12em;
      text-transform: uppercase;
    }}
    .weekend-grid b {{
      display: block;
      margin-top: 3px;
      color: var(--text);
      font-family: "Space Grotesk", monospace;
      font-size: 17px;
    }}
    .weekend-note {{
      margin-top: 9px;
      color: var(--soft);
      font-size: 12px;
      line-height: 1.45;
    }}
    .global-signal {{
      margin-top: 14px;
      padding: 14px;
      border: 1px solid rgba(212, 175, 55, 0.26);
      border-left: 5px solid var(--muted);
      border-radius: 8px;
      background:
        linear-gradient(135deg, rgba(212, 175, 55, 0.09), transparent 44%),
        rgba(19, 27, 46, 0.92);
    }}
    .global-signal.bullish {{
      border-left-color: rgba(78, 222, 163, 0.9);
    }}
    .global-signal.bearish {{
      border-left-color: rgba(255, 180, 171, 0.9);
    }}
    .global-signal-head {{
      display: flex;
      justify-content: space-between;
      align-items: flex-start;
      gap: 12px;
      margin-bottom: 10px;
    }}
    .global-signal h2 {{
      font-size: 18px;
      margin-top: 3px;
    }}
    .global-position {{
      display: flex;
      flex-wrap: wrap;
      align-items: baseline;
      gap: 10px;
    }}
    .global-position strong {{
      font-family: "Space Grotesk", monospace;
      font-size: 42px;
      line-height: 1;
      letter-spacing: 0.02em;
    }}
    .global-position span {{
      color: var(--soft);
      font-size: 13px;
      line-height: 1.45;
    }}
    .global-score {{
      color: var(--amber);
      font-family: "Space Grotesk", monospace;
      font-size: 36px;
      font-weight: 700;
      white-space: nowrap;
      text-shadow: 0 0 16px rgba(212, 175, 55, 0.34);
    }}
    .global-score small {{
      color: var(--soft);
      font-size: 15px;
    }}
    .global-summary {{
      color: var(--text);
      font-size: 13px;
      line-height: 1.55;
      margin-top: 8px;
    }}
    .metric-chip,
    .level-chip {{
      padding: 10px 11px;
    }}
    .metric-chip strong,
    .level-chip strong {{
      display: block;
      color: var(--amber);
      font-size: 11px;
      letter-spacing: 0.08em;
      text-transform: uppercase;
      margin-bottom: 5px;
    }}
    .metric-chip span,
    .level-chip span {{
      display: block;
      font-size: 20px;
      font-weight: 700;
      color: var(--text);
      font-family: "Space Grotesk", monospace;
    }}
    .metric-chip small {{
      display: block;
      margin-top: 5px;
      color: var(--soft);
      font-size: 12px;
      line-height: 1.45;
    }}
    .trade-card {{
      border-left: 5px solid var(--muted);
      background: linear-gradient(180deg, rgba(15, 23, 42, 0.92), rgba(19, 27, 46, 0.88));
    }}
    .trade-card.bullish {{ border-left-color: rgba(78, 222, 163, 0.75); }}
    .trade-card.bearish {{ border-left-color: rgba(255, 180, 171, 0.75); }}
    .trade-card-head {{
      display: flex;
      justify-content: space-between;
      gap: 10px;
      align-items: flex-start;
      margin-bottom: 8px;
    }}
    .trade-card h2 {{
      color: var(--text);
      font-size: 19px;
      margin-top: 2px;
    }}
    .trade-score {{
      color: var(--amber);
      font-family: "Space Grotesk", monospace;
      font-size: 28px;
      font-weight: 700;
      white-space: nowrap;
    }}
    .trade-score small {{
      font-size: 15px;
      color: var(--soft);
    }}
    .trade-verdict {{
      display: inline-block;
      padding: 6px 10px;
      background: var(--panel-alt);
      border: 1px solid var(--line);
      border-radius: 4px;
      font-family: "Space Grotesk", monospace;
      font-size: 14px;
      font-weight: 700;
      letter-spacing: 0.08em;
      text-transform: uppercase;
      margin-bottom: 8px;
    }}
    .tag-row {{
      display: flex;
      flex-wrap: wrap;
      gap: 6px;
      margin: 0 0 9px;
    }}
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
      font-weight: 700;
      letter-spacing: 0.08em;
      text-transform: uppercase;
      overflow-wrap: anywhere;
    }}
    .source-tag.bullish {{ color: var(--bull); border-color: rgba(78, 222, 163, 0.34); }}
    .source-tag.bearish {{ color: var(--bear); border-color: rgba(255, 180, 171, 0.34); }}
    .source-tag.caution {{ color: var(--amber); border-color: rgba(212, 175, 55, 0.34); }}
    .source-tag.neutral {{ color: var(--blue); border-color: rgba(138, 180, 255, 0.34); }}
    .source-tag.OK {{ color: var(--bull); border-color: rgba(78, 222, 163, 0.34); }}
    .trade-summary,
    .story-text,
    .headline-brief p,
    .footer-note {{
      color: var(--text);
      font-size: 13px;
      line-height: 1.55;
    }}
    .trade-levels {{
      margin: 9px 0;
    }}
    .trade-levels div {{
      background: var(--panel-alt);
      border: 1px solid var(--line);
      border-radius: 4px;
      padding: 8px 10px;
    }}
    .trade-levels span {{
      display: block;
      color: var(--amber);
      font-size: 11px;
      text-transform: uppercase;
      letter-spacing: 0.08em;
    }}
    .trade-levels strong {{
      display: block;
      margin-top: 4px;
      font-size: 18px;
      font-family: "Space Grotesk", monospace;
      color: var(--text);
    }}
    .trade-reasons,
    .reason-list {{
      margin: 0;
      padding-left: 18px;
      line-height: 1.5;
      font-size: 12px;
      color: var(--text);
    }}
    .trade-footer {{
      margin-top: 9px;
      padding-top: 9px;
      border-top: 1px solid var(--line);
      color: var(--soft);
      font-size: 12px;
      line-height: 1.45;
      display: grid;
      gap: 4px;
    }}
    .summary-box h2,
    .panel h2 {{
      font-size: 21px;
      color: var(--text);
      margin-bottom: 6px;
    }}
    .summary-box .lead {{
      color: var(--text);
      font-size: 14px;
      line-height: 1.6;
      margin-bottom: 10px;
    }}
    .story-row {{
      padding: 10px 11px;
      margin-top: 8px;
      background: var(--panel-alt);
    }}
    .digest-tag {{
      color: var(--amber);
      font-size: 11px;
      letter-spacing: 0.1em;
      text-transform: uppercase;
      margin-bottom: 8px;
    }}
    .digest-card h3 {{
      font-size: 14px;
      line-height: 1.45;
      margin-bottom: 6px;
      color: var(--text);
    }}
    .digest-card p {{
      color: var(--soft);
      font-size: 12px;
      line-height: 1.55;
      margin: 0;
    }}
    .story-label {{
      color: var(--amber);
      font-size: 11px;
      letter-spacing: 0.1em;
      text-transform: uppercase;
      margin-bottom: 6px;
    }}
    .decision-grid {{
      display: grid;
      gap: 8px;
      margin-top: 8px;
    }}
    .decision-item {{
      padding: 10px;
      background: var(--panel-alt);
      border: 1px solid var(--line);
      border-radius: 4px;
    }}
    .decision-item strong {{
      display: block;
      font-size: 15px;
      margin-bottom: 4px;
    }}
    .decision-item span {{
      color: var(--soft);
      font-size: 13px;
      line-height: 1.6;
    }}
    .agent-grid {{
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(240px, 1fr));
      gap: 10px;
      margin-top: 12px;
    }}
    .agent-card {{
      padding: 12px;
      border: 1px solid var(--line);
      border-top: 3px solid var(--line);
      border-radius: 6px;
      background: var(--panel-alt);
      min-width: 0;
    }}
    .agent-card.bullish {{ border-top-color: var(--bull); }}
    .agent-card.bearish {{ border-top-color: var(--bear); }}
    .agent-card.caution {{ border-top-color: var(--amber); }}
    .agent-card.neutral {{ border-top-color: var(--blue); }}
    .agent-card-top {{
      display: flex;
      justify-content: space-between;
      gap: 10px;
      align-items: flex-start;
      margin-bottom: 8px;
    }}
    .agent-card h3 {{
      font-size: 15px;
      line-height: 1.3;
      color: var(--text);
      margin: 0;
    }}
    .agent-score {{
      flex: 0 0 auto;
      color: var(--gold);
      font-family: "Space Grotesk", monospace;
      font-size: 20px;
      font-weight: 800;
    }}
    .agent-score small {{
      color: var(--soft);
      font-size: 11px;
      margin-left: 2px;
    }}
    .agent-badge {{
      display: inline-flex;
      margin-bottom: 8px;
      padding: 4px 7px;
      border: 1px solid var(--line);
      border-radius: 4px;
      font-family: "Space Grotesk", monospace;
      font-size: 11px;
      font-weight: 700;
      letter-spacing: 0.08em;
      text-transform: uppercase;
    }}
    .agent-badge.bullish {{ color: var(--bull); border-color: rgba(78, 222, 163, 0.35); }}
    .agent-badge.bearish {{ color: var(--bear); border-color: rgba(255, 180, 171, 0.35); }}
    .agent-badge.caution {{ color: var(--amber); border-color: rgba(212, 175, 55, 0.35); }}
    .agent-badge.neutral {{ color: var(--blue); border-color: rgba(138, 180, 255, 0.35); }}
    .agent-card p,
    .agent-muted {{
      color: var(--soft);
      font-size: 12px;
      line-height: 1.55;
      margin: 0;
    }}
    .agent-confidence {{
      margin-top: 8px;
      color: var(--text);
      font-size: 12px;
      font-weight: 700;
    }}
    .agent-evidence-list,
    .agent-risk-list {{
      margin: 8px 0 0;
      padding-left: 17px;
      color: var(--soft);
      font-size: 12px;
      line-height: 1.5;
    }}
    .agent-evidence-list strong,
    .agent-risk-list strong {{
      color: var(--text);
    }}
    .agent-evidence-list small {{
      display: block;
      color: var(--amber);
      font-size: 10px;
      margin-top: 2px;
    }}
    .confidence-bar {{
      height: 10px;
      margin-top: 10px;
      background: #172033;
      border-radius: 999px;
      overflow: hidden;
    }}
    .confidence-bar span {{
      display: block;
      width: {confidence_width}%;
      height: 100%;
      background: linear-gradient(90deg, var(--amber), var(--bull));
      box-shadow: 0 0 14px rgba(78, 222, 163, 0.26);
    }}
    .chart-wrap {{
      margin-top: 10px;
      border: 1px solid var(--line);
      border-radius: 6px;
      overflow: hidden;
      background: #060e20;
    }}
    .chart-wrap svg {{
      display: block;
      width: 100%;
      height: auto;
    }}
    .headline-brief {{
      padding: 12px;
      border-left: 5px solid var(--line);
    }}
    .headline-brief.bullish {{ border-left-color: rgba(0, 208, 132, 0.55); }}
    .headline-brief.bearish {{ border-left-color: rgba(255, 77, 109, 0.55); }}
    .headline-brief.neutral {{ border-left-color: rgba(243, 179, 92, 0.45); }}
    .headline-brief-top {{
      display: flex;
      justify-content: space-between;
      gap: 10px;
      margin-bottom: 8px;
      color: var(--soft);
      font-size: 12px;
    }}
    .headline-brief h3 {{
      font-size: 15px;
      line-height: 1.4;
      margin-bottom: 8px;
    }}
    .headline-brief p + p {{
      margin-top: 8px;
    }}
    .headline-brief a {{
      display: inline-block;
      margin-top: 10px;
      font-size: 13px;
    }}
    .table-wrap {{
      overflow-x: auto;
      margin-top: 10px;
      border: 1px solid var(--line);
      border-radius: 5px;
      background: var(--panel-alt);
    }}
    .technical-table {{
      width: 100%;
      min-width: 860px;
      border-collapse: collapse;
    }}
    .technical-table th,
    .technical-table td {{
      padding: 9px 10px;
      border-bottom: 1px solid var(--line);
      text-align: left;
      font-size: 12px;
      color: var(--text);
    }}
    .technical-table th {{
      background: #0f172a;
      color: var(--amber);
      font-family: "Space Grotesk", monospace;
      font-size: 11px;
      letter-spacing: 0.1em;
      text-transform: uppercase;
    }}
    .technical-table small {{
      color: var(--soft);
      font-size: 11px;
    }}
    .geo-stat {{
      padding: 10px 11px;
      background: var(--panel-alt);
      border: 1px solid var(--line);
      border-radius: 5px;
    }}
    .geo-stat strong {{
      display: block;
      color: var(--amber);
      font-size: 11px;
      letter-spacing: 0.08em;
      text-transform: uppercase;
      margin-bottom: 6px;
    }}
    .geo-stat span {{
      display: block;
      color: var(--text);
      font-size: 13px;
      line-height: 1.45;
    }}
    .geo-stat small {{
      display: block;
      margin-top: 4px;
      color: var(--soft);
      font-size: 11px;
      line-height: 1.35;
    }}
    .scenario {{
      padding: 11px;
    }}
    .scenario h3 {{
      font-size: 14px;
      margin-bottom: 6px;
    }}
    .scenario.positive h3 {{ color: var(--bull); }}
    .scenario.negative h3 {{ color: var(--bear); }}
    .scenario.neutral h3 {{ color: var(--amber); }}
    .ai-panel {{
      margin-top: 10px;
    }}
    .terminal-line {{
      display: grid;
      grid-template-columns: auto auto 1fr;
      gap: 10px;
      align-items: start;
      margin-top: 10px;
    }}
    .prompt {{
      color: var(--bull);
      font-weight: 700;
    }}
    .terminal-tag {{
      color: var(--amber);
      font-size: 12px;
      letter-spacing: 0.08em;
      text-transform: uppercase;
    }}
    .ai-copy {{
      color: var(--text);
      line-height: 1.55;
      font-size: 13px;
    }}
    .scenario-stack {{
      grid-template-columns: 1fr;
      gap: 8px;
    }}
    .module-block {{
      margin-top: 10px;
    }}
    .empty-state {{
      color: var(--soft);
      font-size: 14px;
      padding: 10px 0;
    }}
    @media (max-width: 1180px) {{
      .terminal-shell {{
        grid-template-columns: 1fr;
      }}
      .side-rail {{
        display: none;
      }}
      .hero-grid,
      .summary-grid,
      .digest-grid,
      .headline-grid,
      .metrics-grid,
      .global-live-strip,
      .state-board,
      .scenario-grid,
      .geo-grid,
      .geo-columns {{
        grid-template-columns: 1fr;
      }}
      .span-5,
      .span-7,
      .span-12 {{
        grid-column: span 12;
      }}
    }}
    @media (max-width: 900px) {{
      .page {{
        width: 100%;
        margin: 0;
      }}
      .workspace {{
        padding: 14px 10px 18px;
      }}
      .topbar {{
        margin: -14px -10px 14px;
        padding: 0 10px;
        align-items: flex-start;
        flex-direction: column;
        gap: 6px;
        padding-top: 10px;
        padding-bottom: 10px;
      }}
      .topbar-left {{
        width: 100%;
        align-items: flex-start;
        flex-direction: column;
        gap: 6px;
      }}
      .top-nav {{
        width: 100%;
      }}
      .topbar-meta {{
        white-space: normal;
        line-height: 1.35;
      }}
      .terminal-header {{
        align-items: flex-start;
        flex-direction: column;
        width: 100%;
        max-width: 100%;
      }}
      .terminal-header > div {{
        width: 100%;
      }}
      .terminal-header h1 {{
        font-size: 28px;
        line-height: 1.05;
        max-width: 22rem;
        white-space: normal;
      }}
      .terminal-header p {{
        max-width: 22rem;
        overflow-wrap: anywhere;
      }}
      .mobile-title-break {{
        display: block;
      }}
      .view-tabs {{
        overflow-x: auto;
      }}
      .global-live-strip {{
        width: 100%;
      }}
      .live-cell strong,
      .state-card strong {{
        overflow-wrap: anywhere;
      }}
      .hero-grid,
      .trade-levels,
      .key-levels {{
        grid-template-columns: 1fr;
      }}
      .ticker-row {{
        flex-direction: column;
        align-items: flex-start;
      }}
    }}
  </style>
</head>
<body>
  <main class="page" id="dashboard-app">
    <div class="terminal-shell">
      <aside class="side-rail">
        <div class="brand">AUREUM<br>FLUX</div>
        <div class="rail-card">
          <strong>Terminal XAUUSD</strong>
          <span>Gold/USD intraday intelligence</span>
          <div class="rail-status">Live analysis</div>
        </div>
        <nav class="rail-nav" aria-label="Sections dashboard">
          <a class="rail-link active" href="#dashboard" data-tab-target="dashboard" aria-selected="true">Dashboard</a>
          <a class="rail-link" href="#market" data-tab-target="market" aria-selected="false">Market</a>
          <a class="rail-link" href="#decision" data-tab-target="decision" aria-selected="false">Decision</a>
          <a class="rail-link" href="#technical" data-tab-target="technical" aria-selected="false">Technical</a>
          <a class="rail-link" href="#macro" data-tab-target="macro" aria-selected="false">Macro</a>
          <a class="rail-link" href="#geopolitics" data-tab-target="geopolitics" aria-selected="false">Geopolitics & Flows</a>
          <a class="rail-link" href="#inspector" data-tab-target="inspector" aria-selected="false">Inspector</a>
          <a class="rail-link" href="#reports" data-tab-target="reports" aria-selected="false">Reports</a>
        </nav>
      </aside>
      <div class="workspace">
        <header class="topbar">
          <div class="topbar-left">
            <div class="topbar-brand">AUREUM FLUX</div>
            <nav class="top-nav" aria-label="Navigation principale">
              <a class="active" href="#dashboard" data-tab-target="dashboard" aria-selected="true">Dashboard</a>
              <a href="#market" data-tab-target="market" aria-selected="false">Market</a>
              <a href="#decision" data-tab-target="decision" aria-selected="false">Decision</a>
              <a href="#technical" data-tab-target="technical" aria-selected="false">Technical</a>
              <a href="#macro" data-tab-target="macro" aria-selected="false">Macro</a>
              <a href="#geopolitics" data-tab-target="geopolitics" aria-selected="false">Geopolitics</a>
              <a href="#inspector" data-tab-target="inspector" aria-selected="false">Inspector</a>
              <a href="#reports" data-tab-target="reports" aria-selected="false">Reports</a>
            </nav>
          </div>
          <div class="topbar-meta">System online | {html.escape(generated_at)}</div>
        </header>
        <section class="terminal-header">
          <div>
            <div class="section-kicker">Institutional analytics package</div>
            <h1>XAU/USD Market Dashboard</h1>
            <p>Scoring global, plan BUY/SELL, niveaux de risque et contexte marche live.</p>
          </div>
          <div class="sync-pill">Ready for export</div>
        </section>
        <nav class="view-tabs" aria-label="Vues Aureum Flux">
          <a class="view-tab active" href="#dashboard" data-tab-target="dashboard" aria-selected="true">Dashboard</a>
          <a class="view-tab" href="#market" data-tab-target="market" aria-selected="false">Market</a>
          <a class="view-tab" href="#decision" data-tab-target="decision" aria-selected="false">Decision</a>
          <a class="view-tab" href="#technical" data-tab-target="technical" aria-selected="false">Technical</a>
          <a class="view-tab" href="#macro" data-tab-target="macro" aria-selected="false">Macro</a>
          <a class="view-tab" href="#geopolitics" data-tab-target="geopolitics" aria-selected="false">Geopolitics & Flows</a>
          <a class="view-tab" href="#inspector" data-tab-target="inspector" aria-selected="false">Inspector</a>
          <a class="view-tab" href="#reports" data-tab-target="reports" aria-selected="false">Reports</a>
        </nav>

        <section class="global-live-strip {banner_class}" data-verdict="{html.escape(global_recommendation.verdict)}" data-regime="{html.escape(regime_name)}" data-alert="{html.escape(regime_alert)}">
          <div class="live-cell">
            <small>XAU/USD live</small>
            <strong class="{price_class}">{gold.price:.2f}</strong>
            <span>{gold.change_abs:+.2f} / {gold.change_pct:+.2f}%</span>
          </div>
          <div class="live-cell">
            <small>Decision</small>
            <strong class="{recommendation_css_class(global_recommendation.verdict)}">{html.escape(global_recommendation.verdict)} {global_recommendation.score}/100</strong>
            <span>SL {global_recommendation.stop_loss:.2f} · TP1 {global_recommendation.take_profit_1:.2f} · TP2 {global_recommendation.take_profit_2:.2f}</span>
          </div>
          <div class="live-cell">
            <small>Regime</small>
            <strong>{html.escape(regime_name)}</strong>
            <span>{html.escape(regime_status)}</span>
          </div>
          <div class="live-cell">
            <small>Confiance</small>
            <strong>{analysis.confidence}/100</strong>
            <span>{html.escape(format_bias_label(analysis.bias))}</span>
          </div>
          <div class="live-cell">
            <small>Alerte</small>
            <strong>{html.escape('IG Weekend' if regime_alert == 'ig-weekend' else 'Hormuz/Oil' if regime_alert == 'hormuz-oil-shock' else 'Normal')}</strong>
            <span>{html.escape(regime_summary[:92])}</span>
          </div>
        </section>
        {render_terminal_state_board(global_recommendation, trade_ledger, data_quality, orchestrator_decision, market_regime)}

        <section class="tab-view active" id="dashboard" data-tab-view="dashboard">
          <section class="hero-grid anchor-target">
            <article class="panel hero-price">
              <div class="section-kicker">Tableau de bord intraday</div>
              <div class="ticker-symbol">XAU/USD spot | live</div>
              <div class="ticker-row">
                <div class="ticker-price {price_class}">{gold.price:.2f}<span class="ticker-cursor"></span></div>
                <div class="ticker-delta {price_class}">{gold.change_abs:+.2f} / {gold.change_pct:+.2f}%</div>
              </div>
              <div class="ticker-meta">
                Mis a jour {html.escape(generated_at)}<br>
                Source prix spot: <a href="{INVESTING_XAUUSD_URL}" target="_blank" rel="noopener noreferrer">Investing.com XAU/USD</a><br>
                Range du jour: {format_number(gold.day_low)} / {format_number(gold.day_high)}
              </div>
              {render_weekend_gold_proxy(weekend_gold, gold)}
              <div class="global-signal {recommendation_css_class(global_recommendation.verdict)}">
                <div class="global-signal-head">
                  <div>
                    <div class="section-kicker">Scoring global prioritaire</div>
                    <h2>Position conseillee</h2>
                  </div>
                  <div class="global-score">{global_recommendation.score}<small>/100</small></div>
                </div>
                <div class="global-position">
                  <strong class="{recommendation_css_class(global_recommendation.verdict)}">{html.escape(global_recommendation.verdict)}</strong>
                  <span>SL {global_recommendation.stop_loss:.2f} | TP1 {global_recommendation.take_profit_1:.2f} | TP2 {global_recommendation.take_profit_2:.2f}</span>
                </div>
                <p class="global-summary">{html.escape(global_recommendation.summary)}</p>
                {render_trade_levels(global_recommendation)}
              </div>
              <div class="metrics-grid">
                <div class="metric-chip">
                  <strong>Biais</strong>
                  <span class="{price_class}">{format_bias_label(analysis.bias)}</span>
                  <small>{heuristic_decision_sentence(analysis)}</small>
                </div>
                <div class="metric-chip">
                  <strong>Confiance</strong>
                  <span>{analysis.confidence}/100</span>
                  <div class="confidence-bar"><span></span></div>
                </div>
                <div class="metric-chip">
                  <strong>DXY</strong>
                  <span class="{dxy_class}">{dxy.price:.2f}</span>
                  <small>{dxy.change_pct:+.2f}% aujourd'hui</small>
                </div>
                <div class="metric-chip">
                  <strong>10Y US</strong>
                  <span class="{us10y_class}">{us10y.price:.2f}%</span>
                  <small>{us10y.change_abs * 100:+.1f} bps aujourd'hui</small>
                </div>
              </div>
            </article>

            {render_trade_card(fundamental)}
            {render_trade_card(technical)}
            <article class="panel span-12">
              <div class="section-kicker">Orchestrateur v2</div>
              <h2>Score global multi-agents</h2>
              {render_orchestrator_decision_panel(orchestrator_decision)}
            </article>
            <article class="panel span-12">
              <div class="section-kicker">Trade Tracker</div>
              <h2>Signal locking et suivi des recommandations</h2>
              {render_trade_tracker_panel(trade_ledger)}
            </article>
          </section>
        </section>

        <section class="tab-view" id="market" data-tab-view="market">
          <section class="content-grid anchor-target">
            <article class="panel span-12">
              <div class="section-kicker">Source prix & proxy week-end</div>
              <h2>Spot classique et IG Weekend Gold</h2>
              <div class="ticker-meta">
                Source prix spot: <a href="{INVESTING_XAUUSD_URL}" target="_blank" rel="noopener noreferrer">Investing.com XAU/USD</a><br>
                Prix spot actuel: {format_number(gold.price)} · Range du jour: {format_number(gold.day_low)} / {format_number(gold.day_high)}
              </div>
              {render_weekend_gold_proxy(weekend_gold, gold)}
            </article>

            <article class="panel span-7">
              <div class="section-kicker">Prix & niveaux</div>
              <h2>Chandelles 5m + ligne de prix live</h2>
              <div class="chart-wrap">{chart_svg}</div>
              <div class="footer-note" style="margin-top:10px;">
                Bougies 5 minutes calculees sur le proxy GC=F puis alignees sur le spot XAU/USD.
                La ligne ambre montre le prix spot en temps reel.
              </div>
              <div class="key-levels" style="margin-top:10px;">
                <div class="level-chip"><strong>Support</strong><span>{format_number(gold.support)}</span></div>
                <div class="level-chip"><strong>Resistance</strong><span>{format_number(gold.resistance)}</span></div>
                <div class="level-chip"><strong>Dernier prix</strong><span>{format_number(gold.price)}</span></div>
              </div>
            </article>

            <article class="panel span-5">
              <div class="section-kicker">Confluence inter-marches</div>
              <h2>Ce qui renforce ou affaiblit Gold</h2>
              {render_cross_asset_panel(cross_asset_analysis, real_yield)}
            </article>

            <article class="panel span-12">
              <div class="section-kicker">Regime politique / petrole</div>
              <h2>Safe-haven gold | Hormuz oil shock | dollar squeeze</h2>
              {render_market_regime_panel(market_regime, cross_asset_analysis)}
            </article>

            <article class="panel span-12">
              <div class="section-kicker">COT officiel CFTC</div>
              <h2>Positionnement Gold Futures COMEX</h2>
              <p class="footer-note">Lecture hebdomadaire officielle CFTC: Managed Money, Producer/Merchant, Swap Dealers, Non-reportable et open interest.</p>
              {render_cftc_positioning_panel(cftc_positioning)}
            </article>

            <article class="panel span-12">
              <div class="section-kicker">ETF flows officiels</div>
              <h2>WGC + GLD + IAU</h2>
              <p class="footer-note">Lecture des flux institutionnels gold-backed ETF: WGC global, SPDR GLD via WGC, iShares IAU via BlackRock.</p>
              {render_etf_flows_panel(etf_flows_analysis)}
            </article>

            <article class="panel span-12">
              <div class="section-kicker">Agents passifs experimentaux</div>
              <h2>Market agents</h2>
              {render_agent_department_panel(agent_results, "Market")}
            </article>
          </section>
        </section>

        <section class="tab-view" id="decision" data-tab-view="decision">
          <section class="summary-grid anchor-target">
            <article class="summary-box">
              <div class="section-kicker">Synthese prioritaire</div>
              <h2>Ce qui compte maintenant</h2>
              <p class="lead">{html.escape(executive_summary)}</p>
              {render_what_happens_now(story_lines)}
            </article>

            <article class="summary-box">
              <div class="section-kicker">Decision & prudence</div>
              <h2>Lecture des scores</h2>
              <div class="decision-grid">
                <div class="decision-item">
                  <strong class="{recommendation_css_class(global_recommendation.verdict)}">Global: {html.escape(global_recommendation.verdict)} / {global_recommendation.score}/100</strong>
                  <span>{html.escape(global_recommendation.summary)}</span>
                </div>
                <div class="decision-item">
                  <strong class="{recommendation_css_class(fundamental.verdict)}">Macro/Fondamental: {html.escape(fundamental.verdict)} / {fundamental.score}/100</strong>
                  <span>{html.escape(fundamental.summary)}</span>
                </div>
                <div class="decision-item">
                  <strong class="{recommendation_css_class(technical.verdict)}">Technique: {html.escape(technical.verdict)} / {technical.score}/100</strong>
                  <span>{html.escape(technical.summary)}</span>
                </div>
                <div class="decision-item">
                  <strong class="{geo_class}">Geopolitics & Flows: {f'{geopolitical_analysis.score}/100' if geopolitical_analysis else 'indisponible'}</strong>
                  <span>{html.escape(geopolitical_analysis.summary if geopolitical_analysis else 'Lecture geopolitique indisponible.')}</span>
                </div>
                <div class="decision-item">
                  <strong>Ce que cela veut dire pour vous</strong>
                  <span>Le mot BUY ou SELL ne veut pas dire acheter maintenant a tout prix. Il veut dire que, dans le contexte actuel, le scenario dominant penche de ce cote tant que le prix respecte le SL et les TP affiches.</span>
                </div>
              </div>
            </article>
          </section>
          <section class="content-grid anchor-target">
            <article class="panel span-12">
              <div class="section-kicker">Orchestrateur v2</div>
              <h2>Ponderation, preuves et contre-signaux</h2>
              {render_orchestrator_decision_panel(orchestrator_decision)}
            </article>
            <article class="panel span-12">
              <div class="section-kicker">Regime decisionnel</div>
              <h2>WTI/Brent + Hormuz/Oil Shock</h2>
              {render_market_regime_panel(market_regime, cross_asset_analysis)}
            </article>
            <article class="panel span-12">
              <div class="section-kicker">Data Feed Governance</div>
              <h2>Qualite, fraicheur et fiabilite des sources</h2>
              {render_data_quality_panel(data_quality)}
            </article>
            <article class="panel span-12">
              <div class="section-kicker">Agents passifs experimentaux</div>
              <h2>Decision agents & contradictions</h2>
              {render_agent_department_panel(agent_results, "Decision")}
              <div class="module-block">
                <div class="section-kicker">Contradictions entre agents</div>
                {render_agent_contradictions(agent_results)}
              </div>
            </article>
          </section>
        </section>

        <section class="tab-view" id="technical" data-tab-view="technical">
          <section class="content-grid anchor-target">
            <article class="panel span-7">
              <div class="section-kicker">Technique multi-timeframe</div>
              <h2>EMA 20/50/100/200 | RSI7 | MACD 5/34/5 | Volume</h2>
              {technical_matrix}
            </article>

            <article class="panel span-5">
              <div class="section-kicker">Plan d'execution intraday</div>
              <h2>Hausse | baisse | attente</h2>
              <div class="scenario-grid scenario-stack" style="margin-top:10px;">
                <div class="scenario positive">
                  <h3>Scenario hausse</h3>
                  <p>{html.escape(bullish_case)}</p>
                </div>
                <div class="scenario negative">
                  <h3>Scenario baisse</h3>
                  <p>{html.escape(bearish_case)}</p>
                </div>
                <div class="scenario neutral">
                  <h3>Scenario attente</h3>
                  <p>{html.escape(wait_case)}</p>
                </div>
              </div>
            </article>
            <article class="panel span-12">
              <div class="section-kicker">Agents passifs experimentaux</div>
              <h2>Technical agents</h2>
              {render_agent_department_panel(agent_results, "Technical")}
            </article>
          </section>
        </section>

        <section class="tab-view" id="macro" data-tab-view="macro">
          <section class="content-grid anchor-target">
            <article class="panel span-7">
              <div class="section-kicker">Macro | dollar | taux</div>
              <h2>DXY, FRED officiel, taux reel et lecture fondamentale</h2>
              <div class="metrics-grid">
                <div class="metric-chip">
                  <strong>DXY</strong>
                  <span class="{dxy_class}">{dxy.price:.2f}</span>
                  <small>{dxy.change_pct:+.2f}% aujourd'hui</small>
                </div>
                <div class="metric-chip">
                  <strong>10Y US officiel</strong>
                  <span class="{us10y_class}">{us10y.price:.2f}%</span>
                  <small>FRED DGS10 prioritaire; Yahoo ^TNX controle</small>
                </div>
                <div class="metric-chip">
                  <strong>10Y reel</strong>
                  <span class="{real_yield_class}">{format_number(real_yield.price if real_yield else None, 2, '%')}</span>
                  <small>{'FRED DFII10' if real_yield else 'Indisponible'}</small>
                </div>
              </div>
            </article>
            {render_trade_card(fundamental)}
            <article class="panel span-12">
              <div class="section-kicker">Bloc macro officiel</div>
              <h2>FRED DGS10 | DGS2 | T10YIE | DFII10</h2>
              {render_official_macro_panel(official_macro_rates, us10y)}
            </article>
            <article class="panel span-12">
              <div class="section-kicker">Macro Catalysts</div>
              <h2>Calendrier economique et Fed</h2>
              <p class="footer-note">FOMC, Fed speeches, BEA high impact et lien CME FedWatch. Le bloc explique pourquoi chaque evenement peut changer la lecture gold.</p>
              {render_macro_catalysts_panel(macro_catalysts)}
            </article>
            <article class="panel span-12">
              <div class="section-kicker">Agents passifs experimentaux</div>
              <h2>Macro agents</h2>
              {render_agent_department_panel(agent_results, "Macro")}
            </article>
          </section>
        </section>

        <section class="tab-view" id="geopolitics" data-tab-view="geopolitics">
          <section class="content-grid anchor-target">
            <article class="panel span-7">
              <div class="section-kicker">Geopolitics & Flows</div>
              <h2>Risque externe qui soutient ou freine l'or</h2>
              {render_geopolitical_panel(geopolitical_analysis)}
            </article>

            <article class="panel span-5">
              <div class="section-kicker">Regime de volatilite</div>
              <h2>Mode event et prudence SL</h2>
              {render_event_mode_panel(event_mode)}
            </article>

            <article class="panel span-12">
              <div class="section-kicker">Regime politique / petrole</div>
              <h2>Safe-haven gold | Hormuz oil shock | dollar squeeze</h2>
              {render_market_regime_panel(market_regime, cross_asset_analysis)}
            </article>

            <article class="panel span-12">
              <div class="section-kicker">ETF flows officiels</div>
              <h2>Demande papier institutionnelle</h2>
              {render_etf_flows_panel(etf_flows_analysis)}
            </article>

            <article class="panel span-12">
              <div class="section-kicker">Catalyseurs du jour</div>
              <h2>Messages qui expliquent le mouvement</h2>
              <p class="footer-note">Chaque bloc explique ce qui se passe reellement et pourquoi cela compte pour l'or maintenant.</p>
              <div class="digest-grid">
                {render_information_digest(digest_items)}
              </div>
            </article>

            <article class="panel span-12">
              <div class="section-kicker">Event Facts</div>
              <h2>Faits detectes, sources et chaine marche</h2>
              <p class="footer-note">Chaque conclusion geopolitique doit pouvoir pointer vers un fait concret, une source, un niveau de confirmation et une transmission marche.</p>
              {render_event_facts_panel(event_facts)}
            </article>

            <article class="panel span-12">
              <div class="section-kicker">Trump / White House</div>
              <h2>Declarations politiques sourcees</h2>
              <p class="footer-note">L'agent separe source officielle, agence fiable et rumeur. Une declaration politique ne devient importante que si sa source et sa chaine marche sont explicites.</p>
              {render_political_statements_panel(political_statements)}
            </article>

            <article class="panel span-12">
              <div class="section-kicker">Headlines expliquees</div>
              <h2>Titres sources et impact probable sur l'or</h2>
              <p class="footer-note">Chaque titre ci-dessous est traduit en langage clair avec son impact probable sur l'or, au lieu d'etre affiche brut.</p>
              <div class="headline-grid">
                {render_headline_reason_cards(bundle.news, limit=6)}
              </div>
            </article>

            <article class="panel span-12">
              <div class="section-kicker">Agents passifs experimentaux</div>
              <h2>Geopolitics & Flows agents</h2>
              {render_agent_department_panel(agent_results, "Geopolitics & Flows")}
            </article>
          </section>
        </section>

        <section class="tab-view" id="inspector" data-tab-view="inspector">
          <section class="content-grid anchor-target">
            <article class="panel span-12">
              <div class="section-kicker">Monitoring / Audit / Inspector</div>
              <h2>Flux, sources, agents et trades</h2>
              {render_monitoring_inspector_panel(generated_at, data_quality, agent_results, trade_ledger, orchestrator_decision, global_recommendation, market_regime)}
            </article>
          </section>
        </section>

        <section class="tab-view" id="reports" data-tab-view="reports">
          <section class="content-grid anchor-target">
            {render_ai_summary(ai_analysis)}

            <article class="panel span-12">
              <div class="section-kicker">Exports</div>
              <h2>Rapports disponibles</h2>
              <div class="decision-grid">
                <div class="decision-item">
                  <strong>Markdown</strong>
                  <span>Le rapport principal est genere dans reports/xauusd_report.md.</span>
                </div>
                <div class="decision-item">
                  <strong>JSON</strong>
                  <span>Le payload structure est genere dans reports/xauusd_data.json.</span>
                </div>
                <div class="decision-item">
                  <strong>Dernier calcul</strong>
                  <span>{html.escape(generated_at)}</span>
                </div>
              </div>
            </article>

            <article class="panel span-12">
              <div class="section-kicker">Fondation multi-agents passive</div>
              <h2>Inventaire agents Phase 5</h2>
              {render_agent_department_panel(agent_results, "Market")}
              {render_agent_department_panel(agent_results, "Decision")}
              {render_agent_department_panel(agent_results, "Technical")}
              {render_agent_department_panel(agent_results, "Macro")}
              {render_agent_department_panel(agent_results, "Geopolitics & Flows")}
            </article>

            <article class="panel span-12">
              <div class="section-kicker">Source Registry</div>
              <h2>Gouvernance des flux d'information</h2>
              {render_data_quality_panel(data_quality)}
            </article>

            <article class="panel span-12">
              <div class="section-kicker">Trade Ledger</div>
              <h2>Historique des TradePlan verrouilles</h2>
              {render_trade_tracker_panel(trade_ledger)}
            </article>

            <article class="panel span-12">
              <div class="section-kicker">Monitoring Inspector</div>
              <h2>Audit sources, agents et trades</h2>
              {render_monitoring_inspector_panel(generated_at, data_quality, agent_results, trade_ledger, orchestrator_decision, global_recommendation, market_regime)}
            </article>

            <article class="panel span-12">
              <div class="section-kicker">Avertissement</div>
              <div class="footer-note">
                Ce dashboard aide a lire le marche rapidement. Il ne constitue pas un conseil financier personnalise.
              </div>
            </article>
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
) -> tuple[SymbolSnapshot | None, OfficialMacroRates, CrossAssetAnalysis, EventModeAnalysis, MarketRegimeAnalysis]:
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
    breakeven_10y = cached_snapshot("fred_t10yie", lambda: fetch_fred_series_snapshot("T10YIE", FRED_SERIES_LABELS["T10YIE"]))
    real_yield = cached_snapshot("fred_dfii10", fetch_real_yield_snapshot)
    official_macro_rates = build_official_macro_rates(dgs10, dgs2, breakeven_10y, real_yield, us10y)
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
    event_mode = build_event_mode_analysis(gold, technical_readings, gvz, vix)
    market_regime = build_market_regime_analysis(gold, dxy, us10y, news, wti=wti, brent=brent, event_mode=event_mode)
    return real_yield, official_macro_rates, cross_asset, event_mode, market_regime


def build_live_bundle(base_bundle: BriefingBundle) -> BriefingBundle:
    live_bundle = copy.deepcopy(base_bundle)
    gold = fetch_investing_xauusd_snapshot(include_historical=False)
    weekend_gold = fetch_ig_weekend_gold_snapshot()
    dxy = fetch_symbol_snapshot("DX-Y.NYB", "US Dollar Index", interval="1d", data_range="1mo")
    us10y = fetch_symbol_snapshot("^TNX", "US 10Y", interval="1d", data_range="1mo")
    technical_readings, proxy_price, points_5m = fetch_technical_timeframes()
    gold.intraday_points = align_proxy_points_to_spot(points_5m, gold.price)
    real_yield, official_macro_rates, cross_asset_analysis, event_mode, market_regime = fetch_local_free_context(
        gold,
        dxy,
        us10y,
        live_bundle.news,
        technical_readings,
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
    event_facts = build_event_facts(live_bundle.news)
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
    legacy_global_recommendation = global_recommendation
    global_recommendation, orchestrator_decision = build_orchestrator_decision(
        gold,
        legacy_global_recommendation,
        agent_results,
        data_quality=data_quality,
        market_regime=market_regime,
        event_mode=event_mode,
    )
    agent_results = update_orchestrator_agent(agent_results, orchestrator_decision)
    trade_ledger = build_trade_ledger_summary(
        gold,
        global_recommendation,
        data_quality,
        agent_results,
        market_regime,
        event_facts,
        technical_readings,
    )
    payload = build_payload(
        gold,
        dxy,
        us10y,
        live_bundle.news,
        analysis,
        geopolitical_analysis=geopolitical_analysis,
        fundamental_recommendation=fundamental_recommendation,
        technical_recommendation=technical_recommendation,
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
    return live_bundle


def build_briefing(top_news: int, include_ai: bool = True) -> BriefingBundle:
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
    technical_readings, proxy_price, points_5m = fetch_technical_timeframes()
    gold.intraday_points = align_proxy_points_to_spot(points_5m, gold.price)
    real_yield, official_macro_rates, cross_asset_analysis, event_mode, market_regime = fetch_local_free_context(
        gold,
        dxy,
        us10y,
        news,
        technical_readings,
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
    event_facts = build_event_facts(news)
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
    legacy_global_recommendation = global_recommendation
    global_recommendation, orchestrator_decision = build_orchestrator_decision(
        gold,
        legacy_global_recommendation,
        agent_results,
        data_quality=data_quality,
        market_regime=market_regime,
        event_mode=event_mode,
    )
    agent_results = update_orchestrator_agent(agent_results, orchestrator_decision)
    trade_ledger = build_trade_ledger_summary(
        gold,
        global_recommendation,
        data_quality,
        agent_results,
        market_regime,
        event_facts,
        technical_readings,
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


def persist_artifacts(
    bundle: BriefingBundle,
    save_path: Path | None,
    data_json_path: Path | None,
    dashboard_path: Path | None,
) -> None:
    append_audit_log_safely(bundle)
    report, json_report, html_dashboard = render_artifacts(bundle, include_dashboard=dashboard_path is not None)
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

    def _persist_latest(self, bundle: BriefingBundle, save_report: bool) -> None:
        append_audit_log_safely(bundle)
        if save_report and self.save_path:
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
            write_text_file(self.save_path, report)

        if self.data_json_path:
            write_text_file(self.data_json_path, json.dumps(bundle.payload, ensure_ascii=False, indent=2))

        if self.dashboard_path:
            write_text_file(self.dashboard_path, render_dashboard(bundle, live_client=False))

    def _load_cached_bundle_or_raise(self, original_error: Exception) -> BriefingBundle:
        cached_bundle = load_cached_bundle(self.data_json_path)
        if cached_bundle is None:
            raise original_error
        return cached_bundle

    def get_bundle(self) -> BriefingBundle:
        now = time.time()
        with self.lock:
            if self.full_bundle is None or (now - self.full_refreshed_at) >= self.full_refresh_seconds:
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
                try:
                    bundle = build_live_bundle(self.full_bundle)
                except Exception:
                    return self.latest_bundle or self.full_bundle
                self.latest_bundle = bundle
                self.latest_refreshed_at = now
                self._persist_latest(bundle, save_report=False)

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
    return parser.parse_args()


def main() -> int:
    load_env_file(Path(".env"))
    args = parse_args()
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
