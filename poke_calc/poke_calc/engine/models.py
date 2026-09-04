"""Plain dataclasses standing in for poke-env's Battle/Pokemon/Move objects.

damage_calc_gen9.py (vendored in damage.py) was written against poke-env's
rich, enum-heavy Battle API. Almost everything it actually reads is a plain
lowercase id string (ability, item, move.id, status) or a simple numeric
field, so rather than depend on poke-env itself we model the same surface
with plain dataclasses. This also matches how @smogon/calc's own `Generation`
objects and `Field`/`Side` options work (see oracle/calc/src/state.ts),
which keeps FieldState/Side close to what the JSON oracle harness expects.

Stats are RAW (unboosted) final stats - the output of engine.stats.calc_stat -
with stage boosts (-6..6) applied separately via `boosts`, exactly matching
both poke-env's Pokemon.stats/boosts split and @smogon/calc's rawStats/boosts
split.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

STAT_NAMES = ("hp", "atk", "def", "spa", "spd", "spe")
BOOSTABLE_STATS = ("atk", "def", "spa", "spd", "spe")

# Champions has no Terastallization/Dynamax/Z-Moves, so weather/terrain/status
# are modelled with only the values Champions actually has (see NOTICE and
# the plan's "Champions mechanics deltas" section) rather than poke-env's
# full Gen 9 enums (no Harsh Sunshine/Heavy Rain/Strong Winds, no Stellar).
WEATHERS = ("Sun", "Rain", "Sand", "Snow")
TERRAINS = ("Electric", "Grassy", "Misty", "Psychic")
STATUSES = ("brn", "par", "psn", "tox", "slp", "frz")
PROTECT_EFFECTS = frozenset(
    {"protect", "spikyshield", "kingsshield", "banefulbunker", "obstruct", "silktrap"}
)


@dataclass
class MoveSpec:
    id: str  # normalized (to_id'd), e.g. "earthquake"
    name: str
    type: str  # e.g. "Ground" - matches Dex/type-chart casing
    category: str  # "Physical" | "Special" | "Status"
    base_power: int
    priority: int = 0
    target: str = "normal"  # "normal" | "self" | "allAdjacent" | "allAdjacentFoes"
    flags: dict[str, int] = field(default_factory=dict)
    has_secondary: bool = False
    n_hit: tuple[int, int] = (1, 1)
    is_crit: bool = False
    ignore_defensive: bool = False
    breaks_protect: bool = False
    recoil: float = 0.0
    override_defensive_stat: Optional[str] = None


@dataclass
class Mon:
    species: str  # normalized species id, e.g. "taurospaldeacombat"
    base_species: str  # normalized base-forme species id, e.g. "cubone"
    types: tuple[str, ...]
    stats: dict[str, int]  # raw final stats: hp/atk/def/spa/spd/spe
    weight_kg: float = 0.0
    level: int = 50
    ability: str = ""  # normalized id, e.g. "intimidate"
    item: Optional[str] = None  # normalized id, or None for no item
    gender: Optional[str] = None  # "M" | "F" | None (genderless/neutral)
    status: Optional[str] = None  # one of STATUSES, or None
    current_hp_fraction: float = 1.0  # 0.0-1.0
    boosts: dict[str, int] = field(
        default_factory=lambda: {s: 0 for s in BOOSTABLE_STATS}
    )
    effects: set[str] = field(default_factory=set)  # volatile ids, e.g. "flashfire", "charge"
    allies_fainted: int = 0  # for Supreme Overlord; mirrors @smogon/calc's own field
    ally: Optional["Mon"] = None  # doubles partner, for Plus/Minus/Friend Guard/etc.
    fainted: bool = False

    @property
    def type_1(self) -> str:
        return self.types[0]

    @property
    def type_2(self) -> Optional[str]:
        return self.types[1] if len(self.types) > 1 else None

    def has_ability(self, *names: str) -> bool:
        return self.ability in names

    def has_item(self, *names: str) -> bool:
        return self.item in names

    def has_status(self, *names: str) -> bool:
        return self.status in names

    def has_type(self, *types: str) -> bool:
        return any(t in self.types for t in types)


@dataclass
class Side:
    side_conditions: set[str] = field(default_factory=set)  # "reflect"/"lightscreen"/"auroraveil"
    is_protected: bool = False
    is_helping_hand: bool = False  # cast by an ally onto this side's attacker for the turn


@dataclass
class FieldState:
    game_type: str = "Singles"  # "Singles" | "Doubles"
    weather: Optional[str] = None  # one of WEATHERS, or None
    terrain: Optional[str] = None  # one of TERRAINS, or None
    is_gravity: bool = False
    attacker_side: Side = field(default_factory=Side)
    defender_side: Side = field(default_factory=Side)

    @property
    def is_doubles(self) -> bool:
        return self.game_type == "Doubles"


def is_grounded(mon: Mon, field_state: FieldState) -> bool:
    """Only the checks damage.py actually needs: Gravity and Iron Ball force
    grounding; Flying types and Levitate/Eelevate (the Champions-exclusive
    Levitate clone) are airborne otherwise. Champions has no Air Balloon,
    Ingrain, Roost, or Smack Down in its item/move pool, so those aren't
    modelled."""
    if field_state.is_gravity or mon.has_item("ironball"):
        return True
    if mon.has_type("Flying"):
        return False
    if mon.has_ability("levitate", "eelevate"):
        return False
    return True
