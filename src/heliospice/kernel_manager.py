"""
SPICE kernel download, caching, and loading.

KernelManager is a thread-safe singleton that handles:
- Downloading kernels from NAIF on first use
- Caching kernels in ~/.heliospice/kernels/ (override via HELIOSPICE_KERNEL_DIR)
- Loading/unloading kernels via spiceypy.furnsh/kclear
- Tracking loaded kernels to avoid double-loading
"""

import logging
import os
import threading
from pathlib import Path

import spiceypy as spice

from .missions import GENERIC_KERNELS, MISSION_KERNELS

logger = logging.getLogger("heliospice")

# ---------------------------------------------------------------------------
# Singleton
# ---------------------------------------------------------------------------

_instance = None
_instance_lock = threading.Lock()


def get_kernel_manager() -> "KernelManager":
    """Return the KernelManager singleton."""
    global _instance
    if _instance is not None:
        return _instance
    with _instance_lock:
        if _instance is not None:
            return _instance
        _instance = KernelManager()
        return _instance


class KernelManager:
    """Thread-safe manager for SPICE kernel download, cache, and loading.

    SPICE has a global kernel pool, so all operations are serialized
    via an RLock to prevent concurrent furnsh/spkpos calls from
    corrupting state.
    """

    def __init__(self, kernel_dir: Path | str | None = None):
        self._lock = threading.RLock()
        self._loaded_kernels: set[str] = set()
        self._generic_loaded = False
        self._mission_kernels_loaded: set[str] = set()

        if kernel_dir is not None:
            self._kernel_dir = Path(kernel_dir)
        else:
            base = os.environ.get("HELIOSPICE_KERNEL_DIR")
            if base:
                self._kernel_dir = Path(base)
            else:
                self._kernel_dir = Path.home() / ".heliospice" / "kernels"
        self._kernel_dir.mkdir(parents=True, exist_ok=True)

    @property
    def lock(self) -> threading.RLock:
        """Expose the lock for external callers that need SPICE thread safety."""
        return self._lock

    @property
    def kernel_dir(self) -> Path:
        return self._kernel_dir

    # ------------------------------------------------------------------
    # Download
    # ------------------------------------------------------------------

    def download_kernel(self, url: str, filename: str) -> Path:
        """Download a kernel file if not already cached.

        Args:
            url: HTTP(S) URL to fetch from.
            filename: Local filename to save as.

        Returns:
            Path to the cached file.

        Raises:
            RuntimeError: If the download fails.
        """
        local_path = self._kernel_dir / filename
        if local_path.exists() and local_path.stat().st_size > 0:
            logger.debug("Kernel cached: %s", filename)
            return local_path

        logger.info("Downloading kernel: %s", filename)
        import requests
        try:
            resp = requests.get(url, stream=True, timeout=300)
            resp.raise_for_status()
        except Exception as e:
            raise RuntimeError(f"Failed to download kernel {filename} from {url}: {e}") from e

        # Write to temp file then rename for atomicity
        tmp_path = local_path.with_suffix(".tmp")
        try:
            with open(tmp_path, "wb") as f:
                for chunk in resp.iter_content(chunk_size=1024 * 1024):
                    f.write(chunk)
            tmp_path.rename(local_path)
        except Exception:
            tmp_path.unlink(missing_ok=True)
            raise

        logger.info("Downloaded kernel: %s (%d bytes)", filename, local_path.stat().st_size)
        return local_path

    # ------------------------------------------------------------------
    # Load / unload
    # ------------------------------------------------------------------

    def load_kernel(self, path: Path) -> None:
        """Load a kernel into the SPICE pool (idempotent).

        Args:
            path: Path to the kernel file.
        """
        key = str(path.resolve())
        with self._lock:
            if key in self._loaded_kernels:
                return
            spice.furnsh(key)
            self._loaded_kernels.add(key)
            logger.debug("Loaded kernel: %s", path.name)

    def unload_all(self) -> None:
        """Unload all kernels and clear state."""
        with self._lock:
            spice.kclear()
            self._loaded_kernels.clear()
            self._generic_loaded = False
            self._mission_kernels_loaded.clear()
            logger.info("Unloaded all SPICE kernels")

    def list_loaded(self) -> list[str]:
        """Return list of currently loaded kernel file names."""
        with self._lock:
            return [Path(k).name for k in sorted(self._loaded_kernels)]

    # ------------------------------------------------------------------
    # High-level ensure methods
    # ------------------------------------------------------------------

    def ensure_generic_kernels(self) -> None:
        """Download and load generic kernels (LSK, PCK, planetary SPK).

        Idempotent — safe to call multiple times.
        Loading order: LSK -> PCK -> SPK (dependencies first).
        """
        if self._generic_loaded:
            return

        # Order matters: LSK first (time conversion), then PCK, then SPK
        ordered_files = [
            "naif0012.tls",   # Leap seconds
            "pck00011.tpc",   # Planetary constants
            "gm_de440.tpc",   # Gravitational parameters
            "de440s.bsp",     # Planetary ephemerides
        ]

        for filename in ordered_files:
            url = GENERIC_KERNELS.get(filename)
            if url is None:
                continue
            path = self.download_kernel(url, filename)
            self.load_kernel(path)

        self._generic_loaded = True
        logger.info("Generic kernels loaded")

    def ensure_mission_kernels(self, mission_key: str) -> None:
        """Download and load mission-specific kernels.

        Also ensures generic kernels are loaded first.

        Args:
            mission_key: Canonical mission key (e.g., "PSP", "SOLO").

        Raises:
            KeyError: If no kernels are defined for this mission.
        """
        if mission_key in self._mission_kernels_loaded:
            return

        self.ensure_generic_kernels()

        kernels = MISSION_KERNELS.get(mission_key)
        if kernels is None:
            raise KeyError(
                f"No SPICE kernels defined for mission '{mission_key}'. "
                f"Available: {', '.join(sorted(MISSION_KERNELS.keys()))}"
            )

        for filename, url in kernels.items():
            path = self.download_kernel(url, filename)
            self.load_kernel(path)

        self._mission_kernels_loaded.add(mission_key)
        logger.info("Mission kernels loaded: %s", mission_key)

    # ------------------------------------------------------------------
    # Cache management
    # ------------------------------------------------------------------

    def get_cache_size_bytes(self) -> int:
        """Return total size of cached kernel files in bytes."""
        total = 0
        if self._kernel_dir.exists():
            for f in self._kernel_dir.iterdir():
                if f.is_file() and not f.name.endswith(".tmp"):
                    total += f.stat().st_size
        return total

    def get_cache_info(self) -> dict:
        """Return cache summary: directory, total size, file count."""
        files = []
        if self._kernel_dir.exists():
            files = [
                f for f in self._kernel_dir.iterdir()
                if f.is_file() and not f.name.endswith(".tmp")
            ]
        total = sum(f.stat().st_size for f in files)
        return {
            "kernel_dir": str(self._kernel_dir),
            "total_size_mb": round(total / (1024 * 1024), 2),
            "file_count": len(files),
            "files": [
                {"name": f.name, "size_mb": round(f.stat().st_size / (1024 * 1024), 2)}
                for f in sorted(files)
            ],
        }
