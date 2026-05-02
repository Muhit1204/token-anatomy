import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from token_anatomy.config import get_rates, RATES, MODEL_RATES
from token_anatomy.parser import compute_cost


class TestGetRates:
    def test_known_sonnet(self):
        r = get_rates("claude-sonnet-4-6")
        assert r["input"] == 3.0
        assert r["output"] == 15.0

    def test_known_opus(self):
        r = get_rates("claude-opus-4-7")
        assert r["input"] == 15.0
        assert r["output"] == 75.0

    def test_known_haiku(self):
        r = get_rates("claude-haiku-4-5")
        assert r["input"] == 0.80
        assert r["output"] == 4.0

    def test_date_suffix_stripped(self):
        r = get_rates("claude-haiku-4-5-20251001")
        assert r["input"] == 0.80

    def test_unknown_model_falls_back(self):
        r = get_rates("claude-unknown-model")
        assert r == RATES

    def test_empty_string_falls_back(self):
        r = get_rates("")
        assert r == RATES

    def test_none_equivalent_empty(self):
        r = get_rates(None or "")
        assert r == RATES


class TestComputeCost:
    def test_zero_tokens(self):
        assert compute_cost() == 0.0

    def test_sonnet_input_only(self):
        cost = compute_cost(it=1_000_000, model="claude-sonnet-4-6")
        assert abs(cost - 3.0) < 1e-9

    def test_opus_input_only(self):
        cost = compute_cost(it=1_000_000, model="claude-opus-4-7")
        assert abs(cost - 15.0) < 1e-9

    def test_haiku_input_only(self):
        cost = compute_cost(it=1_000_000, model="claude-haiku-4-5")
        assert abs(cost - 0.80) < 1e-9

    def test_opus_more_expensive_than_sonnet(self):
        sonnet = compute_cost(it=1_000_000, model="claude-sonnet-4-6")
        opus   = compute_cost(it=1_000_000, model="claude-opus-4-7")
        assert opus > sonnet

    def test_haiku_cheaper_than_sonnet(self):
        haiku  = compute_cost(it=1_000_000, ot=1_000_000, model="claude-haiku-4-5")
        sonnet = compute_cost(it=1_000_000, ot=1_000_000, model="claude-sonnet-4-6")
        assert haiku < sonnet

    def test_no_model_uses_fallback(self):
        cost = compute_cost(it=1_000_000)
        assert abs(cost - RATES["input"]) < 1e-9

    def test_cache_read_cheaper_than_input(self):
        input_cost = compute_cost(it=1_000_000, model="claude-sonnet-4-6")
        cache_cost = compute_cost(cr=1_000_000, model="claude-sonnet-4-6")
        assert cache_cost < input_cost

    def test_date_suffix_in_model_string(self):
        cost_with_suffix    = compute_cost(it=1_000_000, model="claude-haiku-4-5-20251001")
        cost_without_suffix = compute_cost(it=1_000_000, model="claude-haiku-4-5")
        assert abs(cost_with_suffix - cost_without_suffix) < 1e-9

    def test_all_token_types(self):
        cost = compute_cost(it=100, ot=100, cr=100, cw=100, model="claude-sonnet-4-6")
        r = MODEL_RATES["claude-sonnet-4-6"]
        expected = (100 * r["input"] + 100 * r["output"] +
                    100 * r["cache_read"] + 100 * r["cache_write"]) / 1_000_000
        assert abs(cost - expected) < 1e-12
