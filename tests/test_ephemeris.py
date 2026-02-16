"""Tests for heliospice.ephemeris — position, state, trajectory."""

from unittest.mock import MagicMock, patch
import numpy as np
import pandas as pd
import pytest


class TestEphemeris:
    @patch("heliospice.ephemeris.get_kernel_manager")
    @patch("heliospice.ephemeris.spice")
    def test_get_position(self, mock_spice, mock_get_km):
        """get_position returns correct dict structure."""
        from heliospice.ephemeris import get_position

        # Mock kernel manager
        mock_km = MagicMock()
        mock_km.lock = MagicMock()
        mock_km.lock.__enter__ = MagicMock(return_value=None)
        mock_km.lock.__exit__ = MagicMock(return_value=False)
        mock_get_km.return_value = mock_km

        # Mock SPICE calls
        mock_spice.utc2et.return_value = 0.0
        mock_spice.spkpos.return_value = (
            [1.496e8, 0.0, 0.0],  # ~1 AU in x
            499.0,  # light time in seconds
        )

        result = get_position("EARTH", "SUN", "2000-01-01T12:00:00")

        assert result["x_km"] == pytest.approx(1.496e8, rel=1e-6)
        assert result["y_km"] == 0.0
        assert result["z_km"] == 0.0
        assert result["r_au"] == pytest.approx(1.0, rel=0.01)
        assert result["light_time_s"] == 499.0
        assert result["target"] == "EARTH"
        assert result["observer"] == "SUN"

    @patch("heliospice.ephemeris.get_kernel_manager")
    @patch("heliospice.ephemeris.spice")
    def test_get_state(self, mock_spice, mock_get_km):
        """get_state returns position + velocity."""
        from heliospice.ephemeris import get_state

        mock_km = MagicMock()
        mock_km.lock = MagicMock()
        mock_km.lock.__enter__ = MagicMock(return_value=None)
        mock_km.lock.__exit__ = MagicMock(return_value=False)
        mock_get_km.return_value = mock_km

        mock_spice.utc2et.return_value = 0.0
        mock_spice.spkezr.return_value = (
            [1.496e8, 0.0, 0.0, 0.0, 29.78, 0.0],  # pos + vel
            499.0,
        )

        result = get_state("EARTH", "SUN", "2000-01-01T12:00:00")

        assert "vx_km_s" in result
        assert result["vy_km_s"] == pytest.approx(29.78, rel=1e-6)
        assert result["speed_km_s"] == pytest.approx(29.78, rel=1e-6)

    @patch("heliospice.ephemeris.get_kernel_manager")
    @patch("heliospice.ephemeris.spice")
    def test_get_trajectory(self, mock_spice, mock_get_km):
        """get_trajectory returns a DataFrame with expected columns."""
        from heliospice.ephemeris import get_trajectory

        mock_km = MagicMock()
        mock_km.lock = MagicMock()
        mock_km.lock.__enter__ = MagicMock(return_value=None)
        mock_km.lock.__exit__ = MagicMock(return_value=False)
        mock_get_km.return_value = mock_km

        mock_spice.utc2et.return_value = 0.0
        # Return different positions for a trajectory
        mock_spice.spkpos.return_value = ([1.496e8, 0.0, 0.0], 499.0)
        mock_spice.et2utc.return_value = "2024-01-01T00:00:00.000"

        df = get_trajectory("EARTH", "SUN", "2024-01-01", "2024-01-01", step="1d")

        assert isinstance(df, pd.DataFrame)
        assert "x_km" in df.columns
        assert "y_km" in df.columns
        assert "z_km" in df.columns
        assert "r_km" in df.columns
        assert "r_au" in df.columns
        assert df.index.name == "time"

    @patch("heliospice.ephemeris.get_kernel_manager")
    @patch("heliospice.ephemeris.spice")
    def test_get_trajectory_with_velocity(self, mock_spice, mock_get_km):
        """get_trajectory with include_velocity adds velocity columns."""
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
        assert "vy_km_s" in df.columns
        assert "vz_km_s" in df.columns

    def test_parse_step(self):
        """_parse_step correctly parses time step strings."""
        from heliospice.ephemeris import _parse_step
        assert _parse_step("1h") == 3600
        assert _parse_step("30m") == 1800
        assert _parse_step("1d") == 86400
        assert _parse_step("60s") == 60
        assert _parse_step("3600") == 3600
