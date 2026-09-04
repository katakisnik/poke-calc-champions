"""Builds engine.models objects (Mon, MoveSpec) from Dex records and simple,
UI/test-friendly keyword arguments. This is the intended public entry point
for the damage engine - callers should not construct Mon/MoveSpec by hand.

`sp` spreads use the same 0-32-per-stat convention as the oracle's JSON
harness's `evs` field (oracle/oracle.js) and @smogon/calc's own gen-0 Pokemon
options, so a differential fuzzer can pass the same numbers to both sides
without any unit conversion.
"""

from __future__ import annotations

import math
from typing import Optional

from poke_calc.data.loader import Dex, to_id
from poke_calc.engine.damage import _effective_speed, calculate_damage
from poke_calc.engine.models import BOOSTABLE_STATS, FieldState, Mon, MoveSpec
from poke_calc.engine.stats import calc_all_stats, validate_sp_spread

# Forecast (Castform) changes the holder's actual type to match weather -
# a real forme change in-game, not a battle-log-tracked volatile, so a
# stateless calculator must resolve it at Mon-build time rather than in the
# damage pipeline. There is no equivalent for Cherrim's Flower Gift (it
# changes stats/ability interactions, not typing) so this table only needs
# Castform's three weather formes.
_FORECAST_FORMES = {"Sun": "castformsunny", "Rain": "castformrainy", "Snow": "castformsnowy"}


def build_mon(
    dex: Dex,
    species: str,
    *,
    ability: Optional[str] = None,
    item: Optional[str] = None,
    nature: Optional[str] = None,
    sp: Optional[dict[str, int]] = None,
    boosts: Optional[dict[str, int]] = None,
    status: Optional[str] = None,
    current_hp_fraction: float = 1.0,
    level: int = 50,
    gender: Optional[str] = None,
    allies_fainted: int = 0,
    ally: Optional[Mon] = None,
    field: Optional[FieldState] = None,
) -> Mon:
    species_rec = dex.get_species(species)
    sp_spread = sp or {}
    validate_sp_spread(sp_spread)
    nature_rec = dex.get_nature(nature) if nature else None
    stats = calc_all_stats(species_rec.base_stats, sp_spread, nature_rec)

    ability_id = to_id(ability) if ability else to_id(species_rec.ability)
    item_id = to_id(item) if item else None
    base_species_id = (
        to_id(species_rec.base_species) if species_rec.base_species else species_rec.id
    )

    types = species_rec.types
    if ability_id == "forecast" and species_rec.id == "castform" and field and field.weather in _FORECAST_FORMES:
        types = dex.species[_FORECAST_FORMES[field.weather]].types

    return Mon(
        species=species_rec.id,
        base_species=base_species_id,
        types=types,
        stats=stats,
        weight_kg=species_rec.weight_kg,
        level=level,
        ability=ability_id,
        item=item_id,
        gender=gender,
        status=status,
        current_hp_fraction=current_hp_fraction,
        boosts={**{s: 0 for s in BOOSTABLE_STATS}, **(boosts or {})},
        allies_fainted=allies_fainted,
        ally=ally,
    )


def effective_speed(mon: Mon, field: FieldState) -> int:
    """Current Speed as it actually determines turn order: stage boosts,
    Choice Scarf/Iron Ball, weather-doubling abilities and Surge Surfer
    (all via engine.damage._effective_speed, the same helper the damage
    math itself uses for speed-dependent formulas), plus paralysis's 0.5x -
    which _effective_speed deliberately excludes since it's irrelevant to
    damage, but does determine who moves first."""
    speed = _effective_speed(mon, field)
    if mon.status == "par":
        speed = math.floor(speed * 0.5)
    return int(speed)


def build_move(
    dex: Dex,
    move_name: str,
    *,
    is_crit: bool = False,
    n_hit: Optional[tuple[int, int]] = None,
) -> MoveSpec:
    m = dex.get_move(move_name)
    return MoveSpec(
        id=m.id,
        name=m.name,
        type=m.type,
        category=m.category,
        base_power=m.base_power,
        priority=m.priority,
        target=m.target,
        flags=dict(m.flags),
        has_secondary=m.has_secondary,
        n_hit=n_hit or (m.multihit or (1, 1)),
        # Guaranteed-crit moves (Storm Throw, Frost Breath, Flower Trick,
        # ...) always crit in-game - `is_crit` can force a crit on a move
        # that doesn't normally get one, but can't force one *off* here.
        is_crit=is_crit or m.will_crit,
        ignore_defensive=m.ignore_defensive,
        breaks_protect=m.breaks_protect,
        recoil=m.recoil,
        override_defensive_stat=m.override_defensive_stat,
    )


def calculate(
    dex: Dex,
    attacker: dict,
    defender: dict,
    move_name: str,
    *,
    field: Optional[FieldState] = None,
    is_crit: bool = False,
) -> list[int]:
    """Convenience one-call form: dicts of build_mon kwargs in, 16 damage
    rolls out. `attacker`/`defender` dicts must include `species` plus any
    of build_mon's other keyword arguments."""
    field = field or FieldState()
    attacker_mon = build_mon(dex, **attacker, field=field)
    defender_mon = build_mon(dex, **defender, field=field)
    move = build_move(dex, move_name, is_crit=is_crit)
    return calculate_damage(attacker_mon, defender_mon, move, field, dex, is_critical=move.is_crit)
