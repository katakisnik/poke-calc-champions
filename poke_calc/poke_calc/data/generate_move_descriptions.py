"""Regenerates data/dump/move_descriptions.json - a full human-readable
description for each move, sourced from Showdown's base data/text/moves.ts.

Same rationale and pattern as generate_ability_descriptions.py: neither
@smogon/calc's own moves.json dump (data/dump/moves.json, this project's
main move table) nor its Champions data anywhere carries description text -
it only records the mechanical fields (type, category, base power, flags,
...) a damage calculator actually needs. Showdown's separate data/text/
tree exists purely to supply prose: id -> {name, shortDesc, desc, ...}.

Unlike generate_ability_descriptions.py (which prefers the concise
shortDesc, matching an in-game ability tooltip), this generator prefers the
longer `desc` field, per request for each move's "full description" -
falling back to shortDesc only for the handful of moves that don't have
one. Note `desc` for a move with no secondary effect is often just "No
additional effect." (e.g. Accelerock) even though its shortDesc separately
calls out a real mechanical property (priority, in that example) - that's
a genuine Showdown convention (desc = additional-effects text, shortDesc =
tooltip summary), not a data gap here.

Move ids in moves.ts already match this project's own to_id() convention
directly (e.g. "Sand Storm" -> "sandstorm"), same as abilities - no fuzzy
fallback matching needed.

Run from poke_calc/ (with the venv active) after any dex refresh:
    python -m poke_calc.data.generate_move_descriptions
"""

from __future__ import annotations

import json
import re
import urllib.request
from pathlib import Path

from poke_calc.data.loader import load_dex

MOVES_TEXT_URL = "https://raw.githubusercontent.com/smogon/pokemon-showdown/master/data/text/moves.ts"
OUT_PATH = Path(__file__).parent / "dump" / "move_descriptions.json"

_BLOCK_RE = re.compile(r'^\t"?([a-z0-9]+)"?: \{\n(.*?)\n\t\},\n', re.MULTILINE | re.DOTALL)
_DESC_RE = re.compile(r'\n\t\tdesc: "((?:[^"\\]|\\.)*)"')
_SHORT_DESC_RE = re.compile(r'\n\t\tshortDesc: "((?:[^"\\]|\\.)*)"')


def _fetch_source() -> str:
    req = urllib.request.Request(MOVES_TEXT_URL, headers={"User-Agent": "curl/8.0"})
    with urllib.request.urlopen(req, timeout=30) as resp:
        return resp.read().decode("utf-8")


def _parse_descriptions(text: str) -> dict[str, str]:
    result = {}
    for m in _BLOCK_RE.finditer(text):
        mid, body = m.group(1), m.group(2)
        dm = _DESC_RE.search(body) or _SHORT_DESC_RE.search(body)
        if dm:
            result[mid] = dm.group(1).replace('\\"', '"')
    return result


def main():
    descriptions = _parse_descriptions(_fetch_source())
    dex = load_dex()

    result = {mid: descriptions.get(mid) for mid in dex.moves}
    OUT_PATH.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")

    missing = [mid for mid, desc in result.items() if desc is None]
    print(f"resolved {len(result) - len(missing)}/{len(result)}; wrote {OUT_PATH}")
    if missing:
        print(f"no description found for: {missing}")


if __name__ == "__main__":
    main()
