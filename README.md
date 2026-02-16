# heliospice

Spacecraft ephemeris made easy — auto-managed SPICE kernels for heliophysics missions.

**heliospice** wraps [SpiceyPy](https://github.com/AndrewAnnex/SpiceyPy) with automatic kernel download, caching, and loading. Ask for a spacecraft position and heliospice handles the rest: downloading the right NAIF kernels, loading them in the correct order, and returning results as Python dicts or pandas DataFrames.

## Installation

```bash
pip install heliospice
```

For MCP server support (Claude Desktop, Claude Code, Cursor, etc.):

```bash
pip install heliospice[mcp]
```

## Quick Start

```python
from heliospice import get_position, get_trajectory

# Where is Parker Solar Probe right now?
pos = get_position("PSP", observer="SUN", time="2024-01-15", frame="ECLIPJ2000")
print(f"PSP is {pos['r_au']:.3f} AU from the Sun")

# Get a month of trajectory data as a DataFrame
df = get_trajectory(
    "PSP", observer="SUN",
    time_start="2024-01-01", time_end="2024-01-31",
    step="1h", frame="ECLIPJ2000",
)
print(df[["r_au"]].describe())
```

Kernels are automatically downloaded from [NAIF](https://naif.jpl.nasa.gov/) on first use and cached in `~/.heliospice/kernels/`.

## Supported Missions

### Heliophysics
- **PSP** (Parker Solar Probe)
- **Solar Orbiter** (SOLO)
- **ACE**
- **Wind**
- **DSCOVR**
- **MMS** (1-4)
- **STEREO-A/B**

### Planetary
- **Cassini**
- **Juno**
- **Voyager 1/2**
- **MAVEN**
- **New Horizons**
- **Galileo**, **Pioneer 10/11**, **Ulysses**, **MESSENGER**

### Natural Bodies
Sun, Earth, Moon, Mercury, Venus, Mars, Jupiter, Saturn, Uranus, Neptune, Pluto

## API Reference

### Position & Trajectory

```python
from heliospice import get_position, get_trajectory, get_state

# Single position
pos = get_position("ACE", observer="EARTH", time="2024-06-01", frame="GSE")

# Full state (position + velocity)
state = get_state("PSP", observer="SUN", time="2024-01-15", frame="ECLIPJ2000")

# Trajectory timeseries (returns pandas DataFrame)
df = get_trajectory(
    "Cassini", observer="SATURN",
    time_start="2010-01-01", time_end="2010-12-31",
    step="6h", frame="ECLIPJ2000",
    include_velocity=True,
)
```

### Coordinate Transforms

```python
from heliospice import transform_vector, list_available_frames

# J2000 to Ecliptic
v_ecl = transform_vector([1.0, 0.0, 0.0], "2024-01-15", "J2000", "ECLIPJ2000")

# RTN transform (requires spacecraft)
v_rtn = transform_vector(
    [5.0, -3.0, 1.0], "2024-01-15",
    from_frame="ECLIPJ2000", to_frame="RTN",
    spacecraft="PSP",
)

# List all frames
print(list_available_frames())
```

### Mission Registry

```python
from heliospice import resolve_mission, list_supported_missions

# Resolve name aliases
naif_id, key = resolve_mission("Parker Solar Probe")  # -> (-96, "PSP")

# List all spacecraft
missions = list_supported_missions()
```

### Kernel Management

```python
from heliospice import get_kernel_manager

km = get_kernel_manager()
km.ensure_mission_kernels("PSP")  # Download + load
print(km.get_cache_info())        # Cache stats
km.unload_all()                    # Free memory
```

## Configuration

| Method | Description |
|--------|-------------|
| `HELIOSPICE_KERNEL_DIR` env var | Override kernel cache directory |
| `KernelManager(kernel_dir=...)` | Per-instance override |
| Default | `~/.heliospice/kernels/` |

## MCP Server

heliospice includes an [MCP](https://modelcontextprotocol.io/) server for LLM tool use:

```bash
# Run directly
heliospice-mcp

# Or via Python
python -m heliospice.server
```

### Claude Desktop Configuration

Add to `claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "heliospice": {
      "command": "heliospice-mcp"
    }
  }
}
```

### Available MCP Tools

| Tool | Description |
|------|-------------|
| `get_spacecraft_position` | Position at a single time |
| `get_spacecraft_trajectory` | Position timeseries |
| `get_spacecraft_velocity` | Velocity timeseries |
| `compute_distance` | Distance between two bodies |
| `transform_coordinates` | Coordinate frame transform |
| `list_spice_missions` | Supported missions |
| `list_coordinate_frames` | Available frames with descriptions |
| `manage_kernels` | Kernel cache management |

## License

MIT
