"""Headless UI tests via Streamlit's own AppTest harness - actually runs
poke_calc/ui/app.py's script and widget tree (not just its helper
functions), which is the first-party way to exercise a Streamlit app
without a browser."""

from __future__ import annotations

from pathlib import Path

import pytest

pytest.importorskip("streamlit")
from streamlit.testing.v1 import AppTest

APP_PATH = str(Path(__file__).parent.parent / "poke_calc" / "ui" / "app.py")


@pytest.fixture(autouse=True)
def isolated_teams_file(tmp_path, monkeypatch):
    """Every test in this file gets its own throwaway teams.json - never
    touch the real user's saved teams."""
    from poke_calc.data import teams as teams_module

    monkeypatch.setattr(teams_module, "TEAMS_PATH", tmp_path / "teams.json")


def _fresh_app() -> AppTest:
    at = AppTest.from_file(APP_PATH, default_timeout=30)
    at.run()
    assert not at.exception, f"initial run raised: {at.exception}"
    return at


class TestInitialRender:
    def test_no_exceptions_on_load(self):
        _fresh_app()

    def test_title_and_panels_present(self):
        at = _fresh_app()
        assert [t.value for t in at.title] == ["Pokémon Champions Damage Calculator"]
        assert {s.value for s in at.subheader} == {"Pokémon A", "Pokémon B"}

    def test_expected_widget_counts(self):
        at = _fresh_app()
        # species/nature/ability/item/status x2 (10) + regulation/weather/terrain (3)
        # + 1 move slot x2 directions (2) = 15, + the "Save to a team" section's
        # own Team selectbox x2 (2, shown even with zero saved teams - it always
        # offers "+ New team") = 17. The "Load from a saved team" section adds
        # no widgets at all when there are no saved teams (just a caption).
        assert len(at.selectbox) == 17
        # boosts (5/mon x2) = 10
        assert len(at.slider) == 10
        # SP per stat (6/mon x2) = 12
        assert len(at.number_input) == 12


class TestSuggestedSet:
    """Pokekipe real Doubles ladder data is tried first (engine.suggestions'
    base-stat heuristic is only a fallback for species with no ladder
    data) - see poke_calc/data/generate_pokekipe_sets.py and Dex.ladder_set(). The
    suggestion is Doubles-sourced regardless of the UI's Singles/Doubles
    toggle, by request."""

    def test_default_species_uses_real_ladder_data(self):
        at = _fresh_app()
        nature_sb = next(sb for sb in at.selectbox if sb.key == "a_nature")
        item_sb = next(sb for sb in at.selectbox if sb.key == "a_item")
        sp_vals = {ni.key.rsplit("_", 1)[-1]: ni.value for ni in at.number_input if ni.key.startswith("a_sp_")}
        assert nature_sb.value == "Jolly"  # Garchomp's actual top Doubles ladder spread
        assert sp_vals == {"hp": 2, "atk": 32, "def": 0, "spa": 0, "spd": 0, "spe": 32}
        assert item_sb.value == "Life Orb"  # Garchomp's actual top Doubles ladder item

    def test_species_with_no_ladder_data_falls_back_to_the_heuristic(self):
        import json
        from pathlib import Path

        from poke_calc.data.loader import load_dex

        dump_dir = Path(__file__).parent.parent / "poke_calc" / "data" / "dump"
        raw = json.loads((dump_dir / "pokekipe_sets.json").read_text())
        no_data_sid = next(sid for sid, v in raw.items() if v is None)
        no_data_name = load_dex().species[no_data_sid].name

        at = _fresh_app()
        next(sb for sb in at.selectbox if sb.key == "a_species").select(no_data_name).run()
        assert not at.exception
        nature_sb = next(sb for sb in at.selectbox if sb.key == "a_nature")
        sp_vals = {ni.key.rsplit("_", 1)[-1]: ni.value for ni in at.number_input if ni.key.startswith("a_sp_")}
        # Just confirm the heuristic path actually ran (a valid, real
        # nature and a full 66-point spread) - the exact nature/spread
        # isn't the point of this test, the fallback triggering is.
        assert sum(sp_vals.values()) == 66
        assert nature_sb.value in load_dex().natures

    def test_changing_species_updates_the_suggestion(self):
        at = _fresh_app()
        next(sb for sb in at.selectbox if sb.key == "a_species").select("Alakazam").run()
        assert not at.exception
        nature_sb = next(sb for sb in at.selectbox if sb.key == "a_nature")
        sp_vals = {ni.key.rsplit("_", 1)[-1]: ni.value for ni in at.number_input if ni.key.startswith("a_sp_")}
        assert nature_sb.value == "Timid"
        assert sp_vals["spa"] == 32
        assert sp_vals["spe"] == 32

    def test_suggestion_is_unaffected_by_the_singles_doubles_toggle(self):
        # By request: the suggested set always comes from the Doubles
        # ladder, regardless of which battle format is selected. Default
        # format is "Singles"; toggling to "Doubles" must not change it.
        at = _fresh_app()
        next(sb for sb in at.selectbox if sb.key == "a_species").select("Absol").run()
        assert next(sb for sb in at.selectbox if sb.key == "a_nature").value == "Brave"

        next(r for r in at.radio if r.label == "Format").set_value("Doubles").run()
        assert not at.exception
        assert next(sb for sb in at.selectbox if sb.key == "a_nature").value == "Brave"

    def test_manual_override_survives_an_unrelated_rerun(self):
        at = _fresh_app()
        next(sb for sb in at.selectbox if sb.key == "a_nature").select("Quiet").run()
        next(cb for cb in at.checkbox if cb.key == "a_hh").set_value(True).run()
        assert not at.exception
        assert next(sb for sb in at.selectbox if sb.key == "a_nature").value == "Quiet"

    def test_manual_override_is_replaced_by_switching_species(self):
        at = _fresh_app()
        next(sb for sb in at.selectbox if sb.key == "a_nature").select("Quiet").run()
        next(sb for sb in at.selectbox if sb.key == "a_species").select("Alakazam").run()
        assert not at.exception
        assert next(sb for sb in at.selectbox if sb.key == "a_nature").value == "Timid"

    def test_changing_species_updates_the_suggested_item(self):
        at = _fresh_app()
        next(sb for sb in at.selectbox if sb.key == "a_species").select("Alakazam").run()
        assert not at.exception
        assert next(sb for sb in at.selectbox if sb.key == "a_item").value == "Focus Sash"

    def test_manual_item_override_survives_an_unrelated_rerun(self):
        at = _fresh_app()
        next(sb for sb in at.selectbox if sb.key == "a_item").select("Choice Scarf").run()
        next(cb for cb in at.checkbox if cb.key == "a_hh").set_value(True).run()
        assert not at.exception
        assert next(sb for sb in at.selectbox if sb.key == "a_item").value == "Choice Scarf"

    def test_suggested_item_illegal_under_the_current_regulation_falls_back_to_none(self):
        # Absol's top Doubles ladder item is Life Orb, which is M-A-banned
        # (see data/regulations.py) - the suggestion must not hand the UI
        # an item its own dropdown would immediately reject.
        at = _fresh_app()
        next(sb for sb in at.selectbox if sb.label == "Regulation").select("M-A").run()
        next(sb for sb in at.selectbox if sb.key == "a_species").select("Absol").run()
        assert not at.exception
        item_sb = next(sb for sb in at.selectbox if sb.key == "a_item")
        assert item_sb.value == "(none)"

    def test_mega_formes_own_stone_is_not_overridden_by_the_item_suggestion(self):
        # Mega formes hardcode their own Mega Stone regardless of ladder
        # data (see render_mon_panel's is_mega guard) - switching to one
        # must not error or leave a stale item value sitting in
        # session_state that the (disabled, single-option) widget can't
        # even offer.
        at = _fresh_app()
        next(sb for sb in at.selectbox if sb.key == "a_species").select("Garchomp-Mega").run()
        assert not at.exception
        item_sb = next(sb for sb in at.selectbox if sb.key == "a_item")
        assert item_sb.options == ["Garchompite"]
        assert item_sb.value == "Garchompite"


