"""
Universal Update Manager - Icon Resolver
Resolves application icons from various sources.
"""

import subprocess
from pathlib import Path
from typing import Optional
import logging

logger = logging.getLogger(__name__)


class IconResolver:
    """Resolves application icons from system and installations."""
    
    # Common icon search paths
    ICON_PATHS = [
        "/usr/share/icons/hicolor",
        "/usr/share/pixmaps",
        "/usr/share/icons",
        Path.home() / ".local/share/icons/hicolor",
        Path.home() / ".local/share/icons",
    ]
    
    # Preferred sizes in order of preference
    PREFERRED_SIZES = ["128x128", "64x64", "48x48", "256x256", "scalable", "32x32"]
    
    # Cache for resolved icons (class-level singleton pattern)
    _cache: dict[str, Optional[str]] = {}
    
    @classmethod
    def clear_cache(cls):
        """Clear the icon resolution cache."""
        cls._cache.clear()
    
    @classmethod
    def resolve(cls, software_id: str, source_type: str, 
                app_id: Optional[str] = None, 
                icon_name: Optional[str] = None) -> str:
        """
        Resolve the icon for a software package.
        
        Args:
            software_id: The software identifier
            source_type: The source type (github, flatpak, etc.)
            app_id: Optional app ID (for Flatpak)
            icon_name: Optional explicit icon name
            
        Returns:
            Icon name or path to use with Gtk.Image
        """
        cache_key = f"{source_type}:{software_id}"
        
        if cache_key in cls._cache:
            return cls._cache[cache_key]
        
        icon = None
        
        if source_type == "flatpak" and app_id:
            icon = cls._resolve_flatpak_icon(app_id)
        elif icon_name:
            icon = cls._resolve_by_name(icon_name)
        
        if not icon:
            icon = cls._resolve_by_name(software_id)
        
        if not icon:
            icon = cls._resolve_from_desktop_file(software_id)
        
        if not icon:
            icon = cls._get_fallback_icon(source_type)
        
        cls._cache[cache_key] = icon
        return icon
    
    @classmethod
    def _resolve_flatpak_icon(cls, app_id: str) -> Optional[str]:
        """Resolve icon for a Flatpak app."""
        # Flatpak apps typically export their icons to the system theme
        # The icon name is usually the app ID
        if cls._icon_exists_in_theme(app_id):
            return app_id
        
        # Try to find in flatpak installation
        flatpak_paths = [
            f"/var/lib/flatpak/app/{app_id}/current/active/export/share/icons",
            f"/var/lib/flatpak/app/{app_id}/current/active/files/share/icons",
            Path.home() / f".local/share/flatpak/app/{app_id}/current/active/export/share/icons",
        ]
        
        for base_path in flatpak_paths:
            if isinstance(base_path, str):
                base_path = Path(base_path)
            
            if not base_path.exists():
                continue
            
            # Look for icon in various sizes
            for size in cls.PREFERRED_SIZES:
                for ext in [".svg", ".png"]:
                    icon_path = base_path / "hicolor" / size / "apps" / f"{app_id}{ext}"
                    if icon_path.exists():
                        return str(icon_path)
        
        return None
    
    @classmethod
    def _resolve_by_name(cls, name: str) -> Optional[str]:
        """Resolve icon by name in system icon directories."""
        # First check if it's already a valid icon name in the theme
        if cls._icon_exists_in_theme(name):
            return name
        
        # Also try with underscores replaced by dashes and vice versa
        alt_name = name.replace("-", "_")
        if cls._icon_exists_in_theme(alt_name):
            return alt_name
        
        alt_name = name.replace("_", "-")
        if cls._icon_exists_in_theme(alt_name):
            return alt_name
        
        # Search in icon paths
        for base_path in cls.ICON_PATHS:
            if isinstance(base_path, str):
                base_path = Path(base_path)
            
            if not base_path.exists():
                continue
            
            for size in cls.PREFERRED_SIZES:
                size_path = base_path / size / "apps"
                if not size_path.exists():
                    continue
                
                for ext in [".svg", ".png"]:
                    for variant in [name, name.replace("-", "_"), name.replace("_", "-")]:
                        icon_path = size_path / f"{variant}{ext}"
                        if icon_path.exists():
                            return str(icon_path)
        
        # Check pixmaps
        for ext in [".png", ".svg", ".xpm"]:
            pixmap_path = Path("/usr/share/pixmaps") / f"{name}{ext}"
            if pixmap_path.exists():
                return str(pixmap_path)
        
        return None
    
    @classmethod
    def _resolve_from_desktop_file(cls, software_id: str) -> Optional[str]:
        """Try to get icon from .desktop file."""
        desktop_paths = [
            Path("/usr/share/applications"),
            Path.home() / ".local/share/applications",
            Path("/var/lib/flatpak/exports/share/applications"),
        ]
        
        for desktop_dir in desktop_paths:
            if not desktop_dir.exists():
                continue
            
            # Try various desktop file name patterns
            for pattern in [f"{software_id}.desktop", 
                           f"{software_id.replace('-', '_')}.desktop",
                           f"*{software_id}*.desktop"]:
                matches = list(desktop_dir.glob(pattern))
                for desktop_file in matches:
                    icon = cls._extract_icon_from_desktop(desktop_file)
                    if icon:
                        return icon
        
        return None
    
    @classmethod
    def _extract_icon_from_desktop(cls, desktop_file: Path) -> Optional[str]:
        """Extract Icon= line from desktop file."""
        try:
            content = desktop_file.read_text()
            for line in content.split("\n"):
                if line.startswith("Icon="):
                    icon_value = line.split("=", 1)[1].strip()
                    # If it's an absolute path, return it
                    if icon_value.startswith("/"):
                        if Path(icon_value).exists():
                            return icon_value
                    else:
                        # It's an icon name, resolve it
                        return cls._resolve_by_name(icon_value) or icon_value
        except Exception:
            pass
        return None
    
    @classmethod
    def _icon_exists_in_theme(cls, icon_name: str) -> bool:
        """Check if an icon exists in the current theme."""
        # This is a heuristic check - if the icon exists in common paths
        for base_path in cls.ICON_PATHS[:2]:  # Check main system paths
            if isinstance(base_path, str):
                base_path = Path(base_path)
            
            if not base_path.exists():
                continue
            
            for size in cls.PREFERRED_SIZES[:3]:  # Check common sizes
                for ext in [".svg", ".png"]:
                    if (base_path / size / "apps" / f"{icon_name}{ext}").exists():
                        return True
        
        return False
    
    @classmethod
    def _get_fallback_icon(cls, source_type: str) -> str:
        """Get fallback icon based on source type."""
        fallbacks = {
            "github": "web-browser-symbolic",
            "flatpak": "system-software-install-symbolic",
            "web": "globe-symbolic",
            "jetbrains": "applications-development-symbolic",
        }
        return fallbacks.get(source_type, "application-x-executable-symbolic")
