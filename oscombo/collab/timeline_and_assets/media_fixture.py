"""Reproducibly generate the tiny, synthetic local media fixture.

Requires optional local PyAV, NumPy and OpenCV to regenerate the checked-in
fixture media. Normal setup/tests consume the fixed files and do not import
this module.
"""
from __future__ import annotations

import math
import wave
from fractions import Fraction
from pathlib import Path

import av
import cv2
import numpy as np


FPS = 25
WIDTH = 320
HEIGHT = 180
CLIPS = (
    ("clip_01.mp4", 150, "INTAKE", (62, 119, 77), "box", 25, 100),
    ("clip_02.mp4", 175, "WASH", (51, 110, 161), "water", 25, 125),
    ("clip_03.mp4", 125, "REUSE", (172, 139, 59), "shelf", 0, 75),
    ("clip_04.mp4", 125, "OUTTAKE", (80, 83, 88), "outtake", 25, 100),
)


def _frame(label: str, base: tuple[int, int, int], motion: str, index: int,
           action_start: int, action_end: int) -> np.ndarray:
    bgr = np.empty((HEIGHT, WIDTH, 3), dtype=np.uint8)
    active = action_start <= index < action_end
    bgr[:] = base if active else (40, 43, 45)
    if not active:
        slate = "LEADER / NO ACTION" if index < action_start else "TAIL / HOLD"
        cv2.putText(bgr, slate, (27, 94), cv2.FONT_HERSHEY_SIMPLEX, 0.65,
                    (220, 220, 215), 2, cv2.LINE_AA)
        cv2.putText(bgr, label, (18, 31), cv2.FONT_HERSHEY_SIMPLEX, 0.8,
                    (245, 245, 238), 2, cv2.LINE_AA)
        return bgr
    if motion in {"box", "wash"}:
        cv2.rectangle(bgr, (0, 138), (WIDTH, 179), (38, 45, 47), -1)
        x = 15 + (index * 3) % 230
        cv2.rectangle(bgr, (x, 88), (x + 62, 137), (180, 151, 107), -1)
        cv2.rectangle(bgr, (x + 25, 88), (x + 35, 137), (105, 94, 72), 2)
        if motion == "wash":
            for n in range(4):
                dx = (index * (n + 2) * 7) % WIDTH
                dy = 45 + ((index * 5 + n * 23) % 82)
                cv2.circle(bgr, (dx, dy), 3 + n % 2, (218, 220, 191), -1)
            cv2.rectangle(bgr, (0, 45), (WIDTH, 54), (89, 166, 208), -1)
    elif motion == "shelf":
        for y in (66, 125):
            cv2.rectangle(bgr, (28, y), (292, y + 7), (46, 55, 43), -1)
        for x in (56, 133, 211):
            cv2.rectangle(bgr, (x, 39 + (index // 9 % 2) * 4), (x + 42, 64), (80, 105, 69), -1)
            cv2.rectangle(bgr, (x, 99), (x + 42, 123), (137, 105, 66), -1)
    else:
        # Deliberately poorer composition: cramped, dark and slightly shifting.
        offset = (index % 3) - 1
        cv2.rectangle(bgr, (66 + offset, 72), (145 + offset, 137), (100, 97, 92), -1)
        cv2.line(bgr, (0, 20 + offset * 2), (WIDTH, 55 - offset * 2), (38, 38, 38), 4)
    cv2.putText(bgr, label, (18, 31), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (245, 245, 238), 2, cv2.LINE_AA)
    cv2.putText(bgr, f"TAKE {index // FPS + 1:02d}", (232, 166), cv2.FONT_HERSHEY_SIMPLEX,
                0.34, (235, 235, 225), 1, cv2.LINE_AA)
    return bgr


def generate_media(destination: str | Path) -> dict[str, str]:
    dest = Path(destination)
    dest.mkdir(parents=True, exist_ok=True)
    for filename, frame_count, label, base, motion, action_start, action_end in CLIPS:
        target = dest / filename
        container = av.open(str(target), mode="w", format="mp4")
        stream = container.add_stream("libx264", rate=FPS)
        stream.width, stream.height = WIDTH, HEIGHT
        stream.pix_fmt = "yuv420p"
        stream.options = {"preset": "ultrafast", "crf": "28", "threads": "1"}
        for i in range(frame_count):
            frame = av.VideoFrame.from_ndarray(
                _frame(label, base, motion, i, action_start, action_end), format="bgr24")
            frame.pts = i
            frame.time_base = Fraction(1, FPS)
            for packet in stream.encode(frame):
                container.mux(packet)
        for packet in stream.encode():
            container.mux(packet)
        container.close()

    audio_path = dest / "music_bed.wav"
    sample_rate, seconds = 48_000, 10
    with wave.open(str(audio_path), "wb") as wav:
        wav.setnchannels(2)
        wav.setsampwidth(2)
        wav.setframerate(sample_rate)
        samples = bytearray()
        for i in range(sample_rate * seconds):
            t = i / sample_rate
            fade = min(1.0, t * 3.0, (seconds - t) * 3.0)
            # A quiet three-note pad; identical left/right channels by design.
            signal = (math.sin(2 * math.pi * 220 * t) +
                      0.45 * math.sin(2 * math.pi * 277.18 * t) +
                      0.25 * math.sin(2 * math.pi * 329.63 * t))
            value = max(-32767, min(32767, int(signal * fade * 3800)))
            samples.extend(value.to_bytes(2, "little", signed=True) * 2)
        wav.writeframes(samples)
    return {path.name: __import__("hashlib").sha256(path.read_bytes()).hexdigest()
            for path in sorted(dest.iterdir()) if path.is_file()}


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Regenerate CDD-TLA-001 synthetic media fixture")
    parser.add_argument("destination", type=Path)
    args = parser.parse_args()
    for name, digest in generate_media(args.destination).items():
        print(f"{digest}  {name}")
