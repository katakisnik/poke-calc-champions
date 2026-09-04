"""Pokemon Champions damage calculator.

Ported from poke-env's damage_calc_gen9.py (MIT license, see NOTICE), which
itself follows https://github.com/smogon/damage-calc/.../mechanics/gen789.ts.
Adapted in two ways:

1. Decoupled from poke-env: takes plain `engine.models` dataclasses instead
   of a poke-env Battle/Pokemon/Move, so this package has no runtime
   dependency on poke-env at all.
2. Layered with the confirmed Champions deltas (see the plan's "Champions
   mechanics deltas" checklist, sourced from reading
   smogon/pokemon-showdown's data/mods/champions/*.ts and
   smogon/damage-calc's calc/src/mechanics/champions.ts directly this
   session). Every deviation from the vendored gen789 logic below is
   commented with what changed and why; a `# JUDGMENT CALL:` comment marks
   a handful of genuinely ambiguous single-ability edge cases where the
   research didn't give an unambiguous answer - these are exactly the kind
   of thing Phase 3's differential fuzzing against the oracle should catch
   if the call was wrong.

Known simplifications inherited from upstream (documented there, still true
here): multi-hit moves use averaged base power rather than enumerating each
hit; Shell Side Arm, Fling, item-paired Knock Off, and Metronome (the item)
are approximated or unsupported. Champions removes Terastallization,
Dynamax, and Z-Moves entirely, which drops several of upstream's own
gen9-only special cases for free.

Parental Bond is NOT modelled (confirmed via fuzzing: the oracle returns a
[main_hit, child_hit] nested pair; this engine returns only the main hit,
flat). Upstream dismissed this as "not legal in gen9", but Parental Bond IS
a real, assignable ability in the Champions dex (confirmed present in the
200-ability pool) - so unlike upstream's assumption, this is a live gap in
Champions specifically, not a dead one. A caller who cares about the second
hit must add it manually (child hit uses 0.25x of the main hit's base
damage, per @smogon/calc's Parental Bond (Child) modelling).

Two further gaps found by fuzzing and deliberately left unfixed, because
both need turn-by-turn battle-log state a stateless single-hit calculator
fundamentally doesn't have (and, per direct testing, the oracle itself
doesn't always get right either without that state - see the Lash Out fix
above for the same category of issue resolved the other way):
- Aqua Step's base power scales with a persistent "how many times has the
  user danced this battle" counter (up to 5 stacks) - not modelled; it
  always uses the base (0-stack) power here.
- Alluring Voice doubles power if the TARGET's stats were raised earlier
  in the SAME turn - not modelled; confirmed (via fuzzing) that the oracle
  sometimes applies this based on the target's current boosts, which is
  itself just a heuristic for "raised this turn", so getting an exact
  match would mean reverse-engineering that heuristic rather than
  modelling the real mechanic. Always computed here as if not doubled.

Additional Champions-only simplifications (new to this port, not upstream's):
Bolt Beak/Fishious Rend/Wake-Up Slap/Psyblade/Crush Grip/Wring Out/Brine/
Collision Course/Electro Drift lose their conditional base-power handlers in
Champions (confirmed absent from champions.ts's own base-power switch) and
so fall back to their flat dex base power - correct per the source, but
worth knowing if a number looks lower than mainline-game intuition expects.
Judgment/Multi-Attack/Natural Gift/Nature Power/Ivy Cudgel/Ogerpon
typing/Ivy Cudgel/Sky Drop/Synchronoise/Ground-immunity-bypassing Thousand
Arrows/Ogerpon mask handling are dropped outright as Champions-irrelevant
(their items/formes are banned) or too niche to justify the risk of a
half-implemented special case.
"""

from __future__ import annotations

import dataclasses
import math
from typing import Optional

from poke_calc.data.loader import Dex
from poke_calc.engine.champions_data import (
    ATTACKER_IGNORES_ABILITY,
    BERRY_RESISTS,
    BOOST_MULTIPLIERS,
    DEFENDER_ABILITY_IGNORED,
    ITEM_BOOST_TYPES,
    MOVE_IGNORES_ABILITY,
)
from poke_calc.engine.models import FieldState, Mon, MoveSpec, is_grounded


_WEATHER_SPEED_ABILITIES = {
    "swiftswim": "Rain", "chlorophyll": "Sun", "sandrush": "Sand", "slushrush": "Snow",
}


def _effective_speed(mon: Mon, field: FieldState) -> float:
    """Speed as used for speed-DEPENDENT base-power formulas (Electro
    Ball, Gyro Ball) and turn-order comparisons (Payback, Analytic, Bolt
    Beak/Fishious Rend's old handler) - CURRENT (stage-boosted) Speed, not
    raw, confirmed via fuzzing (mainline mechanic: "current Speed stats,
    including stage modifiers"). Choice Scarf's 1.5x and Iron Ball's 0.5x
    apply on top; a Pokemon can only hold one item, so these never stack
    on the same mon. Weather-doubling abilities (Swift Swim etc, confirmed
    missing via fuzzing) and Surge Surfer (Electric Terrain) also apply -
    `field.weather` is expected to already be nullified by Cloud Nine/Air
    Lock by the time this is called (see calculate_damage), so those
    abilities correctly stop doubling under a nullified weather for free."""
    speed = math.floor(mon.stats["spe"] * BOOST_MULTIPLIERS[mon.boosts.get("spe", 0)])
    if field.weather is not None and _WEATHER_SPEED_ABILITIES.get(mon.ability) == field.weather:
        speed *= 2
    elif mon.has_ability("surgesurfer") and field.terrain == "Electric":
        speed *= 2
    if mon.has_item("choicescarf"):
        speed *= 1.5
    elif mon.has_item("ironball"):
        speed *= 0.5
    return speed


