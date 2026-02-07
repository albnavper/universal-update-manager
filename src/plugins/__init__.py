"""
Universal Update Manager - Plugins Package
"""

from plugins.base import (
    UpdateSourcePlugin,
    SoftwareInfo,
    UpdateStatus,
    DownloadResult,
    InstallResult,
    UninstallResult,
)
from plugins.github_releases import GitHubReleasesPlugin
from plugins.flatpak import FlatpakPlugin
from plugins.snap import SnapPlugin
from plugins.apt import APTPlugin
from plugins.web_scraper import WebScraperPlugin
from plugins.jetbrains import JetBrainsPlugin

__all__ = [
    "UpdateSourcePlugin",
    "SoftwareInfo",
    "UpdateStatus",
    "DownloadResult",
    "InstallResult",
    "UninstallResult",
    "GitHubReleasesPlugin",
    "FlatpakPlugin",
    "SnapPlugin",
    "APTPlugin",
    "WebScraperPlugin",
    "JetBrainsPlugin",
]


