"""Performance benchmarks for DBPF parser.

These tests measure parsing performance for different file sizes
to ensure the parser scales efficiently.

Run with: pytest tests/performance/test_dbpf_benchmarks.py -v
"""

import struct
import time
import zlib
from pathlib import Path

import pytest

from simanalysis.parsers.dbpf import DBPFReader


class TestDBPFPerformance:
    """Performance benchmarks for DBPF parser."""

    @pytest.fixture
    def benchmark_1mb_package(self, tmp_path: Path) -> Path:
        """Create a 1MB package file for benchmarking."""
        return self._create_benchmark_package(
            tmp_path / "benchmark_1mb.package",
            resource_count=50,
            resource_size=20_000,  # 20KB each
        )

    @pytest.fixture
    def benchmark_10mb_package(self, tmp_path: Path) -> Path:
        """Create a 10MB package file for benchmarking."""
        return self._create_benchmark_package(
            tmp_path / "benchmark_10mb.package",
            resource_count=500,
            resource_size=20_000,  # 20KB each
        )

    @pytest.fixture
    def benchmark_100mb_package(self, tmp_path: Path) -> Path:
        """Create a 100MB package file for benchmarking."""
        return self._create_benchmark_package(
            tmp_path / "benchmark_100mb.package",
            resource_count=1000,
            resource_size=100_000,  # 100KB each
        )

    @pytest.fixture
    def package_with_compressed(self, tmp_path: Path) -> Path:
        """Create package with compressed resources."""
        return self._create_benchmark_package(
            tmp_path / "compressed.package",
            resource_count=100,
            resource_size=50_000,
            compress_ratio=0.8,  # 80% compressed
        )

    def _create_benchmark_package(
        self,
        output_path: Path,
        resource_count: int,
        resource_size: int,
        compress_ratio: float = 0.0,
    ) -> Path:
        """
        Create a synthetic package file for benchmarking.

        Args:
            output_path: Where to save package
            resource_count: Number of resources to create
            resource_size: Size of each resource in bytes
            compress_ratio: Fraction of resources to compress (0.0-1.0)

        Returns:
            Path to created package
        """
        # Create header (96 bytes)
        header = bytearray(96)
        header[0:4] = b"DBPF"
        header[4:8] = struct.pack("<I", 2)  # Major version
        header[8:12] = struct.pack("<I", 1)  # Minor version
        header[40:44] = struct.pack("<I", resource_count)

        # Calculate index position (after all resources)
        resource_data_size = 0
        resource_offsets = []

        # Pre-calculate resource data
        resources_data = []
        for i in range(resource_count):
            # Generate unique data
            data = bytes([(i + j) % 256 for j in range(resource_size)])

            # Compress some resources
            if i < int(resource_count * compress_ratio):
                compressed = zlib.compress(data, level=6)
                resources_data.append((data, compressed, True))
                resource_offsets.append(96 + resource_data_size)
                resource_data_size += len(compressed)
            else:
                resources_data.append((data, data, False))
                resource_offsets.append(96 + resource_data_size)
                resource_data_size += len(data)

        index_offset = 96 + resource_data_size
        index_size = resource_count * 32

        header[44:48] = struct.pack("<I", index_offset)
        header[48:52] = struct.pack("<I", index_size)

        # Create index entries
        index = bytearray(index_size)

        for i in range(resource_count):
            offset = i * 32
            original_data, stored_data, is_compressed = resources_data[i]

            # Type ID (vary types)
            type_id = 0x545503B2 if i % 3 == 0 else 0x0333406C
            index[offset : offset + 4] = struct.pack("<I", type_id)

            # Group ID
            index[offset + 4 : offset + 8] = struct.pack("<I", 0x00000000)

            # Instance ID (unique)
            index[offset + 8 : offset + 16] = struct.pack("<Q", 0x1000000000000000 + i)

            # Resource offset
            index[offset + 16 : offset + 20] = struct.pack("<I", resource_offsets[i])

            # Uncompressed size
            index[offset + 20 : offset + 24] = struct.pack("<I", len(original_data))

            # Compressed size
            if is_compressed:
                index[offset + 24 : offset + 28] = struct.pack("<I", len(stored_data))
            else:
                index[offset + 24 : offset + 28] = struct.pack("<I", 0)

            # Flags
            index[offset + 28 : offset + 32] = struct.pack("<I", 0)

        # Write complete package
        with open(output_path, "wb") as f:
            f.write(header)

            # Write all resource data
            for _, stored_data, _ in resources_data:
                f.write(stored_data)

            # Write index
            f.write(index)

        return output_path

    @pytest.mark.benchmark
    def test_parse_1mb_header(self, benchmark_1mb_package: Path) -> None:
        """Benchmark: Parse header from 1MB package."""
        iterations = 100
        times = []

        for _ in range(iterations):
            reader = DBPFReader(benchmark_1mb_package)
            start = time.perf_counter()
            header = reader.read_header()
            elapsed = time.perf_counter() - start
            times.append(elapsed)

            assert header.magic == b"DBPF"

        avg_time = sum(times) / len(times)
        min_time = min(times)
        max_time = max(times)

        print(f"\n1MB Header Parsing ({iterations} iterations):")
        print(f"  Average: {avg_time*1000:.3f}ms")
        print(f"  Min:     {min_time*1000:.3f}ms")
        print(f"  Max:     {max_time*1000:.3f}ms")

        assert avg_time < 0.001  # Should be < 1ms

    @pytest.mark.benchmark
    def test_parse_1mb_index(self, benchmark_1mb_package: Path) -> None:
        """Benchmark: Parse index from 1MB package (50 resources)."""
        reader = DBPFReader(benchmark_1mb_package)

        start = time.perf_counter()
        resources = reader.read_index()
        elapsed = time.perf_counter() - start

        print(f"\n1MB Index Parsing:")
        print(f"  Time:      {elapsed*1000:.3f}ms")
        print(f"  Resources: {len(resources)}")
        print(f"  Per-resource: {(elapsed/len(resources))*1000:.3f}ms")

        assert len(resources) == 50
        assert elapsed < 0.01  # Should be < 10ms

    @pytest.mark.benchmark
    def test_parse_10mb_index(self, benchmark_10mb_package: Path) -> None:
        """Benchmark: Parse index from 10MB package (500 resources)."""
        reader = DBPFReader(benchmark_10mb_package)

        start = time.perf_counter()
        resources = reader.read_index()
        elapsed = time.perf_counter() - start

        print(f"\n10MB Index Parsing:")
        print(f"  Time:      {elapsed*1000:.3f}ms")
        print(f"  Resources: {len(resources)}")
        print(f"  Per-resource: {(elapsed/len(resources))*1000:.3f}ms")

        assert len(resources) == 500
        assert elapsed < 0.1  # Should be < 100ms

    @pytest.mark.benchmark
    def test_parse_100mb_index(self, benchmark_100mb_package: Path) -> None:
        """Benchmark: Parse index from 100MB package (1000 resources)."""
        reader = DBPFReader(benchmark_100mb_package)

        start = time.perf_counter()
        resources = reader.read_index()
        elapsed = time.perf_counter() - start

        print(f"\n100MB Index Parsing:")
        print(f"  Time:      {elapsed*1000:.3f}ms")
        print(f"  Resources: {len(resources)}")
        print(f"  Per-resource: {(elapsed/len(resources))*1000:.3f}ms")

        assert len(resources) == 1000
        assert elapsed < 0.5  # Should be < 500ms

    @pytest.mark.benchmark
    def test_extract_uncompressed_resource(
        self, benchmark_1mb_package: Path
    ) -> None:
        """Benchmark: Extract uncompressed resource."""
        reader = DBPFReader(benchmark_1mb_package)
        resources = reader.read_index()

        # Find uncompressed resource
        uncompressed = [r for r in resources if not r.is_compressed][0]

        iterations = 50
        times = []

        for _ in range(iterations):
            start = time.perf_counter()
            data = reader.get_resource(uncompressed)
            elapsed = time.perf_counter() - start
            times.append(elapsed)

            assert len(data) == uncompressed.size

        avg_time = sum(times) / len(times)

        print(f"\nUncompressed Resource Extraction ({iterations} iterations):")
        print(f"  Size:    {uncompressed.size} bytes")
        print(f"  Average: {avg_time*1000:.3f}ms")
        print(f"  Throughput: {(uncompressed.size / avg_time / 1024 / 1024):.1f} MB/s")

        assert avg_time < 0.01  # Should be < 10ms

    @pytest.mark.benchmark
    def test_extract_compressed_resource(
        self, package_with_compressed: Path
    ) -> None:
        """Benchmark: Extract and decompress compressed resource."""
        reader = DBPFReader(package_with_compressed)
        resources = reader.read_index()

        # Find compressed resource
        compressed = [r for r in resources if r.is_compressed][0]

        iterations = 50
        times = []

        for _ in range(iterations):
            start = time.perf_counter()
            data = reader.get_resource(compressed)
            elapsed = time.perf_counter() - start
            times.append(elapsed)

            assert len(data) == compressed.size

        avg_time = sum(times) / len(times)
        compression_ratio = compressed.compressed_size / compressed.size

        print(f"\nCompressed Resource Extraction ({iterations} iterations):")
        print(f"  Compressed size:   {compressed.compressed_size} bytes")
        print(f"  Uncompressed size: {compressed.size} bytes")
        print(f"  Compression ratio: {compression_ratio:.2%}")
        print(f"  Average time:      {avg_time*1000:.3f}ms")
        print(
            f"  Throughput: {(compressed.size / avg_time / 1024 / 1024):.1f} MB/s (decompressed)"
        )

        assert avg_time < 0.05  # Should be < 50ms

    @pytest.mark.benchmark
    def test_filter_by_type_performance(self, benchmark_10mb_package: Path) -> None:
        """Benchmark: Filter resources by type."""
        reader = DBPFReader(benchmark_10mb_package)

        # First, read index
        resources = reader.read_index()

        # Benchmark type filtering
        iterations = 100
        times = []

        for _ in range(iterations):
            start = time.perf_counter()
            xml_resources = reader.get_resources_by_type(0x545503B2)
            elapsed = time.perf_counter() - start
            times.append(elapsed)

        avg_time = sum(times) / len(times)

        print(f"\nType Filtering ({iterations} iterations):")
        print(f"  Total resources: {len(resources)}")
        print(f"  Matching:        {len(xml_resources)}")
        print(f"  Average time:    {avg_time*1000:.3f}ms")

        assert avg_time < 0.01  # Should be < 10ms

    @pytest.mark.benchmark
    def test_lazy_loading_overhead(self, benchmark_1mb_package: Path) -> None:
        """Benchmark: Measure lazy loading overhead."""
        iterations = 100

        # Test with lazy loading
        times_lazy = []
        for _ in range(iterations):
            start = time.perf_counter()
            reader = DBPFReader(benchmark_1mb_package)
            # Access header property (triggers lazy load)
            header = reader.header
            elapsed = time.perf_counter() - start
            times_lazy.append(elapsed)

        # Test without lazy loading (direct call)
        times_direct = []
        for _ in range(iterations):
            start = time.perf_counter()
            reader = DBPFReader(benchmark_1mb_package)
            header = reader.read_header()
            elapsed = time.perf_counter() - start
            times_direct.append(elapsed)

        avg_lazy = sum(times_lazy) / len(times_lazy)
        avg_direct = sum(times_direct) / len(times_direct)
        overhead = avg_lazy - avg_direct

        print(f"\nLazy Loading Overhead ({iterations} iterations):")
        print(f"  Lazy loading:   {avg_lazy*1000:.3f}ms")
        print(f"  Direct call:    {avg_direct*1000:.3f}ms")
        print(f"  Overhead:       {overhead*1000:.3f}ms ({overhead/avg_direct:.1%})")

        # Overhead should be minimal (< 10% of direct time)
        assert overhead < avg_direct * 0.1

    @pytest.mark.benchmark
    def test_full_pipeline_performance(self, benchmark_10mb_package: Path) -> None:
        """Benchmark: Complete parse-and-extract pipeline."""
        start = time.perf_counter()

        # Step 1: Initialize reader
        reader = DBPFReader(benchmark_10mb_package)
        init_time = time.perf_counter() - start

        # Step 2: Read header
        start = time.perf_counter()
        header = reader.read_header()
        header_time = time.perf_counter() - start

        # Step 3: Read index
        start = time.perf_counter()
        resources = reader.read_index()
        index_time = time.perf_counter() - start

        # Step 4: Extract first 10 resources
        start = time.perf_counter()
        for res in resources[:10]:
            data = reader.get_resource(res)
        extract_time = time.perf_counter() - start

        total_time = init_time + header_time + index_time + extract_time

        print(f"\nFull Pipeline Performance:")
        print(f"  1. Initialize: {init_time*1000:.3f}ms")
        print(f"  2. Header:     {header_time*1000:.3f}ms")
        print(f"  3. Index:      {index_time*1000:.3f}ms ({len(resources)} resources)")
        print(f"  4. Extract:    {extract_time*1000:.3f}ms (10 resources)")
        print(f"  Total:         {total_time*1000:.3f}ms")

        assert total_time < 1.0  # Complete pipeline < 1 second


