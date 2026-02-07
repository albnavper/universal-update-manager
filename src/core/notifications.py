"""
Universal Update Manager - Update History and Notifications
Tracks update history and provides native desktop notifications.
"""

import json
import logging
import subprocess
from pathlib import Path
from datetime import datetime
from dataclasses import dataclass, asdict, field
from typing import Optional, List

logger = logging.getLogger(__name__)


@dataclass
class UpdateRecord:
    """Record of a single update operation."""
    software_id: str
    software_name: str
    source_type: str
    old_version: str
    new_version: str
    timestamp: str
    success: bool
    error_message: Optional[str] = None
    checksum: Optional[str] = None
    backup_id: Optional[str] = None


class UpdateHistory:
    """Tracks history of all update operations."""

    def __init__(self, history_file: Optional[Path] = None):
        """
        Initialize update history.
        
        Args:
            history_file: Path to history JSON file. Defaults to ~/.config/uum/history.json
        """
        self.history_file = history_file or (
            Path.home() / ".config" / "uum" / "history.json"
        )
        self.history_file.parent.mkdir(parents=True, exist_ok=True)
        self._load_history()

    def _load_history(self):
        """Load history from disk."""
        self.records: List[UpdateRecord] = []
        if self.history_file.exists():
            try:
                with open(self.history_file) as f:
                    data = json.load(f)
                    for record in data.get("records", []):
                        self.records.append(UpdateRecord(**record))
            except Exception as e:
                logger.warning(f"Failed to load history: {e}")

    def _save_history(self):
        """Save history to disk."""
        try:
            with open(self.history_file, 'w') as f:
                json.dump(
                    {"records": [asdict(r) for r in self.records]},
                    f, indent=2
                )
        except Exception as e:
            logger.error(f"Failed to save history: {e}")

    def add_record(
        self,
        software_id: str,
        software_name: str,
        source_type: str,
        old_version: str,
        new_version: str,
        success: bool,
        error_message: Optional[str] = None,
        checksum: Optional[str] = None,
        backup_id: Optional[str] = None,
    ) -> UpdateRecord:
        """
        Add a new update record.
        
        Returns:
            The created UpdateRecord
        """
        record = UpdateRecord(
            software_id=software_id,
            software_name=software_name,
            source_type=source_type,
            old_version=old_version,
            new_version=new_version,
            timestamp=datetime.now().isoformat(),
            success=success,
            error_message=error_message,
            checksum=checksum,
            backup_id=backup_id,
        )
        self.records.append(record)
        self._save_history()
        return record

    def get_recent(self, count: int = 20) -> List[UpdateRecord]:
        """Get most recent update records."""
        return sorted(self.records, key=lambda r: r.timestamp, reverse=True)[:count]

    def get_by_software(self, software_id: str) -> List[UpdateRecord]:
        """Get all records for a specific software."""
        return [r for r in self.records if r.software_id == software_id]

    def get_failed(self) -> List[UpdateRecord]:
        """Get all failed update records."""
        return [r for r in self.records if not r.success]

    def get_stats(self) -> dict:
        """Get update statistics."""
        total = len(self.records)
        successful = sum(1 for r in self.records if r.success)
        failed = total - successful
        
        by_source = {}
        for r in self.records:
            by_source[r.source_type] = by_source.get(r.source_type, 0) + 1
        
        return {
            "total": total,
            "successful": successful,
            "failed": failed,
            "success_rate": successful / total if total > 0 else 1.0,
            "by_source": by_source,
        }

    def clear_old(self, max_records: int = 500):
        """Keep only the most recent records."""
        if len(self.records) > max_records:
            self.records = sorted(
                self.records, key=lambda r: r.timestamp, reverse=True
            )[:max_records]
            self._save_history()


