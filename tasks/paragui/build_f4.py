"""F4 assets - a course's lecture-capture recordings: building the lecture library vs making revision notes.

Writes into out_dir:
  capture/REC_<date>_<time>.mp4    7 H.264 recordings (1280x720, 10 fps, no audio): 5 lectures (recorded out of
                                   order: L03 was a make-up session after L05), a "TEST" colour-bar recording, a no-signal one
  revision_notes.docx              the revision-sheet template (headings + placeholders)
  summary_L0n.png                  reference renders of the Summary slides (host only, used by the checker)
  f4.tar.gz                        recordings + template in Guest layout, extracted once by setup
  expected.json                    ground truth - host only
"""
from __future__ import annotations

import json
import os
import subprocess
import tarfile

import numpy as np
from PIL import Image, ImageDraw

from lib_f import font, md5

VW, VH, FPS = 1280, 720, 10
COURSE = "CS101 Introduction to Programming"
LECTURER = "Dr Nkechi Okafor"
# lecture no: (topic, lecture date, recording file stamp, seconds per slide list, slides)
LECTURES = {
    1: ("Welcome and Python basics", "2026-09-29", "2026-09-29_0931",
        [("What is a program?", ["A program is a sequence of instructions", "Python runs them top to bottom",
                                 "The interpreter reports errors with a line number"]),
         ("Values and types", ["int, float, str, bool", "type(42) -> <class 'int'>", "Types decide which operations work"]),
         ("Variables", ["A variable is a name for a value", "x = 3   then   x = x + 1", "Names are case-sensitive"]),
         ("Input and output", ["print('Hello', name)", "age = int(input('Age? '))", "input() always returns a string"]),
         ("Summary", ["Programs are sequences of statements", "Variables name values; every value has a type",
                      "Use print() and input() for simple I/O"])]),
    2: ("Conditionals", "2026-10-01", "2026-10-01_0929",
        [("Last time", ["Values, types and variables", "print() and input()"]),
         ("Boolean expressions", ["Comparisons: == != < > <= >=", "Combine with and / or / not", "Result is True or False"]),
         ("if statements", ["if temperature > 30:", "    print('Hot!')", "The indented block runs only if True"]),
         ("elif and else", ["if / elif / else picks exactly one branch", "Order matters: first True wins",
                            "else catches everything left"]),
         ("Summary", ["if / elif / else chooses one branch", "Comparisons evaluate to True or False",
                      "Indentation defines the block"])]),
    3: ("Loops and iteration", "2026-10-14", "2026-10-14_1402",
        [("Recap of Lecture 2", ["if / elif / else", "Boolean expressions", "Indentation"]),
         ("for loops", ["for item in sequence:", "range(5) -> 0 1 2 3 4", "Loop over strings and lists"]),
         ("while loops", ["while condition:", "Repeats until the condition is False", "Beware of infinite loops"]),
         ("break and continue", ["break leaves the loop immediately", "continue skips to the next iteration",
                                 "Use them sparingly"]),
         ("Summary", ["for loops iterate over a sequence", "while loops repeat until the condition is False",
                      "break exits a loop early, continue skips ahead"])]),
    4: ("Functions", "2026-10-08", "2026-10-08_0931",
        [("Why functions?", ["Avoid repeating code", "Give a name to an idea", "Test small pieces"]),
         ("Defining a function", ["def area(w, h):", "    return w * h", "Call it: area(3, 4) -> 12"]),
         ("Scope", ["Variables inside a function are local", "Parameters are local too", "Globals: read, don't modify"]),
         ("Summary", ["def defines a reusable function", "Parameters are inputs, return gives the output",
                      "Local variables exist only inside the function"])]),
    5: ("Lists and dictionaries", "2026-10-13", "2026-10-13_0930",
        [("Lists", ["nums = [3, 1, 4]", "nums.append(1)  nums[0]  len(nums)", "Slicing: nums[1:3]"]),
         ("Dictionaries", ["ages = {'Ana': 21, 'Ben': 19}", "ages['Ana'] -> 21", "ages['Cy'] = 20 adds a key"]),
         ("Looping over collections", ["for n in nums:", "for name, age in ages.items():", "sorted(ages)"]),
         ("Membership", ["'Ana' in ages  -> True", "4 in nums -> True", "Fast for dicts, slow for long lists"]),
         ("Summary", ["Lists are ordered and mutable", "Dictionaries map keys to values",
                      "Use in to test membership"])]),
}
SLIDE_SECONDS = {1: [12, 13, 12, 13, 14], 2: [8, 13, 12, 13, 14], 3: [9, 14, 14, 13, 15], 4: [12, 14, 13, 14],
                 5: [11, 13, 12, 13, 14]}
