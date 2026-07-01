"""Quick AppTest-based verification for app.py (Streamlit UI smoke test).

Run with:  .venv\\Scripts\\python.exe verify_app.py

Streamlit's preview/screenshot tooling has a known cross-origin issue with
Streamlit apps (see sibling blackjack-ev-simulator project), so this verifies
via streamlit.testing.v1.AppTest instead of a live browser preview.
"""

from __future__ import annotations

import sys

from streamlit.testing.v1 import AppTest


def _set_card(at: AppTest, key: str, rank: str, suit: str) -> None:
    # Each card slot is a single combined rank+suit selectbox keyed by `key`,
    # with options being raw card notation strings (e.g. "Ah").
    at.selectbox(key=key).set_value(f"{rank}{suit}")


def _get_metric_values(at: AppTest) -> dict[str, float]:
    values = {}
    for metric in at.get("metric"):
        label = metric.label
        raw = metric.value  # e.g. "63.2%"
        values[label] = float(raw.strip().rstrip("%"))
    return values


def run_scenario(name: str, configure) -> None:
    print(f"=== Scenario: {name} ===")
    at = AppTest.from_file("app.py")
    at.run(timeout=60)
    configure(at)
    at.run(timeout=60)

    if at.exception:
        for exc in at.exception:
            print("EXCEPTION:", exc)
        raise SystemExit(f"FAILED: {name} raised an exception")

    metrics = _get_metric_values(at)
    win = metrics.get("Win")
    tie = metrics.get("Tie")
    lose = metrics.get("Lose")
    if win is None or tie is None or lose is None:
        raise SystemExit(f"FAILED: {name} did not display Win/Tie/Lose metrics, got {metrics}")

    total = win + tie + lose
    print(f"Win={win}%  Tie={tie}%  Lose={lose}%  Total={total}%")
    if not (99.0 <= total <= 101.0):
        raise SystemExit(f"FAILED: {name} win+tie+lose={total} not ~100%")

    print(f"PASSED: {name}\n")


def scenario_preflop_heads_up(at: AppTest) -> None:
    # Hero: Ah Ks, 2 players (1 opponent), preflop only.
    _set_card(at, "hero1", "A", "h")
    _set_card(at, "hero2", "K", "s")
    # The players slider is keyed implicitly by Streamlit (no explicit key set in
    # app.py), so locate it positionally instead.
    at.slider[0].set_value(2)


def scenario_flop(at: AppTest) -> None:
    _set_card(at, "hero1", "A", "h")
    _set_card(at, "hero2", "K", "s")
    _set_card(at, "flop1", "2", "c")
    _set_card(at, "flop2", "7", "d")
    _set_card(at, "flop3", "Q", "h")
    at.slider[0].set_value(4)


def scenario_river_dead_cards(at: AppTest) -> None:
    _set_card(at, "hero1", "A", "h")
    _set_card(at, "hero2", "K", "s")
    _set_card(at, "flop1", "2", "c")
    _set_card(at, "flop2", "7", "d")
    _set_card(at, "flop3", "Q", "h")
    _set_card(at, "turn", "9", "s")
    _set_card(at, "river", "3", "d")
    at.slider[0].set_value(3)
    at.multiselect[0].set_value(["4c", "5c"])


def check_duplicate_validation() -> None:
    print("=== Scenario: duplicate-card validation ===")
    at = AppTest.from_file("app.py")
    at.run(timeout=60)
    _set_card(at, "hero1", "A", "h")
    _set_card(at, "hero2", "A", "h")  # duplicate of hero1
    at.run(timeout=60)
    if at.exception:
        for exc in at.exception:
            print("EXCEPTION:", exc)
        raise SystemExit("FAILED: duplicate-card validation raised an exception instead of a clean error")
    if not at.error:
        raise SystemExit("FAILED: duplicate-card validation did not surface an st.error")
    print("Errors shown:", [e.value for e in at.error])
    print("PASSED: duplicate-card validation\n")


