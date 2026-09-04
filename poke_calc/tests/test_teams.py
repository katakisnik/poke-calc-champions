import pytest

from poke_calc.data import teams as teams_module
from poke_calc.data.teams import Preset, add_preset, delete_preset, delete_team, load_teams, save_teams


@pytest.fixture(autouse=True)
def isolated_teams_file(tmp_path, monkeypatch):
    """Every test gets its own throwaway teams.json - never touch the
    real user's saved teams."""
    monkeypatch.setattr(teams_module, "TEAMS_PATH", tmp_path / "teams.json")


def _preset(label="Scarf Chomp", species="Garchomp") -> Preset:
    return Preset(
        label=label, species=species, nature="Jolly", ability="Rough Skin",
        item="Choice Scarf", sp={"hp": 2, "atk": 32, "def": 0, "spa": 0, "spd": 0, "spe": 32},
    )


class TestLoadTeams:
    def test_missing_file_loads_as_empty(self):
        assert load_teams() == {}


class TestSaveAndLoadRoundTrip:
    def test_round_trips_a_team_with_a_preset(self):
        preset = _preset()
        save_teams({"My VGC Team": [preset]})
        loaded = load_teams()
        assert loaded == {"My VGC Team": [preset]}

    def test_round_trips_multiple_teams_and_presets(self):
        team_a = [_preset("Scarf Chomp", "Garchomp"), _preset("Sash Zam", "Alakazam")]
        team_b = [_preset("Sand Tar", "Tyranitar")]
        save_teams({"Team A": team_a, "Team B": team_b})
        assert load_teams() == {"Team A": team_a, "Team B": team_b}


class TestAddPreset:
    def test_creates_a_new_team(self):
        teams = add_preset({}, "New Team", _preset())
        assert teams == {"New Team": [_preset()]}

    def test_appends_to_an_existing_team_without_overwriting(self):
        existing = {"Team A": [_preset("First", "Garchomp")]}
        updated = add_preset(existing, "Team A", _preset("Second", "Tyranitar"))
        assert [p.label for p in updated["Team A"]] == ["First", "Second"]

    def test_does_not_mutate_the_input_dict(self):
        existing = {"Team A": [_preset()]}
        add_preset(existing, "Team A", _preset("Second"))
        assert len(existing["Team A"]) == 1


class TestDeletePreset:
    def test_removes_only_the_targeted_preset(self):
        teams = {"Team A": [_preset("First", "Garchomp"), _preset("Second", "Tyranitar")]}
        updated = delete_preset(teams, "Team A", 0)
        assert [p.label for p in updated["Team A"]] == ["Second"]

    def test_deleting_the_last_preset_leaves_an_empty_team_not_a_deleted_one(self):
        teams = {"Team A": [_preset()]}
        updated = delete_preset(teams, "Team A", 0)
        assert updated == {"Team A": []}

    def test_other_teams_are_untouched(self):
        teams = {"Team A": [_preset()], "Team B": [_preset("Other", "Tyranitar")]}
        updated = delete_preset(teams, "Team A", 0)
        assert updated["Team B"] == [_preset("Other", "Tyranitar")]


class TestDeleteTeam:
    def test_removes_the_whole_team(self):
        teams = {"Team A": [_preset()], "Team B": [_preset("Other", "Tyranitar")]}
        updated = delete_team(teams, "Team A")
        assert updated == {"Team B": [_preset("Other", "Tyranitar")]}
