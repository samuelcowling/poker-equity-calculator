"""Equity calculation engine for Texas Hold'em.

Given a hero's two hole cards, the currently known community board (0, 3, 4,
or 5 cards), a number of opponents, and any additional "dead" cards to
exclude from the unseen pool, this module computes the hero's win/tie/lose
probabilities against opponents holding uniformly-random hole cards (no
ranges in v1).

Two computation strategies are used depending on feasibility:

- Exact enumeration: only when the board is complete (river, 5 cards) AND
  there are at most 2 opponents. Every possible assignment of opponents'
  hole cards from the remaining unseen deck is enumerated exhaustively (no
  sampling) and evaluated.
- Monte Carlo simulation: used for everything else (preflop, flop, turn, or
  river with 3+ opponents). Missing board cards and all opponents' hole
  cards are randomly sampled (without replacement, respecting dead cards)
  over many trials.

Also exposes `calculate_equity_curve`, which recomputes equity using just the
first 0 (preflop), 3 (flop), 4 (turn), and 5 (river) cards of the actual
board provided, for whichever streets are currently determined.
"""

from __future__ import annotations

import random
from dataclasses import dataclass
from itertools import combinations
from typing import Sequence

from poker.cards import Card, Deck
from poker.evaluator import evaluate_hand

# Default number of Monte Carlo trials. At 30,000 trials, simulation error is
# roughly +-0.5 percentage points (95% CI) for win probabilities in the
# typical 20-85% range, which is precise enough for an interactive UI.
DEFAULT_MC_TRIALS = 30_000

# Exact enumeration is only used at the river (board fully known) and with at
# most this many opponents, since combinatorial cost grows quickly:
#   1 opponent: C(45, 2)  ~= 990 hole-card combos to evaluate
#   2 opponents: C(45, 4) 4-card combos, each split 3 ways into two 2-card
#                hole hands ~= 894K (hero, opp1, opp2) deals to tally, though
#                each unique 2-card hole hand is only run through the (more
#                expensive) hand evaluator once thanks to caching - see
#                `_exact_equity`.
# Both are fast in pure Python; 3+ opponents would blow up combinatorially
# and falls back to Monte Carlo instead.
MAX_EXACT_OPPONENTS = 2

BOARD_SIZE_TO_STREET = {0: "preflop", 3: "flop", 4: "turn", 5: "river"}


@dataclass(frozen=True)
class EquityResult:
    win: float
    tie: float
    lose: float

    def as_dict(self) -> dict[str, float]:
        return {"win": self.win, "tie": self.tie, "lose": self.lose}


def _validate_inputs(
    hero_hole: Sequence[Card], board: Sequence[Card], num_opponents: int
) -> None:
    if len(hero_hole) != 2:
        raise ValueError(f"hero_hole must contain exactly 2 cards, got {len(hero_hole)}")
    if len(board) not in (0, 3, 4, 5):
        raise ValueError(
            f"board must contain 0, 3, 4, or 5 cards (preflop/flop/turn/river), got {len(board)}"
        )
    if not (1 <= num_opponents <= 8):
        raise ValueError(f"num_opponents must be between 1 and 8, got {num_opponents}")


def _validate_trials(trials: int) -> None:
    if trials < 1:
        raise ValueError(f"trials must be >= 1, got {trials}")


def _known_cards(
    hero_hole: Sequence[Card], board: Sequence[Card], dead_cards: Sequence[Card] | None
) -> list[Card]:
    known: list[Card] = list(hero_hole) + list(board)
    if dead_cards:
        known += list(dead_cards)
    if len(set(known)) != len(known):
        raise ValueError(f"Duplicate cards across hero_hole/board/dead_cards: {known}")
    return known


