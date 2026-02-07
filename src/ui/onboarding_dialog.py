"""
Universal Update Manager - Onboarding Dialog
Dialog for configuring update sources for newly detected software.
"""

import gi
gi.require_version('Gtk', '4.0')
gi.require_version('Adw', '1')
from gi.repository import Gtk, Adw, GLib

from core.scanner import DetectedSoftware


class OnboardingDialog(Adw.Dialog):
    """Dialog for configuring update source for new software."""
    
    def __init__(self, software: DetectedSoftware, on_complete=None):
        super().__init__()
        self.software = software
        self.on_complete = on_complete
        self.result = None
        
        self.set_title("Configurar actualizaciones")
        self.set_content_width(450)
        self.set_content_height(400)
        
        self._build_ui()
    
    def _build_ui(self):
        """Build the dialog UI."""
        # Main content
        content = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        self.set_child(content)
        
        # Header
        header = Adw.HeaderBar()
        header.set_show_end_title_buttons(False)
        header.set_show_start_title_buttons(False)
        
        cancel_btn = Gtk.Button(label="Cancelar")
        cancel_btn.connect("clicked", self._on_cancel)
        header.pack_start(cancel_btn)
        
        self.save_btn = Gtk.Button(label="Guardar")
        self.save_btn.add_css_class("suggested-action")
        self.save_btn.connect("clicked", self._on_save)
        self.save_btn.set_sensitive(False)
        header.pack_end(self.save_btn)
        
        content.append(header)
        
        # Scrollable content
        scrolled = Gtk.ScrolledWindow()
        scrolled.set_vexpand(True)
        scrolled.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        content.append(scrolled)
        
        # Content box
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=24)
        box.set_margin_top(24)
        box.set_margin_bottom(24)
        box.set_margin_start(24)
        box.set_margin_end(24)
        scrolled.set_child(box)
        
        # Software info
        info_group = Adw.PreferencesGroup()
        info_group.set_title("Software detectado")
        box.append(info_group)
        
        name_row = Adw.ActionRow()
        name_row.set_title("Nombre")
        name_row.set_subtitle(self.software.name)
        info_group.add(name_row)
        
        version_row = Adw.ActionRow()
        version_row.set_title("Versión instalada")
        version_row.set_subtitle(self.software.version)
        info_group.add(version_row)
        
        type_row = Adw.ActionRow()
        type_row.set_title("Tipo de instalación")
        type_row.set_subtitle(self.software.install_type.upper())
        info_group.add(type_row)
        
        # Source selection
        source_group = Adw.PreferencesGroup()
        source_group.set_title("Fuente de actualizaciones")
        source_group.set_description("¿Dónde se publican las nuevas versiones?")
        box.append(source_group)
        
        # GitHub option
        self.github_row = Adw.ActionRow()
        self.github_row.set_title("GitHub Releases")
        self.github_row.set_subtitle("usuario/repositorio")
        self.github_check = Gtk.CheckButton()
        self.github_check.connect("toggled", self._on_source_changed)
        self.github_row.add_prefix(self.github_check)
        source_group.add(self.github_row)
        
        # GitHub entry
        self.github_entry_row = Adw.EntryRow()
        self.github_entry_row.set_title("Repositorio")
        self.github_entry_row.set_text("")
        self.github_entry_row.set_sensitive(False)
        self.github_entry_row.connect("changed", self._validate)
        source_group.add(self.github_entry_row)
        
        # Web scraping option
        self.web_row = Adw.ActionRow()
        self.web_row.set_title("Página web")
        self.web_row.set_subtitle("Extraer versión de una URL")
        self.web_check = Gtk.CheckButton()
        self.web_check.set_group(self.github_check)
        self.web_check.connect("toggled", self._on_source_changed)
        self.web_row.add_prefix(self.web_check)
        source_group.add(self.web_row)
        
        # Web URL entry
        self.web_url_row = Adw.EntryRow()
        self.web_url_row.set_title("URL de versiones")
        self.web_url_row.set_text("")
        self.web_url_row.set_sensitive(False)
        self.web_url_row.connect("changed", self._validate)
        source_group.add(self.web_url_row)
        
        # Pattern entry
        self.pattern_row = Adw.EntryRow()
        self.pattern_row.set_title("Patrón de versión (regex)")
        self.pattern_row.set_text(r"(\d+\.\d+(?:\.\d+)*)")
        self.pattern_row.set_sensitive(False)
        source_group.add(self.pattern_row)
        
        # Ignore option
        self.ignore_row = Adw.ActionRow()
        self.ignore_row.set_title("Ignorar")
        self.ignore_row.set_subtitle("No buscar actualizaciones para este software")
        self.ignore_check = Gtk.CheckButton()
        self.ignore_check.set_group(self.github_check)
        self.ignore_check.connect("toggled", self._on_source_changed)
        self.ignore_row.add_prefix(self.ignore_check)
        source_group.add(self.ignore_row)
    
    def _on_source_changed(self, button):
        """Handle source selection change."""
        github_selected = self.github_check.get_active()
        web_selected = self.web_check.get_active()
        
        self.github_entry_row.set_sensitive(github_selected)
        self.web_url_row.set_sensitive(web_selected)
        self.pattern_row.set_sensitive(web_selected)
        
        self._validate()
    
    def _validate(self, *args):
        """Validate form and enable/disable save button."""
        valid = False
        
        if self.github_check.get_active():
            repo = self.github_entry_row.get_text().strip()
            valid = "/" in repo and len(repo) > 3
        elif self.web_check.get_active():
            url = self.web_url_row.get_text().strip()
            valid = url.startswith("http")
        elif self.ignore_check.get_active():
            valid = True
        
        self.save_btn.set_sensitive(valid)
    
    def _on_cancel(self, button):
        """Handle cancel."""
        self.result = None
        self.close()
    
    def _on_save(self, button):
        """Handle save."""
        if self.github_check.get_active():
            repo = self.github_entry_row.get_text().strip()
            
            # Extract owner/repo if full URL is provided
            if "github.com/" in repo:
                import re
                match = re.search(r"github\.com/([^/]+/[^/]+)", repo)
                if match:
                    repo = match.group(1).rstrip("/")
            
            self.result = {
                "source": "github",
                "repo": repo,
                "asset_pattern": r".*\.deb$|.*linux.*\.tar\.gz$",
                "installed_version": self.software.version,
            }
        elif self.web_check.get_active():
            self.result = {
                "source": "web",
                "url": self.web_url_row.get_text().strip(),
                "version_pattern": self.pattern_row.get_text().strip(),
            }
        elif self.ignore_check.get_active():
            self.result = {"source": "ignore"}
        
        if self.on_complete:
            self.on_complete(self.software.id, self.result)
        
        self.close()


class OnboardingManager:
    """Manages onboarding for multiple software items."""
    
    def __init__(self, parent_window):
        self.parent = parent_window
        self.queue: list[DetectedSoftware] = []
        self.current_dialog = None
        self.results: dict[str, dict] = {}
        self.on_all_complete = None
    
    def add_software(self, software: DetectedSoftware):
        """Add software to onboarding queue."""
        self.queue.append(software)
    
    def start(self, on_complete=None):
        """Start processing the onboarding queue."""
        self.on_all_complete = on_complete
        self._process_next()
    
    def _process_next(self):
        """Process next item in queue."""
        if not self.queue:
            if self.on_all_complete:
                self.on_all_complete(self.results)
            return
        
        software = self.queue.pop(0)
        dialog = OnboardingDialog(software, on_complete=self._on_dialog_complete)
        dialog.present(self.parent)
        self.current_dialog = dialog
    
    def _on_dialog_complete(self, software_id: str, result: dict):
        """Handle dialog completion."""
        if result:
            self.results[software_id] = result
        
        # Process next after a short delay
        GLib.timeout_add(100, self._process_next)
