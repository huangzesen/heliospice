"""
xhelio_spice — Spacecraft ephemeris made easy.

Auto-managed SPICE kernels for heliophysics and planetary missions.
Wraps SpiceyPy with automatic kernel download, caching, and loading.

Quick start::

    from xhelio_spice import get_position

    pos = get_position("PSP", observer="SUN", time="2024-01-15")
    print(f"PSP is {pos['r_au']:.3f} AU from the Sun")

Python API
----------
These functions are available when importing xhelio_spice as a library:

  Ephemeris (also exposed via MCP):
    get_position        — Position of a target at a single time
    get_state           — Position + velocity at a single time
    get_trajectory      — Position (and optionally velocity) timeseries

  Coordinate frames (also exposed via MCP):
    transform_vector           — Transform a 3-vector between frames
    list_available_frames      — List supported frame names
    list_frames_with_descriptions — Frames with descriptions and usage guidance

  Mission info (also exposed via MCP):
    list_supported_missions — List all missions with NAIF IDs and kernel status
    resolve_mission         — Resolve a name/alias to (NAIF ID, canonical key)

  Kernel management (also exposed via MCP):
    KernelManager       — Thread-safe kernel download/cache/load manager
    get_kernel_manager   — Get the KernelManager singleton
    check_remote_kernels — Check NAIF for new .bsp files not in configured set

MCP tools (server.py)
---------------------
The MCP server exposes 6 tools. Some combine multiple Python functions:

  get_ephemeris             — Wraps get_state (single-time) / get_trajectory (timeseries → CSV)
  compute_distance          — MCP-only; distance between two bodies over time
  transform_coordinates     — Wraps transform_vector
  list_spice_missions       — Wraps list_supported_missions
  list_coordinate_frames    — Wraps list_frames_with_descriptions
  manage_kernels            — Wraps KernelManager methods + check_remote_kernels

Note: ``compute_distance`` has no direct Python API equivalent; it uses
``get_trajectory`` internally to compute distances between two bodies.

Supported missions (43 spacecraft):

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

__version__ = "0.5.0"

from .ephemeris import get_position, get_trajectory, get_state
from .frames import (
    transform_vector,
    list_available_frames,
    list_frames_with_descriptions,
)
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
