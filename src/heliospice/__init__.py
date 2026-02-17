"""
heliospice — Spacecraft ephemeris made easy.

Auto-managed SPICE kernels for heliophysics and planetary missions.
Wraps SpiceyPy with automatic kernel download, caching, and loading.

Quick start::

    from heliospice import get_position

    pos = get_position("PSP", observer="SUN", time="2024-01-15")
    print(f"PSP is {pos['r_au']:.3f} AU from the Sun")

Supported missions: PSP, Solar Orbiter, ACE, Wind, DSCOVR, MMS,
STEREO-A, Cassini, Juno, Voyager 1/2, MAVEN, New Horizons, and more.
"""

__version__ = "0.2.0"

from .ephemeris import get_position, get_trajectory, get_state
from .frames import transform_vector, list_available_frames, list_frames_with_descriptions
from .missions import resolve_mission, list_supported_missions
from .kernel_manager import KernelManager, get_kernel_manager

__all__ = [
    "get_position",
    "get_trajectory",
    "get_state",
    "transform_vector",
    "list_available_frames",
    "list_frames_with_descriptions",
    "resolve_mission",
    "list_supported_missions",
    "KernelManager",
    "get_kernel_manager",
]
