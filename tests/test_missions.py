"""Tests for heliospice.missions — mission registry and name resolution."""

import pytest


class TestMissions:
    def test_resolve_mission_direct(self):
        from heliospice.missions import resolve_mission
        naif_id, key = resolve_mission("PSP")
        assert naif_id == -96
        assert key == "PSP"

    def test_resolve_mission_case_insensitive(self):
        from heliospice.missions import resolve_mission
        naif_id, key = resolve_mission("psp")
        assert naif_id == -96
        assert key == "PSP"

    def test_resolve_mission_alias(self):
        from heliospice.missions import resolve_mission
        naif_id, key = resolve_mission("Parker Solar Probe")
        assert naif_id == -96
        assert key == "PSP"

    def test_resolve_mission_alias_solar_orbiter(self):
        from heliospice.missions import resolve_mission
        naif_id, key = resolve_mission("Solar Orbiter")
        assert naif_id == -144
        assert key == "SOLO"

    def test_resolve_mission_alias_voyager(self):
        from heliospice.missions import resolve_mission
        naif_id, key = resolve_mission("Voyager 1")
        assert naif_id == -31
        assert key == "VOYAGER_1"

    def test_resolve_mission_natural_body(self):
        from heliospice.missions import resolve_mission
        naif_id, key = resolve_mission("Earth")
        assert naif_id == 399
        assert key == "EARTH"

    def test_resolve_mission_unknown(self):
        from heliospice.missions import resolve_mission
        with pytest.raises(KeyError, match="Unknown mission"):
            resolve_mission("NONEXISTENT_SPACECRAFT")

    def test_list_supported_missions(self):
        from heliospice.missions import list_supported_missions
        missions = list_supported_missions()
        assert len(missions) > 0
        # All should be spacecraft (negative NAIF IDs)
        for m in missions:
            assert m["naif_id"] < 0
            assert "mission_key" in m
            assert "has_kernels" in m

    def test_list_includes_psp(self):
        from heliospice.missions import list_supported_missions
        missions = list_supported_missions()
        keys = [m["mission_key"] for m in missions]
        assert "PSP" in keys
        # PSP should have kernels defined
        psp = [m for m in missions if m["mission_key"] == "PSP"][0]
        assert psp["has_kernels"] is True
