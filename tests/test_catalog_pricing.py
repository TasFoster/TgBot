from __future__ import annotations

from bot.services.catalog import _final_price


def test_zero_cost_is_passthrough() -> None:
    assert _final_price(0, 15) == 0


def test_no_markup_returns_cost() -> None:
    assert _final_price(100, 0) == 100


def test_basic_markup() -> None:
    assert _final_price(100, 15) == 115
    assert _final_price(200, 50) == 300


def test_markup_rounds_half_up() -> None:
    # 1 ⭐ * 1.15 = 1.15 → round to 1
    assert _final_price(1, 15) == 1
    # 3 ⭐ * 1.15 = 3.45 → 3
    assert _final_price(3, 15) == 3
    # 7 ⭐ * 1.15 = 8.05 → 8
    assert _final_price(7, 15) == 8


def test_minimum_one_when_positive_cost() -> None:
    # 1 ⭐ * 0 = 0 normally → forced to 1 only if markup applied; with 0% it's still cost
    # Edge: a tiny cost with negative-ish rounding never goes below 1
    assert _final_price(1, 0) == 1
