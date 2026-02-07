"""
Universal Update Manager - Snap Plugin
Handles updates for Snap applications.
"""

import subprocess
import re
from typing import Optional
import logging

from .base import (
    UpdateSourcePlugin,
    SoftwareInfo,
    UpdateStatus,
    DownloadResult,
    InstallResult,
    UninstallResult,
)

logger = logging.getLogger(__name__)


class SnapPlugin(UpdateSourcePlugin):
    """Plugin for handling Snap application updates."""

    def __init__(self, config: dict = None):
        """
        Initialize the Snap plugin.
        
        Args:
            config: Optional configuration dict (currently unused).
        """
        self.config = config or {}
        self._updates_cache: dict[str, str] = {}

    @property
    def name(self) -> str:
        return "Snap"

    @property
    def source_type(self) -> str:
        return "snap"

    @property
    def icon(self) -> str:
        return "snap-symbolic"

    def _run_snap(self, *args, timeout: int = 30) -> Optional[str]:
        """Run a snap command and return stdout."""
        try:
            result = subprocess.run(
                ["snap"] + list(args),
                capture_output=True,
                text=True,
                timeout=timeout,
            )
            if result.returncode == 0:
                return result.stdout
            else:
                logger.debug(f"snap {args[0]} stderr: {result.stderr}")
        except FileNotFoundError:
            logger.info("Snap not installed on this system")
        except subprocess.TimeoutExpired as e:
            logger.warning(f"Snap command timed out: {e}")
        return None

    def _is_snap_available(self) -> bool:
        """Check if snap is installed on the system."""
        try:
            result = subprocess.run(
                ["which", "snap"],
                capture_output=True,
                timeout=5,
            )
            return result.returncode == 0
        except:
            return False

    def _get_installed_apps(self) -> list[dict]:
        """Get list of installed Snap applications."""
        output = self._run_snap("list")
        
        if not output:
            return []
        
        apps = []
        lines = output.strip().split("\n")
        
        # Skip header line
        for line in lines[1:]:
            if not line.strip():
                continue
            # Format: Name  Version  Rev  Tracking  Publisher  Notes
            parts = line.split()
            if len(parts) >= 2:
                name = parts[0]
                version = parts[1]
                
                # Skip core snaps and snapd itself
                if name in ("core", "core18", "core20", "core22", "snapd", "bare", "gnome-3-38-2004"):
                    continue
                
                apps.append({
                    "id": name,
                    "version": version,
                    "name": self._prettify_name(name),
                    "revision": parts[2] if len(parts) > 2 else "",
                    "tracking": parts[3] if len(parts) > 3 else "stable",
                })
        
        return apps

    def _prettify_name(self, name: str) -> str:
        """Convert snap name to display name."""
        return name.replace("-", " ").title()

    def _check_updates_available(self) -> dict[str, str]:
        """Check which snaps have updates available."""
        output = self._run_snap("refresh", "--list", timeout=60)
        
        updates = {}
        if output:
            lines = output.strip().split("\n")
            # Skip header line if present
            for line in lines[1:] if len(lines) > 1 else lines:
                if not line.strip() or "All snaps up to date" in line:
                    continue
                parts = line.split()
                if len(parts) >= 2:
                    updates[parts[0]] = parts[1]
        
        self._updates_cache = updates
        return updates

    def _get_app_description(self, snap_name: str) -> Optional[str]:
        """Get description for a Snap app."""
        output = self._run_snap("info", snap_name, timeout=10)
        if output:
            for line in output.split("\n"):
                if line.startswith("summary:"):
                    return line.split(":", 1)[1].strip()
        return None

    def get_tracked_software(self) -> list[SoftwareInfo]:
        """Get list of installed Snap applications."""
        if not self._is_snap_available():
            return []
        
        apps = self._get_installed_apps()
        return [
            SoftwareInfo(
                id=app["id"],
                name=app["name"],
                installed_version=app["version"],
                latest_version=None,
                source_type=self.source_type,
                source_url=f"https://snapcraft.io/{app['id']}",
                icon=self.icon,
                description=None,  # Lazy load to avoid slowdown
                status=UpdateStatus.UNKNOWN,
            )
            for app in apps
        ]

    def check_for_updates(self, software: SoftwareInfo) -> SoftwareInfo:
        """Check if updates are available for the given Snap."""
        # Use cached updates if available
        if not self._updates_cache:
            self._check_updates_available()
        
        if software.id in self._updates_cache:
            software.latest_version = self._updates_cache[software.id]
            software.status = UpdateStatus.UPDATE_AVAILABLE
        else:
            software.latest_version = software.installed_version
            software.status = UpdateStatus.UP_TO_DATE
        
        return software

    def check_all_updates(self) -> list[SoftwareInfo]:
        """
        Efficiently check all Snaps for updates in one call.
        
        Returns:
            List of SoftwareInfo for apps with updates available.
        """
        updates = self._check_updates_available()
        installed = {app["id"]: app for app in self._get_installed_apps()}
        
        result = []
        for snap_id, new_version in updates.items():
            app = installed.get(snap_id, {"name": snap_id, "version": "unknown"})
            result.append(SoftwareInfo(
                id=snap_id,
                name=app.get("name", snap_id),
                installed_version=app.get("version", "unknown"),
                latest_version=new_version,
                source_type=self.source_type,
                source_url=f"https://snapcraft.io/{snap_id}",
                icon=self.icon,
                status=UpdateStatus.UPDATE_AVAILABLE,
            ))
        
        return result

    def download_update(self, software: SoftwareInfo) -> DownloadResult:
        """
        For Snap, download is handled by the install step.
        This returns a dummy success to proceed to installation.
        """
        return DownloadResult(success=True)

    def install_update(self, software: SoftwareInfo, download: DownloadResult) -> InstallResult:
        """Update the Snap application."""
        try:
            result = subprocess.run(
                ["snap", "refresh", software.id],
                capture_output=True,
                text=True,
                timeout=300,  # 5 minutes for large snaps
            )
            
            if result.returncode == 0:
                # Get new version
                new_version = software.latest_version
                apps = self._get_installed_apps()
                for app in apps:
                    if app["id"] == software.id:
                        new_version = app["version"]
                        break
                
                return InstallResult(
                    success=True,
                    new_version=new_version,
                )
            else:
                return InstallResult(
                    success=False,
                    error_message=result.stderr or "Failed to refresh snap"
                )
        except subprocess.TimeoutExpired:
            return InstallResult(
                success=False,
                error_message="Snap refresh timed out"
            )
        except Exception as e:
            return InstallResult(
                success=False,
                error_message=str(e)
            )

    def update_all(self) -> list[InstallResult]:
        """
        Update all Snap applications at once.
        
        Returns:
            List of InstallResult for each updated app.
        """
        try:
            result = subprocess.run(
                ["snap", "refresh"],
                capture_output=True,
                text=True,
                timeout=600,  # 10 minutes for all snaps
            )
            
            if result.returncode == 0:
                return [InstallResult(success=True, new_version="updated")]
            else:
                return [InstallResult(
                    success=False,
                    error_message=result.stderr or "Failed to refresh all snaps"
                )]
        except subprocess.TimeoutExpired:
            return [InstallResult(success=False, error_message="Snap refresh timed out")]

    def uninstall(self, software: SoftwareInfo) -> UninstallResult:
        """
        Uninstall a Snap application.
        
        Args:
            software: The Snap to uninstall.
            
        Returns:
            UninstallResult indicating success or failure.
        """
        try:
            result = subprocess.run(
                ["snap", "remove", software.id],
                capture_output=True,
                text=True,
                timeout=120,
            )
            
            if result.returncode == 0:
                return UninstallResult(success=True)
            else:
                return UninstallResult(
                    success=False,
                    error_message=result.stderr or "Failed to remove snap"
                )
        except subprocess.TimeoutExpired:
            return UninstallResult(
                success=False,
                error_message="Snap remove timed out"
            )
        except Exception as e:
            return UninstallResult(
                success=False,
                error_message=str(e)
            )
