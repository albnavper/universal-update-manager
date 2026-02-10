import time
import schedule
import logging
import qbittorrentapi
import sys

# Configure logging with absolute path that is definitely writable
log_file = "/config/qBittorrent/automation.log"
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(log_file),
        logging.StreamHandler(sys.stdout)
    ]
)

def get_client():
    try:
        conn = qbittorrentapi.Client(host='localhost', port=8080)
        conn.auth_log_in()
        return conn
    except Exception as e:
        logging.error(f"Failed to connect: {e}")
        return None

def force_settings():
    """Forces critical settings to bypass dialogs."""
    client = get_client()
    if not client: return
    
    try:
        prefs = client.app.preferences
        changes = {}
        
        # Force these settings to ensure NO dialogs and IMMEDIATE start
        if prefs.get('addition_dialog_enabled') is not False:
            changes['addition_dialog_enabled'] = False
        if prefs.get('auto_tmm_enabled') is not True:
            changes['auto_tmm_enabled'] = True
        if prefs.get('start_paused_enabled') is not False:
            changes['start_paused_enabled'] = False
            
        if changes:
            logging.info(f"Applying forced settings: {changes}")
            client.app.set_preferences(prefs=changes)
    except Exception as e:
        logging.error(f"Error forcing settings: {e}")

def auto_sequential():
    """Enables sequential download for active torrents."""
    client = get_client()
    if not client: return

    try:
        # Get active downloads
        torrents = client.torrents_info(status_filter='downloading')
        for t in torrents:
            if not t.get('seq_dl'):
                logging.info(f"Enabling Sequential for: {t.get('name')[:30]}...")
                client.torrents_toggle_sequential_download(torrent_hashes=t.get('hash'))
    except Exception as e:
        logging.error(f"Error in auto_sequential: {e}")

logging.info("Starting qBittorrent Automation Script v2...")

# Run once immediately
force_settings()
auto_sequential()

# Schedule
schedule.every(5).seconds.do(auto_sequential)
schedule.every(30).seconds.do(force_settings)

while True:
    schedule.run_pending()
    time.sleep(1)
