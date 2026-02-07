"""
Universal Update Manager - Version Detector
Per-app detection methods for installed software versions.
"""

import subprocess
import re
import json
import logging
from pathlib import Path
from typing import Optional, Callable
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class VersionDetector:
    """Detects installed versions for known applications."""
    
    # Registry of detection methods by app ID or name pattern
    _detectors: dict[str, Callable[[], Optional[str]]] = None
    
    def __post_init__(self):
        """Initialize detection methods registry."""
        self._detectors = {
            # Pattern -> detector function
            "telegram": self._detect_telegram,
            "anki": self._detect_anki,
            "xournalpp": self._detect_xournalpp,
            "xournal++": self._detect_xournalpp,
            "brave": self._detect_brave,
            "brave-browser": self._detect_brave,
            "obsidian": self._detect_obsidian,
            "signal": self._detect_signal,
            "bitwarden": self._detect_bitwarden,
            "discord": self._detect_discord,
            "lutris": self._detect_lutris,
            "obs-studio": self._detect_obs,
            "obs": self._detect_obs,
            "flameshot": self._detect_flameshot,
            "vscode": self._detect_vscode,
            "code": self._detect_vscode,
            "joplin": self._detect_joplin,
            "logseq": self._detect_logseq,
            "marktext": self._detect_marktext,
            "localsend": self._detect_localsend,
        }
    
    def detect_version(self, app_id: str, app_name: str = None) -> Optional[str]:
        """
        Detect installed version for an application.
        
        Args:
            app_id: Application ID (e.g., 'telegram', 'anki')
            app_name: Optional display name for fallback matching
            
        Returns:
            Version string or None if not detected
        """
        # Try exact ID match first
        app_id_lower = app_id.lower()
        if app_id_lower in self._detectors:
            try:
                version = self._detectors[app_id_lower]()
                if version:
                    logger.debug(f"Detected {app_id}: {version}")
                    return version
            except Exception as e:
                logger.warning(f"Version detection failed for {app_id}: {e}")
        
        # Try name-based match
        if app_name:
            name_lower = app_name.lower()
            for pattern, detector in self._detectors.items():
                if pattern in name_lower or name_lower in pattern:
                    try:
                        version = detector()
                        if version:
                            logger.debug(f"Detected {app_name} via {pattern}: {version}")
                            return version
                    except Exception:
                        pass
        
        # Fallback: try dpkg-query
        version = self._detect_via_dpkg(app_id)
        if version:
            return version
        
        # Fallback: try which + --version
        version = self._detect_via_cli(app_id)
        if version:
            return version
            
        # Final fallback: check persistent store
        try:
            from core.version_store import get_stored_version
            stored = get_stored_version(app_id)
            if stored:
                logger.debug(f"Using stored version for {app_id}: {stored}")
                return stored
        except ImportError:
            pass
        
        return None
    
    def _run_cmd(self, cmd: list[str], timeout: int = 5) -> Optional[str]:
        """Run command and return stdout."""
        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=timeout,
            )
            if result.returncode == 0:
                return result.stdout.strip()
        except Exception:
            pass
        return None
    
    def _detect_via_dpkg(self, package: str) -> Optional[str]:
        """Try to detect version via dpkg-query."""
        result = self._run_cmd(["dpkg-query", "-W", "-f=${Version}", package])
        if result:
            # Clean up version (remove epoch and revision)
            return re.sub(r"^\d+:", "", result).split("-")[0].split("+")[0]
        return None
    
    def _detect_via_cli(self, app: str) -> Optional[str]:
        """Try to detect version via --version flag."""
        result = self._run_cmd([app, "--version"])
        if result:
            # Extract version number
            match = re.search(r"(\d+\.\d+(?:\.\d+)?)", result)
            if match:
                return match.group(1)
        return None
    
    # ===== App-specific detectors =====
    
    def _detect_telegram(self) -> Optional[str]:
        """Detect Telegram Desktop version."""
        # Method 1: Check Flatpak (most common)
        result = self._run_cmd(
            ["flatpak", "info", "org.telegram.desktop"]
        )
        if result:
            for line in result.split("\n"):
                if "Version:" in line:
                    return line.split(":")[1].strip()
        
        # Method 2: Check /opt/Telegram version via pkexec or config
        telegram_path = Path("/opt/Telegram")
        if telegram_path.exists():
            # Try reading a simpler version indicator if present
            for vfile in ["version", "VERSION", "version.txt"]:
                vpath = telegram_path / vfile
                if vpath.exists():
                    try:
                        return vpath.read_text().strip()
                    except:
                        pass
        
        return None
    
    def _detect_anki(self) -> Optional[str]:
        """Detect Anki version."""
        # Method 1: Check prefs file in Anki2 folder
        prefs_path = Path.home() / ".local/share/Anki2/prefs21.db"
        if prefs_path.exists():
            # prefs21.db is SQLite, try to read version
            result = self._run_cmd([
                "sqlite3", str(prefs_path),
                "SELECT val FROM config WHERE key='lastVersion';"
            ])
            if result:
                return result
        
        # Method 2: Check /opt
        for anki_dir in Path("/opt").glob("anki*"):
            version_file = anki_dir / "version"
            if version_file.exists():
                return version_file.read_text().strip()
            # Try extracting from folder name
            match = re.search(r"anki-?(\d+\.\d+(?:\.\d+)?)", str(anki_dir), re.I)
            if match:
                return match.group(1)
        
        # Method 3: dpkg
        return self._detect_via_dpkg("anki")
    
    def _detect_xournalpp(self) -> Optional[str]:
        """Detect Xournal++ version."""
        # Method 1: CLI --version (works for both installed and AppImage via PATH)
        result = self._run_cmd(["xournalpp", "--version"])
        if result:
            match = re.search(r"(\d+\.\d+\.\d+)", result)
            if match:
                return match.group(1)
        
        # Method 2: dpkg
        version = self._detect_via_dpkg("xournalpp")
        if version:
            return version
        
        # Method 3: AppImage with version in filename
        for appimage_dir in [Path.home() / "Applications", Path.home() / "AppImages"]:
            if appimage_dir.exists():
                for f in appimage_dir.glob("*ournal*AppImage"):
                    match = re.search(r"(\d+\.\d+\.\d+)", f.name)
                    if match:
                        return match.group(1)
        
        # Method 4: Try running AppImage directly with --version
        for appimage_dir in [Path.home() / "Applications", Path.home() / "AppImages"]:
            if appimage_dir.exists():
                for f in appimage_dir.glob("*ournal*AppImage"):
                    result = self._run_cmd([str(f), "--version"], timeout=10)
                    if result:
                        match = re.search(r"(\d+\.\d+\.\d+)", result)
                        if match:
                            return match.group(1)
        
        return None
    

    def _detect_brave(self) -> Optional[str]:
        """Detect Brave Browser version."""
        # Method 1: dpkg (most reliable)
        version = self._detect_via_dpkg("brave-browser")
        if version:
            return version
        
        # Method 2: CLI
        return self._detect_via_cli("brave-browser")
    
    def _detect_obsidian(self) -> Optional[str]:
        """Detect Obsidian version."""
        # Method 1: dpkg
        version = self._detect_via_dpkg("obsidian")
        if version:
            return version
        
        # Method 2: AppImage filename
        for appimage_dir in [Path.home() / "Applications", Path.home() / "AppImages"]:
            if appimage_dir.exists():
                for f in appimage_dir.glob("*bsidian*AppImage"):
                    match = re.search(r"(\d+\.\d+\.\d+)", f.name)
                    if match:
                        return match.group(1)
        
        return None
    
    def _detect_signal(self) -> Optional[str]:
        """Detect Signal Desktop version."""
        return self._detect_via_dpkg("signal-desktop")
    
    def _detect_bitwarden(self) -> Optional[str]:
        """Detect Bitwarden version."""
        version = self._detect_via_dpkg("bitwarden")
        if version:
            return version
        # AppImage
        for f in (Path.home() / "Applications").glob("*itwarden*AppImage"):
            match = re.search(r"(\d+\.\d+\.\d+)", f.name)
            if match:
                return match.group(1)
        return None
    
    def _detect_discord(self) -> Optional[str]:
        """Detect Discord version."""
        version = self._detect_via_dpkg("discord")
        if version:
            return version
        # Check /opt
        discord_path = Path("/opt/Discord/resources/build_info.json")
        if discord_path.exists():
            try:
                data = json.loads(discord_path.read_text())
                return data.get("version")
            except:
                pass
        return None
    
    def _detect_lutris(self) -> Optional[str]:
        """Detect Lutris version."""
        version = self._detect_via_dpkg("lutris")
        if version:
            return version
        return self._detect_via_cli("lutris")
    
    def _detect_obs(self) -> Optional[str]:
        """Detect OBS Studio version."""
        version = self._detect_via_dpkg("obs-studio")
        if version:
            return version
        return self._detect_via_cli("obs")
    
    def _detect_flameshot(self) -> Optional[str]:
        """Detect Flameshot version."""
        version = self._detect_via_dpkg("flameshot")
        if version:
            return version
        return self._detect_via_cli("flameshot")
    
    def _detect_vscode(self) -> Optional[str]:
        """Detect VS Code version."""
        version = self._detect_via_dpkg("code")
        if version:
            return version
        return self._detect_via_cli("code")
    
    def _detect_joplin(self) -> Optional[str]:
        """Detect Joplin version."""
        # AppImage
        for appimage_dir in [Path.home() / "Applications", Path.home() / ".joplin"]:
            if appimage_dir.exists():
                for f in appimage_dir.glob("*oplin*AppImage"):
                    match = re.search(r"(\d+\.\d+\.\d+)", f.name)
                    if match:
                        return match.group(1)
        return None
    
    def _detect_logseq(self) -> Optional[str]:
        """Detect Logseq version."""
        # AppImage
        for f in (Path.home() / "Applications").glob("*ogseq*AppImage"):
            match = re.search(r"(\d+\.\d+\.\d+)", f.name)
            if match:
                return match.group(1)
        return None
    
    def _detect_marktext(self) -> Optional[str]:
        """Detect Mark Text version."""
        version = self._detect_via_dpkg("marktext")
        if version:
            return version
        # AppImage
        for f in (Path.home() / "Applications").glob("*ark*ext*AppImage"):
            match = re.search(r"(\d+\.\d+\.\d+)", f.name)
            if match:
                return match.group(1)
        return None
    
    def _detect_localsend(self) -> Optional[str]:
        """Detect LocalSend version."""
        version = self._detect_via_dpkg("localsend")
        if version:
            return version
        # AppImage
        for f in (Path.home() / "Applications").glob("*ocal*end*AppImage"):
            match = re.search(r"(\d+\.\d+\.\d+)", f.name)
            if match:
                return match.group(1)
        return None


# Singleton instance
_detector = None

def get_detector() -> VersionDetector:
    """Get singleton VersionDetector instance."""
    global _detector
    if _detector is None:
        _detector = VersionDetector()
    return _detector


def detect_version(app_id: str, app_name: str = None) -> Optional[str]:
    """
    Convenience function to detect app version.
    
    Args:
        app_id: Application ID
        app_name: Optional display name
        
    Returns:
        Detected version or None
    """
    return get_detector().detect_version(app_id, app_name)
