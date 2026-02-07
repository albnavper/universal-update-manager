"""
Universal Update Manager - Main Application Window
GTK4 + libadwaita interface with tabbed view for updates and apps list.
"""

import gi
gi.require_version('Gtk', '4.0')
gi.require_version('Adw', '1')
from gi.repository import Gtk, Adw, GLib, Gio
import threading
import logging
from pathlib import Path

from core import UpdateEngine, SoftwareScanner
from core.migration import FlatpakMigrator, GitHubAlternative
from plugins import SoftwareInfo, UpdateStatus, UninstallResult
from ui.onboarding_dialog import OnboardingDialog, OnboardingManager
from ui.icon_resolver import IconResolver

logger = logging.getLogger(__name__)


class AppRow(Gtk.Box):
    """A row representing a software application (for both updates and apps list)."""

    def __init__(self, software: SoftwareInfo, show_actions: bool = True, 
                 on_update=None, on_uninstall=None, on_toggle=None):
        super().__init__(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
        self.software = software
        self.on_update = on_update
        self.on_uninstall = on_uninstall
        self.on_toggle = on_toggle
        
        self.set_margin_top(12)
        self.set_margin_bottom(12)
        self.set_margin_start(12)
        self.set_margin_end(12)
        
        # Checkbox for updates view
        if on_toggle:
            self.checkbox = Gtk.CheckButton()
            self.checkbox.set_active(True)
            self.checkbox.connect("toggled", self._on_toggled)
            self.append(self.checkbox)
        
        # App icon - try to get real icon
        icon = self._create_app_icon()
        self.append(icon)
        
        # Info box
        info_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
        info_box.set_hexpand(True)
        
        name_label = Gtk.Label(label=software.name)
        name_label.set_xalign(0)
        name_label.add_css_class("heading")
        info_box.append(name_label)
        
        # Version and source type
        version_text = software.display_version
        
        # Determine source label
        source_text = software.source_type.title()
        if software.source_type == "xdg-system":
            source_text = "Sistema (APT)"
        elif software.source_type == "xdg-local":
            source_text = "Usuario (Local)"
        elif software.source_type == "appimage":
            source_text = "AppImage"
            
        source_label = Gtk.Label(label=f"{version_text} • {source_text}")
        source_label.set_xalign(0)
        source_label.add_css_class("dim-label")
        info_box.append(source_label)
        
        # Description (if available)
        if software.description:
            desc_text = software.description[:80] + "..." if len(software.description or "") > 80 else software.description
            desc_label = Gtk.Label(label=desc_text)
            desc_label.set_xalign(0)
            desc_label.add_css_class("caption")
            desc_label.add_css_class("dim-label")
            desc_label.set_wrap(True)
            desc_label.set_max_width_chars(60)
            info_box.append(desc_label)
        
        self.append(info_box)
        
        # Status indicator
        if software.status == UpdateStatus.UPDATE_AVAILABLE:
            status_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=4)
            update_icon = Gtk.Image.new_from_icon_name("software-update-available-symbolic")
            update_icon.add_css_class("accent")
            status_box.append(update_icon)
            self.append(status_box)
        elif software.status == UpdateStatus.UP_TO_DATE:
            check_icon = Gtk.Image.new_from_icon_name("emblem-ok-symbolic")
            check_icon.add_css_class("success")
            self.append(check_icon)
        
        # Action buttons (for apps list view)
        if show_actions and not on_toggle:
            btn_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
            
            if software.status == UpdateStatus.UPDATE_AVAILABLE and on_update:
                update_btn = Gtk.Button(label="Actualizar")
                update_btn.add_css_class("suggested-action")
                update_btn.connect("clicked", lambda b: on_update(software))
                btn_box.append(update_btn)
            
            if on_uninstall:
                uninstall_btn = Gtk.Button(icon_name="user-trash-symbolic")
                uninstall_btn.set_tooltip_text("Desinstalar")
                uninstall_btn.add_css_class("destructive-action")
                uninstall_btn.connect("clicked", lambda b: on_uninstall(software))
                btn_box.append(uninstall_btn)
            
            self.append(btn_box)

    def _create_app_icon(self) -> Gtk.Image:
        """Create an image widget with the app's real icon."""
        # Get app ID for flatpak, or software ID for others
        app_id = getattr(self.software, 'id', None)
        icon_hint = getattr(self.software, 'icon', None)
        
        # Resolve the icon
        resolved = IconResolver.resolve(
            software_id=self.software.id,
            source_type=self.software.source_type,
            app_id=app_id,
            icon_name=icon_hint
        )
        
        # Create image - check if it's a path or icon name
        if resolved and (resolved.startswith('/') or resolved.startswith(str(Path.home()))):
            # It's a file path
            try:
                icon = Gtk.Image.new_from_file(resolved)
            except:
                icon = Gtk.Image.new_from_icon_name("application-x-executable-symbolic")
        else:
            # It's an icon name
            icon = Gtk.Image.new_from_icon_name(resolved)
        
        icon.set_pixel_size(40)
        return icon

    def _on_toggled(self, button):
        if self.on_toggle:
            self.on_toggle(self.software, button.get_active())


