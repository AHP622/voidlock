"""Website blocking through the Windows hosts file (needs administrator rights)."""
import os
import re
import subprocess
import sys
from pathlib import Path

BEGIN = "# >>> VOIDLOCK BEGIN (managed automatically, do not edit) >>>"
END = "# <<< VOIDLOCK END <<<"
DOMAIN_RE = re.compile(r"^(?=.{4,253}$)([a-z0-9]([a-z0-9-]{0,61}[a-z0-9])?\.)+[a-z]{2,24}$")

# well-known extra hosts so one entry really blocks the whole site
EXTRA = {
    "youtube.com": ["m.youtube.com", "music.youtube.com", "youtu.be", "youtube-nocookie.com", "youtubei.googleapis.com"],
    "instagram.com": ["i.instagram.com", "cdninstagram.com"],
    "facebook.com": ["m.facebook.com", "fb.com"],
    "twitter.com": ["x.com", "mobile.twitter.com"],
    "x.com": ["twitter.com"],
    "telegram.org": ["web.telegram.org", "t.me", "telegram.me"],
    "tiktok.com": ["m.tiktok.com", "tiktokv.com"],
    "reddit.com": ["old.reddit.com", "redd.it"],
    "twitch.tv": ["m.twitch.tv"],
    "netflix.com": ["nflxvideo.net"],
    "aparat.com": ["www.aparat.com"],
}

PRESETS = [("YouTube", "youtube.com"), ("Instagram", "instagram.com"), ("Telegram Web", "telegram.org"),
           ("Aparat", "aparat.com"), ("Twitter / X", "x.com"), ("TikTok", "tiktok.com"),
           ("Facebook", "facebook.com"), ("Reddit", "reddit.com"), ("Twitch", "twitch.tv"),
           ("Netflix", "netflix.com")]


def normalize(text):
    """'https://www.YouTube.com/watch?v=1' -> 'youtube.com'. Returns '' if it is not a domain."""
    t = (text or "").strip().lower()
    t = re.sub(r"^[a-z]+://", "", t)
    t = t.split("/")[0].split("?")[0].split("#")[0].split(":")[0]
    if t.startswith("www."):
        t = t[4:]
    return t if DOMAIN_RE.match(t) else ""


def expand(domain):
    d = normalize(domain)
    if not d:
        return []
    out = [d, "www." + d] + EXTRA.get(d, [])
    seen, res = set(), []
    for h in out:
        if h not in seen:
            seen.add(h)
            res.append(h)
    return res


def build_block(domains):
    hosts = []
    for d in domains:
        for h in expand(d):
            if h not in hosts:
                hosts.append(h)
    lines = [BEGIN]
    for h in hosts:
        lines.append(f"0.0.0.0 {h}")
        lines.append(f":: {h}")
    lines.append(END)
    return "\n".join(lines) + "\n"


def apply_to_text(text, domains):
    """Return `text` with our block replaced (or removed when there are no domains). The file keeps its own line
    endings (the Windows hosts file uses CRLF; mixing them confuses some editors and tools)."""
    pat = re.compile(re.escape(BEGIN) + r".*?" + re.escape(END) + r"\r?\n?", re.S)
    base = pat.sub("", text)
    crlf = "\r\n" in text
    nl = "\r\n" if crlf else "\n"
    if base and not base.endswith("\n"):
        base += nl
    block = build_block(domains) if domains else ""
    if crlf:
        block = block.replace("\n", "\r\n")
    return base + block


def hosts_path():
    if os.environ.get("VOIDLOCK_HOSTS"):
        return Path(os.environ["VOIDLOCK_HOSTS"])
    return Path(os.environ.get("SystemRoot", r"C:\Windows")) / "System32" / "drivers" / "etc" / "hosts"


def write_hosts(domains, path=None, flush=True):
    """Rewrite the managed block. Returns (ok, message)."""
    path = Path(path or hosts_path())
    try:
        raw = path.read_bytes() if path.exists() else b""
        text = raw.decode("utf-8", errors="surrogateescape")
        new = apply_to_text(text, sorted(domains))
        if new == text:
            return True, "unchanged"
        bak = path.with_name(path.name + ".voidlock.bak")
        if path.exists() and not bak.exists():
            bak.write_bytes(raw)
        tmp = path.with_name(path.name + ".voidlock.tmp")
        try:
            tmp.write_bytes(new.encode("utf-8", errors="surrogateescape"))
            os.replace(tmp, path)
        except BaseException:
            try:
                tmp.unlink()
            except OSError:
                pass
            raise
        if flush and sys.platform == "win32":
            subprocess.run(["ipconfig", "/flushdns"], capture_output=True, creationflags=0x08000000)
        return True, "updated"
    except PermissionError:
        return False, "permission denied (administrator rights are required)"
    except OSError as e:
        return False, str(e)


def current_block_domains(path=None):
    path = Path(path or hosts_path())
    try:
        text = path.read_text(encoding="utf-8", errors="ignore")
    except OSError:
        return []
    m = re.search(re.escape(BEGIN) + r"(.*?)" + re.escape(END), text, re.S)
    if not m:
        return []
    return sorted({ln.split()[1] for ln in m.group(1).splitlines() if ln.startswith("0.0.0.0 ")})
