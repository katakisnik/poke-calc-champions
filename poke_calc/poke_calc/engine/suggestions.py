"""Suggested nature + SP spread, as a sensible starting point per species.

This is a simple, transparent heuristic derived purely from base stats -
NOT a competitive set-building tool. It has no awareness of movepool, role,
team context, or the current metagame (that would need Pokekipe-style
usage data, which this project doesn't pull in). It exists so a fresh
species pick doesn't start at a flat, uninformative "Hardy / 0 SP
everywhere" - not to replace actually building a real set.

Rule: pick whichever of Atk/SpA is higher as the "primary offense". If the
species is reasonably fast (base Speed >= 60), suggest a Speed-boosting
nature (Jolly/Timid) and put SP into primary offense + Speed. Otherwise
suggest a nature that boosts the primary offense directly (Adamant/Modest)
and put SP into primary offense + HP. Either way the unused offensive stat
is the one lowered, and any SP left over from the 66-point budget after
maxing two stats at 32 goes to HP (or the higher defense, for the slow
path).
"""

from __future__ import annotations

from poke_calc.data.loader import STAT_NAMES
from poke_calc.engine.stats import SP_BUDGET, SP_MAX

FAST_THRESHOLD = 60


def suggest_nature_and_sp(base_stats: dict[str, int]) -> tuple[str, dict[str, int]]:
    primary = "atk" if base_stats["atk"] >= base_stats["spa"] else "spa"
    is_fast = base_stats["spe"] >= FAST_THRESHOLD

    if is_fast:
        nature = "Jolly" if primary == "atk" else "Timid"
        second_stat = "spe"
    else:
        nature = "Adamant" if primary == "atk" else "Modest"
        second_stat = "hp" if base_stats["hp"] >= max(base_stats["def"], base_stats["spd"]) else (
            "def" if base_stats["def"] >= base_stats["spd"] else "spd"
        )

    # Two stats at the 32-point cap, and whatever's left of the 66-point
    # budget (always 2, since 66 - 32 - 32 = 2) goes to a third stat -
    # HP, unless HP is already one of the two big investments.
    sp = {primary: SP_MAX, second_stat: SP_MAX}
    third_stat = "hp" if second_stat != "hp" else "def"
    sp[third_stat] = sp.get(third_stat, 0) + (SP_BUDGET - sum(sp.values()))

    for stat in STAT_NAMES:
        sp.setdefault(stat, 0)
    return nature, sp
