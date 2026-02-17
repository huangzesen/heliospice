"""Tests for heliospice.kernel_manager — kernel download, cache, and loading."""

from unittest.mock import patch
import pytest


class TestKernelManager:
    @patch("heliospice.kernel_manager.spice")
    def test_load_kernel_idempotent(self, mock_spice, tmp_path):
        from heliospice.kernel_manager import KernelManager
        km = KernelManager(kernel_dir=tmp_path)

        fake_path = tmp_path / "test.tls"
        fake_path.write_text("fake kernel")

        km.load_kernel(fake_path)
        km.load_kernel(fake_path)  # second call should be no-op

        # furnsh should only be called once
        assert mock_spice.furnsh.call_count == 1

    @patch("heliospice.kernel_manager.spice")
    def test_unload_all(self, mock_spice, tmp_path):
        from heliospice.kernel_manager import KernelManager
        km = KernelManager(kernel_dir=tmp_path)

        fake_path = tmp_path / "test.tls"
        fake_path.write_text("fake kernel")
        km.load_kernel(fake_path)

        km.unload_all()

        mock_spice.kclear.assert_called_once()
        assert km.list_loaded() == []
        assert km._generic_loaded is False

    @patch("heliospice.kernel_manager.spice")
    def test_list_loaded(self, mock_spice, tmp_path):
        from heliospice.kernel_manager import KernelManager
        km = KernelManager(kernel_dir=tmp_path)

        f1 = tmp_path / "a.tls"
        f2 = tmp_path / "b.bsp"
        f1.write_text("fake")
        f2.write_text("fake")
        km.load_kernel(f1)
        km.load_kernel(f2)

        loaded = km.list_loaded()
        assert "a.tls" in loaded
        assert "b.bsp" in loaded

    @patch("heliospice.kernel_manager.spice")
    def test_cache_size(self, mock_spice, tmp_path):
        from heliospice.kernel_manager import KernelManager
        km = KernelManager(kernel_dir=tmp_path)

        f1 = tmp_path / "test.bsp"
        f1.write_bytes(b"x" * 1024)

        assert km.get_cache_size_bytes() == 1024

    @patch("heliospice.kernel_manager.spice")
    def test_cache_info(self, mock_spice, tmp_path):
        from heliospice.kernel_manager import KernelManager
        km = KernelManager(kernel_dir=tmp_path)

        f1 = tmp_path / "test.bsp"
        f1.write_bytes(b"x" * (1024 * 1024))  # 1 MB

        info = km.get_cache_info()
        assert info["file_count"] == 1
        assert info["total_size_mb"] >= 1.0
        # File grouped under UNKNOWN since test.bsp isn't a known kernel
        assert "UNKNOWN" in info["missions"]
        assert info["missions"]["UNKNOWN"]["file_count"] == 1
        assert info["missions"]["UNKNOWN"]["files"][0]["name"] == "test.bsp"

    @patch("heliospice.kernel_manager.spice")
    @patch("heliospice.kernel_manager.KernelManager.download_kernel")
    def test_ensure_generic_kernels_idempotent(self, mock_download, mock_spice, tmp_path):
        from heliospice.kernel_manager import KernelManager
        km = KernelManager(kernel_dir=tmp_path)

        # Mock download to return a fake path
        mock_download.return_value = tmp_path / "fake.tls"
        (tmp_path / "fake.tls").write_text("fake")

        km.ensure_generic_kernels()
        first_count = mock_download.call_count

        km.ensure_generic_kernels()  # should be no-op
        assert mock_download.call_count == first_count

    @patch("heliospice.kernel_manager.spice")
    @patch("heliospice.kernel_manager.KernelManager.download_kernel")
    def test_ensure_mission_kernels(self, mock_download, mock_spice, tmp_path):
        from heliospice.kernel_manager import KernelManager
        km = KernelManager(kernel_dir=tmp_path)

        mock_download.return_value = tmp_path / "fake.bsp"
        (tmp_path / "fake.bsp").write_text("fake")

        km.ensure_mission_kernels("PSP")
        assert "PSP" in km._mission_kernels_loaded

    @patch("heliospice.kernel_manager.spice")
    @patch("heliospice.kernel_manager.KernelManager.download_kernel")
    def test_ensure_mission_kernels_unknown(self, mock_download, mock_spice, tmp_path):
        from heliospice.kernel_manager import KernelManager
        km = KernelManager(kernel_dir=tmp_path)
        mock_download.return_value = tmp_path / "fake.tls"
        (tmp_path / "fake.tls").write_text("fake")

        with pytest.raises(KeyError, match="No SPICE kernels"):
            km.ensure_mission_kernels("UNKNOWN_MISSION")

    @patch("heliospice.kernel_manager.spice")
    def test_default_kernel_dir(self, mock_spice):
        """Default kernel dir is ~/.heliospice/kernels/."""
        from pathlib import Path
        from heliospice.kernel_manager import KernelManager
        km = KernelManager()
        expected = Path.home() / ".heliospice" / "kernels"
        assert km.kernel_dir == expected

    @patch("heliospice.kernel_manager.spice")
    def test_env_var_kernel_dir(self, mock_spice, tmp_path, monkeypatch):
        """HELIOSPICE_KERNEL_DIR env var overrides default."""
        from heliospice.kernel_manager import KernelManager
        custom_dir = tmp_path / "custom_kernels"
        custom_dir.mkdir()
        monkeypatch.setenv("HELIOSPICE_KERNEL_DIR", str(custom_dir))
        km = KernelManager()
        assert km.kernel_dir == custom_dir

    @patch("heliospice.kernel_manager.spice")
    def test_delete_cached_files(self, mock_spice, tmp_path):
        """delete_cached_files removes files and unloads from SPICE."""
        from heliospice.kernel_manager import KernelManager
        km = KernelManager(kernel_dir=tmp_path)

        f1 = tmp_path / "a.bsp"
        f2 = tmp_path / "b.bsp"
        f1.write_bytes(b"x" * (1024 * 1024))
        f2.write_bytes(b"y" * (1024 * 1024))
        km.load_kernel(f1)

        result = km.delete_cached_files(["a.bsp", "b.bsp"])
        assert "a.bsp" in result["deleted"]
        assert "b.bsp" in result["deleted"]
        assert result["freed_mb"] >= 2.0
        assert not f1.exists()
        assert not f2.exists()
        assert str(f1.resolve()) not in km._loaded_kernels

    @patch("heliospice.kernel_manager.spice")
    def test_delete_cached_files_not_found(self, mock_spice, tmp_path):
        """delete_cached_files reports errors for missing files."""
        from heliospice.kernel_manager import KernelManager
        km = KernelManager(kernel_dir=tmp_path)

        result = km.delete_cached_files(["nonexistent.bsp"])
        assert result["deleted"] == []
        assert "errors" in result
        assert any("not found" in e for e in result["errors"])

    @patch("heliospice.kernel_manager.spice")
    def test_purge_cache(self, mock_spice, tmp_path):
        """purge_cache removes all files and clears state."""
        from heliospice.kernel_manager import KernelManager
        km = KernelManager(kernel_dir=tmp_path)

        for name in ["a.bsp", "b.bsp", "c.tls"]:
            (tmp_path / name).write_bytes(b"x" * (1024 * 1024))
            km.load_kernel(tmp_path / name)

        result = km.purge_cache()
        assert result["deleted_count"] == 3
        assert result["freed_mb"] >= 3.0
        assert km.list_loaded() == []
        assert list(tmp_path.iterdir()) == []

    @patch("heliospice.kernel_manager.spice")
    def test_cache_info_groups_by_mission(self, mock_spice, tmp_path):
        """get_cache_info groups files by mission."""
        from heliospice.kernel_manager import KernelManager
        km = KernelManager(kernel_dir=tmp_path)

        # Create a file matching a generic kernel name
        (tmp_path / "naif0012.tls").write_bytes(b"x" * 100)
        # Create an unknown file
        (tmp_path / "random.bsp").write_bytes(b"y" * 200)

        info = km.get_cache_info()
        assert "GENERIC" in info["missions"]
        assert "UNKNOWN" in info["missions"]
        assert info["missions"]["GENERIC"]["file_count"] == 1
        assert info["file_count"] == 2


