"""POST /api/calculate and /api/calculate/batch - the only two routes
that actually need a round trip, since everything else resolves from the
bootstrap payload client-side. Thin wrappers only: calculate()/ko_chance()/
moves_summary()/effective_speed() are the same functions the Streamlit UI
called (poke_calc.engine.build/ko_chance) - no game logic lives here.
"""

from __future__ import annotations

import re

from fastapi import APIRouter, Depends, HTTPException

from poke_calc.data.loader import Dex, load_dex
from poke_calc.engine.build import build_mon, calculate, effective_speed
from poke_calc.engine.ko_chance import ko_chance, moves_summary
from poke_calc.engine.models import FieldState, Side
from poke_calc.api.schemas import (
    BatchCalculateRequest,
    BatchCalculateResponse,
    CalculateRequest,
    CalculateResponse,
    FieldIn,
    KoChanceEntry,
    MoveSummaryRow,
    SpeedRequest,
    SpeedResponse,
)

router = APIRouter()

_HKO_COLUMN_RE = re.compile(r"^(\d+)HKO %$")


def get_dex() -> Dex:
    return load_dex()


def _to_field_state(field_in: FieldIn) -> FieldState:
    return FieldState(
        game_type=field_in.game_type,
        weather=field_in.weather,
        terrain=field_in.terrain,
        is_gravity=field_in.is_gravity,
        attacker_side=Side(
            side_conditions=set(field_in.attacker_side.side_conditions),
            is_protected=field_in.attacker_side.is_protected,
            is_helping_hand=field_in.attacker_side.is_helping_hand,
        ),
        defender_side=Side(
            side_conditions=set(field_in.defender_side.side_conditions),
            is_protected=field_in.defender_side.is_protected,
            is_helping_hand=field_in.defender_side.is_helping_hand,
        ),
    )


def _ko_chance_entries(chances: dict[int, float]) -> list[KoChanceEntry]:
    return [KoChanceEntry(hits=hits, probability=prob) for hits, prob in chances.items()]


def _hko_column_to_hits(column: str) -> int:
    if column == "OHKO %":
        return 1
    m = _HKO_COLUMN_RE.match(column)
    if not m:
        raise ValueError(f"unrecognized KO-chance column: {column!r}")
    return int(m.group(1))


@router.post("/calculate", response_model=CalculateResponse)
def post_calculate(req: CalculateRequest, dex: Dex = Depends(get_dex)) -> CalculateResponse:
    attacker_kwargs = req.attacker.to_build_kwargs()
    defender_kwargs = req.defender.to_build_kwargs()
    field = _to_field_state(req.field)

    try:
        rolls = calculate(dex, attacker_kwargs, defender_kwargs, req.move_name, field=field)
        chances = ko_chance(dex, attacker_kwargs, defender_kwargs, req.move_name, field=field)
        attacker_mon = build_mon(dex, **attacker_kwargs, field=field)
        defender_mon = build_mon(dex, **defender_kwargs, field=field)
    except (KeyError, ValueError) as e:
        raise HTTPException(status_code=400, detail=str(e)) from None

    return CalculateResponse(
        rolls=rolls,
        attacker_speed=effective_speed(attacker_mon, field),
        defender_speed=effective_speed(defender_mon, field),
        defender_max_hp=defender_mon.stats["hp"],
        ko_chances=_ko_chance_entries(chances),
    )


@router.post("/speed", response_model=SpeedResponse)
def post_speed(req: SpeedRequest, dex: Dex = Depends(get_dex)) -> SpeedResponse:
    field = _to_field_state(req.field)
    try:
        attacker_mon = build_mon(dex, **req.attacker.to_build_kwargs(), field=field)
        defender_mon = build_mon(dex, **req.defender.to_build_kwargs(), field=field)
    except (KeyError, ValueError) as e:
        raise HTTPException(status_code=400, detail=str(e)) from None

    return SpeedResponse(
        attacker_speed=effective_speed(attacker_mon, field),
        defender_speed=effective_speed(defender_mon, field),
    )


@router.post("/calculate/batch", response_model=BatchCalculateResponse)
def post_calculate_batch(req: BatchCalculateRequest, dex: Dex = Depends(get_dex)) -> BatchCalculateResponse:
    attacker_kwargs = req.attacker.to_build_kwargs()
    defender_kwargs = req.defender.to_build_kwargs()
    field = _to_field_state(req.field)

    try:
        raw_rows = moves_summary(dex, attacker_kwargs, defender_kwargs, req.move_names, field=field)
    except (KeyError, ValueError) as e:
        raise HTTPException(status_code=400, detail=str(e)) from None

    rows = []
    for raw in raw_rows:
        ko_chances = [
            KoChanceEntry(hits=_hko_column_to_hits(col), probability=raw[col])
            for col in raw
            if col in ("OHKO %",) or _HKO_COLUMN_RE.match(col)
        ]
        rows.append(MoveSummaryRow(
            move=raw["Move"], type=raw["Type"], category=raw["Category"], base_power=raw["BP"],
            avg_damage_pct=raw["Avg Dmg %"], ko_chances=ko_chances,
        ))
    return BatchCalculateResponse(rows=rows)