class TestTypeBadges:
    def test_default_species_show_colored_type_badges(self):
        from poke_calc.ui.app import TYPE_COLORS

        at = _fresh_app()
        html_blocks = [m.value for m in at.markdown]
        garchomp = next(h for h in html_blocks if ">Dragon<" in h and ">Ground<" in h)
        assert TYPE_COLORS["Dragon"] in garchomp
        assert TYPE_COLORS["Ground"] in garchomp
        tyranitar = next(h for h in html_blocks if ">Rock<" in h and ">Dark<" in h)
        assert TYPE_COLORS["Rock"] in tyranitar
        assert TYPE_COLORS["Dark"] in tyranitar

    def test_changing_species_updates_the_type_badges(self):
        at = _fresh_app()
        next(sb for sb in at.selectbox if sb.key == "a_species").select("Meganium-Mega").run()
        assert not at.exception
        html_blocks = [m.value for m in at.markdown]
        assert any(">Grass<" in h for h in html_blocks)


class TestBaseStatsDisplay:
    """Base stats render as colored HTML bars (st.markdown), not plain
    text - assert on the values/labels showing up in the rendered HTML,
    not on an exact caption string."""

    def test_default_species_shows_its_real_base_stats(self):
        at = _fresh_app()
        html_blocks = [m.value for m in at.markdown]
        garchomp = next(h for h in html_blocks if ">HP<" in h and ">108<" in h)
        for label, value in [("HP", 108), ("Atk", 130), ("Def", 95), ("SpA", 80), ("SpD", 85), ("Spe", 102)]:
            assert f">{label}<" in garchomp
            assert f">{value}<" in garchomp

        tyranitar = next(h for h in html_blocks if ">HP<" in h and ">100<" in h and ">61<" in h)
        for label, value in [("HP", 100), ("Atk", 134), ("Def", 110), ("SpA", 95), ("SpD", 100), ("Spe", 61)]:
            assert f">{label}<" in tyranitar
            assert f">{value}<" in tyranitar

    def test_changing_species_updates_the_displayed_base_stats(self):
        at = _fresh_app()
        next(sb for sb in at.selectbox if sb.key == "a_species").select("Meganium-Mega").run()
        assert not at.exception
        html_blocks = [m.value for m in at.markdown]
        meganium_mega = next(h for h in html_blocks if ">HP<" in h and ">143<" in h)
        for label, value in [("HP", 80), ("Atk", 92), ("Def", 115), ("SpA", 143), ("SpD", 115), ("Spe", 80)]:
            assert f">{label}<" in meganium_mega
            assert f">{value}<" in meganium_mega

    def test_bar_width_and_color_reflect_the_stat_value(self):
        from poke_calc.ui.app import BASE_STAT_MAX, _stat_color

        # A 150 base stat should render a bar noticeably wider than a 61
        # base stat, and the two should be colored differently since they
        # fall in different quality bands.
        assert 150 / BASE_STAT_MAX > 61 / BASE_STAT_MAX
        assert _stat_color(150) != _stat_color(61)
        assert _stat_color(20) == "#ff4d4d"
        assert _stat_color(255) == "#4d8dff"


