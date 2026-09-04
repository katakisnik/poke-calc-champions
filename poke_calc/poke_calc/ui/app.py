"""Pokemon Champions damage calculator - Streamlit UI.

Run from the poke_calc/poke_calc directory (with the project's venv
active - `pip install -e .` makes data/engine/ui importable as ordinary
packages, see pyproject.toml):
    streamlit run poke_calc/ui/app.py

Purely a UI layer: all game logic lives in engine/ and data/, already
validated independently (see tests/). This file only builds widgets,
collects kwargs, and calls engine.build.calculate.

If a running server ever throws an AttributeError/ImportError for a
name that plainly exists in the source (e.g. after a code update),
that's a stale process, not a real bug: Streamlit's autoreload re-runs
THIS file on a change, but doesn't reload already-imported submodules
(data.loader, engine.*) still cached in that process's memory. Fully
stop the server (Ctrl+C) and run `streamlit run` again rather than
trusting the auto-rerun.
"""

from __future__ import annotations

from typing import Optional

import streamlit as st

from poke_calc.data.loader import STAT_NAMES, load_dex, to_id
from poke_calc.data.regulations import REGULATIONS, is_item_legal, legal_items
from poke_calc.data.teams import Preset, add_preset, delete_preset, delete_team, load_teams, save_teams
from poke_calc.engine.build import build_mon, build_move, calculate, effective_speed
from poke_calc.engine.ko_chance import ko_chance
from poke_calc.engine.models import BOOSTABLE_STATS, FieldState, Side
from poke_calc.engine.stats import SP_BUDGET, SP_MAX
from poke_calc.engine.suggestions import suggest_nature_and_sp

STAT_LABELS = {"hp": "HP", "atk": "Atk", "def": "Def", "spa": "SpA", "spd": "SpD", "spe": "Spe"}

# What each field condition actually does - not all of it is damage-relevant
# (this is a single-hit calculator, not a turn-by-turn simulator), so
# per-turn effects that this engine doesn't compute (residual chip damage,
# Grassy Terrain's healing, terrain's 5-turn duration) are called out as
# such rather than left implied. See engine/damage.py for exactly which
# parts ARE modeled (weather/terrain type-power boosts and cuts, the
# listed ability interactions, Solar Beam/Blade's charge-turn exemption).
WEATHER_INFO = {
    "Sun": "Fire-type moves deal 1.5x damage, Water-type moves deal 0.5x. Solar Beam/Solar Blade skip "
           "their charge turn (Sun is their OWN good weather, so they're never halved either). Powers "
           "Chlorophyll (2x Speed) and Solar Power (1.5x Sp. Atk, but the holder loses 1/8 max HP each "
           "turn - not simulated here).",
    "Rain": "Water-type moves deal 1.5x damage, Fire-type moves deal 0.5x. Thunder and Hurricane never "
            "miss. Powers Swift Swim (2x Speed).",
    "Sand": "Rock-types get a 1.5x Sp. Def boost. Non-Rock/Ground/Steel types lose 1/16 max HP each turn "
            "(not simulated here). Powers Sand Rush (2x Speed) and Sand Force (1.3x power for Rock/Ground/"
            "Steel moves).",
    "Snow": "Ice-types get a 1.5x Defense boost. Non-Ice types lose 1/16 max HP each turn (not simulated "
            "here). Powers Slush Rush (2x Speed).",
}
TERRAIN_INFO = {
    "Electric": "Electric-type moves get a 1.3x power boost from a grounded attacker. Grounded Pokemon "
                "can't fall asleep. Powers Surge Surfer (2x Speed). Only affects grounded Pokemon; lasts "
                "5 turns (duration not tracked here).",
    "Grassy": "Grass-type moves get a 1.3x power boost from a grounded attacker, and deal half damage "
              "from Earthquake/Bulldoze/Magnitude against a grounded defender. Grounded Pokemon heal "
              "1/16 max HP each turn (not simulated here). Only affects grounded Pokemon; lasts 5 turns "
              "(duration not tracked here).",
    "Misty": "Dragon-type moves deal half damage against a grounded defender. Grounded Pokemon can't be "
             "inflicted with a major status condition. Only affects grounded Pokemon; lasts 5 turns "
             "(duration not tracked here).",
    "Psychic": "Psychic-type moves get a 1.3x power boost from a grounded attacker. Grounded Pokemon are "
               "protected from moves with increased priority. Only affects grounded Pokemon; lasts 5 "
               "turns (duration not tracked here).",
}

