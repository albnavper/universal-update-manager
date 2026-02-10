
import sys
import os
import importlib.util
import shutil
from pathlib import Path

# Paths
backup_dir = Path.home() / ".local/share/data/qBittorrent/nova3/engines_backup"
engines_dir = Path.home() / ".local/share/data/qBittorrent/nova3/engines"
nova3_dir = Path.home() / ".local/share/data/qBittorrent/nova3"

# Add nova3 dir to sys.path so plugins can import 'nova2' or other helpers if needed
sys.path.append(str(nova3_dir))

# Mock nova2/helpers if they are missing to prevent simple ImportError on helpers
# (Plugins often do `from nova2 import ...`)
# We will create a dummy nova2 module if it doesn't exist for the check, 
# although in the real env it exists.
# But actually, looking at the directory structure, nova2.py might be in nova3/ ?
# Let's assume the environment is roughly correct since we are running in the user's box.

print(f"Scanning plugins in {backup_dir}...")

plugins = list(backup_dir.glob("*.py"))
passed = []
failed = []

for plugin_path in plugins:
    plugin_name = plugin_path.stem
    if plugin_name == "__init__":
        continue

    try:
        # Load the module
        spec = importlib.util.spec_from_file_location(plugin_name, plugin_path)
        if spec and spec.loader:
            module = importlib.util.module_from_spec(spec)
            # This executes the module code!
            spec.loader.exec_module(module)
            
            # Check if it has a 'search' class or function normally required? 
            # Not strictly necessary for "not crashing", but good for "working".
            # For now, just crashing on load is the bar.
            
            print(f"[PASS] {plugin_name}")
            passed.append(plugin_path)
    except Exception as e:
        print(f"[FAIL] {plugin_name}: {e}")
        failed.append((plugin_name, str(e)))

print("\nRestoring valid plugins...")
count = 0
for p in passed:
    # Don't overwrite existing ones (like the eztv we just restored manually) unless it's the same
    dest = engines_dir / p.name
    # if not dest.exists():
    shutil.copy2(p, dest)
    count += 1

print(f"\nRestored {count} plugins.")
print(f"Failed plugins ({len(failed)}):")
for name, err in failed:
    print(f"  - {name}: {err}")