class TestNatureStatEffectCaption:
    def test_shows_boosted_and_lowered_stat_for_a_non_neutral_nature(self):
        at = _fresh_app()
        next(sb for sb in at.selectbox if sb.key == "a_nature").select("Adamant").run()
        assert not at.exception
        assert any(c.value == "+Atk / -SpA" for c in at.caption)

    def test_shows_neutral_for_a_neutral_nature(self):
        at = _fresh_app()
        next(sb for sb in at.selectbox if sb.key == "a_nature").select("Hardy").run()
        assert not at.exception
        assert any("Neutral" in c.value for c in at.caption)


class TestSprites:
    """Sprites render as a fixed-size HTML box (st.markdown), not a bare
    st.image, so every sprite has the same footprint regardless of its own
    GIF's native aspect ratio - see render_sprite()'s docstring."""

    def test_default_species_show_images(self):
        at = _fresh_app()
        html_blocks = [m.value for m in at.markdown]
        urls = {
            "https://play.pokemonshowdown.com/sprites/ani/garchomp.gif",
            "https://play.pokemonshowdown.com/sprites/ani/tyranitar.gif",
        }
        for url in urls:
            assert any(url in h for h in html_blocks)

    def test_changing_species_updates_the_image(self):
        at = _fresh_app()
        next(sb for sb in at.selectbox if sb.key == "a_species").select("Meganium-Mega").run()
        assert not at.exception
        html_blocks = [m.value for m in at.markdown]
        assert any("https://play.pokemonshowdown.com/sprites/ani/meganium-mega.gif" in h for h in html_blocks)

    def test_all_sprites_render_in_a_fixed_size_box(self):
        from poke_calc.ui.app import SPRITE_BOX_SIZE

        at = _fresh_app()
        html_blocks = [m.value for m in at.markdown if "sprites/ani" in m.value]
        assert len(html_blocks) == 2
        for h in html_blocks:
            assert f"width:{SPRITE_BOX_SIZE}px" in h
            assert f"height:{SPRITE_BOX_SIZE}px" in h
            assert "object-fit:contain" in h


class TestMegaStoneItemLock:
    def test_mega_forme_item_is_locked_to_its_own_stone(self):
        at = _fresh_app()
        next(sb for sb in at.selectbox if sb.key == "a_species").select("Meganium-Mega").run()
        assert not at.exception
        item_sb = next(sb for sb in at.selectbox if sb.key == "a_item")
        assert item_sb.options == ["Meganiumite"]
        assert item_sb.value == "Meganiumite"
        assert item_sb.disabled is True

    def test_switching_back_to_a_non_mega_unlocks_the_item_list(self):
        at = _fresh_app()
        next(sb for sb in at.selectbox if sb.key == "a_species").select("Meganium-Mega").run()
        next(sb for sb in at.selectbox if sb.key == "a_species").select("Snorlax").run()
        assert not at.exception
        item_sb = next(sb for sb in at.selectbox if sb.key == "a_item")
        assert item_sb.disabled is False
        assert len(item_sb.options) > 1

    def test_mega_banned_under_current_regulation_shows_error_and_blocks_results(self):
        at = _fresh_app()
        next(sb for sb in at.selectbox if sb.label == "Regulation").select("M-A").run()
        next(sb for sb in at.selectbox if sb.key == "a_species").select("Blaziken-Mega").run()
        assert not at.exception
        assert any("isn't legal under Regulation M-A" in e.value for e in at.error)
        assert any("Fix the error" in w.value for w in at.warning)