# Base stats are shown as bars against the series-wide 0-255 scale (the
# same fixed reference Bulbapedia/Serebii-style stat displays use), so bar
# length reflects absolute quality rather than being relative to just this
# one Pokemon's own other stats. Color bands follow that same convention.
BASE_STAT_MAX = 255
STAT_COLOR_BANDS = (
    (30, "#ff4d4d"),   # red - very poor
    (60, "#ff9f40"),   # orange - poor
    (90, "#ffd700"),   # yellow - average
    (120, "#9bd63c"),  # yellow-green - good
    (150, "#3fd63f"),  # green - great
    (180, "#2fd6c8"),  # cyan - excellent
    (255, "#4d8dff"),  # blue - exceptional
)


def _stat_color(value: int) -> str:
    for threshold, color in STAT_COLOR_BANDS:
        if value < threshold:
            return color
    return STAT_COLOR_BANDS[-1][1]


def render_base_stats(base_stats: dict) -> None:
    rows = []
    for stat in STAT_NAMES:
        value = base_stats[stat]
        pct = min(value / BASE_STAT_MAX, 1.0) * 100
        color = _stat_color(value)
        rows.append(
            f'<div style="display:flex;align-items:center;gap:8px;margin:2px 0;">'
            f'<span style="width:34px;font-size:0.8em;opacity:0.75;">{STAT_LABELS[stat]}</span>'
            f'<div style="flex:1;background:rgba(128,128,128,0.25);border-radius:4px;height:10px;overflow:hidden;">'
            f'<div style="width:{pct:.1f}%;background:{color};height:100%;"></div>'
            f'</div>'
            f'<span style="width:28px;text-align:right;font-size:0.8em;font-weight:600;">{value}</span>'
            f'</div>'
        )
    st.markdown('<div style="margin-bottom:8px;">' + "".join(rows) + "</div>", unsafe_allow_html=True)


# The classic per-type colors used across the games/Bulbapedia/Serebii -
# rendered as rounded pill badges rather than plain text.
TYPE_COLORS = {
    "Normal": "#A8A878", "Fire": "#F08030", "Water": "#6890F0", "Electric": "#F8D030",
    "Grass": "#78C850", "Ice": "#98D8D8", "Fighting": "#C03028", "Poison": "#A040A0",
    "Ground": "#E0C068", "Flying": "#A890F0", "Psychic": "#F85888", "Bug": "#A8B820",
    "Rock": "#B8A038", "Ghost": "#705898", "Dragon": "#7038F8", "Dark": "#705848",
    "Steel": "#B8B8D0", "Fairy": "#EE99AC",
}

# A plain st.selectbox can only ever show flat, single-line text per
# option - no grouped/disabled headers, no colored badge images like
# TYPE_COLORS renders elsewhere (BaseWeb's Select doesn't parse HTML in
# option labels). Emoji are the closest thing to a per-type "image" that
# CAN render inside one, so they stand in for the real type badges here.
MOVE_TYPE_EMOJI = {
    "Normal": "⚪", "Fire": "🔥", "Water": "💧", "Electric": "⚡", "Grass": "🌿",
    "Ice": "❄️", "Fighting": "🥊", "Poison": "☠️", "Ground": "🟤", "Flying": "🌪️",
    "Psychic": "🔮", "Bug": "🐛", "Rock": "🪨", "Ghost": "👻", "Dragon": "🐲",
    "Dark": "🌑", "Steel": "⚙️", "Fairy": "✨",
}
MOVE_HEADER_PREFIX = "── "  # marks a header row; see move_dropdown_options()