class TestCheckRemoteKernels:
    """Tests for KernelManager.check_remote_kernels()."""

    NAIF_HTML = """<!DOCTYPE HTML PUBLIC "-//W3C//DTD HTML 3.2 Final//EN">
<html><head><title>Index of /pub/naif/JUNO/kernels/spk</title></head>
<body><h1>Index of /pub/naif/JUNO/kernels/spk</h1>
<pre><a href="/">Parent Directory</a>
<a href="juno_rec_orbit.bsp">juno_rec_orbit.bsp</a>         2024-03-15 12:00  129M
<a href="juno_pred_orbit.bsp">juno_pred_orbit.bsp</a>       2024-03-15 12:00   15M
<a href="juno_rec_orbit_v2.bsp">juno_rec_orbit_v2.bsp</a>   2024-06-01 10:00  135M
<a href="README.txt">README.txt</a>                         2024-01-01 00:00  1.2K
</pre></body></html>"""

    @patch("heliospice.kernel_manager.spice")
    @patch("requests.get")
    def test_parses_directory_and_finds_other_files(self, mock_get, mock_spice, tmp_path):
        """Parses NAIF HTML listing and identifies other_files correctly."""
        from heliospice.kernel_manager import KernelManager
        km = KernelManager(kernel_dir=tmp_path)

        mock_resp = mock_get.return_value
        mock_resp.raise_for_status.return_value = None
        mock_resp.text = self.NAIF_HTML

        result = km.check_remote_kernels("JUNO")

        assert result["mission"] == "JUNO"
        assert "juno_rec_orbit.bsp" in result["configured_files"]
        assert len(result["directories"]) == 1
        # The directory should contain all 3 .bsp files
        all_bsp = result["directories"][0]["all_bsp_files"]
        assert "juno_rec_orbit.bsp" in all_bsp
        assert "juno_pred_orbit.bsp" in all_bsp
        assert "juno_rec_orbit_v2.bsp" in all_bsp
        # README.txt should NOT be in .bsp list
        assert "README.txt" not in all_bsp
        # other_files = .bsp files NOT in configured set
        assert "juno_pred_orbit.bsp" in result["other_files"]
        assert "juno_rec_orbit_v2.bsp" in result["other_files"]
        assert "juno_rec_orbit.bsp" not in result["other_files"]

    @patch("heliospice.kernel_manager.spice")
    @patch("requests.get")
    def test_filters_only_bsp_files(self, mock_get, mock_spice, tmp_path):
        """Only .bsp files are included, not .txt or other extensions."""
        from heliospice.kernel_manager import KernelManager
        km = KernelManager(kernel_dir=tmp_path)

        html = """<html><body><pre>
<a href="kernel.bsp">kernel.bsp</a>
<a href="kernel.BSP">kernel.BSP</a>
<a href="readme.txt">readme.txt</a>
<a href="data.csv">data.csv</a>
<a href="notes.tls">notes.tls</a>
</pre></body></html>"""

        mock_resp = mock_get.return_value
        mock_resp.raise_for_status.return_value = None
        mock_resp.text = html

        result = km.check_remote_kernels("JUNO")

        all_bsp = result["directories"][0]["all_bsp_files"]
        assert "kernel.bsp" in all_bsp
        assert "kernel.BSP" in all_bsp
        assert "readme.txt" not in all_bsp
        assert "data.csv" not in all_bsp
        assert "notes.tls" not in all_bsp

    @patch("heliospice.kernel_manager.spice")
    @patch("requests.get")
    def test_handles_http_error_gracefully(self, mock_get, mock_spice, tmp_path):
        """HTTP errors are captured in the result, not raised as exceptions."""
        from heliospice.kernel_manager import KernelManager
        km = KernelManager(kernel_dir=tmp_path)

        mock_get.return_value.raise_for_status.side_effect = Exception("404 Not Found")

        result = km.check_remote_kernels("JUNO")

        assert result["mission"] == "JUNO"
        assert len(result["directories"]) == 1
        assert "error" in result["directories"][0]
        assert "404" in result["directories"][0]["error"]
        assert result["directories"][0]["all_bsp_files"] == []

    @patch("heliospice.kernel_manager.spice")
    def test_raises_keyerror_for_segmented_mission(self, mock_spice, tmp_path):
        """Raises KeyError when called with a segmented mission."""
        from heliospice.kernel_manager import KernelManager
        km = KernelManager(kernel_dir=tmp_path)

        with pytest.raises(KeyError, match="segmented kernels"):
            km.check_remote_kernels("CASSINI")
