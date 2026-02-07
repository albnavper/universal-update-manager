"""
Universal Update Manager - Core Package
"""

from core.engine import UpdateEngine
from core.scanner import SoftwareScanner, DetectedSoftware

__all__ = ["UpdateEngine", "SoftwareScanner", "DetectedSoftware"]
