
import json
import re
from pathlib import Path

CONFIG_PATH = Path("/home/mint/scripts/Linux Mint/universal-update-manager/config/sources.json")

def clean_repo(repo):
    if "github.com/" in repo:
        match = re.search(r"github\.com/([^/]+/[^/]+)", repo)
        if match:
            return match.group(1).rstrip("/")
    return repo

def clean_config():
    if not CONFIG_PATH.exists():
        print("Config not found")
        return

    with open(CONFIG_PATH, 'r') as f:
        data = json.load(f)

    if 'github' not in data or 'packages' not in data['github']:
        print("No github packages found")
        return

    packages = data['github']['packages']
    unique_map = {}
    
    print(f"Found {len(packages)} packages. Cleaning...")

    # Process in order, later entries overwrite earlier ones (deduplication)
    for pkg in packages:
        # Sanitize repo
        old_repo = pkg.get('repo', '')
        new_repo = clean_repo(old_repo)
        if old_repo != new_repo:
            print(f"Fixed repo: {old_repo} -> {new_repo}")
            pkg['repo'] = new_repo

        # Key for deduplication: id
        pkg_id = pkg['id']
        unique_map[pkg_id] = pkg

    # Reconstruct list
    cleaned_packages = list(unique_map.values())
    print(f"Reduced to {len(cleaned_packages)} unique packages")

    data['github']['packages'] = cleaned_packages

    with open(CONFIG_PATH, 'w') as f:
        json.dump(data, f, indent=2)
    
    print("Config saved.")

if __name__ == "__main__":
    clean_config()
