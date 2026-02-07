"""
Universal Update Manager - Web Scraper Plugin
Fetches version information from websites via scraping.
"""

import re
import logging
from typing import Optional
import urllib.request
import urllib.error
from html.parser import HTMLParser

from plugins.base import (
    UpdateSourcePlugin,
    SoftwareInfo,
    UpdateStatus,
    DownloadResult,
    InstallResult,
)

logger = logging.getLogger(__name__)


class SimpleHTMLTextExtractor(HTMLParser):
    """Extract text content from HTML."""
    
    def __init__(self):
        super().__init__()
        self.text_parts = []
        self._skip_tags = {'script', 'style', 'noscript'}
        self._in_skip = 0
    
    def handle_starttag(self, tag, attrs):
        if tag in self._skip_tags:
            self._in_skip += 1
    
    def handle_endtag(self, tag):
        if tag in self._skip_tags:
            self._in_skip -= 1
    
    def handle_data(self, data):
        if self._in_skip <= 0:
            self.text_parts.append(data)
    
    def get_text(self) -> str:
        return ' '.join(self.text_parts)


class WebScraperPlugin(UpdateSourcePlugin):
    """Plugin for checking updates via web scraping."""
    
    def __init__(self, config: dict = None):
        """
        Initialize the web scraper plugin.
        
        Args:
            config: Configuration with 'packages' list containing:
                - id: Software identifier
                - name: Display name
                - url: URL to scrape
                - version_pattern: Regex pattern to extract version
                - download_url: Optional direct download URL pattern
        """
        self.config = config or {}
        self.packages = self.config.get("packages", [])
        self._cache: dict[str, str] = {}
    
    @property
    def name(self) -> str:
        return "Web Scraper"
    
    @property
    def source_type(self) -> str:
        return "web"
    
    @property
    def icon(self) -> str:
        return "web-browser"
    
    def _fetch_url(self, url: str, timeout: int = 15) -> Optional[str]:
        """Fetch URL content."""
        try:
            req = urllib.request.Request(
                url,
                headers={
                    'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36'
                }
            )
            with urllib.request.urlopen(req, timeout=timeout) as response:
                return response.read().decode('utf-8', errors='ignore')
        except (urllib.error.URLError, TimeoutError) as e:
            logger.warning(f"Failed to fetch {url}: {e}")
            return None
    
    def _extract_version(self, content: str, pattern: str) -> Optional[str]:
        """Extract version using regex pattern."""
        try:
            match = re.search(pattern, content, re.IGNORECASE)
            if match:
                return match.group(1) if match.groups() else match.group(0)
        except re.error as e:
            logger.error(f"Invalid regex pattern: {e}")
        return None
    
    def _get_text_content(self, html: str) -> str:
        """Extract text from HTML."""
        parser = SimpleHTMLTextExtractor()
        try:
            parser.feed(html)
            return parser.get_text()
        except:
            return html
    
    def get_tracked_software(self) -> list[SoftwareInfo]:
        """Get list of software configured for web scraping."""
        return [
            SoftwareInfo(
                id=pkg["id"],
                name=pkg["name"],
                installed_version=pkg.get("installed_version", "unknown"),
                latest_version=None,
                source_type=self.source_type,
                source_url=pkg["url"],
                status=UpdateStatus.UNKNOWN,
            )
            for pkg in self.packages
        ]
    
    def check_for_updates(self, software: SoftwareInfo) -> SoftwareInfo:
        """Check for updates by scraping the configured URL."""
        # Find config for this software
        pkg_config = next(
            (p for p in self.packages if p["id"] == software.id),
            None
        )
        
        if not pkg_config:
            software.status = UpdateStatus.ERROR
            software.error_message = "No configuration found"
            return software
        
        url = pkg_config["url"]
        pattern = pkg_config.get("version_pattern", r"(\d+\.\d+(?:\.\d+)*)")
        
        # Check cache first
        if url in self._cache:
            content = self._cache[url]
        else:
            content = self._fetch_url(url)
            if content:
                self._cache[url] = content
        
        if not content:
            software.status = UpdateStatus.ERROR
            software.error_message = "Failed to fetch URL"
            return software
        
        # Try to extract version
        # First try on raw HTML, then on text content
        version = self._extract_version(content, pattern)
        if not version:
            text_content = self._get_text_content(content)
            version = self._extract_version(text_content, pattern)
        
        if not version:
            software.status = UpdateStatus.ERROR
            software.error_message = "Could not extract version"
            return software
        
        software.latest_version = version
        
        # Compare versions
        if self._version_compare(version, software.installed_version) > 0:
            software.status = UpdateStatus.UPDATE_AVAILABLE
        else:
            software.status = UpdateStatus.UP_TO_DATE
        
        return software
    
    def _version_compare(self, v1: str, v2: str) -> int:
        """Compare two version strings using shared utility."""
        from core.version import compare_versions
        return compare_versions(v1, v2)
    
    def download_update(self, software: SoftwareInfo) -> DownloadResult:
        """
        Download is not directly supported for web scraping.
        Returns info about where to download manually.
        """
        pkg_config = next(
            (p for p in self.packages if p["id"] == software.id),
            None
        )
        
        if pkg_config and "download_url" in pkg_config:
            return DownloadResult(
                success=True,
                file_path=None,
                download_url=pkg_config["download_url"]
            )
        
        return DownloadResult(
            success=False,
            error_message="Manual download required from: " + software.source_url
        )
    
    def install_update(self, software: SoftwareInfo, download: DownloadResult) -> InstallResult:
        """
        Installation not supported for web-scraped software.
        User must install manually.
        """
        return InstallResult(
            success=False,
            error_message="Manual installation required. Please download from the website."
        )
    
    def update(self, software: SoftwareInfo) -> InstallResult:
        """Update is manual for web-scraped software."""
        return InstallResult(
            success=False,
            error_message=f"Please update manually from: {software.source_url}"
        )


# Pre-configured sources for known software
KNOWN_WEB_SOURCES = [
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
    {
        "id": "expandrive",
        "name": "ExpanDrive",
        "url": "https://www.expandrive.com/download/",
        "version_pattern": r"Version\s+([\d.]+)",
    },
    {
        "id": "autofirma",
        "name": "AutoFirma",
        "url": "https://firmaelectronica.gob.es/Home/Descargas.html",
        "version_pattern": r"AutoFirma\s+v?([\d.]+)",
    },
]
