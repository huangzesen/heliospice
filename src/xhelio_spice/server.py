"""
SPICE MCP server for spacecraft ephemeris.

Exposes SPICE position/trajectory/transform capabilities as MCP tools
over stdio transport. Any MCP-compatible client (Claude Desktop, Claude Code,
Cursor, etc.) can connect and query spacecraft positions.

This server is lightweight — no LLM needed. It wraps xhelio_spice directly.

Usage:
    xhelio-spice-mcp                # Via CLI entrypoint
    python -m xhelio_spice.server   # Via module
    xhelio-spice-mcp -v             # With verbose logging
"""

import argparse
import logging
import sys

try:
    from mcp.server.fastmcp import FastMCP
except ImportError:
    FastMCP = None

def _create_server() -> "FastMCP":
    """Create and configure the MCP server with all tools."""
    if FastMCP is None:
        raise ImportError(
            "MCP support requires the 'mcp' package. "
            "Install it with: pip install xhelio-spice[mcp]"
        )

    def _cache_size_mb() -> float:
        """Return current kernel cache size in MB."""
        from .kernel_manager import get_kernel_manager

        return round(get_kernel_manager().get_cache_size_bytes() / (1024 * 1024), 2)

    mcp = FastMCP(
        "spice-ephemeris",
        instructions=(
            "SPICE Ephemeris Server — Query spacecraft positions, trajectories, and coordinate transforms.\n\n"
            "=== What is SPICE? ===\n"
            "SPICE is NASA's Navigation and Ancillary Information Facility (NAIF) system for accessing "
            "spacecraft ephemerides, planetary positions, and coordinate frames. It uses binary 'kernels' "
            "(SPK for position/velocity, PCK for planetary constants, LSK for leap seconds) to compute "
            "positions of bodies at any time. This server wraps the Python 'SpiceyPy' library with "
            "automatic kernel management — kernels are downloaded on-demand from NAIF and cached locally.\n\n"
            "=== Available Spacecraft (43 total) ===\n"
            "Heliophysics: PSP (Parker Solar Probe), SOLO (Solar Orbiter), SOHO, IBEX, STEREO-A/B, "
            "Helios 1/2, Ulysses, ACE*, Wind*, DSCOVR*, Van Allen Probes (RBSP_A/B), THEMIS A-E (ARTEMIS)\n"
            "Planetary/Deep-Space: Cassini, Juno, Voyager 1/2, MAVEN, MRO, Mars 2020, New Horizons, Galileo, "
            "Pioneer 10/11, MESSENGER, Dawn, Lucy, Europa Clipper, Psyche, JUICE, BepiColombo, "
            "Venus Express, Pioneer Venus, InSight, LRO, Lunar Prospector, MGS\n"
            "* ACE, Wind, DSCOVR have NAIF IDs but no public SPK kernels available.\n\n"
            "=== Available Bodies (observers/targets) ===\n"
            "Sun, Earth, Moon, Mercury, Venus, Mars, Jupiter, Saturn, Uranus, Neptune, Pluto, "
            "Solar System Barycenter (SSB), and planetary barycenters.\n\n"
            "=== Available Coordinate Frames ===\n"
            "Inertial: J2000, ECLIPJ2000, ECLIPB1950\n"
            "Heliocentric: HCI (Heliocentric Inertial), HEE (Heliocentric Earth Ecliptic), HAE (Heliocentric Aries Ecliptic), HEEQ (Heliocentric Earth Equatorial/Stonyhurst)\n"
            "Earth-centered: GSE (Geocentric Solar Ecliptic), GEI (Geocentric Equatorial Inertial)\n"
            "Spacecraft: RTN (Radial-Tangential-Normal), requires spacecraft name\n\n"
            "=== Tools ===\n"
            "1. get_ephemeris — Position and velocity of any body. Single-time returns inline JSON. Timeseries requires output_file path; full data is written to CSV and only metadata (summary stats, column info, preview) is returned in the response.\n"
            "2. compute_distance — Distance between two bodies over time range, returns min/max/mean and closest approach.\n"
            "3. transform_coordinates — Transform 3D vectors between frames (e.g., RTN to J2000). RTN requires spacecraft name.\n"
            "4. list_spice_missions — List all supported missions with kernel status.\n"
            "5. list_coordinate_frames — Show all frames with descriptions and usage guidance.\n"
            "6. manage_kernels — Check status, load kernels, delete cache, or purge all.\n\n"
            "=== Usage Notes ===\n"
            "- frame is required for get_ephemeris — use list_coordinate_frames first to choose.\n"
            "- Observer defaults to SUN; use EARTH for geocentric, or any planet.\n"
            "- Time format: ISO 8601 (e.g., '2024-01-15T12:00:00' or '2024-01-15').\n"
            "- Step for timeseries: '1m', '1h', '6h', '1d' (default '1h').\n"
            "- Timeseries data is written to CSV at the caller-specified output_file path. The MCP response contains only metadata.\n"
            "- Kernels auto-download on first query; cache location: ~/.xhelio_spice/kernels/ (configurable via XHELIO_SPICE_KERNEL_DIR)."
        ),
    )

    @mcp.tool()
    def get_ephemeris(
        target: str,
        time: str,
        frame: str,
        observer: str,
        output_file: str = "",
        time_end: str = "",
        step: str = "1h",
    ) -> dict:
        """Get position and velocity of any body — single time or timeseries.

        Single-time mode (time_end empty): returns position and velocity inline.
        output_file is ignored.

        Timeseries mode (time_end provided): computes trajectory, writes full
        data to CSV at output_file, and returns metadata only (no bulk data
        in the response). The CSV contains columns: time, x_km, y_km, z_km,
        vx_km_s, vy_km_s, vz_km_s, r_km, r_au.

        Args:
            target: Target body (e.g., "PSP", "Earth", "Jupiter", "Cassini")
            time: UTC time in ISO 8601 format. For timeseries, this is the start time.
            frame: Coordinate frame (e.g., "ECLIPJ2000", "GSE", "RTN"). Use list_coordinate_frames to see all options.
            observer: Observer body (e.g., "SUN", "EARTH"). Use "EARTH" for geocentric.
            output_file: File path for timeseries CSV output. Required when time_end is provided. Ignored for single-time queries.
            time_end: End time for timeseries (ISO 8601). Leave empty for single-time query.
            step: Time step for timeseries (e.g., "1m", "1h", "6h", "1d"). Only used when time_end is provided.

        Returns:
            Single-time response:
                status, cache_size_mb, x_km, y_km, z_km, vx_km_s, vy_km_s,
                vz_km_s, r_km, r_au, speed_km_s, light_time_s, target,
                observer, frame, time.

            Timeseries response:
                status, cache_size_mb, target, observer, frame, step,
                time_start, time_end, n_points, n_columns, columns,
                distance_au (dict with min, max, mean),
                distance_km (dict with min, max),
                speed_km_s (dict with min, max, mean),
                output_file (absolute path to CSV), output_size_bytes,
                preview (list of first/last 5 data points).

        Examples:
            - get_ephemeris("PSP", "2024-01-15", "ECLIPJ2000", "SUN", "/tmp/psp.csv")
            - get_ephemeris("Earth", "2024-01-01", "ECLIPJ2000", "SUN", "/tmp/earth.csv", time_end="2024-12-31", step="1d")
        """
        try:
            # --- Single-time mode ---
            if not time_end:
                from .ephemeris import get_state

                result = get_state(
                    target=target, observer=observer, time=time, frame=frame
                )
                return {
                    "status": "success",
                    "cache_size_mb": _cache_size_mb(),
                    **result,
                }

            # --- Timeseries mode ---
            import os

            # Validate output_file
            if not output_file:
                return {
                    "status": "error",
                    "message": "output_file is required for timeseries queries (when time_end is provided).",
                }
            output_path = os.path.abspath(output_file)
            parent_dir = os.path.dirname(output_path)
            if not os.path.isdir(parent_dir):
                return {
                    "status": "error",
                    "message": f"Parent directory does not exist: {parent_dir}",
                }

            from .ephemeris import get_trajectory
            import numpy as np

            df = get_trajectory(
                target=target,
                observer=observer,
                time_start=time,
                time_end=time_end,
                step=step,
                frame=frame,
                include_velocity=True,
            )

            # Compute speed column
            speed = np.sqrt(
                df["vx_km_s"] ** 2 + df["vy_km_s"] ** 2 + df["vz_km_s"] ** 2
            )
            df["speed_km_s"] = speed

            # Write CSV
            df.index.name = "time"
            df.to_csv(output_path)
            output_size = os.path.getsize(output_path)

            # Build metadata response (no bulk data)
            n_preview = min(5, len(df))
            preview_rows = []
            for idx in list(range(n_preview)) + list(
                range(max(n_preview, len(df) - n_preview), len(df))
            ):
                row = df.iloc[idx]
                entry = {"time": str(df.index[idx])}
                for col in df.columns:
                    entry[col] = round(
                        float(row[col]), 6 if "au" in col else 3 if "km_s" in col else 1
                    )
                preview_rows.append(entry)

            return {
                "status": "success",
                "cache_size_mb": _cache_size_mb(),
                "target": target,
                "observer": observer,
                "frame": frame,
                "step": step,
                "time_start": str(df.index[0]),
                "time_end": str(df.index[-1]),
                "n_points": len(df),
                "n_columns": len(df.columns),
                "columns": list(df.columns),
                "distance_au": {
                    "min": round(float(df["r_au"].min()), 6),
                    "max": round(float(df["r_au"].max()), 6),
                    "mean": round(float(df["r_au"].mean()), 6),
                },
                "distance_km": {
                    "min": round(float(df["r_km"].min()), 1),
                    "max": round(float(df["r_km"].max()), 1),
                },
                "speed_km_s": {
                    "min": round(float(speed.min()), 3),
                    "max": round(float(speed.max()), 3),
                    "mean": round(float(speed.mean()), 3),
                },
                "output_file": output_path,
                "output_size_bytes": output_size,
                "preview": preview_rows,
            }

        except Exception as e:
            return {"status": "error", "message": str(e)}

    @mcp.tool()
    def compute_distance(
        target1: str,
        target2: str,
        time_start: str,
        time_end: str,
        step: str,
    ) -> dict:
        """Compute the distance between two bodies over a time range.

        Returns min/max/mean distance in both km and AU, plus closest approach.

        Args:
            target1: First body (e.g., "PSP", "Earth")
            target2: Second body (e.g., "SUN", "ACE")
            time_start: Start time (ISO 8601)
            time_end: End time (ISO 8601)
            step: Time step (e.g., "1h", "6h", "1d")

        Returns:
            status, cache_size_mb, target1, target2, time_start, time_end,
            n_points,
            distance_au (dict with min, max, mean),
            distance_km (dict with min, max, mean),
            closest_approach (dict with time, distance_km, distance_au).

        Examples:
            - compute_distance("PSP", "SUN", "2024-01-01", "2024-01-31", "1h")
            - compute_distance("ACE", "Earth", "2024-06-01", "2024-06-30", "6h")
        """
        from .ephemeris import get_trajectory

        try:
            df = get_trajectory(
                target=target1,
                observer=target2,
                time_start=time_start,
                time_end=time_end,
                step=step,
                frame="ECLIPJ2000",
            )

            result = {
                "status": "success",
                "cache_size_mb": _cache_size_mb(),
                "target1": target1,
                "target2": target2,
                "time_start": str(df.index[0]),
                "time_end": str(df.index[-1]),
                "n_points": len(df),
                "distance_au": {
                    "min": round(float(df["r_au"].min()), 6),
                    "max": round(float(df["r_au"].max()), 6),
                    "mean": round(float(df["r_au"].mean()), 6),
                },
                "distance_km": {
                    "min": round(float(df["r_km"].min()), 1),
                    "max": round(float(df["r_km"].max()), 1),
                    "mean": round(float(df["r_km"].mean()), 1),
                },
            }

            # Find closest approach
            min_idx = df["r_km"].idxmin()
            result["closest_approach"] = {
                "time": str(min_idx),
                "distance_km": round(float(df.loc[min_idx, "r_km"]), 1),
                "distance_au": round(float(df.loc[min_idx, "r_au"]), 6),
            }

            return result

        except Exception as e:
            return {"status": "error", "message": str(e)}

    @mcp.tool()
    def transform_coordinates(
        vector: list[float],
        time: str,
        from_frame: str,
        to_frame: str,
        spacecraft: str = "",
    ) -> dict:
        """Transform a 3D vector between coordinate frames.

        Args:
            vector: 3-element vector [x, y, z] to transform
            time: UTC time (ISO 8601) for the transformation epoch
            from_frame: Source frame (e.g., "J2000", "ECLIPJ2000", "RTN")
            to_frame: Target frame (e.g., "ECLIPJ2000", "J2000", "RTN")
            spacecraft: Spacecraft name (required if RTN frame is used)

        Returns:
            status, cache_size_mb, input_vector, output_vector (list of 3 floats),
            from_frame, to_frame, time, magnitude (vector magnitude).

        Examples:
            - transform_coordinates([1.0, 0.0, 0.0], "2024-01-15", "J2000", "ECLIPJ2000")
            - transform_coordinates([5.0, -3.0, 1.0], "2024-01-15", "RTN", "J2000", spacecraft="PSP")
        """
        from .frames import transform_vector

        try:
            import numpy as np

            result_vec = transform_vector(
                vector=vector,
                time=time,
                from_frame=from_frame,
                to_frame=to_frame,
                spacecraft=spacecraft,
            )
            return {
                "status": "success",
                "cache_size_mb": _cache_size_mb(),
                "input_vector": vector,
                "output_vector": [round(float(v), 6) for v in result_vec],
                "from_frame": from_frame,
                "to_frame": to_frame,
                "time": time,
                "magnitude": round(float(np.linalg.norm(result_vec)), 6),
            }
        except Exception as e:
            return {"status": "error", "message": str(e)}

    @mcp.tool()
    def list_spice_missions() -> dict:
        """List all supported spacecraft missions with NAIF IDs and kernel status.

        Returns the full list of missions that can be queried for positions
        and trajectories.

        Returns:
            status, mission_count,
            missions (list of dicts, each with mission name, naif_id,
            mission_key, kernels_loaded, segmented).
        """
        from .missions import (
            list_supported_missions,
            MISSION_KERNELS,
            SEGMENTED_MISSIONS,
        )
        from .kernel_manager import get_kernel_manager

        missions = list_supported_missions()
        km = get_kernel_manager()
        loaded = set(km.list_loaded())

        for m in missions:
            key = m["mission_key"]
            kernel_files = MISSION_KERNELS.get(key, {})
            m["kernels_loaded"] = (
                all(f in loaded for f in kernel_files) if kernel_files else False
            )
            m["segmented"] = key in SEGMENTED_MISSIONS

        return {
            "status": "success",
            "cache_size_mb": _cache_size_mb(),
            "mission_count": len(missions),
            "missions": missions,
        }

    @mcp.tool()
    def list_coordinate_frames() -> dict:
        """List all supported coordinate frames with descriptions and usage guidance.

        Returns each frame's full name, what it is, and when to use it.
        Call this to understand which frame to choose for a given analysis task.

        Returns:
            status, frame_count,
            frames (list of dicts, each with frame name, full_name,
            description, and usage guidance).
        """
        from .frames import list_frames_with_descriptions

        frames = list_frames_with_descriptions()
        return {
            "status": "success",
            "cache_size_mb": _cache_size_mb(),
            "frame_count": len(frames),
            "frames": frames,
        }

    @mcp.tool()
    def manage_kernels(
        action: str,
        mission: str = "",
        filenames: list[str] | None = None,
    ) -> dict:
        """Manage SPICE kernels: check status, load, clean cache, check remote, or purge.

        Args:
            action: One of:
                - "status" — show loaded kernels and cache disk usage grouped by mission
                - "load" — download (if needed) and load kernels for a mission (requires mission param)
                - "unload_all" — unload all kernels from memory (keeps files on disk)
                - "delete" — delete cached files for a mission (requires mission param) or specific files (requires filenames param). Use "GENERIC" as mission to delete generic kernels.
                - "check_remote" — check remote NAIF directory for new .bsp files not in the configured set (requires mission param, single-file missions only)
                - "purge" — delete ALL cached kernel files and unload everything
            mission: Mission name (required for "load", "delete" by mission, and "check_remote")
            filenames: List of specific filenames to delete (for "delete" action only)

        Returns:
            All actions return status. Additionally:
            - "status": loaded_kernels (list), loaded_count, cache (dict grouped by mission with file sizes).
            - "load": message, loaded (list of loaded kernel filenames).
            - "unload_all": message.
            - "delete": deleted (list), not_found (list), freed_bytes.
            - "check_remote": cache_size_mb, mission, configured (list), available (list), new_files (list).
            - "purge": deleted (list), freed_bytes.
        """
        from .kernel_manager import get_kernel_manager

        km = get_kernel_manager()

        if action == "status":
            loaded = km.list_loaded()
            cache = km.get_cache_info()
            return {
                "status": "success",
                "cache_size_mb": _cache_size_mb(),
                "loaded_kernels": loaded,
                "loaded_count": len(loaded),
                "cache": cache,
            }

        elif action == "load":
            if not mission:
                return {
                    "status": "error",
                    "message": "mission parameter required for load",
                }
            from .missions import resolve_mission

            try:
                _, mission_key = resolve_mission(mission)
                km.ensure_mission_kernels(mission_key)
                return {
                    "status": "success",
                    "cache_size_mb": _cache_size_mb(),
                    "message": f"Kernels loaded for {mission_key}",
                    "loaded": km.list_loaded(),
                }
            except Exception as e:
                return {"status": "error", "message": str(e)}

        elif action == "unload_all":
            km.unload_all()
            return {"status": "success", "cache_size_mb": _cache_size_mb(), "message": "All kernels unloaded"}

        elif action == "delete":
            if filenames:
                result = km.delete_cached_files(filenames)
                return {"status": "success", "cache_size_mb": _cache_size_mb(), **result}
            if not mission:
                return {
                    "status": "error",
                    "message": "delete requires either mission or filenames parameter. "
                    "Use action='status' to see cached files grouped by mission.",
                }
            from .missions import resolve_mission

            try:
                if mission.upper() == "GENERIC":
                    mission_key = "GENERIC"
                else:
                    _, mission_key = resolve_mission(mission)
                result = km.delete_mission_cache(mission_key)
                return {"status": "success", "cache_size_mb": _cache_size_mb(), **result}
            except Exception as e:
                return {"status": "error", "message": str(e)}

        elif action == "check_remote":
            if not mission:
                return {
                    "status": "error",
                    "message": "mission parameter required for check_remote",
                }
            from .missions import resolve_mission

            try:
                _, mission_key = resolve_mission(mission)
                result = km.check_remote_kernels(mission_key)
                return {
                    "status": "success",
                    "cache_size_mb": _cache_size_mb(),
                    **result,
                }
            except Exception as e:
                return {"status": "error", "message": str(e)}

        elif action == "purge":
            result = km.purge_cache()
            return {"status": "success", "cache_size_mb": _cache_size_mb(), **result}

        else:
            return {
                "status": "error",
                "message": (
                    f"Unknown action '{action}'. "
                    f"Use: status, load, unload_all, delete, check_remote, purge"
                ),
            }

    return mcp


def main():
    """CLI entrypoint for the SPICE MCP server."""
    parser = argparse.ArgumentParser(
        description="xhelio-spice MCP server for spacecraft ephemeris"
    )
    parser.add_argument(
        "-v", "--verbose", action="store_true", help="Enable verbose logging"
    )
    args, _ = parser.parse_known_args()

    if args.verbose:
        logging.basicConfig(level=logging.DEBUG, stream=sys.stderr)
    else:
        logging.basicConfig(level=logging.WARNING, stream=sys.stderr)

    server = _create_server()
    server.run()


if __name__ == "__main__":
    main()
