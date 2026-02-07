"""
Universal Update Manager - Persistent Version Storage
Stores installed versions for apps that can't be auto-detected.
"""

import json
import logging
from pathlib import Path
from typing import Optional
from datetime import datetime

logger = logging.getLogger(__name__)

VERSION_STORE_PATH = Path.home() / ".config" / "uum" / "installed_versions.json"


class VersionStore:
    """
    Persistent storage for installed software versions.
    
    This is used for apps where version can't be auto-detected:
    - Telegram Desktop (tarball install in /opt)
    - Xournal++ (AppImage without version in filename)
    - Other portable/AppImage apps
    
    The version is stored when:
    1. User successfully installs/updates via UUM
    2. User manually sets the version via UI
    """
    
    def __init__(self):
        self._store_path = VERSION_STORE_PATH
        self._cache: dict = {}
        self._load()
    
    def _load(self):
        """Load stored versions from disk."""
        if self._store_path.exists():
            try:
                self._cache = json.loads(self._store_path.read_text())
            except (json.JSONDecodeError, IOError) as e:
                logger.warning(f"Failed to load version store: {e}")
                self._cache = {}
        else:
            self._cache = {}
    
    def _save(self):
        """Save versions to disk."""
        try:
            self._store_path.parent.mkdir(parents=True, exist_ok=True)
            self._store_path.write_text(json.dumps(self._cache, indent=2))
        except IOError as e:
            logger.error(f"Failed to save version store: {e}")
    
    def get_version(self, app_id: str) -> Optional[str]:
        """
        Get stored version for an app.
        
        Args:
            app_id: Application ID (e.g., 'telegram', 'xournalpp')
            
        Returns:
            Version string or None if not stored
        """
        entry = self._cache.get(app_id.lower())
        if entry:
            return entry.get("version")
        return None
    
    def set_version(self, app_id: str, version: str, source: str = "uum"):
        """
        Store version for an app.
        
        Args:
            app_id: Application ID
            version: Version string to store
            source: How the version was determined ('uum', 'manual', 'detected')
        """
        app_id = app_id.lower()
        self._cache[app_id] = {
            "version": version,
            "source": source,
            "updated_at": datetime.now().isoformat(),
        }
        self._save()
        logger.info(f"Stored version for {app_id}: {version}")
    
    def remove_version(self, app_id: str):
        """Remove stored version for an app."""
        app_id = app_id.lower()
        if app_id in self._cache:
            del self._cache[app_id]
            self._save()
    
    def get_all(self) -> dict:
        """Get all stored versions."""
        return {k: v.get("version") for k, v in self._cache.items()}


# Singleton instance
_store = None

def get_version_store() -> VersionStore:
    """Get singleton VersionStore instance."""
    global _store
    if _store is None:
        _store = VersionStore()
    return _store


def get_stored_version(app_id: str) -> Optional[str]:
    """Convenience function to get stored version."""
    return get_version_store().get_version(app_id)


def set_stored_version(app_id: str, version: str, source: str = "uum"):
    """Convenience function to store version."""
    get_version_store().set_version(app_id, version, source)
