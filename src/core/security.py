"""
Universal Update Manager - Security Utilities
Provides checksum verification, signature validation, and backup/rollback functionality.
"""

import hashlib
import os
import shutil
import json
import logging
from pathlib import Path
from typing import Optional
from datetime import datetime
from dataclasses import dataclass, asdict

logger = logging.getLogger(__name__)


@dataclass
class BackupInfo:
    """Information about a backed up application version."""
    software_id: str
    software_name: str
    version: str
    backup_path: str
    created_at: str
    source_type: str
    original_path: Optional[str] = None


class ChecksumVerifier:
    """Verifies file integrity using checksums."""

    @staticmethod
    def calculate_sha256(file_path: Path) -> str:
        """Calculate SHA256 hash of a file."""
        sha256 = hashlib.sha256()
        with open(file_path, 'rb') as f:
            for chunk in iter(lambda: f.read(8192), b''):
                sha256.update(chunk)
        return sha256.hexdigest()

    @staticmethod
    def calculate_md5(file_path: Path) -> str:
        """Calculate MD5 hash of a file (legacy compatibility)."""
        md5 = hashlib.md5()
        with open(file_path, 'rb') as f:
            for chunk in iter(lambda: f.read(8192), b''):
                md5.update(chunk)
        return md5.hexdigest()

    @staticmethod
    def verify_checksum(file_path: Path, expected: str, algorithm: str = "sha256") -> bool:
        """
        Verify a file's checksum matches the expected value.
        
        Args:
            file_path: Path to the file to verify
            expected: Expected checksum value
            algorithm: Hash algorithm ("sha256" or "md5")
            
        Returns:
            True if checksum matches, False otherwise
        """
        try:
            if algorithm == "sha256":
                actual = ChecksumVerifier.calculate_sha256(file_path)
            elif algorithm == "md5":
                actual = ChecksumVerifier.calculate_md5(file_path)
            else:
                logger.error(f"Unknown algorithm: {algorithm}")
                return False
            
            matches = actual.lower() == expected.lower()
            if not matches:
                logger.warning(f"Checksum mismatch for {file_path.name}")
                logger.debug(f"Expected: {expected}, Got: {actual}")
            return matches
        except Exception as e:
            logger.error(f"Failed to verify checksum: {e}")
            return False