def calculate_equity(
    hero_hole: Sequence[Card],
    board: Sequence[Card],
    num_opponents: int,
    dead_cards: Sequence[Card] | None = None,
    *,
    trials: int = DEFAULT_MC_TRIALS,
    rng: random.Random | None = None,
) -> dict[str, float]:
    """Compute hero's win/tie/lose probabilities.

    Args:
        hero_hole: exactly 2 cards.
        board: 0, 3, 4, or 5 community cards (preflop/flop/turn/river).
        num_opponents: number of opponents (1-8), each modeled as holding
            uniformly random hole cards from the remaining unseen deck.
        dead_cards: optional additional cards (already-folded/burned, etc.)
            to exclude from the unseen pool, on top of hero_hole and board.
        trials: number of Monte Carlo trials to use when exact enumeration
            isn't feasible. Must be >= 1. Ignored when exact enumeration is
            used.
        rng: optional random.Random instance for reproducibility/testing.
            Ignored when exact enumeration is used.

    Returns:
        {"win": float, "tie": float, "lose": float} summing to ~1.0. If hero
        ties for best hand among N players, that counts as a tie (not a win).

    Raises:
        ValueError: if inputs are malformed (see `_validate_inputs`), if
            `trials < 1`, or if the unseen pool (after removing hero hole,
            board, and dead cards) doesn't contain enough cards to deal the
            requested number of opponents' hole cards (and, when the board
            isn't complete, the remaining board cards).
    """
    _validate_inputs(hero_hole, board, num_opponents)
    _validate_trials(trials)
    known = _known_cards(hero_hole, board, dead_cards)
    deck = Deck(known_cards=known)

    cards_needed = (5 - len(board)) + 2 * num_opponents
    if cards_needed > len(deck):
        raise ValueError(
            f"Not enough unseen cards to deal {cards_needed} cards "
            f"(2 per opponent for {num_opponents} opponent(s) plus "
            f"{5 - len(board)} remaining board card(s)): only {len(deck)} "
            "unseen cards remain. Reduce the number of dead cards or opponents."
        )

    if len(board) == 5 and num_opponents <= MAX_EXACT_OPPONENTS:
        result = _exact_equity(list(hero_hole), list(board), num_opponents, deck)
    else:
        result = _monte_carlo_equity(
            list(hero_hole), list(board), num_opponents, deck, trials=trials, rng=rng
        )
    return result.as_dict()


def calculate_equity_curve(
    hero_hole: Sequence[Card],
    board: Sequence[Card],
    num_opponents: int,
    dead_cards: Sequence[Card] | None = None,
    *,
    trials: int = DEFAULT_MC_TRIALS,
    rng: random.Random | None = None,
) -> list[dict[str, object]]:
    """Compute the equity curve across streets, using only the ACTUAL board
    cards the user has entered so far (no hypothetical future cards).

    For whichever streets are currently determined given len(board), returns
    one entry per street using the first 0 (preflop), 3 (flop), 4 (turn), and
    5 (river) cards of the actual board. E.g. if the user has entered a
    4-card board (turn), the curve includes preflop, flop, and turn entries
    (river is not yet determined, so it is omitted).

    Each street's Monte Carlo simulation (when used) draws from its own fresh
    `random.Random` seeded deterministically from `rng`/`seed`, rather than
    sharing a single advancing RNG stream across streets. This keeps each
    street's result reproducible independent of how many trials earlier
    streets consumed, and means the river entry of the curve always matches
    a standalone `calculate_equity` call made with the same `rng`/seed for
    that same river board (e.g. the headline win/tie/lose metrics in app.py).

    Returns:
        list of {"street": str, "win": float, "tie": float, "lose": float},
        ordered preflop -> flop -> turn -> river, for each street whose board
        prefix length is <= len(board).
    """
    _validate_inputs(hero_hole, board, num_opponents)
    _validate_trials(trials)
    board = list(board)

    # Derive an independent, deterministic RNG per street from the caller's
    # rng (or from a fresh unseeded Random if none was given) so that one
    # street's Monte Carlo sampling never advances another street's stream.
    seed_source = rng if rng is not None else random.Random()

    curve: list[dict[str, object]] = []
    for prefix_len, street in BOARD_SIZE_TO_STREET.items():
        if prefix_len > len(board):
            continue
        prefix_board = board[:prefix_len]
        street_rng = random.Random(seed_source.random())
        equity = calculate_equity(
            hero_hole, prefix_board, num_opponents, dead_cards, trials=trials, rng=street_rng
        )
        curve.append({"street": street, **equity})

    # Sort into canonical street order (dict iteration above is already in
    # that order since BOARD_SIZE_TO_STREET is defined ascending, but be
    # explicit/defensive in case of future reordering).
    street_order = {"preflop": 0, "flop": 1, "turn": 2, "river": 3}
    curve.sort(key=lambda entry: street_order[entry["street"]])
    return curve