class MainWindow(Adw.ApplicationWindow):
    """Main application window with tabbed interface."""

    def __init__(self, app):
        super().__init__(application=app)
        self.set_title("Universal Update Manager")
        self.set_default_size(700, 750)
        
        self.engine = None
        self.scanner = None
        self.migrator = FlatpakMigrator()
        self.all_software: list[SoftwareInfo] = []
        self.updates: list[SoftwareInfo] = []
        self.selected: set[str] = set()
        self.migrations: list[GitHubAlternative] = []
        
        self._build_ui()
        self._init_engine()

    def _build_ui(self):
        """Build the UI components with tabs."""
        # Main box
        main_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        self.set_content(main_box)

        # Header bar
        header = Adw.HeaderBar()
        
        # Refresh button
        refresh_btn = Gtk.Button(icon_name="view-refresh-symbolic")
        refresh_btn.set_tooltip_text("Comprobar actualizaciones")
        refresh_btn.connect("clicked", self._on_refresh)
        header.pack_start(refresh_btn)
        
        # Scan button
        scan_btn = Gtk.Button(icon_name="system-search-symbolic")
        scan_btn.set_tooltip_text("Escanear software nuevo")
        scan_btn.connect("clicked", self._on_scan)
        header.pack_start(scan_btn)
        
        main_box.append(header)

        # Status banner
        self.banner = Adw.Banner()
        self.banner.set_revealed(False)
        main_box.append(self.banner)

        # Tab view
        self.tab_view = Adw.ViewStack()
        self.tab_view.set_vexpand(True)
        
        # Tab switcher in header
        switcher = Adw.ViewSwitcher()
        switcher.set_stack(self.tab_view)
        switcher.set_policy(Adw.ViewSwitcherPolicy.WIDE)
        header.set_title_widget(switcher)
        
        # Updates tab
        updates_page = self._create_updates_page()
        self.tab_view.add_titled_with_icon(updates_page, "updates", "Actualizaciones", "software-update-available-symbolic")
        
        # Apps tab
        apps_page = self._create_apps_page()
        self.tab_view.add_titled_with_icon(apps_page, "apps", "Aplicaciones", "view-grid-symbolic")
        
        # Migrations tab
        migrations_page = self._create_migrations_page()
        self.tab_view.add_titled_with_icon(migrations_page, "migrations", "Migraciones", "emblem-synchronizing-symbolic")
        
        main_box.append(self.tab_view)

        # Bottom action bar for updates
        self.action_bar = Gtk.ActionBar()
        main_box.append(self.action_bar)
        
        self.count_label = Gtk.Label(label="")
        self.action_bar.pack_start(self.count_label)
        
        self.update_btn = Gtk.Button(label="Actualizar seleccionados")
        self.update_btn.add_css_class("suggested-action")
        self.update_btn.connect("clicked", self._on_update_all)
        self.update_btn.set_sensitive(False)
        self.action_bar.pack_end(self.update_btn)

    def _create_updates_page(self) -> Gtk.Widget:
        """Create the updates tab content."""
        scrolled = Gtk.ScrolledWindow()
        scrolled.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        
        self.updates_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        scrolled.set_child(self.updates_box)
        
        # Loading state
        self.spinner = Gtk.Spinner()
        self.spinner.set_size_request(32, 32)
        self.spinner.set_halign(Gtk.Align.CENTER)
        self.spinner.set_margin_top(48)
        self.updates_box.append(self.spinner)
        
        self.status_label = Gtk.Label(label="Comprobando actualizaciones...")
        self.status_label.set_margin_top(12)
        self.updates_box.append(self.status_label)
        
        return scrolled

    def _create_apps_page(self) -> Gtk.Widget:
        """Create the apps list tab content."""
        scrolled = Gtk.ScrolledWindow()
        scrolled.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        
        self.apps_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        scrolled.set_child(self.apps_box)
        
        # Initial loading state
        loading_label = Gtk.Label(label="Cargando aplicaciones...")
        loading_label.set_margin_top(48)
        loading_label.add_css_class("dim-label")
        self.apps_box.append(loading_label)
        
        return scrolled
    
    def _create_migrations_page(self):
        """Create the Flatpak→GitHub migrations page."""
        page = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        
        # Info banner at top
        info_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
        info_box.set_margin_start(16)
        info_box.set_margin_end(16)
        info_box.set_margin_top(12)
        info_box.set_margin_bottom(12)
        info_box.add_css_class("card")
        
        info_icon = Gtk.Image.new_from_icon_name("dialog-information-symbolic")
        info_icon.set_pixel_size(24)
        info_box.append(info_icon)
        
        info_label = Gtk.Label(
            label="Algunas apps Flatpak tienen versiones más nuevas en GitHub.\n"
                  "La migración preservará tu configuración y datos."
        )
        info_label.set_wrap(True)
        info_label.set_xalign(0)
        info_box.append(info_label)
        
        page.append(info_box)
        
        # Scrollable list
        scrolled = Gtk.ScrolledWindow()
        scrolled.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        scrolled.set_vexpand(True)
        
        self.migrations_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        scrolled.set_child(self.migrations_box)
        
        # Initial loading state
        loading_label = Gtk.Label(label="Buscando alternativas...")
        loading_label.set_margin_top(48)
        loading_label.add_css_class("dim-label")
        self.migrations_box.append(loading_label)
        
        page.append(scrolled)
        
        return page

    def _init_engine(self):
        """Initialize the update engine in background."""
        self.spinner.start()
        threading.Thread(target=self._load_engine, daemon=True).start()

    def _load_engine(self):
        """Load engine and check for updates."""
        try:
            logger.info("Starting engine initialization...")
            config_path = Path(__file__).parent.parent.parent / "config" / "sources.json"
            self.engine = UpdateEngine(config_path)
            self.scanner = SoftwareScanner(config_path)
            
            logger.info("Engine initialized, checking for updates...")
            
            # Get all software first
            tracked_software = self.engine.check_all_updates()
            
            # Get detected software from scanner
            detected_software = self.scanner.scan_all()
            
            # Convert detected to SoftwareInfo and merge
            # Avoid duplicates if engine already tracks them
            tracked_ids = {s.id for s in tracked_software}
            
            all_software = list(tracked_software)
            
            for d in detected_software:
                # Skip if already tracked by a plugin
                if d.id in tracked_ids:
                    continue
                    
                # Skip if detected as flatpak-export (already covered by Flatpak plugin)
                if d.install_type == "flatpak-export":
                    continue

                info = SoftwareInfo(
                    id=d.id,
                    name=d.name,
                    installed_version=d.version,
                    latest_version=None,
                    source_type=d.install_type, # xdg-system, xdg-local, etc.
                    source_url=None,
                    icon=d.id, 
                    description=d.description or f"Detectado en {d.install_path}",
                    status=UpdateStatus.UNKNOWN
                )
                all_software.append(info)
                
            self.all_software = all_software
            
            # Filter for updates
            self.updates = [s for s in self.all_software if s.status == UpdateStatus.UPDATE_AVAILABLE]
            self.selected = {u.id for u in self.updates}
            
            logger.info(f"Found {len(self.all_software)} apps, {len(self.updates)} updates")
            
            GLib.idle_add(self._populate_updates)
            GLib.idle_add(self._populate_apps)
            
            # Check for migration opportunities (Flatpak → GitHub)
            flatpak_apps = [
                {"id": s.id, "name": s.name, "version": s.installed_version}
                for s in self.all_software if s.source_type == "flatpak"
            ]
            if flatpak_apps:
                self.migrations = self.migrator.find_alternatives(flatpak_apps)
                logger.info(f"Found {len(self.migrations)} migration opportunities")
                GLib.idle_add(self._populate_migrations)
            
        except Exception as e:
            logger.error(f"Failed to initialize engine: {e}", exc_info=True)
            GLib.idle_add(self._show_error, str(e))

    def _populate_updates(self):
        """Populate the updates tab."""
        self.spinner.stop()
        
        # Clear content
        while child := self.updates_box.get_first_child():
            self.updates_box.remove(child)
        
        if not self.updates:
            # Empty state
            empty_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
            empty_box.set_margin_top(48)
            empty_box.set_halign(Gtk.Align.CENTER)
            
            icon = Gtk.Image.new_from_icon_name("emblem-ok-symbolic")
            icon.set_pixel_size(64)
            icon.add_css_class("success")
            empty_box.append(icon)
            
            label = Gtk.Label(label="Todo actualizado")
            label.add_css_class("title-1")
            empty_box.append(label)
            
            sublabel = Gtk.Label(label="No hay actualizaciones disponibles")
            sublabel.add_css_class("dim-label")
            empty_box.append(sublabel)
            
            self.updates_box.append(empty_box)
            self.count_label.set_label("Sin actualizaciones")
            return
        
        # Add update rows
        for software in self.updates:
            row = AppRow(software, show_actions=False, on_toggle=self._on_row_toggle)
            self.updates_box.append(row)
            
            sep = Gtk.Separator(orientation=Gtk.Orientation.HORIZONTAL)
            self.updates_box.append(sep)
        
        self._update_count()

    def _populate_apps(self):
        """Populate the apps list tab."""
        # Clear content
        while child := self.apps_box.get_first_child():
            self.apps_box.remove(child)
        
        if not self.all_software:
            empty_label = Gtk.Label(label="No se encontraron aplicaciones")
            empty_label.set_margin_top(48)
            empty_label.add_css_class("dim-label")
            self.apps_box.append(empty_label)
            return
        
        # Count by status
        up_to_date = len([s for s in self.all_software if s.status == UpdateStatus.UP_TO_DATE])
        with_updates = len([s for s in self.all_software if s.status == UpdateStatus.UPDATE_AVAILABLE])
        
        # Header
        header_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
        header_box.set_margin_start(12)
        header_box.set_margin_end(12)
        header_box.set_margin_top(12)
        header_box.set_margin_bottom(8)
        
        header_label = Gtk.Label(label=f"{len(self.all_software)} aplicaciones instaladas")
        header_label.set_xalign(0)
        header_label.add_css_class("heading")
        header_label.set_hexpand(True)
        header_box.append(header_label)
        
        stats_label = Gtk.Label(label=f"{up_to_date} ✓  |  {with_updates} ↑")
        stats_label.add_css_class("dim-label")
        header_box.append(stats_label)
        
        self.apps_box.append(header_box)
        
        # Sort: updates first, then alphabetically
        sorted_apps = sorted(
            self.all_software,
            key=lambda s: (0 if s.status == UpdateStatus.UPDATE_AVAILABLE else 1, s.name.lower())
        )
        
        for software in sorted_apps:
            row = AppRow(
                software, 
                show_actions=True,
                on_update=self._on_update_single,
                on_uninstall=self._on_uninstall
            )
            self.apps_box.append(row)
            
            sep = Gtk.Separator(orientation=Gtk.Orientation.HORIZONTAL)
            self.apps_box.append(sep)
    
    def _populate_migrations(self):
        """Populate the migrations tab."""
        # Clear content
        while child := self.migrations_box.get_first_child():
            self.migrations_box.remove(child)
        
        if not self.migrations:
            # No migrations available
            empty_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
            empty_box.set_margin_top(48)
            empty_box.set_halign(Gtk.Align.CENTER)
            
            icon = Gtk.Image.new_from_icon_name("emblem-ok-symbolic")
            icon.set_pixel_size(64)
            icon.add_css_class("success")
            empty_box.append(icon)
            
            label = Gtk.Label(label="Todo al día")
            label.add_css_class("title-1")
            empty_box.append(label)
            
            sublabel = Gtk.Label(
                label="No hay Flatpaks con versiones más nuevas en GitHub"
            )
            sublabel.add_css_class("dim-label")
            empty_box.append(sublabel)
            
            self.migrations_box.append(empty_box)
            return
        
        # Show migration opportunities
        for alt in self.migrations:
            row = self._create_migration_row(alt)
            self.migrations_box.append(row)
            
            sep = Gtk.Separator(orientation=Gtk.Orientation.HORIZONTAL)
            self.migrations_box.append(sep)
    
    def _create_migration_row(self, alt: GitHubAlternative):
        """Create a row for a migration opportunity."""
        row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
        row.set_margin_start(16)
        row.set_margin_end(16)
        row.set_margin_top(12)
        row.set_margin_bottom(12)
        
        # Icon
        icon = Gtk.Image.new_from_icon_name("emblem-synchronizing-symbolic")
        icon.set_pixel_size(40)
        row.append(icon)
        
        # Info
        info_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        info_box.set_hexpand(True)
        
        name_label = Gtk.Label(label=alt.flatpak_name)
        name_label.set_xalign(0)
        name_label.add_css_class("heading")
        info_box.append(name_label)
        
        version_label = Gtk.Label(
            label=f"Flatpak {alt.flatpak_version} → GitHub {alt.github_version}"
        )
        version_label.set_xalign(0)
        version_label.add_css_class("dim-label")
        info_box.append(version_label)
        
        repo_label = Gtk.Label(label=f"github.com/{alt.github_repo}")
        repo_label.set_xalign(0)
        repo_label.add_css_class("caption")
        repo_label.add_css_class("dim-label")
        info_box.append(repo_label)
        
        row.append(info_box)
        
        # Data size indicator
        data_size = self.migrator.get_flatpak_data_size(alt.flatpak_id)
        if data_size > 0:
            size_mb = data_size / (1024 * 1024)
            size_label = Gtk.Label(label=f"📁 {size_mb:.1f} MB")
            size_label.add_css_class("dim-label")
            size_label.set_tooltip_text("Datos que serán migrados")
            row.append(size_label)
        
        # Migrate button
        btn_label = "Migrar" if alt.is_newer else "Cambiar a GitHub"
        migrate_btn = Gtk.Button(label=btn_label)
        if alt.is_newer:
            migrate_btn.add_css_class("suggested-action")
        migrate_btn.connect("clicked", lambda b: self._on_migrate(alt))
        row.append(migrate_btn)
        
        return row
    
    def _on_migrate(self, alt: GitHubAlternative):
        """Handle migration request."""
        # Show confirmation dialog
        action = "Migrar (Actualizar)" if alt.is_newer else "Cambiar versión"
        msg = f"Se instalará desde GitHub (v{alt.github_version}) " \
              f"preservando tu configuración."
        
        if not alt.is_newer:
            msg += "\n\nNOTA: La versión de GitHub es igual o anterior a la de Flatpak."

        dialog = Adw.MessageDialog(
            transient_for=self,
            heading=f"¿{action} {alt.flatpak_name}?",
            body=f"{msg}\n\nEl Flatpak será eliminado después.",
        )
        dialog.add_response("cancel", "Cancelar")
        dialog.add_response("migrate", "Proceder")
        dialog.set_response_appearance("migrate", Adw.ResponseAppearance.SUGGESTED)
        dialog.connect("response", self._on_migrate_response, alt)
        dialog.present()
    
    def _on_migrate_response(self, dialog, response, alt: GitHubAlternative):
        """Handle migration confirmation response."""
        if response != "migrate":
            return
        
        self.banner.set_title(f"Migrando {alt.flatpak_name}...")
        self.banner.set_revealed(True)
        
        threading.Thread(
            target=self._perform_migration,
            args=(alt,),
            daemon=True
        ).start()
    
    def _perform_migration(self, alt: GitHubAlternative):
        """Perform the migration in background."""
        def install_func(repo):
            # Use GitHub plugin to install
            for plugin in self.engine.plugins:
                if plugin.source_type == "github":
                    # Create a temporary SoftwareInfo
                    from plugins import SoftwareInfo
                    # Use a better ID derivation
                    app_id = alt.flatpak_id.lower()
                    if app_id.count(".") >= 2:
                        # try to get the 'telegram' from org.telegram.desktop
                        parts = app_id.split(".")
                        if parts[-1] in ["desktop", "client", "app"]:
                            app_id = parts[-2]
                        else:
                            app_id = parts[-1]
                    
                    software = SoftwareInfo(
                        id=app_id,
                        name=alt.flatpak_name,
                        installed_version=alt.flatpak_version,
                        latest_version=alt.github_version,
                        source_type="github",
                        source_url=f"https://github.com/{repo}/releases",
                        icon=None,
                    )
                    # Add to config temporarily
                    # Asset pattern logic
                    pattern = r".*\.(deb|tar\.gz|tar\.xz|txz|AppImage)$"
                    if "telegram" in repo.lower():
                        pattern = r"tsetup.*\.tar\.xz$"
                    
                    config_data = {
                        "id": software.id,
                        "name": software.name,
                        "repo": repo,
                        "asset_pattern": pattern,
                    }
                    logger.info(f"Adding temp config for migration: {config_data}")
                    self.engine.add_package("github", config_data)
                    
                    result = plugin.update(software)
                    logger.info(f"Migration install result for {repo}: {result}")
                    return result
            from plugins import InstallResult
            return InstallResult(success=False, error_message="No GitHub plugin")
        
        result = self.migrator.migrate(alt, install_func)
        
        if result.success:
            msg = f"✓ {alt.flatpak_name} migrado a GitHub v{alt.github_version}"
            if result.data_preserved:
                msg += " (datos preservados)"
            GLib.idle_add(self.banner.set_title, msg)
            GLib.timeout_add(3000, self._on_refresh, None)
        else:
            GLib.idle_add(self.banner.set_title, f"⚠ Error: {result.message}")

    def _on_row_toggle(self, software: SoftwareInfo, selected: bool):
        """Handle row selection toggle."""
        if selected:
            self.selected.add(software.id)
        else:
            self.selected.discard(software.id)
        self._update_count()

    def _update_count(self):
        """Update the selected count label."""
        total = len(self.updates)
        selected = len(self.selected)
        self.count_label.set_label(f"{selected} de {total} seleccionados")
        self.update_btn.set_sensitive(selected > 0)

    def _on_refresh(self, button):
        """Refresh updates list."""
        # Clear updates box
        while child := self.updates_box.get_first_child():
            self.updates_box.remove(child)
        
        self.spinner = Gtk.Spinner()
        self.spinner.set_size_request(32, 32)
        self.spinner.set_halign(Gtk.Align.CENTER)
        self.spinner.set_margin_top(48)
        self.updates_box.append(self.spinner)
        
        self.status_label = Gtk.Label(label="Comprobando actualizaciones...")
        self.status_label.set_margin_top(12)
        self.updates_box.append(self.status_label)
        
        self.spinner.start()
        self.updates = []
        self.selected = set()
        threading.Thread(target=self._load_engine, daemon=True).start()

    def _on_scan(self, button):
        """Scan for new software."""
        self.banner.set_title("Escaneando software instalado...")
        self.banner.set_revealed(True)
        threading.Thread(target=self._run_scan, daemon=True).start()
    
    def _run_scan(self):
        """Run software scan in background."""
        try:
            if not self.scanner:
                config_path = Path(__file__).parent.parent.parent / "config" / "sources.json"
                self.scanner = SoftwareScanner(config_path)
            
            detected = self.scanner.scan_all()
            
            # Filter out already configured or ignored software
            configured_ids = set()
            for plugin in self.engine.plugins:
                for sw in plugin.get_tracked_software():
                    configured_ids.add(sw.id)
            
            ignored = set(self.engine.config.get("ignored", []))
            
            unconfigured = [
                d for d in detected 
                if d.id not in configured_ids 
                and d.id not in ignored
                and not d.known_source
            ]
            
            GLib.idle_add(self._on_scan_complete, unconfigured)
            
        except Exception as e:
            logger.error(f"Scan failed: {e}", exc_info=True)
            GLib.idle_add(self._show_error, f"Error al escanear: {e}")
    
    def _on_scan_complete(self, unconfigured):
        """Handle scan completion."""
        if not unconfigured:
            self.banner.set_title("✓ No se encontró software sin configurar")
            GLib.timeout_add(3000, lambda: self.banner.set_revealed(False))
            return
        
        self.banner.set_title(f"Se encontraron {len(unconfigured)} apps sin configurar")
        
        manager = OnboardingManager(self)
        for software in unconfigured[:5]:
            manager.add_software(software)
        
        manager.start(on_complete=self._on_onboarding_complete)
    
    def _on_onboarding_complete(self, results: dict):
        """Handle onboarding completion."""
        added = 0
        ignored = 0
        
        for software_id, config in results.items():
            if config.get("source") == "ignore":
                self.engine.ignore_package(software_id)
                ignored += 1
            elif config.get("source") == "github":
                # Ensure repo is clean even if validation missed it
                repo = config["repo"]
                if "github.com/" in repo:
                    import re
                    match = re.search(r"github\.com/([^/]+/[^/]+)", repo)
                    if match:
                        repo = match.group(1).rstrip("/")

                self.engine.add_package("github", {
                    "id": software_id,
                    "name": software_id.replace("-", " ").title(),
                    "repo": repo,
                    "asset_pattern": config.get("asset_pattern", r".*\.(deb|tar\.gz|tar\.xz|txz|AppImage)$"),
                    "installed_version": config.get("installed_version"),
                })
                added += 1
            elif config.get("source") == "web":
                self.engine.add_package("web", {
                    "id": software_id,
                    "name": software_id.replace("-", " ").title(),
                    "url": config["url"],
                    "version_pattern": config.get("version_pattern", r"(\d+\.\d+\.\d+)"),
                })
                added += 1
        
        if added > 0:
            self.banner.set_title(f"✓ {added} fuentes añadidas, {ignored} ignoradas")
            GLib.timeout_add(2000, self._on_refresh, None)
        else:
            self.banner.set_revealed(False)

    def _on_update_single(self, software: SoftwareInfo):
        """Update a single application."""
        self.banner.set_title(f"Actualizando {software.name}...")
        self.banner.set_revealed(True)
        
        threading.Thread(
            target=self._install_single_update,
            args=(software,),
            daemon=True
        ).start()

    def _install_single_update(self, software: SoftwareInfo):
        """Install update for a single app."""
        result = self.engine.install_update(software)
        
        if result.success:
            GLib.idle_add(self.banner.set_title, f"✓ {software.name} actualizado")
            GLib.timeout_add(2000, self._on_refresh, None)
        else:
            GLib.idle_add(self.banner.set_title, f"⚠ Error: {result.error_message}")

    def _on_update_all(self, button):
        """Install selected updates."""
        self.update_btn.set_sensitive(False)
        self.banner.set_title("Instalando actualizaciones...")
        self.banner.set_revealed(True)
        
        threading.Thread(target=self._install_updates, daemon=True).start()

    def _install_updates(self):
        """Install selected updates in background."""
        to_update = [u for u in self.updates if u.id in self.selected]
        success_count = 0
        
        for software in to_update:
            result = self.engine.install_update(software)
            if result.success:
                success_count += 1
        
        GLib.idle_add(self._on_updates_complete, success_count, len(to_update))

    def _on_updates_complete(self, success: int, total: int):
        """Handle update completion."""
        if success == total:
            self.banner.set_title(f"✓ {success} actualizaciones instaladas")
        else:
            self.banner.set_title(f"⚠ {success}/{total} actualizaciones instaladas")
        
        self.banner.set_revealed(True)
        self._on_refresh(None)

    def _on_uninstall(self, software: SoftwareInfo):
        """Handle uninstall request."""
        # Show confirmation dialog
        dialog = Adw.MessageDialog(
            transient_for=self,
            heading=f"¿Desinstalar {software.name}?",
            body="Esta acción no se puede deshacer.",
        )
        dialog.add_response("cancel", "Cancelar")
        dialog.add_response("uninstall", "Desinstalar")
        dialog.set_response_appearance("uninstall", Adw.ResponseAppearance.DESTRUCTIVE)
        dialog.connect("response", self._on_uninstall_response, software)
        dialog.present()

    def _on_uninstall_response(self, dialog, response: str, software: SoftwareInfo):
        """Handle uninstall confirmation response."""
        if response != "uninstall":
            return
        
        self.banner.set_title(f"Desinstalando {software.name}...")
        self.banner.set_revealed(True)
        
        threading.Thread(
            target=self._run_uninstall,
            args=(software,),
            daemon=True
        ).start()

    def _run_uninstall(self, software: SoftwareInfo):
        """Run uninstall in background."""
        if self.engine:
            plugin = self.engine._get_plugin_for_software(software)
        else:
            plugin = None

        # Handle plugin-based apps (Flatpak, etc.)
        if plugin:
            result = plugin.uninstall(software)
            if result.success:
                GLib.idle_add(self.banner.set_title, f"✓ {software.name} desinstalado")
                GLib.timeout_add(2000, self._on_refresh, None)
            else:
                GLib.idle_add(self.banner.set_title, f"⚠ Error: {result.error_message}")
            return
            
        # Handle detected system apps (APT)
        if software.source_type == "xdg-system" or (software.description and "apt" in str(software.description).lower()):
            try:
                # Use pkexec to run apt remove
                # We need the package name, which is stored in software.id for xdg-system
                pkg_name = software.id
                
                # Show indeterminate progress
                GLib.idle_add(self.banner.set_title, f"Desinstalando {pkg_name} via APT...")
                
                cmd = ["pkexec", "apt", "remove", "-y", pkg_name]
                
                subprocess.run(cmd, check=True, text=True, capture_output=True)
                
                GLib.idle_add(self.banner.set_title, f"✓ {software.name} desinstalado (APT)")
                GLib.timeout_add(2000, self._on_refresh, None)
                
            except subprocess.CalledProcessError as e:
                error_msg = e.stderr.strip() if e.stderr else str(e)
                # Check for cancellation
                if "Authorisation not granted" in error_msg or "not authorized" in error_msg.lower():
                     GLib.idle_add(self.banner.set_title, "⚠ Cancelado por usuario")
                else:
                     GLib.idle_add(self.banner.set_title, f"⚠ Fallo al desinstalar: {error_msg}")
            except Exception as e:
                GLib.idle_add(self.banner.set_title, f"⚠ Error: {e}")
            return
            
        # Handle other detected apps (manual)
        GLib.idle_add(self.banner.set_title, "⚠ Desinstalación manual requerida para este tipo")

    def _show_error(self, message: str):
        """Show error message."""
        self.spinner.stop()
        self.banner.set_title(f"Error: {message}")
        self.banner.set_revealed(True)


