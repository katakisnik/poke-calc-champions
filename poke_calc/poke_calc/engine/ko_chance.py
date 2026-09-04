"""KO-chance solver: for a given attacker/defender/move, what's the
probability the defender is KO'd within 1, 2, 3, ... hits of that same
move, repeated - the question a "2HKO to 3HKO" range only gestures at.

The math: each hit's damage is one of the engine's existing 16 rolls (the
85-100% random factor, each equally likely - see engine.damage.
calculate_damage). "P(KO within N hits)" is P(sum of N iid draws from that
distribution >= defender HP), computed via discrete convolution - the same
technique as dice-sum probabilities. Because damage only ever accumulates
(rolls are non-negative), that sum-based probability is automatically the
correct CUMULATIVE "dead by hit N or sooner" number - no separate
bookkeeping is needed for "was it already dead after hit k < N": an
earlier crossing of the HP threshold necessarily means every later
(larger) sum also crosses it.

Crit chance: unlike upstream/poke-env, `is_critical` was a pure caller-
supplied bool with no notion of "chance" anywhere in this engine - this
module is what introduces one. `calculate_damage` already internally
OVERRIDES whatever `is_critical` it's given for two ability interactions
(damage.py: forces non-crit for Battle Armor/Shell Armor defenders, forces
a crit for Merciless vs. a poisoned target) - calling it once with
is_critical=True and once with False and blending by crit probability
respects both overrides automatically, no special-casing needed here.

Scope, deliberately limited (same "document the gap" standard as
engine.damage's module docstring):
- Only a move's own STATIC crit ratio is modeled (base rate 1/24, or 1/8
  for "high crit ratio" moves like Night Slash/Stone Edge - see
  data/generate_crit_ratios.py). Focus Energy, Scope Lens/Razor Claw,
  Super Luck/Sniper's stage-boosting effects are NOT modeled - those need
  cross-move battle-log state (was Focus Energy used earlier this battle?)
  this stateless, single-hit calculator doesn't track, same category of
  gap as Aqua Step's dance counter or Alluring Voice's "raised this turn"
  condition.
- Same-move-every-turn is assumed, same as every mainline damage
  calculator's own KO-chance feature - this is not a turn-by-turn battle
  simulator.
- Computed against the defender's full max HP (current_hp_fraction is
  always 1.0 throughout this project - see engine.build.build_mon), not
  some already-damaged HP total.
- Multi-hit moves inherit calculate_damage's existing averaged-base-power
  approximation rather than being enumerated hit-by-hit.
"""

from __future__ import annotations

from typing import Optional

from poke_calc.data.loader import Dex, MoveData
from poke_calc.engine.build import build_mon, build_move
from poke_calc.engine.damage import calculate_damage
from poke_calc.engine.models import FieldState

# Gen 6+ standard crit-stage table: stage 0 (base rate) through stage 3+
# (guaranteed). A move's static crit_ratio of 1/2/3 maps directly to
# stage 0/1/2 here.
CRIT_STAGE_CHANCES: tuple[float, ...] = (1 / 24, 1 / 8, 1 / 2, 1.0)


def move_crit_chance(move: MoveData) -> float:
    """The probability a single use of `move` lands as a critical hit,
    from its own static crit_ratio alone (see this module's docstring for
    what's deliberately NOT factored in - Focus Energy and similar)."""
    if move.will_crit:
        return 1.0
    stage = max(move.crit_ratio - 1, 0)
    return CRIT_STAGE_CHANCES[min(stage, len(CRIT_STAGE_CHANCES) - 1)]


def _convolve(dist_a: dict[int, float], dist_b: dict[int, float]) -> dict[int, float]:
    """The distribution of the SUM of one draw from each of `dist_a` and
    `dist_b` - plain discrete convolution, no external dependency."""
    result: dict[int, float] = {}
    for a_total, a_prob in dist_a.items():
        for b_total, b_prob in dist_b.items():
            total = a_total + b_total
            result[total] = result.get(total, 0.0) + a_prob * b_prob
    return result


