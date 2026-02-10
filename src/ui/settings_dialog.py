"""
Universal Update Manager - Settings Dialog
Dialog for configuring application settings, including GitHub API token.
"""

import gi
gi.require_version('Gtk', '4.0')
gi.require_version('Adw', '1')
from gi.repository import Gtk, Adw, GLib
import logging

logger = logging.getLogger(__name__)


class SettingsDialog(Adw.PreferencesWindow):
    """Dialog for application settings."""
    
    def __init__(self, parent_window, engine):
        super().__init__()
        self.set_transient_for(parent_window)
        self.set_modal(True)
        self.engine = engine
        
        self.set_title("Ajustes")
        self.set_default_size(500, 400)
        
        # General Page
        page = Adw.PreferencesPage()
        page.set_title("General")
        page.set_icon_name("preferences-system-symbolic")
        self.add(page)
        
        # GitHub Group
        github_group = Adw.PreferencesGroup()
        github_group.set_title("GitHub API")
        github_group.set_description(
            "Configura tu token personal para aumentar el límite de descargas.\n"
            "Sin token: 60 peticiones/hora.\n"
            "Con token: 5,000 peticiones/hora."
        )
        page.add(github_group)
        
        # Token Entry
        self.token_row = Adw.PasswordEntryRow()
        self.token_row.set_title("Personal Access Token (PAT)")
        self.token_row.set_show_apply_button(True)
        self.token_row.connect("apply", self._on_token_apply)
        
        # Load existing token
        current_token = self.engine.config.get("github", {}).get("token", "")
        self.token_row.set_text(current_token)
        
        github_group.add(self.token_row)
        
        # Help Link
        help_row = Adw.ActionRow()
        help_row.set_title("¿Cómo obtener un token?")
        help_row.set_subtitle("Necesitas permisos 'public_repo' (Classic) o acceso a repos públicos.")
        
        link_btn = Gtk.LinkButton(
            uri="https://github.com/settings/tokens/new?scopes=public_repo&description=UniversalUpdateManager",
            label="Crear Token"
        )
        link_btn.set_valign(Gtk.Align.CENTER)
        help_row.add_suffix(link_btn)
        github_group.add(help_row)

    def _on_token_apply(self, entry):
        """Save the token when apply button is clicked."""
        token = entry.get_text().strip()
        
        # Initialize github config if not exists
        if "github" not in self.engine.config:
            self.engine.config["github"] = {"packages": []}
        
        # Update token
        if token:
            self.engine.config["github"]["token"] = token
            logger.info("GitHub token saved")
        else:
            # If empty, remove it
            if "token" in self.engine.config["github"]:
                del self.engine.config["github"]["token"]
                logger.info("GitHub token removed")
        
        # Save config
        self.engine.save_config()
        
        # Visual feedback
        toast = Adw.Toast.new("Configuración guardada")
        self.add_toast(toast)
