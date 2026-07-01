"""Texas Hold'em Equity Calculator — Streamlit dashboard.

Run with:  streamlit run app.py
"""

from __future__ import annotations

import plotly.graph_objects as go
import streamlit as st

from poker.cards import full_deck
from poker.equity import calculate_equity_curve

# --- Page setup & theme -----------------------------------------------------
st.set_page_config(page_title="Poker Equity Calculator", page_icon="\U0001F0CF", layout="wide")

ACCENT = "#2563eb"
GOOD = "#16a34a"
BAD = "#dc2626"
TIE = "#f59e0b"
GRID = "rgba(148,163,184,0.18)"
STREET_ORDER = ["preflop", "flop", "turn", "river"]
STREET_LABELS = {"preflop": "Preflop", "flop": "Flop", "turn": "Turn", "river": "River"}

st.markdown(
    """
    <style>
      .block-container {padding-top: 2.2rem; max-width: 1250px;}
      h1, h2, h3 {letter-spacing:-0.01em;}
      [data-testid="stMetricValue"] {font-variant-numeric: tabular-nums;}
    </style>
    """,
    unsafe_allow_html=True,
)


def _layout(fig, height=380, ytitle="", xtitle=""):
    fig.update_layout(
        height=height,
        margin=dict(l=10, r=10, t=30, b=10),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font=dict(size=13),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, x=0),
        hovermode="x unified",
    )
    fig.update_xaxes(gridcolor=GRID, zeroline=False, title=xtitle)
    fig.update_yaxes(gridcolor=GRID, zeroline=True, zerolinecolor=GRID, title=ytitle, range=[0, 100])
    return fig


# --- Card picker widgets -----------------------------------------------------
NONE_LABEL = "—"
SUIT_SYMBOL = {"s": "♠", "h": "♥", "d": "♦", "c": "♣"}
ALL_CARD_STRINGS = [str(c) for c in full_deck()]


def _format_card(card_str: str) -> str:
    if card_str == NONE_LABEL:
        return NONE_LABEL
    rank, suit = card_str[0], card_str[1]
    return f"{rank}{SUIT_SYMBOL[suit]}"


def _card_picker(container, label: str, key: str, *, optional: bool) -> str | None:
    """Render a single combined rank+suit selectbox for one card slot (e.g. "A♥").

    Returns the card notation string (e.g. "Ah"), or None if the slot is
    optional and left unset.
    """
    options = ([NONE_LABEL] if optional else []) + ALL_CARD_STRINGS
    picked = container.selectbox(
        label, options, key=key, label_visibility="collapsed", format_func=_format_card
    )
    return None if picked == NONE_LABEL else picked


# --- Header -------------------------------------------------------------------
st.title("\U0001F0CF Texas Hold'em Equity Calculator")

# --- Sidebar: all inputs (hand, board, dead cards, table settings) ------------
# Inputs live in the sidebar so they're always reachable while scrolling the
# results, and the main panel can lead with the answer (win/tie/lose) instead
# of burying it below several screens of input widgets.
st.sidebar.header("Your hand")
hh1, hh2 = st.sidebar.columns(2)
hh1.caption("Card 1")
hero_card_1 = _card_picker(hh1, "Hero card 1", "hero1", optional=False)
hh2.caption("Card 2")
hero_card_2 = _card_picker(hh2, "Hero card 2", "hero2", optional=False)

st.sidebar.header("Community board")
st.sidebar.caption("Fill in order — flop (all 3) before turn, turn before river.")
bf1, bf2, bf3 = st.sidebar.columns(3)
bf1.caption("Flop 1")
flop_1 = _card_picker(bf1, "Flop 1", "flop1", optional=True)
bf2.caption("Flop 2")
flop_2 = _card_picker(bf2, "Flop 2", "flop2", optional=True)
bf3.caption("Flop 3")
flop_3 = _card_picker(bf3, "Flop 3", "flop3", optional=True)
bt, br = st.sidebar.columns(2)
bt.caption("Turn")
turn_card = _card_picker(bt, "Turn", "turn", optional=True)
br.caption("River")
river_card = _card_picker(br, "River", "river", optional=True)

flop_cards = [flop_1, flop_2, flop_3]
flop_filled = [c for c in flop_cards if c is not None]

board_errors: list[str] = []
board: list[str] = []

if 0 < len(flop_filled) < 3:
    board_errors.append("The flop needs all 3 cards filled in (or leave all 3 blank).")
elif len(flop_filled) == 3:
    board.extend(flop_filled)
    if turn_card is not None:
        board.append(turn_card)
        if river_card is not None:
            board.append(river_card)
    elif river_card is not None:
        board_errors.append("River is filled in but turn is blank — fill in the turn first.")
else:
    if turn_card is not None or river_card is not None:
        board_errors.append("Turn/river are filled in but the flop is blank — fill in the flop first.")

st.sidebar.header("Dead cards")
st.sidebar.caption("Cards known to be folded/burned — excluded from opponents' possible hands.")

hero_cards_so_far = [c for c in (hero_card_1, hero_card_2) if c is not None]
used_so_far = set(hero_cards_so_far) | set(board)
dead_card_options = [c for c in ALL_CARD_STRINGS if c not in used_so_far]
dead_cards = st.sidebar.multiselect(
    "Dead cards",
    options=dead_card_options,
    default=[],
    label_visibility="collapsed",
    format_func=_format_card,
)

st.sidebar.markdown("---")
st.sidebar.header("Table settings")
num_players = st.sidebar.slider(
    "Players at the table (incl. you)",
    min_value=2,
    max_value=9,
    value=6,
    help="Opponents modeled = players - 1, each holding uniformly random hole cards (no ranges in v1).",
)
num_opponents = num_players - 1

