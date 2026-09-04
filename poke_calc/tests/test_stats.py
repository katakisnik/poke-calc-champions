"""Property tests for the Champions stat formula.

The central claim (poke_calc/engine/stats.py's calc_stat) is that Champions' simplified
formula is an exact algebraic identity with the standard level-50/31-IV
formula when floor(EV/4) = max(2*SP - 1, 0). This module proves that identity
holds for EVERY base stat (1-255) x every SP value (0-32) x every nature
relationship, by computing both formulas independently and asserting they
never disagree - not just spot-checking a handful of values.
"""

import math

import pytest

from poke_calc.data.loader import STAT_NAMES, Nature, load_dex
from poke_calc.engine.stats import (
    SP_BUDGET,
    SP_MAX,
    SP_MIN,
    calc_all_stats,
    calc_stat,
    sp_to_ev,
    validate_sp_spread,
)

ALL_BASES = range(1, 256)
NON_SHEDINJA_BASES = range(2, 256)  # base == 1 is Shedinja's intentional HP=1 carve-out
ALL_SP = range(SP_MIN, SP_MAX + 1)
LEVEL = 50
IV = 31


def _legacy_hp(base: int, iv: int, ev: int, level: int) -> int:
    """The standard (non-Champions) Gen 3+ HP formula."""
    return math.floor((2 * base + iv + math.floor(ev / 4)) * level / 100) + level + 10


def _legacy_other(base: int, iv: int, ev: int, level: int, nature_mult: float) -> int:
    """The standard (non-Champions) Gen 3+ non-HP stat formula."""
    stat = math.floor((2 * base + iv + math.floor(ev / 4)) * level / 100) + 5
    return math.floor(stat * nature_mult)


class TestHPIdentity:
    def test_matches_legacy_formula_for_every_base_and_sp(self):
        mismatches = []
        for base in NON_SHEDINJA_BASES:
            for sp in ALL_SP:
                ev = sp_to_ev(sp)
                expected = _legacy_hp(base, IV, ev, LEVEL)
                actual = calc_stat(base, "hp", sp)
                if expected != actual:
                    mismatches.append((base, sp, expected, actual))
        assert not mismatches, f"{len(mismatches)} HP mismatches, e.g. {mismatches[:5]}"

    def test_shedinja_is_always_one_hp(self):
        for sp in ALL_SP:
            assert calc_stat(1, "hp", sp) == 1

    def test_sp_zero_edge_case(self):
        # floor(0/4) = 0 vs Champions' max(2*0-1, 0) = 0 -- must agree even
        # though the algebra technically only proves equality for sp >= 1.
        for base in NON_SHEDINJA_BASES:
            assert calc_stat(base, "hp", 0) == _legacy_hp(base, IV, 0, LEVEL)


class TestOtherStatIdentity:
    @pytest.mark.parametrize("stat", ["atk", "def", "spa", "spd", "spe"])
    @pytest.mark.parametrize("nature_mult", [1.1, 0.9, 1.0])
    def test_matches_legacy_formula(self, stat, nature_mult):
        # Build a nature whose plus/minus actually targets `stat` for this case.
        if nature_mult == 1.1:
            nat = Nature("Plus", plus=stat, minus="hp")
        elif nature_mult == 0.9:
            nat = Nature("Minus", plus="hp", minus=stat)
        else:
            nat = Nature("Neutral", plus=stat, minus=stat)

        mismatches = []
        for base in ALL_BASES:
            for sp in ALL_SP:
                ev = sp_to_ev(sp)
                expected = _legacy_other(base, IV, ev, LEVEL, nature_mult)
                actual = calc_stat(base, stat, sp, nat)
                if expected != actual:
                    mismatches.append((base, sp, expected, actual))
        assert not mismatches, (
            f"{stat} x{nature_mult}: {len(mismatches)} mismatches, e.g. {mismatches[:5]}"
        )

    def test_no_nature_is_neutral(self):
        for base in ALL_BASES:
            for sp in (0, 16, 32):
                assert calc_stat(base, "atk", sp, None) == calc_stat(
                    base, "atk", sp, Nature("Hardy", plus="atk", minus="atk")
                )


