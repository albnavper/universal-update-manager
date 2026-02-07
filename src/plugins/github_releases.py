"""
Universal Update Manager - GitHub Releases Plugin
Handles updates from GitHub repository releases.
"""

import json
import re
import subprocess
import tempfile
from pathlib import Path
from typing import Optional
import logging
import urllib.request
import urllib.error

from .base import (
    UpdateSourcePlugin,
    SoftwareInfo,
    UpdateStatus,
    DownloadResult,
    InstallResult,
)

logger = logging.getLogger(__name__)


class GitHubReleasesPlugin(UpdateSourcePlugin):
    """Plugin for handling GitHub Releases as update source."""

    GITHUB_API = "https://api.github.com/repos/{owner}/{repo}/releases/latest"

    def __init__(self, config: dict):
        """
        Initialize the GitHub Releases plugin.
        
        Args:
            config: Configuration dict with 'packages' list, each containing:
                - id: Package name (dpkg package name)
                - repo: GitHub repo in "owner/repo" format
                - asset_pattern: Regex pattern to match the .deb asset
                - name: (optional) Display name
        """
        self.config = config
        self.packages = config.get("packages", [])
        self._last_error: str = ""  # Track last API error for UI feedback

    @property
    def name(self) -> str:
        return "GitHub Releases"

    @property
    def source_type(self) -> str:
        return "github"

    @property
    def icon(self) -> str:
        return "github"

    def _get_installed_version(self, package_id: str) -> Optional[str]:
        """Get the installed version of a package via dpkg."""
        try:
            result = subprocess.run(
                ["dpkg-query", "-W", "-f=${Version}", package_id],
                capture_output=True,
                text=True,
                timeout=10,
            )
            if result.returncode == 0:
                return result.stdout.strip()
        except (subprocess.TimeoutExpired, FileNotFoundError) as e:
            logger.warning(f"Failed to get installed version for {package_id}: {e}")
        return None

    def _fetch_latest_release(self, repo: str) -> Optional[dict]:
        """Fetch the latest release info from GitHub API."""
        # Sanitize repo string if it contains full URL
        if "github.com/" in repo:
            import re
            match = re.search(r"github\.com/([^/]+/[^/]+)", repo)
            if match:
                repo = match.group(1).rstrip("/")

        owner_repo = repo.split("/")
        if len(owner_repo) < 2:
            logger.error(f"Invalid repo format: {repo}")
            return None
            
        url = self.GITHUB_API.format(owner=owner_repo[0], repo=owner_repo[1])
        try:
            # Use stored token if available to avoid rate limits
            headers = {"User-Agent": "UniversalUpdateManager/1.0"}
            token = self.config.get("token")
            if token:
                headers["Authorization"] = f"Bearer {token}"
            
            req = urllib.request.Request(url, headers=headers)
            with urllib.request.urlopen(req, timeout=10) as response:
                # Log rate limit info
                remaining = response.headers.get("X-RateLimit-Remaining", "?")
                logger.debug(f"GitHub API rate limit remaining: {remaining}")
                return json.loads(response.read().decode())
        except urllib.error.HTTPError as e:
            if e.code == 403:
                reset_time = e.headers.get("X-RateLimit-Reset", "")
                if reset_time:
                    import time
                    try:
                        reset_in = int(reset_time) - int(time.time())
                        msg = f"Resets in {reset_in//60} min"
                    except:
                        msg = "Try again later"
                    
                    logger.error(f"GitHub API rate limit exceeded. {msg}")
                    self._last_error = f"Rate limit exceeded ({msg})"
                else:
                    logger.error(f"GitHub API rate limit exceeded")
                    self._last_error = "Rate limit exceeded"
            elif e.code == 404:
                logger.error(f"Repository not found: {repo}")
                self._last_error = f"Repository '{repo}' not found"
            else:
                logger.error(f"GitHub API error {e.code}: {e.reason}")
                self._last_error = f"GitHub error: {e.reason}"
        except (urllib.error.URLError, json.JSONDecodeError) as e:
            logger.error(f"Failed to fetch release from {repo}: {e}")
            self._last_error = str(e)
        return None

    def _parse_version(self, tag_name: str) -> str:
        """Parse version from tag name (strips 'v' prefix if present)."""
        return tag_name.lstrip("v")
    
    def _fetch_repo_description(self, repo: str) -> Optional[str]:
        """Fetch the repository description from GitHub API."""
        url = f"https://api.github.com/repos/{repo}"
        try:
            headers = {"User-Agent": "UniversalUpdateManager/1.0"}
            token = self.config.get("token")
            if token:
                headers["Authorization"] = f"Bearer {token}"
                
            req = urllib.request.Request(url, headers=headers)
            with urllib.request.urlopen(req, timeout=10) as response:
                data = json.loads(response.read().decode())
                return data.get("description", "")
        except Exception:
            return None

    def _find_deb_asset(self, release: dict, pattern: str) -> Optional[dict]:
        """Find the .deb asset matching the pattern in release assets."""
        regex = re.compile(pattern)
        for asset in release.get("assets", []):
            if regex.match(asset.get("name", "")):
                return asset
        return None

    def get_tracked_software(self) -> list[SoftwareInfo]:
        """Get list of software tracked by this plugin."""
        software_list = []
        
        for pkg in self.packages:
            # Try dpkg first, then fallback to config's installed_version
            installed = self._get_installed_version(pkg["id"])
            if not installed:
                installed = pkg.get("installed_version")
            
            # Try version_detector for known apps
            if not installed:
                try:
                    from core.version_detector import detect_version
                    installed = detect_version(pkg["id"], pkg.get("name"))
                except ImportError:
                    pass
            
            # Default to 'unknown' if we can't detect version
            # Still show the app so user knows it's tracked
            if not installed:
                installed = "unknown"
            
            # Normalize repo URL to user/repo format
            repo = pkg.get("repo", "")
            if "github.com/" in repo:
                # Extract user/repo from full URL
                import re
                match = re.search(r"github\.com/([^/]+/[^/]+)", repo)
                if match:
                    repo = match.group(1).rstrip("/")
            pkg["repo"] = repo  # Update in place for later use
            
            # Get description from config or will be fetched later
            description = pkg.get("description")
            
            software_list.append(SoftwareInfo(
                id=pkg["id"],
                name=pkg.get("name", pkg["id"]),
                installed_version=installed,
                latest_version=None,
                source_type=self.source_type,
                source_url=f"https://github.com/{repo}/releases",
                icon=pkg.get("icon"),
                description=description,
                    status=UpdateStatus.UNKNOWN,
                ))
        
        return software_list

    def check_for_updates(self, software: SoftwareInfo) -> SoftwareInfo:
        """Check if updates are available for the given software."""
        pkg_config = next(
            (p for p in self.packages if p["id"] == software.id), 
            None
        )
        
        if not pkg_config:
            software.status = UpdateStatus.ERROR
            software.error_message = "Package not found in configuration"
            return software

        release = self._fetch_latest_release(pkg_config["repo"])
        
        if not release:
            software.status = UpdateStatus.ERROR
            software.error_message = "Failed to fetch release info"
            return software

        latest = self._parse_version(release.get("tag_name", ""))
        software.latest_version = latest
        
        # Compare versions
        if self._version_gt(latest, software.installed_version):
            software.status = UpdateStatus.UPDATE_AVAILABLE
        else:
            software.status = UpdateStatus.UP_TO_DATE
        
        return software

    def _version_gt(self, v1: str, v2: str) -> bool:
        """Check if v1 > v2 using shared version comparison."""
        from core.version import is_newer
        return is_newer(v1, v2)

    def download_update(self, software: SoftwareInfo) -> DownloadResult:
        """Download the update for the given software."""
        pkg_config = next(
            (p for p in self.packages if p["id"] == software.id), 
            None
        )
        
        if not pkg_config:
            return DownloadResult(
                success=False,
                error_message="Package not found in configuration"
            )

        release = self._fetch_latest_release(pkg_config["repo"])
        if not release:
            return DownloadResult(
                success=False,
                error_message="Failed to fetch release info"
            )

        asset = self._find_deb_asset(release, pkg_config["asset_pattern"])
        if not asset:
            return DownloadResult(
                success=False,
                error_message="No matching .deb asset found"
            )

        download_url = asset["browser_download_url"]
        
        # Download to temp file
        try:
            tmp_file = Path(tempfile.gettempdir()) / asset["name"]
            logger.info(f"Downloading {download_url} to {tmp_file}")
            
            req = urllib.request.Request(
                download_url,
                headers={"User-Agent": "UniversalUpdateManager/1.0"}
            )
            with urllib.request.urlopen(req, timeout=120) as response:
                with open(tmp_file, "wb") as f:
                    f.write(response.read())
            
            # Calculate checksum for verification
            try:
                from core.security import ChecksumVerifier
                checksum = ChecksumVerifier.calculate_sha256(tmp_file)
                logger.debug(f"Downloaded file SHA256: {checksum}")
            except Exception as e:
                logger.warning(f"Could not calculate checksum: {e}")
                checksum = None
            
            return DownloadResult(success=True, file_path=tmp_file, checksum=checksum)
            
        except (urllib.error.URLError, IOError) as e:
            return DownloadResult(
                success=False,
                error_message=f"Download failed: {e}"
            )

    def install_update(self, software: SoftwareInfo, download: DownloadResult) -> InstallResult:
        """Install the downloaded package (.deb or .tar.gz)."""
        if not download.file_path or not download.file_path.exists():
            return InstallResult(
                success=False,
                error_message="Download file not found"
            )

        filename = download.file_path.name.lower()
        
        if filename.endswith(".deb"):
            return self._install_deb(download.file_path, software)
        elif filename.endswith(".tar.gz") or filename.endswith(".tgz") or filename.endswith(".tar.xz") or filename.endswith(".txz"):
            return self._install_tarball(download.file_path, software)
        elif filename.endswith(".appimage"):
            return self._install_appimage(download.file_path, software)
        else:
            return InstallResult(
                success=False,
                error_message=f"Unsupported file format: {filename}"
            )
    
    def _install_deb(self, file_path: Path, software: SoftwareInfo) -> InstallResult:
        """Install a .deb package using dpkg."""
        try:
            # Create backup before install for rollback
            try:
                from core.security import BackupManager
                backup_mgr = BackupManager()
                backup_mgr.backup_deb_package(software.id, software.installed_version)
            except Exception as e:
                logger.warning(f"Could not create backup: {e}")
            
            result = subprocess.run(
                ["pkexec", "dpkg", "-i", str(file_path)],
                capture_output=True,
                text=True,
                timeout=120,
            )
            
            if result.returncode == 0:
                new_version = self._get_installed_version(software.id)
                return InstallResult(success=True, new_version=new_version)
            else:
                return InstallResult(
                    success=False,
                    error_message=result.stderr or "Installation failed"
                )
                
        except subprocess.TimeoutExpired:
            return InstallResult(success=False, error_message="Installation timed out")
        except FileNotFoundError:
            return InstallResult(success=False, error_message="pkexec not found")
    
    def _install_tarball(self, file_path: Path, software: SoftwareInfo) -> InstallResult:
        """Install a .tar.gz by extracting to /opt."""
        import tarfile
        
        # Determine install directory
        app_name = software.name.replace(" ", "")
        install_dir = Path(f"/opt/{app_name}")
        
        try:
            # Verify it's a valid tarball
            if not tarfile.is_tarfile(file_path):
                return InstallResult(
                    success=False,
                    error_message="Invalid tar.gz file"
                )
            
            # Create temp extraction directory
            import tempfile
            with tempfile.TemporaryDirectory() as temp_dir:
                temp_path = Path(temp_dir)
                
                # Extract tarball
                with tarfile.open(file_path, "r:gz") as tar:
                    tar.extractall(temp_path)
                
                # Find the extracted content (usually a single directory)
                extracted_items = list(temp_path.iterdir())
                if len(extracted_items) == 1 and extracted_items[0].is_dir():
                    source_dir = extracted_items[0]
                else:
                    source_dir = temp_path
                
                # Use pkexec to install to /opt
                # First remove old installation if exists
                result = subprocess.run(
                    ["pkexec", "bash", "-c", 
                     f"rm -rf '{install_dir}' && cp -r '{source_dir}' '{install_dir}' && chmod -R 755 '{install_dir}'"],
                    capture_output=True,
                    text=True,
                    timeout=60,
                )
                
                if result.returncode == 0:
                    # Try to create .desktop file if not exists
                    try:
                        # Common executable names
                        exec_name = None
                        if (install_dir / software.name).exists():
                            exec_name = software.name
                        elif (install_dir / "Telegram").exists(): # Specific for Telegram
                            exec_name = "Telegram"
                        elif (install_dir / software.name.lower()).exists():
                            exec_name = software.name.lower()
                            
                        if exec_name:
                            desktop_file = Path.home() / ".local/share/applications" / f"{software.id}.desktop"
                            desktop_file.parent.mkdir(parents=True, exist_ok=True)
                            
                            with open(desktop_file, "w") as f:
                                f.write(f"""[Desktop Entry]
Type=Application
Name={software.name}
Exec={install_dir}/{exec_name} -- %u
Icon={software.id}
Terminal=false
Categories=Network;InstantMessaging;
StartupWMClass={exec_name}
X-AppImage-Version={software.latest_version}
""")
                            logger.info(f"Created .desktop file at {desktop_file}")
                            
                    except Exception as e:
                        logger.warning(f"Failed to create .desktop file: {e}")

                    return InstallResult(
                        success=True, 
                        new_version=software.latest_version
                    )
                else:
                    return InstallResult(
                        success=False,
                        error_message=result.stderr or "Failed to install to /opt"
                    )
                    
        except tarfile.TarError as e:
            return InstallResult(success=False, error_message=f"Tar extraction failed: {e}")
        except subprocess.TimeoutExpired:
            return InstallResult(success=False, error_message="Installation timed out")
        except Exception as e:
            return InstallResult(success=False, error_message=f"Installation error: {e}")
    
    def _install_appimage(self, file_path: Path, software: SoftwareInfo) -> InstallResult:
        """Install an AppImage to ~/Applications."""
        apps_dir = Path.home() / "Applications"
        apps_dir.mkdir(exist_ok=True)
        
        try:
            dest = apps_dir / f"{software.name.replace(' ', '_')}.AppImage"
            
            # Copy and make executable
            import shutil
            shutil.copy2(file_path, dest)
            dest.chmod(0o755)
            
            return InstallResult(success=True, new_version=software.latest_version)
            
        except Exception as e:
            return InstallResult(success=False, error_message=f"Failed to install AppImage: {e}")