def calculate_damage(
    attacker: Mon,
    defender: Mon,
    move: MoveSpec,
    field: FieldState,
    dex: Dex,
    is_critical: bool = False,
) -> list[int]:
    """Return all 16 damage rolls (the 85-100% random factor) for a single
    hit of `move`. rolls[0] is the min roll, rolls[-1] the max - upstream's
    calculate_damage only computed these two; this port computes all 16
    since Phase 6's KO-chance/solver work needs the full distribution, not
    just the extremes, and it costs nothing extra to compute here.

    Stats on `attacker`/`defender` must be RAW (unboosted) final stats -
    see engine.models.Mon and engine.stats.calc_stat.
    """
    if field.weather is not None and (
        attacker.has_ability("cloudnine", "airlock") or defender.has_ability("cloudnine", "airlock")
    ):
        # Air Lock/Cloud Nine on EITHER side nullifies weather's effects
        # entirely (confirmed retained in champions.ts's prologue: "Air
        # Lock/Cloud Nine clears field.weather") - confirmed missing via
        # fuzzing (it was silently boosting Sun/Fire and Rain/Water moves,
        # and weather-doubling Speed abilities, when it shouldn't have).
        # Reassigning the local `field` here means every downstream use
        # (base power, base damage, effective speed) sees it nullified.
        field = dataclasses.replace(field, weather=None)

    if move.id in ("meteorbeam", "electroshot"):
        # Meteor Beam/Electro Shot raise the user's SpA by 1 stage (-1 if
        # Contrary) BEFORE dealing damage, in the same move use - confirmed
        # in champions.ts, which also drops SV's Simple-doubles-it clause.
        # A stateless calculator has no "the boost already happened this
        # turn" battle log to read from, so this must be applied here
        # rather than expected as caller-supplied input; done as a local
        # copy so the original Mon object passed in isn't mutated.
        delta = -1 if attacker.has_ability("contrary") else 1
        new_spa = max(-6, min(6, attacker.boosts.get("spa", 0) + delta))
        attacker = dataclasses.replace(attacker, boosts={**attacker.boosts, "spa": new_spa})

    move_category = move.category

    if move_category == "Status":
        # Champions: "Status early return: move.category === 'Status'"
        # only - SV's Nature Power exception is gone (Nature Power's
        # dynamic-terrain-power table is one of the removed handlers).
        return [0] * 16

    # Champions removes Punching Glove entirely (confirmed: both its 4506 BP
    # mod and its "removes contact" clause are gone), so unlike upstream
    # there is no flags-copying needed here - move.flags is used as-is.
    flags = move.flags

    move_breaks_protect = move.breaks_protect or (
        attacker.has_ability("unseenfist") and flags.get("contact", 0) == 1
    )
    # Champions' Piercing Drill (Excadrill-Mega) is a Champions-exclusive
    # Unseen Fist clone - contact moves break Protect, at 1/4 damage
    # (applied in calculate_final_mods via `protect_pierce`).
    protect_pierce = False
    if (
        field.defender_side.is_protected
        and attacker.has_ability("unseenfist", "piercingdrill")
        and flags.get("contact", 0) == 1
    ):
        protect_pierce = True
        move_breaks_protect = True

    if field.defender_side.is_protected and not move_breaks_protect:
        return [0] * 16

    if move.id == "painsplit":
        attacker_hp = math.floor(attacker.stats["hp"] * attacker.current_hp_fraction)
        defender_hp = math.floor(defender.stats["hp"] * defender.current_hp_fraction)
        damage = max(0, defender_hp - math.floor((attacker_hp + defender_hp) / 2))
        return [damage] * 16

    defender_ability = defender.ability
    attacker_ability = attacker.ability
    if move.id in MOVE_IGNORES_ABILITY or (
        attacker.ability in ATTACKER_IGNORES_ABILITY
        and defender_ability not in DEFENDER_ABILITY_IGNORED
    ):
        defender_ability = ""

    # Champions removes Neutralizing Gas from the mechanics engine entirely
    # (confirmed: champions.ts has no ignoresNeutralizingGas handling at
    # all), so unlike upstream there is no ability-suppression check here.

    if defender_ability in ("battlearmor", "shellarmor"):
        is_critical = False
    elif attacker_ability == "merciless" and defender.has_status("psn", "tox"):
        is_critical = True

    defender_weight = defender.weight_kg
    if defender_ability == "lightmetal":
        defender_weight *= 0.5
    elif defender_ability == "heavymetal":
        defender_weight *= 2
    # Champions has no Float Stone (removed item).

    move_type: Optional[str] = move.type
    move_target = move.target
    if move.id == "weatherball":
        # Champions has no Utility Umbrella (removed item) and no Harsh
        # Sunshine/Heavy Rain distinction (weather is just Sun/Rain/Sand/
        # Snow). Mega Sol (Meganium-Mega) acts as permanent Sun for its
        # own moves - confirmed in champions.ts's Weather Ball typing.
        if field.weather == "Sun" or attacker.has_ability("megasol"):
            move_type = "Fire"
        elif field.weather == "Rain":
            move_type = "Water"
        elif field.weather == "Sand":
            move_type = "Rock"
        elif field.weather == "Snow":
            move_type = "Ice"
        else:
            move_type = "Normal"
    elif move.id == "terrainpulse" and is_grounded(attacker, field):
        if field.terrain == "Electric":
            move_type = "Electric"
        elif field.terrain == "Grassy":
            move_type = "Grass"
        elif field.terrain == "Misty":
            move_type = "Fairy"
        elif field.terrain == "Psychic":
            move_type = "Psychic"
        else:
            move_type = "Normal"
    elif move.id == "aurawheel":
        if attacker.species == "morpeko":
            move_type = "Electric"
        elif attacker.species == "morpekohangry":
            move_type = "Dark"
    elif move.id == "ragingbull":
        # Champions keeps Raging Bull's type resolution for the Paldean
        # Tauros formes (confirmed retained in champions.ts).
        if attacker.species == "taurospaldeacombat":
            move_type = "Fighting"
        elif attacker.species == "taurospaldeablaze":
            move_type = "Fire"
        elif attacker.species == "taurospaldeaaqua":
            move_type = "Water"
        flags = {**flags, "ignorescreens": 1}
    elif move.id in ("brickbreak", "psychicfangs"):
        flags = {**flags, "ignorescreens": 1}
    elif move.id == "expandingforce" and field.terrain == "Psychic":
        move_target = "allAdjacentFoes"

    has_ate_ability_type_change = False
    # Champions' noTypeChange list shrinks to just these three (confirmed:
    # Judgment/Multi-Attack/Natural Gift/Revelation Dance drop out because
    # their dynamic-type handlers are removed - they just use a static
    # type now, so there's nothing left to gate).
    no_type_change = move.id in {"weatherball", "terrainpulse", "struggle"}

    if not no_type_change:
        # Champions' -ate chain: Aerilate -> Dragonize -> Liquid Voice ->
        # Pixilate -> Refrigerate. Galvanize and Normalize are gone
        # (confirmed removed from the Champions ability pool's -ate set).
        # Dragonize (Feraligatr-Mega, Champions-exclusive) is a Normal ->
        # Dragon "-ate" clone and gets the same 1.2x bp_mods bonus as the
        # others via has_ate_ability_type_change below.
        if attacker_ability == "aerilate" and move_type == "Normal":
            move_type = "Flying"
            has_ate_ability_type_change = True
        elif attacker_ability == "dragonize" and move_type == "Normal":
            move_type = "Dragon"
            has_ate_ability_type_change = True
        elif attacker_ability == "liquidvoice" and flags.get("sound", 0) == 1:
            move_type = "Water"
        elif attacker_ability == "pixilate" and move_type == "Normal":
            move_type = "Fairy"
            has_ate_ability_type_change = True
        elif attacker_ability == "refrigerate" and move_type == "Normal":
            move_type = "Ice"
            has_ate_ability_type_change = True

    move_priority = move.priority
    if attacker_ability == "galewings" and move_type == "Flying" and attacker.current_hp_fraction == 1.0:
        move_priority = 1

    # Champions hard-codes isRingTarget=false (Ring Target is a removed
    # item) and narrows isGhostRevealed to Scrappy only (Mind's Eye and
    # Foresight are dropped - confirmed).
    first_type_effectiveness = get_move_effectiveness(
        dex, move, move_type or move.type, defender.type_1,
        attacker_ability == "scrappy", field.is_gravity, False,
    )
    second_type_effectiveness = (
        1.0
        if defender.type_2 is None
        else get_move_effectiveness(
            dex, move, move_type or move.type, defender.type_2,
            attacker_ability == "scrappy", field.is_gravity, False,
        )
    )
    type_effectiveness = first_type_effectiveness * second_type_effectiveness

    if type_effectiveness == 0 and move_type == "Ground" and defender.has_item("ironball"):
        type_effectiveness = 1.0

    if type_effectiveness == 0:
        return [0] * 16

    if move.id == "dreameater" and defender.status != "slp":
        # Champions drops the Comatose exception (confirmed: "Hex/Infernal
        # Parade | Comatose" interactions removed) - sleep only.
        return [0] * 16
    elif move.id == "steelroller" and field.terrain is None:
        return [0] * 16
    elif move.id == "poltergeist" and not defender.item:
        return [0] * 16

    if defender_ability == "wonderguard" and type_effectiveness <= 1:
        return [0] * 16
    elif move_type == "Grass" and defender_ability == "sapsipper":
        return [0] * 16
    elif move_type == "Fire" and defender_ability == "flashfire":
        return [0] * 16
    elif move_type == "Water" and defender_ability in ("dryskin", "stormdrain", "waterabsorb"):
        return [0] * 16
    elif move_type == "Electric" and defender_ability in ("lightningrod", "motordrive", "voltabsorb"):
        return [0] * 16
    elif (
        move_type == "Ground"
        and not field.is_gravity
        and not defender.has_item("ironball")
        and defender.has_ability("levitate", "eelevate")
    ):
        # Champions drops the Thousand Arrows exception (confirmed: "&&
        # !field.isGravity only" - the move no longer bypasses this).
        return [0] * 16
    elif flags.get("bullet", 0) == 1 and defender_ability == "bulletproof":
        return [0] * 16
    elif flags.get("sound", 0) == 1 and move.id != "clangoroussoul" and defender_ability == "soundproof":
        return [0] * 16
    # JUDGMENT CALL: the research confirmed Queenly Majesty/Armor Tail's
    # priority-move immunity is retained (step 23's "Ability immunities"
    # list), but didn't unambiguously confirm Dazzling specifically stays
    # too (it's functionally identical, just omitted from that one quoted
    # list) - kept here since removing it risks breaking a real Pokemon's
    # legal ability more than an unlikely false-negative. Flagged for
    # Phase 3 fuzzing to verify against the oracle.
    elif move.priority > 0 and defender_ability in ("queenlymajesty", "dazzling", "armortail"):
        return [0] * 16
    elif move_type == "Ground" and defender_ability == "eartheater":
        return [0] * 16
    # JUDGMENT CALL: Wind Rider's wind-move immunity isn't confirmed either
    # way for Champions (only its stat-drop-immunity final-mod use was
    # confirmed removed) - dropped here since Wind Rider isn't confirmed
    # present in the Champions ability pool at all. Revisit if fuzzing
    # surfaces a mismatch on a wind move.
    elif (
        move_priority > 0
        and field.terrain == "Psychic"
        and is_grounded(defender, field)
    ):
        return [0] * 16

    if move.id in ("seismictoss", "nightshade"):
        return [attacker.level] * 16
    elif move.id == "dragonrage":
        return [40] * 16
    elif move.id == "sonicboom":
        return [20] * 16

    if move.id == "finalgambit":
        damage = math.floor(attacker.stats["hp"] * attacker.current_hp_fraction)
        return [damage] * 16

    base_power = calculate_base_power(attacker, defender, move, field, dex, has_ate_ability_type_change, move_type)

    if move.n_hit != (1, 1):
        base_power = base_power * ((move.n_hit[0] + move.n_hit[1]) / 2)

    if base_power == 0:
        return [0] * 16

    attack = calculate_attack(attacker, defender, move, field, move_type, is_critical)
    defense = calculate_defense(attacker, defender, move, field, is_critical)

    base_damage = calculate_base_damage(
        attacker, defender, base_power, attack, defense, move, move_type, move_target, field, is_critical
    )

    pre_stab_mod = get_stab_mod(attacker, move, move_type)

    apply_burn = (
        attacker.status == "brn"
        and move_category == "Physical"
        and attacker_ability != "guts"
        and move.id != "facade"
    )

    final_mods = calculate_final_mods(
        attacker, defender, move, field, type_effectiveness, flags, move_type, is_critical
    )
    if protect_pierce:
        final_mods.append(1024)  # 0.25x, matching Unseen Fist's own bypassProtect mod

    final_mod = chain_mods(final_mods, 41, 131072)

    return [
        get_final_damage(base_damage, i, type_effectiveness, apply_burn, pre_stab_mod, final_mod)
        for i in range(16)
    ]