def _per_hit_distribution(
    dex: Dex, attacker_mon, defender_mon, move_name: str, field: FieldState,
) -> tuple[dict[int, float], list[int]]:
    """The single-hit damage distribution for `move_name` (crit and
    non-crit blended by move_crit_chance), plus the plain is_crit=False
    roll set on its own - this second value is exactly what the single-
    move UI view's own calculate() displays today (same `is_critical=
    move.is_crit` convention, since build_move's `is_crit=is_crit or
    m.will_crit` already forces it True for guaranteed-crit moves even
    when False is passed here), so any caller wanting a plain damage
    range/average gets a number that can never disagree with that view."""
    move_data = dex.get_move(move_name)
    p_crit = move_crit_chance(move_data)

    # build_move's existing `is_crit=is_crit or m.will_crit` already makes
    # both calls identical for guaranteed-crit moves, so this correctly
    # collapses to a single (crit) outcome for those without special-
    # casing here.
    crit_move = build_move(dex, move_name, is_crit=True)
    noncrit_move = build_move(dex, move_name, is_crit=False)
    crit_rolls = calculate_damage(attacker_mon, defender_mon, crit_move, field, dex, is_critical=True)
    noncrit_rolls = calculate_damage(attacker_mon, defender_mon, noncrit_move, field, dex, is_critical=False)

    per_hit_dist: dict[int, float] = {}
    for roll in crit_rolls:
        per_hit_dist[roll] = per_hit_dist.get(roll, 0.0) + p_crit / len(crit_rolls)
    for roll in noncrit_rolls:
        per_hit_dist[roll] = per_hit_dist.get(roll, 0.0) + (1 - p_crit) / len(noncrit_rolls)
    return per_hit_dist, noncrit_rolls


def _cumulative_ko_probs(per_hit_dist: dict[int, float], defender_hp: int, max_hits: int) -> dict[int, float]:
    result: dict[int, float] = {}
    running_dist = {0: 1.0}
    for hit_count in range(1, max_hits + 1):
        running_dist = _convolve(running_dist, per_hit_dist)
        raw_prob = sum(prob for total, prob in running_dist.items() if total >= defender_hp)
        # Floating-point accumulation across many convolution steps can
        # push this a hair past 1.0 (or below 0.0) - clamp so callers get
        # a mathematically valid probability, not e.g. 100.00000002%.
        result[hit_count] = min(1.0, max(0.0, raw_prob))
        if result[hit_count] >= 0.9999:
            break
    return result


def ko_chance(
    dex: Dex,
    attacker: dict,
    defender: dict,
    move_name: str,
    *,
    field: Optional[FieldState] = None,
    max_hits: int = 4,
) -> dict[int, float]:
    """Cumulative P(defender is KO'd within N hits of `move_name`) for
    N = 1..max_hits (fewer keys if an earlier N already reaches ~100% -
    no point computing further). `attacker`/`defender` are build_mon
    kwarg dicts, same convention as engine.build.calculate()."""
    field = field or FieldState()
    attacker_mon = build_mon(dex, **attacker, field=field)
    defender_mon = build_mon(dex, **defender, field=field)
    per_hit_dist, _ = _per_hit_distribution(dex, attacker_mon, defender_mon, move_name, field)
    return _cumulative_ko_probs(per_hit_dist, defender_mon.stats["hp"], max_hits)


def moves_summary(
    dex: Dex,
    attacker: dict,
    defender: dict,
    move_names: list[str],
    *,
    field: Optional[FieldState] = None,
    max_hits: int = 4,
) -> list[dict]:
    """One row per name in `move_names`: damage % and per-hit-count KO
    chances against the same attacker/defender, sharing the Mon-
    construction cost across the whole batch instead of rebuilding it per
    move. Unlike ko_chance()'s own early-stopping dict, every row always
    carries all `max_hits` KO-chance columns - once a move's KO chance
    hits ~100% at some hit count, every later hit count is trivially also
    ~100% (damage only accumulates), so those are filled forward rather
    than omitted, keeping every row's columns consistent.

    Not currently called from ui/app.py - it backed a "compare all moves"
    table that was pulled after shipping with a real display bug
    (st.column_config's format="%.0f%%" doesn't scale a 0-1 fraction the
    way format="percent" does, so every row showed "0%"/"1%" regardless
    of the real value) pending a UI rethink. Left in place, tested
    (tests/test_ko_chance.py::TestMovesSummary), since the bug was in how
    the UI displayed these numbers, not in this function - ko_chance()
    alone is still the right entry point for a single move in the
    meantime."""
    field = field or FieldState()
    attacker_mon = build_mon(dex, **attacker, field=field)
    defender_mon = build_mon(dex, **defender, field=field)
    defender_hp = defender_mon.stats["hp"]

    rows = []
    for move_name in move_names:
        move_data = dex.get_move(move_name)
        per_hit_dist, displayed_rolls = _per_hit_distribution(dex, attacker_mon, defender_mon, move_name, field)
        raw_ko_probs = _cumulative_ko_probs(per_hit_dist, defender_hp, max_hits)

        last_prob = 0.0
        row = {
            "Move": move_data.name,
            "Type": move_data.type,
            "Category": move_data.category,
            "BP": move_data.base_power,
            "Avg Dmg %": (sum(displayed_rolls) / len(displayed_rolls)) / defender_hp,
        }
        for hit_count in range(1, max_hits + 1):
            if hit_count in raw_ko_probs:
                last_prob = raw_ko_probs[hit_count]
            row[f"{hit_count}HKO %" if hit_count > 1 else "OHKO %"] = last_prob
        rows.append(row)
    return rows