class UniversalUpdateManager(Adw.Application):
    """Main application class with system tray support."""

    def __init__(self):
        super().__init__(
            application_id="com.github.universalupdatemanager",
            flags=Gio.ApplicationFlags.FLAGS_NONE,
        )
        self.window = None
        self.tray = None
        self.hold_id = None
    
    def do_startup(self):
        """Application startup."""
        Adw.Application.do_startup(self)
        
        # Create quit action
        quit_action = Gio.SimpleAction.new("quit", None)
        quit_action.connect("activate", self._on_quit)
        self.add_action(quit_action)
        
        # Create show-window action
        show_action = Gio.SimpleAction.new("show-window", None)
        show_action.connect("activate", lambda a, p: self._show_window())
        self.add_action(show_action)
        
        # Create check-updates action
        check_action = Gio.SimpleAction.new("check-updates", None)
        check_action.connect("activate", lambda a, p: self._check_updates())
        self.add_action(check_action)

    def do_activate(self):
        """Handle application activation."""
        if not self.window:
            # Kill any zombie tray runners
            import subprocess
            try:
                subprocess.run(["pkill", "-f", "tray_runner.py"], check=False)
            except Exception:
                pass

            self.window = MainWindow(self)
            self.window.connect("close-request", self._on_window_close)
            
            # Initialize tray
            try:
                from ui.tray import TrayManager
                self.tray = TrayManager(
                    self,
                    on_show=self._show_window,
                    on_check_updates=self._check_updates
                )
            except Exception as e:
                logger.warning(f"Failed to setup tray: {e}")
            
            # Hold application to keep running in background
            self.hold()
        
        self.window.present()
    
    def _on_window_close(self, window):
        """Handle window close - minimize to tray instead of quitting."""
        window.hide()
        
        # Show notification on first hide
        if self.tray:
            self.tray.show_notification(
                "Universal Update Manager",
                "La aplicación sigue ejecutándose en segundo plano"
            )
        
        return True  # Prevent window destruction
    
    def _show_window(self):
        """Show the main window."""
        if self.window:
            self.window.present()
    
    def _check_updates(self):
        """Trigger update check from tray."""
        if self.window:
            self.window.present()
            self.window._on_refresh(None)
    
    def _on_quit(self, action, param):
        """Quit the application completely."""
        if self.tray:
            self.tray.cleanup()
        self.quit()


def main():
    """Application entry point."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )
    
    app = UniversalUpdateManager()
    app.run(None)


if __name__ == "__main__":
    main()
