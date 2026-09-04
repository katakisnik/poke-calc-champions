"""Regenerates data/dump/ability_slots.json - the set of abilities each
Champions dex species can actually have (its normal Slot 0 / Slot 1 /
Hidden Ability pool), sourced from Showdown's base data/pokedex.ts.

@smogon/calc's own species data (data/dump/species.json, this project's
main dex) only records ONE ability per species - confirmed earlier this
project (every one of our 324 species has exactly one `abilities.0`
entry). That's not a Champions game mechanic, though: it's because
@smogon/calc is a calculator, not a team validator, and its own web UI
lets you type any ability freely regardless of species. Champions itself
DOES restrict ability choice: its ruleset inherits "Obtainable Abilities"
(confirmed by reading data/mods/champions/rulesets.ts's `standardag` ->
`Standard AG` chain), the same mainline restriction to a species' normal
ability slots. Since there is no champions/pokedex.ts override, those
slots come from the unmodified base dex - including the ~35 new
Champions-exclusive Mega formes, which ARE present there already (just
`isNonstandard: "Future"` until a regulation enables them).

Cross-checking the two sources surfaced a genuine, if minor, discrepancy:
@smogon/calc's own species.json lists "Limber" for Hawlucha-Mega and
"Keen Eye" for Skarmory-Mega, while pokedex.ts (and this project's own
earlier, independently-sourced research into Champions' Mega list) says
"No Guard" and "Stalwart". pokedex.ts is treated as authoritative here;
callers should not assume a species' own `.ability` field is always a
member of its ability_slots() list (see loader.py's Dex.ability_slots()
docstring for how the UI handles that).

Run from poke_calc/ (with the venv active) after any dex refresh:
    python -m poke_calc.data.generate_ability_slots
"""

from __future__ import annotations

import json
import re
import urllib.request
from pathlib import Path

from poke_calc.data.loader import load_dex, to_id

POKEDEX_URL = "https://raw.githubusercontent.com/smogon/pokemon-showdown/master/data/pokedex.ts"
OUT_PATH = Path(__file__).parent / "dump" / "ability_slots.json"

_BLOCK_RE = re.compile(r"^\t([a-z0-9]+): \{\n(.*?)\n\t\},\n", re.MULTILINE | re.DOTALL)
_ABILITIES_RE = re.compile(r"abilities: \{([^}]*)\}")
_NAME_RE = re.compile(r'"([^"]+)"')


def _fetch_source() -> str:
    req = urllib.request.Request(POKEDEX_URL, headers={"User-Agent": "curl/8.0"})
    with urllib.request.urlopen(req, timeout=30) as resp:
        return resp.read().decode("utf-8")


def _parse_blocks(text: str) -> dict[str, list[str]]:
    blocks = {}
    for m in _BLOCK_RE.finditer(text):
        sid, body = m.group(1), m.group(2)
        am = _ABILITIES_RE.search(body)
        if am:
            blocks[sid] = _NAME_RE.findall(am.group(1))
    return blocks


def main():
    blocks = _parse_blocks(_fetch_source())
    dex = load_dex()

    result: dict[str, list[str]] = {}
    unresolved: list[str] = []
    for sid, species in dex.species.items():
        if sid in blocks:
            result[sid] = blocks[sid]
            continue
        if species.base_species and to_id(species.base_species) in blocks:
            result[sid] = blocks[to_id(species.base_species)]
            continue
        prefix = to_id(species.name.split("-")[0])
        if "-" in species.name and prefix in blocks:
            result[sid] = blocks[prefix]
            continue
        unresolved.append(species.name)

    OUT_PATH.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(f"resolved {len(result)}/{len(dex.species)}; wrote {OUT_PATH}")
    if unresolved:
        print(f"unresolved (no ability slots found anywhere): {unresolved}")

    mismatched = [
        species.name for sid, species in dex.species.items()
        if sid in result and species.ability not in result[sid]
    ]
    if mismatched:
        print(f"NOTE: {len(mismatched)} species' own .ability isn't in its ability_slots() "
              f"list (pokedex.ts vs @smogon/calc discrepancy - see module docstring): {mismatched}")


if __name__ == "__main__":
    main()
