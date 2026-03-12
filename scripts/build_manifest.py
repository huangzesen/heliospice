#!/usr/bin/env python3
"""Build segment manifest JSONs for missions with multi-file SPK kernels.

Developer-only script — not part of the installed package.
Requires: spiceypy, requests, beautifulsoup4

Three strategies for extracting time coverage (avoiding full BSP downloads):
  1. "filename" — parse start/stop dates from the filename pattern
  2. "labels"  — download tiny .lbl sidecar files with coverage metadata
  3. "download" — download full BSP and read with spiceypy (fallback)

Usage:
    python scripts/build_manifest.py cassini
    python scripts/build_manifest.py mro
    python scripts/build_manifest.py all
    python scripts/build_manifest.py all --workers 8
"""

import argparse
import json
import re
import tempfile
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import date, timedelta
from pathlib import Path

import requests
import spiceypy as spice
from bs4 import BeautifulSoup

# Where to write output manifests
MANIFEST_DIR = Path(__file__).resolve().parent.parent / "src" / "xhelio_spice" / "manifests"

# LSK needed for time conversion
NAIF_BASE = "https://naif.jpl.nasa.gov/pub/naif"
LSK_URL = f"{NAIF_BASE}/generic_kernels/lsk/naif0012.tls"

DEFAULT_WORKERS = 4


# ---------------------------------------------------------------------------
# Filename date parsers — return (start_iso, stop_iso) or None
# ---------------------------------------------------------------------------

def _parse_yymmdd_pair(filename: str, pattern: re.Pattern) -> tuple[str, str] | None:
    """Parse YYMMDD_YYMMDD from filename."""
    m = pattern.search(filename)
    if not m:
        return None
    s, e = m.group("start"), m.group("end")
    y1 = 1900 + int(s[:2]) if int(s[:2]) > 50 else 2000 + int(s[:2])
    y2 = 1900 + int(e[:2]) if int(e[:2]) > 50 else 2000 + int(e[:2])
    start = f"{y1}-{s[2:4]}-{s[4:6]}"
    stop = f"{y2}-{e[2:4]}-{e[4:6]}"
    return start, stop


def _parse_yyyymmdd_pair(filename: str, pattern: re.Pattern) -> tuple[str, str] | None:
    """Parse YYYYMMDD_YYYYMMDD from filename."""
    m = pattern.search(filename)
    if not m:
        return None
    s, e = m.group("start"), m.group("end")
    start = f"{s[:4]}-{s[4:6]}-{s[6:8]}"
    stop = f"{e[:4]}-{e[4:6]}-{e[6:8]}"
    return start, stop


def _parse_yyyydoy_21day(filename: str, pattern: re.Pattern) -> tuple[str, str] | None:
    """Parse YYYYDOY and add 21 days for stop."""
    m = pattern.search(filename)
    if not m:
        return None
    year = int(m.group("year"))
    doy = int(m.group("doy"))
    start = date(year, 1, 1) + timedelta(days=doy - 1)
    stop = start + timedelta(days=21)
    return start.isoformat(), stop.isoformat()


def _parse_yydoy_pair(filename: str, pattern: re.Pattern) -> tuple[str, str] | None:
    """Parse YYDOY_YYDOY (5-digit codes) from Cassini-style filenames."""
    m = pattern.search(filename)
    if not m:
        return None
    s, e = m.group("start"), m.group("end")
    y1 = 1900 + int(s[:2]) if int(s[:2]) > 50 else 2000 + int(s[:2])
    y2 = 1900 + int(e[:2]) if int(e[:2]) > 50 else 2000 + int(e[:2])
    d1 = date(y1, 1, 1) + timedelta(days=int(s[2:]) - 1)
    d2 = date(y2, 1, 1) + timedelta(days=int(e[2:]) - 1)
    return d1.isoformat(), d2.isoformat()


def _parse_yyyydoy_pair(filename: str, pattern: re.Pattern) -> tuple[str, str] | None:
    """Parse YYYYDOY_YYYYDOY from LRO-style filenames."""
    m = pattern.search(filename)
    if not m:
        return None
    s, e = m.group("start"), m.group("end")
    d1 = date(int(s[:4]), 1, 1) + timedelta(days=int(s[4:]) - 1)
    d2 = date(int(e[:4]), 1, 1) + timedelta(days=int(e[4:]) - 1)
    return d1.isoformat(), d2.isoformat()


