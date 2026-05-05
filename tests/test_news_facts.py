"""Tests Phase 22 - News Facts Engine v3."""
from __future__ import annotations

import unittest

from explanation_layer import validate_phrase
from news_facts import (
    MarketConfirmation,
    NewsFact,
    build_market_confirmation,
    build_news_fact,
    build_trader_action,
    build_why_it_matters,
    classify_fact_type,
    classify_source_tier,
    deduplicate_news_facts,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

def _iran_fact(**kwargs) -> NewsFact:
    defaults = dict(
        title="Iran tensions rise near Strait of Hormuz as oil shipping risk grows",
        source="Reuters",
        source_url="https://reuters.com/test",
        published_at="2026-05-02T10:00:00+00:00",
        category="geopolitical",
        actors=["Iran", "Etats-Unis"],
        locations=["Hormuz"],
        themes=["Iran", "Hormuz", "oil"],
        confirmation_level="unconfirmed_headline",
        market_chain="Iran -> Hormuz -> WTI/Brent -> inflation -> or mixte",
        gold_impact="Aversion geopolitique: si VIX progresse et TIP confirme, bid or.",
        impact_bias="bullish",
        confidence=72,
    )
    defaults.update(kwargs)
    return build_news_fact(**defaults)


def _fed_fact(**kwargs) -> NewsFact:
    defaults = dict(
        title="Fed signals potential rate cut in June meeting",
        source="Bloomberg",
        source_url="https://bloomberg.com/test",
        published_at="2026-05-02T12:00:00+00:00",
        category="macro_fed",
        actors=["Federal Reserve", "Powell"],
        locations=["Washington"],
        themes=["Fed", "taux", "coupure"],
        confirmation_level="confirmed_secondary",
        market_chain="Fed dovish -> taux reels baissent -> DXY faible -> bullish or",
        gold_impact="Une Fed moins restrictive est plutot favorable a l'or.",
        impact_bias="bullish",
        confidence=82,
    )
    defaults.update(kwargs)
    return build_news_fact(**defaults)


# ---------------------------------------------------------------------------
# classify_source_tier
# ---------------------------------------------------------------------------

class SourceTierTests(unittest.TestCase):
    def test_reuters_is_tier_2(self):
        tier, label = classify_source_tier("Reuters")
        self.assertEqual(tier, 2)
        self.assertEqual(label, "Agence majeure")

    def test_bloomberg_is_tier_2(self):
        tier, _ = classify_source_tier("Bloomberg")
        self.assertEqual(tier, 2)

    def test_white_house_is_tier_1(self):
        tier, label = classify_source_tier("White House")
        self.assertEqual(tier, 1)
        self.assertEqual(label, "Source officielle")

    def test_wgc_is_tier_1(self):
        tier, _ = classify_source_tier("World Gold Council")
        self.assertEqual(tier, 1)

    def test_kitco_is_tier_3(self):
        tier, label = classify_source_tier("Kitco")
        self.assertEqual(tier, 3)
        self.assertEqual(label, "Media finance")

    def test_yahoo_is_tier_4(self):
        tier, _ = classify_source_tier("Yahoo Finance")
        self.assertEqual(tier, 4)

    def test_unknown_source_defaults_to_tier_4(self):
        tier, _ = classify_source_tier("Some Unknown Blog")
        self.assertEqual(tier, 4)


# ---------------------------------------------------------------------------
# classify_fact_type
# ---------------------------------------------------------------------------

class FactTypeTests(unittest.TestCase):
    def test_rumor_detected(self):
        result = classify_fact_type("Reportedly Iran plans to blockade Hormuz", "Unknown", 4)
        self.assertEqual(result, "rumor")

    def test_confirmed_fact_from_tier_1(self):
        result = classify_fact_type("Fed announces rate pause at June meeting", "Federal Reserve", 1)
        self.assertEqual(result, "confirmed_fact")

    def test_opinion_from_tier_3(self):
        result = classify_fact_type("Gold could rally if inflation persists, analysts say", "Kitco", 3)
        self.assertEqual(result, "opinion")

    def test_unconfirmed_headline_default(self):
        result = classify_fact_type("Iran tensions rise near Strait of Hormuz", "Daily Sabah", 3)
        self.assertEqual(result, "unconfirmed_headline")

    def test_market_analysis_with_numbers(self):
        result = classify_fact_type("Gold falls 1.2% as dollar strengthens", "Bloomberg", 2)
        self.assertEqual(result, "market_analysis")


# ---------------------------------------------------------------------------
# build_market_confirmation
# ---------------------------------------------------------------------------

class MarketConfirmationTests(unittest.TestCase):
    def test_geo_oil_fact_confirmed_when_oil_rises(self):
        conf = build_market_confirmation(
            category="geopolitical",
            themes=["Iran", "Hormuz", "oil"],
            impact_bias="bullish",
            wti_change=+1.5,
            brent_change=+1.2,
            dxy_change=-0.3,
            gold_change=+0.4,
        )
        self.assertTrue(conf.oil_confirms)
        self.assertTrue(conf.dxy_confirms)
        self.assertTrue(conf.gold_confirms)
        self.assertGreaterEqual(conf.confirmation_score, 2)

    def test_geo_oil_fact_not_confirmed_when_oil_falls(self):
        conf = build_market_confirmation(
            category="geopolitical",
            themes=["Iran", "Hormuz", "oil"],
            impact_bias="bullish",
            wti_change=-2.5,
            brent_change=-2.0,
            dxy_change=+0.1,
            gold_change=-0.2,
        )
        self.assertFalse(conf.oil_confirms, "Oil qui baisse ne confirme pas un fait bullish geo")
        self.assertEqual(conf.oil_trend, "baisse")

    def test_fed_dovish_confirmed_when_rates_fall(self):
        conf = build_market_confirmation(
            category="macro_fed",
            themes=["Fed", "taux"],
            impact_bias="bullish",
            dxy_change=-0.4,
            rates_change_bps=-4.0,
            gold_change=+0.5,
        )
        self.assertTrue(conf.rates_confirm)
        self.assertTrue(conf.dxy_confirms)
        self.assertTrue(conf.gold_confirms)
        self.assertGreaterEqual(conf.confirmation_score, 2)

    def test_oil_unavailable_shows_indisponible(self):
        conf = build_market_confirmation(
            category="geopolitical",
            themes=["Iran"],
            impact_bias="bullish",
        )
        self.assertEqual(conf.oil_trend, "indisponible")

    def test_summary_mentions_oil_and_dxy(self):
        conf = build_market_confirmation(
            category="geopolitical",
            themes=["oil"],
            impact_bias="bullish",
            wti_change=-2.5,
            dxy_change=+0.2,
        )
        self.assertIn("Oil", conf.summary)
        self.assertIn("DXY", conf.summary)

    def test_zero_score_when_nothing_confirms(self):
        conf = build_market_confirmation(
            category="geopolitical",
            themes=["Iran", "oil"],
            impact_bias="bullish",
            wti_change=-3.0,
            dxy_change=+0.5,
            gold_change=-0.5,
        )
        self.assertEqual(conf.confirmation_score, 0)
        self.assertIn("Validation marche absente", conf.summary)
        self.assertEqual(validate_phrase(conf.summary), [])


# ---------------------------------------------------------------------------
# build_trader_action
# ---------------------------------------------------------------------------

class TraderActionTests(unittest.TestCase):
    def _conf(self, score: int) -> MarketConfirmation:
        c = MarketConfirmation()
        c.confirmation_score = score
        c.summary = f"Score {score}/4"
        return c

    def test_watch_buy_when_bullish_and_confirmed(self):
        action, detail = build_trader_action("bullish", self._conf(3), "confirmed_fact", 85)
        self.assertEqual(action, "WATCH_BUY")
        self.assertIn("Trigger", detail)

    def test_wait_when_bullish_but_not_confirmed(self):
        action, detail = build_trader_action("bullish", self._conf(0), "unconfirmed_headline", 72)
        self.assertEqual(action, "WAIT")
        self.assertEqual(validate_phrase(detail), [])

    def test_watch_sell_when_bearish_and_confirmed(self):
        action, detail = build_trader_action("bearish", self._conf(2), "confirmed_fact", 80)
        self.assertEqual(action, "WATCH_SELL")
        self.assertEqual(validate_phrase(detail), [])

    def test_no_trade_on_rumor(self):
        action, detail = build_trader_action("bullish", self._conf(3), "rumor", 90)
        self.assertEqual(action, "NO_TRADE")
        self.assertIn("Rumeur", detail)

    def test_wait_on_low_confidence(self):
        action, detail = build_trader_action("bullish", self._conf(3), "confirmed_fact", 40)
        self.assertEqual(action, "WAIT")
        self.assertIn("Confiance", detail)

    def test_wait_on_opinion(self):
        action, _ = build_trader_action("bullish", self._conf(3), "opinion", 80)
        self.assertEqual(action, "WAIT")


# ---------------------------------------------------------------------------
# build_news_fact (integration)
# ---------------------------------------------------------------------------

class NewsfactIntegrationTests(unittest.TestCase):
    def test_iran_fact_with_falling_oil_gets_wait(self):
        fact = _iran_fact(wti_change=-2.5, brent_change=-2.0, dxy_change=+0.1, gold_change=-0.2)
        self.assertIn(fact.trader_action, ("WAIT", "NO_TRADE"))
        self.assertFalse(fact.market_confirmation.oil_confirms)

    def test_iran_fact_with_rising_oil_gets_watch_buy(self):
        fact = _iran_fact(wti_change=+1.5, brent_change=+1.2, dxy_change=-0.3, gold_change=+0.4)
        self.assertEqual(fact.trader_action, "WATCH_BUY")
        self.assertTrue(fact.market_confirmed)

    def test_fed_fact_has_correct_source_tier(self):
        fact = _fed_fact()
        self.assertEqual(fact.source_tier, 2)
        self.assertEqual(fact.source_tier_label, "Agence majeure")

    def test_why_it_matters_not_empty(self):
        fact = _iran_fact()
        self.assertGreater(len(fact.why_it_matters), 20)

    def test_market_confirmation_summary_in_fact(self):
        fact = _iran_fact(wti_change=-2.0)
        self.assertIn("Oil", fact.market_confirmation.summary)

    def test_fact_type_label_is_human_readable(self):
        fact = _iran_fact()
        self.assertIn(fact.fact_type_label, list(["Headline non confirmee", "Media finance",
            "Fait confirme", "Opinion / analyse", "Rumeur / non sourcee", "Analyse marche"]))

    def test_rumor_headline_gets_no_trade(self):
        fact = build_news_fact(
            title="Reportedly Iran may close Hormuz by weekend, unconfirmed",
            source="Unknown Blog",
            source_url="", published_at="2026-05-02T10:00:00+00:00",
            category="geopolitical",
            actors=["Iran"], locations=["Hormuz"], themes=["Iran"],
            confirmation_level="rumor",
            market_chain="", gold_impact="", impact_bias="bullish", confidence=40,
        )
        self.assertEqual(fact.trader_action, "NO_TRADE")

    def test_rendered_news_fact_fields_pass_editorial_validator(self):
        facts = [
            _iran_fact(wti_change=-2.5, brent_change=-2.0, dxy_change=+0.1, gold_change=-0.2),
            _iran_fact(wti_change=+1.5, brent_change=+1.2, dxy_change=-0.3, gold_change=+0.4),
            _fed_fact(dxy_change=-0.4, rates_change_bps=-4.0, gold_change=+0.5),
        ]
        for fact in facts:
            fields = [
                fact.why_it_matters,
                fact.market_confirmation.summary,
                fact.gold_impact,
                fact.trader_action_detail,
            ]
            for text in fields:
                self.assertEqual(validate_phrase(text), [], text)


# ---------------------------------------------------------------------------
# Deduplication
# ---------------------------------------------------------------------------

class DeduplicationTests(unittest.TestCase):
    def _make(self, title: str, source: str = "Reuters", tier_source: str = "Reuters") -> NewsFact:
        return _iran_fact(title=title, source=source)

    def test_identical_headlines_deduplicated(self):
        f1 = self._make("Iran tensions rise near Strait of Hormuz as oil shipping grows")
        f2 = self._make("Iran tensions rise near Strait of Hormuz as oil shipping grows")
        result = deduplicate_news_facts([f1, f2])
        self.assertEqual(len(result), 1)

    def test_similar_headlines_deduplicated(self):
        f1 = self._make("Iran tensions rise near Strait of Hormuz")
        f2 = self._make("Tensions rise near Strait of Hormuz as Iran threat grows")
        result = deduplicate_news_facts([f1, f2])
        self.assertEqual(len(result), 1)

    def test_different_headlines_kept(self):
        f1 = self._make("Iran tensions rise near Strait of Hormuz")
        f2 = _fed_fact()
        result = deduplicate_news_facts([f1, f2])
        self.assertEqual(len(result), 2)

    def test_best_source_kept_on_dedup(self):
        f_reuters = self._make("Iran tensions near Hormuz", source="Reuters")
        f_blog = self._make("Iran tensions near Strait of Hormuz", source="Unknown Blog")
        result = deduplicate_news_facts([f_blog, f_reuters])
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0].source, "Reuters")

    def test_empty_list_returns_empty(self):
        self.assertEqual(deduplicate_news_facts([]), [])

    def test_no_false_dedup_on_unrelated(self):
        f1 = self._make("Iran oil threat grows near Hormuz")
        f2 = _fed_fact()
        result = deduplicate_news_facts([f1, f2])
        self.assertEqual(len(result), 2)


if __name__ == "__main__":
    unittest.main()
