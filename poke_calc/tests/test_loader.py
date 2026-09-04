import pytest

from poke_calc.data.loader import load_dex, to_id


class TestToId:
    def test_normalizes_case_spaces_and_hyphens(self):
        assert to_id("Meganium-Mega") == "meganiummega"
        assert to_id("meganium mega") == "meganiummega"
        assert to_id("MEGANIUM-MEGA") == "meganiummega"

    def test_strips_punctuation(self):
        assert to_id("Farfetch'd") == "farfetchd"
        assert to_id("Mr. Mime") == "mrmime"


class TestDexCounts:
    def test_table_sizes_match_the_pinned_dump(self):
        dex = load_dex()
        assert len(dex.species) == 324
        assert len(dex.moves) == 513
        assert len(dex.items) == 148
        assert len(dex.abilities) == 200
        assert len(dex.natures) == 25


class TestForgivingLookups:
    def test_species_lookup_is_case_and_hyphen_insensitive(self):
        dex = load_dex()
        a = dex.get_species("Meganium-Mega")
        b = dex.get_species("meganium mega")
        assert a is b

    def test_unknown_species_raises_with_helpful_message(self):
        dex = load_dex()
        with pytest.raises(KeyError, match="not in the Champions roster"):
            dex.get_species("Landorus-Therian")

    def test_unknown_move_raises_with_helpful_message(self):
        dex = load_dex()
        with pytest.raises(KeyError, match="not a legal Champions move"):
            dex.get_move("Tera Blast")

    def test_unknown_item_raises(self):
        dex = load_dex()
        with pytest.raises(KeyError, match="not a legal Champions item"):
            dex.get_item("Choice Band")


class TestMoveDataGapPatch:
    """@smogon/calc's own CHAMPIONS_PATCH merge drops `type` (and, for Metal
    Claw, `basePower`) for exactly these 12 moves - confirmed upstream, not
    a dump artifact (calculate() itself throws). See loader.py's
    _MOVE_TYPE_OVERRIDES comment and NOTICE."""

    AFFECTED_IDS = (
        "anchorshot", "astralbarrage", "bloodmoon", "boltbeak", "dragonhammer",
        "fishiousrend", "geargrind", "hyperdrill", "metalclaw", "revelationdance",
        "snipeshot", "tripledive",
    )

    def test_all_affected_moves_have_a_type_after_loading(self):
        dex = load_dex()
        for mid in self.AFFECTED_IDS:
            move = dex.moves[mid]
            assert move.type, f"{mid} has no type"

    def test_legal_moves_have_correct_type_and_base_power(self):
        dex = load_dex()
        assert dex.get_move("Anchor Shot").type == "Steel"
        assert dex.get_move("Anchor Shot").base_power == 90
        assert dex.get_move("Bolt Beak").type == "Electric"
        assert dex.get_move("Bolt Beak").base_power == 80
        assert dex.get_move("Fishious Rend").type == "Water"
        assert dex.get_move("Fishious Rend").base_power == 80
        assert dex.get_move("Gear Grind").type == "Steel"
        assert dex.get_move("Gear Grind").base_power == 60

    def test_metal_claw_base_power_patched_and_slicing_flag_preserved(self):
        dex = load_dex()
        metal_claw = dex.get_move("Metal Claw")
        assert metal_claw.base_power == 50
        assert metal_claw.type == "Steel"
        assert metal_claw.flags.get("slicing") == 1


class TestSprites:
    def test_all_species_have_a_sprite_id(self):
        dex = load_dex()
        missing = [s.name for s in dex.species.values() if s.sprite_id is None]
        assert not missing, f"species with no resolved sprite: {missing}"

    def test_sprite_url_uses_showdown_ani_cdn(self):
        dex = load_dex()
        assert dex.get_species("Pikachu").sprite_url == "https://play.pokemonshowdown.com/sprites/ani/pikachu.gif"

    def test_forme_sprite_id_uses_hyphenated_convention_not_to_id(self):
        # Showdown's forme filenames are "{base}-{forme}", not our own
        # collapsed to_id() ("taurospaldeaaqua" would 404) - see
        # poke_calc/data/generate_sprite_ids.py.
        dex = load_dex()
        assert dex.get_species("Tauros-Paldea-Aqua").sprite_id == "tauros-paldeaaqua"
        assert dex.get_species("Charizard-Mega-X").sprite_id == "charizard-megax"

    def test_species_whose_own_name_has_a_hyphen_is_not_split(self):
        # "Kommo-o" is not a forme of "Kommo" - the hyphen is part of its
        # own name, so the sprite id must stay "kommoo", not "kommo-o".
        dex = load_dex()
        assert dex.get_species("Kommo-o").sprite_id == "kommoo"