def _parse_yymmdd_dash_pair(filename: str, pattern: re.Pattern) -> tuple[str, str] | None:
    """Parse YYMMDD-YYMMDD (dash-separated) from LP-style filenames."""
    m = pattern.search(filename)
    if not m:
        return None
    s, e = m.group("start"), m.group("end")
    y1 = 1900 + int(s[:2]) if int(s[:2]) > 50 else 2000 + int(s[:2])
    y2 = 1900 + int(e[:2]) if int(e[:2]) > 50 else 2000 + int(e[:2])
    start = f"{y1}-{s[2:4]}-{s[4:6]}"
    stop = f"{y2}-{e[2:4]}-{e[4:6]}"
    return start, stop


# ---------------------------------------------------------------------------
# Mission configurations
# ---------------------------------------------------------------------------

# "coverage_strategy" determines how time coverage is extracted:
#   "filename" — parse from filename regex (needs "date_parser" and "date_pattern")
#   "labels"   — download .lbl sidecar files and parse COVERAGE times
#   "download" — download full BSP and read with spiceypy (original method)

MISSION_CONFIGS = {
    "cassini": {
        "base_url": f"{NAIF_BASE}/pds/data/co-s_j_e_v-spice-6-v1.0/cosp_1000/data/spk/",
        "pattern": re.compile(r"^\d{6}R[BU]?_SCPSE_\d{5}_\d{5}\.bsp$", re.IGNORECASE),
        "naif_id": -82,
        "coverage_strategy": "filename",
        "date_parser": _parse_yydoy_pair,
        "date_pattern": re.compile(r"SCPSE_(?P<start>\d{5})_(?P<end>\d{5})"),
    },
    "mro": {
        "base_url": f"{NAIF_BASE}/MRO/kernels/spk/",
        "pattern": re.compile(r"^mro_psp\d+.*\.bsp$", re.IGNORECASE),
        "naif_id": -74,
        # MRO filenames are inconsistent — some have dates, some don't
        "coverage_strategy": "download",
    },
    "mars2020": {
        "base_url": f"{NAIF_BASE}/MARS2020/kernels/spk/",
        "pattern": re.compile(r"^m2020_.*\.bsp$", re.IGNORECASE),
        "naif_id": -168,
        "coverage_strategy": "download",
    },
    "lro": {
        "base_url": f"{NAIF_BASE}/pds/data/lro-l-spice-6-v1.0/lrosp_1000/data/spk/",
        "pattern": re.compile(r"^lrorg_\d{7}_\d{7}_v\d+\.bsp$", re.IGNORECASE),
        "naif_id": -85,
        "coverage_strategy": "filename",
        "date_parser": _parse_yyyydoy_pair,
        "date_pattern": re.compile(r"lrorg_(?P<start>\d{7})_(?P<end>\d{7})"),
    },
    "lunar_prospector": {
        "base_url": f"{NAIF_BASE}/LPM/kernels/spk/",
        "pattern": re.compile(r"^lp_ask_\d{6}-\d{6}\.bsp$", re.IGNORECASE),
        "naif_id": -25,
        "coverage_strategy": "filename",
        "date_parser": _parse_yymmdd_dash_pair,
        "date_pattern": re.compile(r"lp_ask_(?P<start>\d{6})-(?P<end>\d{6})"),
    },
    "mgs": {
        "base_url": f"{NAIF_BASE}/pds/data/mgs-m-spice-6-v1.0/mgsp_1000/data/spk/",
        "pattern": re.compile(r"^mgs_(crus|ab[12]|spo[12]|map[1-8c]|ext\d+)(_ipng_mgs95j)?\.bsp$", re.IGNORECASE),
        "naif_id": -94,
        # MGS filenames use phase names, not dates
        "coverage_strategy": "download",
    },
    # --- New missions ---
    "mars_odyssey": {
        "base_url": f"{NAIF_BASE}/M01/kernels/spk/",
        # Only base files (no _ipng_ or _ssd_ gravity variants)
        "pattern": re.compile(r"^m01_(cruise|map\d+(_v\d+)?|ext\d+)\.bsp$", re.IGNORECASE),
        "naif_id": -53,
        "coverage_strategy": "download",
    },
    "stardust": {
        "base_url": f"{NAIF_BASE}/pds/data/sdu-c-spice-6-v1.0/sdsp_1000/data/spk/",
        "pattern": re.compile(r"^sdu_l_\d{4}(_\w+)?\.bsp$", re.IGNORECASE),
        "naif_id": -29,
        "coverage_strategy": "download",
    },
    "akatsuki": {
        "base_url": f"{NAIF_BASE}/pds/data/vco-v-spice-6-v1.0/vcosp_1000/data/spk/",
        "pattern": re.compile(r"^vco_\d{4}_v\d+\.bsp$", re.IGNORECASE),
        "naif_id": -5,
        "coverage_strategy": "download",
    },
    "grail": {
        "base_url": f"{NAIF_BASE}/pds/data/grail-l-spice-6-v1.0/grlsp_1000/data/spk/",
        "pattern": re.compile(r"^grail_\d{6}_\d{6}_(nav|sci)_v\d+\.bsp$", re.IGNORECASE),
        "naif_id": -177,  # GRAIL-A; same SPK files also contain GRAIL-B (-178)
        "coverage_strategy": "filename",
        "date_parser": _parse_yymmdd_pair,
        "date_pattern": re.compile(r"grail_(?P<start>\d{6})_(?P<end>\d{6})"),
    },
    "magellan": {
        "base_url": f"{NAIF_BASE}/MGN/kernels/spk/nav/",
        "pattern": re.compile(r"^(PRECYCL\d|CYCLE\d|AEROBRAK)\.BSP$", re.IGNORECASE),
        "naif_id": -18,
        # Only 9 files, no metadata — must download
        "coverage_strategy": "download",
    },
    "exomars_tgo": {
        "base_url": f"{NAIF_BASE}/EXOMARS2016/kernels/spk/",
        # COG series: em16_tgo_cog_NNN_NN_YYYYMMDD_YYYYMMDD_vNN.bsp
        "pattern": re.compile(
            r"^em16_tgo_cog_\d+_\d+_\d{8}_\d{8}_v\d+\.bsp$", re.IGNORECASE
        ),
        "naif_id": -143,
        "coverage_strategy": "filename",
        "date_parser": _parse_yyyymmdd_pair,
        "date_pattern": re.compile(r"_(?P<start>\d{8})_(?P<end>\d{8})_v"),
    },
    "chandrayaan1": {
        "base_url": "https://spiftp.esac.esa.int/data/SPICE/CHANDRAYAAN-1/kernels/spk/",
        "pattern": re.compile(r"^isro_21_day_eph_\d{7}_\d+\.bsp$", re.IGNORECASE),
        "naif_id": -86,
        "coverage_strategy": "filename",
        "date_parser": _parse_yyyydoy_21day,
        "date_pattern": re.compile(r"isro_21_day_eph_(?P<year>\d{4})(?P<doy>\d{3})"),
    },
}


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------

