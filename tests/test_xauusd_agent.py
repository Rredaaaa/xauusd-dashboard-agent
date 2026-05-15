import json
import unittest
import xml.etree.ElementTree as ET
from dataclasses import asdict
from datetime import datetime, timedelta, timezone
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from xauusd_agent import (
    AnalysisResult,
    AgentResult,
    BriefingBundle,
    CFTCPositioning,
    ChartStore,
    ChartTimeframe,
    CrossAssetAnalysis,
    DataQualitySnapshot,
    ETFFlowsAnalysis,
    ETFHoldingRecord,
    EventModeAnalysis,
    EventFact,
    GeopoliticalAnalysis,
    MacroCatalyst,
    MacroCatalystCalendar,
    MarketRegimeAnalysis,
    NewsItem,
    NewsReactionTradePlan,
    OfficialMacroRates,
    OHLCCandle,
    OrchestratorDecision,
    PoliticalStatement,
    PreflightCheck,
    PricePoint,
    ReversalSetup,
    SetupCandidate,
    SourceSnapshot,
    SymbolSnapshot,
    TechnicalDecision,
    TechnicalReading,
    TradeLedgerSummary,
    TradePlan,
    TradeRecommendation,
    UserSettings,
    WeekendGoldSnapshot,
    CRITICAL_FAST_FEEDS,
    FAST_NEWS_RSS_FEEDS,
    OFFICIAL_NEWS_RSS_FEEDS,
    SOURCE_CATEGORY_TO_LOGICAL,
    append_audit_log_snapshot,
    apply_user_settings_to_agents,
    build_market_trade_levels,
    build_market_regime_analysis,
    build_monitoring_inspector_payload,
    build_cross_asset_analysis,
    build_event_mode_analysis,
    build_official_macro_rates,
    build_event_facts,
    build_geopolitical_analysis,
    build_data_quality_snapshot,
    build_trade_ledger_summary,
    build_replay_report,
    build_wgc_etf_flows_analysis,
    build_cftc_positioning_from_rows,
    build_political_statements,
    build_chart_store,
    detect_recent_swing_levels,
    filter_news_by_categories,
    fetch_political_statement_news,
    find_story_for_categories,
    headline_sort_key,
    logical_category,
    pick_story_headlines,
    parse_bea_release_schedule,
    parse_fed_rss_events,
    parse_fomc_calendar_events,
    classify_bias,
    build_passive_agent_results,
    build_payload,
    build_news_reaction_engine,
    build_strategy_candidates,
    evaluate_breakout_du_jour_setup,
    evaluate_mean_reversion_setup,
    evaluate_pivot_rejection_setup,
    evaluate_range_trading_setup,
    evaluate_trend_continuation_setup,
    build_reversal_engine,
    build_strategy_selection,
    classify_news_reaction_event,
    detect_news_reaction_price,
    detect_rsi_divergence,
    detect_current_session,
    build_orchestrator_decision,
    build_scenario_plan,
    build_technical_decision,
    price_points_to_candles,
    parse_ig_weekend_gold_snapshot,
    parse_ishares_iau_official_data,
    render_dashboard,
    render_desk_position_summary,
    render_monitoring_inspector_panel,
    render_news_flow_panel,
    render_reversal_panels,
    render_signal_locked_panel,
    render_trade_tracker_panel,
    render_replay_report_markdown,
    write_reports_v3,
    load_user_settings,
    macro_catalyst_gold_bias,
    merge_news_items,
    news_reaction_to_setup_candidate,
    resample_candles,
    score_headline,
    score_headline_v2,
    set_agent_enabled,
    should_skip_headline,
    trade_plan_levels_are_valid,
    trade_ledger_public_dict,
    trade_setup_from_structure,
    update_orchestrator_agent,
)


class HeadlineScoringTests(unittest.TestCase):
    def test_bullish_keywords_raise_score(self) -> None:
        score, reasons = score_headline("Gold rises as safe haven demand grows on dovish Fed bets")
        self.assertGreater(score, 0)
        self.assertTrue(reasons)

    def test_bearish_keywords_lower_score(self) -> None:
        score, reasons = score_headline("Gold slips as strong dollar and rising yields hit metals")
        self.assertLess(score, 0)
        self.assertTrue(reasons)

    def test_keyword_scoring_avoids_substring_false_positive(self) -> None:
        score, reasons = score_headline("Brent crude backwardation points to physical market tightness")
        self.assertEqual(score, 0)
        self.assertEqual(reasons, [])

    def test_scoring_v2_scores_iran_nuclear_headline(self) -> None:
        score, reasons = score_headline_v2(
            "Both countries agreed Iran can never have nuclear weapon",
            "Nitter White House",
            "critical_white_house_nitter",
        )
        self.assertGreater(score, 0)
        self.assertIn("bullish:nuclear weapon", reasons)
        self.assertIn("tier_1_official", reasons)

    def test_scoring_v2_scores_hormuz_and_reuters_headline(self) -> None:
        score, reasons = score_headline_v2(
            "New attacks on ships near Hormuz as Trump discusses Iran with Xi",
            "Reuters",
            "fast_reuters",
        )
        self.assertGreater(score, 0)
        self.assertIn("tier_2_agency", reasons)

    def test_scoring_v2_filters_protocol_noise(self) -> None:
        score, reasons = score_headline_v2(
            "R to @WhiteHouse: 🇺🇸🇨🇳",
            "Nitter White House",
            "critical_white_house_nitter",
        )
        self.assertEqual(score, 0)
        self.assertEqual(reasons, ["noise_filter"])
        self.assertTrue(should_skip_headline("History in motion 🇺🇸🇨🇳", "Nitter White House"))

    def test_scoring_v2_inverts_failed_deal(self) -> None:
        score, reasons = score_headline_v2(
            "Iran rejects nuclear deal proposal",
            "Reuters",
            "fast_reuters",
        )
        self.assertGreater(score, 0)
        self.assertIn("negation_inversion", reasons)

    def test_scoring_v2_source_tier_bonus(self) -> None:
        score_t1, _ = score_headline_v2(
            "Federal Reserve announces rate cut",
            "Federal Reserve",
            "official_fed_press_all",
            "https://www.federalreserve.gov/newsevents/pressreleases/test.htm",
        )
        score_t4, _ = score_headline_v2(
            "Federal Reserve announces rate cut",
            "Unknown Blog",
            "macro_fed",
            "https://example.com/test",
        )
        self.assertGreater(score_t1, score_t4)

    def test_scoring_v2_scores_irans_ships_claim(self) -> None:
        score, reasons = score_headline_v2(
            "Iran had 159 ships in their Navy and every ship is now resting at the bottom of the sea",
            "Truth Social",
            "political_trump_truth",
        )
        self.assertGreater(score, 0)
        self.assertTrue(any(reason.startswith("bullish:") for reason in reasons))

    def test_scoring_v2_scores_risk_on_market_wrap(self) -> None:
        score, reasons = score_headline_v2(
            "S&P 500 Tops 7,500 as AI Fuels Record-Breaking Run: Markets Wrap",
            "Bloomberg",
            "fast_bloomberg_markets",
        )
        self.assertLess(score, 0)
        self.assertTrue(any(reason.startswith("bearish:") for reason in reasons))

    def test_scoring_v2_filters_official_non_market_noise(self) -> None:
        self.assertTrue(should_skip_headline("Nominations Sent to the Senate", "White House"))
        self.assertTrue(should_skip_headline("President Trump Honors America’s Moms with New Support for Families", "White House"))

    def test_phase3_news_flow_rejects_weak_forecast_noise(self) -> None:
        self.assertTrue(should_skip_headline("Gold price prediction for next week", "MSN"))
        self.assertTrue(should_skip_headline("XAUUSD analysis today and forecast", "FXEmpire"))

    def test_phase3_news_flow_deduplicates_common_prefix_and_keeps_fresh_impact(self) -> None:
        recent = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
        items = [
            NewsItem(
                title="Fed announces emergency liquidity facility as dollar jumps",
                source="Reuters",
                link="https://www.reuters.com/markets/test",
                published_at=recent,
                category="macro_fed",
                score=-2,
                score_reasons=["bearish:dollar"],
            ),
            NewsItem(
                title="Fed announces emergency liquidity facility as dollar rises",
                source="CNBC",
                link="https://www.cnbc.com/test",
                published_at=recent,
                category="macro_fed",
                score=-2,
                score_reasons=["bearish:dollar"],
            ),
        ]
        merged = merge_news_items(items, [], 10)
        self.assertEqual(len(merged), 1)
        self.assertEqual(merged[0].source, "Reuters")

    def test_news_flow_renders_one_card_for_same_story_across_agents(self) -> None:
        published = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
        title = "Trump says Iran conflict should end quickly as oil markets react"
        fact = EventFact(
            title=title,
            source="Reuters",
            source_url="https://www.reuters.com/world/test",
            published_at=published,
            category="geopolitical",
            actors=["Trump"],
            locations=["Iran"],
            themes=["geopolitical", "oil"],
            confirmation_level="confirmed",
            market_chain="source -> oil -> dollar -> gold",
            gold_impact="Impact XAU/USD: reaction politique sourcee.",
            impact_bias="BULLISH",
            confidence=80,
        )
        statement = PoliticalStatement(
            title=title,
            source="Reuters",
            source_url="https://www.reuters.com/world/test",
            published_at=published,
            theme="Iran / oil",
            validation_level="confirmed",
            source_tier=2,
            gold_impact="Impact XAU/USD: declaration politique sourcee.",
            oil_impact="oil impact",
            usd_impact="usd impact",
            market_chain="political -> oil -> gold",
            score=2,
            confidence=78,
        )
        headline = NewsItem(
            title=title,
            source="Reuters",
            link="https://www.reuters.com/world/test",
            published_at=published,
            category="geopolitical",
            score=2,
            score_reasons=["bullish:war"],
        )
        html = render_news_flow_panel([headline], [fact], [statement], limit=12)
        self.assertEqual(html.count('<article class="headline-card'), 1)
        self.assertEqual(html.count(title), 1)
        self.assertIn("Fact / Political / geopolitical", html)

    def test_bias_buckets(self) -> None:
        self.assertEqual(classify_bias(6), "bullish")
        self.assertEqual(classify_bias(2), "slightly bullish")
        self.assertEqual(classify_bias(0), "neutral")
        self.assertEqual(classify_bias(-2), "slightly bearish")
        self.assertEqual(classify_bias(-6), "bearish")


class Phase7AFoundationTests(unittest.TestCase):
    def news_plan(self, status: str = "TRADE_READY", direction: str = "BUY") -> NewsReactionTradePlan:
        return NewsReactionTradePlan(
            status=status,
            direction=direction,
            event_type="POLITICAL_FLASH",
            title="Trump says Iran talks changed oil risk",
            source="Reuters",
            source_url="https://www.reuters.com/test",
            confidence=82,
            validity_minutes=45,
            valid_until="2026-05-15T13:45:00+00:00",
            entry_type="NEWS_REACTION",
            reference_price=4650.0,
            entry_zone_low=4649.0,
            entry_zone_high=4651.0,
            stop_loss=4638.0,
            tp1=4668.0,
            tp2=4682.0,
            tp3=4700.0,
            risk_reward_tp1=1.5,
            risk_reward_tp2=2.67,
            risk_reward_tp3=4.17,
            confirmation_score=3,
            latency_seconds=18.0,
            created_at="2026-05-15T13:00:00+00:00",
            event_id="news-123",
            reasons=["Source rapide confirmee.", "Prix confirme."],
            blockers=[],
        )

    def test_phase7a_detects_utc_market_sessions(self) -> None:
        self.assertEqual(detect_current_session(datetime(2026, 5, 15, 3, 0, tzinfo=timezone.utc)), "asian")
        self.assertEqual(detect_current_session(datetime(2026, 5, 15, 8, 0, tzinfo=timezone.utc)), "london_open")
        self.assertEqual(detect_current_session(datetime(2026, 5, 15, 11, 0, tzinfo=timezone.utc)), "london_morning")
        self.assertEqual(detect_current_session(datetime(2026, 5, 15, 14, 0, tzinfo=timezone.utc)), "london_ny_overlap")
        self.assertEqual(detect_current_session(datetime(2026, 5, 15, 17, 0, tzinfo=timezone.utc)), "ny_afternoon")
        self.assertEqual(detect_current_session(datetime(2026, 5, 15, 20, 0, tzinfo=timezone.utc)), "ny_close")
        self.assertEqual(detect_current_session(datetime(2026, 5, 15, 22, 0, tzinfo=timezone.utc)), "off_hours")

    def test_phase7a_news_reaction_trade_ready_to_setup_candidate(self) -> None:
        candidate = news_reaction_to_setup_candidate(self.news_plan())
        self.assertIsInstance(candidate, SetupCandidate)
        self.assertEqual(candidate.name, "NewsReactionSetup")
        self.assertEqual(candidate.status, "TRADE_READY")
        self.assertEqual(candidate.direction, "BUY")
        self.assertEqual(candidate.confidence, 82)
        self.assertEqual(candidate.confluence_score, 3)
        self.assertEqual(candidate.rr_tp1, 1.5)
        self.assertEqual(candidate.preferred_session, "all")
        self.assertIn("fast_news_event", candidate.conditions_met)
        self.assertEqual(candidate.metadata["event_id"], "news-123")
        self.assertEqual(candidate.metadata["source"], "Reuters")

    def test_phase7a_news_reaction_watch_direction_is_normalized(self) -> None:
        candidate = news_reaction_to_setup_candidate(self.news_plan(status="WATCH", direction="WATCH_SELL"))
        self.assertEqual(candidate.status, "WATCH")
        self.assertEqual(candidate.direction, "SELL")

    def test_phase7a_news_reaction_empty_candidate_is_no_setup(self) -> None:
        candidate = news_reaction_to_setup_candidate(None)
        self.assertEqual(candidate.status, "NO_SETUP")
        self.assertEqual(candidate.direction, "NEUTRAL")
        self.assertEqual(candidate.name, "NewsReactionSetup")


class Phase45NewsCategoryMappingTests(unittest.TestCase):
    def news_item(
        self,
        category: str,
        title: str = "New attacks near Hormuz as White House says Iran cannot get nuclear weapon",
        source: str = "Nitter White House",
        link: str = "https://nitter.net/WhiteHouse/status/1234",
        score: int = 0,
    ) -> NewsItem:
        return NewsItem(
            title=title,
            source=source,
            link=link,
            published_at="2026-05-14T10:52:00+00:00",
            category=category,
            score=score,
            score_reasons=[],
            is_breaking=True,
        )

    def test_phase45_source_categories_have_logical_mapping(self) -> None:
        expected = {
            "critical_white_house_nitter": "geopolitical",
            "critical_trump_truth": "geopolitical",
            "fast_reuters": "geopolitical",
            "fast_bloomberg_markets": "geopolitical",
            "official_white_house": "geopolitical",
            "official_ecb": "macro_fed",
            "official_fed_press_all": "macro_fed",
            "official_bea": "macro_cpi",
            "official_cftc_press": "sentiment_cot",
            "political_trump_fed": "macro_fed",
        }
        for raw_category, expected_logical in expected.items():
            self.assertEqual(SOURCE_CATEGORY_TO_LOGICAL[raw_category], expected_logical)
            self.assertEqual(logical_category(raw_category), expected_logical)

    def test_build_event_facts_accepts_phase45_categories_with_zero_keyword_score(self) -> None:
        news = [
            self.news_item("critical_white_house_nitter"),
            self.news_item(
                "fast_bloomberg_markets",
                title="Two India-Bound LPG Tankers Add to Uptick in Hormuz Transits",
                source="Bloomberg",
            ),
            self.news_item(
                "fast_reuters",
                title="New attacks on ships near Hormuz as Trump discusses Iran with Xi",
                source="Reuters",
            ),
            self.news_item(
                "official_ecb",
                title="ECB President says inflation path still affects rate policy",
                source="ECB",
                link="https://www.ecb.europa.eu/press/pr/date/2026/html/test.en.html",
            ),
        ]

        facts = build_event_facts(news, limit=6)

        self.assertGreaterEqual(len(facts), 4)
        categories = {fact.category for fact in facts}
        self.assertIn("critical_white_house_nitter", categories)
        self.assertIn("fast_bloomberg_markets", categories)
        self.assertIn("fast_reuters", categories)
        self.assertIn("official_ecb", categories)

    def test_geopolitical_analysis_uses_phase45_categories(self) -> None:
        analysis = build_geopolitical_analysis(
            [
                self.news_item("critical_white_house_nitter", title="War escalation and attack risk rises near Hormuz"),
                self.news_item("fast_reuters", title="New attack near Hormuz raises geopolitical risk", source="Reuters"),
            ]
        )

        self.assertEqual(analysis.risk_off_status, "actif")
        self.assertGreaterEqual(analysis.score, 56)
        self.assertTrue(analysis.event_watch)

    def test_story_selection_and_filters_use_logical_categories(self) -> None:
        critical = self.news_item("critical_white_house_nitter")
        macro = self.news_item(
            "official_fed_press_all",
            title="Federal Reserve statement keeps rates under review",
            source="Federal Reserve",
        )
        news = [macro, critical]

        self.assertEqual(filter_news_by_categories(news, {"geopolitical"}), [critical])
        self.assertEqual(find_story_for_categories(news, "macro_fed"), macro)
        picked_categories = {logical_category(item) for item in pick_story_headlines(news, limit=2)}
        self.assertIn("geopolitical", picked_categories)
        self.assertIn("macro_fed", picked_categories)

    def test_headline_sort_key_prioritizes_critical_categories(self) -> None:
        critical = self.news_item("critical_white_house_nitter")
        low_priority = self.news_item("unknown_feed", title="Generic market headline", source="RSS", score=0)

        self.assertLess(headline_sort_key(critical)[0], headline_sort_key(low_priority)[0])


