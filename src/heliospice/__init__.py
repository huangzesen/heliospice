"""
heliospice — Spacecraft ephemeris made easy.

Auto-managed SPICE kernels for heliophysics and planetary missions.
Wraps SpiceyPy with automatic kernel download, caching, and loading.

Quick start::

    from heliospice import get_position

    pos = get_position("PSP", observer="SUN", time="2024-01-15")
    print(f"PSP is {pos['r_au']:.3f} AU from the Sun")

Supported missions (36 spacecraft):

  Heliophysics:
    PSP, Solar Orbiter, SOHO, IBEX, STEREO-A, STEREO-B,
    Helios 1, Helios 2, Ulysses,
    Van Allen Probes A/B, THEMIS A/B/C/D/E

  Planetary / deep-space:
    Juno, Voyager 1, Voyager 2, MAVEN, New Horizons,
    Galileo, Pioneer 10, Pioneer 11, MESSENGER, Dawn,
    Lucy, Europa Clipper, Psyche, JUICE, BepiColombo,
    Venus Express, Pioneer Venus, InSight,
    Cassini*, MRO*, Mars 2020*, LRO*, Lunar Prospector*, MGS*

  No SPK kernels (NAIF ID only):
    ACE, Wind, DSCOVR

  * = segmented kernels (only segments for your time range are downloaded)

Use ``list_supported_missions()`` for programmatic access.
"""

__version__ = "0.3.1"

from .ephemeris import get_position, get_trajectory, get_state
from .frames import transform_vector, list_available_frames, list_frames_with_descriptions
from .missions import resolve_mission, list_supported_missions
from .kernel_manager import KernelManager, get_kernel_manager, check_remote_kernels

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
    "check_remote_kernels",
]