def fetch_file_listing(base_url: str, pattern: re.Pattern) -> list[str]:
    """Fetch NAIF directory listing and filter filenames by regex."""
    print(f"  Fetching directory listing: {base_url}")
    resp = requests.get(base_url, timeout=60)
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, "html.parser")

    files = []
    for link in soup.find_all("a"):
        href = link.get("href", "")
        name = href.rstrip("/").split("/")[-1]
        if pattern.match(name):
            files.append(name)

    print(f"  Found {len(files)} matching SPK files")
    return sorted(files)


def download_file(url: str, dest: Path, timeout: int = 300) -> Path | None:
    """Download a single file. Returns dest on success, None on failure."""
    if dest.exists() and dest.stat().st_size > 0:
        return dest
    try:
        resp = requests.get(url, stream=True, timeout=timeout)
        resp.raise_for_status()
        tmp = dest.with_suffix(".tmp")
        with open(tmp, "wb") as f:
            for chunk in resp.iter_content(chunk_size=1024 * 1024):
                f.write(chunk)
        tmp.rename(dest)
        return dest
    except Exception as e:
        dest.with_suffix(".tmp").unlink(missing_ok=True)
        print(f"    FAILED to download {dest.name}: {e}")
        return None


def get_spk_coverage(bsp_path: str, naif_id: int) -> tuple[str, str] | None:
    """Extract time coverage from an SPK file using spiceypy.

    Returns (start_date, stop_date) as ISO strings, or None if no coverage.

    NOTE: spiceypy is NOT thread-safe. Call this only from the main thread.
    """
    try:
        spice.furnsh(bsp_path)
        cover = spice.spkcov(bsp_path, naif_id)
        if spice.wncard(cover) == 0:
            spice.unload(bsp_path)
            return None

        start_et = spice.wnfetd(cover, 0)[0]
        last_idx = spice.wncard(cover) - 1
        stop_et = spice.wnfetd(cover, last_idx)[1]

        start_utc = spice.et2utc(start_et, "ISOC", 0)[:10]
        stop_utc = spice.et2utc(stop_et, "ISOC", 0)[:10]

        spice.unload(bsp_path)
        return start_utc, stop_utc
    except Exception as e:
        print(f"    Warning: could not read coverage from {bsp_path}: {e}")
        try:
            spice.unload(bsp_path)
        except Exception:
            pass
        return None


