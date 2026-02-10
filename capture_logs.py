
import subprocess
import time

log_file = "/home/mint/qbittorrent_startup.log"
cmd = ["/home/mint/Applications/qbittorrent-beta.AppImage"]

print(f"Launching qBittorrent and capturing output to {log_file}...")
with open(log_file, "w") as f:
    process = subprocess.Popen(cmd, stdout=f, stderr=subprocess.STDOUT)
    
    # Wait for startup (plugins load on start or first search tab open)
    time.sleep(15) 
    
    process.terminate()
    try:
        process.wait(timeout=5)
    except:
        process.kill()

print("Log capture complete.")