def calculate_base_power(
    attacker: Mon,
    defender: Mon,
    move: MoveSpec,
    field: FieldState,
    dex: Dex,
    has_ate_ability_type_change: bool,
    move_type: str,
) -> float:
    """`move_type` is the RESOLVED effective type (post Weather Ball/
    Terrain Pulse/-ate-ability/etc resolution in calculate_damage), NOT
    `move.type` (the raw dex type). This matters: Terrain Pulse becomes
    Grass-typed under Grassy Terrain, and while grounded should get BOTH
    its own unique BP-doubling AND the generic terrain same-type-boost
    (5325) below - the latter must check the resolved type, or it never
    fires for any dynamically-typed move. Confirmed missing via
    differential fuzzing against the oracle (a real bug, also present
    upstream in poke-env's own Python port)."""
    attacker_spe = _effective_speed(attacker, field)
    defender_spe = _effective_speed(defender, field)
    attacker_first = attacker_spe > defender_spe

    base_power = move.base_power * 1.0

    defender_ability = defender.ability
    if move.id in MOVE_IGNORES_ABILITY or (
        attacker.ability in ATTACKER_IGNORES_ABILITY
        and defender_ability not in DEFENDER_ABILITY_IGNORED
    ):
        defender_ability = ""

    defender_weight = defender.weight_kg
    if defender_ability == "lightmetal":
        defender_weight *= 0.5
    elif defender_ability == "heavymetal":
        defender_weight *= 2

    attacker_weight = attacker.weight_kg
    if attacker.ability == "lightmetal":
        attacker_weight *= 0.5
    elif attacker.ability == "heavymetal":
        attacker_weight *= 2

    if move.id == "payback":
        base_power = base_power * (2 if not attacker_first else 1)
    elif move.id == "electroball":
        if defender_spe == 0:
            base_power = 40
        elif math.floor(attacker_spe / defender_spe) >= 4:
            base_power = 150
        elif math.floor(attacker_spe / defender_spe) >= 3:
            base_power = 120
        elif math.floor(attacker_spe / defender_spe) >= 2:
            base_power = 80
        elif math.floor(attacker_spe / defender_spe) >= 1:
            base_power = 60
        else:
            base_power = 40
    elif move.id == "gyroball":
        base_power = 1 if attacker_spe == 0 else min(150, math.floor((25 * defender_spe) / attacker_spe) + 1)
    elif move.id == "punishment":
        # Only POSITIVE stat stages count ("+20 per stage the target's
        # stats have been RAISED") - confirmed via fuzzing against the
        # oracle; upstream's naive sum-including-negatives is a bug shared
        # with the storedpower/powertrip branch below.
        raised_stages = sum(max(0, defender.boosts[s]) for s in ("atk", "def", "spa", "spd", "spe"))
        base_power = min(200, 60 + 20 * raised_stages)
    elif move.id in ("lowkick", "grassknot"):
        if defender_weight >= 200:
            base_power = 120
        elif defender_weight >= 100:
            base_power = 100
        elif defender_weight >= 50:
            base_power = 80
        elif defender_weight >= 25:
            base_power = 60
        elif defender_weight >= 10:
            base_power = 40
        else:
            base_power = 20
    elif move.id in ("hex", "infernalparade"):
        # Champions drops the Comatose OR-clause (confirmed).
        base_power = base_power * (2 if defender.status is not None else 1)
    elif move.id == "barbbarrage":
        base_power = base_power * (2 if defender.has_status("psn", "tox") else 1)
    elif move.id in ("heavyslam", "heatcrash"):
        if defender_weight == 0:
            base_power = 40
        elif attacker_weight / defender_weight >= 5:
            base_power = 120
        elif attacker_weight / defender_weight >= 4:
            base_power = 100
        elif attacker_weight / defender_weight >= 3:
            base_power = 80
        elif attacker_weight / defender_weight >= 2:
            base_power = 60
        else:
            base_power = 40
    elif move.id in ("storedpower", "powertrip"):
        # Only POSITIVE stat stages count ("+20 per stage the user's stats
        # have been RAISED") - confirmed via fuzzing against the oracle;
        # upstream's naive sum-including-negatives is a real bug (it can
        # even go negative and get silently floor-clamped to BP 1 later).
        raised_stages = sum(max(0, attacker.boosts[s]) for s in ("atk", "def", "spa", "spd", "spe"))
        base_power = 20 + 20 * raised_stages
    elif move.id == "acrobatics":
        # Champions: "!attacker.item" only (no Flying Gem/Booster Energy -
        # neither exists in the Champions item pool anyway). Klutz also
        # counts (confirmed via fuzzing): it negates the item's effect,
        # which Acrobatics treats the same as not holding one at all.
        base_power = base_power * (2 if (not attacker.item or attacker.has_ability("klutz")) else 1)
    elif move.id == "smellingsalts":
        # Champions drops the Comatose OR-clause (confirmed pattern).
        base_power = base_power * (2 if defender.status == "par" else 1)
    elif move.id == "weatherball":
        base_power = base_power * (2 if (field.weather is not None or attacker.has_ability("megasol")) else 1)
    elif move.id == "terrainpulse":
        base_power = base_power * (2 if is_grounded(attacker, field) and field.terrain is not None else 1)
    elif move.id == "risingvoltage":
        base_power = base_power * (2 if is_grounded(defender, field) and field.terrain == "Electric" else 1)
    elif move.id == "eruption" or move.id == "waterspout":
        base_power = max(1, math.floor(150 * attacker.current_hp_fraction))
    elif move.id in ("flail", "reversal"):
        hp_frac_48 = math.floor(48 * attacker.current_hp_fraction)
        if hp_frac_48 <= 1:
            base_power = 200
        elif hp_frac_48 <= 4:
            base_power = 150
        elif hp_frac_48 <= 9:
            base_power = 100
        elif hp_frac_48 <= 16:
            base_power = 80
        elif hp_frac_48 <= 32:
            base_power = 40
        else:
            base_power = 20
    elif move.id == "hardpress":
        # Hard Press: 100 * (defender's current HP / max HP), floored, min
        # 1 - a simpler formula than Crush Grip/Wring Out's, which uses a
        # different 120-based fixed-point constant (those two are removed/
        # illegal in Champions per research, so aren't handled here at all).
        base_power = max(1, math.floor(100 * defender.current_hp_fraction))

    if base_power == 0:
        return 0

    bp_mods = calculate_base_power_mods(
        attacker, defender, move, field, base_power, has_ate_ability_type_change, attacker_first, move_type
    )
    return max(1, poke_round(base_power * chain_mods(bp_mods, 41, 2097152) / 4096))