def type_badge_html(type_name: str) -> str:
    color = TYPE_COLORS.get(type_name, "#777777")
    return (
        f'<span style="display:inline-block;padding:3px 12px;margin-right:6px;'
        f'border-radius:12px;background:{color};color:#fff;font-weight:700;'
        f'font-size:0.78em;letter-spacing:0.03em;text-transform:uppercase;'
        f'text-shadow:0 1px 1px rgba(0,0,0,0.35);'
        f'box-shadow:0 1px 3px rgba(0,0,0,0.35);">{type_name}</span>'
    )


def render_type_badges(types: tuple) -> None:
    st.markdown(
        '<div style="margin:2px 0 8px 0;">' + "".join(type_badge_html(t) for t in types) + "</div>",
        unsafe_allow_html=True,
    )


ABILITY_DESC_LINES = 3  # fixed-height box so a longer/shorter description on one
                        # side doesn't push its column's SP/boost widgets out of
                        # vertical alignment with the other side's


def render_ability_description(description: Optional[str]) -> None:
    text = description or ""
    st.markdown(
        f'<div style="height:{ABILITY_DESC_LINES * 1.3:.1f}em;overflow:hidden;'
        f'display:-webkit-box;-webkit-line-clamp:{ABILITY_DESC_LINES};'
        f'-webkit-box-orient:vertical;font-size:0.8em;opacity:0.75;'
        f'line-height:1.3em;margin-bottom:4px;">{text}</div>',
        unsafe_allow_html=True,
    )


SPRITE_BOX_SIZE = 140  # fixed footprint so every sprite reads as the same size,
                       # regardless of how tall/wide its own source image is


def render_sprite(sprite_url: str) -> None:
    # st.image(width=...) only pins width - height still follows each GIF's
    # own aspect ratio, so a tall sprite (e.g. Wailord) renders visibly
    # bigger than a small one (e.g. Diglett) even at the "same" width. A
    # fixed-size box with object-fit: contain gives every sprite an
    # identical footprint instead.
    st.markdown(
        f'<div style="width:{SPRITE_BOX_SIZE}px;height:{SPRITE_BOX_SIZE}px;'
        f'display:flex;align-items:center;justify-content:center;">'
        f'<img src="{sprite_url}" style="max-width:100%;max-height:100%;'
        f'object-fit:contain;" /></div>',
        unsafe_allow_html=True,
    )


st.set_page_config(page_title="Champions Damage Calc", layout="wide")


@st.cache_resource
def get_dex():
    return load_dex()


def species_options(dex):
    return sorted(s.name for s in dex.species.values())


_TYPE_ORDER = {t: i for i, t in enumerate(TYPE_COLORS)}  # canonical type order, same as TYPE_COLORS/type badges


def move_options(dex, species_name: str) -> list[str]:
    """Every move the species can learn (damaging AND Status - by
    request, this used to filter Status moves out, but a Status move is
    still a real, pickable move whose info/description is worth seeing
    even though it deals no direct damage - see render_matchup()'s
    handling of that), sorted by TYPE (canonical order, same as the type
    badges elsewhere in this UI) and then name within each type -
    grouping same-typed moves together reads better in the dropdown than
    a flat alphabetical list, by request."""
    moves = list(dex.learnable_moves(species_name).values())
    moves.sort(key=lambda m: (_TYPE_ORDER.get(m.type, len(_TYPE_ORDER)), m.name))
    return [m.name for m in moves]


def move_dropdown_options(dex, species_name: str) -> list[str]:
    """move_options(), with a non-selectable-in-spirit header entry (e.g.
    "── Fire ──") inserted before each type's first move - the closest
    approximation of a real grouped/labelled dropdown a plain
    st.selectbox can offer. Paired with format_move_option() (adds a
    per-type emoji to real moves) and render_matchup()'s handling of a
    header actually getting selected (treated the same as picking
    nothing, same as "(none)")."""
    options: list[str] = []
    last_type = None
    for name in move_options(dex, species_name):
        move_type = dex.get_move(name).type
        if move_type != last_type:
            options.append(f"{MOVE_HEADER_PREFIX}{move_type} ──")
            last_type = move_type
        options.append(name)
    return options


def format_move_option(dex, option: str) -> str:
    if option == "(none)" or option.startswith(MOVE_HEADER_PREFIX):
        return option
    emoji = MOVE_TYPE_EMOJI.get(dex.get_move(option).type, "")
    return f"{emoji} {option}" if emoji else option


