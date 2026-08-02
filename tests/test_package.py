"""Tests for the HACS release archive."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from zipfile import ZipFile

ROOT = Path(__file__).resolve().parents[1]


class PackageTest(unittest.TestCase):
    """Verify the generated archive installs as a custom component."""

    def test_archive_has_component_at_hacs_path(self) -> None:
        """The release archive must retain the custom_components prefix."""
        with TemporaryDirectory() as temporary_directory:
            output_directory = Path(temporary_directory)
            subprocess.run(
                [sys.executable, "scripts/package.py", "--output", str(output_directory)],
                cwd=ROOT,
                check=True,
            )
            archive = output_directory / "waterrower_local_ble.zip"
            with ZipFile(archive) as zip_file:
                contents = set(zip_file.namelist())

        self.assertIn(
            "custom_components/waterrower_ble/manifest.json", contents
        )
        self.assertIn("custom_components/waterrower_ble/light.py", contents)
        self.assertIn("custom_components/waterrower_ble/services.yaml", contents)
        self.assertIn("hacs.json", contents)
        self.assertFalse(any("__pycache__" in path for path in contents))