class AnalysisShapeTests(unittest.TestCase):
    def snapshot(self, symbol: str, price: float, previous: float) -> SymbolSnapshot:
        points = [
            PricePoint(timestamp=1, close=previous),
            PricePoint(timestamp=2, close=price),
        ]
        return SymbolSnapshot(
            symbol=symbol,
            label=symbol,
            price=price,
            previous_close=previous,
            change_abs=price - previous,
            change_pct=((price - previous) / previous) * 100 if previous else 0.0,
            period_change_pct=((price - previous) / previous) * 100 if previous else 0.0,
            day_high=max(price, previous),
            day_low=min(price, previous),
            support=min(price, previous),
            resistance=max(price, previous),
            fetched_at="2026-04-24T00:00:00+00:00",
            points=points,
        )

    def technical_decision(self, direction: str, price: float = 2400.0) -> TechnicalDecision:
        is_buy = "BUY" in direction
        return TechnicalDecision(
            status="TRADE_READY",
            direction=direction,
            structure="trend",
            score=72,
            confidence=74,
            trigger=(
                f"BUY seulement si cloture M15 au-dessus de {price + 5:.2f}."
                if is_buy
                else f"SELL seulement si cloture M15 sous {price - 5:.2f}."
            ),
            invalidation=(
                f"Invalidation BUY sous {price - 12:.2f}."
                if is_buy
                else f"Invalidation SELL au-dessus de {price + 12:.2f}."
            ),
            entry_zone_low=price - 2.0,
            entry_zone_high=price + 2.0,
            stop_loss=price - 12.0 if is_buy else price + 12.0,
            tp1=price + 20.0 if is_buy else price - 20.0,
            tp2=price + 36.0 if is_buy else price - 36.0,
            tp3=price + 54.0 if is_buy else price - 54.0,
            reasons=["Structure technique valide."],
            contradictions=[],
        )

    def test_parse_ig_weekend_gold_snapshot(self) -> None:
        html = """
        <html><body>
        <h1>Weekend Gold</h1>
        <span>FFIH5</span>
        <div>SELL 4682.3 BUY 4697.3 -19.2(-0.41%)</div>
        <div>High: 4733.6 Low: 4674.0</div>
        <div>Long Short 41% 59% 59% of client accounts are short on this market</div>
        </body></html>
        """
        snapshot = parse_ig_weekend_gold_snapshot(html)
        self.assertEqual(snapshot.source_name, "IG Weekend Gold")
        self.assertAlmostEqual(snapshot.sell, 4682.3)
        self.assertAlmostEqual(snapshot.buy, 4697.3)
        self.assertAlmostEqual(snapshot.mid, 4689.8)
        self.assertEqual(snapshot.long_pct, 41)
        self.assertEqual(snapshot.short_pct, 59)

    def test_news_item_dataclass(self) -> None:
        item = NewsItem(
            title="Example",
            source="Source",
            link="https://example.com",
            published_at="2026-04-24T00:00:00+00:00",
            category="gold",
            score=1,
            score_reasons=["bullish:safe haven"],
        )
        analysis = AnalysisResult(
            bias="bullish",
            score=3,
            confidence=60,
            reasons=["Example reason"],
            bullish_news=[item],
            bearish_news=[],
            neutral_news=[],
        )
        self.assertEqual(analysis.bullish_news[0].source, "Source")

    def test_dashboard_render_contains_key_sections(self) -> None:
        points = [
            PricePoint(timestamp=1, close=100.0),
            PricePoint(timestamp=2, close=101.5),
            PricePoint(timestamp=3, close=102.0),
        ]
        gold = SymbolSnapshot(
            symbol="XAU/USD",
            label="XAU/USD Spot",
            price=102.0,
            previous_close=100.0,
            change_abs=2.0,
            change_pct=2.0,
            period_change_pct=2.0,
            day_high=103.0,
            day_low=99.5,
            support=100.0,
            resistance=103.0,
            fetched_at="2026-04-24T00:00:00+00:00",
            points=points,
        )
        dxy = SymbolSnapshot(
            symbol="DX-Y.NYB",
            label="US Dollar Index",
            price=98.0,
            previous_close=99.0,
            change_abs=-1.0,
            change_pct=-1.01,
            period_change_pct=-1.01,
            day_high=99.0,
            day_low=97.8,
            support=97.8,
            resistance=99.0,
            fetched_at="2026-04-24T00:00:00+00:00",
            points=points,
        )
        us10y = SymbolSnapshot(
            symbol="^TNX",
            label="US 10Y",
            price=4.2,
            previous_close=4.3,
            change_abs=-0.1,
            change_pct=-2.33,
            period_change_pct=-2.33,
            day_high=4.3,
            day_low=4.2,
            support=4.2,
            resistance=4.3,
            fetched_at="2026-04-24T00:00:00+00:00",
            points=points,
        )
        fred_dgs10 = SymbolSnapshot(
            symbol="DGS10",
            label="US 10Y Treasury Yield",
            price=4.18,
            previous_close=4.20,
            change_abs=-0.02,
            change_pct=-0.48,
            period_change_pct=-0.48,
            day_high=4.20,
            day_low=4.18,
            support=4.18,
            resistance=4.20,
            fetched_at="2026-04-24T00:00:00+00:00",
            points=points,
        )
        fred_dgs2 = SymbolSnapshot(
            symbol="DGS2",
            label="US 2Y Treasury Yield",
            price=3.86,
            previous_close=3.88,
            change_abs=-0.02,
            change_pct=-0.52,
            period_change_pct=-0.52,
            day_high=3.88,
            day_low=3.86,
            support=3.86,
            resistance=3.88,
            fetched_at="2026-04-24T00:00:00+00:00",
            points=points,
        )
        fred_t10yie = SymbolSnapshot(
            symbol="T10YIE",
            label="US 10Y Breakeven Inflation",
            price=2.31,
            previous_close=2.28,
            change_abs=0.03,
            change_pct=1.32,
            period_change_pct=1.32,
            day_high=2.31,
            day_low=2.28,
            support=2.28,
            resistance=2.31,
            fetched_at="2026-04-24T00:00:00+00:00",
            points=points,
        )
        fred_dfii10 = SymbolSnapshot(
            symbol="DFII10",
            label="US 10Y Real Yield",
            price=1.87,
            previous_close=1.92,
            change_abs=-0.05,
            change_pct=-2.60,
            period_change_pct=-2.60,
            day_high=1.92,
            day_low=1.87,
            support=1.87,
            resistance=1.92,
            fetched_at="2026-04-24T00:00:00+00:00",
            points=points,
        )
        item = NewsItem(
            title="Gold rises on softer dollar",
            source="Reuters",
            link="https://example.com",
            published_at="2026-04-24T00:00:00+00:00",
            category="gold",
            score=2,
            score_reasons=["bullish:weak dollar"],
        )
        analysis = AnalysisResult(
            bias="bullish",
            score=6,
            confidence=70,
            reasons=["Dollar faible", "Taux en baisse"],
            bullish_news=[item],
            bearish_news=[],
            neutral_news=[],
        )
        bundle = BriefingBundle(
            gold=gold,
            dxy=dxy,
            us10y=us10y,
            news=[item],
            analysis=analysis,
            payload={"generated_at": "2026-04-24T00:00:00+00:00"},
            ai_analysis="Synthese test.",
            geopolitical_analysis=GeopoliticalAnalysis(
                score=64,
                summary="Lecture geo test.",
                risk_off_status="actif",
                central_bank_bias="accommodant",
                physical_demand_trend="achats en hausse",
                large_speculators="net long",
                etf_flows="inflows",
                comex_open_interest="en hausse",
                vix_tone="risk-off",
                event_watch=["FOMC minutes today"],
                reasons=["Risk-off actif", "ETF en entrees"],
            ),
            fundamental_recommendation=TradeRecommendation(
                mode="Fondamental",
                verdict="BUY",
                score=72,
                summary="Resume fondamental test.",
                reasons=["Dollar faible", "Taux bas"],
                stop_loss=99.0,
                take_profit_1=103.0,
                take_profit_2=105.0,
                source_note="Source test.",
            ),
            technical_recommendation=TradeRecommendation(
                mode="Technique",
                verdict="SELL",
                score=68,
                summary="Resume technique test.",
                reasons=["RSI faible", "MACD negative"],
                stop_loss=103.0,
                take_profit_1=100.0,
                take_profit_2=98.0,
                source_note="Source technique test.",
            ),
            technical_timeframes=[
                TechnicalReading(
                    timeframe="1D",
                    close=102.0,
                    ema20=101.0,
                    ema50=100.5,
                    ema100=100.0,
                    ema200=99.5,
                    rsi7=62.0,
                    macd_line=1.0,
                    macd_signal=0.5,
                    macd_histogram=0.5,
                    volume_ratio=1.2,
                    atr14=3.5,
                    score=4.0,
                    verdict="BUY",
                    reasons=["Test"],
                )
            ],
            executive_summary="Resume executif test.",
            weekend_gold=WeekendGoldSnapshot(
                source_name="IG Weekend Gold",
                source_url="https://www.ig.com/en/indices/markets-indices/weekend-gold",
                sell=101.0,
                buy=103.0,
                mid=102.0,
                spread=2.0,
                change_abs=1.5,
                change_pct=1.47,
                day_high=104.0,
                day_low=100.0,
                long_pct=42,
                short_pct=58,
                fetched_at="2026-04-24T00:00:00+00:00",
            ),
            real_yield=fred_dfii10,
            official_macro_rates=OfficialMacroRates(
                dgs10=fred_dgs10,
                dgs2=fred_dgs2,
                t10yie=fred_t10yie,
                dfii10=fred_dfii10,
                yahoo_tnx_gap_bps=2.0,
            ),
            cftc_positioning=CFTCPositioning(
                market="GOLD - COMMODITY EXCHANGE INC.",
                contract_code="088691",
                report_date="2026-04-21",
                source_url="https://www.cftc.gov/files/dea/history/fut_disagg_txt_2026.zip",
                open_interest=365842,
                open_interest_change=4200,
                managed_money_long=123681,
                managed_money_short=30705,
                managed_money_spread=33896,
                managed_money_net=92976,
                managed_money_net_change=5200,
                managed_money_net_pct_oi=25.42,
                producer_long=12633,
                producer_short=33051,
                producer_net=-20418,
                producer_net_change=-1100,
                swap_long=28115,
                swap_short=210637,
                swap_spread=15513,
                swap_net=-182522,
                swap_net_change=-2800,
                non_reportable_long=52223,
                non_reportable_short=13289,
                non_reportable_net=38934,
                non_reportable_net_change=900,
                score=68,
                status="bullish positioning",
                summary="Managed Money acheteurs nets de +92,976 contrats.",
            ),
            etf_flows_analysis=ETFFlowsAnalysis(
                as_of_date="2026-04-24",
                source_name="World Gold Council ETF holdings and flows",
                source_url="https://www.gold.org/goldhub/data/gold-etfs-holdings-and-flows",
                global_holdings_tonnes=4136.64,
                global_weekly_demand_tonnes=-10.54,
                global_monthly_demand_tonnes=-84.26,
                global_weekly_flows_usd_mn=-1435.8,
                global_monthly_flows_usd_mn=-11740.6,
                score=24,
                status="outflows",
                summary="WGC ETF: sorties sur la semaine.",
                holdings=[
                    ETFHoldingRecord(
                        fund="SPDR Gold Shares",
                        ticker="GLD",
                        source_name="World Gold Council ETF archive",
                        source_url="https://fsapi.gold.org/api/v11/charts/etfv2/revised/archive-tablegroup/all?break-cache=27Apr26",
                        as_of_date="2026-04-24",
                        holdings_tonnes=1046.35,
                        daily_flow_tonnes=None,
                        weekly_flow_tonnes=-14.09,
                        monthly_flow_tonnes=-54.13,
                        ytd_flow_tonnes=-23.86,
                        flow_usd_mn=-2137.0,
                        status="outflows",
                        note="WGC test.",
                    ),
                    ETFHoldingRecord(
                        fund="iShares Gold Trust",
                        ticker="IAU",
                        source_name="BlackRock iShares official page",
                        source_url="https://www.blackrock.com/us/financial-professionals/products/239561/",
                        as_of_date="Apr 29, 2026",
                        holdings_tonnes=482.11,
                        daily_flow_tonnes=0.35,
                        weekly_flow_tonnes=0.35,
                        monthly_flow_tonnes=-23.27,
                        ytd_flow_tonnes=-12.0,
                        flow_usd_mn=-3677.6,
                        status="flat",
                        note="BlackRock test.",
                    ),
                ],
                source_note="WGC official test.",
            ),
            macro_catalysts=MacroCatalystCalendar(
                generated_at="2026-04-24T00:00:00+00:00",
                source_note="Fed FOMC calendar official. BEA release schedule official.",
                fedwatch_status="linked_only",
                fedwatch_note="CME FedWatch officiel lie sans probabilite inventee.",
                fedwatch_source_url="https://www.cmegroup.com/markets/interest-rates/cme-fedwatch-tool.html",
                catalysts=[
                    MacroCatalyst(
                        title="FOMC decision June 17, 2026",
                        event_type="FOMC decision",
                        scheduled_at="2026-06-17T18:00:00+00:00",
                        source_name="Federal Reserve FOMC calendar",
                        source_url="https://www.federalreserve.gov/monetarypolicy/fomccalendars.htm",
                        impact_level="HIGH",
                        gold_impact="Impact gold depend de la trajectoire des taux reels et du dollar.",
                        why_it_matters="Un message hawkish peut monter USD/taux; dovish peut soutenir gold.",
                        status="a venir",
                        minutes_to_event=78540,
                    ),
                    MacroCatalyst(
                        title="Personal Income and Outlays, April 2026",
                        event_type="BEA macro release",
                        scheduled_at="2026-05-28T12:30:00+00:00",
                        source_name="BEA news release schedule",
                        source_url="https://www.bea.gov/news/schedule",
                        impact_level="HIGH",
                        gold_impact="PCE/inflation est cle pour les anticipations de baisse de taux Fed.",
                        why_it_matters="Inflation plus forte soutient USD/taux; plus faible soutient gold.",
                        status="a venir",
                        minutes_to_event=49350,
                    ),
                ],
            ),
            data_quality=DataQualitySnapshot(
                generated_at="2026-04-24T00:00:00+00:00",
                score=88,
                status="HIGH",
                summary="Data quality HIGH 88/100: sources critiques ok.",
                missing_sources=[],
                stale_sources=[],
                weak_sources=["Google News RSS / fallback feeds"],
                contradictions=[],
                snapshots=[
                    SourceSnapshot(
                        source_id="fred_dgs10",
                        name="FRED DGS10",
                        category="rates",
                        tier=1,
                        status="ok",
                        last_update="2026-04-24T00:00:00+00:00",
                        age_minutes=0,
                        value_summary="10Y 4.18%",
                        source_url="https://fred.stlouisfed.org/",
                        critical=True,
                        allowed_agents=["MacroAgent", "RiskManagerAgent"],
                    )
                ],
            ),
            event_facts=[
                EventFact(
                    title="Iran tensions rise near Strait of Hormuz as oil shipping risk grows",
                    source="Reuters",
                    source_url="https://example.com",
                    published_at="2026-04-24T00:00:00+00:00",
                    category="geopolitical",
                    actors=["Iran", "Oil market"],
                    locations=["Hormuz", "Middle East"],
                    themes=["Oil shock", "War risk"],
                    confirmation_level="agence/finance majeure",
                    market_chain="Fait source -> risque petrole/logistique -> WTI/Brent et inflation energie peuvent monter.",
                    gold_impact="Le choc petrole peut soutenir le theme refuge mais aussi renforcer dollar/taux.",
                    impact_bias="mixte",
                    confidence=82,
                )
            ],
            political_statements=[
                PoliticalStatement(
                    title="President Trump says Iran sanctions remain on the table",
                    source="White House",
                    source_url="https://www.whitehouse.gov/news/",
                    published_at="2026-04-24T00:00:00+00:00",
                    theme="Iran / Hormuz / Oil",
                    validation_level="official_confirmed",
                    source_tier=1,
                    gold_impact="mixte: risque refuge, mais oil/dollar peuvent aspirer la liquidite.",
                    oil_impact="haussier si le marche price un risque sur offre/logistique.",
                    usd_impact="haussier possible si demande de liquidite USD.",
                    market_chain="Declaration politique -> Iran/Hormuz/sanctions -> oil et USD peuvent capter la liquidite -> gold devient mixte.",
                    score=-1,
                    confidence=90,
                )
            ],
            market_regime=MarketRegimeAnalysis(
                name="Hormuz / Oil Shock",
                status="ACTIF",
                score=72,
                gold_impact="mixte/baissier court terme",
                summary="Regime Hormuz/Oil Shock test.",
                reasons=["WTI/Brent montent", "Gold ne confirme pas"],
            ),
            trade_ledger=TradeLedgerSummary(
                ledger_path="reports/trade_ledger.jsonl",
                generated_at="2026-04-24T00:00:00+00:00",
                quality_gate_status="WAIT",
                quality_gate_reasons=["Score global insuffisant pour verrouiller un trade."],
                active_trades=[
                    TradePlan(
                        trade_id="test-buy-001",
                        created_at="2026-04-24T00:00:00+00:00",
                        updated_at="2026-04-24T00:00:00+00:00",
                        status="active",
                        direction="BUY",
                        entry_type="market_reference",
                        reference_price=102.0,
                        entry_zone_low=101.0,
                        entry_zone_high=103.0,
                        stop_loss=99.0,
                        tp1=103.0,
                        tp2=105.0,
                        tp3=106.85,
                        risk_reward_tp1=0.33,
                        risk_reward_tp2=1.0,
                        risk_reward_tp3=1.62,
                        max_valid_until="2026-04-24T06:00:00+00:00",
                        source_signal_id="abc123",
                        global_score_at_creation=72,
                        data_quality_score=88,
                        confidence_score=70,
                        market_regime="Normal Macro",
                        agents_validating=["PriceActionAgent", "MacroAgent"],
                        agents_contradicting=[],
                        evidence_sources=["Investing.com XAU/USD", "FRED DGS10"],
                        event_facts_snapshot=["FOMC minutes today"],
                        technical_snapshot="1D:BUY/+4.0",
                        macro_snapshot="Macro supportive.",
                        geopolitical_snapshot="Geo mixed.",
                        elliott_wave_snapshot="Sequence haussiere incomplete.",
                        invalidation_rules=["Invalidation si SL touche."],
                        outcome="open",
                        outcome_reason="Trade Snapshot cree par test.",
                    )
                ],
                recent_trades=[],
                total_trades=1,
                wins=0,
                losses=0,
                partials=0,
                expired=0,
            ),
        )
        dashboard = render_dashboard(bundle)
        self.assertIn("Dashboard XAUUSD", dashboard)
        self.assertIn("Fourniwell Signals Trading Desk", dashboard)
        self.assertIn("Decision exploitable et charte live", dashboard)
        self.assertIn("Chef de file", dashboard)
        self.assertIn("Signal locked", dashboard)
        self.assertIn("Investing.com XAU/USD", dashboard)
        self.assertIn("TradingView", dashboard)
        self.assertIn("Scenario Engine v3", dashboard)
        self.assertIn("Scoring et position de chaque agent", dashboard)
        self.assertIn("Positions agents", dashboard)
        self.assertIn("PriceActionAgent", dashboard)
        self.assertNotIn("OrchestratorAgent", dashboard)
        self.assertIn("Contradictions", dashboard)
        self.assertIn("Flux d'informations utiles", dashboard)
        self.assertIn("News avec impact XAU/USD", dashboard)
        self.assertIn("Flux trie", dashboard)
        self.assertIn("Exports et documentation locale", dashboard)
        self.assertIn("Trade Ledger", dashboard)
        self.assertIn("test-buy-001", dashboard)
        self.assertIn("Monitoring / Audit / Inspector", dashboard)
        self.assertIn("Flux, sources, agents et trades", dashboard)
        self.assertIn("Audit log", dashboard)
        self.assertIn("Source Registry", dashboard)
        self.assertIn("Data Feed Governance", dashboard)
        self.assertIn("Regime interne", dashboard)
        self.assertIn("Event Facts", dashboard)
        self.assertIn("Political Statements", dashboard)
        self.assertIn("President Trump says Iran sanctions remain on the table", dashboard)
        self.assertIn("global-live-strip", dashboard)
        self.assertIn("top-nav", dashboard)
        self.assertIn("layout-desk", dashboard)
        self.assertIn("layout-agents", dashboard)
        self.assertIn("layout-news", dashboard)
        self.assertIn("layout-inspector", dashboard)
        self.assertIn("layout-reports", dashboard)
        self.assertNotIn("view-tabs", dashboard)
        self.assertIn('data-tab-target="desk"', dashboard)
        self.assertIn('data-tab-target="agents"', dashboard)
        self.assertIn('data-tab-target="news"', dashboard)
        self.assertIn('data-tab-target="reports"', dashboard)
        self.assertIn('data-tab-target="inspector"', dashboard)
        self.assertNotIn('data-tab-target="dashboard"', dashboard)
        self.assertNotIn('data-tab-target="market"', dashboard)
        self.assertNotIn('data-tab-target="decision"', dashboard)
        self.assertNotIn('data-tab-target="macro"', dashboard)
        self.assertNotIn('data-tab-target="geopolitics"', dashboard)
        self.assertGreaterEqual(dashboard.count('data-tab-target="desk"'), 2)
        self.assertIn('data-tab-view="desk"', dashboard)
        self.assertIn('data-tab-view="reports"', dashboard)
        self.assertIn("aureumFlux.activeTab", dashboard)
        self.assertIn("applyStoredTab", dashboard)
        self.assertNotIn("ElliottWaveAgent", dashboard)

        self.assertIn("IG Weekend Gold", dashboard)
        self.assertIn("TechnicalDecisionEngine", dashboard)
        self.assertIn("Confluence inter-marches", dashboard)
        self.assertIn("Bloc macro officiel", dashboard)
        self.assertIn("FRED DGS10 | DGS2 | T10YIE | DFII10", dashboard)
        self.assertIn("10Y nominal officiel", dashboard)
        self.assertIn("Controle Yahoo ^TNX", dashboard)
        self.assertIn("FRED prioritaire pour les taux", dashboard)
        self.assertIn("COT officiel CFTC", dashboard)
        self.assertIn("Positionnement Gold Futures COMEX", dashboard)
        self.assertIn("Managed Money acheteurs nets", dashboard)
        self.assertIn("365,842", dashboard)
        self.assertIn("ETF flows officiels", dashboard)
        self.assertIn("WGC + GLD + IAU", dashboard)
        self.assertIn("World Gold Council ETF holdings and flows", dashboard)
        self.assertIn("SPDR Gold Shares", dashboard)
        self.assertIn("iShares Gold Trust", dashboard)
        self.assertIn("Macro Catalysts", dashboard)
        self.assertIn("Calendrier a surveiller", dashboard)
        self.assertIn("Federal Reserve FOMC calendar", dashboard)
        self.assertIn("CME FedWatch officiel", dashboard)
        self.assertIn("Personal Income and Outlays", dashboard)

    def test_monitoring_inspector_payload_and_audit_log(self) -> None:
        gold = self.snapshot("XAU/USD", 102.0, 100.0)
        dxy = self.snapshot("DX-Y.NYB", 98.0, 99.0)
        us10y = self.snapshot("^TNX", 4.2, 4.3)
        news_item = NewsItem(
            title="Gold rises on softer dollar",
            source="Reuters",
            link="https://example.com",
            published_at="2026-04-24T00:00:00+00:00",
            category="gold",
            score=2,
            score_reasons=["bullish:weak dollar"],
        )
        analysis = AnalysisResult(
            bias="bullish",
            score=5,
            confidence=72,
            reasons=["Dollar faible"],
            bullish_news=[news_item],
            bearish_news=[],
            neutral_news=[],
        )
        recommendation = TradeRecommendation(
            mode="Global v3",
            verdict="BUY",
            score=68,
            summary="Signal test auditable.",
            reasons=["Agent confirme"],
            stop_loss=99.0,
            take_profit_1=104.0,
            take_profit_2=106.0,
            source_note="Test.",
        )
        quality = DataQualitySnapshot(
            generated_at="2026-04-24T00:00:00+00:00",
            score=82,
            status="USABLE",
            summary="Data quality test.",
            missing_sources=[],
            stale_sources=["Google News RSS / fallback feeds"],
            weak_sources=[],
            contradictions=[],
            snapshots=[
                SourceSnapshot(
                    source_id="investing_xauusd",
                    name="Investing.com XAU/USD",
                    category="price",
                    tier=2,
                    status="ok",
                    last_update="2026-04-24T00:00:00+00:00",
                    age_minutes=0,
                    value_summary="spot 102.00",
                    source_url="https://example.com",
                    critical=True,
                    allowed_agents=["PriceActionAgent"],
                ),
                SourceSnapshot(
                    source_id="google_news_rss",
                    name="Google News RSS / fallback feeds",
                    category="news",
                    tier=4,
                    status="stale",
                    last_update="2026-04-23T00:00:00+00:00",
                    age_minutes=1440,
                    value_summary="1 headline",
                    source_url="https://news.google.com/rss",
                    critical=True,
                    allowed_agents=["SentimentNewsAgent"],
                ),
            ],
        )
        agents = [
            AgentResult(
                name="PriceActionAgent",
                department="Market",
                bias="BUY",
                score=68,
                confidence=75,
                summary="Prix exploitable.",
                status="ACTIVE",
                experimental=False,
            )
        ]
        ledger = TradeLedgerSummary(
            ledger_path="reports/trade_ledger.jsonl",
            generated_at="2026-04-24T00:00:00+00:00",
            quality_gate_status="WAIT",
            quality_gate_reasons=["Test gate."],
            active_trades=[],
            recent_trades=[],
            total_trades=0,
        )
        inspector = build_monitoring_inspector_payload(
            "2026-04-24T00:00:00+00:00",
            quality,
            agents,
            ledger,
            None,
            recommendation,
            None,
        )
        self.assertEqual(inspector["source_counts"]["active"], 1)
        self.assertEqual(inspector["source_counts"]["stale"], 1)
        self.assertEqual(inspector["agents"]["active"], 1)
        self.assertEqual(inspector["trades"]["quality_gate_status"], "WAIT")

        bundle = BriefingBundle(
            gold=gold,
            dxy=dxy,
            us10y=us10y,
            news=[news_item],
            analysis=analysis,
            payload={"generated_at": "2026-04-24T00:00:00+00:00"},
            ai_analysis=None,
            data_quality=quality,
            agent_results=agents,
            trade_ledger=ledger,
            global_recommendation=recommendation,
        )
        with TemporaryDirectory() as tmpdir:
            audit_path = Path(tmpdir) / "audit_log.jsonl"
            entry = append_audit_log_snapshot(bundle, path=audit_path)
            self.assertTrue(audit_path.exists())
            self.assertEqual(entry["decision"]["verdict"], "BUY")
            self.assertIn("Google News RSS / fallback feeds", audit_path.read_text(encoding="utf-8"))

    def test_macro_catalyst_parsers_extract_official_events(self) -> None:
        fomc_html = """
        <h4>2026 FOMC Meetings</h4>
        <div>June 16-17* July 28-29 September 15-16*</div>
        """
        fomc_events = parse_fomc_calendar_events(fomc_html)
        self.assertTrue(any(event.event_type == "FOMC decision" for event in fomc_events))
        self.assertTrue(any(event.event_type == "FOMC projections" for event in fomc_events))
        self.assertTrue(any("June" in event.title for event in fomc_events))

        bea_html = """
        <table><tr><td>May 28, 2026 8:30 AM</td><td>Personal Income and Outlays, April 2026</td></tr>
        <tr><td>May 28, 2026 8:30 AM</td><td>Gross Domestic Product, 1st Quarter 2026 (Second Estimate)</td></tr></table>
        """
        bea_events = parse_bea_release_schedule(bea_html)
        self.assertEqual(len(bea_events), 2)
        self.assertTrue(any("Personal Income" in event.title for event in bea_events))
        self.assertTrue(all(event.source_name == "BEA news release schedule" for event in bea_events))

        rss_xml = """
        <rss><channel><item><title>Speech by Governor Waller</title>
        <link>https://www.federalreserve.gov/newsevents/speech/test.htm</link>
        <pubDate>Tue, 21 Apr 2026 18:30:00 GMT</pubDate></item></channel></rss>
        """
        fed_events = parse_fed_rss_events(
            rss_xml,
            "Federal Reserve speeches RSS",
            "https://www.federalreserve.gov/feeds/speeches.xml",
        )
        self.assertEqual(fed_events[0].event_type, "Fed speech")
        self.assertEqual(fed_events[0].impact_level, "HIGH")

    def test_data_quality_flags_missing_and_stale_critical_sources(self) -> None:
        gold = self.snapshot("XAU/USD", 2400.0, 2390.0)
        gold.fetched_at = "2026-04-25T00:00:00+00:00"
        dxy = self.snapshot("DXY", 99.0, 98.5)
        us10y = self.snapshot("^TNX", 4.2, 4.1)
        quality = build_data_quality_snapshot(
            gold,
            dxy,
            us10y,
            [],
            now=datetime(2026, 5, 1, tzinfo=timezone.utc),
        )
        self.assertLess(quality.score, 70)
        self.assertIn("Investing.com XAU/USD", quality.stale_sources)
        self.assertIn("FRED DGS10", quality.missing_sources)
        self.assertIn("World Gold Council ETF flows", quality.missing_sources)
        self.assertIsNotNone(quality.preflight)
        self.assertEqual(quality.preflight.status, "SOURCE_STALE")
        self.assertTrue(quality.preflight.trade_blocked)

    def test_preflight_keeps_dashboard_usable_when_secondary_source_missing(self) -> None:
        gold = self.snapshot("XAU/USD", 2400.0, 2390.0)
        dxy = self.snapshot("DXY", 99.0, 98.5)
        us10y = self.snapshot("^TNX", 4.2, 4.1)
        dgs10 = self.snapshot("DGS10", 4.2, 4.1)
        dfii10 = self.snapshot("DFII10", 1.8, 1.9)
        official = build_official_macro_rates(dgs10, None, None, dfii10, us10y)
        quality = build_data_quality_snapshot(
            gold,
            dxy,
            us10y,
            [],
            real_yield=dfii10,
            official_macro_rates=official,
            now=datetime(2026, 4, 24, tzinfo=timezone.utc),
        )
        self.assertIsNotNone(quality.preflight)
        self.assertNotEqual(quality.preflight.status, "OFFLINE")
        self.assertTrue(any(route.source_id == "chart_store_ohlc" for route in quality.preflight.routes))

    def test_chart_store_resamples_and_flags_history_quality(self) -> None:
        fetched_at = "2026-04-24T00:00:00+00:00"
        m1_points = [
            PricePoint(timestamp=index * 60, open=100 + index, high=101 + index, low=99 + index, close=100.5 + index, volume=10)
            for index in range(10)
        ]
        m1_candles = price_points_to_candles(m1_points, "M1", "fixture", fetched_at)
        m5_candles = resample_candles(m1_candles, "M5")
        self.assertEqual(len(m5_candles), 2)
        self.assertEqual(m5_candles[0].open, m1_candles[0].open)
        self.assertEqual(m5_candles[0].close, m1_candles[4].close)
        self.assertEqual(m5_candles[0].volume, 50)

        points_by_tf = {
            "M5": [PricePoint(timestamp=index * 300, close=100 + index) for index in range(60)],
            "M15": [PricePoint(timestamp=index * 900, close=100 + index) for index in range(60)],
            "H1": [PricePoint(timestamp=index * 3600, close=100 + index) for index in range(20)],
            "H4": [PricePoint(timestamp=index * 14400, close=100 + index) for index in range(60)],
            "D1": [PricePoint(timestamp=index * 86400, close=100 + index) for index in range(130)],
        }
        store = build_chart_store(
            points_by_tf,
            source="fixture",
            fetched_at=fetched_at,
            now=datetime(2026, 4, 24, tzinfo=timezone.utc),
        )
        self.assertIsInstance(store, ChartStore)
        self.assertEqual(store.status, "INSUFFICIENT_HISTORY")
        h1 = next(item for item in store.timeframes if item.timeframe == "H1")
        self.assertEqual(h1.status, "INSUFFICIENT_HISTORY")

    def test_event_fact_deduplication_keeps_single_fact_per_headline(self) -> None:
        item = NewsItem(
            title="Gold rises as Fed rate cut bets grow",
            source="Reuters",
            link="https://example.com/a",
            published_at="2026-04-24T00:00:00+00:00",
            category="macro_fed",
            score=2,
            score_reasons=["bullish:rate cut"],
        )
        duplicate = NewsItem(
            title="Gold rises as Fed rate cut bets grow",
            source="Aggregator",
            link="https://example.com/b",
            published_at="2026-04-24T00:05:00+00:00",
            category="macro_fed",
            score=2,
            score_reasons=["bullish:rate cut"],
        )
        facts = build_event_facts([item, duplicate], limit=6)
        self.assertEqual(len(facts), 1)
        self.assertEqual(facts[0].source, "Reuters")

    def test_trade_ledger_locks_trade_and_preserves_levels(self) -> None:
        gold = self.snapshot("XAU/USD", 2400.0, 2390.0)
        gold.fetched_at = "2026-04-24T00:00:00+00:00"
        recommendation = TradeRecommendation(
            mode="Global",
            verdict="BUY",
            score=72,
            summary="Signal test verrouillable.",
            reasons=["Score global fort", "Agents alignes"],
            stop_loss=2380.0,
            take_profit_1=2432.0,
            take_profit_2=2450.0,
            source_note="Test.",
        )
        quality = DataQualitySnapshot(
            generated_at="2026-04-24T00:00:00+00:00",
            score=88,
            status="HIGH",
            summary="Qualite test.",
            missing_sources=[],
            stale_sources=[],
            weak_sources=[],
            contradictions=[],
            snapshots=[],
        )
        agents = [
            AgentResult("PriceActionAgent", "Market", "BUY", 70, 70, "Prix valide."),
            AgentResult("MacroAgent", "Macro", "BUY", 72, 75, "Macro valide."),
            AgentResult("TechnicalAgent", "Technical", "BUY", 68, 65, "Technique valide."),
        ]
        with TemporaryDirectory() as tmpdir:
            ledger_path = Path(tmpdir) / "trade_ledger.jsonl"
            summary = build_trade_ledger_summary(
                gold,
                recommendation,
                quality,
                agents,
                MarketRegimeAnalysis("Normal Macro", "NORMAL", 0, "neutre", "Normal.", []),
                [],
                [],
                path=ledger_path,
                now=datetime(2026, 4, 24, 10, tzinfo=timezone.utc),
            )
            self.assertEqual(summary.quality_gate_status, "VALIDATED")
            self.assertEqual(len(summary.active_trades), 1)
            plan = summary.active_trades[0]
            self.assertEqual(plan.reference_price, 2400.0)
            self.assertTrue(trade_plan_levels_are_valid(plan))
            self.assertGreaterEqual(plan.risk_reward_tp1, 1.5)
            self.assertLess(plan.stop_loss, plan.reference_price)
            self.assertGreater(plan.tp1, plan.reference_price)

            second = build_trade_ledger_summary(
                gold,
                recommendation,
                quality,
                agents,
                MarketRegimeAnalysis("Normal Macro", "NORMAL", 0, "neutre", "Normal.", []),
                [],
                [],
                path=ledger_path,
                now=datetime(2026, 4, 24, 10, 15, tzinfo=timezone.utc),
            )
            self.assertIn("Cooldown actif", second.quality_gate_reasons[0])
            self.assertEqual(second.active_trades[0].reference_price, 2400.0)
            self.assertEqual(second.active_trades[0].stop_loss, plan.stop_loss)

    def test_trade_ledger_evaluates_sl_outcome(self) -> None:
        gold = self.snapshot("XAU/USD", 2400.0, 2390.0)
        recommendation = TradeRecommendation(
            mode="Global",
            verdict="BUY",
            score=72,
            summary="Signal test.",
            reasons=["Test"],
            stop_loss=2380.0,
            take_profit_1=2432.0,
            take_profit_2=2450.0,
            source_note="Test.",
        )
        quality = DataQualitySnapshot("2026-04-24T00:00:00+00:00", 90, "HIGH", "OK", [], [], [], [], [])
        agents = [
            AgentResult("PriceActionAgent", "Market", "BUY", 70, 70, "Prix valide."),
            AgentResult("MacroAgent", "Macro", "BUY", 72, 75, "Macro valide."),
            AgentResult("TechnicalAgent", "Technical", "BUY", 68, 70, "Technique valide."),
        ]
        with TemporaryDirectory() as tmpdir:
            ledger_path = Path(tmpdir) / "trade_ledger.jsonl"
            initial = build_trade_ledger_summary(
                gold,
                recommendation,
                quality,
                agents,
                MarketRegimeAnalysis("Normal Macro", "NORMAL", 0, "neutre", "Normal.", []),
                [],
                [],
                path=ledger_path,
                now=datetime(2026, 4, 24, 10, tzinfo=timezone.utc),
            )
            self.assertTrue(initial.active_trades)
            gold.price = initial.active_trades[0].stop_loss - 1.0
            summary = build_trade_ledger_summary(
                gold,
                recommendation,
                quality,
                agents,
                MarketRegimeAnalysis("Normal Macro", "NORMAL", 0, "neutre", "Normal.", []),
                [],
                [],
                path=ledger_path,
                now=datetime(2026, 4, 24, 11, tzinfo=timezone.utc),
                allow_create=False,
            )
            self.assertEqual(summary.recent_trades[0].status, "sl_hit")
            self.assertEqual(summary.recent_trades[0].outcome, "loss")
            self.assertEqual(summary.recent_trades[0].record_type, "trade_exploitable")
            self.assertEqual(summary.recent_trades[0].r_multiple, -1.0)
            self.assertEqual(summary.losses, 1)
            self.assertEqual(summary.stats.expectancy_r, -1.0)
            self.assertEqual(summary.stats.trade_to_win_rate, 0.0)
            self.assertTrue(summary.post_mortems)
            self.assertIn("Loss", summary.post_mortems[0].summary)

    def test_trade_ledger_v3_builds_expired_post_mortem_and_stats(self) -> None:
        gold = self.snapshot("XAU/USD", 2400.0, 2390.0)
        recommendation = TradeRecommendation(
            mode="Global",
            verdict="BUY",
            score=72,
            summary="Signal test.",
            reasons=["Test"],
            stop_loss=2380.0,
            take_profit_1=2432.0,
            take_profit_2=2450.0,
            source_note="Test.",
        )
        quality = DataQualitySnapshot("2026-04-24T00:00:00+00:00", 90, "HIGH", "OK", [], [], [], [], [])
        agents = [
            AgentResult("PriceActionAgent", "Market", "BUY", 70, 70, "Prix valide."),
            AgentResult("MacroAgent", "Macro", "BUY", 72, 75, "Macro valide."),
            AgentResult("TechnicalAgent", "Technical", "BUY", 68, 70, "Technique valide."),
        ]
        with TemporaryDirectory() as tmpdir:
            ledger_path = Path(tmpdir) / "trade_ledger.jsonl"
            build_trade_ledger_summary(
                gold,
                recommendation,
                quality,
                agents,
                MarketRegimeAnalysis("Normal Macro", "NORMAL", 0, "neutre", "Normal.", []),
                [],
                [],
                path=ledger_path,
                now=datetime(2026, 4, 24, 10, tzinfo=timezone.utc),
            )
            summary = build_trade_ledger_summary(
                gold,
                recommendation,
                quality,
                agents,
                MarketRegimeAnalysis("Normal Macro", "NORMAL", 0, "neutre", "Normal.", []),
                [],
                [],
                path=ledger_path,
                now=datetime(2026, 4, 24, 17, tzinfo=timezone.utc),
                allow_create=False,
            )
            self.assertEqual(summary.recent_trades[0].status, "expired")
            self.assertEqual(summary.recent_trades[0].record_type, "trade_expire")
            self.assertEqual(summary.recent_trades[0].r_multiple, 0.0)
            self.assertEqual(summary.expired, 1)
            self.assertEqual(summary.stats.expectancy_r, 0.0)
            self.assertEqual(summary.stats.average_duration_minutes, 420)
            self.assertIn("Expired", summary.post_mortems[0].summary)

    def test_trade_ledger_phase2_uses_dynamic_validity_from_trigger(self) -> None:
        gold = self.snapshot("XAU/USD", 2400.0, 2390.0)
        recommendation = TradeRecommendation(
            mode="Global",
            verdict="BUY",
            score=72,
            summary="Signal test.",
            reasons=["Test"],
            stop_loss=2380.0,
            take_profit_1=2432.0,
            take_profit_2=2450.0,
            source_note="Test.",
        )
        quality = DataQualitySnapshot("2026-04-24T00:00:00+00:00", 90, "HIGH", "OK", [], [], [], [], [])
        agents = [
            AgentResult("PriceActionAgent", "Market", "BUY", 70, 70, "Prix valide."),
            AgentResult("MacroAgent", "Macro", "BUY", 72, 75, "Macro valide."),
            AgentResult("TechnicalAgent", "Technical", "BUY", 68, 70, "Technique valide."),
        ]
        with TemporaryDirectory() as tmpdir:
            ledger_path = Path(tmpdir) / "trade_ledger.jsonl"
            summary = build_trade_ledger_summary(
                gold,
                recommendation,
                quality,
                agents,
                MarketRegimeAnalysis("Normal Macro", "NORMAL", 0, "neutre", "Normal.", []),
                [],
                [],
                path=ledger_path,
                now=datetime(2026, 4, 24, 10, tzinfo=timezone.utc),
                technical_decision=self.technical_decision("BUY", price=2400.0),
            )
            plan = summary.active_trades[0]
            self.assertEqual(plan.max_valid_until, "2026-04-24T14:00:00+00:00")
            self.assertTrue(any("Validite dynamique: M15, 240 minutes" in item for item in plan.invalidation_rules))

    def test_trade_ledger_phase2_expired_cooldown_and_audit(self) -> None:
        gold = self.snapshot("XAU/USD", 2400.0, 2390.0)
        recommendation = TradeRecommendation(
            mode="Global",
            verdict="BUY",
            score=72,
            summary="Signal test.",
            reasons=["Test"],
            stop_loss=2380.0,
            take_profit_1=2432.0,
            take_profit_2=2450.0,
            source_note="Test.",
        )
        quality = DataQualitySnapshot("2026-04-24T00:00:00+00:00", 90, "HIGH", "OK", [], [], [], [], [])
        agents = [
            AgentResult("PriceActionAgent", "Market", "BUY", 70, 70, "Prix valide."),
            AgentResult("MacroAgent", "Macro", "BUY", 72, 75, "Macro valide."),
            AgentResult("TechnicalAgent", "Technical", "BUY", 68, 70, "Technique valide."),
        ]
        settings = UserSettings(
            active_agents=[
                "PriceActionAgent",
                "MacroAgent",
                "TechnicalAgent",
                "RiskManagerAgent",
            ],
            cooldown_after_expired_minutes=60,
        )
        with TemporaryDirectory() as tmpdir:
            ledger_path = Path(tmpdir) / "trade_ledger.jsonl"
            audit_path = Path(tmpdir) / "trade_gate_audit.jsonl"
            build_trade_ledger_summary(
                gold,
                recommendation,
                quality,
                agents,
                MarketRegimeAnalysis("Normal Macro", "NORMAL", 0, "neutre", "Normal.", []),
                [],
                [],
                path=ledger_path,
                now=datetime(2026, 4, 24, 10, tzinfo=timezone.utc),
                settings=settings,
                technical_decision=self.technical_decision("BUY", price=2400.0),
            )
            expired = build_trade_ledger_summary(
                gold,
                recommendation,
                quality,
                agents,
                MarketRegimeAnalysis("Normal Macro", "NORMAL", 0, "neutre", "Normal.", []),
                [],
                [],
                path=ledger_path,
                now=datetime(2026, 4, 24, 14, 10, tzinfo=timezone.utc),
                allow_create=False,
                settings=settings,
                technical_decision=self.technical_decision("BUY", price=2400.0),
            )
            self.assertEqual(expired.recent_trades[0].outcome, "expired")

            blocked = build_trade_ledger_summary(
                gold,
                recommendation,
                quality,
                agents,
                MarketRegimeAnalysis("Normal Macro", "NORMAL", 0, "neutre", "Normal.", []),
                [],
                [],
                path=ledger_path,
                now=datetime(2026, 4, 24, 14, 30, tzinfo=timezone.utc),
                settings=settings,
                technical_decision=self.technical_decision("BUY", price=2400.0),
            )
            self.assertIn("Cooldown actif", blocked.quality_gate_reasons[0])
            actions = [json.loads(line)["action"] for line in audit_path.read_text(encoding="utf-8").splitlines()]
            self.assertIn("trade_created", actions)
            self.assertIn("trade_expired", actions)
            self.assertIn("trade_refused_cooldown", actions)

    def test_passive_agents_do_not_replace_official_scoring(self) -> None:
        points = [PricePoint(timestamp=index, close=100 + index) for index in range(1, 15)]
        gold = SymbolSnapshot(
            symbol="XAU/USD",
            label="XAU/USD Spot",
            price=114.0,
            previous_close=112.0,
            change_abs=2.0,
            change_pct=1.79,
            period_change_pct=1.79,
            day_high=115.0,
            day_low=111.0,
            support=111.0,
            resistance=115.0,
            fetched_at="2026-04-24T00:00:00+00:00",
            points=points,
            intraday_points=points,
        )
        dxy = self.snapshot("DXY", 99.0, 100.0)
        us10y = self.snapshot("^TNX", 4.1, 4.2)
        analysis = AnalysisResult(
            bias="bullish",
            score=4,
            confidence=66,
            reasons=["Dollar faible"],
            bullish_news=[],
            bearish_news=[],
            neutral_news=[],
        )
        official = TradeRecommendation(
            mode="Global",
            verdict="BUY",
            score=63,
            summary="Verdict officiel test.",
            reasons=["Score global conserve"],
            stop_loss=110.0,
            take_profit_1=116.0,
            take_profit_2=118.0,
            source_note="Test.",
        )
        agents = build_passive_agent_results(
            gold,
            dxy,
            us10y,
            [],
            analysis,
            global_recommendation=official,
        )
        self.assertEqual(len(agents), 10)
        self.assertTrue(all(agent.experimental for agent in agents))
        self.assertFalse(any(agent.name == "ElliottWaveAgent" for agent in agents))
        self.assertEqual(official.verdict, "BUY")

    def test_orchestrator_v3_validates_aligned_buy(self) -> None:
        gold = self.snapshot("XAU/USD", 2400.0, 2390.0)
        legacy = TradeRecommendation(
            mode="Global",
            verdict="BUY",
            score=66,
            summary="Ancien moteur haussier.",
            reasons=["legacy"],
            stop_loss=2385.0,
            take_profit_1=2420.0,
            take_profit_2=2440.0,
            source_note="Test.",
        )
        agents = [
            AgentResult("TechnicalAgent", "Technical", "BUY", 72, 70, "Technique constructive."),
            AgentResult("MacroAgent", "Macro", "BUY", 74, 76, "Macro favorable."),
            AgentResult("GeopoliticalOilShockAgent", "Geopolitics & Flows", "NEUTRAL", 50, 65, "Pas de choc oil."),
            AgentResult("CorrelationAgent", "Market", "BUY", 68, 70, "Cross-assets favorables."),
            AgentResult("FlowPositioningAgent", "Geopolitics & Flows", "BUY", 62, 75, "Flux favorables."),
        ]
        quality = DataQualitySnapshot(
            generated_at="2026-04-24T10:00:00+00:00",
            score=90,
            status="HIGH",
            summary="Sources critiques ok.",
            missing_sources=[],
            stale_sources=[],
            weak_sources=[],
            contradictions=[],
        )
        recommendation, decision = build_orchestrator_decision(
            gold,
            legacy,
            agents,
            data_quality=quality,
            market_regime=MarketRegimeAnalysis("Normal Macro", "NORMAL", 0, "neutre", "Normal.", []),
            event_mode=EventModeAnalysis(False, 0, "NORMAL", "standard", 1.0, []),
            technical_decision=self.technical_decision("BUY", gold.price),
        )
        self.assertEqual(recommendation.verdict, "BUY")
        self.assertEqual(decision.status, "TRADE_BUY")
        self.assertGreaterEqual(decision.score, 60)
        self.assertEqual(decision.engine, "orchestrator_v3_dynamic")
        updated_agents = update_orchestrator_agent(agents, decision)
        self.assertFalse(any(agent.name == "OrchestratorAgent" for agent in updated_agents))

    def test_orchestrator_v3_forces_wait_on_strong_contradiction(self) -> None:
        gold = self.snapshot("XAU/USD", 2400.0, 2390.0)
        legacy = TradeRecommendation(
            mode="Global",
            verdict="BUY",
            score=64,
            summary="Ancien moteur haussier.",
            reasons=["legacy"],
            stop_loss=2385.0,
            take_profit_1=2420.0,
            take_profit_2=2440.0,
            source_note="Test.",
        )
        agents = [
            AgentResult("TechnicalAgent", "Technical", "BUY", 82, 72, "Technique haussiere."),
            AgentResult("MacroAgent", "Macro", "SELL", 80, 76, "Macro defavorable."),
            AgentResult("CorrelationAgent", "Market", "BUY", 70, 70, "Cross-assets favorables."),
            AgentResult("FlowPositioningAgent", "Geopolitics & Flows", "SELL", 35, 75, "Flux defavorables."),
        ]
        quality = DataQualitySnapshot(
            generated_at="2026-04-24T10:00:00+00:00",
            score=88,
            status="HIGH",
            summary="Sources critiques ok.",
            missing_sources=[],
            stale_sources=[],
            weak_sources=[],
            contradictions=[],
        )
        recommendation, decision = build_orchestrator_decision(
            gold,
            legacy,
            agents,
            data_quality=quality,
            market_regime=MarketRegimeAnalysis("Normal Macro", "NORMAL", 0, "neutre", "Normal.", []),
            event_mode=EventModeAnalysis(False, 0, "NORMAL", "standard", 1.0, []),
            technical_decision=self.technical_decision("BUY", gold.price),
        )
        self.assertEqual(recommendation.verdict, "WAIT")
        self.assertEqual(decision.status, "WAIT")
        self.assertTrue(any("Contradiction" in reason for reason in decision.quality_gate_reasons))

    def test_orchestrator_absorbs_single_contradiction_when_majority_is_clear(self) -> None:
        gold = self.snapshot("XAU/USD", 2400.0, 2390.0)
        legacy = TradeRecommendation(
            mode="Global",
            verdict="BUY",
            score=56,
            summary="Ancien moteur haussier.",
            reasons=["legacy"],
            stop_loss=2385.0,
            take_profit_1=2410.0,
            take_profit_2=2440.0,
            source_note="Test.",
        )
        agents = [
            AgentResult("TechnicalAgent", "Technical", "BUY", 82, 72, "Technique haussiere."),
            AgentResult("MacroAgent", "Macro", "SELL", 80, 76, "Macro defavorable."),
            AgentResult("GeopoliticalOilShockAgent", "Geopolitics & Flows", "BUY", 66, 70, "Risque favorable."),
            AgentResult("CorrelationAgent", "Market", "BUY", 68, 70, "Cross-assets favorables."),
            AgentResult("FlowPositioningAgent", "Geopolitics & Flows", "BUY", 62, 75, "Flux favorables."),
        ]
        quality = DataQualitySnapshot(
            generated_at="2026-04-24T10:00:00+00:00",
            score=90,
            status="HIGH",
            summary="Sources critiques ok.",
            missing_sources=[],
            stale_sources=[],
            weak_sources=[],
            contradictions=[],
        )
        recommendation, decision = build_orchestrator_decision(
            gold,
            legacy,
            agents,
            data_quality=quality,
            market_regime=MarketRegimeAnalysis("Normal Macro", "NORMAL", 0, "neutre", "Normal.", []),
            event_mode=EventModeAnalysis(False, 0, "NORMAL", "standard", 1.0, []),
            technical_decision=self.technical_decision("BUY", gold.price),
        )
        self.assertEqual(recommendation.verdict, "WAIT")
        self.assertEqual(decision.status, "WAIT")
        self.assertTrue(any("Contradiction forte" in reason for reason in decision.quality_gate_reasons))

    def test_orchestrator_allows_degraded_quality_and_soft_event_when_direction_clear(self) -> None:
        gold = self.snapshot("XAU/USD", 2400.0, 2390.0)
        legacy = TradeRecommendation(
            mode="Global",
            verdict="SELL",
            score=61,
            summary="Ancien moteur baissier.",
            reasons=["legacy"],
            stop_loss=2415.0,
            take_profit_1=2375.0,
            take_profit_2=2355.0,
            source_note="Test.",
        )
        agents = [
            AgentResult("TechnicalAgent", "Technical", "SELL", 62, 70, "Technique baissiere."),
            AgentResult("MacroAgent", "Macro", "SELL", 64, 76, "Macro defavorable."),
            AgentResult("CorrelationAgent", "Market", "SELL", 35, 70, "Cross-assets defavorables.", status="PASSIVE"),
            AgentResult("FlowPositioningAgent", "Geopolitics & Flows", "NEUTRAL", 46, 75, "Flux mixtes."),
            AgentResult("RiskManagerAgent", "Decision", "CAUTION", 58, 72, "Risque surveille."),
        ]
        quality = DataQualitySnapshot(
            generated_at="2026-04-24T10:00:00+00:00",
            score=66,
            status="DEGRADED",
            summary="Sources secondaires degradees.",
            missing_sources=[],
            stale_sources=["World Gold Council ETF flows"],
            weak_sources=["Google News RSS / fallback feeds"],
            contradictions=[],
        )
        recommendation, decision = build_orchestrator_decision(
            gold,
            legacy,
            agents,
            data_quality=quality,
            market_regime=MarketRegimeAnalysis("Normal Macro", "NORMAL", 0, "neutre", "Normal.", []),
            event_mode=EventModeAnalysis(True, 35, "ACTIF", "surveillance", 1.5, ["volume eleve"]),
            technical_decision=self.technical_decision("SELL", gold.price),
        )
        self.assertEqual(recommendation.verdict, "WATCH_SELL")
        self.assertEqual(decision.status, "WATCH_SELL")
        self.assertTrue(any("Source quality limitee" in reason for reason in decision.quality_gate_reasons))
        self.assertTrue(any("Mode event surveille" in reason for reason in decision.quality_gate_reasons))

    def test_orchestrator_v3_watches_when_technical_trigger_missing(self) -> None:
        gold = self.snapshot("XAU/USD", 2400.0, 2390.0)
        legacy = TradeRecommendation(
            mode="Global",
            verdict="BUY",
            score=66,
            summary="Ancien moteur haussier.",
            reasons=["legacy"],
            stop_loss=2385.0,
            take_profit_1=2420.0,
            take_profit_2=2440.0,
            source_note="Test.",
        )
        agents = [
            AgentResult("TechnicalAgent", "Technical", "BUY", 72, 70, "Technique constructive."),
            AgentResult("MacroAgent", "Macro", "BUY", 74, 76, "Macro favorable."),
            AgentResult("CorrelationAgent", "Market", "BUY", 68, 70, "Cross-assets favorables."),
            AgentResult("FlowPositioningAgent", "Geopolitics & Flows", "BUY", 62, 75, "Flux favorables."),
        ]
        quality = DataQualitySnapshot(
            generated_at="2026-04-24T10:00:00+00:00",
            score=90,
            status="HIGH",
            summary="Sources critiques ok.",
            missing_sources=[],
            stale_sources=[],
            weak_sources=[],
            contradictions=[],
        )
        recommendation, decision = build_orchestrator_decision(
            gold,
            legacy,
            agents,
            data_quality=quality,
            market_regime=MarketRegimeAnalysis("Normal Macro", "NORMAL", 0, "neutre", "Normal.", []),
            event_mode=EventModeAnalysis(False, 0, "NORMAL", "standard", 1.0, []),
            technical_decision=None,
        )
        self.assertEqual(recommendation.verdict, "WATCH_BUY")
        self.assertEqual(decision.status, "WATCH_BUY")
        self.assertTrue(any("TechnicalDecisionEngine absent" in reason for reason in decision.quality_gate_reasons))

    def test_orchestrator_v3_blocks_trade_when_preflight_blocks(self) -> None:
        gold = self.snapshot("XAU/USD", 2400.0, 2390.0)
        legacy = TradeRecommendation(
            mode="Global",
            verdict="SELL",
            score=66,
            summary="Ancien moteur baissier.",
            reasons=["legacy"],
            stop_loss=2415.0,
            take_profit_1=2375.0,
            take_profit_2=2355.0,
            source_note="Test.",
        )
        agents = [
            AgentResult("TechnicalAgent", "Technical", "SELL", 72, 70, "Technique baissiere."),
            AgentResult("MacroAgent", "Macro", "SELL", 74, 76, "Macro defavorable."),
            AgentResult("CorrelationAgent", "Market", "SELL", 35, 70, "Cross-assets defavorables."),
        ]
        quality = DataQualitySnapshot(
            generated_at="2026-04-24T10:00:00+00:00",
            score=88,
            status="SOURCE_STALE",
            summary="Prix principal stale.",
            missing_sources=[],
            stale_sources=["Investing.com XAU/USD"],
            weak_sources=[],
            contradictions=[],
            preflight=PreflightCheck(
                generated_at="2026-04-24T10:00:00+00:00",
                status="SOURCE_STALE",
                summary="Prix principal stale.",
                trade_blocked=True,
                blockers=["Investing.com XAU/USD stale"],
                warnings=[],
            ),
        )
        recommendation, decision = build_orchestrator_decision(
            gold,
            legacy,
            agents,
            data_quality=quality,
            market_regime=MarketRegimeAnalysis("Normal Macro", "NORMAL", 0, "neutre", "Normal.", []),
            event_mode=EventModeAnalysis(False, 0, "NORMAL", "standard", 1.0, []),
            technical_decision=self.technical_decision("SELL", gold.price),
        )
        self.assertEqual(recommendation.verdict, "NO_TRADE")
        self.assertEqual(decision.status, "NO_TRADE")
        self.assertTrue(any("Preflight bloquant" in reason for reason in decision.quality_gate_reasons))

    def test_trade_gate_blocks_weak_score_even_without_audit_agents(self) -> None:
        gold = self.snapshot("XAU/USD", 2400.0, 2390.0)
        recommendation = TradeRecommendation(
            mode="Global",
            verdict="BUY",
            score=61,
            summary="Signal verrouillable avec warnings.",
            reasons=["Score exploitable"],
            stop_loss=2385.0,
            take_profit_1=2420.0,
            take_profit_2=2440.0,
            source_note="Test.",
        )
        quality = DataQualitySnapshot(
            generated_at="2026-04-24T10:00:00+00:00",
            score=66,
            status="DEGRADED",
            summary="Sources secondaires degradees.",
            missing_sources=[],
            stale_sources=["World Gold Council ETF flows"],
            weak_sources=["Google News RSS / fallback feeds"],
            contradictions=[],
        )
        agents = [
            AgentResult("TechnicalAgent", "Technical", "BUY", 64, 70, "Technique valide."),
            AgentResult("MacroAgent", "Macro", "BUY", 62, 76, "Macro valide."),
            AgentResult("RiskManagerAgent", "Decision", "CAUTION", 55, 72, "Risque surveille."),
        ]
        with TemporaryDirectory() as tmpdir:
            ledger_path = Path(tmpdir) / "trade_ledger.jsonl"
            summary = build_trade_ledger_summary(
                gold,
                recommendation,
                quality,
                agents,
                MarketRegimeAnalysis("Normal Macro", "NORMAL", 0, "neutre", "Normal.", []),
                [],
                [],
                path=ledger_path,
                now=datetime(2026, 4, 24, 10, tzinfo=timezone.utc),
            )
            self.assertEqual(summary.quality_gate_status, "WAIT")
            self.assertFalse(summary.active_trades)
            self.assertTrue(any("Score global insuffisant" in reason for reason in summary.quality_gate_reasons))

    def test_trade_gate_blocks_legacy_aggressive_profile_below_v4_threshold(self) -> None:
        gold = self.snapshot("XAU/USD", 2400.0, 2390.0)
        recommendation = TradeRecommendation(
            mode="Global",
            verdict="BUY",
            score=56,
            summary="Signal verrouillable en profil agressif.",
            reasons=["Majorite claire"],
            stop_loss=2385.0,
            take_profit_1=2410.0,
            take_profit_2=2430.0,
            source_note="Test.",
        )
        quality = DataQualitySnapshot(
            generated_at="2026-04-24T10:00:00+00:00",
            score=66,
            status="DEGRADED",
            summary="Sources secondaires degradees.",
            missing_sources=[],
            stale_sources=["World Gold Council ETF flows"],
            weak_sources=[],
            contradictions=[],
        )
        agents = [
            AgentResult("PriceActionAgent", "Market", "BUY", 60, 70, "Prix favorable."),
            AgentResult("TechnicalAgent", "Technical", "BUY", 64, 70, "Technique valide."),
            AgentResult("MacroAgent", "Macro", "BUY", 62, 76, "Macro valide."),
            AgentResult("CorrelationAgent", "Market", "SELL", 58, 70, "Contre-signal isole."),
            AgentResult("FlowPositioningAgent", "Geopolitics & Flows", "NEUTRAL", 50, 70, "Flux neutres."),
        ]
        with TemporaryDirectory() as tmpdir:
            ledger_path = Path(tmpdir) / "trade_ledger.jsonl"
            summary = build_trade_ledger_summary(
                gold,
                recommendation,
                quality,
                agents,
                MarketRegimeAnalysis("Normal Macro", "NORMAL", 0, "neutre", "Normal.", []),
                [],
                [],
                path=ledger_path,
                now=datetime(2026, 4, 24, 10, tzinfo=timezone.utc),
            )
            self.assertEqual(summary.quality_gate_status, "WAIT")
            self.assertFalse(summary.active_trades)
            self.assertTrue(any("Score global insuffisant" in reason for reason in summary.quality_gate_reasons))

    def test_orchestrator_has_no_elliott_component(self) -> None:
        gold = self.snapshot("XAU/USD", 2400.0, 2390.0)
        legacy = TradeRecommendation(
            mode="Global",
            verdict="BUY",
            score=66,
            summary="Ancien moteur haussier.",
            reasons=["legacy"],
            stop_loss=2385.0,
            take_profit_1=2420.0,
            take_profit_2=2440.0,
            source_note="Test.",
        )
        agents = [
            AgentResult("TechnicalAgent", "Technical", "BUY", 72, 70, "Technique constructive."),
            AgentResult("MacroAgent", "Macro", "BUY", 74, 76, "Macro favorable."),
            AgentResult("GeopoliticalOilShockAgent", "Geopolitics & Flows", "NEUTRAL", 50, 65, "Pas de choc oil."),
            AgentResult("CorrelationAgent", "Market", "BUY", 68, 70, "Cross-assets favorables."),
            AgentResult("FlowPositioningAgent", "Geopolitics & Flows", "BUY", 62, 75, "Flux favorables."),
        ]
        quality = DataQualitySnapshot(
            generated_at="2026-04-24T10:00:00+00:00",
            score=90,
            status="HIGH",
            summary="Sources critiques ok.",
            missing_sources=[],
            stale_sources=[],
            weak_sources=[],
            contradictions=[],
        )
        recommendation, decision = build_orchestrator_decision(
            gold,
            legacy,
            agents,
            data_quality=quality,
            market_regime=MarketRegimeAnalysis("Normal Macro", "NORMAL", 0, "neutre", "Normal.", []),
            event_mode=EventModeAnalysis(False, 0, "NORMAL", "standard", 1.0, []),
            technical_decision=self.technical_decision("BUY", gold.price),
        )
        self.assertEqual(recommendation.verdict, "BUY")
        self.assertFalse(any(component.key == "elliott" for component in decision.components))

    def test_official_macro_rates_compare_yahoo_tnx_to_fred(self) -> None:
        dgs10 = self.snapshot("DGS10", 4.50, 4.45)
        yahoo_tnx = self.snapshot("^TNX", 4.55, 4.50)
        rates = build_official_macro_rates(dgs10, None, None, None, yahoo_tnx)
        self.assertIs(rates.dgs10, dgs10)
        self.assertAlmostEqual(rates.yahoo_tnx_gap_bps, 5.0)

    def test_cftc_positioning_calculates_weekly_net_changes(self) -> None:
        rows = [
            {
                "Market_and_Exchange_Names": "GOLD - COMMODITY EXCHANGE INC.",
                "Report_Date_as_YYYY-MM-DD": "2026-04-14",
                "CFTC_Contract_Market_Code": "088691",
                "Open_Interest_All": "360000",
                "Prod_Merc_Positions_Long_All": "12000",
                "Prod_Merc_Positions_Short_All": "31000",
                "Swap_Positions_Long_All": "28000",
                "Swap__Positions_Short_All": "208000",
                "Swap__Positions_Spread_All": "15000",
                "M_Money_Positions_Long_All": "118000",
                "M_Money_Positions_Short_All": "32000",
                "M_Money_Positions_Spread_All": "33000",
                "NonRept_Positions_Long_All": "51000",
                "NonRept_Positions_Short_All": "13500",
            },
            {
                "Market_and_Exchange_Names": "GOLD - COMMODITY EXCHANGE INC.",
                "Report_Date_as_YYYY-MM-DD": "2026-04-21",
                "CFTC_Contract_Market_Code": "088691",
                "Open_Interest_All": "365842",
                "Prod_Merc_Positions_Long_All": "12633",
                "Prod_Merc_Positions_Short_All": "33051",
                "Swap_Positions_Long_All": "28115",
                "Swap__Positions_Short_All": "210637",
                "Swap__Positions_Spread_All": "15513",
                "M_Money_Positions_Long_All": "123681",
                "M_Money_Positions_Short_All": "30705",
                "M_Money_Positions_Spread_All": "33896",
                "NonRept_Positions_Long_All": "52223",
                "NonRept_Positions_Short_All": "13289",
            },
        ]
        positioning = build_cftc_positioning_from_rows(rows, "https://www.cftc.gov/example.zip")
        self.assertIsNotNone(positioning)
        assert positioning is not None
        self.assertEqual(positioning.report_date, "2026-04-21")
        self.assertEqual(positioning.managed_money_net, 92976)
        self.assertEqual(positioning.managed_money_net_change, 6976)
        self.assertEqual(positioning.open_interest_change, 5842)
        self.assertEqual(positioning.producer_net, -20418)
        self.assertGreater(positioning.score, 50)

    def test_wgc_etf_flows_analysis_builds_global_and_fund_rows(self) -> None:
        archive = {
            "regional": {
                "Weekly": {
                    "asOfDate": "2026-04-24",
                    "data": {
                        "columns": [],
                        "0": ["Total", "607.1", "-1435.8", "4136.64", "-10.54", "-0.25"],
                    },
                },
                "Monthly": {
                    "asOfDate": "2026-04-24",
                    "data": {
                        "columns": [],
                        "0": ["Total", "607.1", "-11740.6", "4091.85", "-84.26", "-2.02"],
                    },
                },
            },
            "bottom10_ca": {
                "Weekly": {
                    "asOfDate": "2026-04-24",
                    "data": {
                        "columns": [],
                        "0": ["SPDR Gold Shares", "US", "-2137.0", "1046.35", "-14.09", "-1.33"],
                    },
                },
                "Monthly": {
                    "asOfDate": "2026-04-24",
                    "data": {
                        "columns": [],
                        "0": ["SPDR Gold Shares", "US", "-8426.8", "1046.90", "-54.13", "-4.92"],
                        "1": ["iShares Gold Trust", "US", "-3677.6", "475.96", "-23.27", "-4.66"],
                    },
                },
            },
            "top10_ca": {},
        }
        analysis = build_wgc_etf_flows_analysis(archive)
        self.assertIsNotNone(analysis)
        assert analysis is not None
        self.assertEqual(analysis.status, "outflows")
        self.assertLess(analysis.score, 50)
        self.assertEqual(analysis.global_weekly_demand_tonnes, -10.54)
        self.assertEqual(analysis.holdings[0].ticker, "GLD")
        self.assertEqual(analysis.holdings[0].weekly_flow_tonnes, -14.09)
        self.assertEqual(analysis.holdings[1].ticker, "IAU")
        self.assertEqual(analysis.holdings[1].monthly_flow_tonnes, -23.27)

    def test_ishares_iau_parser_estimates_daily_and_weekly_flows(self) -> None:
        page_html = """
        <div>Shares Outstanding as of Apr 29, 2026 823,600,000</div>
        <div>Ounces in Trust as of Apr 29, 2026 15,500,217.67</div>
        <div>Tonnes in Trust as of Apr 29, 2026 482.11</div>
        """
        spreadsheet_xml = """
        <ss:Workbook>
          <ss:Row><ss:Cell><ss:Data>As Of</ss:Data></ss:Cell><ss:Cell><ss:Data>NAV</ss:Data></ss:Cell><ss:Cell><ss:Data>--</ss:Data></ss:Cell><ss:Cell><ss:Data>Shares Outstanding</ss:Data></ss:Cell></ss:Row>
          <ss:Row><ss:Cell><ss:Data>Apr 29, 2026</ss:Data></ss:Cell><ss:Cell><ss:Data>85</ss:Data></ss:Cell><ss:Cell><ss:Data>--</ss:Data></ss:Cell><ss:Cell><ss:Data>823600000</ss:Data></ss:Cell></ss:Row>
          <ss:Row><ss:Cell><ss:Data>Apr 28, 2026</ss:Data></ss:Cell><ss:Cell><ss:Data>85</ss:Data></ss:Cell><ss:Cell><ss:Data>--</ss:Data></ss:Cell><ss:Cell><ss:Data>823000000</ss:Data></ss:Cell></ss:Row>
          <ss:Row><ss:Cell><ss:Data>Apr 27, 2026</ss:Data></ss:Cell><ss:Cell><ss:Data>85</ss:Data></ss:Cell><ss:Cell><ss:Data>--</ss:Data></ss:Cell><ss:Cell><ss:Data>823000000</ss:Data></ss:Cell></ss:Row>
          <ss:Row><ss:Cell><ss:Data>Apr 24, 2026</ss:Data></ss:Cell><ss:Cell><ss:Data>85</ss:Data></ss:Cell><ss:Cell><ss:Data>--</ss:Data></ss:Cell><ss:Cell><ss:Data>822400000</ss:Data></ss:Cell></ss:Row>
          <ss:Row><ss:Cell><ss:Data>Apr 23, 2026</ss:Data></ss:Cell><ss:Cell><ss:Data>85</ss:Data></ss:Cell><ss:Cell><ss:Data>--</ss:Data></ss:Cell><ss:Cell><ss:Data>822400000</ss:Data></ss:Cell></ss:Row>
          <ss:Row><ss:Cell><ss:Data>Apr 22, 2026</ss:Data></ss:Cell><ss:Cell><ss:Data>85</ss:Data></ss:Cell><ss:Cell><ss:Data>--</ss:Data></ss:Cell><ss:Cell><ss:Data>821600000</ss:Data></ss:Cell></ss:Row>
        </ss:Workbook>
        """
        record = parse_ishares_iau_official_data(page_html, spreadsheet_xml)
        self.assertIsNotNone(record)
        assert record is not None
        self.assertEqual(record.ticker, "IAU")
        self.assertEqual(record.holdings_tonnes, 482.11)
        self.assertGreater(record.daily_flow_tonnes or 0, 0)
        self.assertGreater(record.weekly_flow_tonnes or 0, 0)
        self.assertEqual(record.source_name, "BlackRock iShares official page")

    def test_event_facts_extract_concrete_market_chain(self) -> None:
        item = NewsItem(
            title="Iran tensions rise near Strait of Hormuz as oil shipping risk grows",
            source="Reuters",
            link="https://example.com",
            published_at="2026-04-24T00:00:00+00:00",
            category="geopolitical",
            score=2,
            score_reasons=["bullish:geopolitical risk"],
        )
        facts = build_event_facts([item])
        self.assertEqual(len(facts), 1)
        self.assertIn("Iran", facts[0].actors)
        self.assertIn("Hormuz", facts[0].locations)
        self.assertIn("Oil shock", facts[0].themes)
        self.assertEqual(facts[0].confirmation_level, "agence/finance majeure")
        self.assertIn("WTI/Brent", facts[0].market_chain)

    def test_political_statements_prioritize_official_sources(self) -> None:
        items = [
            NewsItem(
                title="President Trump and the First Lady welcome foreign dignitaries for a state dinner",
                source="News - The White House",
                link="https://www.whitehouse.gov/news/state-dinner",
                published_at="2026-04-24T00:02:00+00:00",
                category="political_white_house",
                score=0,
                score_reasons=[],
            ),
            NewsItem(
                title="President Trump says Iran oil sanctions remain possible",
                source="White House",
                link="https://www.whitehouse.gov/news/example",
                published_at="2026-04-24T00:00:00+00:00",
                category="political_white_house",
                score=-1,
                score_reasons=["bearish:strong dollar"],
            ),
            NewsItem(
                title="Blog claims Trump may comment on gold soon",
                source="Example Blog",
                link="https://example.com/blog",
                published_at="2026-04-24T00:01:00+00:00",
                category="political_trump_iran",
                score=1,
                score_reasons=["bullish:geopolitical risk"],
            ),
        ]
        statements = build_political_statements(items)
        self.assertEqual(statements[0].source_tier, 1)
        self.assertEqual(statements[0].validation_level, "official_confirmed")
        self.assertIn("Iran / Hormuz / Oil", statements[0].theme)
        self.assertIn("WTI/Brent", statements[0].market_chain)

    def test_trump_agent_uses_structured_political_statement(self) -> None:
        points = [PricePoint(timestamp=index, close=100 + index) for index in range(1, 15)]
        gold = SymbolSnapshot(
            symbol="XAU/USD",
            label="XAU/USD Spot",
            price=114.0,
            previous_close=112.0,
            change_abs=2.0,
            change_pct=1.79,
            period_change_pct=1.79,
            day_high=115.0,
            day_low=111.0,
            support=111.0,
            resistance=115.0,
            fetched_at="2026-04-24T00:00:00+00:00",
            points=points,
            intraday_points=points,
        )
        dxy = self.snapshot("DXY", 99.0, 100.0)
        us10y = self.snapshot("^TNX", 4.1, 4.2)
        analysis = AnalysisResult(
            bias="neutral",
            score=0,
            confidence=60,
            reasons=[],
            bullish_news=[],
            bearish_news=[],
            neutral_news=[],
        )
        statement = PoliticalStatement(
            title="President Trump says new sanctions are ready",
            source="White House",
            source_url="https://www.whitehouse.gov/news/",
            published_at="2026-04-24T00:00:00+00:00",
            theme="Iran / Hormuz / Oil",
            validation_level="official_confirmed",
            source_tier=1,
            gold_impact="mixte",
            oil_impact="haussier",
            usd_impact="haussier possible",
            market_chain="Declaration -> sanctions -> oil/USD -> gold mixte.",
            score=-1,
            confidence=90,
        )
        agents = build_passive_agent_results(
            gold,
            dxy,
            us10y,
            [],
            analysis,
            political_statements=[statement],
        )
        trump_agent = next(agent for agent in agents if agent.name == "TrumpPoliticalStatementsAgent")
        self.assertEqual(trump_agent.confidence, 90)
        self.assertIn("official_confirmed", trump_agent.summary)
        self.assertIn("Declaration -> sanctions", trump_agent.evidence[2].value)

    def test_phase4_agents_use_price_action_and_directional_regime(self) -> None:
        gold = self.snapshot("XAU/USD", 2425.0, 2400.0)
        gold.day_low = 2380.0
        gold.day_high = 2420.0
        gold.support = 2380.0
        gold.resistance = 2420.0
        dxy = self.snapshot("DXY", 101.0, 100.0)
        us10y = self.snapshot("^TNX", 4.3, 4.2)
        analysis = AnalysisResult("neutral", 0, 60, [], [], [], [])
        regime = MarketRegimeAnalysis(
            "Hormuz / Oil Shock",
            "ACTIF",
            78,
            "baissier court terme",
            "Oil shock actif.",
            ["WTI confirme."],
        )
        agents = build_passive_agent_results(gold, dxy, us10y, [], analysis, market_regime=regime)
        price_agent = next(agent for agent in agents if agent.name == "PriceActionAgent")
        geo_agent = next(agent for agent in agents if agent.name == "GeopoliticalOilShockAgent")
        self.assertIn("PriceActionAgent", price_agent.summary)
        self.assertTrue(any("Camarilla" in evidence.value for evidence in price_agent.evidence))
        self.assertEqual(geo_agent.bias, "SELL")


