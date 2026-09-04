"""Tests for engine.ko_chance - see that module's docstring for the exact
math and the deliberate scope limits (only a move's own static crit
ratio is modeled; same-move-every-turn; full defender HP)."""

import itertools

import pytest

from poke_calc.data.loader import load_dex
from poke_calc.engine.build import build_mon, build_move
from poke_calc.engine.damage import calculate_damage
from poke_calc.engine.ko_chance import CRIT_STAGE_CHANCES, ko_chance, move_crit_chance, moves_summary
from poke_calc.engine.models import FieldState


@pytest.fixture(scope="module")
def dex():
    return load_dex()


class TestMoveCritChance:
    def test_ordinary_move_uses_the_base_rate(self, dex):
        assert move_crit_chance(dex.get_move("Earthquake")) == pytest.approx(1 / 24)

    def test_high_crit_ratio_move_uses_the_boosted_rate(self, dex):
        assert move_crit_chance(dex.get_move("Night Slash")) == pytest.approx(1 / 8)

    def test_guaranteed_crit_move_is_always_a_crit(self, dex):
        assert move_crit_chance(dex.get_move("Storm Throw")) == 1.0

    def test_crit_ratio_stages_match_the_gen_6_plus_table(self):
        assert CRIT_STAGE_CHANCES == (1 / 24, 1 / 8, 1 / 2, 1.0)


def _brute_force_ko_chance(dex, attacker, defender, move_name, field, max_hits):
    """Independent reference implementation - enumerates every possible
    combination of hits directly (O(32^max_hits)) rather than convolving,
    to cross-check ko_chance()'s DP is exactly right, not just plausible.
    Deliberately does NOT reuse ko_chance()'s own _convolve helper."""
    field = field or FieldState()
    attacker_mon = build_mon(dex, **attacker, field=field)
    defender_mon = build_mon(dex, **defender, field=field)
    defender_hp = defender_mon.stats["hp"]

    move_data = dex.get_move(move_name)
    p_crit = move_crit_chance(move_data)
    crit_move = build_move(dex, move_name, is_crit=True)
    noncrit_move = build_move(dex, move_name, is_crit=False)
    crit_rolls = calculate_damage(attacker_mon, defender_mon, crit_move, field, dex, is_critical=True)
    noncrit_rolls = calculate_damage(attacker_mon, defender_mon, noncrit_move, field, dex, is_critical=False)

    outcomes = [(r, p_crit / len(crit_rolls)) for r in crit_rolls]
    outcomes += [(r, (1 - p_crit) / len(noncrit_rolls)) for r in noncrit_rolls]

    result = {}
    for n in range(1, max_hits + 1):
        ko_prob = 0.0
        for combo in itertools.product(outcomes, repeat=n):
            total_damage = sum(dmg for dmg, _ in combo)
            if total_damage >= defender_hp:
                combo_prob = 1.0
                for _, prob in combo:
                    combo_prob *= prob
                ko_prob += combo_prob
        result[n] = ko_prob
    return result


