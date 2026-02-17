#!/usr/bin/env python3
"""Build segment manifest JSONs for missions with multi-file SPK kernels.

Developer-only script — not part of the installed package.
Requires: spiceypy, requests, beautifulsoup4

Usage:
    python scripts/build_manifest.py cassini
    python scripts/build_manifest.py mro
    python scripts/build_manifest.py mars2020
    python scripts/build_manifest.py all
"""

import argparse
import json
import re
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

import requests
import spiceypy as spice
from bs4 import BeautifulSoup

# Where to write output manifests
MANIFEST_DIR = Path(__file__).resolve().parent.parent / "src" / "heliospice" / "manifests"

# LSK needed for time conversion
NAIF_BASE = "https://naif.jpl.nasa.gov/pub/naif"
LSK_URL = f"{NAIF_BASE}/generic_kernels/lsk/naif0012.tls"

# Mission configurations: (base_url, filename_regex)
MISSION_CONFIGS = {
    "cassini": {
        "base_url": f"{NAIF_BASE}/pds/data/co-s_j_e_v-spice-6-v1.0/cosp_1000/data/spk/",
        "pattern": re.compile(r"^\d{6}R[BU]?_SCPSE_\d{5}_\d{5}\.bsp$", re.IGNORECASE),
        "naif_id": -82,
    },
    "mro": {
        "base_url": f"{NAIF_BASE}/MRO/kernels/spk/",
        "pattern": re.compile(r"^mro_psp\d+.*\.bsp$", re.IGNORECASE),
        "naif_id": -74,
    },
    "mars2020": {
        "base_url": f"{NAIF_BASE}/MARS2020/kernels/spk/",
        "pattern": re.compile(r"^m2020_.*\.bsp$", re.IGNORECASE),
        "naif_id": -168,
    },
}


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


def get_spk_coverage(bsp_path: str, naif_id: int) -> tuple[str, str] | None:
    """Extract time coverage from an SPK file using spiceypy.

    Returns (start_date, stop_date) as ISO strings, or None if no coverage.
    """
    try:
        spice.furnsh(bsp_path)
        cover = spice.spkcov(bsp_path, naif_id)
        if spice.wncard(cover) == 0:
            spice.unload(bsp_path)
            return None

        # Get the overall window (first start to last stop)
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


def build_manifest(mission: str) -> None:
    """Build a manifest JSON for a given mission."""
    config = MISSION_CONFIGS[mission]
    base_url = config["base_url"]
    pattern = config["pattern"]
    naif_id = config["naif_id"]

    print(f"\nBuilding manifest for {mission.upper()}")
    print(f"  NAIF ID: {naif_id}")

    # Ensure LSK is loaded for time conversion
    with tempfile.TemporaryDirectory() as tmpdir:
        lsk_path = Path(tmpdir) / "naif0012.tls"
        if not lsk_path.exists():
            print("  Downloading LSK...")
            resp = requests.get(LSK_URL, timeout=60)
            resp.raise_for_status()
            lsk_path.write_bytes(resp.content)
        spice.furnsh(str(lsk_path))

        # Get file listing
        files = fetch_file_listing(base_url, pattern)

        manifest = []
        for i, filename in enumerate(files):
            print(f"  [{i+1}/{len(files)}] Processing {filename}...", end="", flush=True)

            # Download to temp
            file_path = Path(tmpdir) / filename
            if not file_path.exists():
                url = base_url + filename
                try:
                    resp = requests.get(url, stream=True, timeout=300)
                    resp.raise_for_status()
                    with open(file_path, "wb") as f:
                        for chunk in resp.iter_content(chunk_size=1024 * 1024):
                            f.write(chunk)
                except Exception as e:
                    print(f" FAILED ({e})")
                    continue

            coverage = get_spk_coverage(str(file_path), naif_id)
            if coverage is None:
                print(" no coverage")
                # Clean up to save space
                file_path.unlink(missing_ok=True)
                continue

            start, stop = coverage
            manifest.append({
                "file": filename,
                "url": base_url + filename,
                "start": start,
                "stop": stop,
            })
            print(f" {start} to {stop}")

            # Clean up downloaded file to save disk space
            file_path.unlink(missing_ok=True)

        spice.kclear()

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
    args = parser.parse_args()

    missions = list(MISSION_CONFIGS.keys()) if args.mission == "all" else [args.mission]
    for mission in missions:
        build_manifest(mission)

    print("\nDone!")


if __name__ == "__main__":
    main()