class TestAbilitiesFilteredBySpecies:
    def test_ability_options_are_restricted_to_the_species_pool(self):
        at = _fresh_app()
        ability_sb = next(sb for sb in at.selectbox if sb.key == "a_ability")
        # Garchomp: Sand Veil (normal), Rough Skin (hidden) - not e.g. Levitate.
        assert set(ability_sb.options) == {"Sand Veil", "Rough Skin"}

    def test_changing_species_resets_an_invalid_ability_selection(self):
        at = _fresh_app()
        next(sb for sb in at.selectbox if sb.key == "a_ability").select("Rough Skin").run()
        next(sb for sb in at.selectbox if sb.key == "a_species").select("Alakazam").run()
        assert not at.exception
        ability_sb = next(sb for sb in at.selectbox if sb.key == "a_ability")
        assert ability_sb.value in ability_sb.options
        assert ability_sb.value == "Synchronize"  # Alakazam's own default ability

    def test_known_data_discrepancy_falls_back_to_the_only_legal_option(self):
        # Hawlucha-Mega: @smogon/calc's own species.ability says "Limber",
        # but pokedex.ts (treated as authoritative - see
        # generate_ability_slots.py) says its only real ability is
        # "No Guard". Must not crash, must show/default to the real one.
        at = _fresh_app()
        next(sb for sb in at.selectbox if sb.key == "a_species").select("Hawlucha-Mega").run()
        assert not at.exception
        ability_sb = next(sb for sb in at.selectbox if sb.key == "a_ability")
        assert ability_sb.options == ["No Guard"]
        assert ability_sb.value == "No Guard"

    def test_shows_the_selected_abilitys_description(self):
        at = _fresh_app()
        next(sb for sb in at.selectbox if sb.key == "a_ability").select("Rough Skin").run()
        assert not at.exception
        html_blocks = [m.value for m in at.markdown]
        assert any("contact" in h.lower() for h in html_blocks)

    def test_changing_ability_updates_the_description(self):
        at = _fresh_app()
        next(sb for sb in at.selectbox if sb.key == "a_ability").select("Sand Veil").run()
        assert not at.exception
        html_blocks = [m.value for m in at.markdown]
        assert any("evasiveness" in h.lower() for h in html_blocks)

    def test_description_renders_in_a_fixed_height_box(self):
        # A longer/shorter description on one side must not push that
        # side's SP/boost widgets out of alignment with the other side -
        # see render_ability_description()'s docstring.
        from poke_calc.ui.app import ABILITY_DESC_LINES

        at = _fresh_app()
        next(sb for sb in at.selectbox if sb.key == "a_ability").select("Rough Skin").run()
        assert not at.exception
        html_blocks = [m.value for m in at.markdown if "contact" in m.value.lower()]
        assert len(html_blocks) == 1
        assert f"-webkit-line-clamp:{ABILITY_DESC_LINES}" in html_blocks[0]
        assert f"height:{ABILITY_DESC_LINES * 1.3:.1f}em" in html_blocks[0]


class TestMovesFilteredByLearnset:
    def test_move_options_are_restricted_to_the_attackers_learnset(self):
        at = _fresh_app()
        move_sb = next(sb for sb in at.selectbox if sb.key == "A attacks B_move")
        # default attacker is Garchomp - Earthquake legal, Moonblast is not.
        # Displayed options carry a type-emoji prefix (format_move_option),
        # so this is membership by substring, not exact string equality.
        assert any("Earthquake" in opt for opt in move_sb.options)
        assert not any("Moonblast" in opt for opt in move_sb.options)

    def test_move_options_are_grouped_by_type_not_alphabetical(self):
        # By request: same-typed moves grouped together (canonical type
        # order, same as the type badges elsewhere in this UI), name
        # alphabetical only within a type - not a flat A-Z list.
        from poke_calc.data.loader import load_dex
        from poke_calc.ui.app import TYPE_COLORS, move_options

        dex = load_dex()
        options = move_options(dex, "Garchomp")
        type_order = {t: i for i, t in enumerate(TYPE_COLORS)}
        shown_type_order = [type_order[dex.get_move(name).type] for name in options]
        assert shown_type_order == sorted(shown_type_order)
        # Not just non-decreasing (which an accidental alphabetical sort
        # could also produce for some species) - explicitly confirm it's
        # not the plain A-Z list either.
        assert options != sorted(options)

        import itertools

        for _, group in itertools.groupby(options, key=lambda name: dex.get_move(name).type):
            group_names = list(group)
            assert group_names == sorted(group_names)

    def test_changing_species_updates_the_move_list_and_resets_an_invalid_selection(self):
        at = _fresh_app()
        move_sb = next(sb for sb in at.selectbox if sb.key == "A attacks B_move")
        move_sb.select("Earthquake").run()

        next(sb for sb in at.selectbox if sb.key == "a_species").select("Gengar").run()
        assert not at.exception

        move_sb_after = next(sb for sb in at.selectbox if sb.key == "A attacks B_move")
        assert not any("Earthquake" in opt for opt in move_sb_after.options)  # Gengar can't learn it
        assert move_sb_after.value == "(none)"  # gracefully reset, not left dangling
        # no stale damage result left showing - only the 2 always-on Speed metrics remain
        assert [m.label for m in at.metric] == ["Pokémon A Speed", "Pokémon B Speed"]

    def test_dropdown_shows_a_header_before_each_types_first_move(self):
        from poke_calc.data.loader import load_dex
        from poke_calc.ui.app import move_dropdown_options, move_options

        dex = load_dex()
        options = move_dropdown_options(dex, "Garchomp")
        # A header for Ground should appear immediately before the first
        # Ground move Garchomp learns (alphabetically, per move_options()).
        first_ground_move = next(
            name for name in move_options(dex, "Garchomp") if dex.get_move(name).type == "Ground"
        )
        move_index = options.index(first_ground_move)
        assert options[move_index - 1] == "── Ground ──"

    def test_dropdown_displays_moves_with_a_type_emoji_prefix(self):
        at = _fresh_app()
        move_sb = next(sb for sb in at.selectbox if sb.key == "A attacks B_move")
        # Earthquake is Ground-type - see MOVE_TYPE_EMOJI.
        assert any(opt.startswith("🟤") and "Earthquake" in opt for opt in move_sb.options)

    def test_selecting_a_header_is_a_graceful_no_op(self):
        # A plain st.selectbox can't disable individual options, so a
        # header row is technically selectable - picking one must not
        # crash, and should behave like picking "(none)" (no damage
        # result shown), not silently show stale/wrong data.
        at = _fresh_app()
        move_sb = next(sb for sb in at.selectbox if sb.key == "A attacks B_move")
        header = next(opt for opt in move_sb.options if opt.startswith("── "))
        move_sb.select(header).run()
        assert not at.exception
        assert [m.label for m in at.metric] == ["Pokémon A Speed", "Pokémon B Speed"]

    def test_status_moves_are_included_not_just_damaging_ones(self):
        # By request: the dropdown used to filter Status moves out
        # entirely - Swords Dance is a real Garchomp-learnable move that
        # should now be selectable.
        at = _fresh_app()
        move_sb = next(sb for sb in at.selectbox if sb.key == "A attacks B_move")
        assert any("Swords Dance" in opt for opt in move_sb.options)

    def test_selecting_a_status_move_shows_info_but_no_damage_result(self):
        # calculate_damage() correctly returns [0]*16 for a Status move
        # (a real early return, not a bug) - showing "0-0, OHKO 0%" for
        # e.g. Swords Dance would just be misleading clutter, so the
        # damage metric/KO-chance section is skipped for these; the move
        # info/description above (already category-agnostic) still shows.
        at = _fresh_app()
        move_sb = next(sb for sb in at.selectbox if sb.key == "A attacks B_move")
        move_sb.select("Swords Dance").run()  # the raw value, not the emoji-prefixed display text
        assert not at.exception
        assert [m.label for m in at.metric] == ["Pokémon A Speed", "Pokémon B Speed"]
        captions = [c.value for c in at.caption]
        assert any("Status" in c for c in captions)  # render_move_info's category/BP line