def check_betting_advice_strong_hand() -> None:
    print("=== Scenario: betting advice for a strong hand (river) ===")
    at = AppTest.from_file("app.py")
    at.run(timeout=60)
    # Hero has the stone-cold nuts (quad aces) on this river - should be a
    # clear "Strong value" bet, not a check.
    _set_card(at, "hero1", "A", "s")
    _set_card(at, "hero2", "A", "c")
    _set_card(at, "flop1", "A", "h")
    _set_card(at, "flop2", "A", "d")
    _set_card(at, "flop3", "2", "c")
    _set_card(at, "turn", "7", "d")
    _set_card(at, "river", "9", "h")
    at.slider[0].set_value(2)
    at.run(timeout=60)
    if at.exception:
        for exc in at.exception:
            print("EXCEPTION:", exc)
        raise SystemExit("FAILED: strong-hand betting-advice scenario raised an exception")
    if not at.success:
        raise SystemExit("FAILED: expected a 'bet' recommendation (st.success) for quad aces")
    advice_text = at.success[0].value
    print("Advice shown:", advice_text)
    if "Strong value" not in advice_text or "Bet $" not in advice_text:
        raise SystemExit(f"FAILED: expected a 'Strong value' bet recommendation, got: {advice_text}")
    print("PASSED: betting advice for a strong hand (river)\n")


def check_betting_advice_weak_hand() -> None:
    print("=== Scenario: betting advice for a weak hand (river) ===")
    at = AppTest.from_file("app.py")
    at.run(timeout=60)
    # Hero has ace-high with no pair/draw on a river vs 8 opponents - should
    # be a clear "check" recommendation, not a bet.
    _set_card(at, "hero1", "A", "h")
    _set_card(at, "hero2", "2", "d")
    _set_card(at, "flop1", "5", "c")
    _set_card(at, "flop2", "9", "s")
    _set_card(at, "flop3", "J", "d")
    _set_card(at, "turn", "3", "h")
    _set_card(at, "river", "8", "c")
    at.slider[0].set_value(9)
    at.run(timeout=60)
    if at.exception:
        for exc in at.exception:
            print("EXCEPTION:", exc)
        raise SystemExit("FAILED: weak-hand betting-advice scenario raised an exception")
    if not at.info:
        raise SystemExit("FAILED: expected a 'check' recommendation (st.info) for weak ace-high vs 8 opponents")
    advice_text = at.info[0].value
    print("Advice shown:", advice_text)
    if "Check" not in advice_text:
        raise SystemExit(f"FAILED: expected a 'Check' recommendation, got: {advice_text}")
    print("PASSED: betting advice for a weak hand (river)\n")


def check_equity_curve_present() -> None:
    print("=== Scenario: equity curve rendered after river ===")
    at = AppTest.from_file("app.py")
    at.run(timeout=60)
    scenario_river_dead_cards(at)
    at.run(timeout=60)
    if at.exception:
        raise SystemExit("FAILED: equity curve scenario raised an exception")
    charts = at.get("plotly_chart")
    if len(charts) < 2:
        raise SystemExit(f"FAILED: expected at least 2 plotly charts (bar + curve), found {len(charts)}")
    print(f"Found {len(charts)} plotly charts (win/tie/lose bar + equity curve).")
    print("PASSED: equity curve rendered after river\n")


if __name__ == "__main__":
    run_scenario("preflop heads-up (AhKs, 2 players)", scenario_preflop_heads_up)
    run_scenario("flop (AhKs on 2c7dQh, 4 players)", scenario_flop)
    run_scenario("river with dead cards (3 players, 2 dead cards)", scenario_river_dead_cards)
    check_duplicate_validation()
    check_betting_advice_strong_hand()
    check_betting_advice_weak_hand()
    check_equity_curve_present()
    print("All scenarios passed with zero exceptions.")
