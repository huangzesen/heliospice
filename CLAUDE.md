# CLAUDE.md — xhelio-spice

## What This Is

**xhelio-spice** is a standalone Python package that wraps SpiceyPy with automatic SPICE kernel management. Users call `get_position("PSP", ...)` and xhelio-spice handles kernel download, caching, loading, and computation. It was extracted from helio-ai-agent's `spice/` module in Feb 2026.

## Repository Structure

```
src/xhelio_spice/
  __init__.py          # Public API re-exports, version
  missions.py          # NAIF IDs, kernel URLs, name resolution, SEGMENTED_MISSIONS
  kernel_manager.py    # Download, cache, load/unload kernels (singleton)
  ephemeris.py         # get_position, get_trajectory, get_state
  frames.py            # transform_vector, coordinate frame listings
  server.py            # MCP server (FastMCP, 6 tools)
  __main__.py          # python -m xhelio_spice entrypoint
  manifests/           # Bundled JSON manifests for segmented missions
    __init__.py
    cassini.json       # 505 SPK segments (2001–2017)
    mro.json           # 185 SPK segments (2006–2026)
    mars2020.json      # 52 SPK segments (2019–2036)
    lro.json           # LRO SPK segments
    lunar_prospector.json  # Lunar Prospector SPK segments
    mgs.json           # Mars Global Surveyor SPK segments
    mars_odyssey.json  # 98 SPK segments (2001–2026)
    stardust.json      # 14 SPK segments (1999–2011)
    akatsuki.json      # 10 SPK segments (2011–2021)
    grail.json         # 9 SPK segments (2011–2012)
    magellan.json      # 8 SPK segments (1990–1994)
    exomars_tgo.json   # 322 SPK segments (2018–2026)
    chandrayaan1.json  # 300 SPK segments (2008–2009)
scripts/
  build_manifest.py    # Developer script to regenerate manifests from NAIF
tests/                 # 220 tests, all mocked (no network/SPICE needed)
pyproject.toml         # hatchling build, xhelio-spice-mcp CLI entrypoint
server.json            # MCP registry manifest
```

## Key Design Decisions

- **Kernel cache**: `XHELIO_SPICE_KERNEL_DIR` env var > `~/.xhelio_spice/kernels/` default. helio-ai-agent overrides to `~/.helio-agent/spice_kernels/` via `agent/mcp_client.py`.
- **Two kernel strategies**:
  - **Single-file missions** (PSP, SOLO, Juno, etc.): one SPK file per mission, downloaded in full via `ensure_mission_kernels()`.
  - **Segmented missions** (Cassini, MRO, Mars 2020, LRO, Lunar Prospector, MGS, Mars Odyssey, Stardust, Akatsuki, GRAIL, Magellan, ExoMars TGO, Chandrayaan-1): many SPK files with time coverage recorded in bundled JSON manifests. Only segments overlapping the requested time window are downloaded, via `ensure_segmented_kernels()`.
- **ACE, Wind, DSCOVR are not supported** — no public SPK kernels. Would need JPL Horizons API or CDF orbit files.
- **Cache management**: `get_cache_info()` groups cached files by mission. `delete_mission_cache()`, `delete_cached_files()`, and `purge_cache()` allow selective or full cleanup. Every MCP tool response includes `cache_size_mb` so the LLM can monitor disk usage.
- **MCP server** uses `_create_server()` factory pattern for lazy `mcp` import and testability.
- **Thread safety**: KernelManager is a singleton with RLock — SPICE has a global kernel pool.

## Kernel URL Sources (verified Mar 2026)

| Mission | Source | Notes |
|---------|--------|-------|
| PSP | CDAWeb (`cdaweb.gsfc.nasa.gov`) | v043, 2018-2030 |
| SOLO | ESA SPICE FTP (`spiftp.esac.esa.int`) | 2020-2030 |
| STEREO-A | NAIF operational | Merged trajectory |
| Cassini | NAIF PDS archive (segmented) | 505 reconstructed SPK files |
| MRO | NAIF operational (segmented) | 185 quarterly SPK files |
| Mars 2020 | NAIF operational (segmented) | 52 SPK files (cruise + surface) |
| Mars Odyssey | NAIF operational (segmented) | 98 SPK files (2001–2026) |
| ExoMars TGO | NAIF operational (segmented) | 322 COG SPK files (2018–2026) |
| Chandrayaan-1 | ESA SPICE FTP (segmented) | 300 21-day segments (2008–2009) |
| GRAIL A/B | NAIF PDS archive (segmented) | 9 segments, same files for both S/C |
| Magellan | NAIF operational (segmented) | 8 cycle-based segments (1990–1994) |
| Stardust | NAIF PDS archive (segmented) | 14 yearly segments (1999–2011) |
| Akatsuki | NAIF PDS archive (segmented) | 10 yearly segments (2011–2021) |
| Juno | NAIF operational (`/JUNO/kernels/spk/`) | Reconstructed orbit |
| Voyager 1/2 | NAIF operational (`/VOYAGER/kernels/spk/`) | Extended through 2100 |
| New Horizons | NAIF PDS archive | OD161, 2019-2030 |
| Rosetta | NAIF operational | Full mission trajectory, 182 MB |
| NEAR | NAIF PDS archive | Cruise + Eros orbit, 71 MB |
| JWST | NAIF operational | Reconstructed + predicted, 239 MB |
| Spitzer | NAIF operational (SIRTF) | 615 MB |
| MESSENGER | NAIF PDS archive | Full mission, 653 MB |
| MEX | NAIF operational | Long predict file, 515 MB |
| INTEGRAL/Gaia/Euclid/Hera | ESA SPICE FTP | ESA missions |
| Generic (LSK, PCK, SPK) | NAIF generic_kernels | Always works |

