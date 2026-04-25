import unittest

from xauusd_agent import (
    AnalysisResult,
    BriefingBundle,
    EventModeAnalysis,
    GeopoliticalAnalysis,
    NewsItem,
    PricePoint,
    SymbolSnapshot,
    TechnicalReading,
    TradeRecommendation,
    WeekendGoldSnapshot,
    build_cross_asset_analysis,
    build_event_mode_analysis,
    classify_bias,
    parse_ig_weekend_gold_snapshot,
    render_dashboard,
    score_headline,
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
        )
        dashboard = render_dashboard(bundle)
        self.assertIn("Dashboard XAUUSD", dashboard)
        self.assertIn("Scenario hausse", dashboard)
        self.assertIn("Resume executif test.", dashboard)
        self.assertIn("Verdict: BUY", dashboard)
        self.assertIn("Verdict: SELL", dashboard)
        self.assertIn("Investing.com XAU/USD", dashboard)
        self.assertIn("Proxy week-end IG", dashboard)
        self.assertIn("IG Weekend Gold", dashboard)
        self.assertIn("Synthese prioritaire", dashboard)
        self.assertIn("Headlines expliquees", dashboard)
        self.assertIn("Confluence inter-marches", dashboard)
        self.assertIn("Lecture geo test.", dashboard)


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


if __name__ == "__main__":
    unittest.main()