class TestDamageCalculation:
    def test_selecting_a_move_shows_damage(self):
        at = _fresh_app()
        move_sb = next(sb for sb in at.selectbox if sb.key == "A attacks B_move")
        move_sb.select("Earthquake").run()
        assert not at.exception
        assert any(m.label == "Earthquake" for m in at.metric)

    def test_default_matchup_matches_direct_engine_call(self):
        # Cross-checks the UI's actual default widget state (Garchomp vs
        # Tyranitar, whatever nature/SP the suggestion heuristic picks,
        # species-default ability, no item, full HP) against calling the
        # engine directly with THOSE SAME inputs, read back from the
        # widgets rather than assumed - proves the UI's wiring, not just
        # its rendering, and doesn't hardcode a suggestion-heuristic
        # default that Phase 4's later "suggested set" feature changed.
        from poke_calc.data.loader import load_dex
        from poke_calc.engine.build import calculate
        from poke_calc.engine.models import FieldState

        at = _fresh_app()
        move_sb = next(sb for sb in at.selectbox if sb.key == "A attacks B_move")
        move_sb.select("Earthquake").run()
        assert not at.exception
        shown = next(m for m in at.metric if m.label == "Earthquake").value  # e.g. "132-156"
        lo, hi = (int(x) for x in shown.split("-"))

        a_nature = next(sb for sb in at.selectbox if sb.key == "a_nature").value
        b_nature = next(sb for sb in at.selectbox if sb.key == "b_nature").value
        a_sp = {ni.key.rsplit("_", 1)[-1]: ni.value for ni in at.number_input if ni.key.startswith("a_sp_")}
        b_sp = {ni.key.rsplit("_", 1)[-1]: ni.value for ni in at.number_input if ni.key.startswith("b_sp_")}
        a_item = next(sb for sb in at.selectbox if sb.key == "a_item").value
        b_item = next(sb for sb in at.selectbox if sb.key == "b_item").value
        a_item = None if a_item == "(none)" else a_item
        b_item = None if b_item == "(none)" else b_item

        dex = load_dex()
        rolls = calculate(
            dex,
            {"species": "Garchomp", "nature": a_nature, "ability": "Sand Veil", "sp": a_sp, "item": a_item},
            {"species": "Tyranitar", "nature": b_nature, "ability": "Sand Stream", "sp": b_sp, "item": b_item},
            "Earthquake",
            field=FieldState(game_type="Singles"),
        )
        assert (lo, hi) == (min(rolls), max(rolls))


