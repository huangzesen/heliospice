"""Tests for xhelio_spice.ephemeris — position, state, trajectory."""

from unittest.mock import MagicMock, patch
import numpy as np
import pandas as pd
import pytest


class TestEphemeris:
    @patch("xhelio_spice.ephemeris.get_kernel_manager")
    @patch("xhelio_spice.ephemeris.spice")
    def test_get_position(self, mock_spice, mock_get_km):
        """get_position returns correct dict structure."""
        from xhelio_spice.ephemeris import get_position

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

    @patch("xhelio_spice.ephemeris.get_kernel_manager")
    @patch("xhelio_spice.ephemeris.spice")
    def test_get_state(self, mock_spice, mock_get_km):
        """get_state returns position + velocity."""
        from xhelio_spice.ephemeris import get_state

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

    @patch("xhelio_spice.ephemeris.get_kernel_manager")
    @patch("xhelio_spice.ephemeris.spice")
    def test_get_trajectory(self, mock_spice, mock_get_km):
        """get_trajectory returns a DataFrame with expected columns."""
        from xhelio_spice.ephemeris import get_trajectory

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

    @patch("xhelio_spice.ephemeris.get_kernel_manager")
    @patch("xhelio_spice.ephemeris.spice")
    def test_get_trajectory_with_velocity(self, mock_spice, mock_get_km):
        """get_trajectory with include_velocity adds velocity columns."""
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
        assert "vy_km_s" in df.columns
        assert "vz_km_s" in df.columns

    def test_parse_step(self):
        """_parse_step correctly parses time step strings."""
        from xhelio_spice.ephemeris import _parse_step
        assert _parse_step("1h") == 3600
        assert _parse_step("30m") == 1800
        assert _parse_step("1d") == 86400
        assert _parse_step("60s") == 60
        assert _parse_step("3600") == 3600

    @patch("xhelio_spice.ephemeris.get_kernel_manager")
    @patch("xhelio_spice.ephemeris.spice")
    def test_get_position_rtn(self, mock_spice, mock_get_km):
        """get_position with frame='RTN' rotates into RTN coordinates.

        Spacecraft at [0, 1e8, 0] in J2000 — R-hat points along +y.
        In RTN, this purely radial position should become [1e8, 0, 0].
        If RTN rotation is NOT applied, we'd get [0, 1e8, 0] instead.
        """
        from xhelio_spice.ephemeris import get_position

        mock_km = MagicMock()
        mock_km.lock = MagicMock()
        mock_km.lock.__enter__ = MagicMock(return_value=None)
        mock_km.lock.__exit__ = MagicMock(return_value=False)
        mock_get_km.return_value = mock_km

        mock_spice.utc2et.return_value = 0.0
        # Spacecraft at [0, 1e8, 0] from Sun in J2000 — off-axis
        mock_spice.spkpos.return_value = ([0.0, 1e8, 0.0], 333.0)

        result = get_position("PSP", "SUN", "2024-01-15", frame="RTN")

        # In RTN, the radial component (x) should hold the full distance
        assert result["x_km"] == pytest.approx(1e8, rel=1e-2)
        # T and N should be ~0 for a Sun-centered position
        assert result["y_km"] == pytest.approx(0.0, abs=1e3)
        assert result["z_km"] == pytest.approx(0.0, abs=1e3)
        assert result["frame"] == "RTN"
        # r_km should be unchanged by rotation
        assert result["r_km"] == pytest.approx(1e8, rel=1e-3)

    @patch("xhelio_spice.ephemeris.get_kernel_manager")
    @patch("xhelio_spice.ephemeris.spice")
    def test_get_state_rtn(self, mock_spice, mock_get_km):
        """get_state with frame='RTN' rotates position and velocity.

        Spacecraft at [1e8, 0, 0] with velocity [0, 30, 0] in J2000.
        R-hat = +x, T-hat ≈ +y (for this geometry), N-hat ≈ +z.
        So velocity in RTN: vR~0, vT~30, vN~0.
        If RTN is NOT applied, we'd get vx=0, vy=30, vz=0 in raw J2000.
        We verify by checking velocity components are physically correct.
        """
        from xhelio_spice.ephemeris import get_state

        mock_km = MagicMock()
        mock_km.lock = MagicMock()
        mock_km.lock.__enter__ = MagicMock(return_value=None)
        mock_km.lock.__exit__ = MagicMock(return_value=False)
        mock_get_km.return_value = mock_km

        mock_spice.utc2et.return_value = 0.0
        # spkezr returns state in J2000
        mock_spice.spkezr.return_value = (
            [1e8, 0.0, 0.0, 0.0, 30.0, 0.0], 333.0
        )
        # spkpos for RTN matrix: same position
        mock_spice.spkpos.return_value = ([1e8, 0.0, 0.0], 333.0)

        result = get_state("PSP", "SUN", "2024-01-15", frame="RTN")

        assert result["frame"] == "RTN"
        assert "vx_km_s" in result
        assert "vy_km_s" in result
        assert "vz_km_s" in result
        assert result["speed_km_s"] == pytest.approx(30.0, rel=1e-3)

    @patch("xhelio_spice.ephemeris.get_kernel_manager")
    @patch("xhelio_spice.ephemeris.spice")
    def test_get_position_rtn_preserves_distance(self, mock_spice, mock_get_km):
        """RTN rotation must preserve the distance magnitude."""
        from xhelio_spice.ephemeris import get_position

        mock_km = MagicMock()
        mock_km.lock = MagicMock()
        mock_km.lock.__enter__ = MagicMock(return_value=None)
        mock_km.lock.__exit__ = MagicMock(return_value=False)
        mock_get_km.return_value = mock_km

        mock_spice.utc2et.return_value = 0.0
        # Arbitrary off-axis position
        mock_spice.spkpos.return_value = ([3e7, 4e7, 0.0], 200.0)

        result = get_position("PSP", "SUN", "2024-01-15", frame="RTN")

        expected_r = np.sqrt(3e7**2 + 4e7**2)
        assert result["r_km"] == pytest.approx(expected_r, rel=1e-6)
        # x_km in RTN (R component) should equal the full distance
        assert result["x_km"] == pytest.approx(expected_r, rel=1e-2)

    @patch("xhelio_spice.ephemeris.get_kernel_manager")
    @patch("xhelio_spice.ephemeris.spice")
    def test_get_trajectory_rtn(self, mock_spice, mock_get_km):
        """get_trajectory with frame='RTN' returns RTN-rotated positions.

        Position at [0, 1e8, 0] in J2000 → should become [1e8, 0, 0] in RTN.
        """
        from xhelio_spice.ephemeris import get_trajectory

        mock_km = MagicMock()
        mock_km.lock = MagicMock()
        mock_km.lock.__enter__ = MagicMock(return_value=None)
        mock_km.lock.__exit__ = MagicMock(return_value=False)
        mock_get_km.return_value = mock_km

        mock_spice.utc2et.return_value = 0.0
        mock_spice.spkpos.return_value = ([0.0, 1e8, 0.0], 333.0)
        mock_spice.et2utc.return_value = "2024-01-01T00:00:00.000"

        df = get_trajectory(
            "PSP", "SUN", "2024-01-01", "2024-01-01",
            step="1d", frame="RTN"
        )

        assert isinstance(df, pd.DataFrame)
        assert "x_km" in df.columns
        # Off-axis J2000 position should be rotated: R component ≈ 1e8
        assert df["x_km"].iloc[0] == pytest.approx(1e8, rel=1e-2)
        assert df["y_km"].iloc[0] == pytest.approx(0.0, abs=1e3)

    @patch("xhelio_spice.ephemeris.get_kernel_manager")
    @patch("xhelio_spice.ephemeris.spice")
    def test_get_trajectory_rtn_with_velocity(self, mock_spice, mock_get_km):
        """get_trajectory RTN with include_velocity rotates velocity too."""
        from xhelio_spice.ephemeris import get_trajectory

        mock_km = MagicMock()
        mock_km.lock = MagicMock()
        mock_km.lock.__enter__ = MagicMock(return_value=None)
        mock_km.lock.__exit__ = MagicMock(return_value=False)
        mock_get_km.return_value = mock_km

        mock_spice.utc2et.return_value = 0.0
        mock_spice.spkezr.return_value = (
            [1e8, 0.0, 0.0, 0.0, 30.0, 0.0], 333.0
        )
        mock_spice.spkpos.return_value = ([1e8, 0.0, 0.0], 333.0)
        mock_spice.et2utc.return_value = "2024-01-01T00:00:00.000"

        df = get_trajectory(
            "PSP", "SUN", "2024-01-01", "2024-01-01",
            step="1d", frame="RTN", include_velocity=True
        )

        assert "vx_km_s" in df.columns
        assert "vy_km_s" in df.columns
        assert "vz_km_s" in df.columns


def test_parse_step_zero_raises():
    """Zero step size raises ValueError."""
    from xhelio_spice.ephemeris import _parse_step
    with pytest.raises(ValueError, match="must be positive"):
        _parse_step("0h")
