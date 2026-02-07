"""
Universal Update Manager - System Tray
Manages the tray icon subprocess (GTK3) from the main application (GTK4).
"""

import threading
import logging
from pathlib import Path
from typing import Optional, Callable
import subprocess
import os
import signal
import sys
from gi.repository import GLib, Gio

logger = logging.getLogger(__name__)

class TrayManager:
    """
    Manages the system tray icon subprocess and monitors for new installations.
    """
    
    WATCH_PATHS = [
        "/var/lib/flatpak/app",
        "/opt",
        str(Path.home() / ".local/share/applications"),
    ]
    
    def __init__(self, app, on_show: Callable, on_check_updates: Callable):
        self.app = app
        self.on_show = on_show
        self.on_check_updates = on_check_updates
        self.monitors: list[Gio.FileMonitor] = []
        self._process = None
        self._first_hide = True
        
        self._start_tray_subprocess()
        self._setup_monitors()
    
    def _start_tray_subprocess(self):
        """Start the GTK3 tray runner subprocess."""
        script_path = Path(__file__).parent / "tray_runner.py"
        try:
            self._process = subprocess.Popen(
                [sys.executable, str(script_path)],
                stdin=subprocess.PIPE,
                text=True,
                preexec_fn=os.setsid  # New process group
            )
            logger.info(f"Started tray subprocess with PID {self._process.pid}")
        except Exception as e:
            logger.error(f"Failed to start tray subprocess: {e}")
    
    def update_icon(self, update_count: int):
        """Update the tray icon via stdin."""
        if self._process and self._process.poll() is None:
            try:
                if self._process.stdin:
                    self._process.stdin.write(f"COUNT:{update_count}\n")
                    self._process.stdin.flush()
            except IOError as e:
                logger.warning(f"Failed to communicate with tray: {e}")
    
    def _setup_monitors(self):
        """Setup file system monitors for new installations."""
        for path_str in self.WATCH_PATHS:
            path = Path(path_str)
            if path.exists():
                try:
                    gfile = Gio.File.new_for_path(str(path))
                    monitor = gfile.monitor_directory(
                        Gio.FileMonitorFlags.NONE,
                        None
                    )
                    monitor.connect("changed", self._on_directory_changed)
                    self.monitors.append(monitor)
                    logger.info(f"Monitoring: {path}")
                except Exception as e:
                    logger.warning(f"Failed to monitor {path}: {e}")
    
    def _on_directory_changed(self, monitor, file, other_file, event_type):
        """Handle directory change events."""
        if event_type == Gio.FileMonitorEvent.CREATED:
            filename = file.get_basename()
            logger.info(f"New installation detected: {filename}")
            # Notify about new installation
            GLib.timeout_add(2000, self._notify_new_installation, filename)
    
    def _notify_new_installation(self, name: str):
        """Send notification about new installation."""
        notification = Gio.Notification.new("Nueva aplicación detectada")
        notification.set_body(f"Se ha instalado: {name}")
        notification.set_default_action("app.show-window")
        self.app.send_notification(None, notification)
        return False
    
    def show_notification(self, title: str, body: str):
        """Show a desktop notification."""
        if self._first_hide:
            self._first_hide = False
            notification = Gio.Notification.new(title)
            notification.set_body(body)
            notification.set_default_action("app.show-window")
            self.app.send_notification(None, notification)
    
    def cleanup(self):
        """Clean up monitors and kill tray subprocess."""
        for monitor in self.monitors:
            monitor.cancel()
        self.monitors.clear()
        
        if self._process:
            try:
                # Send QUIT command first
                if self._process.poll() is None and self._process.stdin:
                    try:
                        self._process.stdin.write("QUIT\n")
                        self._process.stdin.flush()
                    except IOError:
                        pass
                
                # Give it a moment, then kill if needed
                try:
                    self._process.wait(timeout=1)
                except subprocess.TimeoutExpired:
                    os.killpg(os.getpgid(self._process.pid), signal.SIGTERM)
            except Exception as e:
                logger.debug(f"Error cleaning up tray process: {e}")
