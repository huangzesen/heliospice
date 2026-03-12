"""Tests for xhelio_spice.missions — mission registry and name resolution."""

import pytest


class TestMissions:
    def test_resolve_mission_direct(self):
        from xhelio_spice.missions import resolve_mission
        naif_id, key = resolve_mission("PSP")
        assert naif_id == -96
        assert key == "PSP"

    def test_resolve_mission_case_insensitive(self):
        from xhelio_spice.missions import resolve_mission
        naif_id, key = resolve_mission("psp")
        assert naif_id == -96
        assert key == "PSP"

    def test_resolve_mission_alias(self):
        from xhelio_spice.missions import resolve_mission
        naif_id, key = resolve_mission("Parker Solar Probe")
        assert naif_id == -96
        assert key == "PSP"

    def test_resolve_mission_alias_solar_orbiter(self):
        from xhelio_spice.missions import resolve_mission
        naif_id, key = resolve_mission("Solar Orbiter")
        assert naif_id == -144
        assert key == "SOLO"

    def test_resolve_mission_alias_voyager(self):
        from xhelio_spice.missions import resolve_mission
        naif_id, key = resolve_mission("Voyager 1")
        assert naif_id == -31
        assert key == "VOYAGER_1"

    def test_resolve_mission_natural_body(self):
        from xhelio_spice.missions import resolve_mission
        naif_id, key = resolve_mission("Earth")
        assert naif_id == 399
        assert key == "EARTH"

    def test_resolve_mission_unknown(self):
        from xhelio_spice.missions import resolve_mission
        with pytest.raises(KeyError, match="Unknown mission"):
            resolve_mission("NONEXISTENT_SPACECRAFT")

    def test_list_supported_missions(self):
        from xhelio_spice.missions import list_supported_missions
        missions = list_supported_missions()
        assert len(missions) > 0
        # All should be spacecraft (negative NAIF IDs)
        for m in missions:
            assert m["naif_id"] < 0
            assert "mission_key" in m
            assert "has_kernels" in m

    def test_list_includes_psp(self):
        from xhelio_spice.missions import list_supported_missions
        missions = list_supported_missions()
        keys = [m["mission_key"] for m in missions]
        assert "PSP" in keys
        # PSP should have kernels defined
        psp = [m for m in missions if m["mission_key"] == "PSP"][0]
        assert psp["has_kernels"] is True


