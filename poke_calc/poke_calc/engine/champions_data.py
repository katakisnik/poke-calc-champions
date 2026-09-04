"""Champions-specific constant tables for the damage engine.

Ported from poke-env's damage_calc_gen9.py (MIT, see NOTICE) constant tables,
narrowed/extended per the confirmed Champions deltas (see the plan's
"Champions mechanics deltas" section, sourced from reading
smogon/pokemon-showdown's data/mods/champions/*.ts and
smogon/damage-calc's calc/src/mechanics/champions.ts directly).
"""

from __future__ import annotations

# SV: {"moldbreaker", "teravolt", "turboblaze"}. Champions narrows this to
# Mold Breaker only (Teravolt/Turboblaze abilities aren't in the Champions
# ability pool either way, but the narrowing is explicit in champions.ts).
ATTACKER_IGNORES_ABILITY = {"moldbreaker"}

# SV: {"moongeistbeam", "photongeyser", "sunsteelstrike"}. Champions removes
# the moveIgnoresAbility mechanism entirely.
MOVE_IGNORES_ABILITY: set[str] = set()

# Abilities Mold Breaker (etc.) cannot ignore. Ported from poke-env's
# DEFENDER_ABILITY_IGNORED (itself unused dead code upstream - this port
# wires it in, since Champions' own defenderAbilityIgnored list is
# confirmed and it's a real mechanic, not a simplification). Champions
# removes: Aura Break, Dazzling, Flower Gift, Grass Pelt, Guard Dog, Ice
# Face, Ice Scales, Mind's Eye, Pastel Veil, Punk Rock, Simple, Suction
# Cups, Wonder Guard, Wonder Skin from the SV list.
DEFENDER_ABILITY_IGNORED = {
    "armortail", "aromaveil", "battlearmor", "bigpecks", "bulletproof",
    "clearbody", "contrary", "damp", "disguise", "dryskin", "eartheater",
    "filter", "flashfire", "flowerveil", "fluffy", "friendguard", "furcoat",
    "heatproof", "heavymetal", "hypercutter", "illuminate", "immunity",
    "innerfocus", "insomnia", "keeneye", "leafguard", "levitate",
    "lightmetal", "lightningrod", "limber", "magicbounce", "marvelscale",
    "mirrorarmor", "motordrive", "multiscale", "oblivious", "overcoat",
    "owntempo", "purifyingsalt", "queenlymajesty", "quickfeet", "raindish",
    "rockhead", "roughskin", "sandveil", "scrappy", "snowcloak",
    "snowwarning", "solidrock", "soundproof", "speedboost", "stakeout",
    "steelworker", "strongjaw", "tintedlens", "torrent", "trace",
    "waterabsorb", "waterveil", "weakarmor",
}

BOOST_MULTIPLIERS = {
    -6: 2.0 / 8, -5: 2.0 / 7, -4: 2.0 / 6, -3: 2.0 / 5, -2: 2.0 / 4, -1: 2.0 / 3,
    0: 1, 1: 1.5, 2: 2, 3: 2.5, 4: 3, 5: 3.5, 6: 4,
}

BERRY_RESISTS = {
    "chilanberry": "Normal", "occaberry": "Fire", "passhoberry": "Water",
    "wacanberry": "Electric", "rindoberry": "Grass", "yacheberry": "Ice",
    "chopleberry": "Fighting", "kebiaberry": "Poison", "shucaberry": "Ground",
    "cobaberry": "Flying", "payapaberry": "Psychic", "tangaberry": "Bug",
    "chartiberry": "Rock", "kasibberry": "Ghost", "habanberry": "Dragon",
    "colburberry": "Dark", "babiriberry": "Steel", "roseliberry": "Fairy",
}

# Champions has no Plates/Orbs/incenses (all removed - see NOTICE); the
# entries below that reference them are harmless dead data since the Dex
# never assigns those item ids. Kept for parity with the vendored source
# rather than pruned, since pruning risks silently dropping a legal item.
ITEM_BOOST_TYPES = {
    "dracoplate": "Dragon", "dragonfang": "Dragon",
    "dreadplate": "Dark", "blackglasses": "Dark",
    "earthplate": "Ground", "softsand": "Ground",
    "fistplate": "Fighting", "blackbelt": "Fighting",
    "flameplate": "Fire", "charcoal": "Fire",
    "icicleplate": "Ice", "nevermeltice": "Ice",
    "insectplate": "Bug", "silverpowder": "Bug",
    "ironplate": "Steel", "metalcoat": "Steel",
    "meadowplate": "Grass", "roseincense": "Grass", "miracleseed": "Grass",
    "mindplate": "Psychic", "oddincense": "Psychic", "twistedspoon": "Psychic",
    "fairyfeather": "Fairy", "pixieplate": "Fairy",
    "skyplate": "Flying", "sharpbeak": "Flying",
    "splashplate": "Water", "seaincense": "Water", "waveincense": "Water",
    "mysticwater": "Water",
    "spookyplate": "Ghost", "spelltag": "Ghost",
    "stoneplate": "Rock", "rockincense": "Rock", "hardstone": "Rock",
    "toxicplate": "Poison", "poisonbarb": "Poison",
    "zapplate": "Electric", "magnet": "Electric",
    "silkscarf": "Normal", "pinkbow": "Normal", "polkadotbow": "Normal",
}

# The 6 Champions-exclusive abilities (see data/mods/champions/abilities.ts).
# Spicy Spray is declared in Showdown's ability data but is never referenced
# in champions.ts's mechanics - confirmed unimplemented upstream, so it is
# deliberately a no-op here too rather than guessed at.
CHAMPIONS_EXCLUSIVE_ABILITIES = frozenset(
    {"megasol", "firemane", "dragonize", "eelevate", "piercingdrill", "spicyspray"}
)
