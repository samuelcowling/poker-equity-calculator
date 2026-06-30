# Poker Equity Calculator

A Texas Hold'em equity calculator (Python/Streamlit) that computes win / tie /
lose probabilities for a hero hand against random opponents, given any
combination of hole cards, board cards, and dead cards.

Features a from-scratch hand evaluator (no external poker library), exact
enumeration at the river when there are 2 or fewer opponents, Monte Carlo
simulation otherwise, and a Streamlit UI with an equity-curve chart showing
how the hero's equity evolved across preflop → flop → turn → river as the
actual board cards were revealed.

This is a sibling portfolio project to `blackjack-ev-simulator` (same
Python/Streamlit stack and style), but is a fully standalone repo.

## Card notation

- **Ranks**: `2 3 4 5 6 7 8 9 T J Q K A` (T = Ten). Case-insensitive on input
  and normalized internally.
- **Suits**: `s h d c` (spades, hearts, diamonds, clubs). Case-insensitive on
  input.
- A card is a 2-character rank+suit string, e.g. `Ah` = Ace of hearts, `Td` =
  Ten of diamonds, `2c` = Two of clubs.

## Setup

Requires Python 3.14. On Windows / PowerShell:

```powershell
python -m venv .venv
.venv\Scripts\python.exe -m pip install -r requirements.txt
```

(No activation script needed — invoke tools directly via
`.venv\Scripts\python.exe`, which works reliably in non-interactive shells.)

## Running the app

```powershell
.venv\Scripts\python.exe -m streamlit run app.py
```

This opens the dashboard in your browser. Enter your two hole cards, any
known board cards (flop/turn/river, filled in order), the number of players
at the table, and optionally mark dead cards, to see your win/tie/lose
probabilities and the equity curve across streets.

## Running tests

```powershell
.venv\Scripts\python.exe -m pytest
```

There's also `verify_app.py`, a `streamlit.testing.v1.AppTest`-based smoke
test that drives the actual Streamlit UI end-to-end (card pickers, sliders,
dead-card multiselect) across several scenarios and checks the rendered
metrics/charts, without needing a live browser:

```powershell
.venv\Scripts\python.exe verify_app.py
```

## Design notes

**Exact enumeration vs. Monte Carlo.** The engine uses exact enumeration only
at the river (all 5 board cards known) with 2 or fewer opponents, where every
possible assignment of opponents' hole cards from the remaining unseen deck
is exhaustively enumerated and evaluated — no sampling error. Every other
case (preflop, flop, turn, or a river with 3+ opponents) falls back to a
30,000-trial Monte Carlo simulation, since exhaustive enumeration would
otherwise grow combinatorially too large to run interactively in pure
Python. At 30,000 trials, simulation error is roughly ±0.5 percentage points
(95% CI) for win probabilities in the typical 20-85% range — precise enough
for an interactive UI, and the equity curve recomputes this independently
per street so each point on the chart carries its own (small) sampling
error.

**v1 scope limitations.** Opponents are always modeled as holding uniformly
random hole cards from the remaining unseen deck — there is no support for
opponent hand ranges. The calculator also does not model side pots, all-ins,
or uneven stack sizes, and only supports a standard 52-card deck (no
short-deck or other deck variants).

## Project structure

```
poker/
├── cards.py      # Card model, notation parsing, Deck (unseen-card pool)
├── evaluator.py  # From-scratch 5/6/7-card best-hand evaluator
└── equity.py     # Exact enumeration + Monte Carlo equity engine, equity curve
app.py            # Streamlit dashboard
verify_app.py     # AppTest-based end-to-end UI smoke test
tests/            # pytest unit tests for evaluator.py and equity.py
```