def nature_options(dex):
    return sorted(dex.natures.keys())


def item_options(dex, regulation):
    return ["(none)"] + sorted(i.name for i in legal_items(dex, regulation).values())


def ability_options(dex, species_name: str):
    return sorted(a.name for a in dex.ability_slots(species_name))


def render_mon_panel(dex, side_label: str, regulation: str, default_species: str, key: str) -> dict | None:
    st.subheader(side_label)

    # Must run BEFORE the Species/Nature/Ability/Item/SP widgets below -
    # same "session_state before the widget's first appearance this run"
    # trick the ladder-suggestion block further down already relies on.
    saved_teams = load_teams()
    with st.expander("📋 Load from a saved team"):
        if not saved_teams:
            st.caption("No saved teams yet - build a set below, then save it at the bottom of this panel.")
        else:
            team_name = st.selectbox("Team", sorted(saved_teams), key=f"{key}_load_team")
            team_presets = saved_teams[team_name]
            preset_label = st.selectbox(
                "Preset", [p.label for p in team_presets], key=f"{key}_load_preset",
            )
            if st.button("Load", key=f"{key}_load_btn"):
                preset = next(p for p in team_presets if p.label == preset_label)
                st.session_state[f"{key}_species"] = preset.species
                st.session_state[f"{key}_nature"] = preset.nature
                st.session_state[f"{key}_ability"] = preset.ability
                st.session_state[f"{key}_item"] = preset.item or "(none)"
                for stat in STAT_NAMES:
                    st.session_state[f"{key}_sp_{stat}"] = preset.sp.get(stat, 0)
                # Stop the ladder-suggestion block below from immediately
                # overwriting this load with a fresh suggestion on this
                # same rerun (it only re-fires when species *changes*).
                st.session_state[f"{key}_suggested_for"] = preset.species

    # Streamlit warns (correctly) if a widget's `index=`/`value=` default is
    # passed on every run AND its session_state is also set elsewhere (the
    # Load button above does exactly that) - `setdefault` seeds the ONE-TIME
    # initial value the same way the ladder-suggestion/Load logic already
    # seeds nature/ability/item/SP, so the widget below takes no default arg
    # of its own at all.
    st.session_state.setdefault(f"{key}_species", default_species)

    img_col, select_col = st.columns([1, 3])
    with select_col:
        species = st.selectbox("Species", species_options(dex), key=f"{key}_species")
    species_rec = dex.get_species(species)
    with img_col:
        if species_rec.sprite_url:
            render_sprite(species_rec.sprite_url)
    render_type_badges(species_rec.types)
    render_base_stats(species_rec.base_stats)

    # Re-suggest a nature + SP spread whenever the species changes (but
    # not on every rerun - a manual tweak sticks until you pick a
    # different species). Must run BEFORE the nature/SP widgets below,
    # since Streamlit only reads a widget's *initial* value/index the
    # first time its key appears - after that, session_state is what's
    # shown, so this is how a "default" gets changed programmatically.
    # The suggestion is always from the Doubles (VGC) ladder, regardless
    # of the Singles/Doubles toggle elsewhere in the UI - by request.
    suggested_for_key = f"{key}_suggested_for"
    if st.session_state.get(suggested_for_key) != species:
        ladder = dex.ladder_set(species)
        if ladder is not None:
            suggested_nature, suggested_sp, suggested_item = ladder
        else:
            suggested_nature, suggested_sp = suggest_nature_and_sp(species_rec.base_stats)
            suggested_item = None
        st.session_state[f"{key}_nature"] = suggested_nature
        for stat in STAT_NAMES:
            st.session_state[f"{key}_sp_{stat}"] = suggested_sp[stat]
        # Mega formes hardcode their own Mega Stone below regardless of
        # this widget's value (see the `mega_stone` branch further down) -
        # leave `{key}_item` untouched for them rather than suggesting
        # something that widget can't even offer as an option. For
        # everyone else, fall back to "(none)" if the suggestion isn't
        # legal under the CURRENT Regulation - a later manual Regulation
        # switch isn't re-checked here (this block only re-fires on a
        # species change), matching how a manually-picked item is likewise
        # left alone on a Regulation switch elsewhere in this function.
        if not species_rec.is_mega:
            if suggested_item and is_item_legal(to_id(suggested_item), regulation):
                st.session_state[f"{key}_item"] = suggested_item
            else:
                st.session_state[f"{key}_item"] = "(none)"
        # Same "seed session_state, don't pass a competing index=" pattern
        # for ability - it used to be seeded via index=abilities.index(...)
        # on the widget itself instead, but that conflicts with the Load
        # button also writing this same key via the Session State API
        # (Streamlit warns loudly about a widget default + a session_state
        # write both applying to one key in the same run).
        species_abilities = ability_options(dex, species)
        st.session_state[f"{key}_ability"] = (
            species_rec.ability if species_rec.ability in species_abilities else species_abilities[0]
        )
        st.session_state[suggested_for_key] = species

    col1, col2 = st.columns(2)
    with col1:
        nature = st.selectbox("Nature", nature_options(dex), key=f"{key}_nature")
        nature_rec = dex.get_nature(nature)
        if nature_rec.is_neutral:
            st.caption("Neutral - no stat boost/cut")
        else:
            st.caption(f"+{STAT_LABELS[nature_rec.plus]} / -{STAT_LABELS[nature_rec.minus]}")
        abilities = ability_options(dex, species)
        ability = st.selectbox("Ability", abilities, key=f"{key}_ability")
        render_ability_description(dex.get_ability(ability).description)
    with col2:
        mega_stone = dex.mega_stone_for(species) if species_rec.is_mega else None
        item_valid = True
        if mega_stone is not None:
            # A Mega forme can only be holding the stone that turned it
            # into that forme in the first place - no other item is a
            # physically valid choice.
            st.selectbox("Item", [mega_stone.name], key=f"{key}_item", disabled=True)
            item = mega_stone.name
            if not is_item_legal(mega_stone.id, regulation):
                st.error(f"{mega_stone.name} isn't legal under Regulation {regulation} - this Mega can't be used here.")
                item_valid = False
        else:
            items = item_options(dex, regulation)
            item_choice = st.selectbox("Item", items, key=f"{key}_item")
            item = None if item_choice == "(none)" else item_choice
        status = st.selectbox("Status", ["(none)", "Burn", "Paralysis", "Poison", "Badly Poisoned", "Sleep", "Freeze"], key=f"{key}_status")
        status_map = {"(none)": None, "Burn": "brn", "Paralysis": "par", "Poison": "psn", "Badly Poisoned": "tox", "Sleep": "slp", "Freeze": "frz"}

    st.caption("Stat Points (0-32 each, 66 total)")
    sp = {}
    sp_cols = st.columns(6)
    for i, stat in enumerate(STAT_NAMES):
        with sp_cols[i]:
            sp[stat] = st.number_input(STAT_LABELS[stat], min_value=0, max_value=SP_MAX, step=1, key=f"{key}_sp_{stat}")
    total_sp = sum(sp.values())
    remaining = SP_BUDGET - total_sp
    if total_sp > SP_BUDGET:
        st.error(f"SP total {total_sp} exceeds the {SP_BUDGET}-point budget by {total_sp - SP_BUDGET}.")
        sp_valid = False
    else:
        st.progress(total_sp / SP_BUDGET, text=f"{total_sp}/{SP_BUDGET} SP used ({remaining} remaining)")
        sp_valid = True

    st.caption("Stat stage boosts (-6 to +6)")
    boosts = {}
    boost_cols = st.columns(5)
    for i, stat in enumerate(BOOSTABLE_STATS):
        with boost_cols[i]:
            boosts[stat] = st.slider(STAT_LABELS[stat], min_value=-6, max_value=6, value=0, key=f"{key}_boost_{stat}")

    with st.expander("💾 Save this build to a team"):
        team_choice = st.selectbox(
            "Team", ["+ New team"] + sorted(saved_teams), key=f"{key}_save_team_choice",
        )
        team_name_input = (
            st.text_input("New team name", key=f"{key}_save_new_team_name")
            if team_choice == "+ New team" else team_choice
        )
        preset_label_input = st.text_input("Preset name", value=species, key=f"{key}_save_preset_label")
        if st.button("Save", key=f"{key}_save_btn"):
            team_name_input = team_name_input.strip()
            if not team_name_input:
                st.error("Enter a team name first.")
            else:
                # Only species/nature/ability/item/SP are saved - boosts
                # and status are battle-transient, not part of a build's
                # identity (see teams.py's module docstring).
                new_preset = Preset(
                    label=preset_label_input.strip() or species, species=species, nature=nature,
                    ability=ability, item=item, sp=dict(sp),
                )
                build_fields = (new_preset.species, new_preset.nature, new_preset.ability, new_preset.item, new_preset.sp)
                is_duplicate = any(
                    (p.species, p.nature, p.ability, p.item, p.sp) == build_fields
                    for p in saved_teams.get(team_name_input, [])
                )
                if is_duplicate:
                    st.error(f"'{team_name_input}' already has this exact build saved (label doesn't matter - "
                             f"same species/nature/ability/item/SP counts as a duplicate).")
                else:
                    save_teams(add_preset(saved_teams, team_name_input, new_preset))
                    # st.toast (not st.success) because a plain inline
                    # element written here wouldn't survive the
                    # st.rerun() below - and the rerun itself is needed
                    # so the "Team" selectbox above (already rendered
                    # earlier THIS run, from the `saved_teams` snapshot
                    # loaded before this save happened) picks up the
                    # newly-saved team immediately rather than on some
                    # later, unrelated interaction.
                    st.toast(f"Saved '{new_preset.label}' to '{team_name_input}'.")
                    st.rerun()

    if not sp_valid or not item_valid:
        return None
    return {
        "species": species,
        "nature": nature,
        "ability": ability,
        "item": item,
        "sp": sp,
        "boosts": boosts,
        "status": status_map[status],
        "current_hp_fraction": 1.0,  # always full HP - no in-battle HP tracking in this calculator
    }


