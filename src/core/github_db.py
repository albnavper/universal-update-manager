"""
Universal Update Manager - GitHub App Database
Maps known applications to their GitHub repositories for auto-detection.
"""

from dataclasses import dataclass
from typing import Optional
import re


@dataclass
class GitHubAppInfo:
    """Information about a known GitHub-hosted application."""
    name: str
    repo: str
    asset_pattern: str
    desktop_patterns: list[str]  # Patterns to match .desktop file names
    executable_patterns: list[str]  # Patterns to match executable names
    install_type: str = "deb"  # deb, appimage, tarball


# Database of known GitHub applications
# This allows auto-detection of apps without manual onboarding
GITHUB_APP_DATABASE: list[GitHubAppInfo] = [
    # Communication
    GitHubAppInfo(
        name="Telegram Desktop",
        repo="telegramdesktop/tdesktop",
        asset_pattern=r"tsetup\.\d+.*\.tar\.xz",
        desktop_patterns=["telegram", "org.telegram"],
        executable_patterns=["telegram", "Telegram"],
        install_type="tarball",
    ),
    GitHubAppInfo(
        name="Signal Desktop",
        repo="signalapp/Signal-Desktop",
        asset_pattern=r"signal-desktop.*\.deb",
        desktop_patterns=["signal"],
        executable_patterns=["signal-desktop"],
        install_type="deb",
    ),
    GitHubAppInfo(
        name="Discord",
        repo="discord/discord",  # Note: Discord doesn't use GitHub releases
        asset_pattern=r"discord.*\.deb",
        desktop_patterns=["discord"],
        executable_patterns=["discord", "Discord"],
        install_type="deb",
    ),
    
    # Productivity
    GitHubAppInfo(
        name="Obsidian",
        repo="obsidianmd/obsidian-releases",
        asset_pattern=r"obsidian.*\.deb",
        desktop_patterns=["obsidian"],
        executable_patterns=["obsidian"],
        install_type="deb",
    ),
    GitHubAppInfo(
        name="Anki",
        repo="ankitects/anki",
        asset_pattern=r"anki-.*-linux-qt6\.tar\.zst",
        desktop_patterns=["anki"],
        executable_patterns=["anki"],
        install_type="tarball",
    ),
    GitHubAppInfo(
        name="Xournal++",
        repo="xournalpp/xournalpp",
        asset_pattern=r"xournalpp.*\.deb",
        desktop_patterns=["xournalpp", "com.github.xournalpp"],
        executable_patterns=["xournalpp"],
        install_type="deb",
    ),
    GitHubAppInfo(
        name="Mark Text",
        repo="marktext/marktext",
        asset_pattern=r"marktext.*\.deb",
        desktop_patterns=["marktext"],
        executable_patterns=["marktext"],
        install_type="deb",
    ),
    GitHubAppInfo(
        name="Joplin",
        repo="laurent22/joplin",
        asset_pattern=r"Joplin.*\.AppImage",
        desktop_patterns=["joplin"],
        executable_patterns=["joplin", "Joplin"],
        install_type="appimage",
    ),
    GitHubAppInfo(
        name="Logseq",
        repo="logseq/logseq",
        asset_pattern=r"Logseq.*\.AppImage",
        desktop_patterns=["logseq"],
        executable_patterns=["logseq", "Logseq"],
        install_type="appimage",
    ),
    
    # Development
    GitHubAppInfo(
        name="Visual Studio Code",
        repo="microsoft/vscode",
        asset_pattern=r"code.*\.deb",
        desktop_patterns=["code", "visual-studio-code"],
        executable_patterns=["code"],
        install_type="deb",
    ),
    GitHubAppInfo(
        name="GitKraken",
        repo="axosoft/gitkraken",  # Note: Uses own download server
        asset_pattern=r"gitkraken.*\.deb",
        desktop_patterns=["gitkraken"],
        executable_patterns=["gitkraken"],
        install_type="deb",
    ),
    GitHubAppInfo(
        name="Insomnia",
        repo="Kong/insomnia",
        asset_pattern=r"Insomnia.*\.deb",
        desktop_patterns=["insomnia"],
        executable_patterns=["insomnia"],
        install_type="deb",
    ),
    GitHubAppInfo(
        name="Postman",
        repo="postmanlabs/postman-app-support",
        asset_pattern=r"postman.*\.tar\.gz",
        desktop_patterns=["postman"],
        executable_patterns=["Postman"],
        install_type="tarball",
    ),
    
    # Media
    GitHubAppInfo(
        name="OBS Studio",
        repo="obsproject/obs-studio",
        asset_pattern=r"OBS.*\.deb",
        desktop_patterns=["obs", "com.obsproject"],
        executable_patterns=["obs"],
        install_type="deb",
    ),
    GitHubAppInfo(
        name="Kdenlive",
        repo="KDE/kdenlive",
        asset_pattern=r"kdenlive.*\.AppImage",
        desktop_patterns=["kdenlive"],
        executable_patterns=["kdenlive"],
        install_type="appimage",
    ),
    
    # Utilities
    GitHubAppInfo(
        name="Flameshot",
        repo="flameshot-org/flameshot",
        asset_pattern=r"flameshot.*\.deb",
        desktop_patterns=["flameshot"],
        executable_patterns=["flameshot"],
        install_type="deb",
    ),
    GitHubAppInfo(
        name="Bitwarden",
        repo="bitwarden/clients",
        asset_pattern=r"Bitwarden.*\.deb",
        desktop_patterns=["bitwarden"],
        executable_patterns=["bitwarden"],
        install_type="deb",
    ),
    GitHubAppInfo(
        name="1Password",
        repo="1Password/1password-teams-open-source",
        asset_pattern=r"1password.*\.deb",
        desktop_patterns=["1password"],
        executable_patterns=["1password"],
        install_type="deb",
    ),
    GitHubAppInfo(
        name="LocalSend",
        repo="localsend/localsend",
        asset_pattern=r"LocalSend.*\.deb",
        desktop_patterns=["localsend"],
        executable_patterns=["localsend"],
        install_type="deb",
    ),
    GitHubAppInfo(
        name="AppImageLauncher",
        repo="TheAssassin/AppImageLauncher",
        asset_pattern=r"appimagelauncher.*\.deb",
        desktop_patterns=["appimagelauncher"],
        executable_patterns=["AppImageLauncher"],
        install_type="deb",
    ),
    
    # Browsers
    GitHubAppInfo(
        name="Brave Browser",
        repo="brave/brave-browser",
        asset_pattern=r"brave-browser.*\.deb",
        desktop_patterns=["brave", "brave-browser"],
        executable_patterns=["brave-browser", "brave"],
        install_type="deb",
    ),
    GitHubAppInfo(
        name="Vivaldi",
        repo="nickvdyck/vivaldi-release",  # Unofficial tracker
        asset_pattern=r"vivaldi.*\.deb",
        desktop_patterns=["vivaldi"],
        executable_patterns=["vivaldi"],
        install_type="deb",
    ),
    
    # Gaming
    GitHubAppInfo(
        name="Lutris",
        repo="lutris/lutris",
        asset_pattern=r"lutris.*\.deb",
        desktop_patterns=["lutris"],
        executable_patterns=["lutris"],
        install_type="deb",
    ),
    GitHubAppInfo(
        name="ProtonUp-Qt",
        repo="DavidoTek/ProtonUp-Qt",
        asset_pattern=r"ProtonUp-Qt.*\.AppImage",
        desktop_patterns=["protonup"],
        executable_patterns=["protonup"],
        install_type="appimage",
    ),
]


