"""
Universal Update Manager - Plugin Base
Abstract base class for all update source plugins.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Optional
import logging

logger = logging.getLogger(__name__)


class UpdateStatus(Enum):
    """Status of an update check."""
    UP_TO_DATE = "up_to_date"
    UPDATE_AVAILABLE = "update_available"
    ERROR = "error"
    UNKNOWN = "unknown"


@dataclass
class SoftwareInfo:
    """Information about a tracked software package."""
    id: str                          # Unique identifier (e.g., "antigravity-tools")
    name: str                        # Display name
    installed_version: str           # Currently installed version
    latest_version: Optional[str]    # Latest available version (None if not checked)
    source_type: str                 # Plugin type (e.g., "github", "flatpak")
    source_url: Optional[str]        # URL for the update source
    icon: Optional[str]              # Path to icon or icon name
    description: Optional[str] = None  # Short description of the software
    status: UpdateStatus = UpdateStatus.UNKNOWN
    error_message: Optional[str] = None

    @property
    def has_update(self) -> bool:
        """Check if an update is available."""
        return self.status == UpdateStatus.UPDATE_AVAILABLE

    @property
    def display_version(self) -> str:
        """Get formatted version string for display."""
        if self.latest_version and self.has_update:
            return f"{self.installed_version} → {self.latest_version}"
        return self.installed_version


@dataclass
class DownloadResult:
    """Result of a download operation."""
    success: bool
    file_path: Optional[Path] = None
    error_message: Optional[str] = None
    download_url: Optional[str] = None  # URL for manual download (used by web scraper)
    checksum: Optional[str] = None  # SHA256 of downloaded file
    checksum_verified: bool = False  # True if checksum was verified against expected


@dataclass
class InstallResult:
    """Result of an installation operation."""
    success: bool
    new_version: Optional[str] = None
    error_message: Optional[str] = None


@dataclass
class UninstallResult:
    """Result of an uninstallation operation."""
    success: bool
    error_message: Optional[str] = None


class UpdateSourcePlugin(ABC):
    """
    Abstract base class for update source plugins.
    
    Each plugin handles a specific type of update source
    (GitHub Releases, Flatpak, AppImage, web scraping, etc.)
    """

    @property
    @abstractmethod
    def name(self) -> str:
        """Human-readable name of the plugin (e.g., 'GitHub Releases')."""
        pass

    @property
    @abstractmethod
    def source_type(self) -> str:
        """Short identifier for the source type (e.g., 'github')."""
        pass

    @property
    def icon(self) -> str:
        """Icon name or path for the plugin."""
        return "application-x-executable"

    @abstractmethod
    def get_tracked_software(self) -> list[SoftwareInfo]:
        """
        Get list of software tracked by this plugin.
        
        Returns:
            List of SoftwareInfo objects for each tracked package.
        """
        pass

    @abstractmethod
    def check_for_updates(self, software: SoftwareInfo) -> SoftwareInfo:
        """
        Check if updates are available for the given software.
        
        Args:
            software: The software to check for updates.
            
        Returns:
            Updated SoftwareInfo with latest version and status.
        """
        pass

    @abstractmethod
    def download_update(self, software: SoftwareInfo) -> DownloadResult:
        """
        Download the update for the given software.
        
        Args:
            software: The software to download update for.
            
        Returns:
            DownloadResult with file path if successful.
        """
        pass

    @abstractmethod
    def install_update(self, software: SoftwareInfo, download: DownloadResult) -> InstallResult:
        """
        Install the downloaded update.
        
        Args:
            software: The software being updated.
            download: The download result containing the file path.
            
        Returns:
            InstallResult indicating success or failure.
        """
        pass

    def cleanup(self, download: DownloadResult) -> None:
        """
        Clean up downloaded files after installation.
        
        Args:
            download: The download result to clean up.
        """
        if download.file_path and download.file_path.exists():
            try:
                download.file_path.unlink()
                logger.debug(f"Cleaned up: {download.file_path}")
            except OSError as e:
                logger.warning(f"Failed to clean up {download.file_path}: {e}")

    def update(self, software: SoftwareInfo) -> InstallResult:
        """
        Perform full update cycle: download and install.
        
        Args:
            software: The software to update.
            
        Returns:
            InstallResult indicating success or failure.
        """
        logger.info(f"Starting update for {software.name}")
        
        # Download
        download = self.download_update(software)
        if not download.success:
            return InstallResult(
                success=False,
                error_message=f"Download failed: {download.error_message}"
            )
        
        # Install
        try:
            result = self.install_update(software, download)
        finally:
            self.cleanup(download)
        
        if result.success:
            logger.info(f"Successfully updated {software.name} to {result.new_version}")
        else:
            logger.error(f"Failed to update {software.name}: {result.error_message}")
        
        return result
    
    def uninstall(self, software: SoftwareInfo) -> UninstallResult:
        """
        Uninstall the given software.
        
        Args:
            software: The software to uninstall.
            
        Returns:
            UninstallResult indicating success or failure.
        """
        return UninstallResult(
            success=False,
            error_message="Uninstall not supported for this source type"
        )