KO_ORDINAL_LABELS = {1: "OHKO", 2: "2HKO", 3: "3HKO", 4: "4HKO", 5: "5HKO"}


def render_ko_chance(dex, attacker_kwargs, defender_kwargs, move_name: str, field: FieldState) -> None:
    """Cumulative P(KO'd within N hits) per hit count, via
    engine.ko_chance - the real answer a "2HKO to 3HKO" range only
    gestures at. See ko_chance()'s own docstring for exactly what is and
    isn't modeled (same-move-every-turn, full HP, no Focus Energy, ...).
    Only the last-shown hit count can ever be the ~100% one - ko_chance()
    itself stops computing further hits once it's reached - so bolding
    whichever entry hits that threshold needs no extra bookkeeping here."""
    chances = ko_chance(dex, attacker_kwargs, defender_kwargs, move_name, field=field)
    last_hit_count = max(chances)
    parts = []
    for hit_count, prob in chances.items():
        label = KO_ORDINAL_LABELS.get(hit_count, f"{hit_count}-hit KO")
        if hit_count == last_hit_count and prob < 0.9999:
            label += "+"  # not even guaranteed within the hits shown
        text = f"{label} {prob:.0%}"
        parts.append(f"**{text}**" if prob >= 0.9999 else text)
    st.caption(" · ".join(parts))


