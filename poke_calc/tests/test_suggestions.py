import pytest

from poke_calc.data.loader import STAT_NAMES, load_dex
from poke_calc.engine.suggestions import suggest_nature_and_sp
from poke_calc.engine.stats import SP_BUDGET, SP_MAX, validate_sp_spread


class TestInvariants:
    """The heuristic must never produce a spread the SP budget itself
    would reject - this is the property that actually matters, checked
    exhaustively across the real dex rather than a handful of examples."""

    def test_every_species_produces_a_valid_spread(self):
        dex = load_dex()
        for species in dex.species.values():
            nature, sp = suggest_nature_and_sp(species.base_stats)
            validate_sp_spread(sp)  # raises if invalid
            assert nature in dex.natures
            assert sum(sp.values()) == SP_BUDGET
            assert set(sp) == set(STAT_NAMES)
            assert all(0 <= v <= SP_MAX for v in sp.values())


class TestKnownArchetypes:
    def test_fast_physical_attacker_gets_jolly(self):
        # Garchomp-like: high Atk, high Speed.
        nature, sp = suggest_nature_and_sp({"hp": 108, "atk": 130, "def": 95, "spa": 80, "spd": 85, "spe": 102})
        assert nature == "Jolly"
        assert sp["atk"] == SP_MAX
        assert sp["spe"] == SP_MAX
        assert sp["hp"] == SP_BUDGET - 2 * SP_MAX

    def test_fast_special_attacker_gets_timid(self):
        nature, sp = suggest_nature_and_sp({"hp": 60, "atk": 55, "def": 50, "spa": 125, "spd": 90, "spe": 104})
        assert nature == "Timid"
        assert sp["spa"] == SP_MAX
        assert sp["spe"] == SP_MAX

    def test_slow_physical_attacker_gets_adamant(self):
        # Snorlax-like: high Atk, low Speed, HP is its best "defense".
        nature, sp = suggest_nature_and_sp({"hp": 160, "atk": 110, "def": 65, "spa": 65, "spd": 110, "spe": 30})
        assert nature == "Adamant"
        assert sp["atk"] == SP_MAX
        assert sp["hp"] == SP_MAX  # HP >= max(def, spd) here, so it's the second big investment

    def test_slow_bulky_attacker_invests_in_its_best_defense_when_hp_is_not_it(self):
        nature, sp = suggest_nature_and_sp({"hp": 65, "atk": 100, "def": 90, "spa": 60, "spd": 140, "spe": 40})
        assert nature == "Adamant"
        assert sp["atk"] == SP_MAX
        assert sp["spd"] == SP_MAX  # spd > def and > hp here
        assert sp["hp"] == SP_BUDGET - 2 * SP_MAX  # hp wasn't the 2nd investment, so it gets the leftover


class TestTieBreaks:
    def test_equal_atk_and_spa_prefers_physical(self):
        nature, sp = suggest_nature_and_sp({"hp": 80, "atk": 100, "def": 80, "spa": 100, "spd": 80, "spe": 80})
        assert nature == "Jolly"
        assert sp["atk"] == SP_MAX

    def test_speed_exactly_at_threshold_counts_as_fast(self):
        nature, _ = suggest_nature_and_sp({"hp": 80, "atk": 100, "def": 80, "spa": 60, "spd": 80, "spe": 60})
        assert nature == "Jolly"

    def test_speed_just_below_threshold_counts_as_slow(self):
        nature, _ = suggest_nature_and_sp({"hp": 80, "atk": 100, "def": 80, "spa": 60, "spd": 80, "spe": 59})
        assert nature == "Adamant"
