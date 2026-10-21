"""Self-update from GitHub Releases. No Qt here.

Flow: read the latest release of `owner/repo`, compare its tag (v1.2.0) with our version, download the
asset `VoidLock.exe`, verify it against the release's `VoidLock.exe.sha256`, then swap the file in place
(a running exe can be renamed on Windows) and restart. Nothing is installed without a matching checksum.
"""
import hashlib
import json
import os
import re
import shutil
import sys
import urllib.error
import urllib.request
from pathlib import Path
from urllib.parse import urlparse

from . import __version__

API = "https://api.github.com/repos/{repo}/releases/latest"
ASSET = "VoidLock.exe"
HOSTS = ("github.com", "githubusercontent.com")
HEADERS = {"User-Agent": "VoidLock-Updater", "Accept": "application/vnd.github+json"}
MAX_DOWNLOAD = 400 * 1024 * 1024          # a program file larger than this is not ours


class _SafeRedirect(urllib.request.HTTPRedirectHandler):
    """GitHub redirects downloads to its own CDN. Anything else is refused (the first URL was checked, the redirect
    target used to be followed blindly)."""

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        _safe_url(newurl)
        return super().redirect_request(req, fp, code, msg, headers, newurl)


_opener = urllib.request.build_opener(_SafeRedirect)
urlopen = _opener.open                    # indirection so tests can fake the network


class UpdateError(Exception):
    pass


def parse_version(s):
    nums = re.findall(r"\d+", (s or "").split("-")[0])
    return tuple(int(x) for x in nums[:4]) or (0,)


def is_newer(tag, current=__version__):
    return parse_version(tag) > parse_version(current)


def valid_repo(repo):
    return bool(re.fullmatch(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+", repo or ""))


def _safe_url(u):
    p = urlparse(u)
    host = (p.hostname or "").lower()
    if p.scheme != "https" or not any(host == h or host.endswith("." + h) for h in HOSTS):
        raise UpdateError(f"Refusing to download from {host or 'an unknown host'}.")
    return u


def check(repo, timeout=10):
    """Returns info dict for a newer release, or None when up to date."""
    if not valid_repo(repo):
        raise UpdateError("Update source must look like owner/repo.")
    try:
        with urlopen(urllib.request.Request(API.format(repo=repo), headers=HEADERS), timeout=timeout) as r:
            data = json.load(r)
    except urllib.error.HTTPError as e:
        if e.code == 404:
            raise UpdateError("No release found. Check the repository name and that it has a published release.")
        if e.code == 403:
            raise UpdateError("GitHub refused the request (rate limit). Try again later.")
        raise UpdateError(f"GitHub returned an error ({e.code}).")
    except (urllib.error.URLError, OSError, ValueError) as e:
        raise UpdateError(f"Could not reach GitHub: {e}")
    tag = data.get("tag_name", "")
    if not is_newer(tag):
        return None
    assets = {a.get("name"): a for a in data.get("assets", [])}
    exe, sha = assets.get(ASSET), assets.get(ASSET + ".sha256")
    if not exe:
        raise UpdateError(f"Release {tag} has no {ASSET} file.")
    if not sha:
        raise UpdateError(f"Release {tag} has no {ASSET}.sha256 file, so it cannot be verified.")
    return {"tag": tag, "version": ".".join(str(n) for n in parse_version(tag)),
            "url": _safe_url(exe["browser_download_url"]), "sha_url": _safe_url(sha["browser_download_url"]),
            "size": int(exe.get("size", 0)), "notes": (data.get("body") or "")[:600]}


def download(info, dest_dir, progress=None, timeout=30):
    """Download + verify. Returns the verified file path."""
    dest_dir = Path(dest_dir)
    dest_dir.mkdir(parents=True, exist_ok=True)
    try:
        with urlopen(urllib.request.Request(info["sha_url"], headers=HEADERS), timeout=timeout) as r:
            want = r.read(4096).decode("utf-8", "ignore").strip().split()[0].lower()
    except (urllib.error.URLError, OSError, IndexError) as e:
        raise UpdateError(f"Could not read the checksum: {e}")
    if not re.fullmatch(r"[0-9a-f]{64}", want):
        raise UpdateError("The checksum file is not a valid SHA-256.")
    part = dest_dir / (ASSET + ".part")
    h = hashlib.sha256()
    done = 0
    try:
        with urlopen(urllib.request.Request(info["url"], headers=HEADERS), timeout=timeout) as r, open(part, "wb") as f:
            total = int(r.headers.get("Content-Length", 0) or info.get("size", 0))
            if total > MAX_DOWNLOAD:
                raise UpdateError("The update file is unreasonably large - update cancelled.")
            while True:
                chunk = r.read(1 << 16)
                if not chunk:
                    break
                if done + len(chunk) > MAX_DOWNLOAD:
                    raise UpdateError("The update file is unreasonably large - update cancelled.")
                f.write(chunk)
                h.update(chunk)
                done += len(chunk)
                if progress and total:
                    progress(int(done * 100 / total))
    except UpdateError:
        _fail_cleanup(part)
        raise
    except (urllib.error.URLError, OSError, ValueError) as e:
        _fail_cleanup(part)
        raise UpdateError(f"Download failed: {e}")
    if h.hexdigest() != want:
        part.unlink(missing_ok=True)
        raise UpdateError("The downloaded file does not match its checksum - update cancelled.")
    with open(part, "rb") as f:
        if f.read(2) != b"MZ":
            part.unlink(missing_ok=True)
            raise UpdateError("The downloaded file is not a Windows program.")
    final = dest_dir / ASSET
    os.replace(part, final)
    return final


def _fail_cleanup(part):
    try:
        Path(part).unlink(missing_ok=True)
    except OSError:
        pass


def apply(new_path, target=None):
    """Swap the running exe for the new one. Rolls back on failure."""
    target = Path(target or sys.executable)
    old = target.with_name(target.name + ".old")
    try:
        old.unlink(missing_ok=True)
    except OSError:
        old = target.with_name(target.name + ".old2")
        try:
            old.unlink(missing_ok=True)
        except OSError as e:
            raise UpdateError(f"Could not prepare the update (an older copy is still in use): {e}")
    try:
        os.replace(target, old)
    except OSError as e:
        raise UpdateError(f"Could not replace the program file: {e}")
    try:
        shutil.move(str(new_path), str(target))
    except Exception as e:
        os.replace(old, target)
        raise UpdateError(f"Could not install the update: {e}")
    return target


def cleanup_old(target=None):
    target = Path(target or sys.executable)
    for suffix in (".old", ".old2"):
        try:
            target.with_name(target.name + suffix).unlink(missing_ok=True)
        except OSError:
            pass   # still used by the previous guard process; removed on a later start
