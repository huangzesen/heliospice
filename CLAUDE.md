# CLAUDE.md — heliospice

## What This Is

**heliospice** is a standalone Python package that wraps SpiceyPy with automatic SPICE kernel management. Users call `get_position("PSP", ...)` and heliospice handles kernel download, caching, loading, and computation. It was extracted from helio-ai-agent's `spice/` module in Feb 2026.

## Repository Structure

```
src/heliospice/
  __init__.py          # Public API re-exports, version
  missions.py          # NAIF IDs, kernel URLs, name resolution, SEGMENTED_MISSIONS
  kernel_manager.py    # Download, cache, load/unload kernels (singleton)
  ephemeris.py         # get_position, get_trajectory, get_state
  frames.py            # transform_vector, coordinate frame listings
  server.py            # MCP server (FastMCP, 6 tools)
  __main__.py          # python -m heliospice entrypoint
  manifests/           # Bundled JSON manifests for segmented missions
    __init__.py
    cassini.json       # 505 SPK segments (2001–2017)
    mro.json           # 185 SPK segments (2006–2026)
    mars2020.json      # 52 SPK segments (2019–2036)
scripts/
  build_manifest.py    # Developer script to regenerate manifests from NAIF
tests/                 # 61 tests, all mocked (no network/SPICE needed)
pyproject.toml         # hatchling build, heliospice-mcp CLI entrypoint
server.json            # MCP registry manifest
```

## Key Design Decisions

- **Kernel cache**: `HELIOSPICE_KERNEL_DIR` env var > `~/.heliospice/kernels/` default. helio-ai-agent overrides to `~/.helio-agent/spice_kernels/` via `agent/mcp_client.py`.
- **Two kernel strategies**:
  - **Single-file missions** (PSP, SOLO, Juno, etc.): one SPK file per mission, downloaded in full via `ensure_mission_kernels()`.
  - **Segmented missions** (Cassini, MRO, Mars 2020): many SPK files with time coverage recorded in bundled JSON manifests. Only segments overlapping the requested time window are downloaded, via `ensure_segmented_kernels()`.
- **No SPK kernels exist for ACE, Wind, DSCOVR, MMS** — these L1 missions only have trajectories in JPL Horizons, not as downloadable SPK files. They have NAIF IDs but no entries in `MISSION_KERNELS` or `SEGMENTED_MISSIONS`.
- **Cache management**: `get_cache_info()` groups cached files by mission. `delete_mission_cache()`, `delete_cached_files()`, and `purge_cache()` allow selective or full cleanup. Every MCP tool response includes `cache_size_mb` so the LLM can monitor disk usage.
- **MCP server** uses `_create_server()` factory pattern for lazy `mcp` import and testability.
- **Thread safety**: KernelManager is a singleton with RLock — SPICE has a global kernel pool.

## Kernel URL Sources (verified Feb 2026)

| Mission | Source | Notes |
|---------|--------|-------|
| PSP | CDAWeb (`cdaweb.gsfc.nasa.gov`) | v043, 2018-2030 |
| SOLO | ESA SPICE FTP (`spiftp.esac.esa.int`) | 2020-2030 |
| STEREO-A | SolarSoft (`sohoftp.nascom.nasa.gov`) | Long-range predict, 2017-2031 |
| Cassini | NAIF PDS archive (segmented) | 505 reconstructed SPK files |
| MRO | NAIF operational (segmented) | 185 quarterly SPK files |
| Mars 2020 | NAIF operational (segmented) | 52 SPK files (cruise + surface) |
| Juno | NAIF operational (`/JUNO/kernels/spk/`) | Reconstructed orbit |
| Voyager 1/2 | NAIF operational (`/VOYAGER/kernels/spk/`) | Extended through 2100 |
| New Horizons | NAIF PDS archive | OD161, 2019-2030 |
| Generic (LSK, PCK, SPK) | NAIF generic_kernels | Always works |

**Important**: NAIF reorganizes directories periodically. If a kernel URL returns 404, check the NAIF operational dirs (`/pub/naif/{MISSION}/kernels/spk/`) first, then CDAWeb (`cdaweb.gsfc.nasa.gov/pub/data/{mission}/ephemeris/spice/`), then ESA SPICE FTP.

## Kernel Sizes (approximate)

- **Generic kernels** (always downloaded): ~31 MB (dominated by `de440s.bsp`)
- **Single-file missions**: 5 KB (BepiColombo) to 653 MB (MESSENGER). PSP is 235 MB, Juno 129 MB.
- **Segmented missions per query**: Cassini 2–50 MB, MRO 42–208 MB, Mars 2020 <1 MB
- **Segmented missions total (all segments)**: Cassini ~7.7 GB, MRO ~12.8 GB, Mars 2020 ~4.3 MB
- Cache can grow to 20+ GB if querying many missions/time ranges. MCP responses always include `cache_size_mb`.

## Publication Status

- **PyPI**: `heliospice` v0.4.0 — https://pypi.org/project/heliospice/
- **MCP Registry**: `io.github.huangzesen/heliospice` v0.4.0 — published via `mcp-publisher`
- **GitHub**: https://github.com/huangzesen/heliospice

To publish a new version:
1. Bump version in `pyproject.toml`, `src/heliospice/__init__.py`, and `server.json`
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
python -c "from heliospice import get_position; print(get_position('PSP', time='2024-01-15'))"
python -c "from heliospice import get_position; print(get_position('Cassini', time='2005-06-15'))"

# Regenerate segmented manifests (developer only, downloads from NAIF)
python scripts/build_manifest.py all

# MCP server
heliospice-mcp          # or: python -m heliospice.server

# Build + publish
python -m build
twine upload dist/heliospice-{version}*
```

## Relationship to helio-ai-agent

- helio-ai-agent depends on `heliospice[mcp]>=0.1.0` (in `requirements.txt`)
- `agent/mcp_client.py` spawns `heliospice-mcp` subprocess, communicates via MCP stdio
- `agent/tools.py` defines 7 SPICE tool schemas exposed to the LLM
- Kernel cache shared: mcp_client sets `HELIOSPICE_KERNEL_DIR=~/.helio-agent/spice_kernels/`

## Known Issues / TODO

- ACE, Wind, DSCOVR, MMS have no public SPK kernels — would need Horizons API or CDF orbit files as alternative
- Segmented manifests are static snapshots — rerun `scripts/build_manifest.py` to pick up new files from NAIF
- MRO segments are individually large (40–128 MB each) — even single-date queries download significant data
- Cassini manifest includes overlapping R/RB/RU versions of segments (all loaded, SPICE uses latest)
