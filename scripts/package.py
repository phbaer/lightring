#!/usr/bin/env python3
"""Build a HACS-compatible release archive."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile

ROOT = Path(__file__).resolve().parents[1]
COMPONENT_PATH = ROOT / "custom_components" / "waterrower_ble"
MANIFEST_PATH = COMPONENT_PATH / "manifest.json"


def build_package(output_directory: Path) -> Path:
    """Create a ZIP whose root contains the custom_components directory."""
    manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    version = manifest["version"]
    output_directory.mkdir(parents=True, exist_ok=True)
    archive = output_directory / "waterrower_local_ble.zip"

    with ZipFile(archive, "w", ZIP_DEFLATED) as zip_file:
        for file_path in sorted(COMPONENT_PATH.rglob("*")):
            if not file_path.is_file() or "__pycache__" in file_path.parts:
                continue
            zip_file.write(file_path, file_path.relative_to(ROOT))
        zip_file.write(ROOT / "hacs.json", "hacs.json")

    return archive


def main() -> None:
    """Build the package selected by the command line."""
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=ROOT / "dist")
    arguments = parser.parse_args()
    print(build_package(arguments.output))


if __name__ == "__main__":
    main()
