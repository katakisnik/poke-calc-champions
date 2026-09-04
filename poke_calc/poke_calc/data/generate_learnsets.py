"""Regenerates data/dump/learnsets.json - maps each Champions dex species
id to the set of move ids it can legally learn, sourced directly from
Showdown's data/mods/champions/learnsets.ts.

That file only has entries for 232 of our 324 dex species - Mega formes
(and a couple of cosmetic-only formes) are simply absent, since Mega
Evolution doesn't change what a Pokemon can learn in the real games (Mega
Charizard X learns everything Charizard does). Unlisted species fall back
to their `base_species`'s learnset; a final fallback strips to the bare
name prefix before the first hyphen for the handful of formes (e.g.
Aegislash-Shield) whose `base_species` field itself doesn't resolve to a
listed entry.

The `inherit: true` seen on exactly one entry (floetteeternal) is
Showdown's MOD-inheritance convention (Champions inheriting from
unmodified Gen 9 data for that species), not forme-inheritance - it does
not mean "copy some other Pokemon's learnset", so it needs no special
handling by this parser (the block's own `learnset: {...}` is already the
complete, additional, Champions-relevant move list; this project just
uses it as an offline snapshot of Champions' own confirmed movepool).

Run from poke_calc/ (with the venv active) after any dex refresh:
    python -m poke_calc.data.generate_learnsets
"""

from __future__ import annotations

import json
import re
import urllib.request
from pathlib import Path

from poke_calc.data.loader import load_dex, to_id

LEARNSETS_URL = "https://raw.githubusercontent.com/smogon/pokemon-showdown/master/data/mods/champions/learnsets.ts"
OUT_PATH = Path(__file__).parent / "dump" / "learnsets.json"

_BLOCK_RE = re.compile(r"^\t([a-z0-9]+): \{\n(.*?)\n\t\},\n", re.MULTILINE | re.DOTALL)
_MOVE_RE = re.compile(r"^\t\t\t([a-z0-9]+):", re.MULTILINE)


def _fetch_source() -> str:
    req = urllib.request.Request(LEARNSETS_URL, headers={"User-Agent": "curl/8.0"})
    with urllib.request.urlopen(req) as resp:
        return resp.read().decode("utf-8")


def _parse_blocks(text: str) -> dict[str, set[str]]:
    blocks = {}
    for m in _BLOCK_RE.finditer(text):
        sid, body = m.group(1), m.group(2)
        blocks[sid] = set(_MOVE_RE.findall(body))
    return blocks


def main():
    blocks = _parse_blocks(_fetch_source())
    dex = load_dex()

    learnsets: dict[str, list[str]] = {}
    unresolved: list[str] = []
    for sid, species in dex.species.items():
        if sid in blocks:
            learnsets[sid] = sorted(blocks[sid])
            continue
        if species.base_species and to_id(species.base_species) in blocks:
            learnsets[sid] = sorted(blocks[to_id(species.base_species)])
            continue
        prefix = to_id(species.name.split("-")[0])
        if "-" in species.name and prefix in blocks:
            learnsets[sid] = sorted(blocks[prefix])
            continue
        unresolved.append(species.name)

    OUT_PATH.write_text(json.dumps(learnsets, indent=2, sort_keys=True) + "\n")
    print(f"resolved {len(learnsets)}/{len(dex.species)}; wrote {OUT_PATH}")
    if unresolved:
        print(f"unresolved (no learnset found anywhere): {unresolved}")


if __name__ == "__main__":
    main()
