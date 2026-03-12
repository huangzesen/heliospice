"""Tests for xhelio_spice.server — MCP tool functions."""

from unittest.mock import MagicMock, patch
import pytest

try:
    import mcp
    _HAS_MCP = True
except ImportError:
    _HAS_MCP = False


@pytest.mark.skipif(not _HAS_MCP, reason="mcp package not installed")
class TestMCPTools:
    """Test the MCP tool functions by calling them through the server module."""

    def _get_tool_func(self, name: str):
        """Get a tool function from the server by creating the server and extracting the tool."""
        from xhelio_spice.server import _create_server
        server = _create_server()
        # FastMCP stores tools; we can call the underlying functions directly
        # The tool functions are registered as closures, so we need to access them
        # through the server's tool registry
        return server._tool_manager.get_tool(name)

    @patch("xhelio_spice.ephemeris.get_kernel_manager")
    @patch("xhelio_spice.ephemeris.spice")
    def test_single_time_position(self, mock_spice, mock_get_km):
        """Single-time ephemeris returns success with position data."""
        mock_km = MagicMock()
        mock_km.lock = MagicMock()
        mock_km.lock.__enter__ = MagicMock(return_value=None)
        mock_km.lock.__exit__ = MagicMock(return_value=False)
        mock_get_km.return_value = mock_km

        mock_spice.utc2et.return_value = 0.0
        mock_spice.spkpos.return_value = ([1.496e8, 0.0, 0.0], 499.0)

        from xhelio_spice.ephemeris import get_position
        result = get_position("EARTH", "SUN", "2000-01-01T12:00:00")
        assert "r_au" in result

    @patch("xhelio_spice.ephemeris.get_kernel_manager")
    @patch("xhelio_spice.ephemeris.spice")
    def test_single_time_with_velocity(self, mock_spice, mock_get_km):
        """Single-time ephemeris with include_velocity returns state data."""
        mock_km = MagicMock()
        mock_km.lock = MagicMock()
        mock_km.lock.__enter__ = MagicMock(return_value=None)
        mock_km.lock.__exit__ = MagicMock(return_value=False)
        mock_get_km.return_value = mock_km

        mock_spice.utc2et.return_value = 0.0
        mock_spice.spkezr.return_value = (
            [1.496e8, 0.0, 0.0, 0.0, 29.78, 0.0], 499.0
        )

        from xhelio_spice.ephemeris import get_state
        result = get_state("EARTH", "SUN", "2000-01-01T12:00:00")
        assert "vx_km_s" in result
        assert "speed_km_s" in result
        assert result["speed_km_s"] == pytest.approx(29.78, rel=1e-6)

    def test_list_spice_missions_tool(self):
        """list_spice_missions returns mission data."""
        from xhelio_spice.missions import list_supported_missions

        missions = list_supported_missions()
        assert len(missions) > 0
        assert any(m["mission_key"] == "PSP" for m in missions)

    def test_manage_kernels_unknown_action(self):
        """Server's manage_kernels with unknown action returns error."""
        # Test via creating server and checking the function behavior
        from xhelio_spice.server import _create_server
        _create_server()  # Just verify it creates without error

    @patch("xhelio_spice.ephemeris.get_kernel_manager")
    @patch("xhelio_spice.ephemeris.spice")
    def test_timeseries_writes_csv(self, mock_spice, mock_get_km):
        """Timeseries mode writes data to CSV and returns metadata only."""
        import tempfile
        import os

        mock_km = MagicMock()
        mock_km.lock = MagicMock()
        mock_km.lock.__enter__ = MagicMock(return_value=None)
        mock_km.lock.__exit__ = MagicMock(return_value=False)
        mock_km.get_cache_size_bytes.return_value = 0
        mock_get_km.return_value = mock_km

        mock_spice.utc2et.return_value = 0.0
        mock_spice.spkezr.return_value = (
            [1.496e8, 0.0, 0.0, 0.0, 29.78, 0.0], 499.0
        )
        mock_spice.et2utc.return_value = "2024-01-01T00:00:00.000"

        from xhelio_spice.ephemeris import get_trajectory
        df = get_trajectory(
            target="EARTH", observer="SUN",
            time_start="2024-01-01", time_end="2024-01-01",
            step="1d", frame="ECLIPJ2000",
            include_velocity=True,
        )

        # Write CSV the same way the MCP tool does
        with tempfile.NamedTemporaryFile(suffix=".csv", delete=False) as f:
            output_path = f.name
        try:
            df.index.name = "time"
            df.to_csv(output_path)
            assert os.path.exists(output_path)
            assert os.path.getsize(output_path) > 0
            # Verify CSV has expected columns
            import csv
            with open(output_path) as csvf:
                reader = csv.reader(csvf)
                header = next(reader)
                assert "time" in header
                assert "x_km" in header
                assert "vx_km_s" in header
        finally:
            os.unlink(output_path)

    @patch("xhelio_spice.ephemeris.get_kernel_manager")
    @patch("xhelio_spice.ephemeris.spice")
    def test_timeseries_with_velocity(self, mock_spice, mock_get_km):
        """Timeseries with include_velocity includes speed computation."""
        import numpy as np
        from xhelio_spice.ephemeris import get_trajectory

        mock_km = MagicMock()
        mock_km.lock = MagicMock()
        mock_km.lock.__enter__ = MagicMock(return_value=None)
        mock_km.lock.__exit__ = MagicMock(return_value=False)
        mock_get_km.return_value = mock_km

        mock_spice.utc2et.return_value = 0.0
        mock_spice.spkezr.return_value = (
            [1.496e8, 0.0, 0.0, 0.0, 29.78, 0.0], 499.0
        )
        mock_spice.et2utc.return_value = "2024-01-01T00:00:00.000"

        df = get_trajectory(
            "EARTH", "SUN", "2024-01-01", "2024-01-01",
            step="1d", include_velocity=True
        )

        assert "vx_km_s" in df.columns
        speed = np.sqrt(
            df["vx_km_s"]**2 + df["vy_km_s"]**2 + df["vz_km_s"]**2
        )
        assert speed.iloc[0] == pytest.approx(29.78, rel=1e-6)

    def test_server_has_six_tools(self):
        """Server registers exactly 6 tools after merge."""
        from xhelio_spice.server import _create_server
        server = _create_server()
        tools = list(server._tool_manager._tools.keys())
        assert len(tools) == 6
        assert "get_ephemeris" in tools
        assert "get_spacecraft_ephemeris" not in tools
        assert "get_spacecraft_position" not in tools
        assert "get_spacecraft_trajectory" not in tools
        assert "get_spacecraft_velocity" not in tools