class LocalFreeContextTests(unittest.TestCase):
    def snapshot(self, symbol: str, price: float, previous: float) -> SymbolSnapshot:
        points = [
            PricePoint(timestamp=1, close=previous),
            PricePoint(timestamp=2, close=price),
        ]
        return SymbolSnapshot(
            symbol=symbol,
            label=symbol,
            price=price,
            previous_close=previous,
            change_abs=price - previous,
            change_pct=((price - previous) / previous) * 100 if previous else 0.0,
            period_change_pct=((price - previous) / previous) * 100 if previous else 0.0,
            day_high=max(price, previous),
            day_low=min(price, previous),
            support=min(price, previous),
            resistance=max(price, previous),
            fetched_at="2026-04-24T00:00:00+00:00",
            points=points,
        )

    def test_cross_asset_context_scores_favorable_gold_setup(self) -> None:
        dxy = self.snapshot("DXY", 99.0, 100.0)
        tips = self.snapshot("DFII10", 1.90, 1.95)
        usdjpy = self.snapshot("JPY=X", 150.0, 151.0)
        silver = self.snapshot("SI=F", 30.5, 30.0)
        gvz = self.snapshot("^GVZ", 25.0, 24.0)
        vix = self.snapshot("^VIX", 20.0, 18.0)
        context = build_cross_asset_analysis(dxy, tips, usdjpy, silver, gvz, vix)
        self.assertGreaterEqual(context.score, 62)
        self.assertEqual(context.status, "favorable")
        self.assertEqual(context.verdict, "BUY renforce")
        self.assertTrue(context.confirmations)
        self.assertTrue(context.signals)
        self.assertTrue(any(signal.instrument == "DXY" and signal.signal == "BUY" for signal in context.signals))

    def test_hormuz_oil_shock_regime_detects_oil_dollar_pressure(self) -> None:
        gold = self.snapshot("XAU/USD", 2388.0, 2400.0)
        dxy = self.snapshot("DXY", 100.6, 100.0)
        us10y = self.snapshot("^TNX", 4.26, 4.20)
        wti = self.snapshot("CL=F", 84.0, 80.0)
        brent = self.snapshot("BZ=F", 88.0, 84.0)
        news = [
            NewsItem(
                title="Iran tensions rise near Strait of Hormuz as oil shipping risk grows",
                source="Example",
                link="https://example.com",
                published_at="2026-04-25T00:00:00+00:00",
                category="geopolitical",
                score=2,
                score_reasons=["bullish:geopolitical risk"],
            )
        ]
        regime = build_market_regime_analysis(gold, dxy, us10y, news, wti=wti, brent=brent)
        self.assertEqual(regime.name, "Hormuz / Oil Shock")
        self.assertEqual(regime.status, "ACTIF")
        self.assertIn("oil", regime.summary.lower())

    def test_event_mode_activates_on_volume_spike(self) -> None:
        gold = self.snapshot("XAU/USD", 2400.0, 2398.0)
        readings = [
            TechnicalReading(
                timeframe="5m",
                close=2400.0,
                ema20=2399.0,
                ema50=2398.0,
                ema100=2397.0,
                ema200=2396.0,
                rsi7=70.0,
                macd_line=1.0,
                macd_signal=0.4,
                macd_histogram=0.6,
                volume_ratio=2.5,
                atr14=6.0,
                score=4.0,
                verdict="BUY",
                reasons=["Test"],
            )
        ]
        event = build_event_mode_analysis(gold, readings, None, None)
        self.assertIsInstance(event, EventModeAnalysis)
        self.assertTrue(event.active)
        self.assertEqual(event.stop_multiplier, 1.5)

    def test_technical_decision_engine_builds_watch_or_trade_direction(self) -> None:
        gold = self.snapshot("XAU/USD", 2400.0, 2390.0)
        readings = [
            TechnicalReading(tf, 2400.0, 2398.0, 2392.0, 2386.0, 2375.0, 61.0, 1.0, 0.4, 0.6, 1.3, 7.0, 5.0, "BUY", ["trend"])
            for tf in ["1D", "4H", "1H", "15m", "5m"]
        ]
        decision = build_technical_decision(gold, readings, 2400.0)
        self.assertIn(decision.direction, {"BUY", "WATCH_BUY"})
        self.assertEqual(decision.structure, "trend")
        self.assertIn("cloture M15", decision.trigger)
        self.assertGreater(decision.tp3, decision.tp2)

    def test_scenario_engine_builds_watch_buy_with_trigger_and_validation(self) -> None:
        gold = self.snapshot("XAU/USD", 2400.0, 2390.0)
        technical_decision = TechnicalDecision(
            status="WATCH",
            direction="WATCH_BUY",
            structure="pullback",
            score=66,
            confidence=68,
            trigger="BUY seulement si cloture M15 au-dessus de 2405.00.",
            invalidation="Invalidation BUY sous 2388.00.",
            entry_zone_low=2398.0,
            entry_zone_high=2402.0,
            stop_loss=2388.0,
            tp1=2412.0,
            tp2=2424.0,
            tp3=2440.0,
            reasons=["Pullback haussier surveille."],
            contradictions=[],
        )
        global_recommendation = TradeRecommendation(
            "Global",
            "BUY",
            64,
            "Biais haussier sous confirmation.",
            ["Test"],
            2388.0,
            2412.0,
            2424.0,
            "test",
        )
        fundamental = TradeRecommendation(
            "Fondamental",
            "BUY",
            70,
            "Macro confirme le biais.",
            ["Test"],
            2388.0,
            2412.0,
            2424.0,
            "test",
        )
        plan = build_scenario_plan(gold, technical_decision, global_recommendation, fundamental)
        self.assertEqual(plan.status, "WATCH_BUY")
        self.assertEqual(plan.bias, "BUY")
        self.assertIn("2405.00", plan.trigger)
        self.assertTrue(any("Macro/Fondamental confirme BUY" in item for item in plan.validations))
        self.assertTrue(plan.confirmation_required)

    def test_scenario_engine_records_news_contradiction(self) -> None:
        gold = self.snapshot("XAU/USD", 2400.0, 2390.0)
        technical_decision = TechnicalDecision(
            status="WATCH",
            direction="WATCH_BUY",
            structure="breakout",
            score=64,
            confidence=66,
            trigger="BUY seulement si cloture M15 au-dessus de 2405.00.",
            invalidation="Invalidation BUY sous 2388.00.",
            entry_zone_low=2398.0,
            entry_zone_high=2402.0,
            stop_loss=2388.0,
            tp1=2412.0,
            tp2=2424.0,
            tp3=2440.0,
            reasons=[],
            contradictions=[],
        )
        global_recommendation = TradeRecommendation(
            "Global",
            "BUY",
            63,
            "Biais haussier sous confirmation.",
            [],
            2388.0,
            2412.0,
            2424.0,
            "test",
        )
        fact = EventFact(
            title="Oil squeeze draws liquidity into crude while gold slips",
            source="Reuters",
            source_url="https://example.com",
            published_at="2026-04-24T10:00:00+00:00",
            category="geopolitical",
            actors=["US", "Iran"],
            locations=["Hormuz"],
            themes=["oil"],
            confirmation_level="confirmed_secondary",
            market_chain="Oil up, dollar up, gold liquidity pressure",
            gold_impact="Oil et dollar captent la liquidite, pression possible sur XAU/USD.",
            impact_bias="SELL",
            confidence=82,
        )
        plan = build_scenario_plan(gold, technical_decision, global_recommendation, event_facts=[fact])
        self.assertEqual(plan.status, "WATCH_BUY")
        self.assertTrue(any("NewsFact contredit BUY" in item for item in plan.contradictions))

    def test_phase27_payload_excludes_elliott_and_keeps_technical_decision(self) -> None:
        gold = self.snapshot("XAU/USD", 2400.0, 2390.0)
        dxy = self.snapshot("DXY", 99.0, 100.0)
        us10y = self.snapshot("^TNX", 4.1, 4.2)
        analysis = AnalysisResult("bullish", 4, 66, ["Dollar faible"], [], [], [])
        technical_decision = TechnicalDecision(
            status="TRADE_READY",
            direction="BUY",
            structure="trend",
            score=72,
            confidence=74,
            trigger="BUY seulement si cloture M15 au-dessus de 2405.00.",
            invalidation="Invalidation BUY sous 2388.00.",
            entry_zone_low=2398.0,
            entry_zone_high=2401.0,
            stop_loss=2388.0,
            tp1=2412.0,
            tp2=2424.0,
            tp3=2440.0,
            reasons=["Alignement multi-timeframe valide."],
            contradictions=[],
        )
        trade = TradePlan(
            trade_id="test",
            created_at="2026-04-24T10:00:00+00:00",
            updated_at="2026-04-24T10:00:00+00:00",
            status="active",
            direction="BUY",
            entry_type="market_reference",
            reference_price=2400.0,
            entry_zone_low=2398.0,
            entry_zone_high=2401.0,
            stop_loss=2388.0,
            tp1=2412.0,
            tp2=2424.0,
            tp3=2440.0,
            risk_reward_tp1=1.0,
            risk_reward_tp2=2.0,
            risk_reward_tp3=3.0,
            max_valid_until="2026-04-24T16:00:00+00:00",
            source_signal_id="phase27",
            global_score_at_creation=72,
            data_quality_score=80,
            confidence_score=74,
            market_regime="Normal Macro",
            agents_validating=["TechnicalAgent"],
            agents_contradicting=[],
            evidence_sources=["TechnicalDecisionEngine"],
            event_facts_snapshot=[],
            technical_snapshot="1D:BUY/+5.0",
            macro_snapshot="",
            geopolitical_snapshot="",
            elliott_wave_snapshot="legacy text must stay private",
            invalidation_rules=["SL"],
            outcome="open",
            outcome_reason="test",
        )
        scenario_plan = build_scenario_plan(
            gold,
            technical_decision,
            TradeRecommendation("Global", "BUY", 72, "Test", [], 2388.0, 2412.0, 2424.0, "test"),
        )
        payload = build_payload(
            gold,
            dxy,
            us10y,
            [],
            analysis,
            technical_decision=technical_decision,
            scenario_plan=scenario_plan,
            agent_results=[AgentResult("TechnicalAgent", "Technical", "BUY", 72, 74, "Decision technique.")],
            trade_ledger=TradeLedgerSummary(
                ledger_path="reports/trade_ledger.jsonl",
                generated_at="2026-04-24T10:00:00+00:00",
                quality_gate_status="VALIDATED",
                quality_gate_reasons=[],
                active_trades=[trade],
            ),
        )
        self.assertIn("technical_decision", payload)
        self.assertIn("scenario_plan", payload)
        self.assertNotIn("ElliottWaveAgent", str(payload))
        self.assertNotIn("elliott_wave_snapshot", str(payload))


