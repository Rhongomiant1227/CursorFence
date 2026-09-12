import unittest

import updater


class UpdaterTests(unittest.TestCase):
    def test_version_tuple_and_newer_comparison(self) -> None:
        self.assertEqual(updater.version_tuple("v1.2.3"), (1, 2, 3))
        self.assertTrue(updater.is_newer_version("0.2.3", "v0.2.4"))
        self.assertFalse(updater.is_newer_version("0.2.4", "v0.2.4"))
        self.assertFalse(updater.is_newer_version("0.2.4", "v0.2.3"))

    def test_invalid_versions_are_ignored(self) -> None:
        self.assertIsNone(updater.version_tuple("nightly"))
        self.assertFalse(updater.is_newer_version("0.2.3", "nightly"))

    def test_release_download_url_is_scoped_to_repository(self) -> None:
        self.assertTrue(updater.DOWNLOAD_HOST_PREFIX.startswith("https://github.com/"))
        self.assertIn("Rhongomiant1227/CursorFence", updater.DOWNLOAD_HOST_PREFIX)
        official = "https://github.com/Rhongomiant1227/CursorFence/releases/download/v0.3.0/CursorFence-Installer.exe"
        self.assertTrue(updater._is_official_download_url(official))
        self.assertFalse(updater._is_official_download_url(official + "?download=1"))
        self.assertFalse(updater._is_official_download_url(official.replace("github.com", "example.com")))
        self.assertFalse(updater._is_official_download_url(official.replace("CursorFence-Installer.exe", "CursorFence-Portable.exe")))


if __name__ == "__main__":
    unittest.main()
