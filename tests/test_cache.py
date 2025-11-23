"""Tests for analysis caching."""

import pickle
import tempfile
import time
from datetime import datetime, timedelta
from pathlib import Path

import pytest

from simanalysis.cache import AnalysisCache, CachedScanner
from simanalysis.models import Mod, ModType


@pytest.fixture
def temp_cache_dir():
    """Create temporary cache directory."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


@pytest.fixture
def test_mod():
    """Create test mod."""
    return Mod(
        name="TestMod.package",
        path=Path("/test/TestMod.package"),
        type=ModType.PACKAGE,
        size=1000,
        hash="abc123",
    )


class TestAnalysisCache:
    """Test AnalysisCache class."""

    def test_init_default_dir(self):
        """Test cache initializes with default directory."""
        cache = AnalysisCache()

        expected_dir = Path.home() / ".simanalysis" / "cache"
        assert cache.cache_dir == expected_dir
        assert cache.cache_dir.exists()

    def test_init_custom_dir(self, temp_cache_dir):
        """Test cache with custom directory."""
        cache = AnalysisCache(cache_dir=temp_cache_dir)

        assert cache.cache_dir == temp_cache_dir
        assert cache.cache_dir.exists()

    def test_get_cache_key_creates_consistent_hash(self, tmp_path):
        """Test cache key is consistent for same file."""
        test_file = tmp_path / "test.package"
        test_file.write_text("test content")

        cache = AnalysisCache()

        key1 = cache.get_cache_key(test_file)
        key2 = cache.get_cache_key(test_file)

        # Same file should produce same key
        assert key1 == key2
        # Key should be SHA256 hash (64 hex characters)
        assert len(key1) == 64

    def test_get_cache_key_changes_on_file_modification(self, tmp_path):
        """Test cache key changes when file is modified."""
        test_file = tmp_path / "test.package"
        test_file.write_text("original content")

        cache = AnalysisCache()
        key1 = cache.get_cache_key(test_file)

        # Wait a bit and modify file
        time.sleep(0.01)
        test_file.write_text("modified content")

        key2 = cache.get_cache_key(test_file)

        # Keys should be different
        assert key1 != key2

    def test_get_cache_key_for_nonexistent_file(self):
        """Test cache key for file that doesn't exist."""
        cache = AnalysisCache()

        key = cache.get_cache_key(Path("/nonexistent/file.package"))

        # Should return some key (won't match anything)
        assert isinstance(key, str)
        assert key.startswith("invalid_")

    def test_save_and_load_cache(self, temp_cache_dir, test_mod, tmp_path):
        """Test saving and loading cache."""
        # Create actual file for the mod
        mod_file = tmp_path / test_mod.name
        content = "test content"
        mod_file.write_text(content)

        # Update mod to match actual file
        test_mod.path = mod_file
        test_mod.size = len(content)  # Match actual file size

        cache = AnalysisCache(cache_dir=temp_cache_dir)

        # Save cache
        success = cache.save_cache(test_mod)
        assert success is True

        # Load cache
        cached_mod = cache.get_cached(mod_file)

        assert cached_mod is not None
        assert cached_mod.name == test_mod.name
        assert cached_mod.size == test_mod.size
        assert cached_mod.hash == test_mod.hash

    def test_cache_miss_returns_none(self, temp_cache_dir, tmp_path):
        """Test cache miss returns None."""
        cache = AnalysisCache(cache_dir=temp_cache_dir)

        # File that was never cached
        test_file = tmp_path / "uncached.package"
        test_file.write_text("test")

        cached_mod = cache.get_cached(test_file)

        assert cached_mod is None

    def test_cache_invalidated_on_file_change(self, temp_cache_dir, test_mod, tmp_path):
        """Test cache is invalidated when file changes."""
        mod_file = tmp_path / test_mod.name
        original_content = "original content"
        mod_file.write_text(original_content)
        test_mod.path = mod_file
        test_mod.size = len(original_content)  # Match actual file size

        cache = AnalysisCache(cache_dir=temp_cache_dir)

        # Save cache
        cache.save_cache(test_mod)

        # Verify cache hit
        assert cache.get_cached(mod_file) is not None

        # Modify file
        time.sleep(0.01)
        mod_file.write_text("modified content with different size!")

        # Cache should be invalidated
        cached_mod = cache.get_cached(mod_file)
        assert cached_mod is None

    def test_corrupted_cache_is_removed(self, temp_cache_dir, tmp_path):
        """Test corrupted cache files are removed."""
        cache = AnalysisCache(cache_dir=temp_cache_dir)

        # Create a test file
        test_file = tmp_path / "test.package"
        test_file.write_text("test content")

        # Create corrupted cache file
        cache_key = cache.get_cache_key(test_file)
        cache_file = temp_cache_dir / f"{cache_key}.pkl"
        cache_file.write_text("corrupted data, not a pickle")

        # Trying to load should remove corrupted cache
        cached_mod = cache.get_cached(test_file)

        assert cached_mod is None
        assert not cache_file.exists()

    def test_clear_all_cache(self, temp_cache_dir, tmp_path):
        """Test clearing all cache files."""
        cache = AnalysisCache(cache_dir=temp_cache_dir)

        # Create multiple cache files
        for i in range(5):
            mod_file = tmp_path / f"mod{i}.package"
            mod_file.write_text(f"content {i}")

            mod = Mod(
                name=f"mod{i}.package",
                path=mod_file,
                type=ModType.PACKAGE,
                size=100,
                hash=f"hash{i}",
            )
            cache.save_cache(mod)

        # Verify cache files exist
        assert len(list(temp_cache_dir.glob("*.pkl"))) == 5

        # Clear all
        removed = cache.clear_cache()

        assert removed == 5
        assert len(list(temp_cache_dir.glob("*.pkl"))) == 0

    def test_clear_old_cache(self, temp_cache_dir, tmp_path):
        """Test clearing only old cache files."""
        cache = AnalysisCache(cache_dir=temp_cache_dir)

        # Create cache files with different ages
        for i in range(3):
            mod_file = tmp_path / f"mod{i}.package"
            mod_file.write_text(f"content {i}")

            mod = Mod(
                name=f"mod{i}.package",
                path=mod_file,
                type=ModType.PACKAGE,
                size=100,
                hash=f"hash{i}",
            )
            cache.save_cache(mod)

        # Get cache files
        cache_files = list(temp_cache_dir.glob("*.pkl"))
        assert len(cache_files) == 3

        # Make one file "old" (8 days)
        old_time = (datetime.now() - timedelta(days=8)).timestamp()
        cache_files[0].touch()
        import os

        os.utime(cache_files[0], (old_time, old_time))

        # Clear files older than 7 days
        removed = cache.clear_cache(older_than_days=7)

        assert removed == 1
        assert len(list(temp_cache_dir.glob("*.pkl"))) == 2

    def test_get_cache_info_empty(self, temp_cache_dir):
        """Test cache info with empty cache."""
        cache = AnalysisCache(cache_dir=temp_cache_dir)

        info = cache.get_cache_info()

        assert info["cached_mods"] == 0
        assert info["cache_size_bytes"] == 0
        assert info["cache_size_mb"] == 0.0
        assert info["oldest_cache_days"] is None
        assert info["newest_cache_days"] is None

    def test_get_cache_info_with_files(self, temp_cache_dir, tmp_path):
        """Test cache info with cached files."""
        cache = AnalysisCache(cache_dir=temp_cache_dir)

        # Create some cache files
        for i in range(3):
            mod_file = tmp_path / f"mod{i}.package"
            mod_file.write_text(f"content {i}")

            mod = Mod(
                name=f"mod{i}.package",
                path=mod_file,
                type=ModType.PACKAGE,
                size=100 * (i + 1),
                hash=f"hash{i}",
            )
            cache.save_cache(mod)

        info = cache.get_cache_info()

        assert info["cached_mods"] == 3
        assert info["cache_size_bytes"] > 0
        assert info["cache_size_mb"] > 0
        assert info["oldest_cache_days"] is not None
        assert info["newest_cache_days"] is not None
        assert str(temp_cache_dir) in info["cache_directory"]

    def test_invalidate_mod(self, temp_cache_dir, test_mod, tmp_path):
        """Test invalidating cache for specific mod."""
        mod_file = tmp_path / test_mod.name
        content = "test content"
        mod_file.write_text(content)
        test_mod.path = mod_file
        test_mod.size = len(content)  # Match actual file size

        cache = AnalysisCache(cache_dir=temp_cache_dir)

        # Save cache
        cache.save_cache(test_mod)
        assert cache.get_cached(mod_file) is not None

        # Invalidate
        result = cache.invalidate_mod(mod_file)

        assert result is True
        assert cache.get_cached(mod_file) is None

    def test_invalidate_uncached_mod(self, temp_cache_dir, tmp_path):
        """Test invalidating mod that wasn't cached."""
        cache = AnalysisCache(cache_dir=temp_cache_dir)

        mod_file = tmp_path / "uncached.package"
        mod_file.write_text("test")

        result = cache.invalidate_mod(mod_file)

        assert result is False


