#!/usr/bin/env python3
import gi
import sys
import threading
import signal
import os

# Enforce GTK 3 for Tray support (AppIndicator/XApp)
gi.require_version('Gtk', '3.0')
from gi.repository import Gtk, GLib, Gio

# Try to load XApp first (Best for Mint), then AppIndicator
APP_INDICATOR = False
AYATANA = False
XAPP = False

try:
    gi.require_version('XApp', '1.0')
    from gi.repository import XApp
    XAPP = True
except (ValueError, ImportError):
    try:
        gi.require_version('AppIndicator3', '0.1')
        from gi.repository import AppIndicator3
        APP_INDICATOR = True
    except (ValueError, ImportError):
        try:
            gi.require_version('AyatanaAppIndicator3', '0.1')
            from gi.repository import AyatanaAppIndicator3
            AYATANA = True
        except (ValueError, ImportError):
            print("No tray library available (XApp, AppIndicator3 or Ayatana)")
            sys.exit(1)

class TrayRunner:
    def __init__(self):
        self.app_id = "com.github.universalupdatemanager"
        self.indicator = None
        self.icon_name = "system-software-update" # Standard icon
        print(f"Tray Runner Initializing with icon: {self.icon_name}...", flush=True)
        self.setup_tray()
        self.start_stdin_reader()
        
    def setup_tray(self):
        menu = Gtk.Menu()
        
        item_show = Gtk.MenuItem(label="Mostrar Universal Update Manager")
        item_show.connect("activate", self.on_show_clicked)
        menu.append(item_show)
        
        item_check = Gtk.MenuItem(label="Buscar actualizaciones")
        item_check.connect("activate", self.on_check_clicked)
        menu.append(item_check)
        
        menu.append(Gtk.SeparatorMenuItem())
        
        item_quit = Gtk.MenuItem(label="Salir")
        item_quit.connect("activate", self.on_quit_clicked)
        menu.append(item_quit)
        
        menu.show_all()
        
        if XAPP:
            print("Using XApp backend", flush=True)
            try:
                self.indicator = XApp.StatusIcon()
                self.indicator.set_name("Universal Update Manager")
                self.indicator.set_icon_name(self.icon_name)
                self.indicator.set_secondary_menu(menu)
                self.indicator.set_visible(True)
                self.indicator.connect("activate", self.on_show_clicked)
            except Exception as e:
                print(f"Error initializing XApp: {e}", flush=True)
        elif APP_INDICATOR:
            print("Using AppIndicator3 backend", flush=True)
            try:
                self.indicator = AppIndicator3.Indicator.new(
                    "uum-tray",
                    self.icon_name,
                    AppIndicator3.IndicatorCategory.APPLICATION_STATUS
                )
                self.indicator.set_status(AppIndicator3.IndicatorStatus.ACTIVE)
                self.indicator.set_menu(menu)
                self.indicator.set_title("Universal Update Manager")
            except Exception as e:
                print(f"Error initializing AppIndicator3: {e}", flush=True)
        elif AYATANA:
            print("Using AyatanaAppIndicator3 backend", flush=True)
            try:
                self.indicator = AyatanaAppIndicator3.Indicator.new(
                    "uum-tray",
                    self.icon_name,
                    AyatanaAppIndicator3.IndicatorCategory.APPLICATION_STATUS
                )
                self.indicator.set_status(AyatanaAppIndicator3.IndicatorStatus.ACTIVE)
                self.indicator.set_menu(menu)
                self.indicator.set_title("Universal Update Manager")
            except Exception as e:
                print(f"Error initializing Ayatana: {e}", flush=True)
        else:
            print("No backend available!", flush=True)

    def on_show_clicked(self, *args):
        # Call Activate on the main app via DBus
        try:
            bus = Gio.bus_get_sync(Gio.BusType.SESSION, None)
            bus.call_sync(
                self.app_id,
                "/com/github/universalupdatemanager",
                "org.freedesktop.Application",
                "Activate",
                GLib.Variant("()", ()),
                None,
                Gio.DBusCallFlags.NONE,
                -1,
                None
            )
        except Exception as e:
            print(f"Failed to activate app: {e}", flush=True)

    def on_check_clicked(self, *args):
        # Trigger 'check-updates' action via D-Bus
        try:
            bus = Gio.bus_get_sync(Gio.BusType.SESSION, None)
            bus.call_sync(
                self.app_id,
                "/com/github/universalupdatemanager",
                "org.freedesktop.Application",
                "ActivateAction",
                GLib.Variant("(sava{sv})", ("check-updates", [], {})),
                None,
                Gio.DBusCallFlags.NONE,
                -1,
                None
            )
        except Exception as e:
            print(f"Failed to trigger check: {e}", flush=True)

    def on_quit_clicked(self, *args):
        # Kill the parent process (main app) and then exit ourselves
        try:
            # Get parent PID (the main application)
            ppid = os.getppid()
            print(f"Killing parent process {ppid}...", flush=True)
            
            # First try D-Bus gracefully
            try:
                bus = Gio.bus_get_sync(Gio.BusType.SESSION, None)
                bus.call_sync(
                    self.app_id,
                    "/com/github/universalupdatemanager",
                    "org.freedesktop.Application",
                    "ActivateAction",
                    GLib.Variant("(sava{sv})", ("quit", [], {})),
                    None,
                    Gio.DBusCallFlags.NONE,
                    500,  # Short timeout
                    None
                )
            except Exception:
                pass
            
            # Then force kill parent if still running
            try:
                os.kill(ppid, signal.SIGTERM)
            except ProcessLookupError:
                pass  # Already dead
            
        except Exception as e:
            print(f"Failed to quit app: {e}", flush=True)
        finally:
            Gtk.main_quit()
            sys.exit(0)

    def update_icon(self, count):
        icon_name = "software-update-urgent" if count > 0 else "software-update-available"
        if APP_INDICATOR:
            self.indicator.set_icon_full(icon_name, "Updates")
        elif XAPP:
            self.indicator.set_icon_name(icon_name)

    def start_stdin_reader(self):
        def reader():
            while True:
                try:
                    line = sys.stdin.readline()
                    if not line:
                        break
                    line = line.strip()
                    if line.startswith("COUNT:"):
                        try:
                            count = int(line.split(":")[1])
                            GLib.idle_add(self.update_icon, count)
                        except ValueError:
                            pass
                    elif line == "QUIT":
                        GLib.idle_add(Gtk.main_quit)
                        break
                except Exception:
                    break
        
        t = threading.Thread(target=reader, daemon=True)
        t.start()

if __name__ == "__main__":
    # Handle SIGINT
    signal.signal(signal.SIGINT, signal.SIG_DFL)
    
    runner = TrayRunner()
    Gtk.main()