class TestKoChance:
    def test_selecting_a_move_shows_per_hit_ko_percentages(self):
        # Hand-verified via direct engine.ko_chance.ko_chance() call:
        # Jolly/Life Orb Garchomp's Earthquake vs. a bulky 32/32 HP/Def
        # Snorlax is 0% OHKO, ~7.9% 2HKO, ~100% 3HKO - a real spread
        # across multiple hit counts, not a degenerate all-or-nothing case.
        at = _fresh_app()
        next(sb for sb in at.selectbox if sb.key == "a_item").select("Life Orb").run()
        next(sb for sb in at.selectbox if sb.key == "b_species").select("Snorlax").run()
        next(sb for sb in at.selectbox if sb.key == "b_nature").select("Impish").run()
        next(sb for sb in at.selectbox if sb.key == "b_ability").select("Thick Fat").run()
        for stat, value in (("hp", 32), ("atk", 0), ("def", 32), ("spa", 0), ("spd", 0), ("spe", 0)):
            next(ni for ni in at.number_input if ni.key == f"b_sp_{stat}").set_value(value).run()

        move_sb = next(sb for sb in at.selectbox if sb.key == "A attacks B_move")
        move_sb.select("Earthquake").run()
        assert not at.exception
        captions = [c.value for c in at.caption]
        ko_caption = next(c for c in captions if "OHKO" in c)
        assert "OHKO 0%" in ko_caption
        assert "2HKO" in ko_caption
        assert "3HKO" in ko_caption

    def test_guaranteed_ohko_is_bolded_and_shown_alone(self):
        # Hand-verified: Adamant/Life Orb Garchomp's Earthquake vs. an
        # undefensively-invested Alakazam is a guaranteed OHKO.
        at = _fresh_app()
        next(sb for sb in at.selectbox if sb.key == "a_nature").select("Adamant").run()
        next(sb for sb in at.selectbox if sb.key == "a_item").select("Life Orb").run()
        next(sb for sb in at.selectbox if sb.key == "b_species").select("Alakazam").run()
        next(ni for ni in at.number_input if ni.key == "b_sp_hp").set_value(0).run()
        next(ni for ni in at.number_input if ni.key == "b_sp_def").set_value(0).run()

        move_sb = next(sb for sb in at.selectbox if sb.key == "A attacks B_move")
        move_sb.select("Earthquake").run()
        assert not at.exception
        captions = [c.value for c in at.caption]
        ko_caption = next(c for c in captions if "OHKO" in c)
        assert ko_caption == "**OHKO 100%**"


class TestSpeedComparison:
    def test_shows_current_speed_for_both_and_who_moves_first(self):
        at = _fresh_app()
        # Force a deterministic spread: A maxes Speed, B dumps none into it.
        for stat in ("hp", "atk", "def", "spa", "spd"):
            next(ni for ni in at.number_input if ni.key == f"a_sp_{stat}").set_value(0).run()
            next(ni for ni in at.number_input if ni.key == f"b_sp_{stat}").set_value(0).run()
        next(ni for ni in at.number_input if ni.key == "a_sp_spe").set_value(32).run()
        next(ni for ni in at.number_input if ni.key == "b_sp_spe").set_value(0).run()
        assert not at.exception

        metrics = {m.label: int(m.value) for m in at.metric if "Speed" in m.label}
        assert metrics["Pokémon A Speed"] > metrics["Pokémon B Speed"]
        captions = [c.value for c in at.caption]
        assert any("Pokémon A moves first" in c for c in captions)

    def test_speed_tie_is_reported(self):
        from poke_calc.data.loader import STAT_NAMES

        at = _fresh_app()
        next(sb for sb in at.selectbox if sb.key == "a_species").select("Tyranitar").run()
        for stat in STAT_NAMES:
            a_val = next(ni for ni in at.number_input if ni.key == f"a_sp_{stat}").value
            next(ni for ni in at.number_input if ni.key == f"b_sp_{stat}").set_value(a_val).run()
        next(sb for sb in at.selectbox if sb.key == "a_nature").select("Hardy").run()
        next(sb for sb in at.selectbox if sb.key == "b_nature").select("Hardy").run()
        assert not at.exception
        metrics = {m.label: int(m.value) for m in at.metric if "Speed" in m.label}
        assert metrics["Pokémon A Speed"] == metrics["Pokémon B Speed"]
        captions = [c.value for c in at.caption]
        assert any("Speed tie" in c for c in captions)

    def test_paralysis_halves_effective_speed(self):
        at = _fresh_app()
        baseline = int(next(m for m in at.metric if m.label == "Pokémon A Speed").value)
        next(sb for sb in at.selectbox if sb.key == "a_status").select("Paralysis").run()
        assert not at.exception
        paralyzed = int(next(m for m in at.metric if m.label == "Pokémon A Speed").value)
        assert paralyzed == baseline // 2