def calculate_base_power_mods(
    attacker: Mon,
    defender: Mon,
    move: MoveSpec,
    field: FieldState,
    base_power: float,
    has_ate_ability_type_change: bool,
    attacker_first: bool,
    move_type: str,
) -> list[int]:
    bp_mods = []

    # Approximate, matching upstream's own documented caveat ("knockoff
    # damage isnt realllllly right cuz I dont look at pokemon/item pairs,
    # just items"): Memories and Drives don't get the bonus; everything
    # else held does, including Mega Stones (a further approximation this
    # port adds - a real Mega Stone that hasn't Mega Evolved yet CAN be
    # Knocked Off, and a stateless calculator has no way to know whether
    # the holder already has; Champions' signature orbs/masks are all
    # removed items either way, so that part of upstream's exclusion list
    # is moot here).
    extra_knockoff_damage = (
        defender.item is not None
        and not defender.item.endswith("memory")
        and not defender.item.endswith("drive")
    )

    # Lash Out's real doubling condition ("user's stats were lowered THIS
    # TURN") needs turn-tracking state neither a stateless calculator nor
    # (confirmed by fuzzing) the oracle itself has - upstream's own
    # heuristic (net current boost sum < 0) is a worse approximation than
    # not applying it at all, since it misfires on any pre-existing
    # negative boost regardless of when it happened. Dropped to match the
    # oracle's own apparent default of never doubling it.
    if (
        (move.id == "facade" and attacker.has_status("brn", "par", "psn", "tox"))
        or (move.id == "venoshock" and defender.has_status("psn", "tox"))
    ):
        bp_mods.append(8192)
    elif move.id == "expandingforce" and is_grounded(attacker, field) and field.terrain == "Psychic":
        bp_mods.append(6144)
    elif (
        (move.id == "knockoff" and extra_knockoff_damage)
        or (move.id == "mistyexplosion" and is_grounded(attacker, field) and field.terrain == "Misty")
        or (move.id == "gravapple" and field.is_gravity)
    ):
        bp_mods.append(6144)
    elif (
        move.id in ("solarbeam", "solarblade")
        and field.weather is not None
        and field.weather != "Sun"  # Sun is Solar Beam/Blade's OWN good weather - never halved
        and not attacker.has_ability("megasol")
    ):
        # Champions: halving still applies in bad weather, but never for
        # Mega Sol (confirmed: "&& !attacker.hasAbility('Mega Sol')").
        bp_mods.append(2048)

    if field.attacker_side.is_helping_hand:
        bp_mods.append(6144)

    # Fairy Aura/Dark Aura are FIELD-wide: EITHER mon having the ability
    # boosts ALL Fairy/Dark moves used by anyone (confirmed retained in
    # champions.ts's BP mods list: "Fairy/Dark Aura active (attacker/
    # defender ability or field flag)"; confirmed missing here via fuzzing).
    if move_type == "Fairy" and (attacker.has_ability("fairyaura") or defender.has_ability("fairyaura")):
        bp_mods.append(5448)
    elif move_type == "Dark" and (attacker.has_ability("darkaura") or defender.has_ability("darkaura")):
        bp_mods.append(5448)

    if is_grounded(attacker, field) and (
        (field.terrain == "Electric" and move_type == "Electric")
        or (field.terrain == "Grassy" and move_type == "Grass")
        or (field.terrain == "Psychic" and move_type == "Psychic")
    ):
        # Champions: terrain multiplier is a flat constant 5325 (confirmed;
        # SV's is gen-conditional but Champions hard-codes the modern
        # value). Uses the resolved move_type (not move.type) so this
        # correctly stacks with Terrain Pulse's own doubling once Terrain
        # Pulse becomes terrain-typed - confirmed missing via fuzzing.
        bp_mods.append(5325)

    if is_grounded(defender, field) and (
        (field.terrain == "Misty" and move_type == "Dragon")
        or (field.terrain == "Grassy" and move.id in ("bulldoze", "earthquake"))
    ):
        bp_mods.append(2048)

    if (
        (attacker.ability == "technician" and base_power <= 60)
        or (attacker.ability == "megalauncher" and "pulse" in move.flags)
        or (attacker.ability == "strongjaw" and "bite" in move.flags)
        or (attacker.ability == "sharpness" and "slicing" in move.flags)
    ):
        bp_mods.append(6144)

    if "charge" in attacker.effects and move_type == "Electric":
        # Electromorphosis sets this volatile (confirmed retained in
        # champions.ts); Charge doubles the next Electric move's base power.
        bp_mods.append(8192)

    if (
        (attacker.ability == "sheerforce" and move.has_secondary)
        or (attacker.ability == "sandforce" and field.weather == "Sand" and move_type in ("Rock", "Ground", "Steel"))
        or (attacker.ability == "analytic" and not attacker_first)
        or (attacker.ability == "toughclaws" and "contact" in move.flags)
    ):
        bp_mods.append(5325)

    if attacker.ability == "rivalry" and attacker.gender and defender.gender:
        bp_mods.append(5120 if attacker.gender == defender.gender else 3072)

    if has_ate_ability_type_change:
        bp_mods.append(4915)

    if attacker.ability == "reckless" and move.recoil > 0:
        bp_mods.append(4915)
    elif attacker.ability == "ironfist" and "punch" in move.flags:
        bp_mods.append(4915)

    if defender.ability == "dryskin" and move_type == "Fire":
        bp_mods.append(5120)
    # Champions: Heatproof's Fire-move reduction moves to an attack-stat
    # modifier always (see calculate_atk_mods), not a base-power mod - so
    # unlike SV, there is no Heatproof branch here at all.

    if attacker.ability == "supremeoverlord" and attacker.allies_fainted > 0:
        pow_mod = [4096, 4506, 4915, 5325, 5734, 6144]
        bp_mods.append(pow_mod[min(attacker.allies_fainted, 5)])

    if (attacker.item or "").replace("gem", "").strip() == move_type.lower():
        bp_mods.append(5325)
    elif attacker.item and move_type == ITEM_BOOST_TYPES.get(attacker.item):
        bp_mods.append(4915)
    elif (attacker.item == "muscleband" and move.category == "Physical") or (
        attacker.item == "wiseglasses" and move.category == "Special"
    ):
        bp_mods.append(4505)

    return bp_mods


