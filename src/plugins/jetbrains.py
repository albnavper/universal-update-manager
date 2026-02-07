"""
Universal Update Manager - JetBrains Plugin
Checks for updates to JetBrains IDEs (Android Studio, IntelliJ, etc).
"""

import re
import json
import logging
from typing import Optional
import urllib.request
import urllib.error

from plugins.base import (
    UpdateSourcePlugin,
    SoftwareInfo,
    UpdateStatus,
    DownloadResult,
    InstallResult,
)

logger = logging.getLogger(__name__)


class JetBrainsPlugin(UpdateSourcePlugin):
    """Plugin for JetBrains IDE updates."""
    
    # JetBrains product codes
    PRODUCTS = {
        "android-studio": {"code": "AI", "name": "Android Studio"},
        "idea": {"code": "IIU", "name": "IntelliJ IDEA Ultimate"},
        "idea-community": {"code": "IIC", "name": "IntelliJ IDEA Community"},
        "webstorm": {"code": "WS", "name": "WebStorm"},
        "pycharm": {"code": "PCP", "name": "PyCharm Professional"},
        "pycharm-community": {"code": "PCC", "name": "PyCharm Community"},
    }
    
    API_URL = "https://data.services.jetbrains.com/products/releases"
    
    def __init__(self, config: dict = None):
        """
        Initialize the JetBrains plugin.
        
        Args:
            config: Configuration with 'packages' list.
        """
        self.config = config or {}
        self.packages = self.config.get("packages", [])
        self._cache: dict[str, dict] = {}
    
    @property
    def name(self) -> str:
        return "JetBrains"
    
    @property
    def source_type(self) -> str:
        return "jetbrains"
    
    @property
    def icon(self) -> str:
        return "applications-development"
    
    def _fetch_releases(self, product_code: str) -> Optional[dict]:
        """Fetch release info from JetBrains API."""
        if product_code in self._cache:
            return self._cache[product_code]
        
        try:
            url = f"{self.API_URL}?code={product_code}&latest=true&type=release"
            req = urllib.request.Request(url)
            
            with urllib.request.urlopen(req, timeout=15) as response:
                data = json.loads(response.read().decode('utf-8'))
                self._cache[product_code] = data
                return data
        except (urllib.error.URLError, json.JSONDecodeError, TimeoutError) as e:
            logger.warning(f"Failed to fetch JetBrains releases: {e}")
            return None
    
    def _parse_build_number(self, build_txt: str) -> tuple[str, str]:
        """Parse Android Studio build.txt format."""
        # Format: AI-222.4459.24.2221.9445173
        # Returns (version, build_number)
        match = re.match(r"([A-Z]+)-(\d+)\.(\d+)\.(\d+)", build_txt)
        if match:
            major = match.group(2)
            minor = match.group(3)
            patch = match.group(4)
            return f"{major}.{minor}.{patch}", build_txt
        return build_txt, build_txt
    
    def get_tracked_software(self) -> list[SoftwareInfo]:
        """Get list of configured JetBrains products."""
        return [
            SoftwareInfo(
                id=pkg["id"],
                name=pkg.get("name", self.PRODUCTS.get(pkg["id"], {}).get("name", pkg["id"])),
                installed_version=pkg.get("installed_version", "unknown"),
                latest_version=None,
                source_type=self.source_type,
                source_url="https://www.jetbrains.com/",
                status=UpdateStatus.UNKNOWN,
            )
            for pkg in self.packages
        ]
    
    def check_for_updates(self, software: SoftwareInfo) -> SoftwareInfo:
        """Check for updates from JetBrains."""
        product_info = self.PRODUCTS.get(software.id)
        if not product_info:
            software.status = UpdateStatus.ERROR
            software.error_message = "Unknown JetBrains product"
            return software
        
        releases = self._fetch_releases(product_info["code"])
        if not releases:
            software.status = UpdateStatus.ERROR
            software.error_message = "Failed to fetch releases"
            return software
        
        # Get latest release
        product_releases = releases.get(product_info["code"], [])
        if not product_releases:
            software.status = UpdateStatus.ERROR
            software.error_message = "No releases found"
            return software
        
        latest = product_releases[0]
        software.latest_version = latest.get("version", "unknown")
        
        # For Android Studio, compare build numbers
        if software.id == "android-studio":
            installed_ver, _ = self._parse_build_number(software.installed_version)
            latest_build = latest.get("build", "")
            latest_ver, _ = self._parse_build_number(f"AI-{latest_build}")
            
            if latest_build > software.installed_version.split("-")[-1]:
                software.status = UpdateStatus.UPDATE_AVAILABLE
            else:
                software.status = UpdateStatus.UP_TO_DATE
        else:
            # Simple version comparison
            if software.latest_version != software.installed_version:
                software.status = UpdateStatus.UPDATE_AVAILABLE
            else:
                software.status = UpdateStatus.UP_TO_DATE
        
        return software
    
    def download_update(self, software: SoftwareInfo) -> DownloadResult:
        """JetBrains IDEs should be downloaded from their website."""
        return DownloadResult(
            success=False,
            error_message="Please download from JetBrains Toolbox or website"
        )
    
    def install_update(self, software: SoftwareInfo, download: DownloadResult) -> InstallResult:
        """Installation not supported - use JetBrains Toolbox."""
        return InstallResult(
            success=False,
            error_message="Please use JetBrains Toolbox for updates"
        )
    
    def update(self, software: SoftwareInfo) -> InstallResult:
        """Update not supported - use JetBrains Toolbox."""
        return InstallResult(
            success=False,
            error_message="Please use JetBrains Toolbox or download manually"
        )
