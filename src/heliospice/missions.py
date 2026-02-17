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
    # Heliophysics missions
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
    "HELIOS_1": -301,
    "HELIOS_2": -302,
    "ULYSSES": -55,
    "THEMIS_A": -650,
    "THEMIS_B": -651,  # aka ARTEMIS P1
    "THEMIS_C": -652,  # aka ARTEMIS P2
    "THEMIS_D": -653,
    "THEMIS_E": -654,
    # Planetary / deep-space missions
    "CASSINI": -82,
    "JUNO": -61,
    "VOYAGER_1": -31,
    "VOYAGER_2": -32,
    "MAVEN": -202,
    "GALILEO": -77,
    "PIONEER_10": -23,
    "PIONEER_11": -24,
    "MESSENGER": -236,
    "NEW_HORIZONS": -98,
    "DAWN": -203,
    "LUCY": -49,
    "EUROPA_CLIPPER": -159,
    "PSYCHE": -255,
    "JUICE": -28,
    "BEPICOLOMBO": -121,
    "MARS_2020": -168,
    "MRO": -74,
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
    "HELIOS1": "HELIOS_1",
    "HELIOS 1": "HELIOS_1",
    "HELIOS2": "HELIOS_2",
    "HELIOS 2": "HELIOS_2",
    "THEMIS": "THEMIS_A",
    "ARTEMIS_P1": "THEMIS_B",
    "ARTEMIS P1": "THEMIS_B",
    "ARTEMIS_P2": "THEMIS_C",
    "ARTEMIS P2": "THEMIS_C",
    "EUROPA CLIPPER": "EUROPA_CLIPPER",
    "EUROPACLIPPER": "EUROPA_CLIPPER",
    "CLIPPER": "EUROPA_CLIPPER",
    "PERSEVERANCE": "MARS_2020",
    "MARS2020": "MARS_2020",
    "MARS 2020": "MARS_2020",
    "BEPI": "BEPICOLOMBO",
    "BEPI COLOMBO": "BEPICOLOMBO",
    "BEPI_COLOMBO": "BEPICOLOMBO",
    "MPO": "BEPICOLOMBO",
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
        "STEREO-A_merged.bsp": (
            f"{_NAIF_BASE}/STEREO/kernels/spk/"
            "STEREO-A_merged.bsp"
        ),
    },
    "STEREO_B": {
        "behind_2026_029_01.epm.bsp": (
            "https://sohoftp.nascom.nasa.gov/solarsoft/stereo/gen/data/spice/epm/behind/"
            "behind_2026_029_01.epm.bsp"
        ),
    },
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
    "MAVEN": {
        "maven_orb_rec.bsp": (
            f"{_NAIF_BASE}/MAVEN/kernels/spk/"
            "maven_orb_rec.bsp"
        ),
    },
    "NEW_HORIZONS": {
        "nh_pred_alleph_od161.bsp": (
            f"{_NAIF_BASE}/pds/data/nh-j_p_ss-spice-6-v1.0/nhsp_1000/data/spk/"
            "nh_pred_alleph_od161.bsp"
        ),
    },
    "ULYSSES": {
        "ulysses_1990_2009_2050.bsp": (
            f"{_NAIF_BASE}/ULYSSES/kernels/spk/"
            "ulysses_1990_2009_2050.bsp"
        ),
    },
    "PIONEER_10": {
        "p10-a.bsp": (
            f"{_NAIF_BASE}/PIONEER10/kernels/spk/"
            "p10-a.bsp"
        ),
    },
    "PIONEER_11": {
        "p11-a.bsp": (
            f"{_NAIF_BASE}/PIONEER11/kernels/spk/"
            "p11-a.bsp"
        ),
    },
    "GALILEO": {
        "gll_951120_021126_raj2021.bsp": (
            f"{_NAIF_BASE}/GLL/kernels/spk/"
            "gll_951120_021126_raj2021.bsp"
        ),
    },
    "HELIOS_1": {
        "100528R_helios1_74345_81272.bsp": (
            f"{_NAIF_BASE}/HELIOS/kernels/spk/"
            "100528R_helios1_74345_81272.bsp"
        ),
        "160707AP_helios1_81272_86074.bsp": (
            f"{_NAIF_BASE}/HELIOS/kernels/spk/"
            "160707AP_helios1_81272_86074.bsp"
        ),
    },
    "HELIOS_2": {
        "100607R_helios2_76016_80068.bsp": (
            f"{_NAIF_BASE}/HELIOS/kernels/spk/"
            "100607R_helios2_76016_80068.bsp"
        ),
    },
    "MESSENGER": {
        "msgr_040803_150430_150430_od431sc_2.bsp": (
            f"{_NAIF_BASE}/pds/data/mess-e_v_h-spice-6-v1.0/"
            "messsp_1000/data/spk/msgr_040803_150430_150430_od431sc_2.bsp"
        ),
    },
    "THEMIS_A": {
        "THEMIS_A_definitive_trajectory.bsp": (
            f"{_NAIF_BASE}/THEMIS/kernels/spk/"
            "THEMIS_A_definitive_trajectory.bsp"
        ),
    },
    "THEMIS_B": {
        "THEMIS_B_definitive_trajectory.bsp": (
            f"{_NAIF_BASE}/THEMIS/kernels/spk/"
            "THEMIS_B_definitive_trajectory.bsp"
        ),
    },
    "THEMIS_C": {
        "THEMIS_C_definitive_trajectory.bsp": (
            f"{_NAIF_BASE}/THEMIS/kernels/spk/"
            "THEMIS_C_definitive_trajectory.bsp"
        ),
    },
    "THEMIS_D": {
        "THEMIS_D_definitive_trajectory.bsp": (
            f"{_NAIF_BASE}/THEMIS/kernels/spk/"
            "THEMIS_D_definitive_trajectory.bsp"
        ),
    },
    "THEMIS_E": {
        "THEMIS_E_definitive_trajectory.bsp": (
            f"{_NAIF_BASE}/THEMIS/kernels/spk/"
            "THEMIS_E_definitive_trajectory.bsp"
        ),
    },
    "DAWN": {
        "dawn_ephem_2018.bsp": (
            f"{_NAIF_BASE}/DAWN/kernels/spk/"
            "Dawn_ephem_2018.bsp"
        ),
    },
    "LUCY": {
        "lcy_250917_330402_250730_OD093-R-MEF2-P-TCM37a-P_v1.bsp": (
            f"{_NAIF_BASE}/LUCY/kernels/spk/"
            "lcy_250917_330402_250730_OD093-R-MEF2-P-TCM37a-P_v1.bsp"
        ),
    },
    "EUROPA_CLIPPER": {
        "trj_251001-260516-dco2601141914-cruise013-predict-OD078-v1.bsp": (
            f"{_NAIF_BASE}/EUROPACLIPPER/kernels/spk/"
            "trj_251001-260516-dco2601141914-cruise013-predict-OD078-v1.bsp"
        ),
    },
    "PSYCHE": {
        "psyche_sc-eph_250912-260601_260114_v1.bsp": (
            f"{_NAIF_BASE}/PSYCHE/kernels/spk/"
            "psyche_sc-eph_250912-260601_260114_v1.bsp"
        ),
    },
    "JUICE": {
        "juice_crema_5_1_150lb_23_1_v01.bsp": (
            f"{_NAIF_BASE}/JUICE/kernels/spk/"
            "juice_crema_5_1_150lb_23_1_v01.bsp"
        ),
    },
    "BEPICOLOMBO": {
        "bc_mtm_scp_cruise_20181016_20251205_v01.bsp": (
            f"{_NAIF_BASE}/BEPICOLOMBO/kernels/spk/"
            "bc_mtm_scp_cruise_20181016_20251205_v01.bsp"
        ),
    },
}

# Missions with segmented SPK files — each maps to a manifest JSON
# listing individual segment files with time coverage.
SEGMENTED_MISSIONS: dict[str, str] = {
    "CASSINI": "cassini.json",
    "MRO": "mro.json",
    "MARS_2020": "mars2020.json",
}


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def has_kernels(mission_key: str) -> bool:
    """Check if a mission has kernel support (single-file or segmented)."""
    return mission_key in MISSION_KERNELS or mission_key in SEGMENTED_MISSIONS

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
            "has_kernels": has_kernels(key),
        }
        for key, naif_id in sorted(MISSION_NAIF_IDS.items())
        if naif_id < 0  # spacecraft only
    ]
