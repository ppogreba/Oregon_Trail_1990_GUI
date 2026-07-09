"""Minimal MML player for SONGS.TXT, using winsound.Beep on a background thread.

SONGS.TXT holds one MML-ish tune per line -- 18 lines, one per trail landmark, in
the same order as assets/mcga/p0.png..p17.png. This is not a full MML
implementation, just the subset actually used in the file: o/O (octave), l/L
(default length), t/T (tempo), </> (octave shift), '#'/'+' sharp, '-' flat,
p/r (rest), '.' (dotted). Unknown tokens ('k', '!') are consumed and ignored.
"""
from __future__ import annotations
import re
import threading

try:
    import winsound
    _HAVE_SOUND = True
except ImportError:                # pragma: no cover - non-Windows fallback
    _HAVE_SOUND = False

SEMITONE = {"c": 0, "d": 2, "e": 4, "f": 5, "g": 7, "a": 9, "b": 11}

_TOKEN = re.compile(r"""
    (?P<oct>[oO])(?P<octval>\d+)
  | (?P<len>[lL])(?P<lenval>\d+)
  | (?P<tempo>[tT])(?P<tempoval>\d+)
  | (?P<shift>[<>])
  | (?P<unk>[kK])(?P<kval>\d+)?
  | (?P<bang>!)
  | (?P<rest>[pPrR])(?P<restlen>\d+)?(?P<restdot>\.?)
  | (?P<note>[a-gA-G])(?P<acc>[#+\-]?)(?P<notelen>\d*)(?P<notedot>\.?)
""", re.VERBOSE)


def _parse(mml):
    """Yield (freq_hz_or_None, duration_ms) events; freq None means a rest."""
    octave, length, tempo = 4, 4, 120
    for m in _TOKEN.finditer(mml):
        if m.group("oct"):
            octave = int(m.group("octval"))
        elif m.group("len"):
            length = max(1, int(m.group("lenval")))
        elif m.group("tempo"):
            tempo = max(1, int(m.group("tempoval")))
        elif m.group("shift"):
            octave += 1 if m.group("shift") == ">" else -1
        elif m.group("unk") or m.group("bang"):
            pass
        elif m.group("rest"):
            n = int(m.group("restlen")) if m.group("restlen") else length
            dur = (60000 / tempo) * (4 / max(1, n))
            if m.group("restdot"):
                dur *= 1.5
            yield None, dur
        elif m.group("note"):
            acc = 1 if m.group("acc") in ("#", "+") else (-1 if m.group("acc") == "-" else 0)
            n = int(m.group("notelen")) if m.group("notelen") else length
            dur = (60000 / tempo) * (4 / max(1, n))
            if m.group("notedot"):
                dur *= 1.5
            midi = octave * 12 + SEMITONE[m.group("note").lower()] + acc
            freq = 440.0 * (2 ** ((midi - 57) / 12))     # A4 (midi 57 here) = 440 Hz
            yield freq, dur


_gen = 0
_lock = threading.Lock()


def play(mml, max_notes=250):
    """Play an MML tune on a background daemon thread. No-op without winsound."""
    global _gen
    if not _HAVE_SOUND or not mml:
        return
    with _lock:
        _gen += 1
        my_gen = _gen

    def worker():
        for i, (freq, dur) in enumerate(_parse(mml)):
            if _gen != my_gen or i > max_notes:
                return
            ms = max(1, int(dur))
            if freq:
                try:
                    winsound.Beep(min(32767, max(37, int(freq))), ms)
                except RuntimeError:
                    pass
            else:
                threading.Event().wait(ms / 1000)

    threading.Thread(target=worker, daemon=True).start()


def stop():
    global _gen
    with _lock:
        _gen += 1
