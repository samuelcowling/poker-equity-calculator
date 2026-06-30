"""Tests for poker.equity.

Covers:
- win + tie + lose sums to ~1.0 across preflop/flop/river, single and
  multiple opponents.
- AA vs random opponent heads-up preflop matches the published ~85.2% win
  rate within tolerance.
- AA vs KK heads-up preflop matches the published ~81.9% win rate within
  tolerance.
- Cross-validation of the Monte Carlo path against the exact enumeration
  path on a river scenario (forcing Monte Carlo via the internal function
  directly, since exact would normally be chosen there).
- A nut flush on the river vs a random opponent shows very high win
  probability, as a sanity check.
"""

from __future__ import annotations

import random

import pytest

from poker.cards import Deck, parse_cards
from poker.equity import (
    DEFAULT_MC_TRIALS,
    calculate_equity,
    calculate_equity_curve,
    _exact_equity,
    _monte_carlo_equity,
)


def cards(spec: str):
    """Helper: parse a space-separated card spec string, e.g. 'Ah Kh'."""
    return parse_cards(spec.split())


SUM_TOLERANCE = 1e-6


def _assert_sums_to_one(result: dict[str, float]) -> None:
    total = result["win"] + result["tie"] + result["lose"]
    assert total == pytest.approx(1.0, abs=SUM_TOLERANCE), f"probabilities did not sum to 1: {result}"
    for key in ("win", "tie", "lose"):
        assert 0.0 <= result[key] <= 1.0, f"{key} out of [0,1] range: {result}"


# ---------------------------------------------------------------------------
# win + tie + lose ~= 1.0 across scenarios
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "hero_hole,board,num_opponents",
    [
        ("Ah Kh", "", 1),  # preflop, heads-up
        ("Ah Kh", "", 3),  # preflop, multiway
        ("7c 7d", "2h 9s Jc", 1),  # flop, heads-up
        ("7c 7d", "2h 9s Jc", 4),  # flop, multiway
        ("Th 9h", "8h 7h 2c 3d", 2),  # turn
        ("Qs Qd", "Qh 7c 2d 9s 4h", 1),  # river, exact-enumeration path
        ("Qs Qd", "Qh 7c 2d 9s 4h", 2),  # river, exact-enumeration path (2 opp)
        ("Qs Qd", "Qh 7c 2d 9s 4h", 5),  # river, Monte Carlo path (3+ opp)
    ],
)
def test_probabilities_sum_to_one(hero_hole, board, num_opponents):
    # Low trial count here: these checks only verify bookkeeping (the three
    # outcome buckets partition the trials correctly), not precision, so
    # variance doesn't matter and we can keep the suite fast.
    result = calculate_equity(cards(hero_hole), cards(board), num_opponents, trials=2_000)
    _assert_sums_to_one(result)


def test_probabilities_sum_to_one_with_dead_cards():
    result = calculate_equity(
        cards("Ah Kh"),
        cards("2c 9s Jd"),
        num_opponents=3,
        dead_cards=cards("3c 4d 5h"),
        trials=2_000,
    )
    _assert_sums_to_one(result)


# ---------------------------------------------------------------------------
# Published reference win rates (Monte Carlo, heads-up preflop)
# ---------------------------------------------------------------------------


def test_aa_vs_random_opponent_preflop_heads_up():
    # Well-known published value: AA wins ~85.2% heads-up vs a random hand.
    result = calculate_equity(
        cards("As Ad"), [], num_opponents=1, trials=100_000, rng=random.Random(42)
    )
    _assert_sums_to_one(result)
    assert result["win"] == pytest.approx(0.852, abs=0.015)


def test_aa_vs_kk_preflop_heads_up():
    # Well-known published value: AA wins ~81.9% heads-up vs KK specifically.
    # calculate_equity()/the Monte Carlo engine always models opponents as
    # random hands, so to pin the opponent to a specific KK we drive the
    # engine's own Monte Carlo sampling/evaluation logic (deck.deal +
    # evaluate_hand, the same machinery _monte_carlo_equity uses internally)
    # directly with a fixed opponent hand, using a high trial count to keep
    # variance low per the published reference.
    hero_hole = cards("As Ad")
    opp_hole = cards("Ks Kd")
    deck = Deck(known_cards=hero_hole + opp_hole)

    trials = 100_000
    rng = random.Random(99)
    win = tie = lose = 0
    from poker.evaluator import evaluate_hand

    for _ in range(trials):
        board = deck.deal(5, rng=rng)
        hero_best = evaluate_hand(hero_hole + board)
        opp_best = evaluate_hand(opp_hole + board)
        if hero_best > opp_best:
            win += 1
        elif hero_best == opp_best:
            tie += 1
        else:
            lose += 1

    win_rate = win / trials
    assert win_rate == pytest.approx(0.819, abs=0.015)


