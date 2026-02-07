"""
Universal Update Manager - Software Scanner
Automatically detects software installed outside of APT.
"""

import subprocess
import re
import os
from pathlib import Path
from dataclasses import dataclass, field
from typing import Optional
import logging
import json

logger = logging.getLogger(__name__)


@dataclass
class DetectedSoftware:
    """Represents a detected software installation."""
    id: str
    name: str
    version: str
    install_type: str  # 'dpkg', 'opt', 'appimage', 'flatpak'
    install_path: Optional[str] = None
    executable: Optional[str] = None
    description: Optional[str] = None
    
    # For matching with known sources
    known_source: Optional[str] = None  # 'github', 'web', etc.
    known_config: Optional[dict] = field(default_factory=dict)


class SoftwareScanner:
    """Scans the system for software installed outside of APT."""
    
    # Known software patterns and their update sources
    KNOWN_SOFTWARE = {
        # GitHub-based software
        "antigravity-tools": {
            "source": "github",
            "repo": "lbjlaq/Antigravity-Manager",
            "asset_pattern": r".*_amd64\.deb$",
        },
        "jackett": {
            "source": "github",
            "repo": "Jackett/Jackett",
            "asset_pattern": r"Jackett\.Binaries\.LinuxAMDx64\.tar\.gz$",
        },
        
        # JetBrains software
        "android-studio": {
            "source": "jetbrains",
            "product_code": "AI",
            "channel": "release",
        },
        
        # Web scraping sources
        "devkinsta": {
            "source": "web",
            "url": "https://kinsta.com/devkinsta/",
            "version_pattern": r"Version\s+([\d.]+)",
        },
        "local": {
            "source": "web",
            "url": "https://localwp.com/releases/",
            "version_pattern": r"([\d.]+)",
        },
        "expandrive": {
            "source": "web",
            "url": "https://www.expandrive.com/download/",
            "version_pattern": r"Version\s+([\d.]+)",
        },
        "autofirma": {
            "source": "web",
            "url": "https://firmaelectronica.gob.es/Home/Descargas.html",
            "version_pattern": r"AutoFirma\s+v?([\d.]+)",
        },
        "lampp": {
            "source": "web",
            "url": "https://www.apachefriends.org/download.html",
            "version_pattern": r"XAMPP\s+para\s+Linux\s+([\d.]+)",
        },
    }
    
    def __init__(self, config_path: Optional[Path] = None):
        """Initialize the scanner."""
        self.config_path = config_path
        self.user_config = self._load_user_config()
    
    def _load_user_config(self) -> dict:
        """Load user-configured sources."""
        if self.config_path and self.config_path.exists():
            try:
                with open(self.config_path) as f:
                    return json.load(f)
            except (json.JSONDecodeError, IOError):
                pass
        return {}
    
    def _save_user_config(self):
        """Save user configuration."""
        if self.config_path:
            self.config_path.parent.mkdir(parents=True, exist_ok=True)
            with open(self.config_path, 'w') as f:
                json.dump(self.user_config, f, indent=2)
    
    def scan_all(self, include_dpkg: bool = False) -> list[DetectedSoftware]:
        """Scan all sources and return detected software.
        
        Args:
            include_dpkg: If True, also scan dpkg orphans (slow).
        """
        detected = []
        
        # Helper to merge/deduplicate
        unique_software = {}
        
        def merge(detected_list):
            for s in detected_list:
                if s.id in unique_software:
                    # Merge rules:
                    # 1. Prefer APT (xdg-system with valid package) over anything else
                    existing = unique_software[s.id]
                    if s.install_type == "xdg-system" and s.known_source == "apt":
                         unique_software[s.id] = s
                    # 2. Prefer XDG over /opt (better metadata)
                    elif s.install_type.startswith("xdg-") and existing.install_type == "opt":
                         unique_software[s.id] = s
                    # 3. Otherwise keep existing (first come priority, or specific logic)
                else:
                    unique_software[s.id] = s

        # Scan XDG applications (.desktop files) - High quality metadata
        # Scan these FIRST so they populate the map
        merge(self._scan_xdg_applications())

        # Scan /opt directory (fast)
        # Will only add if not already found via XDG
        merge(self._scan_opt_directory())
        
        # Scan for AppImages (fast)
        merge(self._scan_appimages())
        
        detected = list(unique_software.values())
        
        # Match with known sources
        
        # Match with known sources
        for software in detected:
            self._match_known_source(software)
        
        return detected
    
    def _scan_dpkg_orphans(self) -> list[DetectedSoftware]:
        """Find dpkg packages not from APT repositories."""
        detected = []
        
        try:
            # Get list of installed packages
            result = subprocess.run(
                ["dpkg-query", "-W", "-f=${Package}\\t${Version}\\n"],
                capture_output=True, text=True, timeout=30
            )
            
            if result.returncode != 0:
                return detected
            
            packages = []
            for line in result.stdout.strip().split("\n"):
                if "\t" in line:
                    pkg, ver = line.split("\t", 1)
                    packages.append((pkg, ver))
            
            # Check each package's APT status
            for pkg, ver in packages:
                if self._is_orphan_package(pkg):
                    detected.append(DetectedSoftware(
                        id=pkg,
                        name=self._prettify_name(pkg),
                        version=ver,
                        install_type="dpkg",
                    ))
        
        except (subprocess.TimeoutExpired, FileNotFoundError) as e:
            logger.warning(f"Failed to scan dpkg: {e}")
        
        return detected
    
    def _is_orphan_package(self, package: str) -> bool:
        """Check if a package is installed but not from any APT repo."""
        try:
            result = subprocess.run(
                ["apt-cache", "policy", package],
                capture_output=True, text=True, timeout=5
            )
            
            # If package has 500 priority from http source, it's from a repo
            if "500 http" in result.stdout or "500 https" in result.stdout:
                return False
            
            # If only 100 (local status), it's an orphan
            return "100 /var/lib/dpkg/status" in result.stdout
            
        except (subprocess.TimeoutExpired, FileNotFoundError):
            return False
    
    def _scan_opt_directory(self) -> list[DetectedSoftware]:
        """Scan /opt for installed applications."""
        detected = []
        opt_path = Path("/opt")
        
        if not opt_path.exists():
            return detected
        
        # Known patterns to detect version
        version_files = [
            "version.txt",
            "VERSION",
            "package.json",
            "product.json",
            "build.txt",
        ]
        
        for entry in opt_path.iterdir():
            if not entry.is_dir():
                continue
            
            # Skip system directories
            if entry.name in ("containerd", "google"):
                continue
            
            software_id = entry.name.lower().replace(" ", "-")
            version = self._detect_opt_version(entry, version_files)
            
            detected.append(DetectedSoftware(
                id=software_id,
                name=self._prettify_name(entry.name),
                version=version or "unknown",
                install_type="opt",
                install_path=str(entry),
            ))
        
        return detected
    
    def _detect_opt_version(self, path: Path, version_files: list[str]) -> Optional[str]:
        """Try to detect version from common version files."""
        for vf in version_files:
            vf_path = path / vf
            if not vf_path.exists():
                # Also check in resources/app for Electron apps
                vf_path = path / "resources" / "app" / vf
            
            if vf_path.exists():
                try:
                    content = vf_path.read_text()
                    
                    if vf.endswith(".json"):
                        data = json.loads(content)
                        return data.get("version") or data.get("ideVersion")
                    else:
                        # Just return first line for txt files
                        return content.strip().split("\n")[0]
                except:
                    pass
        
        return None
    
    def _scan_appimages(self) -> list[DetectedSoftware]:
        """Scan for AppImage files."""
        detected = []
        
        search_paths = [
            Path.home() / "Applications",
            Path.home() / ".local" / "bin",
            Path.home() / "AppImages",
        ]
        
        for search_path in search_paths:
            if not search_path.exists():
                continue
            
            for appimage in search_path.glob("*.AppImage"):
                name = appimage.stem
                # Try to extract version from filename
                version_match = re.search(r"[-_](\d+(?:\.\d+)+)", name)
                version = version_match.group(1) if version_match else "unknown"
                
                detected.append(DetectedSoftware(
                    id=name.lower().replace(" ", "-"),
                    name=self._prettify_name(name.split("-")[0]),
                    version=version,
                    install_type="appimage",
                    install_path=str(appimage),
                    executable=str(appimage),
                ))
        
        return detected

    def _scan_xdg_applications(self) -> list[DetectedSoftware]:
        """
        Scan standard XDG application directories for .desktop files.
        Resolves system packages via dpkg to get version and description.
        Optimized to use batched dpkg calls.
        """
        detected = []
        import configparser
        
        # Directories to scan (priority order: user > system)
        xdg_dirs = [
            Path.home() / ".local" / "share" / "applications",
            Path("/usr/share/applications"),
        ]

        # 1. Collect all desktop files first
        desktop_files = []
        seen_ids = set()
        
        for d in xdg_dirs:
            if not d.exists():
                continue
            for f in d.glob("*.desktop"):
                app_id = f.stem
                if app_id not in seen_ids:
                    desktop_files.append(f)
                    seen_ids.add(app_id)
        
        # 2. Batch resolve via dpkg -S
        # Map: file_path -> (package, version, description)
        pkg_map = {}
        
        try:
            # We can only check files that exist and are absolute paths
            paths_to_check = [str(f.absolute()) for f in desktop_files]
            
            # dpkg -S accepts multiple arguments. 
            # Output format: "package: /path/to/file"
            # It might fail if too many args, so verify chunking if needed. 
            # Linux command line length limit is usually huge (2MB), 
            # 200 files * 100 chars = 20KB, so safe to batch all.
            if paths_to_check:
                cmd = ["dpkg", "-S"] + paths_to_check
                res = subprocess.run(cmd, capture_output=True, text=True)
                # Ignore duplicate/not found errors, just parse stdout
                
                # Map: path -> package_name
                path_to_pkg = {}
                detected_packages = set()
                
                for line in res.stdout.splitlines():
                    if ": " in line:
                        pkg_str, path_str = line.split(": ", 1)
                        # Handle cases with multiple packages "pkg1, pkg2: path"
                        pkg = pkg_str.split(",")[0].strip() 
                        path_to_pkg[path_str.strip()] = pkg
                        detected_packages.add(pkg)
                
                # 3. Batch resolve package info via dpkg-query
                # Map: package -> (version, description)
                pkg_info = {}
                if detected_packages:
                    cmd_query = ["dpkg-query", "-W", "-f=${Package}|${Version}|${Description}\\n"] + list(detected_packages)
                    res_query = subprocess.run(cmd_query, capture_output=True, text=True)
                    
                    for line in res_query.stdout.splitlines():
                        if "|" in line:
                            parts = line.split("|", 2)
                            if len(parts) >= 2:
                                p_name = parts[0]
                                p_ver = parts[1]
                                p_desc = parts[2].split("\\n")[0] if len(parts) > 2 else ""
                                pkg_info[p_name] = (p_ver, p_desc)
                
                # 4. Fill pkg_map
                for path, pkg in path_to_pkg.items():
                    if pkg in pkg_info:
                        pkg_map[path] = (pkg, pkg_info[pkg][0], pkg_info[pkg][1])
                        
        except Exception as e:
            logger.debug(f"Batch dpkg resolution failed: {e}")

        # 5. Process files with updated info
        for desktop_file in desktop_files:
            try:
                config = configparser.ConfigParser(interpolation=None)
                config.read(desktop_file)
                
                if "Desktop Entry" not in config:
                    continue
                
                entry = config["Desktop Entry"]
                
                if entry.getboolean("NoDisplay", fallback=False):
                    continue
                
                if entry.get("Type") != "Application":
                    continue
                
                app_id = desktop_file.stem
                name = entry.get("Name", app_id)
                exec_cmd = entry.get("Exec", "").split()[0] if entry.get("Exec") else None
                
                if exec_cmd and "flatpak" in exec_cmd:
                    continue
                    
                # Look up in our batch-resolved map
                pkg_name, pkg_ver, pkg_desc = pkg_map.get(str(desktop_file.absolute()), (None, None, None))
                
                version = pkg_ver or entry.get("X-Version") or entry.get("Version") or "unknown"
                description = pkg_desc or entry.get("Comment")
                
                install_type = "xdg-local"
                if "/usr/share" in str(desktop_file):
                    install_type = "xdg-system"
                elif ".local" in str(desktop_file):
                    install_type = "xdg-local"
                
                # If resolved to a package, verify it's system
                if pkg_name:
                    install_type = "xdg-system"

                detected.append(DetectedSoftware(
                    id=pkg_name if pkg_name else app_id,
                    name=name,
                    version=version,
                    install_type=install_type,
                    install_path=str(desktop_file),
                    executable=exec_cmd,
                    description=description,
                    known_source="apt" if pkg_name else None
                ))

            except Exception as e:
                logger.debug(f"Failed to parse {desktop_file}: {e}")
        
        return detected
    
    def _match_known_source(self, software: DetectedSoftware) -> None:
        """Match detected software with known update sources."""
        # Check user config first
        user_sources = self.user_config.get("custom_sources", {})
        if software.id in user_sources:
            software.known_source = user_sources[software.id].get("source")
            software.known_config = user_sources[software.id]
            return
        
        # Check built-in known sources
        if software.id in self.KNOWN_SOFTWARE:
            config = self.KNOWN_SOFTWARE[software.id]
            software.known_source = config.get("source")
            software.known_config = config
            return
        
        # Try auto-matching with GitHub database
        try:
            from core.github_db import find_matching_github_app
            
            # Get desktop file name from install path or id
            desktop_name = None
            if software.install_path and ".desktop" in str(software.install_path):
                desktop_name = Path(software.install_path).name
            
            matches = find_matching_github_app(
                desktop_file_name=desktop_name,
                executable_name=software.executable,
                app_name=software.name,
            )
            
            if matches:
                # Use the best match (highest score)
                best_match = matches[0]
                software.known_source = "github"
                software.known_config = {
                    "source": "github",
                    "repo": best_match.repo,
                    "asset_pattern": best_match.asset_pattern,
                    "install_type": best_match.install_type,
                    "auto_matched": True,
                    "match_name": best_match.name,
                }
                logger.debug(f"Auto-matched {software.name} to GitHub: {best_match.repo}")
        except ImportError:
            pass
    
    def _prettify_name(self, name: str) -> str:
        """Convert package/folder name to display name."""
        # Remove common suffixes
        name = re.sub(r"[-_](amd64|x64|linux|bin)$", "", name, flags=re.I)
        # Convert separators to spaces and capitalize
        name = re.sub(r"[-_]", " ", name)
        return name.title()
    
    def add_custom_source(self, software_id: str, source_config: dict) -> None:
        """Add a user-configured source for software."""
        if "custom_sources" not in self.user_config:
            self.user_config["custom_sources"] = {}
        
        self.user_config["custom_sources"][software_id] = source_config
        self._save_user_config()
    
    def ignore_software(self, software_id: str) -> None:
        """Mark software as ignored (no update checks)."""
        if "ignored" not in self.user_config:
            self.user_config["ignored"] = []
        
        if software_id not in self.user_config["ignored"]:
            self.user_config["ignored"].append(software_id)
            self._save_user_config()
    
    def is_ignored(self, software_id: str) -> bool:
        """Check if software is in the ignore list."""
        return software_id in self.user_config.get("ignored", [])
