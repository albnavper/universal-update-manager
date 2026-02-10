"""
Tests for plugins.base — data classes and base plugin.
"""

import sys
from pathlib import Path

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

import unittest
from plugins.base import (
    SoftwareInfo,
    UpdateStatus,
    DownloadResult,
    InstallResult,
    UninstallResult,
    UpdateSourcePlugin,
)


class TestSoftwareInfo(unittest.TestCase):
    """Tests for SoftwareInfo dataclass."""

    def _make(self, **kwargs):
        defaults = dict(
            id="test-app",
            name="Test App",
            installed_version="1.0.0",
            latest_version=None,
            source_type="github",
            source_url="https://example.com",
            icon=None,
        )
        defaults.update(kwargs)
        return SoftwareInfo(**defaults)

    def test_has_update_true(self):
        s = self._make(status=UpdateStatus.UPDATE_AVAILABLE)
        self.assertTrue(s.has_update)

    def test_has_update_false(self):
        s = self._make(status=UpdateStatus.UP_TO_DATE)
        self.assertFalse(s.has_update)

    def test_display_version_no_update(self):
        s = self._make(status=UpdateStatus.UP_TO_DATE)
        self.assertEqual(s.display_version, "1.0.0")

    def test_display_version_with_update(self):
        s = self._make(
            latest_version="2.0.0",
            status=UpdateStatus.UPDATE_AVAILABLE,
        )
        self.assertEqual(s.display_version, "1.0.0 → 2.0.0")

    def test_default_status(self):
        s = self._make()
        self.assertEqual(s.status, UpdateStatus.UNKNOWN)


class TestDownloadResult(unittest.TestCase):
    """Tests for DownloadResult dataclass."""

    def test_success(self):
        r = DownloadResult(success=True, file_path=Path("/tmp/test.deb"))
        self.assertTrue(r.success)
        self.assertEqual(r.file_path, Path("/tmp/test.deb"))

    def test_failure(self):
        r = DownloadResult(success=False, error_message="Network error")
        self.assertFalse(r.success)
        self.assertEqual(r.error_message, "Network error")

    def test_download_url_field(self):
        """Verify the download_url field exists (added during audit)."""
        r = DownloadResult(success=True, download_url="https://example.com/file.deb")
        self.assertEqual(r.download_url, "https://example.com/file.deb")

    def test_defaults(self):
        r = DownloadResult(success=True)
        self.assertIsNone(r.file_path)
        self.assertIsNone(r.error_message)
        self.assertIsNone(r.download_url)
        self.assertIsNone(r.checksum)
        self.assertFalse(r.checksum_verified)


class TestInstallResult(unittest.TestCase):
    """Tests for InstallResult dataclass."""

    def test_success(self):
        r = InstallResult(success=True, new_version="2.0.0")
        self.assertTrue(r.success)
        self.assertEqual(r.new_version, "2.0.0")

    def test_failure(self):
        r = InstallResult(success=False, error_message="Permission denied")
        self.assertFalse(r.success)


class TestUninstallResult(unittest.TestCase):
    """Tests for UninstallResult dataclass."""

    def test_success(self):
        r = UninstallResult(success=True)
        self.assertTrue(r.success)

    def test_failure(self):
        r = UninstallResult(success=False, error_message="Package locked")
        self.assertFalse(r.success)


class TestUpdateSourcePluginDefaults(unittest.TestCase):
    """Tests for UpdateSourcePlugin default method behavior."""

    def test_uninstall_default_not_supported(self):
        """Default uninstall returns not-supported error."""

        class DummyPlugin(UpdateSourcePlugin):
            name = "dummy"
            source_type = "dummy"

            def get_tracked_software(self):
                return []

            def check_for_updates(self, s):
                return s

            def download_update(self, s):
                return DownloadResult(success=True)

            def install_update(self, s, d):
                return InstallResult(success=True)

        plugin = DummyPlugin()
        si = SoftwareInfo(
            id="x", name="x", installed_version="1",
            latest_version=None, source_type="dummy",
            source_url=None, icon=None,
        )
        result = plugin.uninstall(si)
        self.assertFalse(result.success)
        self.assertIn("not supported", result.error_message.lower())

    def test_cleanup_nonexistent_file(self):
        """cleanup() should not crash on nonexistent paths."""

        class DummyPlugin(UpdateSourcePlugin):
            name = "dummy"
            source_type = "dummy"

            def get_tracked_software(self):
                return []

            def check_for_updates(self, s):
                return s

            def download_update(self, s):
                return DownloadResult(success=True)

            def install_update(self, s, d):
                return InstallResult(success=True)

        plugin = DummyPlugin()
        dr = DownloadResult(success=True, file_path=Path("/nonexistent/file.tmp"))
        # Should not raise
        plugin.cleanup(dr)


if __name__ == "__main__":
    unittest.main()
