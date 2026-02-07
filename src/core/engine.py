"""
Universal Update Manager - Core Update Engine
Coordinates update checking and installation across all plugins.
"""

import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Optional
from pathlib import Path
import json

from plugins import (
    UpdateSourcePlugin,
    SoftwareInfo,
    UpdateStatus,
    InstallResult,
    GitHubReleasesPlugin,
    FlatpakPlugin,
    WebScraperPlugin,
    JetBrainsPlugin,
)

logger = logging.getLogger(__name__)


class UpdateEngine:
    """
    Core engine that coordinates update checking and installation.
    """

    def __init__(self, config_path: Optional[Path] = None):
        """
        Initialize the update engine.
        
        Args:
            config_path: Path to configuration file.
        """
        self.config_path = config_path
        self.plugins: list[UpdateSourcePlugin] = []
        self.config = self._load_config(config_path)
        self._init_plugins()

    def _load_config(self, config_path: Optional[Path]) -> dict:
        """Load configuration from file or use defaults."""
        if config_path and config_path.exists():
            try:
                with open(config_path) as f:
                    return json.load(f)
            except (json.JSONDecodeError, IOError) as e:
                logger.warning(f"Failed to load config: {e}")
        
        return self._default_config()
    
    def save_config(self) -> None:
        """Save current configuration to file."""
        if self.config_path:
            self.config_path.parent.mkdir(parents=True, exist_ok=True)
            with open(self.config_path, 'w') as f:
                json.dump(self.config, f, indent=2)

    def _default_config(self) -> dict:
        """Return default configuration."""
        return {
            "github": {
                "enabled": True,
                "packages": [
                    {
                        "id": "antigravity-tools",
                        "name": "Antigravity Tools",
                        "repo": "lbjlaq/Antigravity-Manager",
                        "asset_pattern": r".*_amd64\.deb$",
                    },
                    {
                        "id": "jackett",
                        "name": "Jackett",
                        "repo": "Jackett/Jackett",
                        "asset_pattern": r"Jackett\.Binaries\.LinuxAMDx64\.tar\.gz$",
                    },
                ]
            },
            "flatpak": {
                "enabled": True,
            },
            "web": {
                "enabled": True,
                "packages": [
                    {
                        "id": "devkinsta",
                        "name": "DevKinsta",
                        "url": "https://kinsta.com/devkinsta/",
                        "version_pattern": r"Version\s+([\d.]+)",
                    },
                    {
                        "id": "local",
                        "name": "Local by Flywheel",
                        "url": "https://localwp.com/releases/",
                        "version_pattern": r"(\d+\.\d+\.\d+)",
                    },
                ]
            },
            "jetbrains": {
                "enabled": True,
                "packages": [
                    {
                        "id": "android-studio",
                        "name": "Android Studio",
                    },
                ]
            },
            "ignored": [],
        }

    def _init_plugins(self) -> None:
        """Initialize enabled plugins."""
        if self.config.get("github", {}).get("enabled", True):
            self.plugins.append(
                GitHubReleasesPlugin(self.config.get("github", {}))
            )
        
        if self.config.get("flatpak", {}).get("enabled", True):
            self.plugins.append(
                FlatpakPlugin(self.config.get("flatpak", {}))
            )
        
        if self.config.get("snap", {}).get("enabled", True):
            from plugins.snap import SnapPlugin
            self.plugins.append(
                SnapPlugin(self.config.get("snap", {}))
            )
        
        if self.config.get("apt", {}).get("enabled", False):
            # APT disabled by default - can list ALL upgradable packages
            from plugins.apt import APTPlugin
            self.plugins.append(
                APTPlugin(self.config.get("apt", {}))
            )
        
        if self.config.get("web", {}).get("enabled", True):
            self.plugins.append(
                WebScraperPlugin(self.config.get("web", {}))
            )
        
        if self.config.get("jetbrains", {}).get("enabled", True):
            self.plugins.append(
                JetBrainsPlugin(self.config.get("jetbrains", {}))
            )
    
    def add_package(self, source_type: str, package_config: dict) -> None:
        """Add a new package to configuration with deduplication."""
        if source_type not in self.config:
            self.config[source_type] = {"enabled": True, "packages": []}
        
        if "packages" not in self.config[source_type]:
            self.config[source_type]["packages"] = []
        
        packages = self.config[source_type]["packages"]
        
        # Check for duplicate by repo (for github) or id
        new_repo = package_config.get("repo", "").lower()
        new_id = package_config.get("id", "").lower()
        
        for existing in packages:
            existing_repo = existing.get("repo", "").lower()
            existing_id = existing.get("id", "").lower()
            
            if new_repo and existing_repo == new_repo:
                logger.warning(f"Duplicate repo {new_repo} - updating existing entry")
                # Update existing entry instead of adding duplicate
                existing.update(package_config)
                self.save_config()
                self.plugins = []
                self._init_plugins()
                return
            
            if existing_id == new_id:
                logger.warning(f"Duplicate ID {new_id} - updating existing entry")
                existing.update(package_config)
                self.save_config()
                self.plugins = []
                self._init_plugins()
                return
        
        # Sanitize ID if it looks auto-generated or ugly
        pkg_id = package_config.get("id", "")
        if "." in pkg_id and len(pkg_id) > 30:
            # Auto-generated ID, derive cleaner one from repo or name
            if new_repo:
                package_config["id"] = new_repo.split("/")[-1].lower()
            elif package_config.get("name"):
                package_config["id"] = package_config["name"].lower().replace(" ", "-")
        
        packages.append(package_config)
        self.save_config()
        
        # Reinitialize plugins
        self.plugins = []
        self._init_plugins()
    
    def ignore_package(self, package_id: str) -> None:
        """Add a package to the ignore list."""
        if "ignored" not in self.config:
            self.config["ignored"] = []
        
        if package_id not in self.config["ignored"]:
            self.config["ignored"].append(package_id)
            self.save_config()

    def get_all_tracked_software(self) -> list[SoftwareInfo]:
        """
        Get all tracked software from all plugins.
        
        Returns:
            List of SoftwareInfo from all enabled plugins.
        """
        all_software = []
        for plugin in self.plugins:
            try:
                software = plugin.get_tracked_software()
                all_software.extend(software)
            except Exception as e:
                logger.error(f"Error getting software from {plugin.name}: {e}")
        return all_software

    def check_all_updates(self, parallel: bool = True) -> list[SoftwareInfo]:
        """
        Check for updates across all tracked software.
        
        Args:
            parallel: Whether to check in parallel for speed.
            
        Returns:
            List of SoftwareInfo with updated status.
        """
        all_software = self.get_all_tracked_software()
        
        if not parallel:
            return [self._check_single(s) for s in all_software]
        
        results = []
        with ThreadPoolExecutor(max_workers=4) as executor:
            futures = {
                executor.submit(self._check_single, s): s 
                for s in all_software
            }
            for future in as_completed(futures):
                try:
                    results.append(future.result())
                except Exception as e:
                    software = futures[future]
                    software.status = UpdateStatus.ERROR
                    software.error_message = str(e)
                    results.append(software)
        
        return results

    def _check_single(self, software: SoftwareInfo) -> SoftwareInfo:
        """Check updates for a single software item."""
        plugin = self._get_plugin_for_software(software)
        if plugin:
            return plugin.check_for_updates(software)
        software.status = UpdateStatus.ERROR
        software.error_message = "No plugin found"
        return software

    def _get_plugin_for_software(self, software: SoftwareInfo) -> Optional[UpdateSourcePlugin]:
        """Get the plugin that handles a given software item."""
        for plugin in self.plugins:
            if plugin.source_type == software.source_type:
                return plugin
        return None

    def get_updates_available(self) -> list[SoftwareInfo]:
        """
        Get list of software with available updates.
        
        Returns:
            List of SoftwareInfo where status is UPDATE_AVAILABLE.
        """
        all_software = self.check_all_updates()
        return [s for s in all_software if s.status == UpdateStatus.UPDATE_AVAILABLE]

    def install_update(self, software: SoftwareInfo) -> InstallResult:
        """
        Install an update for the given software.
        
        Args:
            software: The software to update.
            
        Returns:
            InstallResult indicating success or failure.
        """
        plugin = self._get_plugin_for_software(software)
        if not plugin:
            return InstallResult(
                success=False,
                error_message="No plugin found for this software"
            )
        
        result = plugin.update(software)
        
        # Record in history
        try:
            from core.notifications import UpdateHistory
            history = UpdateHistory()
            history.add_record(
                software_id=software.id,
                software_name=software.name,
                source_type=software.source_type,
                old_version=software.installed_version,
                new_version=result.new_version or software.latest_version or "unknown",
                success=result.success,
                error_message=result.error_message,
            )
        except Exception as e:
            logger.warning(f"Could not record update history: {e}")
        
        # If successful, update the installed version in config
        if result.success and software.latest_version:
            self._update_installed_version(software.id, software.source_type, software.latest_version)
        
        return result
    
    def _update_installed_version(self, software_id: str, source_type: str, new_version: str) -> None:
        """Update the installed_version in config for a package."""
        source_key = source_type  # e.g., "github", "web"
        if source_key not in self.config:
            return
        
        packages = self.config[source_key].get("packages", [])
        for pkg in packages:
            if pkg.get("id") == software_id:
                pkg["installed_version"] = new_version
                self.save_config()
                
                # Also persist to VersionStore for apps with hard-to-detect versions
                try:
                    from core.version_store import set_stored_version
                    set_stored_version(software_id, new_version, source="update")
                except Exception as e:
                    logger.warning(f"Could not persist version store for {software_id}: {e}")
                
                logger.info(f"Updated {software_id} installed_version to {new_version}")
                return

    def install_all_updates(self) -> dict[str, InstallResult]:
        """
        Install all available updates.
        
        Returns:
            Dict mapping software ID to InstallResult.
        """
        updates = self.get_updates_available()
        results = {}
        
        for software in updates:
            logger.info(f"Installing update for {software.name}...")
            results[software.id] = self.install_update(software)
        
        return results
