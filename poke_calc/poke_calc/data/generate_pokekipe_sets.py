"""Regenerates data/dump/pokekipe_sets.json - the most-used real Doubles
ladder nature + SP spread + held item per species, from Pokekipe's free
public API (https://pokekipe.com, see /api/v1/formats and
/api/v1/pokemon/{name}/{format_id} in its OpenAPI spec at
https://pokekipe.com/openapi.json).

This is fetched once and baked into a local JSON snapshot rather than
called live from the running UI: Streamlit reruns the whole script on
every widget interaction, so a live per-species call would mean hundreds
of requests to someone else's free API per session - baking a snapshot
here (like data/generate_sprite_ids.py and data/generate_learnsets.py
already do) is both far faster for the app and more respectful of their
service.

Doubles only, from Champions VGC 2026 Reg M-B (gen9championsvgc2026regmb,
the biggest doubles/VGC format - 1.7M+ battles/month at the time of
writing) - by request, this project's suggested set is always the Doubles
ladder spread regardless of the Singles/Doubles toggle in the UI (an
earlier version also fetched Champions OU for a Singles-specific
suggestion; that was dropped).

Confirmed by direct API inspection (not assumed):
- Species slugs are the display name lowercased with hyphens kept as-is
  (e.g. "Tauros-Paldea-Aqua" -> "tauros-paldea-aqua") - a DIFFERENT
  convention from both our own to_id() and Showdown's sprite filenames.
- `tolerate_missing=true` returns a bare JSON `null` (not a 404) when a
  species has no recorded data in that format - common for niche/new
  Mega formes.
- The `spreads` list is already sorted by usage descending; each entry's
  `spread` field is "Nature:hp/atk/def/spa/spd/spe" already in the SAME
  0-32 SP scale this project uses internally - no EV conversion needed.
- The `items` list is also usage-sorted, and its `name` fields are already
  in this project's own to_id() convention (e.g. "lifeorb", "choicescarf") -
  no slug remapping needed, unlike species. Taken as-is: the single top
  entry, skipping any id this dex doesn't have (Pokekipe's own item stats
  aren't restricted to Champions' legal pool, and its own item ids don't
  care about a species being a Mega forme, so e.g. a Mega forme's top item
  is just always its own Mega Stone at near-100% usage - harmless, since
  the UI already hardcodes the Mega Stone for Mega formes regardless of
  this field). Whether the suggested item is legal under the currently
  selected Regulation is the UI's job, not this snapshot's - see
  ui/app.py's fallback-to-"(none)" handling.

Run from poke_calc/ (with the venv active) after any dex refresh, or
periodically to pick up ladder shifts:
    python -m poke_calc.data.generate_pokekipe_sets
"""

from __future__ import annotations

import json
import re
import time
import urllib.error
import urllib.request
from pathlib import Path

from poke_calc.data.loader import STAT_NAMES, load_dex, to_id

BASE_URL = "https://pokekipe.com/api/v1/pokemon"
FORMAT_ID = "gen9championsvgc2026regmb"
OUT_PATH = Path(__file__).parent / "dump" / "pokekipe_sets.json"
REQUEST_DELAY_SECONDS = 0.3
MAX_RETRIES = 5

_SPREAD_RE = re.compile(r"^([A-Za-z]+):(\d+)/(\d+)/(\d+)/(\d+)/(\d+)/(\d+)$")


def _slug(species_name: str) -> str:
    return species_name.lower().replace(" ", "-")


def _fetch_json(url: str):
    """Retries with exponential backoff on HTTP 429 - the free API rate-
    limits fairly aggressively (confirmed: a run at the original 0.1s
    delay and no retries started getting 429s partway through and would
    have silently REGRESSED this snapshot's coverage from a prior 145/324
    down to 112/324 if trusted as "no data"). A 429 must never be treated
    the same as a genuine no-data 404/null - that's a transient rate limit,
    not a statement about the species."""
    req = urllib.request.Request(url, headers={"User-Agent": "curl/8.0"})
    for attempt in range(MAX_RETRIES):
        try:
            with urllib.request.urlopen(req, timeout=15) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            if e.code == 429 and attempt < MAX_RETRIES - 1:
                time.sleep(2 ** attempt)
                continue
            raise


def _top_spread(payload: dict) -> tuple[str, dict[str, int]] | None:
    spreads = payload.get("spreads") or []
    if not spreads:
        return None
    m = _SPREAD_RE.match(spreads[0]["spread"])
    if not m:
        return None
    nature = m.group(1)
    values = [int(x) for x in m.group(2, 3, 4, 5, 6, 7)]
    sp = dict(zip(STAT_NAMES, values))
    if any(v < 0 or v > 32 for v in sp.values()) or sum(sp.values()) > 66:
        return None  # sanity check - don't trust a malformed entry
    return nature, sp


def _top_item(payload: dict, dex) -> str | None:
    for entry in payload.get("items") or []:
        iid = to_id(entry["name"])
        if iid in dex.items:
            return iid
    return None


def main():
    dex = load_dex()
    result: dict[str, dict | None] = {}

    total = len(dex.species)
    for done, (sid, species) in enumerate(dex.species.items(), start=1):
        url = f"{BASE_URL}/{_slug(species.name)}/{FORMAT_ID}?tolerate_missing=true"
        try:
            payload = _fetch_json(url)
        except urllib.error.HTTPError as e:
            print(f"  {species.name}: HTTP {e.code}, treating as no data")
            payload = None
        top = _top_spread(payload) if payload else None
        item = _top_item(payload, dex) if payload else None
        result[sid] = {"nature": top[0], "sp": top[1], "item": item} if top else None
        time.sleep(REQUEST_DELAY_SECONDS)
        if done % 40 == 0:
            print(f"  ...{done}/{total} requests done")

    OUT_PATH.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    with_data = sum(1 for v in result.values() if v)
    with_item = sum(1 for v in result.values() if v and v.get("item"))
    print(f"wrote {OUT_PATH}: {with_data}/{len(result)} species have Doubles ladder data "
          f"({with_item}/{with_data} of those also resolved a top item)")


if __name__ == "__main__":
    main()