TITLE_S, END_S = 6, 5
EXTRA = [("test", "2026-10-06_0855", 18), ("nosignal", "2026-10-08_0915", 34)]
REVISION_LECTURES = [2, 3, 5]
KEYPOINTS = {  # regexes the typed key points must match (one per bullet of the Summary slide)
    2: [r"elif", r"true\s*or\s*false|true/false|boolean", r"indent"],
    3: [r"for\b.*(iterat|sequence)|(iterat|sequence).*\bfor\b", r"while\b.*(until|false)", r"break"],
    5: [r"lists?\b.*(ordered|mutable)", r"dict.*(key|map)", r"\bin\b.*member|member.*\bin\b"],
}


def slide_image(lec: int, title: str, bullets: list, k: int, n: int) -> Image.Image:
    im = Image.new("RGB", (VW, VH), (250, 250, 252))
    d = ImageDraw.Draw(im)
    d.rectangle((0, 0, VW, 96), fill=(28, 52, 104))
    d.text((48, 48), title, fill="white", font=font("lato-black", 46), anchor="lm")
    d.text((VW - 40, 48), f"CS101 - L{lec:02d}", fill=(190, 205, 235), font=font("lato-bold", 26), anchor="rm")
    y = 170
    for b in bullets:
        mono = any(ch in b for ch in "=()[]{}:") and not b.endswith(".")
        f = font("mono", 34) if mono else font("lato", 38)
        d.ellipse((60, y + 14, 74, y + 28), fill=(28, 52, 104))
        d.text((100, y), b, fill=(25, 25, 30), font=f)
        y += 92
    d.text((48, VH - 36), f"{LECTURER} - {COURSE}", fill=(120, 120, 130), font=font("lato", 22), anchor="lm")
    d.text((VW - 40, VH - 36), f"{k}/{n}", fill=(120, 120, 130), font=font("lato", 22), anchor="rm")
    return im


