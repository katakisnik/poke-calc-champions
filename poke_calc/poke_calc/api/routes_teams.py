"""/api/teams - saved team presets CRUD. Thin wrapper over
data/teams.py's load_teams/save_teams/add_preset/delete_preset/
delete_team - the only bit of logic added here (not in data/teams.py
itself) is the same-build duplicate guard the Streamlit UI enforced
(same species/nature/ability/item/sp counts as a duplicate regardless of
label) - that was UI-layer validation, not part of teams.py's own
contract, so it belongs here rather than in data/teams.py.
"""

from __future__ import annotations

from dataclasses import asdict

from fastapi import APIRouter, HTTPException

from poke_calc.data.teams import delete_preset, delete_team, load_teams, save_teams, add_preset
from poke_calc.api.schemas import PresetIn, TeamsResponse

router = APIRouter()


def _teams_response() -> TeamsResponse:
    teams = load_teams()
    return TeamsResponse(teams={name: [PresetIn(**asdict(p)) for p in presets] for name, presets in teams.items()})


@router.get("", response_model=TeamsResponse)
def get_teams() -> TeamsResponse:
    return _teams_response()


@router.put("/{team_name}/presets", response_model=TeamsResponse)
def put_preset(team_name: str, preset_in: PresetIn) -> TeamsResponse:
    teams = load_teams()
    new_preset = preset_in.to_preset()
    build_fields = (new_preset.species, new_preset.nature, new_preset.ability, new_preset.item, new_preset.sp)
    is_duplicate = any(
        (p.species, p.nature, p.ability, p.item, p.sp) == build_fields
        for p in teams.get(team_name, [])
    )
    if is_duplicate:
        raise HTTPException(
            status_code=409,
            detail=f"'{team_name}' already has this exact build saved "
                    "(label doesn't matter - same species/nature/ability/item/SP counts as a duplicate).",
        )
    save_teams(add_preset(teams, team_name, new_preset))
    return _teams_response()


@router.delete("/{team_name}/presets/{index}", response_model=TeamsResponse)
def delete_preset_route(team_name: str, index: int) -> TeamsResponse:
    teams = load_teams()
    if team_name not in teams:
        raise HTTPException(status_code=404, detail=f"no team named '{team_name}'")
    if not (0 <= index < len(teams[team_name])):
        raise HTTPException(status_code=404, detail=f"no preset at index {index} in '{team_name}'")
    save_teams(delete_preset(teams, team_name, index))
    return _teams_response()


@router.delete("/{team_name}", response_model=TeamsResponse)
def delete_team_route(team_name: str) -> TeamsResponse:
    teams = load_teams()
    if team_name not in teams:
        raise HTTPException(status_code=404, detail=f"no team named '{team_name}'")
    save_teams(delete_team(teams, team_name))
    return _teams_response()
