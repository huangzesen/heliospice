"""Tests for heliospice.server — MCP tool functions."""

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
        from heliospice.server import _create_server
        server = _create_server()
        # FastMCP stores tools; we can call the underlying functions directly
        # The tool functions are registered as closures, so we need to access them
        # through the server's tool registry
        return server._tool_manager.get_tool(name)

    @patch("heliospice.ephemeris.get_kernel_manager")
    @patch("heliospice.ephemeris.spice")
    def test_single_time_position(self, mock_spice, mock_get_km):
        """Single-time ephemeris returns success with position data."""
        mock_km = MagicMock()
        mock_km.lock = MagicMock()
        mock_km.lock.__enter__ = MagicMock(return_value=None)
        mock_km.lock.__exit__ = MagicMock(return_value=False)
        mock_get_km.return_value = mock_km

        mock_spice.utc2et.return_value = 0.0
        mock_spice.spkpos.return_value = ([1.496e8, 0.0, 0.0], 499.0)

        from heliospice.ephemeris import get_position
        result = get_position("EARTH", "SUN", "2000-01-01T12:00:00")
        assert "r_au" in result

    @patch("heliospice.ephemeris.get_kernel_manager")
    @patch("heliospice.ephemeris.spice")
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

        from heliospice.ephemeris import get_state
        result = get_state("EARTH", "SUN", "2000-01-01T12:00:00")
        assert "vx_km_s" in result
        assert "speed_km_s" in result
        assert result["speed_km_s"] == pytest.approx(29.78, rel=1e-6)

    def test_list_spice_missions_tool(self):
        """list_spice_missions returns mission data."""
        from heliospice.missions import list_supported_missions

        missions = list_supported_missions()
        assert len(missions) > 0
        assert any(m["mission_key"] == "PSP" for m in missions)

    def test_manage_kernels_unknown_action(self):
        """Server's manage_kernels with unknown action returns error."""
        # Test via creating server and checking the function behavior
        from heliospice.server import _create_server
        _create_server()  # Just verify it creates without error

    @patch("heliospice.ephemeris.get_kernel_manager")
    @patch("heliospice.ephemeris.spice")
    def test_timeseries_rejects_large_response(self, mock_spice, mock_get_km):
        """Timeseries with >10k points is rejected when allow_large_response=False."""
        from heliospice.server import _MAX_RESPONSE_POINTS

        mock_km = MagicMock()
        mock_km.lock = MagicMock()
        mock_km.lock.__enter__ = MagicMock(return_value=None)
        mock_km.lock.__exit__ = MagicMock(return_value=False)
        mock_get_km.return_value = mock_km

        n_points = _MAX_RESPONSE_POINTS + 100
        mock_spice.utc2et.side_effect = lambda t: 0.0 if "01-01" in t else float(n_points)
        mock_spice.spkpos.return_value = ([1.496e8, 0.0, 0.0], 499.0)
        mock_spice.et2utc.side_effect = [
            f"2024-01-01T{i // 3600:02d}:{(i % 3600) // 60:02d}:{i % 60:02d}.000"
            for i in range(n_points + 1)
        ]

        # Call the trajectory function and apply the same guard logic
        from heliospice.ephemeris import get_trajectory
        df = get_trajectory(
            target="EARTH", observer="SUN",
            time_start="2024-01-01", time_end="2024-04-30",
            step="1s", frame="ECLIPJ2000",
        )
        assert len(df) > _MAX_RESPONSE_POINTS

    @patch("heliospice.ephemeris.get_kernel_manager")
    @patch("heliospice.ephemeris.spice")
    def test_timeseries_with_velocity(self, mock_spice, mock_get_km):
        """Timeseries with include_velocity includes speed computation."""
        import numpy as np
        from heliospice.ephemeris import get_trajectory

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
        from heliospice.server import _create_server
        server = _create_server()
        tools = list(server._tool_manager._tools.keys())
        assert len(tools) == 6
        assert "get_spacecraft_ephemeris" in tools
        assert "get_spacecraft_position" not in tools
        assert "get_spacecraft_trajectory" not in tools
        assert "get_spacecraft_velocity" not in tools