def calculate_attack(
    attacker: Mon, defender: Mon, move: MoveSpec, field: FieldState, move_type: str, is_critical: bool = False
) -> float:
    attack_stat = "atk" if move.category == "Physical" else "spa"
    if move.id == "bodypress":
        attack_stat = "def"

    attack_source = attacker if move.id != "foulplay" else defender

    if attack_source.boosts.get(attack_stat, 0) == 0 or (
        is_critical and attack_source.boosts.get(attack_stat, 0) < 0
    ) or defender.has_ability("unaware"):
        attack = attack_source.stats[attack_stat]
    else:
        attack = math.floor(attack_source.stats[attack_stat] * BOOST_MULTIPLIERS[attack_source.boosts[attack_stat]])

    if attacker.has_ability("hustle") and move.category == "Physical":
        attack = poke_round((attack * 3) / 2)

    at_mods = calculate_atk_mods(attacker, defender, move, field, move_type)
    return max(1, poke_round((attack * chain_mods(at_mods, 410, 131072)) / 4096))


def calculate_atk_mods(
    attacker: Mon, defender: Mon, move: MoveSpec, field: FieldState, move_type: str
) -> list[int]:
    """`move_type` is the resolved effective type, not move.type - see
    calculate_base_power's docstring."""
    atk_mods = []
    attacker_ally = attacker.ally

    if attacker.has_ability("solarpower") and field.weather == "Sun" and move.category == "Special":
        atk_mods.append(6144)
    # Champions' Mega Sol computes its own damage as if Sun were always
    # active - Solar Power (a separate, non-exclusive ability) is
    # unaffected by Mega Sol on a DIFFERENT mon, so no change here.
    elif (
        attacker.has_ability("guts") and attacker.status and move.category == "Physical"
    ) or (
        attacker.current_hp_fraction <= 1.0 / 3
        and (
            (attacker.has_ability("overgrow") and move_type == "Grass")
            or (attacker.has_ability("blaze") and move_type == "Fire")
            or (attacker.has_ability("torrent") and move_type == "Water")
            or (attacker.has_ability("swarm") and move_type == "Bug")
        )
    ):
        atk_mods.append(6144)
    elif attacker.has_ability("flashfire") and "flashfire" in attacker.effects and move_type == "Fire":
        atk_mods.append(6144)
    elif attacker.has_ability("firemane") and move_type == "Fire":
        # Champions-exclusive (Pyroar-Mega): 1.5x Atk on Fire moves.
        atk_mods.append(6144)
    elif attacker.has_ability("waterbubble") and move_type == "Water":
        atk_mods.append(8192)
    elif attacker.has_ability("hugepower", "purepower") and move.category == "Physical":
        atk_mods.append(8192)

    if (
        defender.ability == "thickfat" and move_type in ("Fire", "Ice")
    ) or (defender.ability == "waterbubble" and move_type == "Fire") or (
        defender.ability == "purifyingsalt" and move_type == "Ghost"
    ):
        atk_mods.append(2048)

    if defender.ability == "heatproof" and move_type == "Fire":
        # Champions applies Heatproof's Fire reduction as an attack-stat
        # mod unconditionally (confirmed: "atMod 2048 always" - unlike SV,
        # which gates this by generation and otherwise uses a base-power
        # mod branch).
        atk_mods.append(2048)

    if attacker.item == "lightball" and attacker.base_species == "pikachu":
        atk_mods.append(8192)

    return atk_mods