class TestNewMissionResolution:
    """Tests for newly added missions."""

    @pytest.mark.parametrize("name,expected_id,expected_key", [
        # Planetary flagships
        ("ROSETTA", -226, "ROSETTA"),
        ("NEAR", -93, "NEAR"),
        ("DEEP_IMPACT", -140, "DEEP_IMPACT"),
        ("EPOXI", -140, "EPOXI"),
        ("CLEMENTINE", -40, "CLEMENTINE"),
        ("DEEP_SPACE_1", -30, "DEEP_SPACE_1"),
        ("MSL", -76, "MSL"),
        ("HAYABUSA", -130, "HAYABUSA"),
        ("OSIRIS_REX", -64, "OSIRIS_REX"),
        ("MEX", -41, "MEX"),
        ("PHOENIX", -84, "PHOENIX"),
        ("VIKING_1", -27, "VIKING_1"),
        ("VIKING_2", -30, "VIKING_2"),
        ("MER_SPIRIT", -253, "MER_SPIRIT"),
        ("MER_OPPORTUNITY", -254, "MER_OPPORTUNITY"),
        # Observatories
        ("JWST", -170, "JWST"),
        ("HST", -48, "HST"),
        ("CHANDRA", -151, "CHANDRA"),
        ("SPITZER", -79, "SPITZER"),
        ("GAIA", -123, "GAIA"),
        ("EUCLID", -171, "EUCLID"),
        ("INTEGRAL", -198, "INTEGRAL"),
        # Historic / small
        ("GENESIS", -47, "GENESIS"),
        ("GIOTTO", -78, "GIOTTO"),
        ("MARINER_9", -9, "MARINER_9"),
        ("MARINER_10", -10, "MARINER_10"),
        ("VEGA_1", -11, "VEGA_1"),
        ("SMART_1", -238, "SMART_1"),
        ("CONTOUR", -36, "CONTOUR"),
        ("IUE", -43, "IUE"),
        ("PIONEER_6", -6, "PIONEER_6"),
        ("PIONEER_8", -8, "PIONEER_8"),
        ("LUNAR_ORBITER_1", -1, "LUNAR_ORBITER_1"),
        ("LUNAR_ORBITER_2", -2, "LUNAR_ORBITER_2"),
        ("LUNAR_ORBITER_3", -3, "LUNAR_ORBITER_3"),
        ("LUNAR_ORBITER_4", -4, "LUNAR_ORBITER_4"),
        ("LUNAR_ORBITER_5", -5, "LUNAR_ORBITER_5"),
        ("HERA", -658, "HERA"),
        ("LADEE", -397, "LADEE"),
        ("GRAIL_B", -178, "GRAIL_B"),
        # Segmented
        ("MARS_ODYSSEY", -53, "MARS_ODYSSEY"),
        ("STARDUST", -29, "STARDUST"),
        ("AKATSUKI", -5, "AKATSUKI"),
        ("GRAIL_A", -177, "GRAIL_A"),
        ("MAGELLAN", -18, "MAGELLAN"),
        ("EXOMARS_TGO", -143, "EXOMARS_TGO"),
        ("CHANDRAYAAN_1", -86, "CHANDRAYAAN_1"),
    ])
    def test_resolve_new_mission(self, name, expected_id, expected_key):
        from xhelio_spice.missions import resolve_mission
        naif_id, key = resolve_mission(name)
        assert naif_id == expected_id
        assert key == expected_key

    @pytest.mark.parametrize("alias,expected_key", [
        ("Curiosity", "MSL"),
        ("Mars Science Laboratory", "MSL"),
        ("NEAR Shoemaker", "NEAR"),
        ("NEAR_SHOEMAKER", "NEAR"),
        ("James Webb", "JWST"),
        ("James Webb Space Telescope", "JWST"),
        ("Webb", "JWST"),
        ("Hubble", "HST"),
        ("Hubble Space Telescope", "HST"),
        ("Mars Express", "MEX"),
        ("MARS_EXPRESS", "MEX"),
        ("Spirit", "MER_SPIRIT"),
        ("MER1", "MER_SPIRIT"),
        ("MER-1", "MER_SPIRIT"),
        ("MER A", "MER_SPIRIT"),
        ("Opportunity", "MER_OPPORTUNITY"),
        ("MER2", "MER_OPPORTUNITY"),
        ("MER-2", "MER_OPPORTUNITY"),
        ("MER B", "MER_OPPORTUNITY"),
        ("Viking 1", "VIKING_1"),
        ("Viking 2", "VIKING_2"),
        ("Viking Orbiter 1", "VIKING_1"),
        ("Viking Orbiter 2", "VIKING_2"),
        ("DS1", "DEEP_SPACE_1"),
        ("DS-1", "DEEP_SPACE_1"),
        ("Deep Space One", "DEEP_SPACE_1"),
        ("DI", "DEEP_IMPACT"),
        ("Deep Impact", "DEEP_IMPACT"),
        ("EPOXI", "EPOXI"),
        ("DIF", "EPOXI"),
        ("GRAIL B", "GRAIL_B"),
        ("GRAIL Flow", "GRAIL_B"),
        ("OSIRIS-REx", "OSIRIS_REX"),
        ("ORX", "OSIRIS_REX"),
        ("OSIRIS-APEX", "OSIRIS_REX"),
        ("Hayabusa 1", "HAYABUSA"),
        ("MUSES-C", "HAYABUSA"),
        ("Mariner 9", "MARINER_9"),
        ("Mariner 10", "MARINER_10"),
        ("Vega 1", "VEGA_1"),
        ("LO1", "LUNAR_ORBITER_1"),
        ("LO2", "LUNAR_ORBITER_2"),
        ("LO3", "LUNAR_ORBITER_3"),
        ("LO4", "LUNAR_ORBITER_4"),
        ("LO5", "LUNAR_ORBITER_5"),
        ("Lunar Orbiter 1", "LUNAR_ORBITER_1"),
        ("SMART1", "SMART_1"),
        ("SMART-1", "SMART_1"),
    ])
    def test_resolve_alias(self, alias, expected_key):
        from xhelio_spice.missions import resolve_mission
        _, key = resolve_mission(alias)
        assert key == expected_key


class TestNewMissionKernels:
    """Tests that new missions have kernel support."""

    @pytest.mark.parametrize("mission_key", [
        "ROSETTA", "NEAR", "DEEP_IMPACT", "EPOXI", "CLEMENTINE",
        "DEEP_SPACE_1", "MSL", "HAYABUSA", "JWST", "HST",
        "CHANDRA", "SPITZER", "GENESIS", "GIOTTO",
        "MARINER_9", "MARINER_10", "VEGA_1", "PHOENIX",
        "VIKING_1", "VIKING_2", "MER_SPIRIT", "MER_OPPORTUNITY",
        "SMART_1", "CONTOUR", "IUE", "PIONEER_6", "PIONEER_8",
        "LUNAR_ORBITER_1", "LUNAR_ORBITER_2", "LUNAR_ORBITER_3",
        "LUNAR_ORBITER_4", "LUNAR_ORBITER_5",
        "INTEGRAL", "GAIA", "EUCLID", "HERA", "LADEE",
        "OSIRIS_REX", "MEX",
    ])
    def test_has_kernels(self, mission_key):
        from xhelio_spice.missions import has_kernels
        assert has_kernels(mission_key) is True, f"{mission_key} should have kernels"

    def test_kernel_urls_are_strings(self):
        from xhelio_spice.missions import MISSION_KERNELS
        for mission, kernels in MISSION_KERNELS.items():
            for filename, url in kernels.items():
                assert isinstance(url, str), f"{mission}/{filename} URL is not a string"
                assert url.startswith("http"), f"{mission}/{filename} URL doesn't start with http"
                assert url.endswith(".bsp") or url.endswith(".BSP"), \
                    f"{mission}/{filename} URL doesn't end with .bsp"


class TestDawnKernelFix:
    def test_dawn_kernel_is_full_trajectory(self):
        """Dawn kernel should be the full predict trajectory, not the 23 KB stub."""
        from xhelio_spice.missions import MISSION_KERNELS
        dawn_files = list(MISSION_KERNELS["DAWN"].keys())
        assert "dawn_ephem_2018.bsp" not in dawn_files
        assert "dawn_p_181030-431030_181211_v1.bsp" in dawn_files
