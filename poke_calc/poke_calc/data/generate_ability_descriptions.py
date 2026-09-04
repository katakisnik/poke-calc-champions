"""Regenerates data/dump/ability_descriptions.json - a short human-readable
description for each ability, sourced from Showdown's base
data/text/abilities.ts.

Neither @smogon/calc's own abilities.json dump (data/dump/abilities.json,
this project's main ability table) nor its Champions data anywhere carries
description text - it only records id/name, since a damage calculator has
no mechanical need for prose. Showdown's separate data/text/ tree exists
purely for exactly this: id -> {name, shortDesc, desc, ...}. Ability ids
there already match this project's own to_id() convention directly (e.g.
"Sand Stream" -> "sandstream"), unlike species/sprite/Pokekipe slugs
elsewhere in data/generate_*.py, so no fuzzy fallback matching is needed
here.

shortDesc is preferred over the longer desc (matches the concise,
tooltip-style text shown in-game); a handful of abilities only have desc,
so that's the fallback. Restricted to ability ids present in this dex's
own 200-entry Champions table - same handling as generate_ability_slots.py
excluding Battle Bond.

Run from poke_calc/ (with the venv active) after any dex refresh:
    python -m poke_calc.data.generate_ability_descriptions
"""

from __future__ import annotations

import json
import re
import urllib.request
from pathlib import Path

from poke_calc.data.loader import load_dex

ABILITIES_TEXT_URL = "https://raw.githubusercontent.com/smogon/pokemon-showdown/master/data/text/abilities.ts"
OUT_PATH = Path(__file__).parent / "dump" / "ability_descriptions.json"

_BLOCK_RE = re.compile(r"^\t([a-z0-9]+): \{\n(.*?)\n\t\},\n", re.MULTILINE | re.DOTALL)
_SHORT_DESC_RE = re.compile(r'\n\t\tshortDesc: "((?:[^"\\]|\\.)*)"')
_DESC_RE = re.compile(r'\n\t\tdesc: "((?:[^"\\]|\\.)*)"')


def _fetch_source() -> str:
    req = urllib.request.Request(ABILITIES_TEXT_URL, headers={"User-Agent": "curl/8.0"})
    with urllib.request.urlopen(req, timeout=30) as resp:
        return resp.read().decode("utf-8")


def _parse_descriptions(text: str) -> dict[str, str]:
    result = {}
    for m in _BLOCK_RE.finditer(text):
        aid, body = m.group(1), m.group(2)
        dm = _SHORT_DESC_RE.search(body) or _DESC_RE.search(body)
        if dm:
            result[aid] = dm.group(1).replace('\\"', '"')
    return result


def main():
    descriptions = _parse_descriptions(_fetch_source())
    dex = load_dex()

    result = {aid: descriptions.get(aid) for aid in dex.abilities}
    OUT_PATH.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")

    missing = [aid for aid, desc in result.items() if desc is None]
    print(f"resolved {len(result) - len(missing)}/{len(result)}; wrote {OUT_PATH}")
    if missing:
        print(f"no description found for: {missing}")


if __name__ == "__main__":
    main()
