"""
SPICE MCP server for spacecraft ephemeris.

Exposes SPICE position/trajectory/transform capabilities as MCP tools
over stdio transport. Any MCP-compatible client (Claude Desktop, Claude Code,
Cursor, etc.) can connect and query spacecraft positions.

This server is lightweight — no LLM needed. It wraps heliospice directly.

Usage:
    heliospice-mcp                  # Via CLI entrypoint
    python -m heliospice.server     # Via module
    heliospice-mcp -v               # With verbose logging
"""

import argparse
import logging
import sys

try:
    from mcp.server.fastmcp import FastMCP
except ImportError:
    FastMCP = None

# ---------------------------------------------------------------------------
# Response size limit
# ---------------------------------------------------------------------------
# Max data points returned in a single trajectory/velocity response.
# Requests exceeding this are rejected with summary stats unless the caller
# explicitly opts in with allow_large_response=True.
_MAX_RESPONSE_POINTS = 10_000


def _create_server() -> "FastMCP":
    """Create and configure the MCP server with all tools."""
    if FastMCP is None:
        raise ImportError(
            "MCP support requires the 'mcp' package. "
            "Install it with: pip install heliospice[mcp]"
        )

    def _cache_size_mb() -> float:
        """Return current kernel cache size in MB."""
        from .kernel_manager import get_kernel_manager
        return round(get_kernel_manager().get_cache_size_bytes() / (1024 * 1024), 2)

    mcp = FastMCP(
        "spice-ephemeris",
        instructions=(
            "SPICE ephemeris server for spacecraft position and trajectory queries. "
            "Supports 36 spacecraft: heliophysics missions (PSP, Solar Orbiter, SOHO, "
            "IBEX, STEREO-A/B, Helios 1/2, Ulysses, Van Allen Probes A/B, THEMIS A–E) "
            "and planetary/deep-space missions (Cassini, Juno, Voyager 1/2, MAVEN, "
            "New Horizons, Galileo, Pioneer 10/11, MESSENGER, Dawn, Lucy, Europa Clipper, "
            "Psyche, JUICE, BepiColombo, Venus Express, Pioneer Venus, InSight, MRO, "
            "Mars 2020, LRO, Lunar Prospector, MGS). ACE, Wind, and DSCOVR have NAIF IDs "
            "but no SPK kernels. Kernels are auto-downloaded from NAIF on first use. "
            "Use list_coordinate_frames to see available coordinate frames before "
            "querying — frame is a required parameter. Use get_spacecraft_ephemeris for "
            "position/velocity at a single time or as a timeseries, compute_distance for "
            "distances between bodies, and transform_coordinates for frame transforms."
        ),
    )

    @mcp.tool()
    def get_spacecraft_ephemeris(
        spacecraft: str,
        time: str,
        frame: str,
        observer: str,
        time_end: str = "",
        step: str = "1h",
        include_velocity: bool = False,
        allow_large_response: bool = False,
    ) -> dict:
        """Get spacecraft position and/or velocity — single time or timeseries.

        Single-time mode (time_end empty): returns position in km, distance in km
        and AU, and light time. With include_velocity=True, also returns velocity
        components and speed.

        Timeseries mode (time_end provided): returns summary stats, preview rows,
        and full data records. With include_velocity=True, adds velocity columns
        and speed stats.

        Args:
            spacecraft: Spacecraft name (e.g., "PSP", "ACE", "Solar Orbiter", "Earth")
            time: UTC time in ISO 8601 format. For timeseries, this is the start time.
            frame: Coordinate frame (e.g., "ECLIPJ2000", "GSE", "RTN"). Use list_coordinate_frames to see all options.
            observer: Observer body (e.g., "SUN", "EARTH"). Use "EARTH" for geocentric.
            time_end: End time for timeseries (ISO 8601). Leave empty for single-time query.
            step: Time step for timeseries (e.g., "1m", "1h", "6h", "1d"). Only used when time_end is provided.
            include_velocity: If True, include velocity components (vx, vy, vz in km/s) and speed.
            allow_large_response: Set True to return more than 10,000 data points. Default False — large responses are rejected with summary stats and a hint to increase the step size or narrow the time range. Only used for timeseries.

        Examples:
            - get_spacecraft_ephemeris("PSP", "2024-01-15", "ECLIPJ2000", "SUN")
            - get_spacecraft_ephemeris("PSP", "2024-01-15", "ECLIPJ2000", "SUN", include_velocity=True)
            - get_spacecraft_ephemeris("PSP", "2024-01-01", "ECLIPJ2000", "SUN", time_end="2024-01-31", step="1h")
            - get_spacecraft_ephemeris("PSP", "2024-01-01", "ECLIPJ2000", "SUN", time_end="2024-01-31", step="1h", include_velocity=True)
        """
        try:
            # --- Single-time mode ---
            if not time_end:
                if include_velocity:
                    from .ephemeris import get_state
                    result = get_state(
                        target=spacecraft, observer=observer, time=time, frame=frame
                    )
                else:
                    from .ephemeris import get_position
                    result = get_position(
                        target=spacecraft, observer=observer, time=time, frame=frame
                    )
                return {"status": "success", "cache_size_mb": _cache_size_mb(), **result}

            # --- Timeseries mode ---
            from .ephemeris import get_trajectory
            import numpy as np

            df = get_trajectory(
                target=spacecraft,
                observer=observer,
                time_start=time,
                time_end=time_end,
                step=step,
                frame=frame,
                include_velocity=include_velocity,
            )

            # Summary stats
            summary = {
                "status": "success",
                "cache_size_mb": _cache_size_mb(),
                "spacecraft": spacecraft,
                "observer": observer,
                "frame": frame,
                "time_start": str(df.index[0]),
                "time_end": str(df.index[-1]),
                "n_points": len(df),
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
            }

            # Add speed stats when velocity is included
            if include_velocity:
                speed = np.sqrt(
                    df["vx_km_s"]**2 + df["vy_km_s"]**2 + df["vz_km_s"]**2
                )
                df["speed_km_s"] = speed
                summary["columns"] = list(df.columns)
                summary["speed_km_s"] = {
                    "min": round(float(speed.min()), 3),
                    "max": round(float(speed.max()), 3),
                    "mean": round(float(speed.mean()), 3),
                }

            # Preview: first/last few data points
            n_preview = min(5, len(df))
            preview_rows = []
            for idx in list(range(n_preview)) + list(range(max(n_preview, len(df) - n_preview), len(df))):
                row = df.iloc[idx]
                entry = {"time": str(df.index[idx])}
                for col in df.columns:
                    entry[col] = round(float(row[col]), 6 if "au" in col else 3 if "km_s" in col else 1)
                preview_rows.append(entry)
            summary["preview"] = preview_rows

            # Guard: reject large responses unless caller opted in
            if len(df) > _MAX_RESPONSE_POINTS and not allow_large_response:
                summary["status"] = "error"
                summary["message"] = (
                    f"Response contains {len(df):,} data points, exceeding the "
                    f"{_MAX_RESPONSE_POINTS:,} point limit. Either increase the step "
                    f"size, narrow the time range, or set allow_large_response=True."
                )
                return summary

            # Full data for downstream storage/plotting
            records = []
            for ts, row in df.iterrows():
                record = {"time": str(ts)}
                for col in df.columns:
                    record[col] = float(row[col])
                records.append(record)
            summary["data"] = records

            return summary

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
        """
        from .missions import list_supported_missions, MISSION_KERNELS, SEGMENTED_MISSIONS
        from .kernel_manager import get_kernel_manager

        missions = list_supported_missions()
        km = get_kernel_manager()
        loaded = set(km.list_loaded())

        for m in missions:
            key = m["mission_key"]
            kernel_files = MISSION_KERNELS.get(key, {})
            m["kernels_loaded"] = all(f in loaded for f in kernel_files) if kernel_files else False
            m["segmented"] = key in SEGMENTED_MISSIONS

        return {
            "status": "success",
            "mission_count": len(missions),
            "missions": missions,
        }

    @mcp.tool()
    def list_coordinate_frames() -> dict:
        """List all supported coordinate frames with descriptions and usage guidance.

        Returns each frame's full name, what it is, and when to use it.
        Call this to understand which frame to choose for a given analysis task.
        """
        from .frames import list_frames_with_descriptions
        frames = list_frames_with_descriptions()
        return {
            "status": "success",
            "frame_count": len(frames),
            "frames": frames,
        }

    @mcp.tool()
    def manage_kernels(
        action: str,
        mission: str = "",
        filenames: list[str] | None = None,
    ) -> dict:
        """Manage SPICE kernels: check status, download, load, clean cache, check remote, or purge.

        Args:
            action: One of:
                - "status" — show loaded kernels and cache disk usage grouped by mission
                - "download" — download kernels for a mission (requires mission param)
                - "load" — download + load kernels for a mission
                - "unload_all" — unload all kernels from memory (keeps files on disk)
                - "delete" — delete cached files for a mission (requires mission param) or specific files (requires filenames param). Use "GENERIC" as mission to delete generic kernels.
                - "check_remote" — check remote NAIF directory for new .bsp files not in the configured set (requires mission param, single-file missions only)
                - "purge" — delete ALL cached kernel files and unload everything
            mission: Mission name (required for "download", "load", "delete" by mission, and "check_remote")
            filenames: List of specific filenames to delete (for "delete" action only)
        """
        from .kernel_manager import get_kernel_manager

        km = get_kernel_manager()

        if action == "status":
            loaded = km.list_loaded()
            cache = km.get_cache_info()
            return {
                "status": "success",
                "loaded_kernels": loaded,
                "loaded_count": len(loaded),
                "cache": cache,
            }

        elif action == "download":
            if not mission:
                return {"status": "error", "message": "mission parameter required for download"}
            from .missions import resolve_mission
            try:
                _, mission_key = resolve_mission(mission)
                km.ensure_mission_kernels(mission_key)
                return {
                    "status": "success",
                    "message": f"Kernels downloaded and loaded for {mission_key}",
                    "loaded": km.list_loaded(),
                }
            except Exception as e:
                return {"status": "error", "message": str(e)}

        elif action == "load":
            if not mission:
                return {"status": "error", "message": "mission parameter required for load"}
            from .missions import resolve_mission
            try:
                _, mission_key = resolve_mission(mission)
                km.ensure_mission_kernels(mission_key)
                return {
                    "status": "success",
                    "message": f"Kernels loaded for {mission_key}",
                    "loaded": km.list_loaded(),
                }
            except Exception as e:
                return {"status": "error", "message": str(e)}

        elif action == "unload_all":
            km.unload_all()
            return {"status": "success", "message": "All kernels unloaded"}

        elif action == "delete":
            if filenames:
                result = km.delete_cached_files(filenames)
                return {"status": "success", **result}
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
                return {"status": "success", **result}
            except Exception as e:
                return {"status": "error", "message": str(e)}

        elif action == "check_remote":
            if not mission:
                return {"status": "error", "message": "mission parameter required for check_remote"}
            from .missions import resolve_mission
            try:
                _, mission_key = resolve_mission(mission)
                result = km.check_remote_kernels(mission_key)
                return {"status": "success", "cache_size_mb": _cache_size_mb(), **result}
            except Exception as e:
                return {"status": "error", "message": str(e)}

        elif action == "purge":
            result = km.purge_cache()
            return {"status": "success", **result}

        else:
            return {
                "status": "error",
                "message": (
                    f"Unknown action '{action}'. "
                    f"Use: status, download, load, unload_all, delete, check_remote, purge"
                ),
            }

    return mcp


def main():
    """CLI entrypoint for the SPICE MCP server."""
    parser = argparse.ArgumentParser(description="heliospice MCP server for spacecraft ephemeris")
    parser.add_argument("-v", "--verbose", action="store_true", help="Enable verbose logging")
    args, _ = parser.parse_known_args()

    if args.verbose:
        logging.basicConfig(level=logging.DEBUG, stream=sys.stderr)
    else:
        logging.basicConfig(level=logging.WARNING, stream=sys.stderr)

    server = _create_server()
    server.run()


if __name__ == "__main__":
    main()
