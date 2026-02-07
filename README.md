# Universal Update Manager

<div align="center">

![Version](https://img.shields.io/badge/version-0.0.1-blue)
![Platform](https://img.shields.io/badge/platform-Linux-green)
![Python](https://img.shields.io/badge/python-3.10+-yellow)
![License](https://img.shields.io/badge/license-GPL--3.0-purple)

**A unified update manager for all your Linux applications**

</div>

## ✨ Features

- **Multi-source Updates**: GitHub Releases, Flatpak, Snap, APT, JetBrains Toolbox
- **Auto-Detection**: Automatically detects 24+ popular apps (Telegram, Brave, OBS, Anki, etc.)
- **Security**: SHA256 checksum verification and automatic backups before updates
- **System Tray**: Always-on tray icon with update notifications
- **Update History**: Track all past updates with full details
- **Scheduled Checks**: Systemd timers for automatic background updates

## 📸 Screenshot

<div align="center">
<img src="docs/screenshot.png" width="600" alt="Universal Update Manager">
</div>

## 🚀 Installation

### Requirements
- Python 3.10+
- GTK4 and libadwaita
- notify-send (for notifications)

### Quick Start
```bash
# Clone the repository
git clone https://github.com/yourusername/universal-update-manager.git
cd universal-update-manager

# Install dependencies
pip install packaging

# Run
python3 main.py
```

### Desktop Entry
The app creates a `.desktop` file automatically on first run at:
`~/.local/share/applications/universal-update-manager.desktop`

## 📦 Supported Sources

| Source | Status | Description |
|--------|--------|-------------|
| **GitHub Releases** | ✅ | Auto-download .deb, .AppImage, tarballs |
| **Flatpak** | ✅ | Full integration with flatpak |
| **Snap** | ✅ | Snap store updates |
| **APT** | ✅ | Native Debian/Ubuntu packages |
| **JetBrains** | ✅ | IntelliJ, PyCharm, WebStorm, etc. |
| **Web Scraping** | ✅ | Custom version detection |

## ⚙️ Configuration

Configuration is stored in `config/sources.json`. The app will guide you through initial setup.

### Auto-Detected Apps
The following apps are automatically detected without configuration:
- Telegram, Signal, Discord
- Obsidian, Anki, Xournal++, Mark Text, Joplin
- VS Code, Insomnia, Postman
- OBS Studio, Kdenlive
- Brave, Vivaldi
- Bitwarden, 1Password, LocalSend
- And more...

## 🔐 Security

- **Checksum Verification**: SHA256 checksums calculated for all downloads
- **Backup System**: Automatic backups before installing updates (`~/.cache/uum/backups`)
- **Rollback**: Restore previous versions if updates fail

## 📅 Automatic Updates

Enable automatic update checking with systemd timers:

```python
from core.scheduler import Scheduler, ScheduleFrequency

scheduler = Scheduler()
scheduler.enable(ScheduleFrequency.DAILY)  # or HOURLY, WEEKLY
```

## 🛠️ Development

```bash
# Run with debug logging
python3 main.py --debug

# Run tests
python3 -m pytest tests/
```

## 📝 License

GPL-3.0 License - see [LICENSE](LICENSE) for details.

## 🤝 Contributing

Contributions are welcome! Please open an issue or pull request.

---

<div align="center">
Made with ❤️ for the Linux community
</div>
