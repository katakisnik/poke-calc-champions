"""Loads @smogon/calc's Champions (generation 0) data dump into typed records.

The dump (poke_calc/data/dump/*.json) was produced by oracle/dump-data.js from
a pinned build of https://github.com/smogon/damage-calc — see NOTICE.

Each record keeps its original JSON under `.raw` so nothing the dump carries
is ever lost, even fields this loader doesn't give a typed accessor for.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path
from typing import Optional

DUMP_DIR = Path(__file__).parent / "dump"

STAT_NAMES = ("hp", "atk", "def", "spa", "spd", "spe")


def to_id(text: str) -> str:
    """Normalize a display name the way Showdown/@smogon/calc's toID does."""
    return re.sub(r"[^a-z0-9]", "", text.lower())


@dataclass(frozen=True)
class Species:
    id: str
    name: str
    base_stats: dict[str, int]
    types: tuple[str, ...]
    ability: str
    weight_kg: float
    base_species: Optional[str] = None
    other_formes: tuple[str, ...] = ()
    nfe: bool = False
    sprite_id: Optional[str] = None  # key into Showdown's sprites/ani/ CDN, see data/dump/sprite_ids.json
    raw: dict = field(default_factory=dict, repr=False, compare=False)

    @property
    def is_mega(self) -> bool:
        return self.base_species is not None and "Mega" in self.name

    @property
    def sprite_url(self) -> Optional[str]:
        if self.sprite_id is None:
            return None
        return f"https://play.pokemonshowdown.com/sprites/ani/{self.sprite_id}.gif"


@dataclass(frozen=True)
class MoveData:
    id: str
    name: str
    type: str
    category: str
    base_power: int
    priority: int = 0
    target: str = "normal"
    flags: dict[str, int] = field(default_factory=dict)
    multihit: Optional[tuple[int, int]] = None
    has_secondary: bool = False
    drain: Optional[tuple[int, int]] = None
    recoil: float = 0.0  # fraction of damage dealt, e.g. 0.33 for Flare Blitz
    breaks_protect: bool = False
    ignore_defensive: bool = False
    override_defensive_stat: Optional[str] = None
    will_crit: bool = False  # e.g. Storm Throw, Frost Breath, Flower Trick
    crit_ratio: int = 1  # 1 = base rate; see data/generate_crit_ratios.py
    description: Optional[str] = None  # see data/generate_move_descriptions.py
    raw: dict = field(default_factory=dict, repr=False, compare=False)

    @property
    def is_spread(self) -> bool:
        return self.target in ("allAdjacent", "allAdjacentFoes")

    @property
    def is_status(self) -> bool:
        return self.category == "Status"


@dataclass(frozen=True)
class ItemData:
    id: str
    name: str
    mega_stone: Optional[dict[str, str]] = None
    is_berry: bool = False
    raw: dict = field(default_factory=dict, repr=False, compare=False)

    @property
    def is_mega_stone(self) -> bool:
        return self.mega_stone is not None


@dataclass(frozen=True)
class AbilityData:
    id: str
    name: str
    description: Optional[str] = None  # see data/generate_ability_descriptions.py
    raw: dict = field(default_factory=dict, repr=False, compare=False)


@dataclass(frozen=True)
class Nature:
    name: str
    plus: Optional[str]
    minus: Optional[str]

    @property
    def is_neutral(self) -> bool:
        return self.plus == self.minus


def _load_json(filename: str) -> dict:
    with open(DUMP_DIR / filename, encoding="utf-8") as f:
        return json.load(f)


def _multihit(raw: dict) -> Optional[tuple[int, int]]:
    mh = raw.get("multihit")
    if mh is None:
        return None
    if isinstance(mh, list):
        return (mh[0], mh[1])
    return (mh, mh)


def _drain(raw: dict) -> Optional[tuple[int, int]]:
    d = raw.get("drain")
    return (d[0], d[1]) if d else None


def _recoil(raw: dict) -> float:
    r = raw.get("recoil")
    return r[0] / r[1] if r else 0.0


# @smogon/calc's own CHAMPIONS_PATCH merge is shallow for these 12 move ids:
# the patch object (which only carries the *changed* fields, e.g. {bp: 90})
# replaces the base SV move entry instead of merging into it, so `type` (and
# for Metal Claw, `basePower`) is silently dropped. Confirmed upstream, not a
# dump artifact: `calculate()` itself throws for all 12 in the pinned build
# (see NOTICE). Only anchorshot/boltbeak/fishiousrend/geargrind are actually
# legal in Champions today; the rest are "Past"-flagged and dormant, but all
# 12 are patched here for a self-consistent dex. basePower is left alone
# except for Metal Claw, whose patch entry has none at all.
_MOVE_TYPE_OVERRIDES: dict[str, str] = {
    "anchorshot": "Steel",
    "astralbarrage": "Ghost",
    "bloodmoon": "Normal",
    "boltbeak": "Electric",
    "dragonhammer": "Dragon",
    "fishiousrend": "Water",
    "geargrind": "Steel",
    "hyperdrill": "Normal",
    "metalclaw": "Steel",
    "revelationdance": "Normal",
    "snipeshot": "Water",
    "tripledive": "Water",
}
_MOVE_BASE_POWER_OVERRIDES: dict[str, int] = {
    "metalclaw": 50,
}