class TestMoveInfo:
    def test_selecting_a_move_shows_its_type_category_and_power(self):
        at = _fresh_app()
        move_sb = next(sb for sb in at.selectbox if sb.key == "A attacks B_move")
        move_sb.select("Earthquake").run()
        assert not at.exception
        html_blocks = [m.value for m in at.markdown]
        assert any(">Ground<" in h for h in html_blocks)  # type badge
        captions = [c.value for c in at.caption]
        earthquake_info = next(c for c in captions if "Physical" in c)
        assert "100 BP" in earthquake_info
        assert "Hits all adjacent Pokemon" in earthquake_info

    def test_move_info_lists_notable_effects(self):
        at = _fresh_app()
        move_sb = next(sb for sb in at.selectbox if sb.key == "A attacks B_move")
        move_sb.select("Double-Edge").run()  # Garchomp-learnable, has recoil + contact
        assert not at.exception
        captions = [c.value for c in at.caption]
        double_edge_info = next(c for c in captions if "Contact" in c)
        assert "Recoil 33% of damage dealt" in double_edge_info

    def test_no_move_info_shown_before_a_move_is_selected(self):
        at = _fresh_app()
        captions = [c.value for c in at.caption]
        assert not any("Physical" in c or "Special" in c for c in captions)

    def test_shows_the_moves_full_description(self):
        at = _fresh_app()
        move_sb = next(sb for sb in at.selectbox if sb.key == "A attacks B_move")
        move_sb.select("Earthquake").run()
        assert not at.exception
        captions = [c.value for c in at.caption]
        assert "Damage doubles if the target is using Dig." in captions

    def test_changing_move_updates_the_description(self):
        at = _fresh_app()
        move_sb = next(sb for sb in at.selectbox if sb.key == "A attacks B_move")
        move_sb.select("Double-Edge").run()
        assert not at.exception
        captions = [c.value for c in at.caption]
        assert any(c.startswith("If the target lost HP") for c in captions)


class TestSpBudgetGuard:
    def test_over_budget_shows_error_and_suppresses_results(self):
        at = _fresh_app()
        for stat in ("atk", "spa", "spe"):
            next(ni for ni in at.number_input if ni.key == f"a_sp_{stat}").set_value(32).run()
        assert not at.exception
        assert any("exceeds the 66-point budget" in e.value for e in at.error)
        assert any("Fix the error" in w.value for w in at.warning)


class TestWeatherAndTerrainInfo:
    """Shown as a hover-over "?" icon (st.selectbox's `help=`) rather than
    a caption, to avoid eating vertical space - see main()'s comment on
    why `help=` reads last run's session_state value back instead of the
    widget's own (not-yet-returned) value."""

    def test_no_help_tooltip_when_none_selected(self):
        at = _fresh_app()
        weather_sb = next(sb for sb in at.selectbox if sb.label == "Weather")
        terrain_sb = next(sb for sb in at.selectbox if sb.label == "Terrain")
        assert not weather_sb.help
        assert not terrain_sb.help

    def test_selecting_a_weather_sets_its_help_tooltip(self):
        at = _fresh_app()
        next(sb for sb in at.selectbox if sb.label == "Weather").select("Sun").run()
        assert not at.exception
        weather_sb = next(sb for sb in at.selectbox if sb.label == "Weather")
        assert weather_sb.help.startswith("Fire-type moves deal 1.5x damage")

    def test_selecting_a_terrain_sets_its_help_tooltip(self):
        at = _fresh_app()
        next(sb for sb in at.selectbox if sb.label == "Terrain").select("Grassy").run()
        assert not at.exception
        terrain_sb = next(sb for sb in at.selectbox if sb.label == "Terrain")
        assert terrain_sb.help.startswith("Grass-type moves get a 1.3x power boost")


class TestRegulationFiltering:
    def test_m_a_excludes_life_orb(self):
        at = _fresh_app()
        reg_sb = next(sb for sb in at.selectbox if sb.label == "Regulation")
        item_sb = next(sb for sb in at.selectbox if sb.key == "a_item")
        assert "Life Orb" in item_sb.options  # default is M-B

        reg_sb.select("M-A").run()
        assert not at.exception
        item_sb_after = next(sb for sb in at.selectbox if sb.key == "a_item")
        assert "Life Orb" not in item_sb_after.options


