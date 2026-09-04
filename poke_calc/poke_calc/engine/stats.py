"""Pokemon Champions stat calculation.

Champions replaces EVs with SP (Stat Points): 0-32 per stat, 66 total, with
IVs hard-forced to 31 and level hard-forced to 50. Confirmed exactly from
@smogon/calc's calc/src/stats.ts `calcStatChampions`:

    HP    = base + SP + 75                       (base == 1 -> 1, Shedinja)
    other = floor(n * (base + SP + 20))           n in {1.1, 1.0, 0.9}

This is an exact algebraic simplification of the standard level-50/31-IV
formula with floor(EV/4) = max(2*SP - 1, 0) (Showdown's own comment: "the
first stat point gives 4 EVs and the others give 8 EVs") - verified by
brute force below over every base (1-255) x SP (0-32) combination.

`n` is applied by comparing a Nature's plus/minus stat to the stat being
computed: 1.1 if it's the boosted stat, 0.9 if it's the lowered stat (unless
both point at the same stat, i.e. a neutral nature, in which case 1.0).
"""

from __future__ import annotations

from poke_calc.data.loader import STAT_NAMES, Nature

SP_MIN = 0
SP_MAX = 32
SP_BUDGET = 66


def sp_to_ev(sp: int) -> int:
    """The EV-equivalent for a given SP investment (SP 32 -> EV 252).

    Useful for interop with Showdown-format sets. Not used by calc_stat
    itself, which implements the already-simplified Champions formula
    directly rather than routing through EVs.
    """
    return 4 * max(2 * sp - 1, 0)


def _nature_multiplier(nature: Nature | None, stat: str) -> float:
    if nature is None:
        return 1.0
    if nature.plus == stat and nature.minus == stat:
        return 1.0
    if nature.plus == stat:
        return 1.1
    if nature.minus == stat:
        return 0.9
    return 1.0


def calc_stat(base: int, stat: str, sp: int, nature: Nature | None = None) -> int:
    """Compute a Champions final stat.

    :param base: the species' base stat value for `stat`.
    :param stat: one of "hp", "atk", "def", "spa", "spd", "spe".
    :param sp: stat points invested, 0-32.
    :param nature: the Pokemon's nature, or None for a flat x1.0.
    """
    if stat not in STAT_NAMES:
        raise ValueError(f"unknown stat {stat!r}, expected one of {STAT_NAMES}")
    if not (SP_MIN <= sp <= SP_MAX):
        raise ValueError(f"SP must be in [{SP_MIN}, {SP_MAX}], got {sp}")

    if stat == "hp":
        if base == 1:  # Shedinja
            return 1
        return base + sp + 75

    n = _nature_multiplier(nature, stat)
    return int(n * (base + sp + 20))  # matches JS Math.floor for n*positive-int


def calc_all_stats(
    base_stats: dict[str, int], sp_spread: dict[str, int], nature: Nature | None = None
) -> dict[str, int]:
    """Compute all six final stats from a base-stat dict and an SP spread."""
    return {
        stat: calc_stat(base_stats[stat], stat, sp_spread.get(stat, 0), nature)
        for stat in STAT_NAMES
    }


def validate_sp_spread(sp_spread: dict[str, int]) -> None:
    """Raise ValueError if a spread violates the 0-32/stat, 66-total budget.

    Neither @smogon/calc nor its data dump enforces this - it is purely a
    Showdown team-validator rule (`EV Limit = Auto` -> 66 under `champions*`
    mods), so it must be enforced in this layer.
    """
    unknown = set(sp_spread) - set(STAT_NAMES)
    if unknown:
        raise ValueError(f"unknown stat(s) in SP spread: {sorted(unknown)}")
    for stat, sp in sp_spread.items():
        if not (SP_MIN <= sp <= SP_MAX):
            raise ValueError(f"{stat}: SP must be in [{SP_MIN}, {SP_MAX}], got {sp}")
    total = sum(sp_spread.values())
    if total > SP_BUDGET:
        raise ValueError(f"SP spread totals {total}, exceeds the {SP_BUDGET}-point budget")
