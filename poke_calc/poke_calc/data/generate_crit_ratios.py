"""Regenerates data/dump/crit_ratios.json - each move's own static crit
ratio (1 = base rate, 2 = "high crit ratio" moves like Night Slash/Stone
Edge, 3 = the rare few higher than that), sourced from Showdown's base
data/moves.ts.

Neither @smogon/calc's own moves.json dump (data/dump/moves.json, this
project's main move table) nor its Champions data anywhere carries a crit
ratio - confirmed by grep, zero `critRatio` keys in that dump. Showdown's
mechanics file data/moves.ts (NOT the data/text/ tree generate_move_
descriptions.py already uses - that one is prose-only) carries a static
critRatio field for exactly the moves whose crit chance differs from the
base rate; absent means the base rate (1), same as this project already
defaults move.crit_ratio to 1 in loader.py.

Only the STATIC per-move field is captured here. Showdown's moves.ts also
defines DYNAMIC crit-ratio boosts as onModifyCritRatio handlers - most
importantly Focus Energy's own move effect (+2 stages to the user's next
attacks) - which need cross-move battle-log state (whether Focus Energy
was used earlier this battle) that this stateless, single-hit calculator
doesn't track. Same category of deliberate, documented gap as Aqua Step's
dance counter or Alluring Voice's "raised this turn" condition in
engine/damage.py's module docstring - see engine/ko_chance.py and NOTICE.

Move ids in moves.ts already match this project's own to_id() convention
directly, same as data/text/moves.ts - no fuzzy fallback matching needed.

Run from poke_calc/ (with the venv active) after any dex refresh:
    python -m poke_calc.data.generate_crit_ratios
"""

from __future__ import annotations

import json
import re
import urllib.request
from pathlib import Path

from poke_calc.data.loader import load_dex

MOVES_MECHANICS_URL = "https://raw.githubusercontent.com/smogon/pokemon-showdown/master/data/moves.ts"
OUT_PATH = Path(__file__).parent / "dump" / "crit_ratios.json"

_BLOCK_RE = re.compile(r'^\t"?([a-z0-9]+)"?: \{\n(.*?)\n\t\},\n', re.MULTILINE | re.DOTALL)
_CRIT_RATIO_RE = re.compile(r"\n\t\tcritRatio: (\d+),")


def _fetch_source() -> str:
    req = urllib.request.Request(MOVES_MECHANICS_URL, headers={"User-Agent": "curl/8.0"})
    with urllib.request.urlopen(req, timeout=30) as resp:
        return resp.read().decode("utf-8")


def _parse_crit_ratios(text: str) -> dict[str, int]:
    result = {}
    for m in _BLOCK_RE.finditer(text):
        mid, body = m.group(1), m.group(2)
        cm = _CRIT_RATIO_RE.search(body)
        if cm:
            result[mid] = int(cm.group(1))
    return result


def main():
    crit_ratios = _parse_crit_ratios(_fetch_source())
    dex = load_dex()

    # Absent from moves.ts means the base rate (1) - not a gap, the same
    # default loader.py's MoveData.crit_ratio already falls back to.
    result = {mid: crit_ratios.get(mid, 1) for mid in dex.moves}
    OUT_PATH.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")

    boosted = {mid: ratio for mid, ratio in result.items() if ratio > 1}
    print(f"wrote {OUT_PATH}: {len(boosted)}/{len(result)} moves have a boosted crit ratio")


if __name__ == "__main__":
    main()
