"""
Universal Update Manager - Flatpak Plugin
Handles updates for Flatpak applications.
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


class FlatpakPlugin(UpdateSourcePlugin):
    """Plugin for handling Flatpak application updates."""

    def __init__(self, config: dict = None):
        """
        Initialize the Flatpak plugin.
        
        Args:
            config: Optional configuration dict (currently unused).
        """
        self.config = config or {}

    @property
    def name(self) -> str:
        return "Flatpak"

    @property
    def source_type(self) -> str:
        return "flatpak"

    @property
    def icon(self) -> str:
        return "flatpak"

    def _run_flatpak(self, *args, timeout: int = 30) -> Optional[str]:
        """Run a flatpak command and return stdout."""
        try:
            result = subprocess.run(
                ["flatpak"] + list(args),
                capture_output=True,
                text=True,
                timeout=timeout,
            )
            if result.returncode == 0:
                return result.stdout
        except (subprocess.TimeoutExpired, FileNotFoundError) as e:
            logger.warning(f"Flatpak command failed: {e}")
        return None

    def _get_installed_apps(self) -> list[dict]:
        """Get list of installed Flatpak applications."""
        output = self._run_flatpak(
            "list", "--app", "--columns=application,version,name"
        )
        
        if not output:
            return []
        
        apps = []
        for line in output.strip().split("\n"):
            if not line:
                continue
            parts = line.split("\t")
            if len(parts) >= 2:
                apps.append({
                    "id": parts[0],
                    "version": parts[1] if len(parts) > 1 else "",
                    "name": parts[2] if len(parts) > 2 else parts[0].split(".")[-1],
                })
        
        return apps

    def _check_updates_available(self) -> dict[str, str]:
        """Check which flatpaks have updates available."""
        output = self._run_flatpak(
            "remote-ls", "--updates", "--columns=application,version",
            timeout=15  # Reduced from 60s to prevent UI freeze
        )
        
        updates = {}
        if output:
            for line in output.strip().split("\n"):
                if not line:
                    continue
                parts = line.split("\t")
                if len(parts) >= 2:
                    updates[parts[0]] = parts[1]
        
        return updates

    def _get_app_description(self, app_id: str) -> Optional[str]:
        """Get description for a Flatpak app."""
        output = self._run_flatpak("info", app_id, timeout=5)
        if output:
            for line in output.split("\n"):
                if line.strip().startswith("Description:"):
                    return line.split(":", 1)[1].strip()
        return None

    def get_tracked_software(self) -> list[SoftwareInfo]:
        """Get list of installed Flatpak applications."""
        apps = self._get_installed_apps()
        software_list = []
        
        for app in apps:
            # Get description (may be slow, so we cache it)
            description = self._get_app_description(app["id"])
            
            software_list.append(SoftwareInfo(
                id=app["id"],
                name=app["name"],
                installed_version=app["version"],
                latest_version=None,
                source_type=self.source_type,
                source_url=f"https://flathub.org/apps/{app['id']}",
                icon=app["id"],
                description=description,
                status=UpdateStatus.UNKNOWN,
            ))
        
        return software_list

    def check_for_updates(self, software: SoftwareInfo) -> SoftwareInfo:
        """Check if updates are available for the given Flatpak."""
        updates = self._check_updates_available()
        
        if software.id in updates:
            software.latest_version = updates[software.id]
            software.status = UpdateStatus.UPDATE_AVAILABLE
        else:
            software.latest_version = software.installed_version
            software.status = UpdateStatus.UP_TO_DATE
        
        return software

    def check_all_updates(self) -> list[SoftwareInfo]:
        """
        Efficiently check all Flatpaks for updates in one call.
        
        Returns:
            List of SoftwareInfo for apps with updates available.
        """
        updates = self._check_updates_available()
        apps = self._get_installed_apps()
        
        results = []
        for app in apps:
            if app["id"] in updates:
                results.append(SoftwareInfo(
                    id=app["id"],
                    name=app["name"],
                    installed_version=app["version"],
                    latest_version=updates[app["id"]],
                    source_type=self.source_type,
                    source_url=f"https://flathub.org/apps/{app['id']}",
                    icon=app["id"],
                    status=UpdateStatus.UPDATE_AVAILABLE,
                ))
        
        return results

    def download_update(self, software: SoftwareInfo) -> DownloadResult:
        """
        For Flatpak, download is handled by the install step.
        This returns a dummy success to proceed to installation.
        """
        return DownloadResult(success=True, file_path=None)

    def install_update(self, software: SoftwareInfo, download: DownloadResult) -> InstallResult:
        """Update the Flatpak application."""
        try:
            result = subprocess.run(
                ["flatpak", "update", "-y", software.id],
                capture_output=True,
                text=True,
                timeout=300,  # 5 minutes for large updates
            )
            
            if result.returncode == 0:
                # Get new version
                apps = self._get_installed_apps()
                app = next((a for a in apps if a["id"] == software.id), None)
                new_version = app["version"] if app else software.latest_version
                
                return InstallResult(success=True, new_version=new_version)
            else:
                return InstallResult(
                    success=False,
                    error_message=result.stderr or "Update failed"
                )
                
        except subprocess.TimeoutExpired:
            return InstallResult(
                success=False,
                error_message="Update timed out"
            )
        except FileNotFoundError:
            return InstallResult(
                success=False,
                error_message="Flatpak not found"
            )

    def update_all(self) -> list[InstallResult]:
        """
        Update all Flatpak applications at once.
        
        Returns:
            List of InstallResult for each updated app.
        """
        try:
            result = subprocess.run(
                ["flatpak", "update", "-y"],
                capture_output=True,
                text=True,
                timeout=600,  # 10 minutes
            )
            
            if result.returncode == 0:
                return [InstallResult(success=True, new_version="latest")]
            else:
                return [InstallResult(
                    success=False,
                    error_message=result.stderr or "Update failed"
                )]
                
        except subprocess.TimeoutExpired:
            return [InstallResult(
                success=False,
                error_message="Update timed out"
            )]
    
    def uninstall(self, software: SoftwareInfo) -> UninstallResult:
        """
        Uninstall a Flatpak application.
        
        Args:
            software: The Flatpak to uninstall.
            
        Returns:
            UninstallResult indicating success or failure.
        """
        try:
            result = subprocess.run(
                ["flatpak", "uninstall", "-y", software.id],
                capture_output=True,
                text=True,
                timeout=120,
            )
            
            if result.returncode == 0:
                return UninstallResult(success=True)
            else:
                return UninstallResult(
                    success=False,
                    error_message=result.stderr or "Uninstall failed"
                )
                
        except subprocess.TimeoutExpired:
            return UninstallResult(
                success=False,
                error_message="Uninstall timed out"
            )
        except FileNotFoundError:
            return UninstallResult(
                success=False,
                error_message="Flatpak not found"
            )
