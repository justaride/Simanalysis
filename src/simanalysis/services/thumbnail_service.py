"""Service for extracting and managing mod thumbnails."""

import logging
from pathlib import Path
from typing import Optional

from simanalysis.exceptions import DBPFError
from simanalysis.parsers.dbpf import DBPFReader

logger = logging.getLogger(__name__)


class ThumbnailService:
    """Service for extracting thumbnails from Sims 4 package files."""

    # Resource Type IDs for thumbnails
    THUMBNAIL_TYPES = [
        0x3C2A8647,  # Build/Buy Thumbnail
        0x3C1AF1F2,  # CAS Part Thumbnail
        0x5B282D45,  # Body Part Thumbnail
        0x00000000,  # Generic Image (fallback)
    ]

    # PNG Image Resource Type
    PNG_IMAGE_TYPE = 0x2F7D0004

    def __init__(self, cache_dir: Optional[Path] = None):
        """
        Initialize ThumbnailService.

        Args:
            cache_dir: Directory to store cached thumbnails. If None, caching is disabled.
        """
        self.cache_dir = cache_dir
        if self.cache_dir:
            self.cache_dir.mkdir(parents=True, exist_ok=True)

    def get_thumbnail(self, package_path: Path) -> Optional[bytes]:
        """
        Extract the best available thumbnail from a package file.

        Args:
            package_path: Path to the .package file.

        Returns:
            Raw image bytes (usually PNG) or None if no thumbnail found.
        """
        if not package_path.exists():
            return None

        try:
            reader = DBPFReader(package_path)

            # 1. Try specific thumbnail types first
            for type_id in self.THUMBNAIL_TYPES:
                resources = reader.get_resources_by_type(type_id)
                if resources:
                    # Return the largest thumbnail (usually the best quality)
                    # Some packages have multiple sizes (small, medium, large)
                    best_resource = max(resources, key=lambda r: r.size)
                    return reader.get_resource(best_resource)

            # 2. Fallback to generic PNG images if no specific thumbnail found
            # This is risky as it might pick a UI icon or texture, but better than nothing
            png_resources = reader.get_resources_by_type(self.PNG_IMAGE_TYPE)
            if png_resources:
                # Heuristic: Pick the image that looks most like a thumbnail (e.g., reasonable size)
                # For now, just pick the largest one that isn't huge (textures are huge)
                # Limit to 256KB to avoid loading massive textures
                candidates = [r for r in png_resources if 1024 < r.size < 256 * 1024]
                if candidates:
                    best_resource = max(candidates, key=lambda r: r.size)
                    return reader.get_resource(best_resource)

            return None

        except DBPFError as e:
            logger.warning(f"Error reading package {package_path}: {e}")
            return None
        except Exception as e:
            logger.error(f"Unexpected error extracting thumbnail from {package_path}: {e}")
            return None
