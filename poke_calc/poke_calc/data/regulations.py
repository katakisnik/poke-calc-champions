"""Regulation-level item/Mega Stone legality: M-A vs M-B.

@smogon/calc's own Champions data (data/dump/*.json) is Reg M-B-shaped -
confirmed in Phase 1 by direct testing (Life Orb produces an exact 1.3x
multiplier there). Reg M-A is a strict subset: Showdown's `championsregma`
mod is defined purely as a diff against the base `champions` mod, banning
these ids via `isNonstandard: "Past"` (previously legal, rotated out) or
`"Future"` (not yet released) - both mean "not legal in M-A" here. Fetched
directly from
https://raw.githubusercontent.com/smogon/pokemon-showdown/master/data/mods/championsregma/items.ts
(31 entries total, all `inherit: true` diffs - no guessing involved).

Species/move/ability legality does NOT differ between M-A and M-B (there is
no championsregma/formats-data.ts or pokedex.ts - confirmed 404 on both) -
only this item/Mega Stone set does, so that's all this module needs to model.
"""

from __future__ import annotations

from poke_calc.data.loader import Dex, ItemData

# fmt: off
_BANNED_IN_REG_M_A: frozenset[str] = frozenset({
    # regular items ("Past" in championsregma - legal in M-B, not M-A)
    "bigroot", "damprock", "expertbelt", "heatrock", "icyrock", "ironball",
    "lifeorb", "lightclay", "metronome", "muscleband", "shedshell",
    "smoothrock", "wiseglasses", "widelens", "zoomlens",
    # Mega Stones ("Past" - previously legal, rotated out for M-A)
    "blazikenite", "mawilite", "metagrossite", "sceptilite", "swampertite",
    # Mega Stones ("Future" - not yet released as of M-A)
    "barbaracite", "dragalgite", "eelektrossite", "falinksite", "malamarite",
    "pyroarite", "raichunitex", "raichunitey", "scolipite", "scraftinite",
    "staraptite",
})
# fmt: on

REGULATIONS = ("M-A", "M-B")


def is_item_legal(item_id: str, regulation: str) -> bool:
    if regulation == "M-B":
        return True
    if regulation == "M-A":
        return item_id not in _BANNED_IN_REG_M_A
    raise ValueError(f"unknown regulation {regulation!r}, expected one of {REGULATIONS}")


def legal_items(dex: Dex, regulation: str) -> dict[str, ItemData]:
    """The dex's item table filtered to what's legal under `regulation`."""
    return {iid: item for iid, item in dex.items.items() if is_item_legal(iid, regulation)}