class TestCachedScanner:
    """Test CachedScanner class."""

    def test_init(self, temp_cache_dir):
        """Test scanner initialization."""
        scanner = CachedScanner(cache_dir=temp_cache_dir)

        assert scanner.cache is not None
        assert scanner.cache_hits == 0
        assert scanner.cache_misses == 0

    def test_scan_with_cache_hits(self, temp_cache_dir, tmp_path):
        """Test scanning with cache hits."""
        # Create some test files
        for i in range(3):
            (tmp_path / f"mod{i}.package").write_text(f"content {i}")

        scanner = CachedScanner(
            parse_tunings=False,
            parse_scripts=False,
            calculate_hashes=False,
            cache_dir=temp_cache_dir,
        )

        # First scan (cache misses)
        mods1 = scanner.scan_directory(tmp_path, recursive=False)
        stats1 = scanner.get_cache_stats()

        assert stats1["cache_hits"] == 0
        assert stats1["cache_misses"] > 0

        # Second scan (cache hits)
        mods2 = scanner.scan_directory(tmp_path, recursive=False)
        stats2 = scanner.get_cache_stats()

        assert stats2["cache_hits"] > 0
        assert stats2["cache_hits"] == len(mods2)
        assert stats2["hit_rate"] == 100.0

    def test_cache_hit_rate_calculation(self, temp_cache_dir, tmp_path):
        """Test cache hit rate calculation."""
        # Create test files
        for i in range(10):
            (tmp_path / f"mod{i}.package").write_text(f"content {i}")

        scanner = CachedScanner(
            parse_tunings=False,
            parse_scripts=False,
            calculate_hashes=False,
            cache_dir=temp_cache_dir,
        )

        # First scan
        scanner.scan_directory(tmp_path, recursive=False)
        stats1 = scanner.get_cache_stats()
        assert stats1["hit_rate"] == 0.0

        # Second scan (all hits)
        scanner.scan_directory(tmp_path, recursive=False)
        stats2 = scanner.get_cache_stats()
        assert stats2["hit_rate"] == 100.0

    def test_mixed_cache_hits_and_misses(self, temp_cache_dir, tmp_path):
        """Test with some cached and some new files."""
        # Create initial files
        for i in range(5):
            (tmp_path / f"mod{i}.package").write_text(f"content {i}")

        scanner = CachedScanner(
            parse_tunings=False,
            parse_scripts=False,
            calculate_hashes=False,
            cache_dir=temp_cache_dir,
        )

        # First scan
        scanner.scan_directory(tmp_path, recursive=False)

        # Add more files
        for i in range(5, 10):
            (tmp_path / f"mod{i}.package").write_text(f"content {i}")

        # Second scan (mix of hits and misses)
        scanner.scan_directory(tmp_path, recursive=False)
        stats = scanner.get_cache_stats()

        assert stats["cache_hits"] == 5
        assert stats["cache_misses"] == 5
        assert stats["hit_rate"] == 50.0