def calculate_defense(
    attacker: Mon, defender: Mon, move: MoveSpec, field: FieldState, is_critical: bool = False
) -> float:
    hits_physical = move.category == "Physical" or move.override_defensive_stat == "def"
    defense_stat = "def" if hits_physical else "spd"

    if defender.boosts.get(defense_stat, 0) == 0 or (
        is_critical and defender.boosts.get(defense_stat, 0) > 0
    ) or move.ignore_defensive or attacker.has_ability("unaware"):
        defense = defender.stats[defense_stat]
    else:
        defense = math.floor(defender.stats[defense_stat] * BOOST_MULTIPLIERS[defender.boosts[defense_stat]])

    # Champions: Sand/Snow's direct 1.5x defensive boost is suppressed if
    # the ATTACKER has Mega Sol (confirmed: "wrapped in `if
    # (!attacker.hasAbility('Mega Sol'))`" - note this gates the whole
    # boost, not just the weather-matches-Mega-Sol case).
    if not attacker.has_ability("megasol"):
        if field.weather == "Sand" and defender.has_type("Rock") and not hits_physical:
            defense = poke_round((defense * 3) / 2)
        if field.weather == "Snow" and defender.has_type("Ice") and hits_physical:
            defense = poke_round((defense * 3) / 2)

    def_mods = calculate_def_mods(attacker, defender, hits_physical)
    return max(1, poke_round((defense * chain_mods(def_mods, 410, 131072)) / 4096))