class Phase31To34CompletionTests(unittest.TestCase):
    def snapshot(self, symbol: str = "XAU/USD", price: float = 100.0) -> SymbolSnapshot:
        return SymbolSnapshot(
            symbol=symbol,
            label=symbol,
            price=price,
            previous_close=price - 1,
            change_abs=1.0,
            change_pct=1.0,
            period_change_pct=1.0,
            day_high=price + 2,
            day_low=price - 2,
            support=price - 2,
            resistance=price + 2,
            fetched_at="2026-04-24T10:00:00+00:00",
            points=[PricePoint(timestamp=1, close=price - 1), PricePoint(timestamp=2, close=price)],
        )

    def trade_plan(self) -> TradePlan:
        return TradePlan(
            trade_id="replay-test",
            created_at="2026-04-24T10:00:00+00:00",
            updated_at="2026-04-24T10:00:00+00:00",
            status="active",
            direction="BUY",
            entry_type="market_reference",
            reference_price=100.0,
            entry_zone_low=99.5,
            entry_zone_high=100.5,
            stop_loss=95.0,
            tp1=105.0,
            tp2=110.0,
            tp3=115.0,
            risk_reward_tp1=1.0,
            risk_reward_tp2=2.0,
            risk_reward_tp3=3.0,
            max_valid_until="2026-04-24T16:00:00+00:00",
            source_signal_id="replay",
            global_score_at_creation=72,
            data_quality_score=88,
            confidence_score=70,
            market_regime="Normal Macro",
            agents_validating=["PriceActionAgent", "TechnicalAgent", "MacroAgent"],
            agents_contradicting=[],
            evidence_sources=["test"],
            event_facts_snapshot=[],
            technical_snapshot="15m:BUY",
            macro_snapshot="macro ok",
            geopolitical_snapshot="geo ok",
            elliott_wave_snapshot="",
            invalidation_rules=["SL"],
            outcome="open",
            outcome_reason="test",
        )

    def test_phase31_replay_uses_audit_log_prices(self) -> None:
        with TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            ledger_path = tmp_path / "trade_ledger.jsonl"
            audit_path = tmp_path / "audit_log.jsonl"
            ledger_path.write_text(json.dumps(asdict(self.trade_plan())) + "\n", encoding="utf-8")
            audit_entries = [
                {"generated_at": "2026-04-24T10:00:00+00:00", "xauusd_price": 100.0, "decision": {"status": "TRADE_BUY", "score": 72}},
                {"generated_at": "2026-04-24T11:00:00+00:00", "xauusd_price": 106.0, "decision": {"status": "TRADE_BUY", "score": 74}},
            ]
            audit_path.write_text("\n".join(json.dumps(item) for item in audit_entries) + "\n", encoding="utf-8")
            report = build_replay_report(ledger_path=ledger_path, audit_log_path=audit_path)
            self.assertEqual(report.trades_replayed, 1)
            self.assertEqual(report.results[0].replay_outcome, "partial")
            self.assertIn("Replay v3", render_replay_report_markdown(report))

    def test_phase32_settings_file_can_be_initialized_and_validated(self) -> None:
        with TemporaryDirectory() as tmp:
            settings_path = Path(tmp) / "aureum_settings.json"
            settings, validation = load_user_settings(path=settings_path, create_if_missing=True)
            self.assertTrue(settings_path.exists())
            self.assertEqual(validation.status, "OK")
            self.assertIn("TechnicalAgent", settings.active_agents)

            settings_path.write_text(
                json.dumps({"active_agents": ["TechnicalAgent"], "scoring_mode": "conservative", "trade_threshold": 55}),
                encoding="utf-8",
            )
            loaded, validation = load_user_settings(path=settings_path)
            self.assertEqual(validation.status, "OK")
            self.assertEqual(loaded.trade_threshold, 70)
            self.assertGreaterEqual(loaded.minimum_risk_reward, 1.8)

    def test_phase35_agent_toggle_persists_and_marks_agent_off(self) -> None:
        with TemporaryDirectory() as tmp:
            settings_path = Path(tmp) / "aureum_settings.json"
            settings, validation = set_agent_enabled("TechnicalAgent", False, path=settings_path)
            self.assertEqual(validation.status, "OK")
            self.assertNotIn("TechnicalAgent", settings.active_agents)

            agents = [
                AgentResult("TechnicalAgent", "Technical", "BUY", 72, 80, "tech ok"),
                AgentResult("MacroAgent", "Macro", "BUY", 62, 75, "macro ok"),
            ]
            updated = apply_user_settings_to_agents(agents, settings)
            technical = next(agent for agent in updated if agent.name == "TechnicalAgent")
            macro = next(agent for agent in updated if agent.name == "MacroAgent")
            self.assertEqual(technical.status, "OFF")
            self.assertEqual(technical.bias, "OFF")
            self.assertEqual(macro.status, "PASSIVE")

    def test_phase35_macro_calendar_exposes_values_and_bias(self) -> None:
        event = MacroCatalyst(
            title="FOMC decision",
            event_type="FOMC",
            scheduled_at="2026-05-10T18:00:00+00:00",
            source_name="Federal Reserve",
            source_url="https://example.com",
            impact_level="HIGH",
            gold_impact="Dovish rate path can support gold.",
            why_it_matters="Lower yields reduce gold opportunity cost.",
            status="scheduled",
            forecast="4.50%",
            previous="4.75%",
            actual="",
        )
        self.assertEqual(macro_catalyst_gold_bias(event), "BULLISH")

    def test_phase33_reports_v3_exports_are_written(self) -> None:
        bundle = BriefingBundle(
            gold=self.snapshot("XAU/USD", 100.0),
            dxy=self.snapshot("DX-Y.NYB", 98.0),
            us10y=self.snapshot("^TNX", 4.2),
            news=[],
            analysis=AnalysisResult("bullish", 6, 70, ["test"], [], [], []),
            payload={"generated_at": "2026-04-24T10:00:00+00:00"},
            ai_analysis=None,
            global_recommendation=TradeRecommendation("Global", "BUY", 72, "Signal test.", [], 95.0, 105.0, 110.0, "test"),
            trade_ledger=TradeLedgerSummary(
                ledger_path="reports/trade_ledger.jsonl",
                generated_at="2026-04-24T10:00:00+00:00",
                quality_gate_status="WAIT",
                quality_gate_reasons=["test"],
                recent_trades=[self.trade_plan()],
                total_trades=1,
            ),
        )
        with TemporaryDirectory() as tmp:
            exports = write_reports_v3(bundle, "# main\n", output_dir=Path(tmp))
            labels = {export.label for export in exports}
            self.assertIn("daily_report.md", labels)
            self.assertIn("signal_report.md", labels)
            self.assertIn("replay_report.json", labels)
            self.assertTrue((Path(tmp) / "index.html").exists())

    def test_phase45_news_sources_include_fast_and_official_feeds(self) -> None:
        official_ids = {source_id for source_id, _ in OFFICIAL_NEWS_RSS_FEEDS}
        fast_ids = {source_id for source_id, _ in FAST_NEWS_RSS_FEEDS}
        self.assertIn("official_ecb", official_ids)
        self.assertIn("official_boj", official_ids)
        self.assertIn("official_cftc_press", official_ids)
        self.assertIn("fast_reuters_top", fast_ids)
        self.assertIn("fast_bloomberg_markets", fast_ids)
        self.assertIn("trump_truth", CRITICAL_FAST_FEEDS)

    def test_phase45_event_mode_pre_event_macro_is_active(self) -> None:
        calendar = MacroCatalystCalendar(
            generated_at="2026-05-14T10:00:00+00:00",
            source_note="test",
            fedwatch_status="linked_only",
            fedwatch_note="test",
            fedwatch_source_url="https://example.com",
            catalysts=[],
            high_impact_24h=3,
            density_status="high_density",
            pre_event_active=True,
            pre_event_summary="Pre-event HIGH actif: FOMC dans 20 min.",
        )
        result = build_event_mode_analysis(
            self.snapshot("XAU/USD", 2400.0),
            [],
            None,
            None,
            macro_catalysts=calendar,
        )
        self.assertTrue(result.active)
        self.assertEqual(result.stop_multiplier, 1.5)
        self.assertTrue(any("Pre-event" in reason for reason in result.reasons))

    def test_phase45_market_regime_detects_stagflation_fear(self) -> None:
        gold = self.snapshot("XAU/USD", 2440.0)
        dxy = self.snapshot("DX-Y.NYB", 101.0)
        us10y = self.snapshot("^TNX", 4.45)
        us10y.previous_close = 4.38
        us10y.change_abs = 0.07
        with TemporaryDirectory() as tmp, patch("xauusd_agent.REGIME_STATE_PATH", Path(tmp) / "regime_state.json"):
            regime = build_market_regime_analysis(gold, dxy, us10y, [], wti=self.snapshot("WTI", 82.0))
        self.assertEqual(regime.name, "Stagflation Fear")
        self.assertIn("Stagflation Fear", regime.probabilities)

    def test_phase45_cftc_positioning_tracks_producers_merchants_percentiles(self) -> None:
        base = {
            "Market_and_Exchange_Names": "GOLD - COMMODITY EXCHANGE INC.",
            "CFTC_Contract_Market_Code": "088691",
            "Open_Interest_All": "100000",
            "M_Money_Positions_Long_All": "20000",
            "M_Money_Positions_Short_All": "10000",
            "M_Money_Positions_Spread_All": "1000",
            "Prod_Merc_Positions_Long_All": "8000",
            "Prod_Merc_Positions_Short_All": "30000",
            "Swap_Positions_Long_All": "10000",
            "Swap__Positions_Short_All": "12000",
            "Swap__Positions_Spread_All": "1000",
            "NonRept_Positions_Long_All": "5000",
            "NonRept_Positions_Short_All": "4000",
        }
        rows = []
        for index, producer_short in enumerate([22000, 26000, 30000], start=1):
            row = dict(base)
            row["Report_Date_as_YYYY-MM-DD"] = f"2026-04-{index:02d}"
            row["Prod_Merc_Positions_Short_All"] = str(producer_short)
            row["M_Money_Positions_Long_All"] = str(18000 + index * 1000)
            rows.append(row)
        positioning = build_cftc_positioning_from_rows(rows, "https://www.cftc.gov/test")
        self.assertIsNotNone(positioning)
        assert positioning is not None
        self.assertLessEqual(positioning.producer_net_percentile_1y, 50.0)
        self.assertIn("Producers/Merchants", positioning.summary)

    def test_phase45_price_action_detects_m15_swing(self) -> None:
        points = [
            PricePoint(timestamp=1_700_000_000 + index * 300, close=2400 + index, high=2401 + index, low=2399 + index)
            for index in range(20)
        ]
        swing = detect_recent_swing_levels(points)
        self.assertEqual(swing["status"], "ok")
        self.assertIn("swing high", swing["summary"])


