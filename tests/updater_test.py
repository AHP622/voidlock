"""Updater downloads on a bad line (voidlock/updater.py). Run: python tests/updater_test.py  (no network, no Qt)"""
import hashlib
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from voidlock import updater  # noqa: E402

DATA = b"MZ" + bytes(range(256)) * 80            # ~20 KB "program"
SHA = hashlib.sha256(DATA).hexdigest()


class Resp:
    def __init__(self, body, status=200, cut_after=None):
        self.body, self.pos, self.status, self.cut, self.sent = body, 0, status, cut_after, 0
        self.headers = {"Content-Length": str(len(body))}

    def __enter__(self): return self
    def __exit__(self, *a): pass
    def getcode(self): return self.status

    def read(self, n=-1):
        if self.cut is not None and self.sent >= self.cut:
            raise ConnectionResetError(10054, "An existing connection was forcibly closed by the remote host")
        n = len(self.body) - self.pos if n is None or n < 0 else n
        if self.cut is not None:
            n = min(n, self.cut - self.sent)
        chunk = self.body[self.pos:self.pos + n]
        self.pos += len(chunk)
        self.sent += len(chunk)
        return chunk


class Net:
    """Fake GitHub CDN: cuts every connection after `cut` bytes (None = never), honours Range, or refuses everything."""
    def __init__(self, cut=None, refuse=False, ranges=True):
        self.cut, self.refuse, self.ranges, self.connections = cut, refuse, ranges, 0

    def __call__(self, req, timeout=0):
        self.connections += 1
        if self.refuse:
            raise ConnectionResetError(10054, "forcibly closed")
        rng = req.headers.get("Range")
        if rng and self.ranges:
            start = int(rng.split("=")[1].split("-")[0])
            return Resp(DATA[start:], 206, self.cut)
        return Resp(DATA, 200, self.cut)


def info(sha=SHA):
    return {"tag": "v9.9.9", "version": "9.9.9", "url": "https://github.com/a/b/VoidLock.exe", "sha": sha,
            "sha_url": "", "size": len(DATA), "notes": ""}


class Download(unittest.TestCase):
    def setUp(self):
        self._u, self._s = updater.urlopen, updater.time.sleep
        updater.time.sleep = lambda x: None
        self.dir = Path(tempfile.mkdtemp())

    def tearDown(self):
        updater.urlopen, updater.time.sleep = self._u, self._s

    def test_a_line_that_resets_every_few_KB_still_finishes(self):
        updater.urlopen = Net(cut=1500)                 # ~14 resets: the old "4 tries" gave up long before
        p = updater.download(info(), self.dir)
        self.assertEqual(p.read_bytes(), DATA)
        self.assertGreater(updater.urlopen.connections, 10)
        self.assertEqual(list(self.dir.glob("*.part")), [])

    def test_a_clean_line_needs_one_connection(self):
        updater.urlopen = Net()
        self.assertEqual(updater.download(info(), self.dir).read_bytes(), DATA)
        self.assertEqual(updater.urlopen.connections, 1)

    def test_a_line_that_never_gives_a_byte_stops_after_6_tries_and_says_so(self):
        updater.urlopen = Net(refuse=True)
        with self.assertRaises(updater.UpdateError) as c:
            updater.download(info(), self.dir)
        self.assertEqual(updater.urlopen.connections, 6)
        self.assertIn("10054", str(c.exception))
        self.assertIn("Nothing was installed", str(c.exception))
        self.assertEqual(list(self.dir.glob("*")), [], "no half-file is left behind")

    def test_a_wrong_checksum_is_never_installed(self):
        updater.urlopen = Net()
        with self.assertRaises(updater.UpdateError):
            updater.download(info(sha="0" * 64), self.dir)
        self.assertFalse((self.dir / "VoidLock.exe").exists())

    def test_server_ignoring_range_cannot_loop_forever(self):
        updater.urlopen = Net(cut=1500, ranges=False)   # restarts from zero each time and never gets past 1500 bytes
        with self.assertRaises(updater.UpdateError):
            updater.download(info(), self.dir)
        self.assertLess(updater.urlopen.connections, 20)

    def test_curl_fallback_is_off_outside_windows(self):
        if sys.platform != "win32":
            self.assertFalse(updater._curl_fallback("https://github.com/x", self.dir / "x.part", 1, SHA, None))

    def test_curl_fallback_refuses_other_hosts(self):
        self.assertFalse(updater._curl_fallback("https://evil.example/x.exe", self.dir / "x.part", 1, SHA, None))


if __name__ == "__main__":
    unittest.main(verbosity=2)
