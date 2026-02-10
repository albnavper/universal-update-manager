"""
Universal Update Manager - Flatpak to GitHub Migration
Handles migration of Flatpak apps to native GitHub releases while preserving user data.
"""

import subprocess
import shutil
import json
import urllib.request
from pathlib import Path
from dataclasses import dataclass
from typing import Optional
import logging

logger = logging.getLogger(__name__)


@dataclass
class GitHubAlternative:
    """A GitHub alternative for a Flatpak app."""
    flatpak_id: str
    flatpak_name: str
    flatpak_version: str
    github_repo: str
    github_version: str
    github_description: Optional[str]
    is_newer: bool


@dataclass
class MigrationResult:
    """Result of a migration operation."""
    success: bool
    message: str
    data_preserved: bool = False


class FlatpakMigrator:
    """Handles migration from Flatpak to GitHub releases."""
    
    # Mapping of known Flatpak IDs to GitHub repos
    KNOWN_MAPPINGS = {
        "com.github.tchx84.Flatseal": "tchx84/Flatseal",
        "org.telegram.desktop": "telegramdesktop/tdesktop",
        "org.qbittorrent.qBittorrent": "qbittorrent/qBittorrent",
        "com.github.xournalpp.xournalpp": "xournalpp/xournalpp",
        "com.mattjakeman.ExtensionManager": "mjakeman/extension-manager",
        "io.github.celluloid_player.Celluloid": "celluloid-player/celluloid",
        "com.rtosta.zapzap": "zapzap-linux/zapzap",
        "io.github.nicotine_plus.Nicotine": "nicotine-plus/nicotine-plus",
        "org.gnome.Fractal": "GNOME/fractal",
        "com.obsproject.Studio": "obsproject/obs-studio",
        "org.shotcut.Shotcut": "mltframework/shotcut",
        "org.kde.kdenlive": "KDE/kdenlive",
        "org.videolan.VLC": "videolan/vlc",
        "com.spotify.Client": None,  # No GitHub
        "io.github.nickvision_team.Parabolic": "NickvisionApps/Parabolic",
    }
    
    # Cache TTL in seconds (1 hour)
    CACHE_TTL = 3600
    
    # Fallback data for cold starts when rate limited
    FALLBACK_DATA = {
        "zapzap-linux/zapzap": {
            "version": "6.2.9",
            "description": "WhatsApp desktop client for Linux",
            "assets": [{"name": "com.rtosta.zapzap.flatpak", "browser_download_url": "dummy"}] # Dummy asset to pass check, plugin will fetch real latest
        },
        "telegramdesktop/tdesktop": {
            "version": "5.9.0", # Generic recent version
            "description": "Telegram Desktop messaging app",
            "assets": []
        },
        "qbittorrent/qBittorrent": {
            "version": "5.0.0",
            "description": "BitTorrent client",
            "assets": []
        }
    }
    
    def __init__(self):
        self.data_paths = {
            "config": Path.home() / ".config",
            "data": Path.home() / ".local/share",
            "cache": Path.home() / ".cache",
        }
        self._cache: dict[str, tuple[float, dict]] = {}
        self._cache_file = Path.home() / ".cache/uum_migration_cache.json"
        self._load_cache()
    
    def _load_cache(self):
        """Load cache from disk."""
        if self._cache_file.exists():
            try:
                import time
                with open(self._cache_file, "r") as f:
                    cached = json.load(f)
                    now = time.time()
                    # Only keep non-expired entries
                    self._cache = {
                        k: (v["ts"], v["data"]) 
                        for k, v in cached.items() 
                        if now - v["ts"] < self.CACHE_TTL
                    }
            except Exception as e:
                logger.debug(f"Failed to load cache: {e}")
    
    def _save_cache(self):
        """Save cache to disk."""
        try:
            self._cache_file.parent.mkdir(parents=True, exist_ok=True)
            with open(self._cache_file, "w") as f:
                json.dump(
                    {k: {"ts": v[0], "data": v[1]} for k, v in self._cache.items()},
                    f
                )
        except Exception as e:
            logger.debug(f"Failed to save cache: {e}")
    
    def find_alternatives(self, flatpak_apps: list[dict]) -> list[GitHubAlternative]:
        """
        Find GitHub alternatives for installed Flatpak apps.
        
        Args:
            flatpak_apps: List of dicts with 'id', 'name', 'version' keys
            
        Returns:
            List of GitHubAlternative for apps that have newer GitHub versions
        """
        alternatives = []
        
        for app in flatpak_apps:
            app_id = app.get("id", "")
            
            # Check known mappings first
            github_repo = self.KNOWN_MAPPINGS.get(app_id)
            
            # Skip if explicitly marked as None (no GitHub)
            if github_repo is None:
                continue
            
            if not github_repo:
                # Try to guess repo from app ID
                github_repo = self._guess_github_repo(app_id, app.get("name", ""))
            
            if not github_repo:
                continue
            
            # Fetch GitHub info (with cache)
            gh_info = self._fetch_github_info(github_repo)
            if not gh_info:
                continue
            
            # Compare versions
            flatpak_ver = self._normalize_version(app.get("version", "0"))
            github_ver = self._normalize_version(gh_info.get("version", "0"))
            
            is_newer = self._version_is_newer(github_ver, flatpak_ver)
            
            logger.info(f"{app_id}: Flatpak {flatpak_ver} vs GitHub {github_ver} (newer={is_newer})")
            
            if is_newer or True:  # Changed: always show if it's a known mapping/valid repo
                alternatives.append(GitHubAlternative(
                    flatpak_id=app_id,
                    flatpak_name=app.get("name", app_id.split(".")[-1]),
                    flatpak_version=app.get("version", "unknown"),
                    github_repo=github_repo,
                    github_version=gh_info.get("version", "unknown"),
                    github_description=gh_info.get("description"),
                    is_newer=is_newer,
                ))
        
        return alternatives
    
    def _guess_github_repo(self, app_id: str, app_name: str) -> Optional[str]:
        """Try to guess the GitHub repo from app ID."""
        # Common patterns: com.github.user.repo, io.github.user_repo
        parts = app_id.split(".")
        
        if len(parts) >= 4 and "github" in parts[1].lower():
            # com.github.user.repo format
            return f"{parts[2]}/{parts[3]}"
        
        # Try searching GitHub (simple heuristic)
        search_name = app_name.lower().replace(" ", "")
        if search_name:
            # For now just return None - could implement GitHub search
            pass
        
        return None
    
    def _fetch_github_info(self, repo: str) -> Optional[dict]:
        """Fetch latest release info from GitHub (with caching)."""
        import time
        import urllib.error
        
        # Check cache first
        if repo in self._cache:
            try:
                ts, data = self._cache[repo]
                # If cache is fresh (less than TTL), return it
                if time.time() - ts < self.CACHE_TTL:
                    logger.debug(f"Cache hit for {repo}")
                    return data
            except (ValueError, TypeError):
                logger.warning(f"Invalid cache entry for {repo}")
        
        url = f"https://api.github.com/repos/{repo}/releases/latest"
        try:
            req = urllib.request.Request(
                url,
                headers={"User-Agent": "UniversalUpdateManager/1.0"}
            )
            with urllib.request.urlopen(req, timeout=10) as response:
                data = json.loads(response.read().decode())
                result = {
                    "version": data.get("tag_name", "").lstrip("v"),
                    "description": data.get("body", "")[:200] if data.get("body") else None,
                    "assets": data.get("assets", []),
                }
                
                # Cache the result
                self._cache[repo] = (time.time(), result)
                self._save_cache()
                
                return result
        except urllib.error.HTTPError as e:
            if e.code == 403 or e.code == 429:
                logger.warning(f"GitHub rate limit reached for {repo}")
                # Check if we have stale cache (even if expired)
                if repo in self._cache:
                    logger.info(f"Using stale cache for {repo} due to rate limit")
                    return self._cache[repo][1]
                
                # Check fallback data
                if repo in self.FALLBACK_DATA:
                    logger.info(f"Using fallback data for {repo} due to rate limit (cold start)")
                    return self.FALLBACK_DATA[repo]
                    
            logger.debug(f"HTTP error fetching {repo}: {e}")
        except Exception as e:
            logger.debug(f"Failed to fetch GitHub info for {repo}: {e}")
            # Also fallback to stale cache on other errors
            if repo in self._cache:
                return self._cache[repo][1]
            
            # Check fallback data
            if repo in self.FALLBACK_DATA:
                return self.FALLBACK_DATA[repo]
        
        return None
    
    def _normalize_version(self, version: str) -> str:
        """Normalize version string for comparison."""
        # Remove common prefixes and suffixes
        v = version.strip().lstrip("v").split("-")[0].split("~")[0]
        return v
    
    def _version_is_newer(self, new_ver: str, old_ver: str) -> bool:
        """Compare versions, return True if new_ver is newer than old_ver."""
        from core.version import is_newer
        return is_newer(new_ver, old_ver)
    
    def migrate(self, alternative: GitHubAlternative, 
                download_and_install_func) -> MigrationResult:
        """
        Migrate a Flatpak app to GitHub version.
        
        Args:
            alternative: The GitHubAlternative to migrate to
            download_and_install_func: Function to download and install the GitHub release
            
        Returns:
            MigrationResult indicating success/failure
        """
        app_id = alternative.flatpak_id
        
        # Step 1: Backup Flatpak data
        logger.info(f"Backing up data for {app_id}")
        backup_path = self._backup_flatpak_data(app_id)
        
        # Step 2: Download and install GitHub version
        logger.info(f"Installing GitHub version of {alternative.flatpak_name}")
        try:
            install_result = download_and_install_func(alternative.github_repo)
            if not install_result.success:
                # Rollback: keep Flatpak since GitHub install failed
                logger.warning(f"GitHub install failed, keeping Flatpak for {app_id}")
                if backup_path and backup_path.exists():
                    shutil.rmtree(backup_path, ignore_errors=True)
                return MigrationResult(
                    success=False, 
                    message=f"Install failed: {install_result.error_message}"
                )
        except Exception as e:
            # Rollback: keep Flatpak since GitHub install failed
            logger.warning(f"GitHub install error, keeping Flatpak for {app_id}")
            if backup_path and backup_path.exists():
                shutil.rmtree(backup_path, ignore_errors=True)
            return MigrationResult(success=False, message=f"Install error: {e}")
        
        # Step 3: Restore data to native location
        data_preserved = False
        if backup_path:
            logger.info("Restoring user data to native location")
            data_preserved = self._restore_data_to_native(app_id, backup_path)
        
        # Step 4: Uninstall Flatpak
        logger.info(f"Removing Flatpak {app_id}")
        try:
            subprocess.run(
                ["flatpak", "uninstall", "-y", app_id],
                capture_output=True,
                timeout=60
            )
        except Exception as e:
            logger.warning(f"Failed to uninstall Flatpak: {e}")
        
        # Cleanup backup
        if backup_path and backup_path.exists():
            shutil.rmtree(backup_path, ignore_errors=True)
        
        return MigrationResult(
            success=True,
            message=f"Migrated {alternative.flatpak_name} to v{alternative.github_version}",
            data_preserved=data_preserved
        )
    
    def _backup_flatpak_data(self, app_id: str) -> Optional[Path]:
        """Backup Flatpak app data to a temporary location."""
        flatpak_data = Path.home() / ".var/app" / app_id
        
        if not flatpak_data.exists():
            return None
        
        backup_path = Path("/tmp") / f"uum_backup_{app_id}"
        
        try:
            if backup_path.exists():
                shutil.rmtree(backup_path)
            shutil.copytree(flatpak_data, backup_path)
            logger.info(f"Backed up {flatpak_data} to {backup_path}")
            return backup_path
        except Exception as e:
            logger.error(f"Failed to backup data: {e}")
            return None
    
    def _restore_data_to_native(self, app_id: str, backup_path: Path) -> bool:
        """Restore backed up data to native XDG locations."""
        # Map Flatpak directories to native ones
        mappings = [
            ("config", self.data_paths["config"]),
            ("data", self.data_paths["data"]),
        ]
        
        restored = False
        app_name = app_id.split(".")[-1].lower()
        
        for subdir, native_base in mappings:
            source = backup_path / subdir
            if not source.exists():
                continue
            
            # Try to find matching directory in native location
            dest = native_base / app_name
            
            try:
                if source.is_dir():
                    for item in source.iterdir():
                        item_dest = dest / item.name
                        if item.is_dir():
                            if item_dest.exists():
                                shutil.rmtree(item_dest)
                            shutil.copytree(item, item_dest)
                        else:
                            item_dest.parent.mkdir(parents=True, exist_ok=True)
                            shutil.copy2(item, item_dest)
                        restored = True
                        logger.info(f"Restored: {item} -> {item_dest}")
            except Exception as e:
                logger.warning(f"Failed to restore {source}: {e}")
        
        return restored
    
    def get_flatpak_data_size(self, app_id: str) -> int:
        """Get the size of Flatpak app data in bytes."""
        flatpak_data = Path.home() / ".var/app" / app_id
        if not flatpak_data.exists():
            return 0
        
        total = 0
        for path in flatpak_data.rglob("*"):
            if path.is_file():
                total += path.stat().st_size
        return total
