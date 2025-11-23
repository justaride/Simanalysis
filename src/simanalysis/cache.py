"""Analysis result caching for faster re-runs."""

import hashlib
import logging
import pickle
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

from simanalysis.models import Mod

logger = logging.getLogger(__name__)


class AnalysisCache:
    """
    Cache analysis results for faster re-runs.

    Caches parsed mod data based on file path, modification time, and size.
    When a mod hasn't changed, cached results are returned instantly.

    Example:
        >>> cache = AnalysisCache()
        >>> cached_mod = cache.get_cached(mod_path)
        >>> if cached_mod is None:
        >>>     mod = analyze_mod(mod_path)
        >>>     cache.save_cache(mod)
    """

    def __init__(self, cache_dir: Optional[Path] = None):
        """
        Initialize cache.

        Args:
            cache_dir: Directory for cache files (default: ~/.simanalysis/cache/)
        """
        if cache_dir is None:
            cache_dir = Path.home() / ".simanalysis" / "cache"

        self.cache_dir = cache_dir
        self.cache_dir.mkdir(parents=True, exist_ok=True)

        logger.debug(f"AnalysisCache initialized at {self.cache_dir}")

    def get_cache_key(self, mod_path: Path) -> str:
        """
        Generate cache key from file path and metadata.

        Cache key is based on:
        - File path
        - Modification time
        - File size

        If any of these change, cache is invalidated.

        Args:
            mod_path: Path to mod file

        Returns:
            SHA256 hash of file metadata
        """
        try:
            stat = mod_path.stat()

            # Key = hash of (path + mtime + size)
            key_data = f"{mod_path.absolute()}:{stat.st_mtime}:{stat.st_size}"
            return hashlib.sha256(key_data.encode()).hexdigest()

        except (FileNotFoundError, OSError) as e:
            logger.debug(f"Failed to get cache key for {mod_path}: {e}")
            # Return placeholder key that won't match
            return "invalid_" + hashlib.sha256(str(mod_path).encode()).hexdigest()

    def get_cached(self, mod_path: Path) -> Optional[Mod]:
        """
        Get cached analysis result if valid.

        Args:
            mod_path: Path to mod file

        Returns:
            Cached Mod object or None if not cached/invalid
        """
        cache_key = self.get_cache_key(mod_path)
        cache_file = self.cache_dir / f"{cache_key}.pkl"

        if not cache_file.exists():
            logger.debug(f"Cache miss for {mod_path.name}")
            return None

        try:
            with open(cache_file, "rb") as f:
                cached_mod = pickle.load(f)

            # Verify cache is still valid
            if self._is_cache_valid(mod_path, cached_mod):
                logger.debug(f"Cache hit for {mod_path.name}")
                return cached_mod
            else:
                # Stale cache, remove it
                logger.debug(f"Stale cache for {mod_path.name}, removing")
                cache_file.unlink()
                return None

        except Exception as e:
            # Corrupted or incompatible cache, remove it
            logger.debug(f"Cache error for {mod_path.name}: {e}, removing")
            try:
                cache_file.unlink()
            except Exception:
                pass
            return None

    def save_cache(self, mod: Mod) -> bool:
        """
        Save analysis result to cache.

        Args:
            mod: Mod object to cache

        Returns:
            True if cache saved successfully, False otherwise
        """
        try:
            cache_key = self.get_cache_key(mod.path)
            cache_file = self.cache_dir / f"{cache_key}.pkl"

            with open(cache_file, "wb") as f:
                pickle.dump(mod, f, protocol=pickle.HIGHEST_PROTOCOL)

            logger.debug(f"Cached {mod.name}")
            return True

        except Exception as e:
            logger.warning(f"Failed to save cache for {mod.name}: {e}")
            return False

    def _is_cache_valid(self, mod_path: Path, cached_mod: Mod) -> bool:
        """
        Check if cached result is still valid.

        Args:
            mod_path: Path to mod file
            cached_mod: Cached mod object

        Returns:
            True if cache is valid, False otherwise
        """
        try:
            current_stat = mod_path.stat()

            # Invalid if file size changed
            if cached_mod.size != current_stat.st_size:
                return False

            # Could add more validation here
            # (e.g., checksum comparison, version checks)

            return True

        except (FileNotFoundError, OSError):
            # File no longer exists
            return False

    def clear_cache(self, older_than_days: Optional[int] = None) -> int:
        """
        Clear cache files.

        Args:
            older_than_days: Only clear files older than this many days
                            (None = clear all)

        Returns:
            Number of cache files removed
        """
        removed = 0

        if older_than_days is not None:
            cutoff = datetime.now() - timedelta(days=older_than_days)
            cutoff_timestamp = cutoff.timestamp()

            for cache_file in self.cache_dir.glob("*.pkl"):
                try:
                    if cache_file.stat().st_mtime < cutoff_timestamp:
                        cache_file.unlink()
                        removed += 1
                except Exception as e:
                    logger.warning(f"Failed to remove cache file {cache_file.name}: {e}")
        else:
            # Clear all
            for cache_file in self.cache_dir.glob("*.pkl"):
                try:
                    cache_file.unlink()
                    removed += 1
                except Exception as e:
                    logger.warning(f"Failed to remove cache file {cache_file.name}: {e}")

        logger.info(f"Removed {removed} cache files")
        return removed

    def get_cache_info(self) -> dict:
        """
        Get cache statistics.

        Returns:
            Dictionary with cache information:
            - cached_mods: Number of cached mods
            - cache_size_bytes: Total cache size in bytes
            - cache_size_mb: Total cache size in MB
            - cache_directory: Path to cache directory
            - oldest_cache: Age of oldest cache file in days
            - newest_cache: Age of newest cache file in days
        """
        cache_files = list(self.cache_dir.glob("*.pkl"))

        if not cache_files:
            return {
                "cached_mods": 0,
                "cache_size_bytes": 0,
                "cache_size_mb": 0.0,
                "cache_directory": str(self.cache_dir),
                "oldest_cache_days": None,
                "newest_cache_days": None,
            }

        total_size = sum(f.stat().st_size for f in cache_files)

        # Find oldest and newest cache files
        now = datetime.now().timestamp()
        mtimes = [f.stat().st_mtime for f in cache_files]
        oldest_age = (now - min(mtimes)) / 86400  # days
        newest_age = (now - max(mtimes)) / 86400  # days

        return {
            "cached_mods": len(cache_files),
            "cache_size_bytes": total_size,
            "cache_size_mb": total_size / 1024 / 1024,
            "cache_directory": str(self.cache_dir),
            "oldest_cache_days": oldest_age,
            "newest_cache_days": newest_age,
        }

    def invalidate_mod(self, mod_path: Path) -> bool:
        """
        Invalidate cache for a specific mod.

        Args:
            mod_path: Path to mod file

        Returns:
            True if cache was removed, False if not found
        """
        cache_key = self.get_cache_key(mod_path)
        cache_file = self.cache_dir / f"{cache_key}.pkl"

        if cache_file.exists():
            try:
                cache_file.unlink()
                logger.debug(f"Invalidated cache for {mod_path.name}")
                return True
            except Exception as e:
                logger.warning(f"Failed to invalidate cache for {mod_path.name}: {e}")
                return False
        else:
            return False