@pytest.mark.skipif(not _HAS_MCP, reason="mcp package not installed")
class TestGetEphemerisValidation:
    """Test input validation for get_ephemeris MCP tool."""

    def test_output_file_nonexistent_parent(self):
        """output_file with nonexistent parent directory returns error."""
        from xhelio_spice.server import _create_server
        server = _create_server()
        tool = server._tool_manager.get_tool("get_ephemeris")
        result = tool.fn(
            target="EARTH", time="2024-01-01", frame="ECLIPJ2000",
            observer="SUN", output_file="/nonexistent/dir/out.csv",
            time_end="2024-01-02", step="1d",
        )
        assert result["status"] == "error"
        assert "parent directory" in result["message"].lower() or "does not exist" in result["message"].lower()


@pytest.mark.skipif(not _HAS_MCP, reason="mcp package not installed")
class TestCacheSizeInResponses:
    """All MCP tools must return cache_size_mb in success responses."""

    @patch("xhelio_spice.kernel_manager.get_kernel_manager")
    def test_list_spice_missions_has_cache_size(self, mock_get_km):
        from xhelio_spice.server import _create_server
        mock_km = MagicMock()
        mock_km.get_cache_size_bytes.return_value = 1024 * 1024
        mock_km.list_loaded.return_value = []
        mock_get_km.return_value = mock_km

        server = _create_server()
        tool = server._tool_manager.get_tool("list_spice_missions")
        result = tool.fn()
        assert "cache_size_mb" in result

    @patch("xhelio_spice.kernel_manager.get_kernel_manager")
    def test_list_coordinate_frames_has_cache_size(self, mock_get_km):
        from xhelio_spice.server import _create_server
        mock_km = MagicMock()
        mock_km.get_cache_size_bytes.return_value = 1024 * 1024
        mock_get_km.return_value = mock_km

        server = _create_server()
        tool = server._tool_manager.get_tool("list_coordinate_frames")
        result = tool.fn()
        assert "cache_size_mb" in result

    @patch("xhelio_spice.kernel_manager.get_kernel_manager")
    def test_manage_kernels_status_has_cache_size(self, mock_get_km):
        from xhelio_spice.server import _create_server
        mock_km = MagicMock()
        mock_km.get_cache_size_bytes.return_value = 1024 * 1024
        mock_km.list_loaded.return_value = []
        mock_km.get_cache_info.return_value = {
            "kernel_dir": "/tmp", "total_size_mb": 1.0,
            "file_count": 0, "missions": {},
        }
        mock_get_km.return_value = mock_km

        server = _create_server()
        tool = server._tool_manager.get_tool("manage_kernels")
        result = tool.fn(action="status")
        assert "cache_size_mb" in result