class NotificationManager:
    """Manages desktop notifications for update events."""

    def __init__(self):
        """Initialize notification manager."""
        self._check_notify_send()

    def _check_notify_send(self):
        """Check if notify-send is available."""
        try:
            result = subprocess.run(
                ["which", "notify-send"],
                capture_output=True,
                timeout=5
            )
            self._has_notify_send = result.returncode == 0
        except:
            self._has_notify_send = False

    def notify(
        self,
        title: str,
        body: str,
        icon: str = "system-software-update",
        urgency: str = "normal",
        timeout_ms: int = 5000,
    ) -> bool:
        """
        Send a desktop notification.
        
        Args:
            title: Notification title
            body: Notification body text
            icon: Icon name or path
            urgency: "low", "normal", or "critical"
            timeout_ms: Notification timeout in milliseconds
            
        Returns:
            True if notification was sent successfully
        """
        if not self._has_notify_send:
            logger.debug("notify-send not available")
            return False
        
        try:
            subprocess.run(
                [
                    "notify-send",
                    title,
                    body,
                    "-i", icon,
                    "-u", urgency,
                    "-t", str(timeout_ms),
                    "-a", "Universal Update Manager",
                ],
                capture_output=True,
                timeout=5,
            )
            return True
        except Exception as e:
            logger.warning(f"Failed to send notification: {e}")
            return False

    def notify_updates_available(self, count: int, software_names: List[str]):
        """Notify user about available updates."""
        if count == 0:
            return
        
        if count == 1:
            body = f"{software_names[0]} tiene una actualización disponible"
        elif count <= 3:
            body = f"Actualizaciones: {', '.join(software_names)}"
        else:
            body = f"{count} actualizaciones disponibles"
        
        self.notify(
            title="Actualizaciones Disponibles",
            body=body,
            icon="software-update-available",
            urgency="normal",
        )

    def notify_update_complete(self, software_name: str, new_version: str, success: bool):
        """Notify user about completed update."""
        if success:
            self.notify(
                title=f"{software_name} Actualizado",
                body=f"Versión {new_version} instalada correctamente",
                icon="emblem-ok-symbolic",
                urgency="low",
            )
        else:
            self.notify(
                title=f"Error al actualizar {software_name}",
                body="La actualización ha fallado. Revisa los logs.",
                icon="dialog-error",
                urgency="critical",
            )

    def notify_all_updates_complete(self, total: int, successful: int, failed: int):
        """Notify user about batch update completion."""
        if failed == 0:
            self.notify(
                title="Todas las actualizaciones completadas",
                body=f"{successful} paquetes actualizados correctamente",
                icon="emblem-ok-symbolic",
                urgency="low",
            )
        else:
            self.notify(
                title="Actualizaciones completadas con errores",
                body=f"{successful} correctas, {failed} fallidas",
                icon="dialog-warning",
                urgency="normal",
            )


class ProgressTracker:
    """Tracks progress of batch update operations."""

    def __init__(self, total: int):
        """
        Initialize progress tracker.
        
        Args:
            total: Total number of items to process
        """
        self.total = total
        self.completed = 0
        self.successful = 0
        self.failed = 0
        self.current_item: Optional[str] = None
        self._callbacks: List[callable] = []

    def add_callback(self, callback: callable):
        """Add a progress callback function."""
        self._callbacks.append(callback)

    def _notify_callbacks(self):
        """Notify all registered callbacks."""
        for callback in self._callbacks:
            try:
                callback(self.progress, self.current_item)
            except Exception as e:
                logger.debug(f"Callback error: {e}")

    @property
    def progress(self) -> float:
        """Get progress as percentage (0.0 - 1.0)."""
        return self.completed / self.total if self.total > 0 else 1.0

    def start_item(self, name: str):
        """Mark an item as being processed."""
        self.current_item = name
        self._notify_callbacks()

    def complete_item(self, success: bool):
        """Mark an item as completed."""
        self.completed += 1
        if success:
            self.successful += 1
        else:
            self.failed += 1
        self._notify_callbacks()

    def is_complete(self) -> bool:
        """Check if all items are processed."""
        return self.completed >= self.total
