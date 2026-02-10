"""
Tests for core.version — version comparison utilities.
"""

import sys
from pathlib import Path

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

import unittest
from core.version import normalize_version, compare_versions, is_newer, is_older_or_equal


class TestNormalizeVersion(unittest.TestCase):
    """Tests for normalize_version()."""

    def test_simple_semver(self):
        self.assertEqual(normalize_version("1.2.3"), [1, 2, 3])

    def test_v_prefix(self):
        self.assertEqual(normalize_version("v1.2.3"), [1, 2, 3])

    def test_two_part(self):
        self.assertEqual(normalize_version("1.2"), [1, 2])

    def test_year_based(self):
        self.assertEqual(normalize_version("2024.1.3"), [2024, 1, 3])

    def test_with_prerelease(self):
        # Should extract numeric parts only
        result = normalize_version("1.2.3-beta")
        self.assertEqual(result, [1, 2, 3])

    def test_with_rc(self):
        result = normalize_version("5.0.0-rc1")
        self.assertEqual(result, [5, 0, 0, 1])

    def test_unknown(self):
        self.assertEqual(normalize_version("unknown"), [0])

    def test_none_string(self):
        self.assertEqual(normalize_version("none"), [0])

    def test_empty(self):
        self.assertEqual(normalize_version(""), [0])

    def test_none_value(self):
        self.assertEqual(normalize_version(None), [0])

    def test_single_number(self):
        self.assertEqual(normalize_version("42"), [42])


class TestCompareVersions(unittest.TestCase):
    """Tests for compare_versions()."""

    def test_equal(self):
        self.assertEqual(compare_versions("1.0.0", "1.0.0"), 0)

    def test_greater(self):
        self.assertEqual(compare_versions("1.1.0", "1.0.0"), 1)

    def test_lesser(self):
        self.assertEqual(compare_versions("1.0.0", "1.1.0"), -1)

    def test_patch_difference(self):
        self.assertEqual(compare_versions("1.0.1", "1.0.0"), 1)

    def test_major_difference(self):
        self.assertEqual(compare_versions("2.0.0", "1.9.9"), 1)

    def test_different_lengths(self):
        # 1.0 should equal 1.0.0
        self.assertEqual(compare_versions("1.0", "1.0.0"), 0)

    def test_different_lengths_not_equal(self):
        self.assertEqual(compare_versions("1.0.1", "1.0"), 1)

    def test_v_prefixed(self):
        self.assertEqual(compare_versions("v1.2.0", "1.1.0"), 1)

    def test_both_v_prefixed(self):
        self.assertEqual(compare_versions("v1.2.0", "v1.2.0"), 0)

    def test_year_based_versions(self):
        self.assertEqual(compare_versions("2024.2.0", "2024.1.0"), 1)

    def test_unknown_vs_version(self):
        self.assertEqual(compare_versions("1.0.0", "unknown"), 1)

    def test_both_unknown(self):
        self.assertEqual(compare_versions("unknown", "unknown"), 0)

    def test_prerelease_less_than_release(self):
        # packaging.version correctly treats beta as LESS than release
        self.assertEqual(compare_versions("1.2.3-beta", "1.2.3"), -1)


class TestIsNewer(unittest.TestCase):
    """Tests for is_newer()."""

    def test_newer(self):
        self.assertTrue(is_newer("2.0.0", "1.0.0"))

    def test_not_newer(self):
        self.assertFalse(is_newer("1.0.0", "2.0.0"))

    def test_same(self):
        self.assertFalse(is_newer("1.0.0", "1.0.0"))


class TestIsOlderOrEqual(unittest.TestCase):
    """Tests for is_older_or_equal()."""

    def test_older(self):
        self.assertTrue(is_older_or_equal("1.0.0", "2.0.0"))

    def test_equal(self):
        self.assertTrue(is_older_or_equal("1.0.0", "1.0.0"))

    def test_newer(self):
        self.assertFalse(is_older_or_equal("2.0.0", "1.0.0"))


if __name__ == "__main__":
    unittest.main()
