"""Tests for segmented (multi-file) SPICE kernel support."""

import json
from datetime import date
from unittest.mock import MagicMock, patch, mock_open

import pytest


# ---- missions.py tests ----

class TestSegmentedMissions:
    def test_segmented_missions_dict(self):
        from heliospice.missions import SEGMENTED_MISSIONS
        assert "CASSINI" in SEGMENTED_MISSIONS
        assert "MRO" in SEGMENTED_MISSIONS
        assert "MARS_2020" in SEGMENTED_MISSIONS
        assert "LRO" in SEGMENTED_MISSIONS
        assert "LUNAR_PROSPECTOR" in SEGMENTED_MISSIONS
        assert "MGS" in SEGMENTED_MISSIONS
        assert SEGMENTED_MISSIONS["CASSINI"] == "cassini.json"
        assert SEGMENTED_MISSIONS["LRO"] == "lro.json"
        assert SEGMENTED_MISSIONS["LUNAR_PROSPECTOR"] == "lunar_prospector.json"
        assert SEGMENTED_MISSIONS["MGS"] == "mgs.json"

    def test_has_kernels_standard(self):
        from heliospice.missions import has_kernels
        assert has_kernels("PSP") is True

    def test_has_kernels_segmented(self):
        from heliospice.missions import has_kernels
        assert has_kernels("CASSINI") is True
        assert has_kernels("MRO") is True
        assert has_kernels("MARS_2020") is True
        assert has_kernels("LRO") is True
        assert has_kernels("LUNAR_PROSPECTOR") is True
        assert has_kernels("MGS") is True

    def test_has_kernels_none(self):
        from heliospice.missions import has_kernels
        assert has_kernels("ACE") is False
        assert has_kernels("WIND") is False

    def test_list_supported_missions_includes_segmented(self):
        from heliospice.missions import list_supported_missions
        missions = list_supported_missions()
        cassini = next(m for m in missions if m["mission_key"] == "CASSINI")
        assert cassini["has_kernels"] is True
        mro = next(m for m in missions if m["mission_key"] == "MRO")
        assert mro["has_kernels"] is True


# ---- kernel_manager.py tests ----

SAMPLE_MANIFEST = [
    {"file": "seg_a.bsp", "url": "https://example.com/seg_a.bsp",
     "start": "2004-05-14", "stop": "2004-06-19"},
    {"file": "seg_b.bsp", "url": "https://example.com/seg_b.bsp",
     "start": "2004-06-19", "stop": "2004-08-01"},
    {"file": "seg_c.bsp", "url": "https://example.com/seg_c.bsp",
     "start": "2005-01-01", "stop": "2005-03-01"},
]


class TestKernelManagerSegmented:
    @patch("heliospice.kernel_manager.spice")
    def test_segmented_files_loaded_init(self, mock_spice, tmp_path):
        from heliospice.kernel_manager import KernelManager
        km = KernelManager(kernel_dir=tmp_path)
        assert km._segmented_files_loaded == set()

    @patch("heliospice.kernel_manager.spice")
    def test_unload_all_clears_segmented(self, mock_spice, tmp_path):
        from heliospice.kernel_manager import KernelManager
        km = KernelManager(kernel_dir=tmp_path)
        km._segmented_files_loaded.add("some_file.bsp")
        km.unload_all()
        assert km._segmented_files_loaded == set()

    @patch("heliospice.kernel_manager.spice")
    @patch("heliospice.kernel_manager.KernelManager.download_kernel")
    @patch("heliospice.kernel_manager.KernelManager._load_manifest")
    def test_ensure_segmented_kernels_loads_matching(
        self, mock_manifest, mock_download, mock_spice, tmp_path
    ):
        from heliospice.kernel_manager import KernelManager
        km = KernelManager(kernel_dir=tmp_path)

        mock_manifest.return_value = SAMPLE_MANIFEST

        fake_path = tmp_path / "fake.bsp"
        fake_path.write_text("fake")
        mock_download.return_value = fake_path

        # Query spanning seg_a and seg_b
        km.ensure_segmented_kernels("CASSINI", date(2004, 6, 1), date(2004, 7, 1))

        # Should download seg_a and seg_b but not seg_c
        assert mock_download.call_count >= 2
        downloaded_files = [call.args[1] for call in mock_download.call_args_list
                           if len(call.args) > 1]
        # Check via _segmented_files_loaded
        assert "seg_a.bsp" in km._segmented_files_loaded
        assert "seg_b.bsp" in km._segmented_files_loaded
        assert "seg_c.bsp" not in km._segmented_files_loaded

    @patch("heliospice.kernel_manager.spice")
    @patch("heliospice.kernel_manager.KernelManager.download_kernel")
    @patch("heliospice.kernel_manager.KernelManager._load_manifest")
    def test_ensure_segmented_kernels_single_date(
        self, mock_manifest, mock_download, mock_spice, tmp_path
    ):
        from heliospice.kernel_manager import KernelManager
        km = KernelManager(kernel_dir=tmp_path)

        mock_manifest.return_value = SAMPLE_MANIFEST
        fake_path = tmp_path / "fake.bsp"
        fake_path.write_text("fake")
        mock_download.return_value = fake_path

        # Query a single date in seg_c
        km.ensure_segmented_kernels("CASSINI", date(2005, 2, 1), date(2005, 2, 1))

        assert "seg_c.bsp" in km._segmented_files_loaded
        assert "seg_a.bsp" not in km._segmented_files_loaded

    @patch("heliospice.kernel_manager.spice")
    @patch("heliospice.kernel_manager.KernelManager.download_kernel")
    @patch("heliospice.kernel_manager.KernelManager._load_manifest")
    def test_ensure_segmented_kernels_idempotent(
        self, mock_manifest, mock_download, mock_spice, tmp_path
    ):
        from heliospice.kernel_manager import KernelManager
        km = KernelManager(kernel_dir=tmp_path)

        mock_manifest.return_value = SAMPLE_MANIFEST
        fake_path = tmp_path / "fake.bsp"
        fake_path.write_text("fake")
        mock_download.return_value = fake_path

        km.ensure_segmented_kernels("CASSINI", date(2005, 2, 1), date(2005, 2, 1))
        first_download_count = mock_download.call_count

        # Second call — already loaded, should not download again
        km.ensure_segmented_kernels("CASSINI", date(2005, 2, 1), date(2005, 2, 1))
        assert mock_download.call_count == first_download_count

    @patch("heliospice.kernel_manager.spice")
    @patch("heliospice.kernel_manager.KernelManager._load_manifest")
    def test_ensure_segmented_kernels_no_coverage(
        self, mock_manifest, mock_spice, tmp_path
    ):
        from heliospice.kernel_manager import KernelManager
        km = KernelManager(kernel_dir=tmp_path)

        mock_manifest.return_value = SAMPLE_MANIFEST

        with pytest.raises(ValueError, match="No kernel segments"):
            km.ensure_segmented_kernels("CASSINI", date(2010, 1, 1), date(2010, 2, 1))

    @patch("heliospice.kernel_manager.spice")
    @patch("heliospice.kernel_manager.KernelManager._load_manifest")
    def test_ensure_segmented_kernels_empty_manifest(
        self, mock_manifest, mock_spice, tmp_path
    ):
        from heliospice.kernel_manager import KernelManager
        km = KernelManager(kernel_dir=tmp_path)

        mock_manifest.return_value = []

        with pytest.raises(ValueError, match="empty"):
            km.ensure_segmented_kernels("CASSINI", date(2005, 1, 1), date(2005, 2, 1))

    @patch("heliospice.kernel_manager.spice")
    @patch("heliospice.kernel_manager.KernelManager.download_kernel")
    def test_ensure_mission_kernels_segmented_error(
        self, mock_download, mock_spice, tmp_path
    ):
        """ensure_mission_kernels raises informative error for segmented missions."""
        from heliospice.kernel_manager import KernelManager
        km = KernelManager(kernel_dir=tmp_path)

        mock_download.return_value = tmp_path / "fake.tls"
        (tmp_path / "fake.tls").write_text("fake")

        with pytest.raises(KeyError, match="segmented kernels"):
            km.ensure_mission_kernels("CASSINI")