MOVE_FLAG_LABELS = {
    "contact": "Contact",
    "bullet": "Bullet",
    "bite": "Bite",
    "pulse": "Pulse",
    "punch": "Punch",
    "slicing": "Slicing",
    "sound": "Sound",
    "wind": "Wind",
}


def render_move_info(move) -> None:
    st.markdown(type_badge_html(move.type), unsafe_allow_html=True)
    parts = [move.category, f"{move.base_power} BP" if move.base_power else "– BP"]
    if move.priority:
        parts.append(f"Priority {move.priority:+d}")
    if move.target == "allAdjacent":
        parts.append("Hits all adjacent Pokemon")
    elif move.target == "allAdjacentFoes":
        parts.append("Hits both foes")
    parts.extend(MOVE_FLAG_LABELS[flag] for flag in move.flags if flag in MOVE_FLAG_LABELS)
    if move.multihit:
        lo, hi = move.multihit
        parts.append("Hits twice" if (lo, hi) == (2, 2) else f"Hits {lo}-{hi} times")
    if move.drain:
        num, den = move.drain
        parts.append(f"Drains {num}/{den} of damage dealt")
    if move.recoil:
        parts.append(f"Recoil {move.recoil:.0%} of damage dealt")
    if move.will_crit:
        parts.append("Always a critical hit")
    if move.breaks_protect:
        parts.append("Bypasses Protect")
    if move.has_secondary:
        parts.append("Has a secondary effect")
    st.caption(" · ".join(parts))
    if move.description:
        st.caption(move.description)