class TestKoChanceAgainstBruteForce:
    def test_matches_brute_force_enumeration_for_a_weak_move(self, dex):
        # A move too weak to OHKO/2HKO reliably, so 3 hits actually
        # exercises interesting probability mass instead of trivially
        # collapsing to 0% or 100% at hit 1.
        attacker = {
            "species": "Garchomp", "nature": "Jolly", "ability": "Rough Skin",
            "sp": {"hp": 0, "atk": 32, "def": 0, "spa": 0, "spd": 0, "spe": 32},
        }
        defender = {
            "species": "Snorlax", "nature": "Impish", "ability": "Thick Fat",
            "sp": {"hp": 32, "atk": 0, "def": 32, "spa": 0, "spd": 0, "spe": 0},
        }
        expected = _brute_force_ko_chance(dex, attacker, defender, "Earthquake", None, max_hits=3)
        actual = ko_chance(dex, attacker, defender, "Earthquake", max_hits=3)
        for hit_count, expected_prob in expected.items():
            assert actual[hit_count] == pytest.approx(expected_prob, abs=1e-9), hit_count

    def test_matches_brute_force_for_a_high_crit_ratio_move(self, dex):
        # Exercises the crit/non-crit blending specifically (Night Slash
        # has a boosted 1/8 crit chance, not the base 1/24).
        attacker = {
            "species": "Weavile", "nature": "Jolly", "ability": "Pressure",
            "sp": {"hp": 0, "atk": 32, "def": 0, "spa": 0, "spd": 0, "spe": 32},
        }
        defender = {
            "species": "Tyranitar", "nature": "Careful", "ability": "Sand Stream",
            "sp": {"hp": 32, "atk": 0, "def": 0, "spa": 0, "spd": 32, "spe": 0},
        }
        expected = _brute_force_ko_chance(dex, attacker, defender, "Night Slash", None, max_hits=2)
        actual = ko_chance(dex, attacker, defender, "Night Slash", max_hits=2)
        for hit_count, expected_prob in expected.items():
            assert actual[hit_count] == pytest.approx(expected_prob, abs=1e-9), hit_count


class TestKoChanceProperties:
    def test_probabilities_are_bounded_and_non_decreasing(self, dex):
        attacker = {
            "species": "Garchomp", "nature": "Jolly", "ability": "Rough Skin",
            "sp": {"hp": 0, "atk": 32, "def": 0, "spa": 0, "spd": 0, "spe": 32},
        }
        defender = {
            "species": "Snorlax", "nature": "Impish", "ability": "Thick Fat",
            "sp": {"hp": 32, "atk": 0, "def": 32, "spa": 0, "spd": 0, "spe": 0},
        }
        result = ko_chance(dex, attacker, defender, "Earthquake", max_hits=4)
        values = [result[k] for k in sorted(result)]
        assert all(0.0 <= v <= 1.0 for v in values)
        assert values == sorted(values)

    def test_guaranteed_ohko_reports_100_percent_at_hit_one_and_stops(self, dex):
        attacker = {
            "species": "Garchomp", "nature": "Adamant", "ability": "Rough Skin",
            "item": "Choice Band", "sp": {"hp": 0, "atk": 32, "def": 0, "spa": 0, "spd": 0, "spe": 32},
        }
        defender = {
            "species": "Alakazam", "nature": "Timid", "ability": "Synchronize",
            "sp": {"hp": 0, "atk": 0, "def": 0, "spa": 32, "spd": 0, "spe": 32},
        }
        result = ko_chance(dex, attacker, defender, "Earthquake", max_hits=4)
        assert result == {1: pytest.approx(1.0)}

    def test_type_immunity_never_reaches_certainty_within_max_hits(self, dex):
        # A Ground move vs a Flying-type is a total-immunity case (0
        # damage every roll, per engine.damage's documented handling) -
        # confirms ko_chance() doesn't spuriously report 100% and that
        # all max_hits keys are kept when it genuinely never reaches ~100%.
        attacker = {
            "species": "Garchomp", "nature": "Jolly", "ability": "Rough Skin",
            "sp": {"hp": 0, "atk": 32, "def": 0, "spa": 0, "spd": 0, "spe": 32},
        }
        defender = {"species": "Skarmory", "nature": "Impish", "ability": "Sturdy", "sp": {}}
        result = ko_chance(dex, attacker, defender, "Earthquake", max_hits=4)
        assert list(result) == [1, 2, 3, 4]
        assert all(p == 0.0 for p in result.values())


