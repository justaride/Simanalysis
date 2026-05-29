"""Service for managing application configuration."""

import json
import logging
from pathlib import Path
from typing import Any, Optional

logger = logging.getLogger(__name__)


class ConfigService:
    """
    Service for loading and saving application configuration.
    Stores config in ~/.simanalysis/config.json
    """

    def __init__(self) -> None:
        self.config_dir = Path.home() / ".simanalysis"
        self.config_file = self.config_dir / "config.json"
        self._config: dict[str, Any] = {}
        self._load_config()

    def _load_config(self) -> None:
        """Load configuration from file."""
        try:
            if not self.config_dir.exists():
                self.config_dir.mkdir(parents=True, exist_ok=True)

            if self.config_file.exists():
                with open(self.config_file) as f:
                    self._config = json.load(f)
            else:
                self._config = {}
                self._save_config()

        except Exception as e:
            logger.error(f"Failed to load config: {e}")
            self._config = {}

    def _save_config(self) -> None:
        """Save configuration to file."""
        try:
            with open(self.config_file, "w") as f:
                json.dump(self._config, f, indent=2)
        except Exception as e:
            logger.error(f"Failed to save config: {e}")

    def get(self, key: str, default: Any = None) -> Any:
        """Get a configuration value."""
        return self._config.get(key, default)

    def set(self, key: str, value: Any) -> None:
        """Set a configuration value and save."""
        self._config[key] = value
        self._save_config()

    @property
    def last_scan_path(self) -> Optional[str]:
        """Get the last scanned directory path."""
        value = self.get("last_scan_path")
        if value is None or isinstance(value, str):
            return value
        return str(value)

    @last_scan_path.setter
    def last_scan_path(self, path: str) -> None:
        """Set the last scanned directory path."""
        self.set("last_scan_path", str(path))
