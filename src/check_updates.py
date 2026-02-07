#!/usr/bin/env python3
"""
Universal Update Manager - Background Update Check Script
Called by systemd timer to check for updates and send notifications.
"""

import sys
import os

# Add src to path
src_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, src_dir)

from pathlib import Path
import logging

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(Path.home() / ".cache" / "uum" / "check.log"),
        logging.StreamHandler(),
    ]
)
logger = logging.getLogger(__name__)


def main():
    """Check for updates and send notification if any found."""
    try:
        from core.engine import UpdateEngine
        from core.notifications import NotificationManager
        
        # Initialize engine
        config_path = Path(__file__).parent.parent / "config" / "sources.json"
        engine = UpdateEngine(config_path)
        
        # Check for updates
        logger.info("Checking for updates...")
        updates = engine.get_updates_available()
        
        if updates:
            logger.info(f"Found {len(updates)} updates available")
            
            # Send notification
            nm = NotificationManager()
            nm.notify_updates_available(
                count=len(updates),
                software_names=[u.name for u in updates[:5]]
            )
        else:
            logger.info("No updates available")
        
        return 0
        
    except Exception as e:
        logger.error(f"Update check failed: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