# ---------------------------------------------------------------------------
# Cross-validation: exact enumeration vs Monte Carlo agree
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "hero_hole,board,num_opponents",
    [
        ("Ah Ac", "Kh 9s 4d 2c 7h", 1),
        ("Th 9h", "8h 7h 2c Jd 5s", 1),
        ("Qs Qd", "Qh 7c 2d 9s 4h", 2),
    ],
)
def test_exact_matches_monte_carlo_on_river(hero_hole, board, num_opponents):
    hero = cards(hero_hole)
    board_cards = cards(board)
    known = hero + board_cards
    deck = Deck(known_cards=known)

    exact = _exact_equity(hero, board_cards, num_opponents, deck)
    mc = _monte_carlo_equity(
        hero, board_cards, num_opponents, deck, trials=30_000, rng=random.Random(7)
    )

    assert exact.win == pytest.approx(mc.win, abs=0.025)
    assert exact.tie == pytest.approx(mc.tie, abs=0.025)
    assert exact.lose == pytest.approx(mc.lose, abs=0.025)


# ---------------------------------------------------------------------------
# Nut flush sanity check
# ---------------------------------------------------------------------------


def test_nut_flush_river_high_win_probability():
    # Hero holds the nut flush (Ace-high hearts flush) on a river where the
    # board doesn't pair or otherwise enable a higher hand category for a
    # random opponent very often.
    hero_hole = cards("Ah Kh")
    board = cards("2h 7h 9h 3c Jd")
    result = calculate_equity(hero_hole, board, num_opponents=1, trials=15_000, rng=random.Random(1))
    _assert_sums_to_one(result)
    assert result["win"] > 0.85


# ---------------------------------------------------------------------------
# Equity curve
# ---------------------------------------------------------------------------


def test_equity_curve_preflop_only():
    curve = calculate_equity_curve(cards("Ah Kh"), [], num_opponents=1, trials=5_000)
    assert [entry["street"] for entry in curve] == ["preflop"]
    _assert_sums_to_one(curve[0])


def test_equity_curve_flop():
    curve = calculate_equity_curve(
        cards("Ah Kh"), cards("2h 9s Jc"), num_opponents=1, trials=5_000
    )
    assert [entry["street"] for entry in curve] == ["preflop", "flop"]
    for entry in curve:
        _assert_sums_to_one(entry)


def test_equity_curve_turn():
    curve = calculate_equity_curve(
        cards("Ah Kh"), cards("2h 9s Jc 4d"), num_opponents=1, trials=5_000
    )
    assert [entry["street"] for entry in curve] == ["preflop", "flop", "turn"]


def test_equity_curve_river():
    curve = calculate_equity_curve(
        cards("Ah Kh"), cards("2h 9s Jc 4d Qh"), num_opponents=1, trials=5_000
    )
    assert [entry["street"] for entry in curve] == ["preflop", "flop", "turn", "river"]
    for entry in curve:
        _assert_sums_to_one(entry)


# ---------------------------------------------------------------------------
# Input validation
# ---------------------------------------------------------------------------


def test_rejects_wrong_hero_hole_count():
    with pytest.raises(ValueError):
        calculate_equity(cards("Ah"), [], num_opponents=1)


def test_rejects_invalid_board_size():
    with pytest.raises(ValueError):
        calculate_equity(cards("Ah Kh"), cards("2h 9s"), num_opponents=1)


def test_rejects_invalid_num_opponents():
    with pytest.raises(ValueError):
        calculate_equity(cards("Ah Kh"), [], num_opponents=0)
    with pytest.raises(ValueError):
        calculate_equity(cards("Ah Kh"), [], num_opponents=9)


def test_rejects_duplicate_cards_across_groups():
    with pytest.raises(ValueError):
        calculate_equity(cards("Ah Kh"), cards("Ah 9s Jc"), num_opponents=1)