def render_speed_comparison(dex, a_kwargs: dict, b_kwargs: dict, field: FieldState) -> None:
    """Who moves first - current (stage-boosted, item/ability/weather/
    paralysis-adjusted) Speed, not base Speed. Doesn't factor in move
    priority - that's shown per-move in render_move_info() instead, since
    it depends on which move is picked, not just the two Pokemon."""
    a_mon = build_mon(dex, **a_kwargs, field=field)
    b_mon = build_mon(dex, **b_kwargs, field=field)
    a_speed = effective_speed(a_mon, field)
    b_speed = effective_speed(b_mon, field)

    col_a, col_mid, col_b = st.columns([2, 1, 2])
    with col_a:
        st.metric("Pokémon A Speed", a_speed)
    with col_b:
        st.metric("Pokémon B Speed", b_speed)
    with col_mid:
        if a_speed == b_speed:
            st.caption("Speed tie - coin flip for who moves first")
        else:
            faster, diff = ("A", a_speed - b_speed) if a_speed > b_speed else ("B", b_speed - a_speed)
            st.caption(f"Pokémon {faster} moves first (+{diff} Speed)")


def render_matchup(dex, attacker_kwargs, defender_kwargs, field: FieldState, direction: str):
    st.markdown(f"#### {direction}")
    defender_mon = build_mon(dex, **defender_kwargs, field=field)
    defender_hp = defender_mon.stats["hp"]

    dropdown_options = move_dropdown_options(dex, attacker_kwargs["species"])
    move_name = st.selectbox(
        "Move", ["(none)"] + dropdown_options, key=f"{direction}_move",
        format_func=lambda opt: format_move_option(dex, opt),
    )
    if move_name == "(none)" or move_name.startswith(MOVE_HEADER_PREFIX):
        return
    move_data = dex.get_move(move_name)
    render_move_info(move_data)
    if move_data.is_status:
        # A Status move deals no direct damage - calculate_damage()
        # itself already returns [0]*16 for these (a real, correct early
        # return, not a bug), but showing "0-0, OHKO 0%" for e.g. Swords
        # Dance or Protect would just be misleading clutter. Its info/
        # description above (already category-agnostic) is the useful
        # part for a Status move.
        return
    try:
        rolls = calculate(dex, attacker_kwargs, defender_kwargs, move_name, field=field)
    except Exception as e:  # noqa: BLE001
        st.error(f"{e}")
        return
    lo, hi = min(rolls), max(rolls)
    pct_lo, pct_hi = lo / defender_hp * 100, hi / defender_hp * 100
    st.metric(move_name, f"{lo}-{hi}", f"{pct_lo:.1f}-{pct_hi:.1f}% of max HP")
    render_ko_chance(dex, attacker_kwargs, defender_kwargs, move_name, field)