class Phase5NewsReactionEngineTests(unittest.TestCase):
    def snapshot(self, symbol: str, price: float, previous: float) -> SymbolSnapshot:
        return SymbolSnapshot(
            symbol=symbol,
            label=symbol,
            price=price,
            previous_close=previous,
            change_abs=price - previous,
            change_pct=((price - previous) / previous) * 100 if previous else 0.0,
            period_change_pct=((price - previous) / previous) * 100 if previous else 0.0,
            day_high=max(price, previous),
            day_low=min(price, previous),
            support=min(price, previous),
            resistance=max(price, previous),
            fetched_at="2026-05-14T10:05:00+00:00",
            points=[
                PricePoint(timestamp=1, close=previous),
                PricePoint(timestamp=2, close=price),
            ],
        )

    def news(self, title: str, source: str = "Reuters", category: str = "fast_reuters") -> NewsItem:
        score, reasons = score_headline_v2(title, source, category)
        return NewsItem(
            title=title,
            source=source,
            link="https://www.reuters.com/test",
            published_at="2026-05-14T10:00:00+00:00",
            category=category,
            score=score,
            score_reasons=reasons,
        )

    def cross_asset(self, oil_change: float = 1.2) -> CrossAssetAnalysis:
        return CrossAssetAnalysis(
            score=50,
            status="test",
            verdict="NEUTRAL",
            summary="test",
            confirmations=[],
            contradictions=[],
            drivers={
                "wti": {"available": True, "change_pct": oil_change},
                "brent": {"available": True, "change_pct": oil_change * 0.8},
            },
            signals=[],
        )

    def test_phase5_classifies_rejected_iran_deal_as_buy(self) -> None:
        gold = self.snapshot("XAU/USD", 2405.0, 2400.0)
        facts = build_event_facts(
            [self.news("Iran rejects nuclear deal as Trump warns of sanctions")],
            wti=self.snapshot("WTI", 81.0, 80.0),
            dxy=self.snapshot("DXY", 99.8, 100.0),
            us10y=self.snapshot("10Y", 4.30, 4.32),
            gold=gold,
        )
        event = classify_news_reaction_event(facts[0], datetime(2026, 5, 14, 10, 5, tzinfo=timezone.utc))
        self.assertIsNotNone(event)
        assert event is not None
        self.assertEqual(event.direction, "BUY")
        self.assertEqual(event.event_type, "GEOPOLITICAL_ESCALATION")

    def test_phase5_classifies_ceasefire_as_sell(self) -> None:
        gold = self.snapshot("XAU/USD", 2398.0, 2400.0)
        facts = build_event_facts(
            [self.news("Israel and Iran agree ceasefire after White House talks")],
            wti=self.snapshot("WTI", 79.5, 80.0),
            dxy=self.snapshot("DXY", 100.2, 100.0),
            us10y=self.snapshot("10Y", 4.34, 4.32),
            gold=gold,
        )
        event = classify_news_reaction_event(facts[0], datetime(2026, 5, 14, 10, 5, tzinfo=timezone.utc))
        self.assertIsNotNone(event)
        assert event is not None
        self.assertEqual(event.direction, "SELL")
        self.assertEqual(event.event_type, "GEOPOLITICAL_DEESCALATION")

    def test_phase5_price_reaction_requires_market_confirmation(self) -> None:
        gold = self.snapshot("XAU/USD", 2406.0, 2400.0)
        dxy = self.snapshot("DXY", 99.8, 100.0)
        us10y = self.snapshot("10Y", 4.30, 4.32)
        facts = build_event_facts(
            [self.news("Trump warns Iran after tanker attack near Hormuz")],
            wti=self.snapshot("WTI", 81.0, 80.0),
            dxy=dxy,
            us10y=us10y,
            gold=gold,
        )
        event = classify_news_reaction_event(facts[0], datetime(2026, 5, 14, 10, 5, tzinfo=timezone.utc))
        assert event is not None
        reaction = detect_news_reaction_price(event, gold, dxy, us10y, self.cross_asset())
        self.assertTrue(reaction.confirms)
        self.assertGreaterEqual(reaction.confirmation_score, 2)

    def test_phase5_classifies_fed_dovish_surprise_as_buy(self) -> None:
        gold = self.snapshot("XAU/USD", 2404.0, 2400.0)
        facts = build_event_facts(
            [self.news("Federal Reserve announces dovish rate cut surprise", "Federal Reserve", "official_fed_press_all")],
            dxy=self.snapshot("DXY", 99.7, 100.0),
            us10y=self.snapshot("10Y", 4.28, 4.32),
            gold=gold,
        )
        event = classify_news_reaction_event(facts[0], datetime(2026, 5, 14, 10, 5, tzinfo=timezone.utc))
        self.assertIsNotNone(event)
        assert event is not None
        self.assertEqual(event.event_type, "FED_DOVISH_SURPRISE")
        self.assertEqual(event.direction, "BUY")

    def test_phase5_classifies_hot_cpi_as_sell(self) -> None:
        gold = self.snapshot("XAU/USD", 2397.0, 2400.0)
        facts = build_event_facts(
            [self.news("CPI hotter than expected as inflation accelerates", "BLS", "official_bls")],
            dxy=self.snapshot("DXY", 100.3, 100.0),
            us10y=self.snapshot("10Y", 4.36, 4.32),
            gold=gold,
        )
        event = classify_news_reaction_event(facts[0], datetime(2026, 5, 14, 10, 5, tzinfo=timezone.utc))
        self.assertIsNotNone(event)
        assert event is not None
        self.assertEqual(event.event_type, "MACRO_SURPRISE")
        self.assertEqual(event.direction, "SELL")

    def test_phase5_classifies_weak_nfp_as_buy(self) -> None:
        gold = self.snapshot("XAU/USD", 2403.0, 2400.0)
        facts = build_event_facts(
            [self.news("NFP misses as jobs market weakens sharply", "BLS", "official_bls")],
            dxy=self.snapshot("DXY", 99.8, 100.0),
            us10y=self.snapshot("10Y", 4.29, 4.32),
            gold=gold,
        )
        event = classify_news_reaction_event(facts[0], datetime(2026, 5, 14, 10, 5, tzinfo=timezone.utc))
        self.assertIsNotNone(event)
        assert event is not None
        self.assertEqual(event.event_type, "MACRO_SURPRISE")
        self.assertEqual(event.direction, "BUY")

    def test_phase5_news_reaction_plan_has_valid_sell_levels(self) -> None:
        gold = self.snapshot("XAU/USD", 2395.0, 2400.0)
        dxy = self.snapshot("DXY", 100.3, 100.0)
        us10y = self.snapshot("10Y", 4.35, 4.32)
        facts = build_event_facts(
            [self.news("Iran and Israel agree ceasefire as oil drops", "Reuters", "fast_reuters")],
            wti=self.snapshot("WTI", 79.0, 80.0),
            dxy=dxy,
            us10y=us10y,
            gold=gold,
        )
        plan = build_news_reaction_engine(
            facts,
            gold,
            dxy,
            us10y,
            cross_asset=self.cross_asset(oil_change=-1.0),
            now=datetime(2026, 5, 14, 10, 5, tzinfo=timezone.utc),
        )
        self.assertEqual(plan.entry_type, "NEWS_REACTION")
        self.assertEqual(plan.status, "TRADE_READY")
        self.assertLess(plan.tp1, plan.reference_price)
        self.assertLess(plan.tp2, plan.tp1)
        self.assertLess(plan.tp3, plan.tp2)
        self.assertGreater(plan.stop_loss, plan.reference_price)

    def test_phase5_multi_event_collision_suspends_signal(self) -> None:
        gold = self.snapshot("XAU/USD", 2402.0, 2400.0)
        dxy = self.snapshot("DXY", 100.0, 100.0)
        us10y = self.snapshot("10Y", 4.32, 4.32)
        facts = build_event_facts(
            [
                self.news("Trump warns Iran after attack near Hormuz"),
                self.news("Israel and Iran agree ceasefire after White House talks"),
            ],
            wti=self.snapshot("WTI", 80.0, 80.0),
            dxy=dxy,
            us10y=us10y,
            gold=gold,
        )
        plan = build_news_reaction_engine(
            facts,
            gold,
            dxy,
            us10y,
            cross_asset=self.cross_asset(),
            now=datetime(2026, 5, 14, 10, 5, tzinfo=timezone.utc),
        )
        self.assertEqual(plan.status, "SUSPENDED")
        self.assertEqual(plan.event_type, "MULTI_EVENT_COLLISION")


