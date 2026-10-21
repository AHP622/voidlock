"""Short, gentle sounds synthesised in memory (no audio files needed).

Every style has the same four sounds (close = a blocked program was closed, reward, done, bell) so the rest of the program
only says *what* happened; the style decides how it sounds."""
import io
import math
import struct
import sys
import wave
from functools import lru_cache

RATE = 22050

# partials: [(frequency ratio, amplitude)]; wave: sine | square | tri; decay: bigger = shorter ring; attack in seconds
STYLES = {
    "soft": dict(partials=[(1, 1.0), (2, 0.22)], decay=3.4, attack=0.012, vol=0.28,
                 close=[(659.3, 0.22), (493.9, 0.55)], reward=[(523.3, 0.14), (659.3, 0.14), (784.0, 0.5)],
                 done=[(523.3, 0.2), (784.0, 0.7)], bell=[(880.0, 1.0)]),
    "bell": dict(partials=[(1, 1.0), (2, 0.22)], decay=3.4, attack=0.012, vol=0.4,
                 close=[(880.0, 1.0)], reward=[(523.3, 0.14), (659.3, 0.14), (784.0, 0.5)],
                 done=[(523.3, 0.2), (784.0, 0.7)], bell=[(880.0, 1.0)]),
    "chime": dict(partials=[(1, 1.0), (3, 0.28), (5, 0.1)], decay=4.2, attack=0.006, vol=0.26,
                  close=[(1046.5, 0.12), (1318.5, 0.12), (1568.0, 0.45)], reward=[(784.0, 0.1), (987.8, 0.1), (1174.7, 0.1), (1568.0, 0.5)],
                  done=[(1046.5, 0.16), (1568.0, 0.6)], bell=[(1318.5, 0.9)]),
    "marimba": dict(partials=[(1, 1.0), (4, 0.35), (10, 0.08)], decay=7.5, attack=0.003, vol=0.34,
                    close=[(392.0, 0.18), (523.3, 0.4)], reward=[(392.0, 0.12), (494.0, 0.12), (587.3, 0.12), (784.0, 0.4)],
                    done=[(440.0, 0.15), (659.3, 0.45)], bell=[(587.3, 0.6)]),
    "zen": dict(partials=[(1, 1.0), (2.76, 0.3), (5.4, 0.1)], decay=2.2, attack=0.03, vol=0.3,
                close=[(261.6, 1.2)], reward=[(261.6, 0.5), (392.0, 1.1)], done=[(293.7, 0.6), (440.0, 1.2)], bell=[(220.0, 1.6)]),
    "crystal": dict(partials=[(1, 1.0), (2.4, 0.3), (4.1, 0.12)], decay=3.0, attack=0.004, vol=0.22,
                    close=[(1568.0, 0.16), (1174.7, 0.55)], reward=[(1046.5, 0.1), (1318.5, 0.1), (1568.0, 0.1), (2093.0, 0.5)],
                    done=[(1318.5, 0.18), (1976.0, 0.6)], bell=[(1760.0, 0.9)]),
    "pulse": dict(partials=[(1, 1.0), (3, 0.33), (5, 0.2), (7, 0.14)], decay=5.0, attack=0.004, vol=0.2,
                  close=[(440.0, 0.09), (330.0, 0.09), (220.0, 0.28)], reward=[(330.0, 0.08), (440.0, 0.08), (660.0, 0.3)],
                  done=[(440.0, 0.1), (660.0, 0.3)], bell=[(660.0, 0.5)]),
    "arcade": dict(partials=[(1, 1.0), (3, 0.33), (5, 0.2), (7, 0.14), (9, 0.11)], decay=1.4, attack=0.002, vol=0.16,
                   close=[(784.0, 0.07), (659.3, 0.07), (523.3, 0.07), (392.0, 0.22)],
                   reward=[(523.3, 0.07), (659.3, 0.07), (784.0, 0.07), (1046.5, 0.25)], done=[(659.3, 0.08), (988.0, 0.3)],
                   bell=[(1046.5, 0.3)]),
    "drop": dict(partials=[(1, 1.0), (2, 0.12)], decay=6.0, attack=0.004, vol=0.3, sweep=0.55,
                 close=[(900.0, 0.16), (620.0, 0.3)], reward=[(500.0, 0.1), (700.0, 0.1), (1000.0, 0.3)],
                 done=[(600.0, 0.12), (1000.0, 0.34)], bell=[(800.0, 0.4)]),
}
STYLE_ORDER = ("off", "soft", "bell", "chime", "marimba", "zen", "crystal", "pulse", "arcade", "drop")
KINDS = ("close", "bell", "reward", "done")


def _tone(freq, dur, style):
    n = int(RATE * dur)
    parts, decay, attack, sweep = style["partials"], style["decay"], style["attack"], style.get("sweep", 0.0)
    norm = sum(a for _r, a in parts) or 1.0
    out = []
    phase = 0.0
    for i in range(n):
        t = i / RATE
        env = min(1.0, t / attack) * math.exp(-decay * t / dur) * (1.0 if t < dur - 0.02 else max(0.0, (dur - t) / 0.02))
        f = freq * (1.0 - sweep * (t / dur) * 0.5) if sweep else freq
        phase += 2 * math.pi * f / RATE
        s = sum(a * math.sin(phase * r) for r, a in parts if r * f < RATE / 2)
        out.append(int(32767 * style["vol"] * env * s / norm))
    return out


@lru_cache(maxsize=64)
def wav_bytes(kind="close", style_name="soft"):
    style = STYLES.get(style_name, STYLES["soft"])
    data = []
    for freq, dur in style.get(kind, style["close"]):
        data += _tone(freq, dur, style)
    buf = io.BytesIO()
    with wave.open(buf, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(RATE)
        w.writeframes(struct.pack("<%dh" % len(data), *data))
    return buf.getvalue()


def _wav_file(kind, style_name):
    """winsound cannot play memory buffers asynchronously, so the sound is cached as a temp file."""
    import os
    import tempfile
    path = os.path.join(tempfile.gettempdir(), f"voidlock2_{style_name}_{kind}.wav")
    if not os.path.exists(path) or os.path.getsize(path) == 0:
        tmp = f"{path}.{os.getpid()}.tmp"          # written whole, then renamed: the guard and the UI both use it
        with open(tmp, "wb") as f:
            f.write(wav_bytes(kind, style_name))
        os.replace(tmp, path)
    return path


def play(kind="close", mode="soft"):
    """mode: off | one of STYLES. Returns True if a sound was started."""
    if mode == "off" or sys.platform != "win32":
        return False
    try:
        import winsound
        style = mode if mode in STYLES else "soft"
        kind = kind if kind in KINDS else "close"
        winsound.PlaySound(_wav_file(kind, style), winsound.SND_FILENAME | winsound.SND_ASYNC)
        return True
    except Exception:
        return False
