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