def find_matching_github_app(
    desktop_file_name: Optional[str] = None,
    executable_name: Optional[str] = None,
    app_name: Optional[str] = None,
) -> list[GitHubAppInfo]:
    """
    Find GitHub apps that match the given criteria.
    
    Args:
        desktop_file_name: Name of the .desktop file
        executable_name: Name of the executable
        app_name: Display name of the application
        
    Returns:
        List of matching GitHubAppInfo objects (may be multiple for ambiguous matches)
    """
    matches = []
    
    for app in GITHUB_APP_DATABASE:
        score = 0
        
        # Check desktop file patterns
        if desktop_file_name:
            desktop_lower = desktop_file_name.lower()
            for pattern in app.desktop_patterns:
                if pattern.lower() in desktop_lower:
                    score += 2
                    break
        
        # Check executable patterns
        if executable_name:
            exe_lower = executable_name.lower()
            for pattern in app.executable_patterns:
                if pattern.lower() in exe_lower or exe_lower in pattern.lower():
                    score += 2
                    break
        
        # Check app name (fuzzy match)
        if app_name:
            app_name_lower = app_name.lower()
            db_name_lower = app.name.lower()
            
            # Exact match
            if app_name_lower == db_name_lower:
                score += 5
            # Contains match
            elif app_name_lower in db_name_lower or db_name_lower in app_name_lower:
                score += 3
            # Word match
            else:
                for word in app_name_lower.split():
                    if len(word) > 3 and word in db_name_lower:
                        score += 1
        
        if score > 0:
            matches.append((score, app))
    
    # Sort by score descending
    matches.sort(key=lambda x: x[0], reverse=True)
    return [app for score, app in matches]


def get_all_known_apps() -> list[GitHubAppInfo]:
    """Get all apps in the database."""
    return GITHUB_APP_DATABASE.copy()


def get_app_by_repo(repo: str) -> Optional[GitHubAppInfo]:
    """Find an app by its GitHub repo."""
    repo_lower = repo.lower()
    for app in GITHUB_APP_DATABASE:
        if app.repo.lower() == repo_lower:
            return app
    return None
