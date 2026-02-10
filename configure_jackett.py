
import requests
import json
import time

# Jackett Configuration
JACKETT_URL = "http://192.168.1.132:9117"
API_KEY = "d2ffpmovb2snm9trzthqmkhzxf8ks5po"

# List of popular public trackers to add
indexers = [
    "1337x", "acgrip", "anidex", "badass", "bitru", "bitsearch",
    "btdig", "btetree", "concen", "darklibria", "demonoid", "divxtotal",
    "dodi-repacks", "eztv", "fitgirl-repacks",
    "gtdb", "horriblesubs", "idope", "ilcorsaronero",
    "kickasstorrents-to", "leechers-paradise", "lime-torrents", "linuxtracker",
    "mikan", "nyaa-pantsu", "nyaasi", "rarbg", "rutor",
    "showrss", "solidtorrents", "subsplease", "tokyotoshokan",
    "torrent-downloads", "torrent9", "torrentfunk", "torrentgalaxy",
    "torrentproject2", "torrentz2eu", "yts", "zooqle"
]

print(f"Configuring Jackett at {JACKETT_URL}...")

def configure_indexer(indexer_id):
    url = f"{JACKETT_URL}/api/v2.0/indexers/{indexer_id}/config"
    headers = {'X-Api-Key': API_KEY, 'Content-Type': 'application/json'}
    # Empty config usually works for public trackers to just 'add' them
    data = [] 
    
    try:
        response = requests.post(url, headers=headers, json=data, timeout=10)
        if response.status_code == 204: # Success, no content
            print(f"[OK] Added {indexer_id}")
        elif response.status_code == 400: # Already added or config needed
             # Some might need config, we skip those for now or print error
             print(f"[SKIP] {indexer_id} (Already added or needs config)")
        else:
            print(f"[FAIL] {indexer_id}: {response.status_code}")
    except Exception as e:
        print(f"[ERROR] {indexer_id}: {e}")

print(f"Attempting to add {len(indexers)} public indexers...")

for idx in indexers:
    configure_indexer(idx)
    time.sleep(0.5) # Be gentle

print("\nConfiguration complete.")