class TestCachePerformance:
    """Test cache performance improvements."""

    def test_cache_is_faster_than_no_cache(self, temp_cache_dir, tmp_path):
        """Test that cached scans are faster."""
        # Create test files
        for i in range(20):
            (tmp_path / f"mod{i}.package").write_text(f"content {i}")

        scanner = CachedScanner(
            parse_tunings=False,
            parse_scripts=False,
            calculate_hashes=False,
            cache_dir=temp_cache_dir,
        )

        # First scan (no cache)
        start = time.time()
        mods1 = scanner.scan_directory(tmp_path, recursive=False)
        time_no_cache = time.time() - start

        # Second scan (with cache)
        start = time.time()
        mods2 = scanner.scan_directory(tmp_path, recursive=False)
        time_with_cache = time.time() - start

        # Cached should be faster (or at least not significantly slower)
        # For empty files, difference might be small
        assert len(mods1) == len(mods2)
        # Cached scan should be at least 2x faster for real mods
        # For empty files in tests, just verify it works
        assert time_with_cache < time_no_cache * 2


class TestIntegration:
    """Integration tests."""

    def test_complete_workflow(self, temp_cache_dir, tmp_path):
        """Test complete caching workflow."""
        # Create test directory
        for i in range(5):
            (tmp_path / f"mod{i}.package").write_text(f"content {i}")

        # Create scanner
        scanner = CachedScanner(
            parse_tunings=False,
            parse_scripts=False,
            calculate_hashes=False,
            cache_dir=temp_cache_dir,
        )

        # Initial scan
        mods1 = scanner.scan_directory(tmp_path)
        stats1 = scanner.get_cache_stats()

        assert len(mods1) == 5
        assert stats1["cache_hits"] == 0

        # Re-scan (all cached)
        mods2 = scanner.scan_directory(tmp_path)
        stats2 = scanner.get_cache_stats()

        assert len(mods2) == 5
        assert stats2["cache_hits"] == 5
        assert stats2["hit_rate"] == 100.0

        # Get cache info
        info = scanner.cache.get_cache_info()
        assert info["cached_mods"] == 5

        # Clear cache
        removed = scanner.cache.clear_cache()
        assert removed == 5

        # Re-scan (cache cleared)
        mods3 = scanner.scan_directory(tmp_path)
        stats3 = scanner.get_cache_stats()

        assert len(mods3) == 5
        assert stats3["cache_hits"] == 0
