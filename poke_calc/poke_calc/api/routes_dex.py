"""GET /api/bootstrap - the entire static dex, fetched once by the
frontend. Every interactive concern that doesn't need the damage math
itself (species/move/ability/item pickers, learnset filtering, ability
slots, sprites, type badges, base stats, regulation legality, suggested
sets) resolves client-side from this single payload - see the migration
plan's "Backend" section.

Purely a translation layer: every field here comes straight from
data/loader.py's Dex or a function in engine/, nothing computed here that
doesn't already exist. Cached for the process lifetime the same way
load_dex() itself is - this is static data, built once.
"""

from __future__ import annotations

from functools import lru_cache

from fastapi import APIRouter

from poke_calc.data.loader import load_dex
from poke_calc.data.regulations import is_item_legal
from poke_calc.engine.models import STATUSES, TERRAINS, WEATHERS
from poke_calc.engine.stats import SP_BUDGET, SP_MAX
from poke_calc.engine.suggestions import suggest_nature_and_sp
from poke_calc.api.schemas import (
    AbilityOut,
    BootstrapResponse,
    ItemOut,
    MoveOut,
    NatureOut,
    SpeciesOut,
)

router = APIRouter()


def _species_out(dex, species) -> SpeciesOut:
    ladder = dex.ladder_set(species.name)
    if ladder is not None:
        suggested_nature, suggested_sp, suggested_item = ladder
    else:
        suggested_nature, suggested_sp = suggest_nature_and_sp(species.base_stats)
        suggested_item = None

    mega_stone = dex.mega_stone_for(species.name)

    return SpeciesOut(
        id=species.id,
        name=species.name,
        types=list(species.types),
        base_stats=species.base_stats,
        ability=species.ability,
        weight_kg=species.weight_kg,
        base_species=species.base_species,
        is_mega=species.is_mega,
        sprite_url=species.sprite_url,
        ability_slots=[a.name for a in dex.ability_slots(species.name)],
        learnable_moves=list(dex.learnable_moves(species.name).keys()),
        mega_stone=mega_stone.name if mega_stone else None,
        suggested_nature=suggested_nature,
        suggested_sp=suggested_sp,
        suggested_item=suggested_item,
    )


def _move_out(move) -> MoveOut:
    return MoveOut(
        id=move.id,
        name=move.name,
        type=move.type,
        category=move.category,
        base_power=move.base_power,
        priority=move.priority,
        target=move.target,
        flags=move.flags,
        multihit=list(move.multihit) if move.multihit else None,
        has_secondary=move.has_secondary,
        drain=list(move.drain) if move.drain else None,
        recoil=move.recoil,
        breaks_protect=move.breaks_protect,
        will_crit=move.will_crit,
        crit_ratio=move.crit_ratio,
        description=move.description,
        is_status=move.is_status,
        is_spread=move.is_spread,
    )


def _item_out(item) -> ItemOut:
    return ItemOut(
        id=item.id,
        name=item.name,
        is_mega_stone=item.is_mega_stone,
        is_berry=item.is_berry,
        legal_in_reg_m_a=is_item_legal(item.id, "M-A"),
    )


@lru_cache(maxsize=1)
def _build_bootstrap() -> BootstrapResponse:
    dex = load_dex()
    return BootstrapResponse(
        species=[_species_out(dex, s) for s in dex.species.values()],
        moves=[_move_out(m) for m in dex.moves.values()],
        items=[_item_out(i) for i in dex.items.values()],
        abilities=[AbilityOut(id=a.id, name=a.name, description=a.description) for a in dex.abilities.values()],
        natures=[
            NatureOut(name=n.name, plus=n.plus, minus=n.minus, is_neutral=n.is_neutral)
            for n in dex.natures.values()
        ],
        regulations=["M-A", "M-B"],
        sp_budget=SP_BUDGET,
        sp_max=SP_MAX,
        weathers=list(WEATHERS),
        terrains=list(TERRAINS),
        statuses=list(STATUSES),
        type_chart=dex.type_chart,
    )


@router.get("/bootstrap", response_model=BootstrapResponse)
def get_bootstrap() -> BootstrapResponse:
    return _build_bootstrap()