class Phase6TradeLevelsTests(unittest.TestCase):
    def snapshot(self, price: float = 2400.0) -> SymbolSnapshot:
        points = [
            PricePoint(timestamp=1_700_000_000 + index * 300, close=price - 18 + index, high=price - 16 + index, low=price - 20 + index)
            for index in range(40)
        ]
        return SymbolSnapshot(
            symbol="XAU/USD",
            label="XAU/USD",
            price=price,
            previous_close=price - 6,
            change_abs=6,
            change_pct=0.25,
            period_change_pct=0.25,
            day_high=price + 18,
            day_low=price - 28,
            support=price - 22,
            resistance=price + 20,
            fetched_at="2026-05-14T10:05:00+00:00",
            points=points,
            intraday_points=points,
        )

    def readings(self, verdict: str = "BUY") -> list[TechnicalReading]:
        return [
            TechnicalReading(
                timeframe=timeframe,
                close=2395.0,
                ema20=2392.0,
                ema50=2388.0,
                ema100=2380.0,
                ema200=2365.0,
                rsi7=55.0 if verdict == "BUY" else 42.0,
                macd_line=1.0,
                macd_signal=0.5,
                macd_histogram=0.5 if verdict == "BUY" else -0.5,
                volume_ratio=1.1,
                atr14=8.0,
                score=4.0 if verdict == "BUY" else -4.0,
                verdict=verdict,
                reasons=[],
            )
            for timeframe in ["1D", "4H", "1H", "15m", "5m"]
        ]

    def test_phase6_buy_levels_are_ordered_and_rr_valid(self) -> None:
        gold = self.snapshot(2400.0)
        levels = build_market_trade_levels(gold, "BUY", "trend_continuation", atr=8.0, readings=self.readings("BUY"), proxy_price=2395.0)
        self.assertLess(levels.stop_loss, gold.price)
        self.assertGreater(levels.tp1, gold.price)
        self.assertGreater(levels.tp2, levels.tp1)
        self.assertGreater(levels.tp3, levels.tp2)
        self.assertGreaterEqual(levels.risk_reward_tp1, 1.5)
        self.assertEqual((levels.partial_tp1_pct, levels.partial_tp2_pct, levels.partial_tp3_pct), (50, 30, 20))

    def test_phase6_sell_levels_are_ordered_and_rr_valid(self) -> None:
        gold = self.snapshot(2400.0)
        levels = build_market_trade_levels(gold, "SELL", "pivot_rejection", atr=8.0, readings=self.readings("SELL"), proxy_price=2395.0)
        self.assertGreater(levels.stop_loss, gold.price)
        self.assertLess(levels.tp1, gold.price)
        self.assertLess(levels.tp2, levels.tp1)
        self.assertLess(levels.tp3, levels.tp2)
        self.assertGreaterEqual(levels.risk_reward_tp1, 1.5)

    def test_phase6_technical_decision_uses_market_levels(self) -> None:
        gold = self.snapshot(2400.0)
        decision = build_technical_decision(gold, self.readings("BUY"), proxy_price=2395.0)
        self.assertLess(decision.stop_loss, gold.price)
        self.assertGreater(decision.tp1, gold.price)
        self.assertGreater(decision.tp2, decision.tp1)
        self.assertGreater(decision.tp3, decision.tp2)
        self.assertTrue(any("Niveaux" in reason or "Setup" in reason for reason in decision.reasons))

    def test_phase6_setup_classifier_maps_breakout_and_range(self) -> None:
        self.assertEqual(trade_setup_from_structure("breakout", "BUY"), "breakout")
        self.assertEqual(trade_setup_from_structure("range", "SELL"), "range")
        self.assertEqual(trade_setup_from_structure("reversal", "SELL"), "pivot_rejection")

    def test_phase6_dashboard_exposes_partial_tp_plan(self) -> None:
        plan = TradePlan(
            trade_id="SELL-TEST",
            created_at="2026-05-14T10:00:00+00:00",
            updated_at="2026-05-14T10:00:00+00:00",
            status="open",
            direction="SELL",
            entry_type="trend_continuation",
            reference_price=2400.0,
            entry_zone_low=2398.0,
            entry_zone_high=2402.0,
            stop_loss=2410.0,
            tp1=2385.0,
            tp2=2375.0,
            tp3=2360.0,
            risk_reward_tp1=1.5,
            risk_reward_tp2=2.5,
            risk_reward_tp3=4.0,
            max_valid_until="2026-05-14T14:00:00+00:00",
            source_signal_id="signal",
            global_score_at_creation=72,
            data_quality_score=82,
            confidence_score=70,
            market_regime="normal",
            agents_validating=["TechnicalAgent"],
            agents_contradicting=[],
            evidence_sources=["test"],
            event_facts_snapshot=[],
            technical_snapshot="M15:SELL",
            macro_snapshot="",
            geopolitical_snapshot="",
            elliott_wave_snapshot="",
            invalidation_rules=[],
            outcome="open",
            outcome_reason="open",
        )
        ledger = TradeLedgerSummary(
            ledger_path="reports/trade_ledger.jsonl",
            generated_at="2026-05-14T10:00:00+00:00",
            quality_gate_status="TRADE_SELL",
            quality_gate_reasons=[],
            active_trades=[plan],
            recent_trades=[plan],
            total_trades=1,
        )
        recommendation = TradeRecommendation("SELL", "SELL", 72, "resume", [], 2410.0, 2385.0, 2375.0, "source")
        signal_html = render_signal_locked_panel(ledger, recommendation, None, None)
        tracker_html = render_trade_tracker_panel(ledger)
        self.assertIn("TP1 · 50%", signal_html)
        self.assertIn("TP2 · 30%", signal_html)
        self.assertIn("TP3 · 20%", signal_html)
        self.assertIn("TP1 50%", tracker_html)
        self.assertIn("TP2 30%", tracker_html)
        self.assertIn("TP3 20%", tracker_html)

    def test_phase6_trump_direct_down_uses_google_news_fallback(self) -> None:
        rss = ET.fromstring(
            """
            <rss><channel><title>Google News</title>
              <item>
                <title>Reuters: Trump says Iran oil sanctions remain possible</title>
                <link>https://www.reuters.com/world/trump-iran-oil</link>
                <pubDate>Thu, 14 May 2026 10:00:00 GMT</pubDate>
                <source>Reuters</source>
              </item>
            </channel></rss>
            """
        )

        def fake_fetch_root(category: str, _url: str, **_kwargs):
            if category == "political_trump_google_fallback":
                return rss
            return None

        with patch("xauusd_agent.fetch_nitter_feed_with_fallback", return_value=None), patch("xauusd_agent.fetch_rss_root", side_effect=fake_fetch_root), patch("xauusd_agent.append_source_error") as append_error:
            items = fetch_political_statement_news(limit=4)

        self.assertEqual(len(items), 1)
        self.assertEqual(items[0].category, "political_trump_google_fallback")
        self.assertIn("Trump", items[0].title)
        append_error.assert_any_call(
            "trump_political_direct_feeds",
            unittest.mock.ANY,
            "all_trump_white_house_direct_feeds_down",
            criticality="high",
        )

    def test_p0_desk_uses_locked_trade_levels_not_live_recommendation(self) -> None:
        plan = TradePlan(
            trade_id="LOCKED-SELL",
            created_at="2026-05-14T22:04:00+00:00",
            updated_at="2026-05-14T22:04:00+00:00",
            status="active",
            direction="SELL",
            entry_type="trend_continuation",
            reference_price=4651.14,
            entry_zone_low=4650.0,
            entry_zone_high=4652.0,
            stop_loss=4659.87,
            tp1=4634.19,
            tp2=4625.0,
            tp3=4610.04,
            risk_reward_tp1=1.94,
            risk_reward_tp2=3.0,
            risk_reward_tp3=4.7,
            max_valid_until="2026-05-15T22:04:00+00:00",
            source_signal_id="locked-signal",
            global_score_at_creation=77,
            data_quality_score=80,
            confidence_score=72,
            market_regime="normal",
            agents_validating=["TechnicalAgent"],
            agents_contradicting=[],
            evidence_sources=["ledger"],
            event_facts_snapshot=[],
            technical_snapshot="M15:SELL",
            macro_snapshot="",
            geopolitical_snapshot="",
            elliott_wave_snapshot="",
            invalidation_rules=[],
            outcome="open",
            outcome_reason="Trade Snapshot cree par Quality Gate; SL/TP figes.",
        )
        ledger = TradeLedgerSummary(
            ledger_path="reports/trade_ledger.jsonl",
            generated_at="2026-05-15T00:00:00+00:00",
            quality_gate_status="WAIT",
            quality_gate_reasons=[],
            active_trades=[],
            recent_trades=[plan],
            total_trades=1,
        )
        live_recommendation = TradeRecommendation(
            "global",
            "SELL",
            81,
            "Live recommendation recalculated at refresh.",
            [],
            4704.90,
            4575.72,
            4524.04,
            "live",
        )
        orchestrator = OrchestratorDecision(
            verdict="SELL",
            score=77,
            status="TRADE_SELL",
            engine="orchestrator_v3",
            bullish_score=32.3,
            legacy_verdict="SELL",
            legacy_score=62,
            top_reasons=["Trade exploitable."],
            counter_reasons=[],
            contradictions=[],
            quality_gate_reasons=[],
        )
        html = render_desk_position_summary(live_recommendation, orchestrator, None, ledger)
        self.assertIn("4659.87", html)
        self.assertIn("4634.19", html)
        self.assertIn("4625.00", html)
        self.assertIn("4610.04", html)
        self.assertIn("Position historisee", html)
        self.assertNotIn("4704.90", html)
        self.assertNotIn("4575.72", html)
        self.assertNotIn("4524.04", html)

    def test_p0_desk_hides_live_levels_when_trade_status_without_lock(self) -> None:
        live_recommendation = TradeRecommendation(
            "global",
            "SELL",
            81,
            "Live recommendation recalculated at refresh.",
            [],
            4704.90,
            4575.72,
            4524.04,
            "live",
        )
        orchestrator = OrchestratorDecision(
            verdict="SELL",
            score=77,
            status="TRADE_SELL",
            engine="orchestrator_v3",
            bullish_score=32.3,
            legacy_verdict="SELL",
            legacy_score=62,
            top_reasons=["Trade exploitable."],
            counter_reasons=[],
            contradictions=[],
            quality_gate_reasons=[],
        )
        ledger = TradeLedgerSummary(
            ledger_path="reports/trade_ledger.jsonl",
            generated_at="2026-05-15T00:00:00+00:00",
            quality_gate_status="WAIT",
            quality_gate_reasons=[],
            active_trades=[],
            recent_trades=[],
            total_trades=0,
        )
        html = render_desk_position_summary(live_recommendation, orchestrator, None, ledger)
        self.assertIn("Aucune position active", html)
        self.assertNotIn("Signal live sans trade locked", html)
        self.assertNotIn("4704.90", html)
        self.assertNotIn("4575.72", html)
        self.assertNotIn("4524.04", html)

    def test_p0_active_trades_and_plans_alias_include_open_ledger_trade(self) -> None:
        with TemporaryDirectory() as tmp:
            ledger_path = Path(tmp) / "trade_ledger.jsonl"
            open_plan = TradePlan(
                trade_id="OPEN-BUY",
                created_at="2026-05-15T00:00:00+00:00",
                updated_at="2026-05-15T00:00:00+00:00",
                status="active",
                direction="BUY",
                entry_type="trend_continuation",
                reference_price=2400.0,
                entry_zone_low=2399.0,
                entry_zone_high=2401.0,
                stop_loss=2388.0,
                tp1=2418.0,
                tp2=2428.0,
                tp3=2440.0,
                risk_reward_tp1=1.5,
                risk_reward_tp2=2.3,
                risk_reward_tp3=3.3,
                max_valid_until="2026-05-15T12:00:00+00:00",
                source_signal_id="open-buy",
                global_score_at_creation=70,
                data_quality_score=80,
                confidence_score=70,
                market_regime="normal",
                agents_validating=[],
                agents_contradicting=[],
                evidence_sources=[],
                event_facts_snapshot=[],
                technical_snapshot="",
                macro_snapshot="",
                geopolitical_snapshot="",
                elliott_wave_snapshot="",
                invalidation_rules=[],
                outcome="open",
                outcome_reason="open",
            )
            ledger_path.write_text(json.dumps(asdict(open_plan), ensure_ascii=False) + "\n", encoding="utf-8")
            recommendation = TradeRecommendation("global", "WAIT", 50, "wait", [], 0.0, 0.0, 0.0, "test")
            summary = build_trade_ledger_summary(
                self.snapshot(2400.0),
                recommendation,
                None,
                [],
                None,
                [],
                [],
                path=ledger_path,
                now=datetime(2026, 5, 15, 1, 0, tzinfo=timezone.utc),
                allow_create=False,
            )
            payload = trade_ledger_public_dict(summary)
            self.assertEqual(len(summary.active_trades), 1)
            self.assertEqual(summary.active_trades[0].trade_id, "OPEN-BUY")
            self.assertEqual(len(payload["plans"]), 1)
            self.assertEqual(payload["plans"][0]["trade_id"], "OPEN-BUY")


