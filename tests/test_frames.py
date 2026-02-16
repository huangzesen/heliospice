"""Tests for heliospice.frames — coordinate frame transforms."""

from unittest.mock import MagicMock, patch
import numpy as np
import pytest


class TestFrames:
    def test_list_available_frames(self):
        from heliospice.frames import list_available_frames
        frames = list_available_frames()
        assert "J2000" in frames
        assert "ECLIPJ2000" in frames
        assert "RTN" in frames

    def test_resolve_frame_alias(self):
        from heliospice.frames import _resolve_frame
        assert _resolve_frame("ECLIPTIC") == "ECLIPJ2000"
        assert _resolve_frame("j2000") == "J2000"
        assert _resolve_frame("RTN") == "RTN"

    @patch("heliospice.frames.get_kernel_manager")
    @patch("heliospice.frames.spice")
    def test_transform_identity(self, mock_spice, mock_get_km):
        """Transforming to the same frame returns the input."""
        from heliospice.frames import transform_vector

        mock_km = MagicMock()
        mock_km.lock = MagicMock()
        mock_km.lock.__enter__ = MagicMock(return_value=None)
        mock_km.lock.__exit__ = MagicMock(return_value=False)
        mock_get_km.return_value = mock_km

        v = np.array([1.0, 2.0, 3.0])
        result = transform_vector(v, "2024-01-01", "J2000", "J2000")
        np.testing.assert_array_equal(result, v)

    @patch("heliospice.frames.get_kernel_manager")
    @patch("heliospice.frames.spice")
    def test_transform_spice_native(self, mock_spice, mock_get_km):
        """Standard SPICE frame transform uses pxform."""
        from heliospice.frames import transform_vector

        mock_km = MagicMock()
        mock_km.lock = MagicMock()
        mock_km.lock.__enter__ = MagicMock(return_value=None)
        mock_km.lock.__exit__ = MagicMock(return_value=False)
        mock_get_km.return_value = mock_km

        mock_spice.utc2et.return_value = 0.0
        # Identity rotation for simplicity
        mock_spice.pxform.return_value = np.eye(3)

        v = np.array([1.0, 0.0, 0.0])
        result = transform_vector(v, "2024-01-01", "J2000", "ECLIPJ2000")

        mock_spice.pxform.assert_called_once()
        np.testing.assert_array_almost_equal(result, v)

    def test_transform_bad_vector_shape(self):
        """Non-3D vectors raise ValueError."""
        from heliospice.frames import transform_vector
        with pytest.raises(ValueError, match="3-element vector"):
            transform_vector([1.0, 2.0], "2024-01-01", "J2000", "ECLIPJ2000")

    @patch("heliospice.frames.get_kernel_manager")
    @patch("heliospice.frames.spice")
    def test_rtn_requires_spacecraft(self, mock_spice, mock_get_km):
        """RTN transform without spacecraft raises ValueError."""
        from heliospice.frames import transform_vector

        mock_km = MagicMock()
        mock_km.lock = MagicMock()
        mock_km.lock.__enter__ = MagicMock(return_value=None)
        mock_km.lock.__exit__ = MagicMock(return_value=False)
        mock_get_km.return_value = mock_km

        mock_spice.utc2et.return_value = 0.0

        with pytest.raises(ValueError, match="spacecraft.*required"):
            transform_vector([1.0, 0.0, 0.0], "2024-01-01", "J2000", "RTN")

    def test_list_frames_with_descriptions(self):
        """list_frames_with_descriptions returns structured data."""
        from heliospice.frames import list_frames_with_descriptions
        frames = list_frames_with_descriptions()
        assert len(frames) > 0
        for f in frames:
            assert "frame" in f
            assert "full_name" in f
            assert "description" in f
            assert "use_when" in f