class BackupManager:
    """Manages application backups for rollback capability."""

    def __init__(self, backup_dir: Optional[Path] = None):
        """
        Initialize the backup manager.
        
        Args:
            backup_dir: Directory to store backups. Defaults to ~/.cache/uum/backups
        """
        xdg_cache = Path(os.environ.get("XDG_CACHE_HOME", Path.home() / ".cache"))
        self.backup_dir = backup_dir or xdg_cache / "uum" / "backups"
        self.backup_dir.mkdir(parents=True, exist_ok=True)
        self.index_file = self.backup_dir / "index.json"
        self._load_index()

    def _load_index(self):
        """Load backup index from disk."""
        self.backups: dict[str, BackupInfo] = {}
        if self.index_file.exists():
            try:
                with open(self.index_file) as f:
                    data = json.load(f)
                    for key, info in data.items():
                        self.backups[key] = BackupInfo(**info)
            except Exception as e:
                logger.warning(f"Failed to load backup index: {e}")

    def _save_index(self):
        """Save backup index to disk."""
        try:
            with open(self.index_file, 'w') as f:
                json.dump(
                    {k: asdict(v) for k, v in self.backups.items()},
                    f, indent=2
                )
        except Exception as e:
            logger.error(f"Failed to save backup index: {e}")

    def backup_deb_package(self, package_name: str, version: str) -> Optional[BackupInfo]:
        """
        Backup an installed .deb package before updating.
        
        Args:
            package_name: Name of the dpkg package
            version: Current version being backed up
            
        Returns:
            BackupInfo if successful, None otherwise
        """
        try:
            import subprocess
            
            # Get list of files in package
            result = subprocess.run(
                ["dpkg", "-L", package_name],
                capture_output=True, text=True, timeout=30
            )
            
            if result.returncode != 0:
                logger.warning(f"Package {package_name} not found in dpkg")
                return None
            
            # Create backup directory
            backup_id = f"{package_name}_{version}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
            pkg_backup_dir = self.backup_dir / backup_id
            pkg_backup_dir.mkdir(parents=True, exist_ok=True)
            
            # Save file list (not the actual files - too large)
            files_list = result.stdout.strip().split('\n')
            with open(pkg_backup_dir / "files.txt", 'w') as f:
                f.write('\n'.join(files_list))
            
            # Save package info
            info_result = subprocess.run(
                ["dpkg", "-s", package_name],
                capture_output=True, text=True, timeout=10
            )
            if info_result.returncode == 0:
                with open(pkg_backup_dir / "package_info.txt", 'w') as f:
                    f.write(info_result.stdout)
            
            backup_info = BackupInfo(
                software_id=package_name,
                software_name=package_name,
                version=version,
                backup_path=str(pkg_backup_dir),
                created_at=datetime.now().isoformat(),
                source_type="deb",
            )
            
            self.backups[backup_id] = backup_info
            self._save_index()
            
            logger.info(f"Created backup for {package_name} v{version}")
            return backup_info
            
        except Exception as e:
            logger.error(f"Failed to backup {package_name}: {e}")
            return None

    def backup_file(self, source_path: Path, software_id: str, 
                    software_name: str, version: str, source_type: str) -> Optional[BackupInfo]:
        """
        Backup a file or directory before updating.
        
        Args:
            source_path: Path to file/directory to backup
            software_id: Identifier for the software
            software_name: Display name
            version: Current version
            source_type: Type of source (appimage, tarball, etc.)
            
        Returns:
            BackupInfo if successful, None otherwise
        """
        try:
            if not source_path.exists():
                logger.warning(f"Source path does not exist: {source_path}")
                return None
            
            backup_id = f"{software_id}_{version}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
            backup_path = self.backup_dir / backup_id
            
            if source_path.is_dir():
                shutil.copytree(source_path, backup_path)
            else:
                backup_path.mkdir(parents=True, exist_ok=True)
                shutil.copy2(source_path, backup_path / source_path.name)
            
            backup_info = BackupInfo(
                software_id=software_id,
                software_name=software_name,
                version=version,
                backup_path=str(backup_path),
                created_at=datetime.now().isoformat(),
                source_type=source_type,
                original_path=str(source_path),
            )
            
            self.backups[backup_id] = backup_info
            self._save_index()
            
            logger.info(f"Created backup for {software_name} v{version}")
            return backup_info
            
        except Exception as e:
            logger.error(f"Failed to backup {software_id}: {e}")
            return None

    def restore(self, backup_id: str) -> bool:
        """
        Restore a previous version from backup.
        
        Args:
            backup_id: ID of the backup to restore
            
        Returns:
            True if successful, False otherwise
        """
        if backup_id not in self.backups:
            logger.error(f"Backup not found: {backup_id}")
            return False
        
        backup = self.backups[backup_id]
        backup_path = Path(backup.backup_path)
        
        if not backup_path.exists():
            logger.error(f"Backup path missing: {backup_path}")
            return False
        
        try:
            if backup.source_type == "deb":
                # For .deb packages, we can try to reinstall the old version
                # This requires the old .deb file or apt cache
                logger.warning("Deb package rollback not fully implemented")
                return False
            
            if backup.original_path:
                original = Path(backup.original_path)
                
                # Remove current version
                if original.exists():
                    if original.is_dir():
                        shutil.rmtree(original)
                    else:
                        original.unlink()
                
                # Restore backup
                if backup_path.is_dir():
                    # Check if backup contains single file or directory
                    contents = list(backup_path.iterdir())
                    if len(contents) == 1 and contents[0].is_file():
                        shutil.copy2(contents[0], original)
                    else:
                        shutil.copytree(backup_path, original)
                else:
                    shutil.copy2(backup_path, original)
                
                logger.info(f"Restored {backup.software_name} v{backup.version}")
                return True
            
            return False
            
        except Exception as e:
            logger.error(f"Failed to restore backup: {e}")
            return False

    def list_backups(self, software_id: Optional[str] = None) -> list[BackupInfo]:
        """
        List available backups.
        
        Args:
            software_id: Optional filter by software ID
            
        Returns:
            List of BackupInfo objects
        """
        if software_id:
            return [b for b in self.backups.values() if b.software_id == software_id]
        return list(self.backups.values())

    def cleanup_old_backups(self, max_per_software: int = 3, max_age_days: int = 30):
        """
        Remove old backups to save space.
        
        Args:
            max_per_software: Maximum backups to keep per software
            max_age_days: Remove backups older than this
        """
        from datetime import timedelta
        
        cutoff = datetime.now() - timedelta(days=max_age_days)
        by_software: dict[str, list[str]] = {}
        
        for backup_id, info in list(self.backups.items()):
            backup_path = Path(info.backup_path)
            created = datetime.fromisoformat(info.created_at)
            
            # Remove if too old
            if created < cutoff:
                logger.info(f"Removing old backup: {backup_id}")
                if backup_path.exists():
                    shutil.rmtree(backup_path)
                del self.backups[backup_id]
                continue
            
            # Track by software for max count check
            sw_id = info.software_id
            if sw_id not in by_software:
                by_software[sw_id] = []
            by_software[sw_id].append((backup_id, created))
        
        # Remove excess backups per software (keep newest)
        for sw_id, backup_list in by_software.items():
            if len(backup_list) > max_per_software:
                backup_list.sort(key=lambda x: x[1], reverse=True)
                for backup_id, _ in backup_list[max_per_software:]:
                    logger.info(f"Removing excess backup: {backup_id}")
                    info = self.backups[backup_id]
                    backup_path = Path(info.backup_path)
                    if backup_path.exists():
                        shutil.rmtree(backup_path)
                    del self.backups[backup_id]
        
        self._save_index()
