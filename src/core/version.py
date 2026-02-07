"""
Universal Update Manager - Version Comparison Utility
Provides consistent version comparison logic across all plugins.
"""

import re
from typing import Tuple, List
import logging

logger = logging.getLogger(__name__)


def normalize_version(version: str) -> List[int]:
    """
    Normalize a version string to a list of integers for comparison.
    
    Handles formats like:
    - 1.2.3
    - v1.2.3
    - 1.2.3-beta
    - 2024.1.3
    - 5.0.0-rc1
    
    Args:
        version: The version string to normalize
        
    Returns:
        List of integers representing version components
    """
    if not version or version.lower() in ("unknown", "none", ""):
        return [0]
    
    # Strip common prefixes
    version = version.lower().strip()
    if version.startswith("v"):
        version = version[1:]
    
    # Extract only numeric parts
    parts = re.findall(r'\d+', version)
    
    return [int(p) for p in parts] if parts else [0]


def compare_versions(v1: str, v2: str) -> int:
    """
    Compare two version strings.
    
    Args:
        v1: First version string
        v2: Second version string
        
    Returns:
        1 if v1 > v2, -1 if v1 < v2, 0 if equal
    """
    try:
        # Try packaging library first (most accurate)
        from packaging.version import Version, InvalidVersion
        try:
            ver1 = Version(v1.lstrip('v'))
            ver2 = Version(v2.lstrip('v'))
            if ver1 > ver2:
                return 1
            elif ver1 < ver2:
                return -1
            return 0
        except InvalidVersion:
            # Fall back to manual parsing
            pass
    except ImportError:
        pass
    
    # Fallback: Manual comparison
    parts1 = normalize_version(v1)
    parts2 = normalize_version(v2)
    
    # Pad shorter list with zeros
    max_len = max(len(parts1), len(parts2))
    parts1.extend([0] * (max_len - len(parts1)))
    parts2.extend([0] * (max_len - len(parts2)))
    
    for a, b in zip(parts1, parts2):
        if a > b:
            return 1
        elif a < b:
            return -1
    
    return 0


def is_newer(new_version: str, current_version: str) -> bool:
    """
    Check if new_version is newer than current_version.
    
    Args:
        new_version: The potentially newer version
        current_version: The current/installed version
        
    Returns:
        True if new_version > current_version
    """
    return compare_versions(new_version, current_version) > 0


def is_older_or_equal(version: str, than: str) -> bool:
    """Check if version is older than or equal to 'than'."""
    return compare_versions(version, than) <= 0
