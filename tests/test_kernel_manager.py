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
        assert len(info["files"]) == 1
        assert info["files"][0]["name"] == "test.bsp"

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
