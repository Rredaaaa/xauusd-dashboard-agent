import unittest
from datetime import datetime, timezone
from pathlib import Path
from tempfile import TemporaryDirectory

from xauusd_agent import (
    AnalysisResult,
    AgentResult,
    BriefingBundle,
    CFTCPositioning,
    ChartStore,
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
    OfficialMacroRates,
    PoliticalStatement,
    PreflightCheck,
    PricePoint,
    SourceSnapshot,
    SymbolSnapshot,
    TechnicalDecision,
    TechnicalReading,
    TradeLedgerSummary,
    TradePlan,
    TradeRecommendation,
    WeekendGoldSnapshot,
    append_audit_log_snapshot,
    build_market_regime_analysis,
    build_monitoring_inspector_payload,
    build_cross_asset_analysis,
    build_event_mode_analysis,
    build_official_macro_rates,
    build_event_facts,
    build_data_quality_snapshot,
    build_trade_ledger_summary,
    build_wgc_etf_flows_analysis,
    build_cftc_positioning_from_rows,
    build_political_statements,
    build_chart_store,
    parse_bea_release_schedule,
    parse_fed_rss_events,
    parse_fomc_calendar_events,
    classify_bias,
    build_passive_agent_results,
    build_payload,
    build_orchestrator_decision,
    build_scenario_plan,
    build_technical_decision,
    price_points_to_candles,
    parse_ig_weekend_gold_snapshot,
    parse_ishares_iau_official_data,
    render_dashboard,
    resample_candles,
    score_headline,
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

    def test_bias_buckets(self) -> None:
        self.assertEqual(classify_bias(6), "bullish")
        self.assertEqual(classify_bias(2), "slightly bullish")
        self.assertEqual(classify_bias(0), "neutral")
        self.assertEqual(classify_bias(-2), "slightly bearish")
        self.assertEqual(classify_bias(-6), "bearish")


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
            tp1=price + 14.0 if is_buy else price - 14.0,
            tp2=price + 28.0 if is_buy else price - 28.0,
            tp3=price + 42.0 if is_buy else price - 42.0,
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
                        agents_validating=["PriceAgent", "MacroAgent"],
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
        self.assertIn("Aureum Flux Trading Desk", dashboard)
        self.assertIn("Decision exploitable et charte live", dashboard)
        self.assertIn("Chef de file", dashboard)
        self.assertIn("Signal locked", dashboard)
        self.assertIn("Investing.com XAU/USD", dashboard)
        self.assertIn("TradingView", dashboard)
        self.assertIn("Scenario Engine v3", dashboard)
        self.assertIn("Scoring et position de chaque agent", dashboard)
        self.assertIn("Positions agents", dashboard)
        self.assertIn("PriceAgent", dashboard)
        self.assertIn("OrchestratorAgent", dashboard)
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

        # Legacy technical modules still exist below the fold during Phase 30A,
        # but they are no longer part of the product navigation.
        self.assertIn("Spot classique et IG Weekend Gold", dashboard)
        self.assertIn("TechnicalDecisionEngine", dashboard)
        self.assertIn("Confluence inter-marches", dashboard)
        self.assertIn("Bloc macro officiel", dashboard)
        self.assertIn("FRED DGS10 | DGS2 | T10YIE | DFII10", dashboard)
        self.assertIn("10Y nominal officiel", dashboard)
        self.assertIn("Controle Yahoo ^TNX", dashboard)
        self.assertIn("FRED DGS10 prioritaire", dashboard)
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
        self.assertIn("Calendrier economique et Fed", dashboard)
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
                    allowed_agents=["PriceAgent"],
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
                name="PriceAgent",
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
            take_profit_1=2425.0,
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
            AgentResult("PriceAgent", "Market", "BUY", 70, 70, "Prix valide."),
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
            self.assertEqual(plan.stop_loss, 2380.0)
            self.assertEqual(plan.tp1, 2425.0)

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
            self.assertEqual(second.active_trades[0].stop_loss, 2380.0)

    def test_trade_ledger_evaluates_sl_outcome(self) -> None:
        gold = self.snapshot("XAU/USD", 2400.0, 2390.0)
        recommendation = TradeRecommendation(
            mode="Global",
            verdict="BUY",
            score=72,
            summary="Signal test.",
            reasons=["Test"],
            stop_loss=2380.0,
            take_profit_1=2425.0,
            take_profit_2=2450.0,
            source_note="Test.",
        )
        quality = DataQualitySnapshot("2026-04-24T00:00:00+00:00", 90, "HIGH", "OK", [], [], [], [], [])
        agents = [
            AgentResult("PriceAgent", "Market", "BUY", 70, 70, "Prix valide."),
            AgentResult("MacroAgent", "Macro", "BUY", 72, 75, "Macro valide."),
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
            gold.price = 2379.0
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
            take_profit_1=2425.0,
            take_profit_2=2450.0,
            source_note="Test.",
        )
        quality = DataQualitySnapshot("2026-04-24T00:00:00+00:00", 90, "HIGH", "OK", [], [], [], [], [])
        agents = [
            AgentResult("PriceAgent", "Market", "BUY", 70, 70, "Prix valide."),
            AgentResult("MacroAgent", "Macro", "BUY", 72, 75, "Macro valide."),
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
        self.assertEqual(len(agents), 11)
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
            AgentResult("OrchestratorAgent", "Decision", "BUY", 66, 74, "Ancien orchestrateur passif."),
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
        active_orchestrator = next(agent for agent in updated_agents if agent.name == "OrchestratorAgent")
        self.assertEqual(active_orchestrator.status, "ACTIVE")
        self.assertFalse(active_orchestrator.experimental)

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
            AgentResult("OrchestratorAgent", "Decision", "BUY", 64, 74, "Ancien orchestrateur passif."),
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
        self.assertEqual(recommendation.verdict, "SELL")
        self.assertEqual(decision.status, "TRADE_SELL")
        self.assertTrue(any("Data quality degradee" in reason for reason in decision.quality_gate_reasons))
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

    def test_trade_gate_ignores_audit_agents_for_locking(self) -> None:
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
            AgentResult("OrchestratorAgent", "Decision", "CAUTION", 55, 64, "Audit."),
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
            self.assertEqual(summary.active_trades[0].agents_contradicting, [])

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
            AgentResult("OrchestratorAgent", "Decision", "BUY", 66, 74, "Ancien orchestrateur passif."),
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


if __name__ == "__main__":
    unittest.main()