class TestMegaStoneLookup:
    def test_finds_the_stone_for_a_mega_forme(self):
        dex = load_dex()
        stone = dex.mega_stone_for("Meganium-Mega")
        assert stone is not None
        assert stone.name == "Meganiumite"

    def test_gendered_mega_formes_resolve_to_the_same_shared_stone(self):
        # Meowsticite maps two different base species (Meowstic, Meowstic-F)
        # to their own Mega formes - both must resolve to it.
        dex = load_dex()
        assert dex.mega_stone_for("Meowstic-M-Mega").name == "Meowsticite"
        assert dex.mega_stone_for("Meowstic-F-Mega").name == "Meowsticite"

    def test_non_mega_species_has_no_stone(self):
        dex = load_dex()
        assert dex.mega_stone_for("Garchomp") is None


class TestLadderSets:
    """Doubles-only by request - see poke_calc/data/generate_pokekipe_sets.py and
    Dex.ladder_set()'s docstring."""

    def test_known_species_returns_a_real_spread_and_item(self):
        dex = load_dex()
        result = dex.ladder_set("Garchomp")
        assert result is not None
        nature, sp, item = result
        assert nature in dex.natures
        assert sum(sp.values()) <= 66
        assert all(0 <= v <= 32 for v in sp.values())
        assert item is None or item in {i.name for i in dex.items.values()}

    def test_species_with_no_data_returns_none(self):
        dex = load_dex()
        # Not every species has Doubles ladder data (niche/brand-new Mega
        # formes, or ones that hit the source API's rate limit during the
        # snapshot fetch) - assert the mechanism returns None cleanly for
        # at least one that doesn't, rather than assuming a specific
        # species (which could gain data on a future refresh).
        import json
        from pathlib import Path

        dump_dir = Path(__file__).parent.parent / "poke_calc" / "data" / "dump"
        raw = json.loads((dump_dir / "pokekipe_sets.json").read_text())
        no_data_species = next(sid for sid, v in raw.items() if v is None)
        assert dex.ladder_set(no_data_species) is None

    def test_mega_forme_item_is_its_own_mega_stone(self):
        dex = load_dex()
        result = dex.ladder_set("Garchomp-Mega")
        assert result is not None
        _, _, item = result
        assert item == "Garchompite"

    def test_ladder_set_tolerates_an_entry_with_no_resolvable_item(self):
        # Every species in the current snapshot that has spread data also
        # resolved a top item, so this exercises the "item id present in
        # the raw dump but not in this dex" fallback path directly rather
        # than depending on the live snapshot happening to contain one.
        dex = load_dex()
        dex._pokekipe_sets["faketestentry"] = {
            "nature": "Adamant", "sp": {s: 0 for s in dex.species["garchomp"].base_stats}, "item": "not-a-real-item",
        }
        nature, sp, item = dex.ladder_set("faketestentry")
        assert item is None


class TestAbilitySlots:
    def test_all_species_have_at_least_one_ability(self):
        dex = load_dex()
        empty = [s.name for s in dex.species.values() if not dex.ability_slots(s.name)]
        assert not empty, f"species with no resolved ability slots: {empty}"

    def test_multi_ability_species_returns_all_slots(self):
        dex = load_dex()
        names = {a.name for a in dex.ability_slots("Gyarados")}
        assert names == {"Intimidate", "Moxie"}

    def test_mega_forme_has_exactly_its_own_fixed_ability(self):
        dex = load_dex()
        names = {a.name for a in dex.ability_slots("Meganium-Mega")}
        assert names == {"Mega Sol"}

    def test_species_own_ability_field_matches_a_slot_in_the_common_case(self):
        dex = load_dex()
        for species in dex.species.values():
            slot_names = {a.name for a in dex.ability_slots(species.name)}
            if species.name in ("Hawlucha-Mega", "Skarmory-Mega"):
                continue  # confirmed pokedex.ts-vs-@smogon/calc discrepancy, see generator docstring
            assert species.ability in slot_names, species.name

    def test_battle_bond_is_excluded_since_this_dex_has_no_data_for_it(self):
        # Present in pokedex.ts but absent from @smogon/calc's own
        # Champions ability table - filtered out rather than crashing.
        dex = load_dex()
        assert "battlebond" not in dex.abilities


