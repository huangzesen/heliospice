"""
Mission registry for SPICE operations.

Maps mission IDs to NAIF integer IDs, kernel source URLs,
and provides fuzzy mission name resolution.
"""

# ---------------------------------------------------------------------------
# NAIF ID mapping
# ---------------------------------------------------------------------------

# Maps mission keys (uppercase) to NAIF body/spacecraft IDs.
# Negative IDs are spacecraft; positive are natural bodies.
MISSION_NAIF_IDS: dict[str, int] = {
    # Heliophysics missions (CDAWeb)
    "PSP": -96,
    "SOLO": -144,
    "ACE": -92,
    "WIND": -8,
    "DSCOVR": -78,
    "MMS1": -189,
    "MMS2": -190,
    "MMS3": -191,
    "MMS4": -192,
    "STEREO_A": -234,
    "STEREO_B": -235,
    # Planetary missions (PDS PPI)
    "CASSINI": -82,
    "JUNO": -61,
    "VOYAGER_1": -31,
    "VOYAGER_2": -32,
    "MAVEN": -202,
    "GALILEO": -77,
    "PIONEER_10": -23,
    "PIONEER_11": -24,
    "ULYSSES": -55,
    "MESSENGER": -236,
    "NEW_HORIZONS": -98,
    # Natural bodies (for observer/target)
    "SUN": 10,
    "EARTH": 399,
    "MOON": 301,
    "MERCURY": 199,
    "VENUS": 299,
    "MARS": 4,        # Barycenter — body center (499) not in de440s.bsp
    "JUPITER": 5,     # Barycenter — body center (599) not in de440s.bsp
    "SATURN": 6,      # Barycenter — body center (699) not in de440s.bsp
    "URANUS": 7,      # Barycenter — body center (799) not in de440s.bsp
    "NEPTUNE": 8,     # Barycenter — body center (899) not in de440s.bsp
    "PLUTO": 9,       # Barycenter — body center (999) not in de440s.bsp
    # Barycenters
    "SSB": 0,  # Solar System Barycenter
    "EARTH_BARYCENTER": 3,
    "MARS_BARYCENTER": 4,
    "JUPITER_BARYCENTER": 5,
    "SATURN_BARYCENTER": 6,
}

# Aliases: common names -> canonical mission key
_ALIASES: dict[str, str] = {
    "PARKER": "PSP",
    "PARKER SOLAR PROBE": "PSP",
    "SOLAR ORBITER": "SOLO",
    "SOLAR_ORBITER": "SOLO",
    "SOLORB": "SOLO",
    "MMS": "MMS1",
    "STEREOA": "STEREO_A",
    "STEREO-A": "STEREO_A",
    "STEREOB": "STEREO_B",
    "STEREO-B": "STEREO_B",
    "VOYAGER1": "VOYAGER_1",
    "VOYAGER 1": "VOYAGER_1",
    "VGR1": "VOYAGER_1",
    "VOYAGER2": "VOYAGER_2",
    "VOYAGER 2": "VOYAGER_2",
    "VGR2": "VOYAGER_2",
    "PIONEER10": "PIONEER_10",
    "PIONEER 10": "PIONEER_10",
    "PIONEER11": "PIONEER_11",
    "PIONEER 11": "PIONEER_11",
    "NEWHORIZONS": "NEW_HORIZONS",
    "NEW HORIZONS": "NEW_HORIZONS",
    "NH": "NEW_HORIZONS",
}

# ---------------------------------------------------------------------------
# Kernel sources — URLs to NAIF/ESA kernel repositories
# ---------------------------------------------------------------------------

_NAIF_BASE = "https://naif.jpl.nasa.gov/pub/naif"

# Generic kernels needed by all missions
GENERIC_KERNELS: dict[str, str] = {
    "naif0012.tls": f"{_NAIF_BASE}/generic_kernels/lsk/naif0012.tls",
    "pck00011.tpc": f"{_NAIF_BASE}/generic_kernels/pck/pck00011.tpc",
    "de440s.bsp": f"{_NAIF_BASE}/generic_kernels/spk/planets/de440s.bsp",
    "gm_de440.tpc": f"{_NAIF_BASE}/generic_kernels/pck/gm_de440.tpc",
}

