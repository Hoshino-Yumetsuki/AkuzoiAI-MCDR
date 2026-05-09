#!/usr/bin/env python3
# requires-python = ">=3.13"
# dependencies = ["mcdreforged"]

"""
Build script: packs the plugin into a .mcdr file under dist/.

Usage:
    uv run build.py
"""
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).parent
DIST = ROOT / "dist"


def main() -> None:
    DIST.mkdir(exist_ok=True)
    cmd = [
        sys.executable, "-m", "mcdreforged", "pack",
        "-i", str(ROOT),
        "-o", str(DIST),
    ]
    print(f"Running: {' '.join(cmd)}")
    result = subprocess.run(cmd, cwd=ROOT)
    if result.returncode != 0:
        sys.exit(result.returncode)

    # Print the output file
    mcdr_files = sorted(DIST.glob("*.mcdr"))
    if mcdr_files:
        print(f"\nBuilt: {mcdr_files[-1]}")


if __name__ == "__main__":
    main()
