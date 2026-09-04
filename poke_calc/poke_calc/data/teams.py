"""Saved team presets - a user-built roster of reusable Pokemon builds
(species/nature/ability/item/SP spread), persisted to data/teams.json.

Unlike everything under data/dump/, this file is NOT baked from an
external source by a generate_*.py script - it's mutable app state the
running UI writes itself whenever you save or delete a preset. That's why
it lives as a sibling of dump/ rather than inside it, and why there's
nothing about it in NOTICE (no external data, nothing to attribute).

A preset intentionally captures only build IDENTITY - species, nature,
ability, item, SP spread - not battle-transient state (stat stage boosts,
status, current HP), matching how a real teambuilder "set" is scoped and
matching exactly what ui/app.py's render_mon_panel() already treats as
"the build" vs. "battle state" in its returned dict.

A "team" is a free-form named list of presets you build up over time - by
request, there's no cap on team size or preset count (unlike Champions'
own real "bring 6" team-size rule).

This file is tiny (a handful of teams/presets for one local user), so
there's no caching layer here unlike the large, baked Dex (cached via
st.cache_resource) - every read/write just goes straight to disk.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Optional

TEAMS_PATH = Path(__file__).parent / "teams.json"


@dataclass
class Preset:
    label: str  # user-given name, e.g. "Scarf Chomp" - distinct from species
    species: str
    nature: str
    ability: str
    item: Optional[str]
    sp: dict[str, int] = field(default_factory=dict)


def load_teams() -> dict[str, list[Preset]]:
    """Missing file -> no saved teams yet, not an error."""
    if not TEAMS_PATH.exists():
        return {}
    raw = json.loads(TEAMS_PATH.read_text())
    return {
        team_name: [Preset(**preset) for preset in presets]
        for team_name, presets in raw.items()
    }


def save_teams(teams: dict[str, list[Preset]]) -> None:
    raw = {
        team_name: [asdict(preset) for preset in presets]
        for team_name, presets in teams.items()
    }
    TEAMS_PATH.write_text(json.dumps(raw, indent=2))


def add_preset(teams: dict[str, list[Preset]], team_name: str, preset: Preset) -> dict[str, list[Preset]]:
    """Appends `preset` to `team_name`, creating that team if it doesn't
    exist yet. Returns a new dict rather than mutating `teams` in place."""
    updated = dict(teams)
    updated[team_name] = [*updated.get(team_name, []), preset]
    return updated


def delete_preset(teams: dict[str, list[Preset]], team_name: str, index: int) -> dict[str, list[Preset]]:
    """Removes the preset at `index` from `team_name`. Leaves the (now
    possibly empty) team in place - deleting the last preset in a team
    does not implicitly delete the team; use delete_team for that."""
    updated = dict(teams)
    presets = list(updated[team_name])
    del presets[index]
    updated[team_name] = presets
    return updated


def delete_team(teams: dict[str, list[Preset]], team_name: str) -> dict[str, list[Preset]]:
    updated = dict(teams)
    del updated[team_name]
    return updated
