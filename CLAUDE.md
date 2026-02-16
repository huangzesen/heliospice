# CLAUDE.md — heliospice

## What This Is

**heliospice** is a standalone Python package that wraps SpiceyPy with automatic SPICE kernel management. Users call `get_position("PSP", ...)` and heliospice handles kernel download, caching, loading, and computation. It was extracted from helio-ai-agent's `spice/` module in Feb 2026.

## Repository Structure

```
src/heliospice/
  __init__.py          # Public API re-exports, version
  missions.py          # NAIF IDs, kernel URLs, name resolution
  kernel_manager.py    # Download, cache, load/unload kernels (singleton)
  ephemeris.py         # get_position, get_trajectory, get_state
  frames.py            # transform_vector, coordinate frame listings
  server.py            # MCP server (FastMCP, 8 tools)
  __main__.py          # python -m heliospice entrypoint
tests/                 # 36 tests, all mocked (no network/SPICE needed)
pyproject.toml         # hatchling build, heliospice-mcp CLI entrypoint
server.json            # MCP registry manifest
```

## Key Design Decisions

- **Kernel cache**: `HELIOSPICE_KERNEL_DIR` env var > `~/.heliospice/kernels/` default. helio-ai-agent overrides to `~/.helio-agent/spice_kernels/` via `agent/mcp_client.py`.
- **Single-file kernels only**: Each mission maps to one SPK file. Missions needing multi-segment loading (Cassini ~200 files, MAVEN ~50 files) are not yet supported — noted in `missions.py` comments.
- **No SPK kernels exist for ACE, Wind, DSCOVR, MMS** — these L1 missions only have trajectories in JPL Horizons, not as downloadable SPK files. They have NAIF IDs but no entries in `MISSION_KERNELS`.
- **MCP server** uses `_create_server()` factory pattern for lazy `mcp` import and testability.
- **Thread safety**: KernelManager is a singleton with RLock — SPICE has a global kernel pool.

## Kernel URL Sources (verified Feb 2026)

| Mission | Source | Notes |
|---------|--------|-------|
| PSP | CDAWeb (`cdaweb.gsfc.nasa.gov`) | v043, 2018-2030 |
| SOLO | ESA SPICE FTP (`spiftp.esac.esa.int`) | 2020-2030 |
| STEREO-A | SolarSoft (`sohoftp.nascom.nasa.gov`) | Long-range predict, 2017-2031 |
| Juno | NAIF operational (`/JUNO/kernels/spk/`) | Reconstructed orbit |
| Voyager 1/2 | NAIF operational (`/VOYAGER/kernels/spk/`) | Extended through 2100 |
| New Horizons | NAIF PDS archive | OD161, 2019-2030 |
| Generic (LSK, PCK, SPK) | NAIF generic_kernels | Always works |

**Important**: NAIF reorganizes directories periodically. If a kernel URL returns 404, check the NAIF operational dirs (`/pub/naif/{MISSION}/kernels/spk/`) first, then CDAWeb (`cdaweb.gsfc.nasa.gov/pub/data/{mission}/ephemeris/spice/`), then ESA SPICE FTP.

## Publication Status

- **PyPI**: `heliospice` v0.1.2 — https://pypi.org/project/heliospice/
- **MCP Registry**: `io.github.huangzesen/heliospice` — published via `mcp-publisher`
- **GitHub**: https://github.com/huangzesen/heliospice

To publish a new version:
1. Bump version in `pyproject.toml` and `src/heliospice/__init__.py`
2. `python -m build && twine upload dist/*` (PyPI)
3. Update `server.json` version, then `mcp-publisher publish` (MCP registry)
4. The current PyPI version (0.1.2) does NOT include the kernel URL fixes from the latest commit — a new release is needed.

## Commands

```bash
# Setup
python -m venv venv && source venv/bin/activate
pip install -e ".[dev]"

# Tests (fast, all mocked)
python -m pytest tests/ -x -q

# Integration test (downloads real kernels, slow first run)
python -c "from heliospice import get_position; print(get_position('PSP', time='2024-01-15'))"

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

- Cassini and MAVEN need multi-segment kernel loading (see comments in `missions.py`)
- ACE, Wind, DSCOVR, MMS have no public SPK kernels — would need Horizons API or CDF orbit files as alternative
- PyPI v0.1.2 still has the old broken kernel URLs — needs v0.1.3 release with the latest fixes
- DSCOVR NAIF ID was wrong (-135 = DART) — fixed to -78 in latest commit but not yet on PyPI