# Mission-specific kernel sets: {filename: url}
# Each mission needs at minimum an SPK (trajectory) file.
# Some also need FK (frame kernel), SCLK (clock kernel), etc.
MISSION_KERNELS: dict[str, dict[str, str]] = {
    "PSP": {
        "spp_nom_20180812_20300101_v043_PostV7.bsp": (
            "https://cdaweb.gsfc.nasa.gov/pub/data/psp/ephemeris/spice/ephemerides/"
            "spp_nom_20180812_20300101_v043_PostV7.bsp"
        ),
    },
    "SOLO": {
        "solo_ANC_soc-orbit-stp_20200210-20301120_399_V1_00513_V01.bsp": (
            "https://spiftp.esac.esa.int/data/SPICE/SOLAR-ORBITER/kernels/spk/"
            "solo_ANC_soc-orbit-stp_20200210-20301120_399_V1_00513_V01.bsp"
        ),
    },
    "STEREO_A": {
        "ahead_2017_061_5295day_predict.epm.bsp": (
            "https://sohoftp.nascom.nasa.gov/solarsoft/stereo/gen/data/spice/epm/ahead/"
            "ahead_2017_061_5295day_predict.epm.bsp"
        ),
    },
    # NOTE: Cassini requires ~200 SCPSE segment files from NAIF PDS archive.
    # Not yet supported — needs multi-file kernel loading.
    # See: https://naif.jpl.nasa.gov/pub/naif/pds/data/co-s_j_e_v-spice-6-v1.0/cosp_1000/data/spk/
    "JUNO": {
        "juno_rec_orbit.bsp": (
            f"{_NAIF_BASE}/JUNO/kernels/spk/"
            "juno_rec_orbit.bsp"
        ),
    },
    "VOYAGER_1": {
        "vgr1.x2100.bsp": (
            f"{_NAIF_BASE}/VOYAGER/kernels/spk/"
            "vgr1.x2100.bsp"
        ),
    },
    "VOYAGER_2": {
        "vgr2.x2100.bsp": (
            f"{_NAIF_BASE}/VOYAGER/kernels/spk/"
            "vgr2.x2100.bsp"
        ),
    },
    # NOTE: MAVEN kernels on NAIF are individual quarterly segments, not merged.
    # Full coverage requires loading ~50 segment files. Not yet supported.
    # See: https://naif.jpl.nasa.gov/pub/naif/MAVEN/kernels/spk/
    "NEW_HORIZONS": {
        "nh_pred_alleph_od161.bsp": (
            f"{_NAIF_BASE}/pds/data/nh-j_p_ss-spice-6-v1.0/nhsp_1000/data/spk/"
            "nh_pred_alleph_od161.bsp"
        ),
    },
}


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def resolve_mission(name: str) -> tuple[int, str]:
    """Resolve a mission name to (NAIF ID, canonical mission key).

    Performs case-insensitive lookup with alias support.

    Args:
        name: Mission name (e.g., "PSP", "Parker Solar Probe", "ace").

    Returns:
        Tuple of (NAIF integer ID, canonical key string).

    Raises:
        KeyError: If the mission name cannot be resolved.
    """
    key = name.strip().upper().replace("-", "_")

    # Direct match
    if key in MISSION_NAIF_IDS:
        return MISSION_NAIF_IDS[key], key

    # Alias match
    alias_key = _ALIASES.get(key) or _ALIASES.get(name.strip().upper())
    if alias_key and alias_key in MISSION_NAIF_IDS:
        return MISSION_NAIF_IDS[alias_key], alias_key

    # Try without underscores
    compact = key.replace("_", "")
    for canon, naif_id in MISSION_NAIF_IDS.items():
        if canon.replace("_", "") == compact:
            return naif_id, canon

    raise KeyError(
        f"Unknown mission '{name}'. Supported: "
        + ", ".join(sorted(k for k, v in MISSION_NAIF_IDS.items() if v < 0))
    )


def list_supported_missions() -> list[dict]:
    """Return a list of supported missions with NAIF IDs and kernel availability.

    Returns:
        List of dicts with keys: mission_key, naif_id, has_kernels.
    """
    return [
        {
            "mission_key": key,
            "naif_id": naif_id,
            "has_kernels": key in MISSION_KERNELS,
        }
        for key, naif_id in sorted(MISSION_NAIF_IDS.items())
        if naif_id < 0  # spacecraft only
    ]