class PrePhase7ReversalEngineTests(unittest.TestCase):
    def snapshot(self, price: float = 100.0) -> SymbolSnapshot:
        return SymbolSnapshot(
            symbol="XAU/USD",
            label="XAU/USD",
            price=price,
            previous_close=98.0,
            change_abs=2.0,
            change_pct=2.0,
            period_change_pct=1.0,
            day_high=125.0,
            day_low=95.0,
            support=95.0,
            resistance=125.0,
            fetched_at="2026-05-15T00:00:00+00:00",
            points=[PricePoint(timestamp=1, close=price)],
        )

    def reading(self, timeframe: str, rsi: float = 14.0, volume_ratio: float = 1.9) -> TechnicalReading:
        return TechnicalReading(
            timeframe=timeframe,
            close=100.0,
            ema20=101.0,
            ema50=102.0,
            ema100=103.0,
            ema200=104.0,
            rsi7=rsi,
            macd_line=-1.0,
            macd_signal=-1.2,
            macd_histogram=0.2,
            volume_ratio=volume_ratio,
            atr14=4.0,
            score=0.0,
            verdict="NEUTRAL",
            reasons=[],
        )

    def buy_rejection_candles(self, timeframe: str) -> list[OHLCCandle]:
        candles: list[OHLCCandle] = []
        closes = [108, 106, 104, 102, 100, 99, 98, 97, 96, 95.5, 96.2, 96.8, 98.5]
        for index, close in enumerate(closes):
            low = close - 0.6
            high = close + 0.9
            if index == len(closes) - 1:
                low = 94.7
                high = 100.6
                close = 99.2
            candles.append(
                OHLCCandle(
                    timestamp=1_700_000_000 + index * 300,
                    open=close - 0.2,
                    high=high,
                    low=low,
                    close=close,
                    volume=1000 + index,
                    source="test",
                    timeframe=timeframe,
                    fetched_at="2026-05-15T00:00:00+00:00",
                )
            )
        return candles

    def chart_store(self) -> ChartStore:
        timeframes = [
            ChartTimeframe("M5", "READY", self.buy_rejection_candles("M5")),
            ChartTimeframe("M15", "READY", self.buy_rejection_candles("M15")),
            ChartTimeframe("H1", "READY", self.buy_rejection_candles("H1")),
            ChartTimeframe("H4", "READY", self.buy_rejection_candles("H4")),
        ]
        return ChartStore(
            generated_at="2026-05-15T00:00:00+00:00",
            symbol="GC=F",
            source="test",
            status="READY",
            summary="ready",
            timeframes=timeframes,
        )

    def test_pre_phase7_detects_bullish_and_bearish_rsi_divergence(self) -> None:
        bullish = detect_rsi_divergence(
            [100, 99, 98, 97, 96, 97, 95],
            [30, 28, 24, 20, 18, 22, 25],
            window=7,
        )
        bearish = detect_rsi_divergence(
            [100, 101, 102, 103, 104, 103, 105],
            [70, 74, 80, 84, 86, 82, 76],
            window=7,
        )
        self.assertEqual(bullish["direction"], "BUY")
        self.assertEqual(bearish["direction"], "SELL")

    def test_pre_phase7_reversal_engine_exposes_three_horizons(self) -> None:
        readings = [
            self.reading("5m"),
            self.reading("15m"),
            self.reading("1H"),
            self.reading("4H", rsi=45.0, volume_ratio=1.0),
        ]
        engine = build_reversal_engine(self.snapshot(), readings, self.chart_store())
        self.assertEqual(set(engine), {"scalp", "intraday", "swing"})
        self.assertTrue(all(setup.status == "REVERSAL_BUY" for setup in engine.values()))
        self.assertTrue(all(setup.tp1 > setup.entry_zone_high for setup in engine.values()))
        self.assertTrue(all(setup.stop_loss < setup.entry_zone_low for setup in engine.values()))

    def test_pre_phase7_reversal_engine_returns_no_trade_when_conditions_are_weak(self) -> None:
        readings = [
            self.reading("5m", rsi=48.0, volume_ratio=1.0),
            self.reading("15m", rsi=48.0, volume_ratio=1.0),
            self.reading("1H", rsi=48.0, volume_ratio=1.0),
            self.reading("4H", rsi=48.0, volume_ratio=1.0),
        ]
        engine = build_reversal_engine(self.snapshot(price=110.0), readings, self.chart_store())
        self.assertTrue(all(setup.status == "NO_REVERSAL_TRADE" for setup in engine.values()))

    def test_pre_phase7_render_reversal_panels_uses_only_visible_statuses(self) -> None:
        setup = ReversalSetup(
            horizon="scalp",
            status="REVERSAL_BUY",
            direction="BUY",
            tf_signal="5m",
            tf_context="15m",
            confluence_score=4,
            conditions_met=["rsi_extreme", "swing_rejection", "volume_spike", "range_position"],
            entry_zone_low=99.5,
            entry_zone_high=100.5,
            stop_loss=94.0,
            tp1=108.0,
            tp2=112.0,
            tp3=118.0,
            risk_reward_tp1=1.6,
            validity_minutes=30,
            reasons=["RSI7 en survente extreme."],
            blockers=[],
            detected_at="2026-05-15T00:00:00+00:00",
        )
        html = render_reversal_panels({"scalp": setup})
        self.assertIn("REVERSAL BUY", html)
        self.assertIn("NO REVERSAL TRADE", html)
        self.assertNotIn("WATCH BUY", html)
        self.assertNotIn("BLOCKED", html)

    def test_pre_phase7_desk_clean_hides_internal_gate_language(self) -> None:
        recommendation = TradeRecommendation(
            "global",
            "SELL",
            59,
            "Orchestrateur v3 NO_TRADE: score pondere 23.9/100, reference initiale SELL 62/100. Pas de trade.",
            [],
            0.0,
            0.0,
            0.0,
            "test",
        )
        orchestrator = OrchestratorDecision(
            verdict="SELL",
            score=59,
            status="NO_TRADE",
            engine="orchestrator_v3",
            bullish_score=23.9,
            legacy_verdict="SELL",
            legacy_score=62,
            top_reasons=[],
            counter_reasons=[],
            contradictions=[],
            quality_gate_reasons=["Quality Gate v3: setup surveille."],
        )
        html = render_desk_position_summary(recommendation, orchestrator, None, None)
        locked_html = render_signal_locked_panel(None, recommendation, orchestrator, None)
        combined = html + locked_html
        self.assertIn("Aucune position active", combined)
        for hidden in ["Orchestrateur v3", "score pondere", "reference initiale", "Quality Gate", "SURVEILLER", "WATCH BUY", "BLOCKED", "Signal live"]:
            self.assertNotIn(hidden, combined)


