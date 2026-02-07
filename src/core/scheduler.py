"""
Universal Update Manager - Update Scheduler
Manages automatic update checking via systemd user timers.
"""

import subprocess
import logging
from pathlib import Path
from typing import Optional
from enum import Enum

logger = logging.getLogger(__name__)


class ScheduleFrequency(Enum):
    """Update check frequency options."""
    HOURLY = "hourly"
    DAILY = "daily"
    WEEKLY = "weekly"
    MANUAL = "manual"  # No automatic checking


class Scheduler:
    """Manages automatic update checking via systemd user timers."""

    SERVICE_NAME = "uum-check"
    SYSTEMD_USER_DIR = Path.home() / ".config" / "systemd" / "user"
    
    def __init__(self):
        """Initialize the scheduler."""
        self.SYSTEMD_USER_DIR.mkdir(parents=True, exist_ok=True)
        self._service_file = self.SYSTEMD_USER_DIR / f"{self.SERVICE_NAME}.service"
        self._timer_file = self.SYSTEMD_USER_DIR / f"{self.SERVICE_NAME}.timer"

    def _get_check_script_path(self) -> Path:
        """Get path to the update check script."""
        # Script is in the same src directory
        return Path(__file__).parent.parent / "check_updates.py"

    def _create_service_file(self, check_script: Path) -> bool:
        """Create the systemd service file."""
        service_content = f"""[Unit]
Description=Universal Update Manager - Check for Updates
After=network-online.target
Wants=network-online.target

[Service]
Type=oneshot
ExecStart=/usr/bin/python3 {check_script}
Environment=DISPLAY=:0
Environment=DBUS_SESSION_BUS_ADDRESS=unix:path=/run/user/%U/bus
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=default.target
"""
        try:
            self._service_file.write_text(service_content)
            logger.info(f"Created service file: {self._service_file}")
            return True
        except Exception as e:
            logger.error(f"Failed to create service file: {e}")
            return False

    def _create_timer_file(self, frequency: ScheduleFrequency) -> bool:
        """Create the systemd timer file."""
        if frequency == ScheduleFrequency.MANUAL:
            return True
        
        # Map frequency to systemd calendar spec
        calendar_specs = {
            ScheduleFrequency.HOURLY: "*-*-* *:00:00",
            ScheduleFrequency.DAILY: "*-*-* 09:00:00",
            ScheduleFrequency.WEEKLY: "Mon *-*-* 09:00:00",
        }
        
        timer_content = f"""[Unit]
Description=Universal Update Manager - Check Timer

[Timer]
OnCalendar={calendar_specs[frequency]}
RandomizedDelaySec=300
Persistent=true

[Install]
WantedBy=timers.target
"""
        try:
            self._timer_file.write_text(timer_content)
            logger.info(f"Created timer file: {self._timer_file}")
            return True
        except Exception as e:
            logger.error(f"Failed to create timer file: {e}")
            return False

    def is_enabled(self) -> bool:
        """Check if the update timer is enabled."""
        try:
            result = subprocess.run(
                ["systemctl", "--user", "is-enabled", f"{self.SERVICE_NAME}.timer"],
                capture_output=True,
                text=True,
                timeout=10,
            )
            return result.returncode == 0
        except Exception:
            return False

    def is_active(self) -> bool:
        """Check if the update timer is currently active."""
        try:
            result = subprocess.run(
                ["systemctl", "--user", "is-active", f"{self.SERVICE_NAME}.timer"],
                capture_output=True,
                text=True,
                timeout=10,
            )
            return result.returncode == 0
        except Exception:
            return False

    def get_next_run(self) -> Optional[str]:
        """Get the next scheduled run time."""
        try:
            result = subprocess.run(
                ["systemctl", "--user", "show", f"{self.SERVICE_NAME}.timer",
                 "--property=NextElapseUSecRealtime"],
                capture_output=True,
                text=True,
                timeout=10,
            )
            if result.returncode == 0:
                line = result.stdout.strip()
                if "=" in line:
                    return line.split("=", 1)[1]
        except Exception:
            pass
        return None

    def enable(self, frequency: ScheduleFrequency = ScheduleFrequency.DAILY) -> bool:
        """
        Enable automatic update checking.
        
        Args:
            frequency: How often to check for updates
            
        Returns:
            True if successfully enabled
        """
        if frequency == ScheduleFrequency.MANUAL:
            return self.disable()
        
        check_script = self._get_check_script_path()
        
        # Create service and timer files
        if not self._create_service_file(check_script):
            return False
        if not self._create_timer_file(frequency):
            return False
        
        try:
            # Reload systemd user daemon
            subprocess.run(
                ["systemctl", "--user", "daemon-reload"],
                capture_output=True,
                timeout=10,
            )
            
            # Enable and start timer
            result = subprocess.run(
                ["systemctl", "--user", "enable", "--now", f"{self.SERVICE_NAME}.timer"],
                capture_output=True,
                text=True,
                timeout=10,
            )
            
            if result.returncode == 0:
                logger.info(f"Enabled update checking: {frequency.value}")
                return True
            else:
                logger.error(f"Failed to enable timer: {result.stderr}")
                return False
                
        except Exception as e:
            logger.error(f"Failed to enable scheduler: {e}")
            return False

    def disable(self) -> bool:
        """Disable automatic update checking."""
        try:
            subprocess.run(
                ["systemctl", "--user", "disable", "--now", f"{self.SERVICE_NAME}.timer"],
                capture_output=True,
                timeout=10,
            )
            logger.info("Disabled automatic update checking")
            return True
        except Exception as e:
            logger.error(f"Failed to disable scheduler: {e}")
            return False

    def run_now(self) -> bool:
        """Trigger an immediate update check."""
        try:
            result = subprocess.run(
                ["systemctl", "--user", "start", f"{self.SERVICE_NAME}.service"],
                capture_output=True,
                text=True,
                timeout=10,
            )
            return result.returncode == 0
        except Exception as e:
            logger.error(f"Failed to run check: {e}")
            return False

    def get_status(self) -> dict:
        """Get scheduler status information."""
        return {
            "enabled": self.is_enabled(),
            "active": self.is_active(),
            "next_run": self.get_next_run(),
            "service_file": str(self._service_file),
            "timer_file": str(self._timer_file),
        }