class TestDBPFScalability:
    """Tests to ensure DBPF parser scales linearly with file size."""

    def test_index_parsing_scales_linearly(self, tmp_path: Path) -> None:
        """Verify index parsing time scales linearly with resource count."""
        counts = [10, 50, 100, 500, 1000]
        times = []

        for count in counts:
            # Create package with 'count' resources
            package = self._create_package_with_n_resources(tmp_path, count)

            # Time index parsing
            reader = DBPFReader(package)
            start = time.perf_counter()
            resources = reader.read_index()
            elapsed = time.perf_counter() - start

            times.append(elapsed)
            assert len(resources) == count

        # Calculate time per resource
        times_per_resource = [t / c for t, c in zip(times, counts)]

        print(f"\nScalability Analysis (Index Parsing):")
        for count, total_time, per_res in zip(counts, times, times_per_resource):
            print(
                f"  {count:4d} resources: {total_time*1000:6.3f}ms "
                f"({per_res*1000:.4f}ms per resource)"
            )

        # Verify linear scaling: time per resource should be relatively constant
        # Allow for some variance due to I/O and caching
        avg_per_resource = sum(times_per_resource) / len(times_per_resource)
        for per_res in times_per_resource:
            # Each should be within 2x of average
            assert per_res < avg_per_resource * 2

    def _create_package_with_n_resources(
        self, tmp_path: Path, count: int
    ) -> Path:
        """Helper to create package with specific resource count."""
        package = tmp_path / f"package_{count}.package"

        # Header
        header = bytearray(96)
        header[0:4] = b"DBPF"
        header[4:8] = struct.pack("<I", 2)
        header[40:44] = struct.pack("<I", count)

        # Small resources for faster creation
        resource_size = 100
        index_offset = 96 + (count * resource_size)
        index_size = count * 32

        header[44:48] = struct.pack("<I", index_offset)
        header[48:52] = struct.pack("<I", index_size)

        # Index
        index = bytearray(index_size)
        for i in range(count):
            offset = i * 32
            index[offset : offset + 4] = struct.pack("<I", 0x545503B2)
            index[offset + 4 : offset + 8] = struct.pack("<I", 0)
            index[offset + 8 : offset + 16] = struct.pack("<Q", i)
            index[offset + 16 : offset + 20] = struct.pack("<I", 96 + i * resource_size)
            index[offset + 20 : offset + 24] = struct.pack("<I", resource_size)
            index[offset + 24 : offset + 28] = struct.pack("<I", 0)

        # Write file
        with open(package, "wb") as f:
            f.write(header)
            f.write(bytes(count * resource_size))  # Dummy resource data
            f.write(index)

        return package
