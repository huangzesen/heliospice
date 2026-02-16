"""
Spacecraft position and trajectory computation via SPICE.

All functions resolve mission names, ensure kernels are loaded,
and call SpiceyPy under the KernelManager lock for thread safety.
"""

import logging
from datetime import datetime

import numpy as np
import pandas as pd
import spiceypy as spice

from .missions import resolve_mission, MISSION_NAIF_IDS
from .kernel_manager import get_kernel_manager

logger = logging.getLogger("heliospice")

# Astronomical unit in km (IAU 2012)
AU_KM = 149597870.7


def _resolve_body(name: str) -> tuple[int, str]:
    """Resolve a body name to (NAIF ID, canonical key).

    Tries mission registry first, then falls back to SPICE bodn2c.
    """
    try:
        return resolve_mission(name)
    except KeyError:
        pass

    # Try SPICE built-in name resolution
    key = name.strip().upper().replace("-", "_")
    if key in MISSION_NAIF_IDS:
        return MISSION_NAIF_IDS[key], key

    # Let SPICE try
    km = get_kernel_manager()
    km.ensure_generic_kernels()
    with km.lock:
        try:
            naif_id = spice.bodn2c(name.strip())
            return naif_id, name.strip().upper()
        except Exception:
            raise KeyError(f"Cannot resolve body name '{name}'")


def _ensure_kernels(target_key: str, observer_key: str) -> None:
    """Ensure relevant kernels are loaded for both target and observer."""
    km = get_kernel_manager()
    km.ensure_generic_kernels()

    from .missions import MISSION_KERNELS
    for key in (target_key, observer_key):
        if key in MISSION_KERNELS:
            km.ensure_mission_kernels(key)


def _to_et(time_input) -> float:
    """Convert a datetime or ISO string to SPICE ephemeris time (ET).

    Args:
        time_input: datetime object, ISO 8601 string, or "YYYY-MM-DDTHH:MM:SS".

    Returns:
        SPICE ephemeris time (seconds past J2000).
    """
    if isinstance(time_input, datetime):
        time_str = time_input.strftime("%Y-%m-%dT%H:%M:%S")
    elif isinstance(time_input, str):
        time_str = time_input.strip()
    else:
        time_str = str(time_input)

    return spice.utc2et(time_str)


def _parse_step(step: str) -> float:
    """Parse a step string like '1h', '30m', '1d' into seconds."""
    step = step.strip().lower()
    if step.endswith("d"):
        return float(step[:-1]) * 86400
    elif step.endswith("h"):
        return float(step[:-1]) * 3600
    elif step.endswith("m"):
        return float(step[:-1]) * 60
    elif step.endswith("s"):
        return float(step[:-1])
    else:
        return float(step)  # assume seconds


def get_position(
    target: str,
    observer: str = "SUN",
    time: str | datetime = "2024-01-01T00:00:00",
    frame: str = "ECLIPJ2000",
) -> dict:
    """Get the position of a target relative to an observer at a single time.

    Args:
        target: Target body name (e.g., "PSP", "Earth", "ACE").
        observer: Observer body name (default: "SUN").
        time: UTC time as ISO string or datetime.
        frame: Reference frame (default: "ECLIPJ2000").

    Returns:
        Dict with keys: x, y, z (km), r_km, r_au, light_time_s,
        target, observer, frame, time.
    """
    target_id, target_key = _resolve_body(target)
    observer_id, observer_key = _resolve_body(observer)
    _ensure_kernels(target_key, observer_key)

    km = get_kernel_manager()
    with km.lock:
        et = _to_et(time)
        pos, lt = spice.spkpos(str(target_id), et, frame, "NONE", str(observer_id))

    x, y, z = float(pos[0]), float(pos[1]), float(pos[2])
    r_km = float(np.sqrt(x**2 + y**2 + z**2))

    return {
        "x_km": x,
        "y_km": y,
        "z_km": z,
        "r_km": r_km,
        "r_au": r_km / AU_KM,
        "light_time_s": float(lt),
        "target": target_key,
        "observer": observer_key,
        "frame": frame,
        "time": str(time),
    }