class TestKnownValues:
    """Spot-checks against values computed by hand from the confirmed formula."""

    def test_max_investment_matches_252_ev_equivalent(self):
        assert sp_to_ev(32) == 252

    def test_zero_investment(self):
        assert sp_to_ev(0) == 0

    def test_one_point_is_four_ev(self):
        assert sp_to_ev(1) == 4

    def test_meganium_mega_spa_32sp_modest(self):
        # Cross-checked against the live oracle in this session:
        # Meganium-Mega, 32 SpA, Modest -> spa: 214.
        nat = Nature("Modest", plus="spa", minus="atk")
        assert calc_stat(143, "spa", 32, nat) == 214

    def test_tyranitar_hp_32sp(self):
        # Cross-checked against the live oracle: 32 HP SP -> hp: 207.
        assert calc_stat(100, "hp", 32) == 207

    def test_garchomp_mega_asymmetric_spread_matches_live_oracle(self):
        # Cross-checked against the live oracle in this session (16 Atk /
        # 24 Spe Jolly Garchomp-Mega): all six stats, not just the invested
        # ones, since nature affects a stat with zero investment too.
        dex = load_dex()
        chomp = dex.get_species("garchomp-mega")
        jolly = dex.get_nature("jolly")
        stats = calc_all_stats(chomp.base_stats, {"atk": 16, "spe": 24}, jolly)
        assert stats == {"hp": 183, "atk": 206, "def": 135, "spa": 126, "spd": 115, "spe": 149}


class TestSpreadHelpers:
    def test_calc_all_stats(self):
        dex = load_dex()
        meg = dex.get_species("meganium-mega")
        nat = dex.get_nature("modest")
        stats = calc_all_stats(meg.base_stats, {"spa": 32, "spe": 32}, nat)
        assert stats == {"hp": 155, "atk": 100, "def": 135, "spa": 214, "spd": 135, "spe": 132}

    def test_missing_stats_in_spread_default_to_zero_sp(self):
        stats = calc_all_stats({s: 100 for s in STAT_NAMES}, {})
        assert stats["atk"] == calc_stat(100, "atk", 0)


class TestValidateSpSpread:
    def test_valid_spread_passes(self):
        validate_sp_spread({"atk": 32, "spe": 32, "hp": 2})

    def test_over_budget_rejected(self):
        with pytest.raises(ValueError, match="66-point budget"):
            validate_sp_spread({"atk": 32, "spe": 32, "hp": 3})

    def test_over_per_stat_cap_rejected(self):
        with pytest.raises(ValueError, match=r"\[0, 32\]"):
            validate_sp_spread({"atk": 33})

    def test_negative_rejected(self):
        with pytest.raises(ValueError, match=r"\[0, 32\]"):
            validate_sp_spread({"atk": -1})

    def test_unknown_stat_rejected(self):
        with pytest.raises(ValueError, match="unknown stat"):
            validate_sp_spread({"attack": 10})

    def test_exactly_at_budget_passes(self):
        validate_sp_spread({"atk": 32, "spe": 32, "hp": 2})  # 66 exactly

    def test_all_stats_at_max_exceeds_budget(self):
        with pytest.raises(ValueError, match="66-point budget"):
            validate_sp_spread({s: 32 for s in STAT_NAMES})  # 192, way over


class TestInputValidation:
    def test_unknown_stat_name_rejected(self):
        with pytest.raises(ValueError, match="unknown stat"):
            calc_stat(100, "attack", 0)

    def test_sp_out_of_range_rejected(self):
        with pytest.raises(ValueError, match=r"\[0, 32\]"):
            calc_stat(100, "atk", 33)
        with pytest.raises(ValueError, match=r"\[0, 32\]"):
            calc_stat(100, "atk", -1)
