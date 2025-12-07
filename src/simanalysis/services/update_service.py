"""Service for checking application updates."""

import logging
import aiohttp
from typing import Optional, Dict, Any
from simanalysis import __version__

logger = logging.getLogger(__name__)

class UpdateService:
    """
    Service for checking for application updates via GitHub API.
    """

    GITHUB_REPO = "justaride/Simanalysis"
    API_URL = f"https://api.github.com/repos/{GITHUB_REPO}/releases/latest"

    async def check_for_updates(self) -> Optional[Dict[str, Any]]:
        """
        Check if a new version is available.
        
        Returns:
            Dictionary with update info if available, None otherwise.
        """
        ssl_context = ssl.create_default_context(cafile=certifi.where())
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    self.API_URL,
                    ssl=ssl_context
                ) as response:
                    if response.status == 200:
                        data = await response.json()
                        latest_version = data.get("tag_name", "").lstrip("v")
                        current_version = __version__
                        
                        if self._is_newer(latest_version, current_version):
                            return {
                                "version": latest_version,
                                "current_version": current_version,
                                "download_url": data.get("html_url"),
                                "release_notes": data.get("body"),
                                "published_at": data.get("published_at")
                            }
        except Exception as e:
            logger.warning(f"Failed to check for updates: {e}")
            
        return None

    def _is_newer(self, latest: str, current: str) -> bool:
        """Compare semantic versions."""
        try:
            l_parts = [int(x) for x in latest.split(".")]
            c_parts = [int(x) for x in current.split(".")]
            
            # Pad with zeros if lengths differ
            while len(l_parts) < 3: l_parts.append(0)
            while len(c_parts) < 3: c_parts.append(0)
            
            return l_parts > c_parts
        except ValueError:
            return False