class Phase7BStrategyCandidateTests(unittest.TestCase):
    base_time = datetime(2026, 5, 15, 7, 15, tzinfo=timezone.utc)

    def snapshot(
        self,
        price: float = 100.0,
        previous_close: float = 100.0,
        day_low: float = 80.0,
        day_high: float = 120.0,
    ) -> SymbolSnapshot:
        return SymbolSnapshot(
            symbol="XAU/USD",
            label="XAU/USD",
            price=price,
            previous_close=previous_close,
            change_abs=price - previous_close,
            change_pct=((price - previous_close) / previous_close) * 100,
            period_change_pct=((price - previous_close) / previous_close) * 100,
            day_high=day_high,
            day_low=day_low,
            support=day_low,
            resistance=day_high,
            fetched_at=self.base_time.isoformat(),
            points=[PricePoint(timestamp=int(self.base_time.timestamp()), close=price)],
        )

    def reading(
        self,
        timeframe: str,
        verdict: str = "BUY",
        rsi: float = 56.0,
        atr: float = 4.0,
        volume_ratio: float = 1.2,
        close: float = 100.0,
        score: float = 7.0,
    ) -> TechnicalReading:
        if verdict == "SELL":
            ema20, ema50, ema100, ema200 = close - 1.0, close, close + 1.5, close + 3.0
            macd_histogram = -0.8
        else:
            ema20, ema50, ema100, ema200 = close + 1.0, close, close - 1.5, close - 3.0
            macd_histogram = 0.8
        return TechnicalReading(
            timeframe=timeframe,
            close=close,
            ema20=ema20,
            ema50=ema50,
            ema100=ema100,
            ema200=ema200,
            rsi7=rsi,
            macd_line=macd_histogram,
            macd_signal=0.0,
            macd_histogram=macd_histogram,
            volume_ratio=volume_ratio,
            atr14=atr,
            score=score if verdict == "BUY" else -score,
            verdict=verdict,
            reasons=["test"],
        )

    def candle(
        self,
        offset_minutes: int,
        open_: float,
        high: float,
        low: float,
        close: float,
        timeframe: str = "H1",
        volume: int = 1000,
    ) -> OHLCCandle:
        timestamp = int((self.base_time + timedelta(minutes=offset_minutes)).timestamp())
        return OHLCCandle(
            timestamp=timestamp,
            open=open_,
            high=high,
            low=low,
            close=close,
            volume=volume,
            source="test",
            timeframe=timeframe,
            fetched_at=self.base_time.isoformat(),
        )

    def chart_store(self, h1: list[OHLCCandle] | None = None, m15: list[OHLCCandle] | None = None) -> ChartStore:
        return ChartStore(
            generated_at=self.base_time.isoformat(),
            symbol="GC=F",
            source="test",
            status="READY",
            summary="ready",
            timeframes=[
                ChartTimeframe("H1", "READY", h1 or []),
                ChartTimeframe("M15", "READY", m15 or []),
            ],
        )

    def rejection_series(self, direction: str, base: float = 100.0) -> list[OHLCCandle]:
        candles = [self.candle(-720 + index * 60, base, base + 2, base - 2, base + 0.2) for index in range(12)]
        if direction == "BUY":
            candles[-1] = self.candle(0, base - 1.0, base + 2.0, base - 7.0, base + 1.2)
        else:
            candles[-1] = self.candle(0, base + 1.0, base + 7.0, base - 2.0, base - 1.2)
        return candles

    def test_phase7b_pivot_rejection_buy_ready_near_camarilla_support(self) -> None:
        gold = self.snapshot(price=89.2, previous_close=100.0, day_low=80.0, day_high=120.0)
        readings = [self.reading("1H", "BUY", rsi=42.0, close=89.0)]
        setup = evaluate_pivot_rejection_setup(gold, readings, self.chart_store(h1=self.rejection_series("BUY", 89.0)), now=self.base_time)
        self.assertEqual(setup.name, "PivotRejectionSetup")
        self.assertEqual(setup.direction, "BUY")
        self.assertEqual(setup.status, "TRADE_READY")
        self.assertIn("wick_rejection", setup.conditions_met)
        self.assertGreater(setup.tp1, setup.entry_zone_high)

    def test_phase7b_pivot_rejection_sell_ready_near_camarilla_resistance(self) -> None:
        gold = self.snapshot(price=110.8, previous_close=100.0, day_low=80.0, day_high=120.0)
        readings = [self.reading("1H", "SELL", rsi=62.0, close=111.0)]
        setup = evaluate_pivot_rejection_setup(gold, readings, self.chart_store(h1=self.rejection_series("SELL", 111.0)), now=self.base_time)
        self.assertEqual(setup.direction, "SELL")
        self.assertEqual(setup.status, "TRADE_READY")
        self.assertLess(setup.tp1, setup.entry_zone_low)

    def test_phase7b_mean_reversion_buy_uses_h1_extreme_and_extension(self) -> None:
        gold = self.snapshot(price=90.0, previous_close=100.0, day_low=88.0, day_high=118.0)
        reading = self.reading("1H", "BUY", rsi=20.0, atr=4.0, close=90.0)
        reading.ema20 = 99.0
        reading.macd_histogram = -0.2
        setup = evaluate_mean_reversion_setup(gold, [reading], self.chart_store(h1=self.rejection_series("BUY", 90.0)), now=self.base_time)
        self.assertEqual(setup.direction, "BUY")
        self.assertIn(setup.status, {"TRADE_READY", "WATCH"})
        self.assertIn("rsi_extreme", setup.conditions_met)
        self.assertIn("ema20_extension", setup.conditions_met)

    def test_phase7b_mean_reversion_sell_uses_h1_overbought(self) -> None:
        gold = self.snapshot(price=112.0, previous_close=100.0, day_low=88.0, day_high=114.0)
        reading = self.reading("1H", "SELL", rsi=80.0, atr=4.0, close=112.0)
        reading.ema20 = 103.0
        reading.macd_histogram = 0.2
        setup = evaluate_mean_reversion_setup(gold, [reading], self.chart_store(h1=self.rejection_series("SELL", 112.0)), now=self.base_time)
        self.assertEqual(setup.direction, "SELL")
        self.assertIn("rsi_extreme", setup.conditions_met)
        self.assertLess(setup.tp1, setup.entry_zone_low)

    def test_phase7b_range_trading_buy_at_lower_edge(self) -> None:
        h1 = []
        for index in range(24):
            low = 100.0 if index % 5 == 0 else 102.0
            high = 120.0 if index % 6 == 0 else 118.0
            h1.append(self.candle(-1440 + index * 60, 110.0, high, low, 101.5 if index == 23 else 110.0))
        gold = self.snapshot(price=101.0, previous_close=110.0, day_low=100.0, day_high=120.0)
        reading = self.reading("1H", "NEUTRAL", rsi=40.0, atr=3.0, close=101.0, score=0.0)
        reading.ema20 = 109.0
        reading.ema50 = 109.2
        reading.ema100 = 109.5
        reading.ema200 = 109.8
        setup = evaluate_range_trading_setup(gold, [reading], self.chart_store(h1=h1), now=datetime(2026, 5, 15, 3, 0, tzinfo=timezone.utc))
        self.assertEqual(setup.direction, "BUY")
        self.assertIn("range_touches", setup.conditions_met)
        self.assertEqual(setup.preferred_session, "asian")

    def test_phase7b_range_trading_rejects_middle_of_range(self) -> None:
        h1 = [self.candle(-720 + index * 60, 110.0, 120.0, 100.0, 110.0) for index in range(12)]
        gold = self.snapshot(price=110.0, previous_close=110.0, day_low=100.0, day_high=120.0)
        setup = evaluate_range_trading_setup(gold, [self.reading("1H", "NEUTRAL", close=110.0, score=0.0)], self.chart_store(h1=h1), now=self.base_time)
        self.assertEqual(setup.status, "NO_SETUP")
        self.assertEqual(setup.direction, "NEUTRAL")

    def test_phase7b_trend_continuation_buy_ready_on_alignment(self) -> None:
        gold = self.snapshot(price=111.8, previous_close=108.0, day_low=104.0, day_high=116.0)
        readings = [
            self.reading("1D", "BUY", close=112.0),
            self.reading("4H", "BUY", close=112.0),
            self.reading("1H", "BUY", close=112.0, volume_ratio=1.5),
        ]
        setup = evaluate_trend_continuation_setup(gold, readings, self.chart_store(), now=datetime(2026, 5, 15, 13, 30, tzinfo=timezone.utc))
        self.assertEqual(setup.direction, "BUY")
        self.assertEqual(setup.status, "TRADE_READY")
        self.assertIn("multi_timeframe_alignment", setup.conditions_met)

    def test_phase7b_trend_continuation_suspended_by_event_mode(self) -> None:
        gold = self.snapshot(price=111.8, previous_close=108.0)
        readings = [self.reading("1D", "BUY"), self.reading("4H", "BUY"), self.reading("1H", "BUY")]
        event_mode = EventModeAnalysis(True, 80, "ACTIVE", "freeze", 1.5, ["test"])
        setup = evaluate_trend_continuation_setup(gold, readings, self.chart_store(), event_mode=event_mode, now=self.base_time)
        self.assertEqual(setup.status, "NO_SETUP")
        self.assertIn("Mode event actif", setup.reasons[0])

    def test_phase7b_breakout_du_jour_buy_ready_on_london_break(self) -> None:
        reference = datetime(2026, 5, 15, 7, 15, tzinfo=timezone.utc)
        candles: list[OHLCCandle] = []
        for index in range(28):
            ts = int((datetime(2026, 5, 15, 0, 0, tzinfo=timezone.utc) + timedelta(minutes=15 * index)).timestamp())
            candles.append(OHLCCandle(ts, 101.0, 104.0, 100.0, 102.0, 1000, "test", "M15", reference.isoformat()))
        candles.append(OHLCCandle(int((reference - timedelta(minutes=15)).timestamp()), 103.5, 104.5, 102.5, 104.0, 1200, "test", "M15", reference.isoformat()))
        candles.append(OHLCCandle(int(reference.timestamp()), 104.2, 107.0, 103.8, 106.2, 2200, "test", "M15", reference.isoformat()))
        gold = self.snapshot(price=106.2, previous_close=102.0, day_low=100.0, day_high=107.0)
        setup = evaluate_breakout_du_jour_setup(
            gold,
            [self.reading("15m", "BUY", rsi=58.0, atr=3.0, volume_ratio=1.8, close=106.2)],
            self.chart_store(m15=candles),
            now=reference,
        )
        self.assertEqual(setup.direction, "BUY")
        self.assertEqual(setup.status, "TRADE_READY")
        self.assertIn("asian_range_break", setup.conditions_met)

    def test_phase7b_breakout_du_jour_rejects_off_hours(self) -> None:
        reference = datetime(2026, 5, 15, 22, 15, tzinfo=timezone.utc)
        candles = [
            OHLCCandle(int((datetime(2026, 5, 15, 0, 0, tzinfo=timezone.utc) + timedelta(minutes=15 * index)).timestamp()), 101.0, 104.0, 100.0, 102.0, 1000, "test", "M15", reference.isoformat())
            for index in range(28)
        ]
        candles.append(OHLCCandle(int((reference - timedelta(minutes=15)).timestamp()), 103.5, 104.5, 102.5, 104.0, 1200, "test", "M15", reference.isoformat()))
        candles.append(OHLCCandle(int(reference.timestamp()), 104.2, 107.0, 103.8, 106.2, 2200, "test", "M15", reference.isoformat()))
        gold = self.snapshot(price=106.2, previous_close=102.0)
        setup = evaluate_breakout_du_jour_setup(
            gold,
            [self.reading("15m", "BUY", rsi=58.0, atr=3.0, volume_ratio=1.8, close=106.2)],
            self.chart_store(m15=candles),
            now=reference,
        )
        self.assertEqual(setup.direction, "BUY")
        self.assertIn(setup.status, {"WATCH", "NO_SETUP"})
        self.assertIn("Session peu favorable au breakout du jour.", setup.blockers)

    def test_phase7b_build_strategy_candidates_returns_all_six_sources(self) -> None:
        gold = self.snapshot(price=111.8, previous_close=108.0, day_low=104.0, day_high=116.0)
        readings = [self.reading("1D", "BUY", close=112.0), self.reading("4H", "BUY", close=112.0), self.reading("1H", "BUY", close=112.0), self.reading("15m", "BUY", close=112.0)]
        candidates = build_strategy_candidates(gold, readings, self.chart_store(h1=self.rejection_series("BUY", 112.0)), now=self.base_time)
        self.assertEqual(len(candidates), 6)
        self.assertEqual(candidates[-1].name, "NewsReactionSetup")
        self.assertTrue({candidate.name for candidate in candidates}.issuperset({"PivotRejectionSetup", "MeanReversionSetup", "RangeTradingSetup", "TrendContinuationSetup", "BreakoutDuJourSetup"}))


class Phase7CStrategyCoordinatorTests(unittest.TestCase):
    reference = datetime(2026, 5, 15, 13, 30, tzinfo=timezone.utc)

    def candidate(
        self,
        name: str,
        status: str = "TRADE_READY",
        direction: str = "BUY",
        confidence: int = 75,
        confluence: int = 75,
        rr: float = 2.0,
        preferred_session: str = "all",
        blockers: list[str] | None = None,
    ) -> SetupCandidate:
        return SetupCandidate(
            name=name,
            status=status,
            direction=direction,
            confidence=confidence,
            confluence_score=confluence,
            conditions_met=["condition_a", "condition_b", "condition_c"],
            entry_zone_low=99.0,
            entry_zone_high=101.0,
            stop_loss=95.0 if direction == "BUY" else 105.0,
            tp1=110.0 if direction == "BUY" else 90.0,
            tp2=115.0 if direction == "BUY" else 85.0,
            tp3=120.0 if direction == "BUY" else 80.0,
            rr_tp1=rr,
            rr_tp2=rr + 1.0,
            rr_tp3=rr + 2.0,
            validity_minutes=240,
            cooldown_after_loss_minutes=240,
            cooldown_after_win_minutes=60,
            preferred_session=preferred_session,
            reasons=["test candidate"],
            blockers=blockers or [],
            detected_at=self.reference.isoformat(),
            metadata={},
        )

    def trade_plan(self, outcome: str = "loss", direction: str = "BUY", minutes_ago: int = 30) -> TradePlan:
        closed_at = (self.reference - timedelta(minutes=minutes_ago)).isoformat()
        return TradePlan(
            trade_id="test-trade",
            created_at=(self.reference - timedelta(minutes=minutes_ago + 30)).isoformat(),
            updated_at=closed_at,
            status="sl_hit" if outcome == "loss" else "tp3_hit",
            direction=direction,
            entry_type="market_reference",
            reference_price=100.0,
            entry_zone_low=99.0,
            entry_zone_high=101.0,
            stop_loss=95.0,
            tp1=110.0,
            tp2=115.0,
            tp3=120.0,
            risk_reward_tp1=2.0,
            risk_reward_tp2=3.0,
            risk_reward_tp3=4.0,
            max_valid_until=(self.reference + timedelta(hours=4)).isoformat(),
            source_signal_id="test",
            global_score_at_creation=80,
            data_quality_score=80,
            confidence_score=80,
            market_regime="Normal Macro",
            agents_validating=["TechnicalAgent", "MacroAgent", "RiskManagerAgent"],
            agents_contradicting=[],
            evidence_sources=[],
            event_facts_snapshot=[],
            technical_snapshot="test",
            macro_snapshot="test",
            geopolitical_snapshot="test",
            elliott_wave_snapshot="disabled",
            invalidation_rules=[],
            outcome=outcome,
            outcome_reason="test",
            closed_at=closed_at,
        )

    def test_phase7c_news_reaction_wins_when_event_mode_active(self) -> None:
        selection = build_strategy_selection(
            [
                self.candidate("TrendContinuationSetup", confidence=95, confluence=95, preferred_session="london_ny_overlap"),
                self.candidate("NewsReactionSetup", confidence=80, confluence=80),
            ],
            event_mode=EventModeAnalysis(True, 80, "ACTIVE", "freeze", 1.5, ["event"]),
            now=self.reference,
        )
        self.assertEqual(selection.status, "TRADE_READY")
        self.assertIsNotNone(selection.selected_setup)
        self.assertEqual(selection.selected_setup.name, "NewsReactionSetup")
        self.assertTrue(selection.event_mode_active)

    def test_phase7c_trend_continuation_wins_london_ny_overlap_without_event(self) -> None:
        selection = build_strategy_selection(
            [
                self.candidate("PivotRejectionSetup", confidence=90, confluence=90),
                self.candidate("TrendContinuationSetup", confidence=78, confluence=78, preferred_session="london_ny_overlap"),
            ],
            now=self.reference,
        )
        self.assertIsNotNone(selection.selected_setup)
        self.assertEqual(selection.selected_setup.name, "TrendContinuationSetup")
        self.assertEqual(selection.session, "london_ny_overlap")

    def test_phase7c_breakout_requires_two_r_minimum(self) -> None:
        selection = build_strategy_selection(
            [self.candidate("BreakoutDuJourSetup", rr=1.8, preferred_session="london_open")],
            now=datetime(2026, 5, 15, 7, 30, tzinfo=timezone.utc),
        )
        self.assertEqual(selection.status, "NO_SETUP")
        self.assertIn("R/R TP1 1.80R < minimum 2.00R.", selection.rejected_candidates[0]["blockers"])

    def test_phase7c_cooldown_blocks_recent_same_direction_loss(self) -> None:
        ledger = TradeLedgerSummary(
            ledger_path="test",
            generated_at=self.reference.isoformat(),
            quality_gate_status="OK",
            quality_gate_reasons=[],
            recent_trades=[self.trade_plan(outcome="loss", direction="BUY", minutes_ago=30)],
        )
        selection = build_strategy_selection(
            [self.candidate("MeanReversionSetup", direction="BUY", rr=2.2)],
            trade_ledger=ledger,
            now=self.reference,
        )
        self.assertEqual(selection.status, "NO_SETUP")
        self.assertIn("Cooldown MeanReversionSetup", selection.rejected_candidates[0]["blockers"][0])

    def test_phase7c_no_setup_when_all_candidates_are_noise(self) -> None:
        selection = build_strategy_selection(
            [self.candidate("RangeTradingSetup", status="NO_SETUP", direction="NEUTRAL", rr=0.0)],
            now=self.reference,
        )
        self.assertEqual(selection.status, "NO_SETUP")
        self.assertIsNone(selection.selected_setup)
        self.assertEqual(selection.ranked_candidates, [])

    def test_phase7d_inspector_renders_selected_strategy_without_changing_verdict(self) -> None:
        candidates = [
            self.candidate("TrendContinuationSetup", confidence=78, confluence=80, preferred_session="london_ny_overlap"),
            self.candidate("PivotRejectionSetup", confidence=92, confluence=92),
        ]
        selection = build_strategy_selection(candidates, now=self.reference)
        recommendation = TradeRecommendation(
            "global",
            "WAIT",
            55,
            "Signal principal inchange.",
            [],
            0.0,
            0.0,
            0.0,
            "test",
        )
        html = render_monitoring_inspector_panel(
            self.reference.isoformat(),
            None,
            [],
            None,
            None,
            recommendation,
            None,
            None,
            candidates,
            selection,
        )
        self.assertIn("Phase 7D", html)
        self.assertIn("Multi-Strategy", html)
        self.assertIn("TrendContinuationSetup", html)
        self.assertIn("Inspector · WAIT 55/100", html)


if __name__ == "__main__":
    unittest.main()
