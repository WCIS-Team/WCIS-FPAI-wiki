"""Prepare shallow plugin caches and verify installed pins and generated titles."""

import json
from pathlib import Path
import re
import subprocess
import sys


def git(directory, *arguments):
    return subprocess.check_output(
        ["git", "-C", str(directory), *arguments], encoding="utf-8"
    ).strip()


def plugins(mode):
    root = Path.cwd().resolve()
    directory = root / ".quartz" / "plugins"
    entries = json.loads((root / "quartz.lock.json").read_text(encoding="utf-8"))["plugins"]
    checked = 0
    for name, entry in entries.items():
        expected = entry["commit"]
        if expected == "local":
            continue
        if not re.fullmatch(r"[0-9a-f]{40}", expected):
            raise RuntimeError(f"Invalid pinned commit for {name}")
        plugin = (directory / name).resolve()
        if not plugin.is_relative_to(directory.resolve()):
            raise RuntimeError(f"Plugin path escapes cache: {name}")
        if mode == "prepare":
            if plugin.is_dir() and git(plugin, "rev-parse", "HEAD") != expected:
                # Quartz v5 fetches only origin HEAD when updating a shallow cache.
                # Fetch the exact object first so its subsequent reset can succeed.
                subprocess.run(
                    ["git", "-C", str(plugin), "fetch", "--depth=1", "origin", expected],
                    check=True,
                )
                print(f"Prepared pinned object: {name}@{expected[:7]}")
        else:
            if not plugin.is_dir():
                raise RuntimeError(f"Missing plugin: {name}")
            actual = git(plugin, "rev-parse", "HEAD")
            if actual != expected:
                raise RuntimeError(f"Plugin revision mismatch: {name}: {actual} != {expected}")
            if not (plugin / "dist" / "index.js").is_file():
                raise RuntimeError(f"Missing built plugin: {name}")
            checked += 1
    if mode == "verify":
        print(f"Verified {checked} pinned plugin revisions and build outputs")


def output():
    index = json.loads(Path("public/static/contentIndex.json").read_text(encoding="utf-8"))
    prefixed = [slug for slug, entry in index.items() if entry.get("title", "").startswith("Folder: ")]
    if prefixed:
        raise RuntimeError(f"Unexpected folder title prefixes: {prefixed}")
    print(f"Verified {len(index)} generated titles: no Folder: prefix")


def main():
    if len(sys.argv) != 2 or sys.argv[1] not in {"prepare", "verify", "output"}:
        raise SystemExit("Usage: check-plugins.py prepare|verify|output (inside Quartz checkout)")
    if sys.argv[1] == "output":
        output()
    else:
        plugins(sys.argv[1])


if __name__ == "__main__":
    main()