**Important**: NAIF reorganizes directories periodically. If a kernel URL returns 404, check the NAIF operational dirs (`/pub/naif/{MISSION}/kernels/spk/`) first, then CDAWeb (`cdaweb.gsfc.nasa.gov/pub/data/{mission}/ephemeris/spice/`), then ESA SPICE FTP.

## Kernel Sizes (approximate)

- **Generic kernels** (always downloaded): ~31 MB (dominated by `de440s.bsp`)
- **Single-file missions**: 5 KB (BepiColombo) to 653 MB (MESSENGER). PSP 235 MB, Juno 129 MB, JWST 239 MB, Spitzer 615 MB, MEX 515 MB, Rosetta 182 MB, Gaia 151 MB, Dawn 140 MB.
- **Segmented missions per query**: Cassini 2–50 MB, MRO 42–208 MB, Mars 2020 <1 MB, Mars Odyssey 2–50 MB, ExoMars TGO <5 MB per segment
- **Segmented missions total (all segments)**: Cassini ~7.7 GB, MRO ~12.8 GB, Mars 2020 ~4.3 MB, Mars Odyssey ~3 GB, Chandrayaan-1 ~1 GB, ExoMars TGO ~2 GB
- Cache can grow to 30+ GB if querying many missions/time ranges. MCP responses always include `cache_size_mb`.

## Publication Status

- **PyPI**: `xhelio-spice` v0.6.0 — https://pypi.org/project/xhelio-spice/
- **MCP Registry**: `io.github.huangzesen/xhelio-spice` v0.6.0 — published via `mcp-publisher`
- **ClawHub**: `xhelio-spice` skill — https://clawhub.ai/skill/xhelio-spice
- **GitHub**: https://github.com/huangzesen/xhelio-spice

To publish a new version:
1. Bump version in `pyproject.toml`, `src/xhelio_spice/__init__.py`, and `server.json`
2. `python -m build && twine upload dist/*` (PyPI)
3. `mcp-publisher login github && mcp-publisher publish` (MCP registry)

## Commands

```bash
# Setup
python -m venv venv && source venv/bin/activate
pip install -e ".[dev]"

# Tests (fast, all mocked)
python -m pytest tests/ -x -q

# Integration test (downloads real kernels, slow first run)
python -c "from xhelio_spice import get_position; print(get_position('PSP', time='2024-01-15'))"
python -c "from xhelio_spice import get_position; print(get_position('Cassini', time='2005-06-15'))"

# Regenerate segmented manifests (developer only, downloads from NAIF)
python scripts/build_manifest.py all

# MCP server
xhelio-spice-mcp        # or: python -m xhelio_spice.server

# Build + publish
python -m build
twine upload dist/xhelio_spice-{version}*

# Full publish workflow (git → PyPI → MCP registry → ClawHub)
# 1. Update version in pyproject.toml, src/xhelio_spice/__init__.py, and server.json
# 2. Git push
git add -A && git commit -m "Bump version to {version}" && git push
# 3. Build + PyPI
python -m build && twine upload dist/xhelio_spice-{version}*
# 4. MCP registry auto-discovers from PyPI (or use mcp-publisher)
mcp-publisher publish  # if manual update needed
# 5. Publish to ClawHub (OpenClaw skills)
clawhub publish ./xhelio-spice-skill --slug xhelio-spice --name "XHelio-SPICE" --version {version} --tags "space,ephemeris,nasa,planets,spacecraft" --changelog "Version {version}"
```

## Relationship to xhelio

xhelio (at `../xhelio`, formerly helio-ai-agent) **no longer depends on xhelio-spice** as of March 2026. The SPICE envoy layer was removed — the envoy infrastructure is intact but empty. xhelio-spice is now a standalone package. If re-integration is needed, xhelio's envoy registry (`agent/envoy_kinds/registry.py`) and `.mcp.json` are ready to accept new MCP-backed data sources.

## Known Issues / TODO

- ACE, Wind, DSCOVR, MMS have no public SPK kernels — would need Horizons API or CDF orbit files as alternative data source
- Segmented manifests are static snapshots — rerun `scripts/build_manifest.py` to pick up new files from NAIF
- MRO segments are individually large (40–128 MB each) — even single-date queries download significant data
- Cassini manifest includes overlapping R/RB/RU versions of segments (all loaded, SPICE uses latest)