class TestAbilityDescriptions:
    """See data/generate_ability_descriptions.py and NOTICE #5."""

    def test_all_abilities_have_a_description(self):
        dex = load_dex()
        missing = [a.name for a in dex.abilities.values() if not a.description]
        assert not missing, f"abilities with no description: {missing}"

    def test_known_ability_has_the_expected_description(self):
        dex = load_dex()
        assert dex.get_ability("Intimidate").description == (
            "On switch-in, this Pokemon lowers the Attack of opponents by 1 stage."
        )

    def test_champions_exclusive_ability_has_a_description(self):
        # Confirms Showdown's text tree covers Champions-exclusive
        # abilities too, despite living in the unmodified base file.
        dex = load_dex()
        assert "Sunny Day" in dex.get_ability("Mega Sol").description


class TestMoveDescriptions:
    """See data/generate_move_descriptions.py and NOTICE."""

    def test_all_real_moves_have_a_description(self):
        dex = load_dex()
        missing = [m.name for m in dex.moves.values() if not m.description and m.id != "nomove"]
        assert not missing, f"moves with no description: {missing}"

    def test_nomove_placeholder_has_no_description(self):
        # "(No Move)" is @smogon/calc's own sentinel for an empty move
        # slot, not a real move - Showdown's text tree has nothing for it,
        # and that's correct, not a gap.
        dex = load_dex()
        assert dex.moves["nomove"].description is None

    def test_known_move_has_the_expected_full_description(self):
        dex = load_dex()
        assert dex.get_move("Earthquake").description == "Damage doubles if the target is using Dig."

    def test_effectless_move_falls_back_to_no_additional_effect_text(self):
        # `desc` for a move with no secondary effect is often just "No
        # additional effect." (a real Showdown convention, not a data
        # gap) even when its shortDesc separately calls out a mechanical
        # property like priority - see the generator's docstring.
        dex = load_dex()
        assert dex.get_move("Accelerock").description == "No additional effect."


class TestCritRatios:
    """See data/generate_crit_ratios.py and NOTICE."""

    def test_ordinary_move_defaults_to_base_crit_ratio(self):
        dex = load_dex()
        assert dex.get_move("Earthquake").crit_ratio == 1

    def test_known_high_crit_ratio_moves(self):
        dex = load_dex()
        for name in ("Night Slash", "Stone Edge", "Crabhammer", "Leaf Blade", "Shadow Claw"):
            assert dex.get_move(name).crit_ratio == 2, name

    def test_no_move_exceeds_the_known_max_ratio(self):
        # Confirms the live-fetched data doesn't contain a surprise this
        # project's CRIT_STAGE_CHANCES table (engine/ko_chance.py) isn't
        # sized for - would need a code change, not silently clamp wrong.
        dex = load_dex()
        assert all(m.crit_ratio <= 3 for m in dex.moves.values())


class TestLearnsets:
    def test_all_species_have_a_learnset(self):
        dex = load_dex()
        empty = [s.name for s in dex.species.values() if not dex.learnset(s.name)]
        assert not empty, f"species with an empty learnset: {empty}"

    def test_known_move_is_learnable(self):
        dex = load_dex()
        assert "earthquake" in dex.learnset("Garchomp")

    def test_illegal_move_is_not_learnable(self):
        dex = load_dex()
        assert "dracometeor" not in dex.learnset("Snorlax")

    def test_mega_forme_falls_back_to_base_species_learnset(self):
        # Mega Evolution doesn't change what a Pokemon can learn - Showdown's
        # learnsets.ts has no separate entry for Mega formes at all.
        dex = load_dex()
        assert dex.learnset("Garchomp-Mega") == dex.learnset("Garchomp")

    def test_learnable_moves_excludes_ids_absent_from_our_move_dex(self):
        # "pound" is in Showdown's learnset data for many species but not
        # in @smogon/calc's own 513-move Champions table - excluded since
        # there's no data to calculate damage with for it.
        dex = load_dex()
        assert "pound" not in dex.moves
        movable = dex.learnable_moves("Pikachu")
        assert "pound" not in movable

    def test_unknown_species_raises(self):
        dex = load_dex()
        with pytest.raises(KeyError, match="no known learnset"):
            dex.learnset("Not A Real Species")


class TestTypeEffectiveness:
    def test_double_weakness(self):
        dex = load_dex()
        assert dex.type_effectiveness("Fire", ("Grass", "Steel")) == 4.0

    def test_immunity(self):
        dex = load_dex()
        assert dex.type_effectiveness("Ground", ("Flying",)) == 0.0

    def test_neutral(self):
        dex = load_dex()
        assert dex.type_effectiveness("Normal", ("Normal",)) == 1.0