def title_card(lec: int, topic: str, date: str, note: str | None) -> Image.Image:
    import datetime as dt
    im = Image.new("RGB", (VW, VH), (28, 52, 104))
    d = ImageDraw.Draw(im)
    d.text((VW // 2, 200), COURSE, fill=(190, 205, 235), font=font("lato-bold", 40), anchor="mm")
    d.text((VW // 2, 320), f"Lecture {lec}", fill="white", font=font("lato-black", 84), anchor="mm")
    d.text((VW // 2, 420), topic, fill="white", font=font("lato-bold", 54), anchor="mm")
    day = dt.date.fromisoformat(date)
    d.text((VW // 2, 530), f"{LECTURER}  -  {day.strftime('%A')} {day.day} {day.strftime('%B %Y')}",
           fill=(190, 205, 235), font=font("lato", 32), anchor="mm")
    if note:
        d.text((VW // 2, 600), note, fill=(250, 210, 90), font=font("lato-bold", 30), anchor="mm")
    return im


def end_card() -> Image.Image:
    im = Image.new("RGB", (VW, VH), (28, 52, 104))
    d = ImageDraw.Draw(im)
    d.text((VW // 2, 300), "Questions?", fill="white", font=font("lato-black", 80), anchor="mm")
    d.text((VW // 2, 420), "Office hours Thursday 14:00-15:00, room B2.17", fill=(190, 205, 235),
           font=font("lato", 36), anchor="mm")
    return im


def webcam(frame: Image.Image, t: float):
    """Small presenter inset bottom-right that changes every frame (so stills differ slightly)."""
    d = ImageDraw.Draw(frame)
    x0, y0, w, h = VW - 250, VH - 210, 220, 150
    d.rectangle((x0, y0, x0 + w, y0 + h), fill=(70, 80, 90), outline=(20, 20, 20), width=3)
    cx = x0 + w / 2 + 40 * np.sin(t * 0.7)
    d.ellipse((cx - 22, y0 + 30, cx + 22, y0 + 74), fill=(150, 100, 70))
    d.rounded_rectangle((cx - 45, y0 + 78, cx + 45, y0 + h), radius=18, fill=(180, 60, 60))


def encode(frames_iter, path: str):
    p = subprocess.Popen(["ffmpeg", "-loglevel", "error", "-y", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{VW}x{VH}",
                          "-r", str(FPS), "-i", "-", "-c:v", "libx264", "-preset", "medium", "-crf", "30", "-threads", "1",
                          "-pix_fmt", "yuv420p", "-movflags", "+faststart", "-metadata", "title=Lecture capture",
                          path], stdin=subprocess.PIPE)
    n = 0
    for fr in frames_iter:
        p.stdin.write(fr.tobytes())
        n += 1
    p.stdin.close()
    assert p.wait() == 0, path
    return n


def lecture_frames(lec: int):
    topic, date, _, slides = LECTURES[lec]
    note = "Make-up session for the lecture cancelled on Tuesday 6 October" if lec == 3 else None
    segs = [(title_card(lec, topic, date, note), TITLE_S, False)]
    n = len(slides)
    for k, ((title, bullets), sec) in enumerate(zip(slides, SLIDE_SECONDS[lec]), 1):
        segs.append((slide_image(lec, title, bullets, k, n), sec, True))
    segs.append((end_card(), END_S, False))
    t = 0.0
    for img, sec, cam in segs:
        for _ in range(sec * FPS):
            fr = img.copy()
            if cam:
                webcam(fr, t)
            t += 1 / FPS
            yield fr


def extra_frames(kind: str, sec: int):
    if kind == "test":
        bars = Image.new("RGB", (VW, VH))
        d = ImageDraw.Draw(bars)
        cols = [(192, 192, 192), (192, 192, 0), (0, 192, 192), (0, 192, 0), (192, 0, 192), (192, 0, 0), (0, 0, 192)]
        for i, c in enumerate(cols):
            d.rectangle((i * VW // 7, 0, (i + 1) * VW // 7, VH * 2 // 3), fill=c)
        d.rectangle((0, VH * 2 // 3, VW, VH), fill=(20, 20, 20))
        d.text((VW // 2, VH * 5 // 6), "TEST - mic check, room B1.04", fill="white", font=font("lato-black", 44), anchor="mm")
        for _ in range(sec * FPS):
            yield bars
    else:
        rng = np.random.default_rng(7)
        base = Image.new("RGB", (VW, VH), (4, 4, 6))
        ImageDraw.Draw(base).text((VW - 30, VH - 30), "NO SIGNAL - HDMI 1", fill=(60, 60, 70), font=font("lato", 22), anchor="rb")
        a0 = np.asarray(base, np.int16)
        for i in range(sec * FPS):
            a = np.clip(a0 + rng.integers(-3, 4, a0.shape[:2])[..., None], 0, 255).astype(np.uint8)
            yield Image.fromarray(a)


def revision_doc(path):
    from docx import Document
    from docx.shared import Pt
    doc = Document()
    doc.add_heading("CS101 - Mid-term revision notes", 0)
    doc.add_paragraph("For each lecture: the Summary slide from the recording and its three key points.")
    for lec in REVISION_LECTURES:
        doc.add_heading(f"Lecture {lec} - {LECTURES[lec][0]}", 1)
        doc.add_paragraph("[insert snapshot of the Summary slide here]")
        p = doc.add_paragraph("Key points: [type the three key points here]")
        p.runs[0].font.size = Pt(12)
    doc.save(path)


def build(d: str):
    os.makedirs(f"{d}/capture", exist_ok=True)
    recs = []
    for lec, (topic, date, stamp, slides) in LECTURES.items():
        name = f"REC_{stamp}.mp4"
        n = encode(lecture_frames(lec), f"{d}/capture/{name}")
        recs.append({"name": name, "kind": "lecture", "lecture": lec, "topic": topic, "date": date,
                     "seconds": n / FPS, "md5": md5(f"{d}/capture/{name}")})
        slides_n = len(slides)
        summary = slide_image(lec, "Summary", slides[-1][1], slides_n, slides_n)
        summary.save(f"{d}/summary_L{lec:02d}.png")
        for k, (t, b) in enumerate(slides[:-1], 1):  # the other slides, to make sure the snapshot is the right one
            slide_image(lec, t, b, k, slides_n).save(f"{d}/slide_L{lec:02d}_{k}.png")
    for kind, stamp, sec in EXTRA:
        name = f"REC_{stamp}.mp4"
        n = encode(extra_frames(kind, sec), f"{d}/capture/{name}")
        recs.append({"name": name, "kind": kind, "seconds": n / FPS, "md5": md5(f"{d}/capture/{name}")})
    revision_doc(f"{d}/revision_notes.docx")
    with tarfile.open(f"{d}/f4.tar.gz", "w:gz") as tf:
        tf.add(f"{d}/capture", arcname="Videos/lecture_capture")
        tf.add(f"{d}/revision_notes.docx", arcname="Documents/CS101/revision_notes.docx")
    json.dump({"recordings": sorted(recs, key=lambda r: r["name"]), "revision": REVISION_LECTURES,
               "keypoints": {str(k): v for k, v in KEYPOINTS.items()},
               "summaries": {str(k): LECTURES[k][3][-1][1] for k in LECTURES}},
              open(f"{d}/expected.json", "w"), indent=1)