# ---------------------------------------------------------------------------
# Exact enumeration (river, <=2 opponents)
# ---------------------------------------------------------------------------


def _exact_equity(
    hero_hole: list[Card], board: list[Card], num_opponents: int, deck: Deck
) -> EquityResult:
    """Exhaustively enumerate every possible assignment of opponents' hole
    cards from the unseen deck and tally exact win/tie/lose probabilities.
    """
    unseen = deck.unseen_cards
    hero_best = evaluate_hand(hero_hole + board)

    win = tie = lose = 0
    total = 0

    # Precompute and cache each unique 2-card hole hand's best-hand-with-board
    # result once. The board is fixed for the whole enumeration, so a given
    # hole-card pair always evaluates to the same HandRank regardless of which
    # other cards are dealt to other opponents - caching avoids re-running the
    # (relatively expensive) 7-card evaluator on the same hole pair thousands
    # of times across different combinations.
    hole_pair_rank: dict[tuple[Card, Card], object] = {}
    for hole in combinations(unseen, 2):
        hole_pair_rank[hole] = evaluate_hand(list(hole) + board)

    if num_opponents == 1:
        for opp_hole, opp_best in hole_pair_rank.items():
            win, tie, lose = _tally(hero_best, [opp_best], win, tie, lose)
            total += 1
    elif num_opponents == 2:
        for combo in combinations(unseen, 4):
            # Split the 4 drawn cards into two opponents' 2-card hole hands.
            # Only the 3 unordered partitions matter for hero's win/tie/lose
            # outcome (swapping which named opponent holds which pair doesn't
            # change max(opponent_bests)), so enumerate 3 partitions per
            # 4-combo rather than all 6 ordered splits.
            a, b, c, d = combo
            partitions = (((a, b), (c, d)), ((a, c), (b, d)), ((a, d), (b, c)))
            for opp1_hole, opp2_hole in partitions:
                opp1_best = hole_pair_rank[opp1_hole]
                opp2_best = hole_pair_rank[opp2_hole]
                win, tie, lose = _tally(hero_best, [opp1_best, opp2_best], win, tie, lose)
                total += 1
    else:
        raise ValueError(
            f"_exact_equity only supports up to {MAX_EXACT_OPPONENTS} opponents, got {num_opponents}"
        )

    return EquityResult(win=win / total, tie=tie / total, lose=lose / total)


def _tally(
    hero_best, opponent_bests: list, win: int, tie: int, lose: int
) -> tuple[int, int, int]:
    best_among_opponents = max(opponent_bests)
    if hero_best > best_among_opponents:
        win += 1
    elif hero_best == best_among_opponents:
        tie += 1
    else:
        lose += 1
    return win, tie, lose


# ---------------------------------------------------------------------------
# Monte Carlo simulation (preflop/flop/turn, or river with 3+ opponents)
# ---------------------------------------------------------------------------


def _monte_carlo_equity(
    hero_hole: list[Card],
    board: list[Card],
    num_opponents: int,
    deck: Deck,
    *,
    trials: int = DEFAULT_MC_TRIALS,
    rng: random.Random | None = None,
) -> EquityResult:
    cards_needed_for_board = 5 - len(board)
    cards_per_trial = cards_needed_for_board + 2 * num_opponents

    win = tie = lose = 0
    for _ in range(trials):
        dealt = deck.deal(cards_per_trial, rng=rng)
        board_fill = dealt[:cards_needed_for_board]
        full_board = board + board_fill

        hero_best = evaluate_hand(hero_hole + full_board)

        opponent_bests = []
        offset = cards_needed_for_board
        for _ in range(num_opponents):
            opp_hole = dealt[offset : offset + 2]
            offset += 2
            opponent_bests.append(evaluate_hand(opp_hole + full_board))

        win, tie, lose = _tally(hero_best, opponent_bests, win, tie, lose)

    return EquityResult(win=win / trials, tie=tie / trials, lose=lose / trials)