def main():
    st.title("Pokémon Champions Damage Calculator")

    dex = get_dex()

    with st.sidebar:
        st.header("Field")
        regulation = st.selectbox("Regulation", REGULATIONS, index=1)
        game_type = st.radio("Format", ["Singles", "Doubles"], horizontal=True)
        # help= renders as a small hover-over "?" icon next to the label
        # rather than a caption taking up its own line. It needs to know
        # the CURRENTLY selected option before the widget call returns it
        # - reading last run's value back from session_state works because
        # Streamlit updates a widget's session_state entry for a change
        # BEFORE rerunning the script, so this already reflects the new
        # selection on the very rerun that made it.
        weather = st.selectbox(
            "Weather", ["(none)", "Sun", "Rain", "Sand", "Snow"], key="weather",
            help=WEATHER_INFO.get(st.session_state.get("weather", "(none)")),
        )
        terrain = st.selectbox(
            "Terrain", ["(none)", "Electric", "Grassy", "Misty", "Psychic"], key="terrain",
            help=TERRAIN_INFO.get(st.session_state.get("terrain", "(none)")),
        )
        is_gravity = st.checkbox("Gravity")

        st.divider()
        st.caption("Side A")
        a_helping_hand = st.checkbox("A: Helping Hand active", key="a_hh")
        a_protected = st.checkbox("A: Protected", key="a_prot")
        a_reflect = st.checkbox("A: Reflect", key="a_reflect")
        a_light_screen = st.checkbox("A: Light Screen", key="a_ls")
        a_aurora_veil = st.checkbox("A: Aurora Veil", key="a_av")

        st.caption("Side B")
        b_helping_hand = st.checkbox("B: Helping Hand active", key="b_hh")
        b_protected = st.checkbox("B: Protected", key="b_prot")
        b_reflect = st.checkbox("B: Reflect", key="b_reflect")
        b_light_screen = st.checkbox("B: Light Screen", key="b_ls")
        b_aurora_veil = st.checkbox("B: Aurora Veil", key="b_av")

        st.divider()
        with st.expander("Manage Teams"):
            saved_teams_for_management = load_teams()
            if not saved_teams_for_management:
                st.caption("No saved teams yet.")
            for team_name in sorted(saved_teams_for_management):
                st.caption(f"**{team_name}**")
                for i, preset in enumerate(saved_teams_for_management[team_name]):
                    row_label_col, row_delete_col = st.columns([4, 1])
                    with row_label_col:
                        st.write(f"{preset.label} ({preset.species})")
                    with row_delete_col:
                        if st.button("🗑", key=f"del_preset_{team_name}_{i}"):
                            save_teams(delete_preset(saved_teams_for_management, team_name, i))
                            st.rerun()
                if st.button(f"Delete team \"{team_name}\"", key=f"del_team_{team_name}"):
                    save_teams(delete_team(saved_teams_for_management, team_name))
                    st.rerun()

    side_a = Side(
        is_protected=a_protected,
        is_helping_hand=a_helping_hand,
        side_conditions={
            *(["reflect"] if a_reflect else []),
            *(["lightscreen"] if a_light_screen else []),
            *(["auroraveil"] if a_aurora_veil else []),
        },
    )
    side_b = Side(
        is_protected=b_protected,
        is_helping_hand=b_helping_hand,
        side_conditions={
            *(["reflect"] if b_reflect else []),
            *(["lightscreen"] if b_light_screen else []),
            *(["auroraveil"] if b_aurora_veil else []),
        },
    )

    col_a, col_b = st.columns(2)
    with col_a:
        a_kwargs = render_mon_panel(dex, "Pokémon A", regulation, "Garchomp", "a")
    with col_b:
        b_kwargs = render_mon_panel(dex, "Pokémon B", regulation, "Tyranitar", "b")

    st.divider()

    if a_kwargs is None or b_kwargs is None:
        st.warning("Fix the error(s) above (SP budget or an illegal Mega Stone) to see damage results.")
        return

    field_a_to_b = FieldState(
        game_type=game_type, weather=None if weather == "(none)" else weather,
        terrain=None if terrain == "(none)" else terrain, is_gravity=is_gravity,
        attacker_side=side_a, defender_side=side_b,
    )
    field_b_to_a = FieldState(
        game_type=game_type, weather=None if weather == "(none)" else weather,
        terrain=None if terrain == "(none)" else terrain, is_gravity=is_gravity,
        attacker_side=side_b, defender_side=side_a,
    )

    render_speed_comparison(dex, a_kwargs, b_kwargs, field_a_to_b)
    st.divider()

    render_matchup(dex, a_kwargs, b_kwargs, field_a_to_b, "A attacks B")
    st.divider()
    render_matchup(dex, b_kwargs, a_kwargs, field_b_to_a, "B attacks A")


if __name__ == "__main__":
    main()