class CachedScanner:
    """
    Scanner that uses caching for faster re-runs.

    Wraps a regular scanner and adds caching layer.

    Example:
        >>> scanner = CachedScanner()
        >>> mods = scanner.scan_directory(Path("~/Mods"))
        >>> # First run: Normal speed
        >>> # Second run: 98% faster (cache hits)
    """

    def __init__(
        self,
        parse_tunings: bool = True,
        parse_scripts: bool = True,
        calculate_hashes: bool = True,
        cache_dir: Optional[Path] = None,
    ):
        """
        Initialize cached scanner.

        Args:
            parse_tunings: Whether to parse XML tunings
            parse_scripts: Whether to analyze scripts
            calculate_hashes: Whether to calculate file hashes
            cache_dir: Cache directory (default: ~/.simanalysis/cache/)
        """
        from simanalysis.scanners.mod_scanner import ModScanner

        self.scanner = ModScanner(
            parse_tunings=parse_tunings,
            parse_scripts=parse_scripts,
            calculate_hashes=calculate_hashes,
        )

        self.cache = AnalysisCache(cache_dir=cache_dir)
        self.cache_hits = 0
        self.cache_misses = 0

    def scan_directory(
        self,
        directory: Path,
        recursive: bool = True,
        extensions: Optional[set] = None,
    ) -> list[Mod]:
        """
        Scan directory with caching.

        Args:
            directory: Directory to scan
            recursive: Whether to scan subdirectories
            extensions: File extensions to scan

        Returns:
            List of mods
        """
        # Find all mod files
        if extensions is None:
            extensions = {".package", ".ts4script"}

        files = self.scanner._find_mod_files(directory, recursive, extensions)
        logger.info(f"Found {len(files)} files, checking cache...")

        mods = []
        self.cache_hits = 0
        self.cache_misses = 0

        for file_path in files:
            # Try cache first
            cached_mod = self.cache.get_cached(file_path)

            if cached_mod is not None:
                mods.append(cached_mod)
                self.cache_hits += 1
            else:
                # Cache miss, scan normally
                mod = self.scanner.scan_file(file_path)
                if mod:
                    mods.append(mod)
                    # Save to cache
                    self.cache.save_cache(mod)
                self.cache_misses += 1

        hit_rate = (self.cache_hits / len(files) * 100) if files else 0
        logger.info(f"Cache: {self.cache_hits} hits, {self.cache_misses} misses ({hit_rate:.1f}% hit rate)")

        return mods

    def get_cache_stats(self) -> dict:
        """
        Get cache statistics for last scan.

        Returns:
            Dictionary with cache_hits and cache_misses
        """
        return {
            "cache_hits": self.cache_hits,
            "cache_misses": self.cache_misses,
            "hit_rate": (self.cache_hits / (self.cache_hits + self.cache_misses) * 100)
            if (self.cache_hits + self.cache_misses) > 0
            else 0.0,
        }