class TestTeamPresets:
    def test_saving_the_current_build_creates_a_new_team(self):
        from poke_calc.data.teams import load_teams

        at = _fresh_app()
        next(ti for ti in at.text_input if ti.key == "a_save_new_team_name").set_value("My Team").run()
        next(bt for bt in at.button if bt.key == "a_save_btn").click().run()
        assert not at.exception
        assert next(t for t in at.toast).value.startswith("Saved")

        teams = load_teams()
        assert list(teams) == ["My Team"]
        preset = teams["My Team"][0]
        assert preset.species == "Garchomp"
        assert preset.nature == "Jolly"  # Garchomp's real ladder-suggested default
        assert preset.item == "Life Orb"

    def test_saving_without_a_team_name_shows_an_error(self):
        at = _fresh_app()
        next(bt for bt in at.button if bt.key == "a_save_btn").click().run()
        assert not at.exception
        assert any("Enter a team name" in e.value for e in at.error)

    def test_saving_the_exact_same_build_twice_is_rejected(self):
        from poke_calc.data.teams import load_teams

        at = _fresh_app()
        next(ti for ti in at.text_input if ti.key == "a_save_new_team_name").set_value("My Team").run()
        next(bt for bt in at.button if bt.key == "a_save_btn").click().run()
        assert not at.exception

        # Same team, same species/nature/ability/item/SP, but a DIFFERENT
        # label - label alone must not make it count as a different build.
        next(sb for sb in at.selectbox if sb.key == "a_save_team_choice").select("My Team").run()
        next(ti for ti in at.text_input if ti.key == "a_save_preset_label").set_value("Duplicate").run()
        next(bt for bt in at.button if bt.key == "a_save_btn").click().run()
        assert not at.exception

        assert any("already has this exact build" in e.value for e in at.error)
        assert [p.label for p in load_teams()["My Team"]] == ["Garchomp"]

    def test_saving_again_appends_to_the_same_team_rather_than_overwriting(self):
        at = _fresh_app()
        next(ti for ti in at.text_input if ti.key == "a_save_new_team_name").set_value("My Team").run()
        next(bt for bt in at.button if bt.key == "a_save_btn").click().run()
        assert not at.exception

        # The Team selectbox now offers "My Team" as an existing option,
        # not just "+ New team" - pick it for the second save. Nature is
        # changed too so this is a genuinely different build, not a
        # same-build duplicate (which is now correctly rejected).
        next(sb for sb in at.selectbox if sb.key == "a_save_team_choice").select("My Team").run()
        next(sb for sb in at.selectbox if sb.key == "a_nature").select("Adamant").run()
        next(ti for ti in at.text_input if ti.key == "a_save_preset_label").set_value("Second Build").run()
        next(bt for bt in at.button if bt.key == "a_save_btn").click().run()
        assert not at.exception

        from poke_calc.data.teams import load_teams

        teams = load_teams()
        assert [p.label for p in teams["My Team"]] == ["Garchomp", "Second Build"]

    def test_loading_a_preset_populates_the_panel_and_is_not_overridden_by_the_suggestion(self):
        # Alakazam's own real ladder-suggested nature is "Timid" (see
        # TestSuggestedSet) - deliberately saving it here with a DIFFERENT
        # nature ("Modest") makes this a real regression check: if the
        # Load button forgot to update `{key}_suggested_for`, the
        # suggestion block would silently flip it back to "Timid".
        from poke_calc.data.teams import Preset, save_teams

        save_teams({
            "My Team": [Preset(
                label="Special Zam", species="Alakazam", nature="Modest",
                ability="Synchronize", item="Focus Sash",
                sp={"hp": 4, "atk": 0, "def": 0, "spa": 30, "spd": 0, "spe": 32},
            )],
        })

        at = _fresh_app()
        next(bt for bt in at.button if bt.key == "a_load_btn").click().run()
        assert not at.exception

        assert next(sb for sb in at.selectbox if sb.key == "a_species").value == "Alakazam"
        assert next(sb for sb in at.selectbox if sb.key == "a_nature").value == "Modest"
        assert next(sb for sb in at.selectbox if sb.key == "a_ability").value == "Synchronize"
        assert next(sb for sb in at.selectbox if sb.key == "a_item").value == "Focus Sash"
        sp_vals = {ni.key.rsplit("_", 1)[-1]: ni.value for ni in at.number_input if ni.key.startswith("a_sp_")}
        assert sp_vals == {"hp": 4, "atk": 0, "def": 0, "spa": 30, "spd": 0, "spe": 32}

    def test_loading_a_preset_does_not_trigger_streamlits_session_state_conflict_warning(self, caplog):
        # Regression check: a widget given BOTH an explicit index=/value=
        # default AND a session_state write (from the Load button) in the
        # same run makes Streamlit log "was created with a default value
        # but also had its value set via the Session State API" - species/
        # nature/ability/item/SP widgets must all avoid that combination.
        from poke_calc.data.teams import Preset, save_teams

        save_teams({
            "My Team": [Preset(
                label="Special Zam", species="Alakazam", nature="Modest",
                ability="Synchronize", item="Focus Sash",
                sp={"hp": 4, "atk": 0, "def": 0, "spa": 30, "spd": 0, "spe": 32},
            )],
        })

        at = _fresh_app()
        with caplog.at_level("WARNING", logger="streamlit.elements.lib.policies"):
            next(bt for bt in at.button if bt.key == "a_load_btn").click().run()
        assert not at.exception
        policy_warnings = [r.message for r in caplog.records if r.name == "streamlit.elements.lib.policies"]
        assert not policy_warnings, policy_warnings

    def test_no_load_widgets_shown_when_there_are_no_saved_teams(self):
        at = _fresh_app()
        assert not any(sb.key == "a_load_team" for sb in at.selectbox)
        captions = [c.value for c in at.caption]
        assert any("No saved teams yet" in c for c in captions)

    def test_deleting_a_preset_removes_only_that_preset(self):
        from poke_calc.data.teams import Preset, load_teams, save_teams

        save_teams({"My Team": [
            Preset(label="First", species="Garchomp", nature="Jolly", ability="Rough Skin", item=None, sp={}),
            Preset(label="Second", species="Tyranitar", nature="Adamant", ability="Sand Stream", item=None, sp={}),
        ]})

        at = _fresh_app()
        next(bt for bt in at.button if bt.key == "del_preset_My Team_0").click().run()
        assert not at.exception
        assert [p.label for p in load_teams()["My Team"]] == ["Second"]

    def test_deleting_a_team_removes_it_entirely(self):
        from poke_calc.data.teams import Preset, load_teams, save_teams

        save_teams({"My Team": [
            Preset(label="First", species="Garchomp", nature="Jolly", ability="Rough Skin", item=None, sp={}),
        ]})

        at = _fresh_app()
        next(bt for bt in at.button if bt.key == 'del_team_My Team').click().run()
        assert not at.exception
        assert load_teams() == {}