trials = st.sidebar.select_slider(
    "Monte Carlo trials",
    options=[1_000, 2_000, 3_000, 5_000, 10_000, 30_000],
    value=2_000,
    help="More trials → tighter accuracy, slower runs. The equity curve runs this many "
    "trials per street (up to 4x total), and the pure-Python engine is not vectorized, "
    "so keep this low for snappy reruns — results are cached per exact input. Exact "
    "enumeration is used instead of Monte Carlo whenever the board is complete (river) "
    "with 2 or fewer opponents, regardless of this setting.",
)
seed = st.sidebar.number_input(
    "Random seed",
    min_value=0,
    max_value=10_000,
    value=7,
    step=1,
    help="Fixes the Monte Carlo sampling so results are reproducible for the same inputs.",
)

st.sidebar.markdown("---")
st.sidebar.caption(
    "v1 models opponents with uniformly random hole cards — no hand ranges, no "
    "side pots/all-ins, no deck variants."
)

# --- Validation -----------------------------------------------------------
all_selected = hero_cards_so_far + board + dead_cards
duplicates = {c for c in all_selected if all_selected.count(c) > 1}

errors = list(board_errors)
if len(hero_cards_so_far) != 2:
    errors.append("Select both of your hole cards in the sidebar.")
if duplicates:
    errors.append(f"The same card was selected more than once: {', '.join(sorted(duplicates))}.")

if errors:
    for err in errors:
        st.error(err)
    st.stop()


# --- Cached equity computation ----------------------------------------------
# The headline win/tie/lose metrics always mirror curve[-1] (the entry for
# the current street) rather than running a second, separate
# calculate_equity() call — that way they can never disagree with the
# chart's rightmost point, and the current street's Monte Carlo simulation
# (when used) only runs once instead of twice.
@st.cache_data(show_spinner=False)
def _equity_curve(hero_tuple, board_tuple, dead_tuple, n_opponents, n_trials, rng_seed):
    import random

    from poker.cards import parse_cards

    hero_hole = parse_cards(list(hero_tuple), context="hero hole cards")
    board_cards = parse_cards(list(board_tuple), context="board")
    dead = parse_cards(list(dead_tuple), context="dead cards")
    rng = random.Random(rng_seed)
    return calculate_equity_curve(
        hero_hole, board_cards, n_opponents, dead, trials=n_trials, rng=rng
    )


hero_tuple = tuple(hero_cards_so_far)
board_tuple = tuple(board)
dead_tuple = tuple(sorted(dead_cards))

with st.spinner("Crunching equity…"):
    try:
        curve = _equity_curve(hero_tuple, board_tuple, dead_tuple, num_opponents, trials, seed)
    except ValueError as exc:
        st.error(f"Couldn't compute equity: {exc}")
        st.stop()

result = curve[-1]

# --- Results: win / tie / lose ----------------------------------------------
win_pct = result["win"] * 100
tie_pct = result["tie"] * 100
lose_pct = result["lose"] * 100

street_so_far = STREET_LABELS[curve[-1]["street"]] if curve else "Preflop"
hero_label = " ".join(_format_card(c) for c in hero_cards_so_far)
board_label = " ".join(_format_card(c) for c in board) if board else "no board cards yet"
st.subheader(f"Your equity — {hero_label}")
st.caption(f"Board: {board_label}")

m1, m2, m3 = st.columns(3)
m1.metric("Win", f"{win_pct:.1f}%")
m2.metric("Tie", f"{tie_pct:.1f}%")
m3.metric("Lose", f"{lose_pct:.1f}%")
st.caption(
    f"As of **{street_so_far}**, vs {num_opponents} opponent{'s' if num_opponents != 1 else ''} "
    f"with random hole cards · {len(dead_tuple)} dead card{'s' if len(dead_tuple) != 1 else ''} excluded."
)

bar = go.Figure(
    go.Bar(
        x=["Win", "Tie", "Lose"],
        y=[win_pct, tie_pct, lose_pct],
        marker_color=[GOOD, TIE, BAD],
        text=[f"{v:.1f}%" for v in [win_pct, tie_pct, lose_pct]],
        textposition="outside",
    )
)
_layout(bar, height=320, ytitle="Probability (%)")
st.plotly_chart(bar, width="stretch")

# --- Equity curve across streets --------------------------------------------
st.subheader("Equity curve")
st.caption(
    "Win probability recomputed using only the actual board cards revealed so far — "
    "preflop, then flop/turn/river once you've entered enough community cards."
)

curve_x = [STREET_LABELS[entry["street"]] for entry in curve]
curve_win = [entry["win"] * 100 for entry in curve]
curve_tie = [entry["tie"] * 100 for entry in curve]
curve_lose = [entry["lose"] * 100 for entry in curve]

line = go.Figure()
line.add_trace(go.Scatter(x=curve_x, y=curve_win, name="Win", line=dict(color=GOOD, width=2.6), mode="lines+markers"))
line.add_trace(go.Scatter(x=curve_x, y=curve_tie, name="Tie", line=dict(color=TIE, width=2.0), mode="lines+markers"))
line.add_trace(go.Scatter(x=curve_x, y=curve_lose, name="Lose", line=dict(color=BAD, width=2.0), mode="lines+markers"))
_layout(line, height=380, ytitle="Probability (%)", xtitle="Street")
st.plotly_chart(line, width="stretch")

st.markdown("---")
st.caption(
    "Built with NumPy · Streamlit · Plotly. Engine: from-scratch hand evaluator with exact "
    "enumeration at the river (≤ 2 opponents) and Monte Carlo simulation otherwise."
)
