"""Short, gentle sounds synthesised in memory (no audio files needed)."""
import io
import math
import struct
import sys
import wave
from functools import lru_cache

RATE = 22050
KINDS = {
    "close": [(659.3, 0.22), (493.9, 0.55)],          # soft two-note descent (E5 -> B4)
    "bell": [(880.0, 1.0)],
    "reward": [(523.3, 0.14), (659.3, 0.14), (784.0, 0.5)],
    "done": [(523.3, 0.2), (784.0, 0.7)],
}


def _samples(freq, dur, vol):
    n = int(RATE * dur)
    out = []
    for i in range(n):
        t = i / RATE
        env = min(1.0, t / 0.012) * math.exp(-3.4 * t / dur) * (1.0 if t < dur - 0.02 else (dur - t) / 0.02)
        s = math.sin(2 * math.pi * freq * t) + 0.22 * math.sin(2 * math.pi * freq * 2 * t)
        out.append(int(32767 * vol * env * s / 1.22))
    return out


@lru_cache(maxsize=16)
def wav_bytes(kind="close", vol=0.28):
    data = []
    for freq, dur in KINDS.get(kind, KINDS["close"]):
        data += _samples(freq, dur, vol)
    buf = io.BytesIO()
    with wave.open(buf, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(RATE)
        w.writeframes(struct.pack("<%dh" % len(data), *data))
    return buf.getvalue()


def play(kind="close", mode="soft"):
    """mode: off | soft | bell. Returns True if a sound was started."""
    if mode == "off" or sys.platform != "win32":
        return False
    try:
        import winsound
        if mode == "bell" and kind == "close":
            kind = "bell"
        winsound.PlaySound(wav_bytes(kind, 0.4 if mode == "bell" else 0.28), winsound.SND_MEMORY | winsound.SND_ASYNC)
        return True
    except Exception:
        return False
