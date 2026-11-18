"""Used by release.cmd: checks that every place that carries the version agrees, and prints the version.
Exit code 1 (with the reasons on stderr) when something is out of step. Run: python tools/release_check.py"""
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def read(rel):
    return (ROOT / rel).read_text(encoding="utf-8")


def main():
    problems = []
    m = re.search(r'__version__\s*=\s*"([^"]+)"', read("voidlock/__init__.py"))
    if not m:
        print("Could not find __version__ in voidlock/__init__.py", file=sys.stderr)
        return 1
    ver = m.group(1)
    parts = ver.split(".")
    if len(parts) != 3 or not all(p.isdigit() for p in parts):
        problems.append(f"the version '{ver}' is not like 1.14.70")
    else:
        code = f"{int(parts[0])}{int(parts[1]):03d}{int(parts[2]):03d}"
        g = read("android/app/build.gradle.kts")
        n = re.search(r'VOIDLOCK_VERSION_NAME"\)\s*\?:\s*"([^"]+)"', g)
        c = re.search(r'VOIDLOCK_VERSION_CODE"\)\s*\?:\s*"(\d+)"', g)
        if not n or n.group(1) != ver:
            problems.append(f"android/app/build.gradle.kts has version name {n.group(1) if n else '?'} (expected {ver})")
        if not c or c.group(1) != code:
            problems.append(f"android/app/build.gradle.kts has version code {c.group(1) if c else '?'} (expected {code})")
        j = re.search(r'version:\s*"([^"]+)"', read("android/app/src/main/assets/www/config.js"))
        if not j or j.group(1) != ver:
            problems.append(f"android/.../www/config.js has version {j.group(1) if j else '?'} (expected {ver})")
    if not re.search(rf"^## {re.escape(ver)}\s*$", read("CHANGELOG.md"), re.M):
        problems.append(f'CHANGELOG.md has no "## {ver}" section')
    if f'"{ver}": (' not in read("voidlock/intro.py"):
        problems.append(f'voidlock/intro.py has no "What\'s new" entry for {ver}')
    if problems:
        print("The version is not the same everywhere:", file=sys.stderr)
        for p in problems:
            print("  - " + p, file=sys.stderr)
        return 1
    print(ver)
    return 0


if __name__ == "__main__":
    sys.exit(main())