def calculate_def_mods(attacker: Mon, defender: Mon, hits_physical: bool = False) -> list[int]:
    def_mods = []
    if defender.has_ability("marvelscale") and defender.status and hits_physical:
        def_mods.append(6144)
    elif defender.has_ability("furcoat") and hits_physical:
        def_mods.append(8192)
    # Champions' def_mods list is otherwise empty (confirmed: "only two
    # entries exist in Champions" - Grass Pelt, Flower Gift, the four
    # Ruins, and Protosynthesis/Quark Drive's defensive boosts are gone).
    return def_mods


def calculate_base_damage(
    attacker: Mon,
    defender: Mon,
    base_power: float,
    attack: float,
    defense: float,
    move: MoveSpec,
    move_type: Optional[str],
    move_target: str,
    field: FieldState,
    is_critical: bool = False,
) -> float:
    is_spread = field.is_doubles and move_target in ("allAdjacent", "allAdjacentFoes")

    base_damage = math.floor(
        math.floor((math.floor(2 * attacker.level / 5 + 2) * base_power) * attack / defense) / 50 + 2
    )

    if is_spread:
        base_damage = poke_round((base_damage * 3072) / 4096)

    is_mega_sol = attacker.has_ability("megasol")
    if (field.weather == "Sun" or is_mega_sol) and move_type == "Fire":
        base_damage = poke_round((base_damage * 6144) / 4096)
    elif field.weather == "Rain" and not is_mega_sol and move_type == "Water":
        base_damage = poke_round((base_damage * 6144) / 4096)
    elif (field.weather == "Sun" or is_mega_sol) and move_type == "Water":
        base_damage = poke_round((base_damage * 2048) / 4096)
    elif field.weather == "Rain" and move_type == "Fire":
        base_damage = poke_round((base_damage * 2048) / 4096)

    if is_critical:
        base_damage = poke_round(base_damage * 1.5)

    return base_damage