class Dex:
    """Champions (gen 0) data, keyed by normalized id, with forgiving lookups."""

    def __init__(self):
        species_raw = _load_json("species.json")
        moves_raw = _load_json("moves.json")
        items_raw = _load_json("items.json")
        abilities_raw = _load_json("abilities.json")
        natures_raw = _load_json("natures.json")
        self.type_chart: dict[str, dict[str, float]] = _load_json("typeChart.json")
        self.meta: dict = _load_json("meta.json")
        sprite_ids: dict = _load_json("sprite_ids.json")
        self._learnsets: dict[str, list[str]] = _load_json("learnsets.json")
        self._pokekipe_sets: dict = _load_json("pokekipe_sets.json")
        self._ability_slots: dict[str, list[str]] = _load_json("ability_slots.json")
        ability_descriptions: dict = _load_json("ability_descriptions.json")
        move_descriptions: dict = _load_json("move_descriptions.json")
        crit_ratios: dict = _load_json("crit_ratios.json")

        self.species: dict[str, Species] = {
            sid: Species(
                id=sid,
                name=raw["name"],
                base_stats={
                    "hp": raw["baseStats"]["hp"],
                    "atk": raw["baseStats"]["atk"],
                    "def": raw["baseStats"]["def"],
                    "spa": raw["baseStats"]["spa"],
                    "spd": raw["baseStats"]["spd"],
                    "spe": raw["baseStats"]["spe"],
                },
                types=tuple(raw["types"]),
                ability=raw.get("abilities", {}).get("0", ""),
                weight_kg=raw.get("weightkg", 0.0),
                base_species=raw.get("baseSpecies"),
                other_formes=tuple(raw.get("otherFormes", [])),
                nfe=raw.get("nfe", False),
                sprite_id=sprite_ids.get(sid),
                raw=raw,
            )
            for sid, raw in species_raw.items()
        }

        self.moves: dict[str, MoveData] = {
            mid: MoveData(
                id=mid,
                name=raw["name"],
                type=raw.get("type") or _MOVE_TYPE_OVERRIDES[mid],
                category=raw.get("category", "Status"),
                base_power=_MOVE_BASE_POWER_OVERRIDES.get(mid, raw.get("basePower", 0)),
                priority=raw.get("priority", 0),
                target=raw.get("target", "normal"),
                flags=raw.get("flags", {}),
                multihit=_multihit(raw),
                has_secondary=bool(raw.get("secondaries", False)),
                drain=_drain(raw),
                recoil=_recoil(raw),
                breaks_protect=raw.get("breaksProtect", False),
                ignore_defensive=raw.get("ignoreDefensive", False),
                override_defensive_stat=raw.get("overrideDefensiveStat"),
                will_crit=raw.get("willCrit", False),
                crit_ratio=crit_ratios.get(mid, 1),
                description=move_descriptions.get(mid),
                raw=raw,
            )
            for mid, raw in moves_raw.items()
        }

        self.items: dict[str, ItemData] = {
            iid: ItemData(
                id=iid,
                name=raw["name"],
                mega_stone=raw.get("megaStone"),
                is_berry=raw.get("isBerry", False),
                raw=raw,
            )
            for iid, raw in items_raw.items()
        }

        self.abilities: dict[str, AbilityData] = {
            aid: AbilityData(id=aid, name=raw["name"], description=ability_descriptions.get(aid), raw=raw)
            for aid, raw in abilities_raw.items()
        }

        self.natures: dict[str, Nature] = {
            name: Nature(name=name, plus=plus, minus=minus)
            for name, (plus, minus) in natures_raw.items()
        }
        self._natures_by_id = {to_id(n): nat for n, nat in self.natures.items()}

    # --- forgiving lookups -------------------------------------------------

    def get_species(self, name: str) -> Species:
        sid = to_id(name)
        try:
            return self.species[sid]
        except KeyError:
            raise KeyError(f"'{name}' is not in the Champions roster ({sid!r})") from None

    def get_move(self, name: str) -> MoveData:
        mid = to_id(name)
        try:
            return self.moves[mid]
        except KeyError:
            raise KeyError(f"'{name}' is not a legal Champions move ({mid!r})") from None

    def get_item(self, name: str) -> ItemData:
        iid = to_id(name)
        try:
            return self.items[iid]
        except KeyError:
            raise KeyError(f"'{name}' is not a legal Champions item ({iid!r})") from None

    def get_ability(self, name: str) -> AbilityData:
        aid = to_id(name)
        try:
            return self.abilities[aid]
        except KeyError:
            raise KeyError(f"'{name}' is not a Champions ability ({aid!r})") from None

    def get_nature(self, name: str) -> Nature:
        nid = to_id(name)
        try:
            return self._natures_by_id[nid]
        except KeyError:
            raise KeyError(f"'{name}' is not a known nature ({nid!r})") from None

    def type_effectiveness(self, move_type: str, defender_types: tuple[str, ...]) -> float:
        row = self.type_chart[move_type]
        mult = 1.0
        for t in defender_types:
            mult *= row[t]
        return mult

    def mega_stone_for(self, species_name: str) -> Optional[ItemData]:
        """The Mega Stone that turns a Pokemon into `species_name`, or None
        if it isn't a Mega forme. Looked up by matching the forme's own
        display name against each Mega Stone's `mega_stone` dict VALUES
        (not by base species), since some stones map multiple base species
        to their own formes (e.g. Meowsticite: Meowstic->Meowstic-M-Mega
        *and* Meowstic-F->Meowstic-F-Mega) - matching by value is correct
        for either forme regardless of how the base key is spelled."""
        species = self.get_species(species_name)
        for item in self.items.values():
            if item.mega_stone and species.name in item.mega_stone.values():
                return item
        return None

    def ladder_set(self, species_name: str) -> Optional[tuple[str, dict[str, int], Optional[str]]]:
        """The most-used real nature + SP spread + held item for
        `species_name` from Pokekipe's Champions Doubles (VGC Reg M-B)
        ladder data (see data/generate_pokekipe_sets.py) - or None if that
        species has no recorded data (common for niche or brand-new Mega
        formes). Doubles-only by request, regardless of the UI's Singles/
        Doubles toggle. The item is the raw most-used one from that
        snapshot - it is NOT filtered for legality under any particular
        Regulation (that's the caller's job, e.g. ui/app.py falling back to
        "(none)" if it isn't legal) - and for a Mega forme it's simply
        that Mega's own Stone (harmless; callers that hardcode the Mega
        Stone for Mega formes can ignore this field for them)."""
        sid = to_id(species_name)
        entry = self._pokekipe_sets.get(sid)
        if entry is None:
            return None
        item_id = entry.get("item")
        item_name = self.items[item_id].name if item_id and item_id in self.items else None
        return entry["nature"], dict(entry["sp"]), item_name

    def ability_slots(self, species_name: str) -> list[AbilityData]:
        """The abilities `species_name` can actually have (its normal
        Slot 0 / Slot 1 / Hidden Ability pool), per Showdown's base
        data/pokedex.ts (see poke_calc/data/generate_ability_slots.py) - filtered to
        abilities this dex actually has data for (one ability, "Battle
        Bond", appears in pokedex.ts but not in @smogon/calc's own
        Champions ability table, so there's nothing to simulate it with).

        Note: for exactly 2 species (Hawlucha-Mega, Skarmory-Mega) the
        species' own `.ability` field disagrees with this list - a
        confirmed @smogon/calc-vs-pokedex.ts discrepancy, not a bug here;
        see generate_ability_slots.py's docstring. Callers that need a
        default should not assume `species.ability` is always a member of
        this list."""
        sid = to_id(species_name)
        names = self._ability_slots.get(sid, [])
        return [self.abilities[to_id(n)] for n in names if to_id(n) in self.abilities]

    def learnset(self, species_name: str) -> set[str]:
        """Move ids `species_name` can legally learn, per Showdown's
        data/mods/champions/learnsets.ts (see poke_calc/data/generate_learnsets.py).
        Mega formes fall back to their base species' learnset - Mega
        Evolution doesn't change what a Pokemon can learn."""
        sid = to_id(species_name)
        try:
            return set(self._learnsets[sid])
        except KeyError:
            raise KeyError(f"'{species_name}' has no known learnset ({sid!r})") from None

    def learnable_moves(self, species_name: str) -> dict[str, MoveData]:
        """`self.moves` filtered to what `species_name` can legally learn
        AND that this dex actually has data for (a small number of moves
        appear in Showdown's learnset but not in @smogon/calc's own
        Champions move table, e.g. "Pound" - excluded here since there is
        nothing to calculate damage with for them anyway)."""
        learnable_ids = self.learnset(species_name)
        return {mid: move for mid, move in self.moves.items() if mid in learnable_ids}


@lru_cache(maxsize=1)
def load_dex() -> Dex:
    return Dex()