class TestMovesSummary:
    def test_empty_move_list_returns_empty(self, dex):
        attacker = {"species": "Garchomp", "nature": "Jolly", "ability": "Rough Skin", "sp": {}}
        defender = {"species": "Tyranitar", "nature": "Careful", "ability": "Sand Stream", "sp": {}}
        assert moves_summary(dex, attacker, defender, [], field=None) == []

    def test_one_row_per_move_in_the_given_order(self, dex):
        attacker = {"species": "Garchomp", "nature": "Jolly", "ability": "Rough Skin", "sp": {}}
        defender = {"species": "Tyranitar", "nature": "Careful", "ability": "Sand Stream", "sp": {}}
        rows = moves_summary(dex, attacker, defender, ["Earthquake", "Dragon Claw", "Poison Jab"], field=None)
        assert [r["Move"] for r in rows] == ["Earthquake", "Dragon Claw", "Poison Jab"]

    def test_ko_columns_match_ko_chance_for_the_same_move(self, dex):
        attacker = {
            "species": "Garchomp", "nature": "Adamant", "ability": "Rough Skin", "item": "Life Orb",
            "sp": {"hp": 0, "atk": 32, "def": 0, "spa": 0, "spd": 0, "spe": 32},
        }
        defender = {
            "species": "Snorlax", "nature": "Impish", "ability": "Thick Fat",
            "sp": {"hp": 32, "atk": 0, "def": 32, "spa": 0, "spd": 0, "spe": 0},
        }
        rows = moves_summary(dex, attacker, defender, ["Earthquake"], field=None)
        row = rows[0]
        expected = ko_chance(dex, attacker, defender, "Earthquake", max_hits=4)
        # ko_chance() stops early once ~100% is reached - moves_summary()
        # fills every later column forward with that same value instead,
        # so compare only the keys ko_chance() actually computed.
        column_by_hits = {1: "OHKO %", 2: "2HKO %", 3: "3HKO %", 4: "4HKO %"}
        for hits, expected_prob in expected.items():
            assert row[column_by_hits[hits]] == pytest.approx(expected_prob)

    def test_damage_column_matches_a_direct_non_crit_calculate_damage_call(self, dex):
        attacker = {
            "species": "Garchomp", "nature": "Jolly", "ability": "Rough Skin",
            "sp": {"hp": 0, "atk": 32, "def": 0, "spa": 0, "spd": 0, "spe": 32},
        }
        defender = {
            "species": "Snorlax", "nature": "Impish", "ability": "Thick Fat",
            "sp": {"hp": 32, "atk": 0, "def": 32, "spa": 0, "spd": 0, "spe": 0},
        }
        field = FieldState()
        rows = moves_summary(dex, attacker, defender, ["Earthquake"], field=field)

        attacker_mon = build_mon(dex, **attacker, field=field)
        defender_mon = build_mon(dex, **defender, field=field)
        move = build_move(dex, "Earthquake", is_crit=False)
        rolls = calculate_damage(attacker_mon, defender_mon, move, field, dex, is_critical=move.is_crit)
        expected_avg_pct = (sum(rolls) / len(rolls)) / defender_mon.stats["hp"]
        assert rows[0]["Avg Dmg %"] == pytest.approx(expected_avg_pct)

    def test_ko_probability_is_filled_forward_past_a_guaranteed_hit_count(self, dex):
        # Garchomp's Earthquake OHKOs an undefensive Alakazam - every
        # later hit-count column should carry the same ~100%, not
        # silently read as 0% just because ko_chance() stopped computing.
        attacker = {
            "species": "Garchomp", "nature": "Adamant", "ability": "Rough Skin", "item": "Life Orb",
            "sp": {"hp": 0, "atk": 32, "def": 0, "spa": 0, "spd": 0, "spe": 32},
        }
        defender = {
            "species": "Alakazam", "nature": "Timid", "ability": "Synchronize",
            "sp": {"hp": 0, "atk": 0, "def": 0, "spa": 32, "spd": 0, "spe": 32},
        }
        rows = moves_summary(dex, attacker, defender, ["Earthquake"], field=None)
        row = rows[0]
        assert row["OHKO %"] == pytest.approx(1.0)
        assert row["2HKO %"] == pytest.approx(1.0)
        assert row["3HKO %"] == pytest.approx(1.0)
        assert row["4HKO %"] == pytest.approx(1.0)