def calculate_final_mods(
    attacker: Mon,
    defender: Mon,
    move: MoveSpec,
    field: FieldState,
    type_effectiveness: float,
    flags: dict[str, int],
    move_type: str,
    is_critical: bool = False,
    hit_count: int = 0,
) -> list[int]:
    """`move_type` is the resolved effective type, not move.type - see
    calculate_base_power's docstring."""
    final_mods = []
    # Infiltrator bypasses Reflect/Light Screen/Aurora Veil entirely
    # (confirmed retained in champions.ts's prologue: "clears Reflect/
    # Light Screen/Aurora Veil"; confirmed missing here via fuzzing).
    defender_side_conditions = (
        set() if attacker.has_ability("infiltrator") else field.defender_side.side_conditions
    )
    defender_ally = defender.ally

    if (
        "reflect" in defender_side_conditions
        and move.category == "Physical"
        and not is_critical
        and "auroraveil" not in defender_side_conditions
        and flags.get("ignorescreens", 0) != 1
    ):
        final_mods.append(2732 if field.is_doubles else 2048)
    elif (
        "lightscreen" in defender_side_conditions
        and move.category == "Special"
        and not is_critical
        and "auroraveil" not in defender_side_conditions
        and flags.get("ignorescreens", 0) != 1
    ):
        final_mods.append(2732 if field.is_doubles else 2048)
    elif (
        "auroraveil" in defender_side_conditions
        and not is_critical
        and flags.get("ignorescreens", 0) != 1
    ):
        final_mods.append(2732 if field.is_doubles else 2048)

    if attacker.has_ability("sniper") and is_critical:
        final_mods.append(6144)

    if defender.has_ability("multiscale") and defender.current_hp_fraction == 1 and hit_count == 0:
        final_mods.append(2048)

    if defender.has_ability("fluffy") and "contact" in flags and not attacker.has_ability("longreach"):
        final_mods.append(2048)

    if defender.has_ability("solidrock", "filter") and type_effectiveness > 1:
        final_mods.append(3072)

    if defender_ally and defender_ally.has_ability("friendguard"):
        final_mods.append(3072)

    if defender.has_ability("fluffy") and move_type == "Fire":
        final_mods.append(8192)

    if attacker.has_item("expertbelt") and type_effectiveness > 1:
        final_mods.append(4915)
    elif attacker.has_item("lifeorb"):
        final_mods.append(5324)
    # Metronome (the item) is not modelled - see module docstring.

    if (
        defender.item
        and move.id != "struggle"  # Struggle is typeless ("???"), not Normal, despite its dex entry
        and BERRY_RESISTS.get(defender.item) == move_type
        and (type_effectiveness > 1 or move_type == "Normal")
        and hit_count == 0
        and attacker.ability != "unnerve"
    ):
        final_mods.append(1024 if defender.has_ability("ripen") else 2048)

    return final_mods


def get_stab_mod(pokemon: Mon, move: MoveSpec, move_type: Optional[str]) -> int:
    """Champions has no Terastallization, so the tera/Adaptability-tera
    interaction in the vendored source is dropped entirely (confirmed:
    Stellar and Tera STAB are absent from champions.ts)."""
    stab_mod = 4096
    if move.id == "struggle":
        return stab_mod
    if move_type in pokemon.types:
        stab_mod += 2048
    elif pokemon.has_ability("protean", "libero"):
        stab_mod += 2048
    if pokemon.has_ability("adaptability") and move_type in pokemon.types:
        stab_mod += 2048
    return stab_mod


def get_berry_resist_type(berry: str) -> Optional[str]:
    return BERRY_RESISTS.get(berry)


def get_item_boost_type(item: str) -> Optional[str]:
    return ITEM_BOOST_TYPES.get(item)


def poke_round(num: float) -> int:
    """Game Freak rounds down on an exact .5 (confirmed identical in
    Champions - no override in champions.ts)."""
    return math.ceil(num) if num % 1 > 0.5 else math.floor(num)


def get_final_damage(
    base_amount: float, i: int, effectiveness: float, is_burned: bool, stab_mod: int, final_mod: int
) -> int:
    damage_amount = math.floor(base_amount * (85 + i) / 100) * 1.0
    if stab_mod != 4096:
        damage_amount = (damage_amount * stab_mod) / 4096
    damage_amount = math.floor(poke_round(damage_amount) * effectiveness)
    if is_burned:
        damage_amount = math.floor(damage_amount / 2)
    return poke_round(max(1, (damage_amount * final_mod) / 4096))


def chain_mods(mods: list[int], lb: int, ub: int) -> int:
    m = 4096
    for mod in mods:
        if mod != 4096:
            m = (m * mod + 2048) >> 12
    return max(min(m, ub), lb)


def get_move_effectiveness(
    dex: Dex,
    move: MoveSpec,
    move_type: str,
    defending_type: str,
    is_ghost_revealed: bool = False,
    is_gravity: bool = False,
    is_ring_target: bool = False,
) -> float:
    """is_ring_target is always False in Champions (Ring Target is a
    removed item) and is_ghost_revealed is Scrappy-only (Mind's Eye and
    Foresight are dropped) - callers already reflect that; kept as a
    parameter for structural parity with the vendored source."""
    if is_ghost_revealed and defending_type == "Ghost" and move_type in ("Normal", "Fighting"):
        return 1
    elif move.id == "struggle":
        return 1
    elif is_gravity and defending_type == "Flying" and move_type == "Ground":
        return 1
    elif move.id == "freezedry" and defending_type == "Water":
        return 2
    else:
        effectiveness = dex.type_chart[move_type][defending_type]
        if effectiveness == 0 and is_ring_target:
            effectiveness = 1
        if move.id == "flyingpress":
            effectiveness *= dex.type_chart["Flying"][defending_type]
        return effectiveness