def get_state(
    target: str,
    observer: str = "SUN",
    time: str | datetime = "2024-01-01T00:00:00",
    frame: str = "ECLIPJ2000",
) -> dict:
    """Get position and velocity of a target at a single time.

    Args:
        target: Target body name.
        observer: Observer body name.
        time: UTC time as ISO string or datetime.
        frame: Reference frame.

    Returns:
        Dict with position (x,y,z km), velocity (vx,vy,vz km/s),
        distance (r_km, r_au), speed_km_s, light_time_s.
    """
    target_id, target_key = _resolve_body(target)
    observer_id, observer_key = _resolve_body(observer)
    _ensure_kernels(target_key, observer_key)

    km = get_kernel_manager()
    with km.lock:
        et = _to_et(time)
        state, lt = spice.spkezr(str(target_id), et, frame, "NONE", str(observer_id))

    x, y, z = float(state[0]), float(state[1]), float(state[2])
    vx, vy, vz = float(state[3]), float(state[4]), float(state[5])
    r_km = float(np.sqrt(x**2 + y**2 + z**2))
    speed = float(np.sqrt(vx**2 + vy**2 + vz**2))

    return {
        "x_km": x,
        "y_km": y,
        "z_km": z,
        "vx_km_s": vx,
        "vy_km_s": vy,
        "vz_km_s": vz,
        "r_km": r_km,
        "r_au": r_km / AU_KM,
        "speed_km_s": speed,
        "light_time_s": float(lt),
        "target": target_key,
        "observer": observer_key,
        "frame": frame,
        "time": str(time),
    }


def get_trajectory(
    target: str,
    observer: str = "SUN",
    time_start: str | datetime = "2024-01-01",
    time_end: str | datetime = "2024-01-31",
    step: str = "1h",
    frame: str = "ECLIPJ2000",
    include_velocity: bool = False,
) -> pd.DataFrame:
    """Compute a trajectory (position timeseries) over a time range.

    Args:
        target: Target body name (e.g., "PSP", "Earth").
        observer: Observer body name (default: "SUN").
        time_start: Start time (ISO string or datetime).
        time_end: End time (ISO string or datetime).
        step: Time step (e.g., "1h", "30m", "1d"). Default: "1h".
        frame: Reference frame (default: "ECLIPJ2000").
        include_velocity: If True, include vx, vy, vz columns.

    Returns:
        DataFrame with DatetimeIndex and columns:
        x_km, y_km, z_km, r_km, r_au (+ vx_km_s, vy_km_s, vz_km_s if requested).
    """
    target_id, target_key = _resolve_body(target)
    observer_id, observer_key = _resolve_body(observer)
    _ensure_kernels(target_key, observer_key)

    km = get_kernel_manager()
    step_s = _parse_step(step)

    with km.lock:
        et_start = _to_et(time_start)
        et_end = _to_et(time_end)

    n_steps = max(1, int((et_end - et_start) / step_s) + 1)
    # Cap at 100k points to prevent memory issues
    if n_steps > 100_000:
        step_s = (et_end - et_start) / 100_000
        n_steps = 100_001
        logger.warning("Trajectory capped at 100k points; step adjusted to %.1fs", step_s)

    et_times = np.linspace(et_start, et_end, n_steps)

    # Compute positions (and optionally velocities) under lock
    positions = np.empty((n_steps, 3))
    velocities = np.empty((n_steps, 3)) if include_velocity else None
    utc_times = []

    with km.lock:
        for i, et in enumerate(et_times):
            if include_velocity:
                state, _ = spice.spkezr(str(target_id), et, frame, "NONE", str(observer_id))
                positions[i] = state[:3]
                velocities[i] = state[3:]
            else:
                pos, _ = spice.spkpos(str(target_id), et, frame, "NONE", str(observer_id))
                positions[i] = pos
            utc_times.append(spice.et2utc(et, "ISOC", 3))

    # Build DataFrame
    index = pd.to_datetime(utc_times)
    r_km = np.sqrt(np.sum(positions**2, axis=1))

    data = {
        "x_km": positions[:, 0],
        "y_km": positions[:, 1],
        "z_km": positions[:, 2],
        "r_km": r_km,
        "r_au": r_km / AU_KM,
    }

    if include_velocity:
        data["vx_km_s"] = velocities[:, 0]
        data["vy_km_s"] = velocities[:, 1]
        data["vz_km_s"] = velocities[:, 2]

    df = pd.DataFrame(data, index=index)
    df.index.name = "time"

    logger.info(
        "Computed trajectory: %s rel. %s, %d points, %s to %s",
        target_key, observer_key, n_steps,
        utc_times[0] if utc_times else "?",
        utc_times[-1] if utc_times else "?",
    )

    return df
