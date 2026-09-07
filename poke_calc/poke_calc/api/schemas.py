"""Pydantic request/response models for poke_calc.api.

These mirror shapes that already exist in engine/data as closely as
possible - MonBuildIn's fields are exactly build_mon()'s kwargs,
FieldIn/SideIn mirror engine.models.FieldState/Side field-for-field - no
new shapes are invented here beyond what's needed to carry them over
JSON. See the migration plan's "Backend" section for the reasoning.
"""

from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, Field

from poke_calc.engine.models import BOOSTABLE_STATS
from poke_calc.data.teams import Preset


# --- shared build/field shapes, used by both /calculate and /calculate/batch ---

class MonBuildIn(BaseModel):
    species: str
    ability: Optional[str] = None
    item: Optional[str] = None
    nature: Optional[str] = None
    sp: dict[str, int] = Field(default_factory=dict)
    boosts: dict[str, int] = Field(default_factory=dict)
    status: Optional[str] = None
    current_hp_fraction: float = 1.0

    def to_build_kwargs(self) -> dict:
        return {
            "species": self.species,
            "ability": self.ability,
            "item": self.item,
            "nature": self.nature,
            "sp": self.sp,
            "boosts": {**{s: 0 for s in BOOSTABLE_STATS}, **self.boosts},
            "status": self.status,
            "current_hp_fraction": self.current_hp_fraction,
        }


class SideIn(BaseModel):
    side_conditions: list[str] = Field(default_factory=list)
    is_protected: bool = False
    is_helping_hand: bool = False


class FieldIn(BaseModel):
    game_type: str = "Singles"
    weather: Optional[str] = None
    terrain: Optional[str] = None
    is_gravity: bool = False
    attacker_side: SideIn = Field(default_factory=SideIn)
    defender_side: SideIn = Field(default_factory=SideIn)


# --- /api/calculate ---

class CalculateRequest(BaseModel):
    attacker: MonBuildIn
    defender: MonBuildIn
    move_name: str
    field: FieldIn = Field(default_factory=FieldIn)


class KoChanceEntry(BaseModel):
    hits: int
    probability: float


class CalculateResponse(BaseModel):
    rolls: list[int]
    attacker_speed: int
    defender_speed: int
    defender_max_hp: int  # needed client-side for "% of max HP" - stat math (calc_stat) only lives in the engine
    ko_chances: list[KoChanceEntry]


# --- /api/speed ---
# A separate, move-independent endpoint: effective_speed() doesn't need a
# move at all, and the UI shows "who moves first" before either side has
# picked one (see ui/app.py's render_speed_comparison(), called ahead of
# render_matchup()) - bundling speed only into /api/calculate would force
# a move selection just to see it.

class SpeedRequest(BaseModel):
    attacker: MonBuildIn
    defender: MonBuildIn
    field: FieldIn = Field(default_factory=FieldIn)


class SpeedResponse(BaseModel):
    attacker_speed: int
    defender_speed: int


# --- /api/calculate/batch ---

class BatchCalculateRequest(BaseModel):
    attacker: MonBuildIn
    defender: MonBuildIn
    move_names: list[str]
    field: FieldIn = Field(default_factory=FieldIn)


class MoveSummaryRow(BaseModel):
    move: str
    type: str
    category: str
    base_power: int
    avg_damage_pct: float
    ko_chances: list[KoChanceEntry]


class BatchCalculateResponse(BaseModel):
    rows: list[MoveSummaryRow]


# --- /api/teams ---

class PresetIn(BaseModel):
    label: str
    species: str
    nature: str
    ability: str
    item: Optional[str] = None
    sp: dict[str, int] = Field(default_factory=dict)

    def to_preset(self) -> Preset:
        return Preset(
            label=self.label, species=self.species, nature=self.nature,
            ability=self.ability, item=self.item, sp=self.sp,
        )


class TeamsResponse(BaseModel):
    teams: dict[str, list[PresetIn]]


# --- /api/bootstrap ---

class SpeciesOut(BaseModel):
    id: str
    name: str
    types: list[str]
    base_stats: dict[str, int]
    ability: str
    weight_kg: float
    base_species: Optional[str] = None
    is_mega: bool
    sprite_url: Optional[str] = None
    ability_slots: list[str]  # ability names this species can actually have
    learnable_moves: list[str]  # move ids, per Dex.learnable_moves()
    mega_stone: Optional[str] = None  # item name that turns THIS forme's base into it
    suggested_nature: str
    suggested_sp: dict[str, int]
    suggested_item: Optional[str] = None


class MoveOut(BaseModel):
    id: str
    name: str
    type: str
    category: str
    base_power: int
    priority: int
    target: str
    flags: dict[str, int]
    multihit: Optional[list[int]] = None
    has_secondary: bool
    drain: Optional[list[int]] = None
    recoil: float
    breaks_protect: bool
    will_crit: bool
    crit_ratio: int
    description: Optional[str] = None
    is_status: bool
    is_spread: bool


class ItemOut(BaseModel):
    id: str
    name: str
    is_mega_stone: bool
    is_berry: bool
    legal_in_reg_m_a: bool


class AbilityOut(BaseModel):
    id: str
    name: str
    description: Optional[str] = None


class NatureOut(BaseModel):
    name: str
    plus: Optional[str] = None
    minus: Optional[str] = None
    is_neutral: bool


class BootstrapResponse(BaseModel):
    species: list[SpeciesOut]
    moves: list[MoveOut]
    items: list[ItemOut]
    abilities: list[AbilityOut]
    natures: list[NatureOut]
    regulations: list[str]
    sp_budget: int
    sp_max: int
    weathers: list[str]
    terrains: list[str]
    statuses: list[str]
    type_chart: dict[str, dict[str, float]]