# ---------------------------------------------------------------------------
# Coverage extraction by strategy
# ---------------------------------------------------------------------------

def _parse_lbl_coverage(text: str) -> tuple[str, str] | None:
    """Parse COVERAGE_BEGIN_TIME / COVERAGE_END_TIME from a .lbl file."""
    start_match = re.search(
        r"(?:COVERAGE_BEGIN_TIME|START_TIME)\s*=\s*(\d{4}-\d{2}-\d{2})", text
    )
    end_match = re.search(
        r"(?:COVERAGE_END_TIME|STOP_TIME)\s*=\s*(\d{4}-\d{2}-\d{2})", text
    )
    if start_match and end_match:
        return start_match.group(1), end_match.group(1)
    return None


def build_from_filenames(config: dict, files: list[str], base_url: str) -> list[dict]:
    """Extract coverage by parsing dates from filenames. No downloads needed."""
    parser = config["date_parser"]
    date_pat = config["date_pattern"]
    manifest = []

    for filename in files:
        coverage = parser(filename, date_pat)
        if coverage:
            start, stop = coverage
            manifest.append({
                "file": filename,
                "url": base_url + filename,
                "start": start,
                "stop": stop,
            })
            print(f"    {filename}: {start} to {stop}")
        else:
            print(f"    {filename}: could not parse dates from filename")

    return manifest


def build_from_labels(
    config: dict, files: list[str], base_url: str, workers: int
) -> list[dict]:
    """Extract coverage by downloading .lbl sidecar files (tiny, ~1 KB each)."""
    manifest = []
    total = len(files)

    # Download .lbl files in parallel
    def fetch_label(filename: str) -> tuple[str, tuple[str, str] | None]:
        lbl_url = base_url + filename + ".lbl"
        try:
            resp = requests.get(lbl_url, timeout=30)
            resp.raise_for_status()
            return filename, _parse_lbl_coverage(resp.text)
        except Exception:
            # Try without .lbl extension (some use .xml or different naming)
            return filename, None

    print(f"  Fetching {total} label files with {workers} workers...")
    with ThreadPoolExecutor(max_workers=workers) as pool:
        futures = {pool.submit(fetch_label, f): f for f in files}
        done = 0
        for fut in as_completed(futures):
            done += 1
            filename, coverage = fut.result()
            if coverage:
                start, stop = coverage
                manifest.append({
                    "file": filename,
                    "url": base_url + filename,
                    "start": start,
                    "stop": stop,
                })
                print(f"  [{done}/{total}] {filename}: {start} to {stop}")
            else:
                print(f"  [{done}/{total}] {filename}: no label or could not parse")

    return manifest


