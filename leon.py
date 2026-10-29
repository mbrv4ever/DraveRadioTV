# -*- coding: utf-8 -*-
# DraveRadio & TV - Copyright (C) 2026 Dravenlock (Roger & Claudio).
"""leon.py - Leon (neuvoice) zegt de naam van de zender. Wordt bewaard, zodat elke naam maar een keer gemaakt hoeft."""
import hashlib
import os
import re
import threading
import wave

_tts = None
_stijl = None
_sr = 44100
_lock = threading.Lock()
status = "uit"           # uit | laden | klaar | geen


def _laad():
    global _tts, _stijl, _sr, status
    if _tts is not None or status == "geen":
        return _tts is not None
    with _lock:
        if _tts is not None:
            return True
        try:
            status = "laden"
            from neuvoice import TTS
            _tts = TTS(auto_download=True)
            namen = list(getattr(_tts, "voice_style_names", []) or [])
            _stijl = _tts.get_voice_style("Leon" if "Leon" in namen else namen[0])
            _sr = int(getattr(_tts, "sample_rate", 44100) or 44100)
            status = "klaar"
            return True
        except Exception:
            status = "geen"
            return False


def spreekbaar(t):
    t = re.sub(r"\b(\d+)\s?[kK]\b", r"\1", t)
    t = t.replace("&", " en ").replace("NPO", "N P O").replace("TV", "tee vee").replace("FM", "ef em")
    t = re.sub(r"[_|/\\\[\](){}]+", " ", t)
    return re.sub(r"\s+", " ", t).strip()


def maak(tekst, map_):
    """Maakt (of vindt) een wav-bestand met Leon. Geeft het pad terug, of None."""
    os.makedirs(map_, exist_ok=True)
    pad = os.path.join(map_, hashlib.md5(tekst.encode("utf-8")).hexdigest()[:16] + ".wav")
    if os.path.exists(pad):
        return pad
    if not _laad():
        return None
    try:
        import numpy as np
        wav, _ = _tts.synthesize(spreekbaar(tekst), voice_style=_stijl, total_steps=10, speed=0.88, lang="nl")
        x = np.asarray(wav, dtype=np.float32).flatten()
        stil = np.zeros(int(_sr * 0.2), np.float32)              # even stilte vooraf: Leon begint niet gehaast
        x = np.concatenate([stil, x, stil[: len(stil) // 2]])
        x = x / (np.max(np.abs(x)) or 1) * 0.9
        with wave.open(pad, "wb") as w:
            w.setnchannels(1)
            w.setsampwidth(2)
            w.setframerate(_sr)
            w.writeframes((x * 32767).astype("<i2").tobytes())
        return pad
    except Exception:
        return None
