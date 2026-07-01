from poker.advice import suggest_bet


def test_strong_value_tier():
    a = suggest_bet(90.0, pot_size=10.0, loose_opponents=False)
    assert a.tier == "Strong value"
    assert a.action == "bet"
    assert a.pot_pct_low == 75.0 and a.pot_pct_high == 100.0
    assert 7.0 <= a.suggested_amount <= 10.0


def test_good_value_tier():
    a = suggest_bet(60.0, pot_size=4.0, loose_opponents=False)
    assert a.tier == "Good value"
    assert a.action == "bet"
    assert 1.5 <= a.suggested_amount <= 3.0


def test_marginal_drawing_tier():
    a = suggest_bet(45.0, pot_size=3.0, loose_opponents=False)
    assert a.tier == "Marginal / drawing"
    assert a.action == "bet"
    assert 1.0 <= a.suggested_amount <= 2.5


def test_weak_air_tier_recommends_check():
    a = suggest_bet(20.0, pot_size=5.0, loose_opponents=False)
    assert a.tier == "Weak / air"
    assert a.action == "check"
    assert a.suggested_amount is None


def test_tier_boundaries_are_inclusive_on_the_low_end():
    assert suggest_bet(75.0, 10.0).tier == "Strong value"
    assert suggest_bet(74.9, 10.0).tier == "Good value"
    assert suggest_bet(55.0, 10.0).tier == "Good value"
    assert suggest_bet(54.9, 10.0).tier == "Marginal / drawing"
    assert suggest_bet(40.0, 10.0).tier == "Marginal / drawing"
    assert suggest_bet(39.9, 10.0).tier == "Weak / air"


def test_loose_opponents_bumps_value_bet_sizing_up():
    tight = suggest_bet(90.0, pot_size=10.0, loose_opponents=False)
    loose = suggest_bet(90.0, pot_size=10.0, loose_opponents=True)
    assert loose.pot_pct_low >= tight.pot_pct_low
    assert loose.pot_pct_high >= tight.pot_pct_high
    assert loose.suggested_amount >= tight.suggested_amount


def test_loose_opponents_does_not_change_check_action():
    a = suggest_bet(10.0, pot_size=5.0, loose_opponents=True)
    assert a.action == "check"
    assert a.suggested_amount is None


def test_bet_sizing_never_recommends_a_small_probe_bet():
    # Never bet below 50% pot with a real hand, and check tiers suggest no bet at all.
    for equity in (100.0, 80.0, 60.0, 45.0):
        a = suggest_bet(equity, pot_size=10.0, loose_opponents=False)
        assert a.pot_pct_low >= 50.0


def test_suggested_amount_rounds_to_chip_increment():
    a = suggest_bet(90.0, pot_size=7.0, loose_opponents=False, chip_increment=0.5)
    doubled = a.suggested_amount * 2
    assert abs(doubled - round(doubled)) < 1e-9


def test_negative_pot_size_raises():
    import pytest

    with pytest.raises(ValueError):
        suggest_bet(50.0, pot_size=-1.0)