def build_from_downloads(
    config: dict, files: list[str], base_url: str, workers: int
) -> list[dict]:
    """Extract coverage by downloading full BSPs and reading with spiceypy."""
    naif_id = config["naif_id"]
    total = len(files)
    manifest = []

    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir = Path(tmpdir)

        # Download LSK for time conversion
        lsk_path = tmpdir / "naif0012.tls"
        print("  Downloading LSK...")
        resp = requests.get(LSK_URL, timeout=60)
        resp.raise_for_status()
        lsk_path.write_bytes(resp.content)
        spice.furnsh(str(lsk_path))

        # Phase 1: Parallel download
        print(f"  Downloading {total} BSP files with {workers} workers...")
        downloaded: dict[str, Path] = {}
        with ThreadPoolExecutor(max_workers=workers) as pool:
            futures = {}
            for filename in files:
                url = base_url + filename
                dest = tmpdir / filename
                fut = pool.submit(download_file, url, dest)
                futures[fut] = filename

            done_count = 0
            for fut in as_completed(futures):
                done_count += 1
                filename = futures[fut]
                result = fut.result()
                if result is not None:
                    downloaded[filename] = result
                    print(f"  [{done_count}/{total}] Downloaded {filename}")
                else:
                    print(f"  [{done_count}/{total}] Failed {filename}")

        print(f"  Downloaded {len(downloaded)}/{total} files")

        # Phase 2: Sequential coverage extraction (spiceypy is not thread-safe)
        print(f"  Extracting coverage from {len(downloaded)} files...")
        for i, (filename, file_path) in enumerate(sorted(downloaded.items())):
            coverage = get_spk_coverage(str(file_path), naif_id)
            if coverage is None:
                print(f"  [{i+1}/{len(downloaded)}] {filename}: no coverage")
            else:
                start, stop = coverage
                manifest.append({
                    "file": filename,
                    "url": base_url + filename,
                    "start": start,
                    "stop": stop,
                })
                print(f"  [{i+1}/{len(downloaded)}] {filename}: {start} to {stop}")

            # Clean up to save disk space
            file_path.unlink(missing_ok=True)

        spice.kclear()

    return manifest


# ---------------------------------------------------------------------------
# Main build entry
# ---------------------------------------------------------------------------

def build_manifest(mission: str, workers: int = DEFAULT_WORKERS) -> None:
    """Build a manifest JSON for a given mission."""
    config = MISSION_CONFIGS[mission]
    base_url = config["base_url"]
    pattern = config["pattern"]
    strategy = config.get("coverage_strategy", "download")

    print(f"\nBuilding manifest for {mission.upper()}")
    print(f"  Strategy: {strategy}, workers: {workers}")

    files = fetch_file_listing(base_url, pattern)

    if strategy == "filename":
        manifest = build_from_filenames(config, files, base_url)
    elif strategy == "labels":
        manifest = build_from_labels(config, files, base_url, workers)
    elif strategy == "download":
        manifest = build_from_downloads(config, files, base_url, workers)
    else:
        raise ValueError(f"Unknown coverage strategy: {strategy}")

    # Sort by start date
    manifest.sort(key=lambda s: s["start"])

    # Write JSON
    output_path = MANIFEST_DIR / f"{mission}.json"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w") as f:
        json.dump(manifest, f, indent=2)

    size_kb = output_path.stat().st_size / 1024
    print(f"\n  Wrote {output_path} ({len(manifest)} segments, {size_kb:.1f} KB)")


def main():
    parser = argparse.ArgumentParser(description="Build SPK segment manifests")
    parser.add_argument(
        "mission",
        choices=list(MISSION_CONFIGS.keys()) + ["all"],
        help="Mission to build manifest for (or 'all')",
    )
    parser.add_argument(
        "--workers", "-w",
        type=int,
        default=DEFAULT_WORKERS,
        help=f"Number of parallel download workers (default: {DEFAULT_WORKERS})",
    )
    args = parser.parse_args()

    missions = list(MISSION_CONFIGS.keys()) if args.mission == "all" else [args.mission]
    for mission in missions:
        build_manifest(mission, workers=args.workers)

    print("\nDone!")


if __name__ == "__main__":
    main()
