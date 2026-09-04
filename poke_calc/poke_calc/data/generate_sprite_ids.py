"""Regenerates data/dump/sprite_ids.json - maps each Champions dex species
id to its filename (sans extension) in Showdown's sprites/ani/ CDN
(https://play.pokemonshowdown.com/sprites/ani/{id}.gif), a community sprite
set that (unlike sprites/dex/) has full coverage of Champions' newer Mega
formes (confirmed: 324/324 resolved as of this writing).

Showdown's sprite filenames follow a DIFFERENT normalization than our own
to_id(): alternate formes are `{base_id}-{forme_suffix}` (e.g.
"tauros-paldeaaqua", "charizard-megax"), not our fully-collapsed id
("taurospaldeaaqua"). Species whose OWN name contains a hyphen that is NOT
a forme delimiter (e.g. "Kommo-o") instead use the plain collapsed id, and
a couple of species (e.g. Aegislash-Shield) have no dedicated art at all
and fall back to their base species' sprite. Hence the multi-candidate
fallback chain below rather than a single formula.

Run from poke_calc/ (with the venv active) after any dex refresh:
    python -m poke_calc.data.generate_sprite_ids
"""

from __future__ import annotations

import json
import re
import urllib.request
from pathlib import Path

from poke_calc.data.loader import Species, load_dex, to_id

SPRITE_LISTING_URL = "https://play.pokemonshowdown.com/sprites/ani/?sort=name"
OUT_PATH = Path(__file__).parent / "dump" / "sprite_ids.json"


def _fetch_available_ids() -> set[str]:
    # The server 403s Python's default urllib User-Agent.
    req = urllib.request.Request(SPRITE_LISTING_URL, headers={"User-Agent": "curl/8.0"})
    with urllib.request.urlopen(req) as resp:
        html = resp.read().decode("utf-8")
    return set(re.findall(r'href="\./([a-z0-9-]+)\.gif"', html))


def _candidates(species: Species) -> list[str]:
    out = []
    if "-" in species.name:
        base, forme = species.name.split("-", 1)
        out.append(f"{to_id(base)}-{to_id(forme)}")
    out.append(to_id(species.name))
    if species.base_species:
        out.append(to_id(species.base_species))
    if "-" in species.name:
        out.append(to_id(species.name.split("-")[0]))  # last resort: bare name prefix
    return out


def main():
    available = _fetch_available_ids()
    dex = load_dex()

    mapping: dict[str, str] = {}
    unresolved: list[str] = []
    for sid, species in dex.species.items():
        resolved = next((c for c in _candidates(species) if c in available), None)
        if resolved:
            mapping[sid] = resolved
        else:
            unresolved.append(species.name)

    OUT_PATH.write_text(json.dumps(mapping, indent=2, sort_keys=True) + "\n")
    print(f"resolved {len(mapping)}/{len(dex.species)}; wrote {OUT_PATH}")
    if unresolved:
        print(f"unresolved (no image available anywhere): {unresolved}")


if __name__ == "__main__":
    main()
