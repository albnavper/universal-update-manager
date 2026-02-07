"""
Universal Update Manager - APT Plugin
Handles updates for native Debian/Ubuntu packages via APT.
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


class APTPlugin(UpdateSourcePlugin):
    """Plugin for handling native APT package updates."""

    def __init__(self, config: dict = None):
        """
        Initialize the APT plugin.
        
        Args:
            config: Optional configuration dict with 'packages' list.
                   If empty, will track all upgradable packages.
        """
        self.config = config or {}
        self.packages = self.config.get("packages", [])
        self._upgradable_cache: dict[str, str] = {}
        self._last_error: str = ""

    @property
    def name(self) -> str:
        return "APT"

    @property
    def source_type(self) -> str:
        return "apt"

    @property
    def icon(self) -> str:
        return "package-x-generic"

    def _run_apt(self, *args, use_sudo: bool = False, timeout: int = 60) -> Optional[str]:
        """Run an apt command and return stdout."""
        cmd = ["pkexec", "apt"] if use_sudo else ["apt"]
        try:
            result = subprocess.run(
                cmd + list(args),
                capture_output=True,
                text=True,
                timeout=timeout,
                env={"DEBIAN_FRONTEND": "noninteractive", "LC_ALL": "C"},
            )
            if result.returncode == 0:
                return result.stdout
            else:
                self._last_error = result.stderr
                logger.debug(f"apt {args[0]} stderr: {result.stderr}")
        except FileNotFoundError:
            logger.info("APT not available on this system")
        except subprocess.TimeoutExpired as e:
            logger.warning(f"APT command timed out: {e}")
            self._last_error = "Command timed out"
        return None

    def _is_apt_available(self) -> bool:
        """Check if apt is available on the system."""
        try:
            result = subprocess.run(
                ["which", "apt"],
                capture_output=True,
                timeout=5,
            )
            return result.returncode == 0
        except:
            return False

    def _get_upgradable_packages(self) -> dict[str, tuple[str, str]]:
        """
        Get list of packages that can be upgraded.
        
        Returns:
            Dict mapping package name to (current_version, new_version)
        """
        output = self._run_apt("list", "--upgradable", timeout=30)
        
        upgradable = {}
        if output:
            # Format: package/release version [upgradable from: old_version]
            pattern = r"^(\S+)/\S+\s+(\S+)\s+.*\[upgradable from: (\S+)\]"
            for line in output.strip().split("\n"):
                match = re.match(pattern, line)
                if match:
                    pkg_name = match.group(1)
                    new_version = match.group(2)
                    old_version = match.group(3)
                    upgradable[pkg_name] = (old_version, new_version)
        
        self._upgradable_cache = upgradable
        return upgradable

    def _get_package_info(self, package_name: str) -> Optional[dict]:
        """Get info about an installed package."""
        try:
            result = subprocess.run(
                ["dpkg-query", "-W", "-f=${Version}\t${Status}\t${binary:Summary}", package_name],
                capture_output=True,
                text=True,
                timeout=5,
            )
            if result.returncode == 0:
                parts = result.stdout.strip().split("\t")
                if len(parts) >= 2 and "installed" in parts[1].lower():
                    return {
                        "version": parts[0],
                        "status": parts[1],
                        "description": parts[2] if len(parts) > 2 else "",
                    }
        except Exception as e:
            logger.debug(f"Failed to get info for {package_name}: {e}")
        return None

    def get_tracked_software(self) -> list[SoftwareInfo]:
        """Get list of upgradable APT packages."""
        if not self._is_apt_available():
            return []
        
        # If specific packages configured, track those
        if self.packages:
            result = []
            for pkg in self.packages:
                pkg_id = pkg if isinstance(pkg, str) else pkg.get("id", "")
                info = self._get_package_info(pkg_id)
                if info:
                    result.append(SoftwareInfo(
                        id=pkg_id,
                        name=pkg_id.replace("-", " ").title(),
                        installed_version=info["version"],
                        latest_version=None,
                        source_type=self.source_type,
                        source_url=f"apt://{pkg_id}",
                        icon=self.icon,
                        description=info.get("description", ""),
                        status=UpdateStatus.UNKNOWN,
                    ))
            return result
        
        # Otherwise, return all upgradable packages
        upgradable = self._get_upgradable_packages()
        return [
            SoftwareInfo(
                id=pkg_name,
                name=pkg_name.replace("-", " ").title(),
                installed_version=versions[0],
                latest_version=versions[1],
                source_type=self.source_type,
                source_url=f"apt://{pkg_name}",
                icon=self.icon,
                status=UpdateStatus.UPDATE_AVAILABLE,
            )
            for pkg_name, versions in upgradable.items()
        ]

    def check_for_updates(self, software: SoftwareInfo) -> SoftwareInfo:
        """Check if updates are available for the given package."""
        # Refresh cache if empty
        if not self._upgradable_cache:
            self._get_upgradable_packages()
        
        if software.id in self._upgradable_cache:
            _, new_version = self._upgradable_cache[software.id]
            software.latest_version = new_version
            software.status = UpdateStatus.UPDATE_AVAILABLE
        else:
            # Check if package is even installed
            info = self._get_package_info(software.id)
            if info:
                software.installed_version = info["version"]
                software.latest_version = software.installed_version
                software.status = UpdateStatus.UP_TO_DATE
            else:
                software.status = UpdateStatus.ERROR
                software.error_message = "Package not installed"
        
        return software

    def refresh_package_list(self) -> bool:
        """Run apt update to refresh package lists."""
        try:
            result = subprocess.run(
                ["pkexec", "apt", "update"],
                capture_output=True,
                text=True,
                timeout=120,
            )
            if result.returncode == 0:
                # Clear cache so next check gets fresh data
                self._upgradable_cache = {}
                return True
            else:
                self._last_error = result.stderr
                logger.warning(f"apt update failed: {result.stderr}")
        except Exception as e:
            self._last_error = str(e)
            logger.warning(f"apt update failed: {e}")
        return False

    def download_update(self, software: SoftwareInfo) -> DownloadResult:
        """
        For APT, download is handled by the install step.
        """
        return DownloadResult(success=True)

    def install_update(self, software: SoftwareInfo, download: DownloadResult) -> InstallResult:
        """Install/upgrade the APT package."""
        try:
            result = subprocess.run(
                ["pkexec", "apt", "install", "-y", "--only-upgrade", software.id],
                capture_output=True,
                text=True,
                timeout=300,
                env={"DEBIAN_FRONTEND": "noninteractive", "LC_ALL": "C"},
            )
            
            if result.returncode == 0:
                # Get new version
                info = self._get_package_info(software.id)
                new_version = info["version"] if info else software.latest_version
                
                return InstallResult(
                    success=True,
                    new_version=new_version,
                )
            else:
                return InstallResult(
                    success=False,
                    error_message=result.stderr or "Failed to install update"
                )
        except subprocess.TimeoutExpired:
            return InstallResult(
                success=False,
                error_message="Installation timed out"
            )
        except Exception as e:
            return InstallResult(
                success=False,
                error_message=str(e)
            )

    def upgrade_all(self) -> InstallResult:
        """
        Upgrade all APT packages at once.
        
        Returns:
            InstallResult indicating success or failure.
        """
        try:
            result = subprocess.run(
                ["pkexec", "apt", "upgrade", "-y"],
                capture_output=True,
                text=True,
                timeout=600,
                env={"DEBIAN_FRONTEND": "noninteractive", "LC_ALL": "C"},
            )
            
            if result.returncode == 0:
                return InstallResult(success=True, new_version="upgraded")
            else:
                return InstallResult(
                    success=False,
                    error_message=result.stderr or "Failed to upgrade"
                )
        except subprocess.TimeoutExpired:
            return InstallResult(success=False, error_message="Upgrade timed out")

    def uninstall(self, software: SoftwareInfo) -> UninstallResult:
        """
        Uninstall an APT package.
        
        Args:
            software: The package to uninstall.
            
        Returns:
            UninstallResult indicating success or failure.
        """
        try:
            result = subprocess.run(
                ["pkexec", "apt", "remove", "-y", software.id],
                capture_output=True,
                text=True,
                timeout=120,
                env={"DEBIAN_FRONTEND": "noninteractive", "LC_ALL": "C"},
            )
            
            if result.returncode == 0:
                return UninstallResult(success=True)
            else:
                return UninstallResult(
                    success=False,
                    error_message=result.stderr or "Failed to remove package"
                )
        except subprocess.TimeoutExpired:
            return UninstallResult(
                success=False,
                error_message="Remove timed out"
            )
        except Exception as e:
            return UninstallResult(
                success=False,
                error_message=str(e)
            )
