"""Tests for poke_calc.api - the FastAPI layer wrapping engine/data. Uses
FastAPI's TestClient (httpx-based, no real network/browser) - same "no
game logic here" standard as the routes themselves: every assertion
either checks the wrapping/shape is right, or cross-checks a value
against calling the underlying engine function directly.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from poke_calc.api.main import app
from poke_calc.data.loader import load_dex


@pytest.fixture(autouse=True)
def isolated_teams_file(tmp_path, monkeypatch):
    from poke_calc.data import teams as teams_module

    monkeypatch.setattr(teams_module, "TEAMS_PATH", tmp_path / "teams.json")


@pytest.fixture(scope="module")
def dex():
    return load_dex()


@pytest.fixture
def client():
    return TestClient(app)


class TestBootstrap:
    def test_returns_200_with_expected_top_level_shape(self, client):
        resp = client.get("/api/bootstrap")
        assert resp.status_code == 200
        body = resp.json()
        assert set(body) == {
            "species", "moves", "items", "abilities", "natures", "regulations",
            "sp_budget", "sp_max", "weathers", "terrains", "statuses", "type_chart",
        }

    def test_counts_match_the_dex(self, client, dex):
        body = client.get("/api/bootstrap").json()
        assert len(body["species"]) == len(dex.species)
        assert len(body["moves"]) == len(dex.moves)
        assert len(body["items"]) == len(dex.items)
        assert len(body["abilities"]) == len(dex.abilities)
        assert len(body["natures"]) == len(dex.natures)
        assert body["regulations"] == ["M-A", "M-B"]
        assert body["sp_budget"] == 66
        assert body["sp_max"] == 32

    def test_garchomp_fields_are_correct(self, client):
        body = client.get("/api/bootstrap").json()
        garchomp = next(s for s in body["species"] if s["id"] == "garchomp")
        assert garchomp["name"] == "Garchomp"
        assert set(garchomp["types"]) == {"Dragon", "Ground"}
        assert garchomp["base_stats"]["hp"] == 108
        assert set(garchomp["ability_slots"]) == {"Sand Veil", "Rough Skin"}
        assert "earthquake" in garchomp["learnable_moves"]
        assert garchomp["is_mega"] is False
        assert garchomp["mega_stone"] is None
        # Real Doubles ladder data, not the base-stat heuristic (see
        # data/generate_pokekipe_sets.py) - confirmed multiple times this
        # session, still true as of this snapshot.
        assert garchomp["suggested_nature"] == "Jolly"
        assert garchomp["suggested_item"] == "Life Orb"

    def test_mega_forme_has_its_own_mega_stone(self, client):
        body = client.get("/api/bootstrap").json()
        mega = next(s for s in body["species"] if s["id"] == "garchompmega")
        assert mega["is_mega"] is True
        assert mega["mega_stone"] == "Garchompite"

    def test_item_legality_flags_reg_m_a_correctly(self, client):
        body = client.get("/api/bootstrap").json()
        items_by_id = {i["id"]: i for i in body["items"]}
        assert items_by_id["lifeorb"]["legal_in_reg_m_a"] is False
        assert items_by_id["choicescarf"]["legal_in_reg_m_a"] is True

    def test_response_is_cached_across_calls(self, client):
        first = client.get("/api/bootstrap").json()
        second = client.get("/api/bootstrap").json()
        assert first == second


def _mon(species, nature, ability, sp, item=None):
    return {"species": species, "nature": nature, "ability": ability, "item": item, "sp": sp}


class TestCalculate:
    def test_matches_a_direct_engine_call(self, client, dex):
        from poke_calc.engine.build import calculate

        attacker = _mon("Garchomp", "Jolly", "Rough Skin", {"hp": 0, "atk": 32, "def": 0, "spa": 0, "spd": 0, "spe": 32}, "Life Orb")
        defender = _mon("Snorlax", "Impish", "Thick Fat", {"hp": 32, "atk": 0, "def": 32, "spa": 0, "spd": 0, "spe": 0})

        resp = client.post("/api/calculate", json={"attacker": attacker, "defender": defender, "move_name": "Earthquake"})
        assert resp.status_code == 200
        body = resp.json()

        expected_rolls = calculate(dex, attacker, defender, "Earthquake")
        assert body["rolls"] == expected_rolls

    def test_ko_chances_match_a_direct_engine_call(self, client, dex):
        from poke_calc.engine.ko_chance import ko_chance

        attacker = _mon("Garchomp", "Adamant", "Rough Skin", {"hp": 0, "atk": 32, "def": 0, "spa": 0, "spd": 0, "spe": 32}, "Life Orb")
        defender = _mon("Alakazam", "Timid", "Synchronize", {"hp": 0, "atk": 0, "def": 0, "spa": 32, "spd": 0, "spe": 32})

        resp = client.post("/api/calculate", json={"attacker": attacker, "defender": defender, "move_name": "Earthquake"})
        body = resp.json()

        expected = ko_chance(dex, attacker, defender, "Earthquake")
        got = {entry["hits"]: entry["probability"] for entry in body["ko_chances"]}
        assert got == pytest.approx(expected)
        # Hand-verified guaranteed OHKO (see tests/test_ko_chance.py) - a
        # real, unambiguous case rather than just "some probability".
        assert got == {1: pytest.approx(1.0)}

    def test_speeds_match_a_direct_engine_call(self, client, dex):
        from poke_calc.engine.build import build_mon, effective_speed
        from poke_calc.engine.models import FieldState

        attacker = _mon("Garchomp", "Jolly", "Rough Skin", {"hp": 0, "atk": 0, "def": 0, "spa": 0, "spd": 0, "spe": 32})
        defender = _mon("Tyranitar", "Careful", "Sand Stream", {"hp": 0, "atk": 0, "def": 0, "spa": 0, "spd": 0, "spe": 0})

        resp = client.post("/api/calculate", json={"attacker": attacker, "defender": defender, "move_name": "Earthquake"})
        body = resp.json()

        field = FieldState()
        expected_a_speed = effective_speed(build_mon(dex, **attacker, field=field), field)
        expected_b_speed = effective_speed(build_mon(dex, **defender, field=field), field)
        assert body["attacker_speed"] == expected_a_speed
        assert body["defender_speed"] == expected_b_speed
        assert body["attacker_speed"] > body["defender_speed"]  # Garchomp is faster by a wide margin here

    def test_defender_max_hp_matches_a_direct_engine_call(self, client, dex):
        from poke_calc.engine.build import build_mon
        from poke_calc.engine.models import FieldState

        attacker = _mon("Garchomp", "Jolly", "Rough Skin", {})
        defender = _mon("Tyranitar", "Careful", "Sand Stream", {"hp": 32, "atk": 0, "def": 0, "spa": 0, "spd": 0, "spe": 0})

        resp = client.post("/api/calculate", json={"attacker": attacker, "defender": defender, "move_name": "Earthquake"})
        body = resp.json()

        expected_hp = build_mon(dex, **defender, field=FieldState()).stats["hp"]
        assert body["defender_max_hp"] == expected_hp

    def test_sp_over_budget_returns_400(self, client):
        attacker = _mon("Garchomp", "Jolly", "Rough Skin", {"hp": 32, "atk": 32, "def": 32, "spa": 0, "spd": 0, "spe": 32})
        defender = _mon("Tyranitar", "Careful", "Sand Stream", {})
        resp = client.post("/api/calculate", json={"attacker": attacker, "defender": defender, "move_name": "Earthquake"})
        assert resp.status_code == 400
        assert "66-point budget" in resp.json()["detail"]

    def test_unknown_species_returns_400(self, client):
        attacker = _mon("NotAPokemon", "Jolly", "Rough Skin", {})
        defender = _mon("Tyranitar", "Careful", "Sand Stream", {})
        resp = client.post("/api/calculate", json={"attacker": attacker, "defender": defender, "move_name": "Earthquake"})
        assert resp.status_code == 400
        assert "not in the Champions roster" in resp.json()["detail"]

    def test_unknown_move_returns_400(self, client):
        attacker = _mon("Garchomp", "Jolly", "Rough Skin", {})
        defender = _mon("Tyranitar", "Careful", "Sand Stream", {})
        resp = client.post("/api/calculate", json={"attacker": attacker, "defender": defender, "move_name": "Not A Move"})
        assert resp.status_code == 400
        assert "not a legal Champions move" in resp.json()["detail"]


class TestSpeed:
    def test_matches_a_direct_engine_call_and_needs_no_move(self, client, dex):
        from poke_calc.engine.build import build_mon, effective_speed
        from poke_calc.engine.models import FieldState

        attacker = _mon("Garchomp", "Jolly", "Rough Skin", {"hp": 0, "atk": 0, "def": 0, "spa": 0, "spd": 0, "spe": 32})
        defender = _mon("Tyranitar", "Careful", "Sand Stream", {"hp": 0, "atk": 0, "def": 0, "spa": 0, "spd": 0, "spe": 0})

        resp = client.post("/api/speed", json={"attacker": attacker, "defender": defender})
        assert resp.status_code == 200
        body = resp.json()

        field = FieldState()
        expected_a = effective_speed(build_mon(dex, **attacker, field=field), field)
        expected_b = effective_speed(build_mon(dex, **defender, field=field), field)
        assert body["attacker_speed"] == expected_a
        assert body["defender_speed"] == expected_b

    def test_unknown_species_returns_400(self, client):
        attacker = _mon("NotAPokemon", "Jolly", "Rough Skin", {})
        defender = _mon("Tyranitar", "Careful", "Sand Stream", {})
        resp = client.post("/api/speed", json={"attacker": attacker, "defender": defender})
        assert resp.status_code == 400


class TestCalculateBatch:
    def test_matches_a_direct_moves_summary_call(self, client, dex):
        from poke_calc.engine.ko_chance import moves_summary

        attacker = _mon("Garchomp", "Jolly", "Rough Skin", {"hp": 0, "atk": 32, "def": 0, "spa": 0, "spd": 0, "spe": 32}, "Life Orb")
        defender = _mon("Snorlax", "Impish", "Thick Fat", {"hp": 32, "atk": 0, "def": 32, "spa": 0, "spd": 0, "spe": 0})
        move_names = ["Earthquake", "Dragon Claw"]

        resp = client.post("/api/calculate/batch", json={
            "attacker": attacker, "defender": defender, "move_names": move_names,
        })
        assert resp.status_code == 200
        rows = resp.json()["rows"]
        assert [r["move"] for r in rows] == move_names

        expected = moves_summary(dex, attacker, defender, move_names)
        eq_row = next(r for r in rows if r["move"] == "Earthquake")
        eq_expected = next(r for r in expected if r["Move"] == "Earthquake")
        assert eq_row["avg_damage_pct"] == pytest.approx(eq_expected["Avg Dmg %"])
        got_ohko = next(k["probability"] for k in eq_row["ko_chances"] if k["hits"] == 1)
        assert got_ohko == pytest.approx(eq_expected["OHKO %"])

    def test_empty_move_list_returns_empty_rows(self, client):
        attacker = _mon("Garchomp", "Jolly", "Rough Skin", {})
        defender = _mon("Tyranitar", "Careful", "Sand Stream", {})
        resp = client.post("/api/calculate/batch", json={"attacker": attacker, "defender": defender, "move_names": []})
        assert resp.status_code == 200
        assert resp.json()["rows"] == []


class TestTeams:
    def test_no_teams_initially(self, client):
        resp = client.get("/api/teams")
        assert resp.status_code == 200
        assert resp.json()["teams"] == {}

    def test_add_a_preset_creates_a_team(self, client):
        preset = {"label": "Scarf Chomp", "species": "Garchomp", "nature": "Jolly", "ability": "Rough Skin", "item": "Choice Scarf", "sp": {}}
        resp = client.put("/api/teams/My Team/presets", json=preset)
        assert resp.status_code == 200
        teams = resp.json()["teams"]
        assert [p["label"] for p in teams["My Team"]] == ["Scarf Chomp"]

    def test_adding_the_same_build_twice_is_rejected(self, client):
        preset = {"label": "First", "species": "Garchomp", "nature": "Jolly", "ability": "Rough Skin", "item": None, "sp": {}}
        client.put("/api/teams/My Team/presets", json=preset)

        duplicate = {**preset, "label": "Different Label, Same Build"}
        resp = client.put("/api/teams/My Team/presets", json=duplicate)
        assert resp.status_code == 409

        teams = client.get("/api/teams").json()["teams"]
        assert len(teams["My Team"]) == 1

    def test_delete_preset_removes_only_that_one(self, client):
        client.put("/api/teams/My Team/presets", json={"label": "A", "species": "Garchomp", "nature": "Jolly", "ability": "Rough Skin", "item": None, "sp": {}})
        client.put("/api/teams/My Team/presets", json={"label": "B", "species": "Tyranitar", "nature": "Adamant", "ability": "Sand Stream", "item": None, "sp": {}})

        resp = client.delete("/api/teams/My Team/presets/0")
        assert resp.status_code == 200
        teams = resp.json()["teams"]
        assert [p["label"] for p in teams["My Team"]] == ["B"]

    def test_delete_preset_404s_for_unknown_team_or_index(self, client):
        assert client.delete("/api/teams/Nonexistent/presets/0").status_code == 404
        client.put("/api/teams/My Team/presets", json={"label": "A", "species": "Garchomp", "nature": "Jolly", "ability": "Rough Skin", "item": None, "sp": {}})
        assert client.delete("/api/teams/My Team/presets/5").status_code == 404

    def test_delete_team_removes_it_entirely(self, client):
        client.put("/api/teams/My Team/presets", json={"label": "A", "species": "Garchomp", "nature": "Jolly", "ability": "Rough Skin", "item": None, "sp": {}})
        resp = client.delete("/api/teams/My Team")
        assert resp.status_code == 200
        assert resp.json()["teams"] == {}

    def test_delete_team_404s_for_unknown_team(self, client):
        assert client.delete("/api/teams/Nonexistent").status_code == 404