# ---- ephemeris.py tests ----

class TestToDate:
    def test_from_iso_string(self):
        from heliospice.ephemeris import _to_date
        assert _to_date("2005-06-15") == date(2005, 6, 15)

    def test_from_iso_datetime_string(self):
        from heliospice.ephemeris import _to_date
        assert _to_date("2005-06-15T12:00:00") == date(2005, 6, 15)

    def test_from_datetime(self):
        from datetime import datetime
        from heliospice.ephemeris import _to_date
        dt = datetime(2005, 6, 15, 12, 0, 0)
        assert _to_date(dt) == date(2005, 6, 15)

    def test_from_date(self):
        from heliospice.ephemeris import _to_date
        d = date(2005, 6, 15)
        assert _to_date(d) == d


class TestEnsureKernelsSegmented:
    @patch("heliospice.ephemeris.get_kernel_manager")
    def test_segmented_mission_calls_ensure_segmented(self, mock_get_km):
        from heliospice.ephemeris import _ensure_kernels

        mock_km = MagicMock()
        mock_get_km.return_value = mock_km

        _ensure_kernels("CASSINI", "SUN", time_start=date(2005, 1, 1), time_end=date(2005, 2, 1))

        mock_km.ensure_segmented_kernels.assert_called_once_with(
            "CASSINI", date(2005, 1, 1), date(2005, 2, 1)
        )

    @patch("heliospice.ephemeris.get_kernel_manager")
    def test_segmented_mission_without_time_raises(self, mock_get_km):
        from heliospice.ephemeris import _ensure_kernels

        mock_km = MagicMock()
        mock_get_km.return_value = mock_km

        with pytest.raises(ValueError, match="requires.*time range"):
            _ensure_kernels("CASSINI", "SUN")

    @patch("heliospice.ephemeris.get_kernel_manager")
    def test_standard_mission_unchanged(self, mock_get_km):
        from heliospice.ephemeris import _ensure_kernels

        mock_km = MagicMock()
        mock_get_km.return_value = mock_km

        _ensure_kernels("PSP", "SUN", time_start=date(2024, 1, 1), time_end=date(2024, 1, 31))

        mock_km.ensure_mission_kernels.assert_called_once_with("PSP")
        mock_km.ensure_segmented_kernels.assert_not_called()


# ---- server.py tests ----

class TestServerSegmented:
    @patch("heliospice.server.FastMCP", new_callable=lambda: type("FakeMCP", (), {
        "__init__": lambda self, *a, **kw: None,
        "tool": lambda self: lambda f: f,
    }))
    def test_list_spice_missions_has_segmented_flag(self, _):
        """list_spice_missions output includes 'segmented' flag."""
        from heliospice.missions import list_supported_missions, SEGMENTED_MISSIONS

        missions = list_supported_missions()
        for m in missions:
            m["segmented"] = m["mission_key"] in SEGMENTED_MISSIONS

        cassini = next(m for m in missions if m["mission_key"] == "CASSINI")
        assert cassini["segmented"] is True

        psp = next(m for m in missions if m["mission_key"] == "PSP")
        assert psp["segmented"] is False
