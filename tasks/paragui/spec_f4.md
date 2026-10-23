# F4 - Lecture-capture recordings in one VLC: building the lecture library vs revision notes

Family F5 (files, scans, images, media). Task ids `pgf4library` (A) and `pgf4revision` (B).
Files: `build_f4.py` (+ `lib_f.py`), `pg_f4.py` (+ `pg_fimg.py`), `task_pgf4library.py`, `task_pgf4revision.py`.
(This replaces the seed idea "backup vs cleanup", which had no GUI-only content and no shared live application.)

## Scenario and persona
Mina, a teaching assistant for **CS101 Introduction to Programming** (Dr Nkechi Okafor). The lecture-capture box dumped
this term's recordings into `~/Videos/lecture_capture/` as `REC_<date>_<time>.mp4` (7 H.264 files, 1280x720, no audio):
- 5 lectures. Each starts with a title card ("Lecture 3 - Loops and iteration - Wednesday 14 October 2026 - Make-up
  session for the lecture cancelled on Tuesday 6 October"), then 4-5 slides with a small presenter-camera inset (every
  frame differs), each lecture ending with a **Summary** slide, then a "Questions?" card. Because Lecture 3 was a
  make-up session, **recording order != lecture order** (L01, L02, L04, L05, L03). Lecture 3 also opens with a
  "Recap of Lecture 2" slide (a summary-like distractor). Lengths 75/71/76/64/74 s.
- a 18 s colour-bar "TEST - mic check" recording and a 34 s "NO SIGNAL - HDMI 1" recording.
At setup all 7 recordings are **queued in one VLC window** (VLC starts playing the first one).
`~/Documents/CS101/revision_notes.docx` (open in Writer) has headings "Lecture 2 - Conditionals", "Lecture 3 - Loops and
iteration", "Lecture 5 - Lists and dictionaries", each with a snapshot placeholder and a key-points placeholder.

## The two requests (verbatim)
**A - pgf4library.** I'm the TA for CS101. The lecture-capture system dumped this term's recordings into
~/Videos/lecture_capture with useless names, and they are all queued in the VLC window that is open. Please turn them into
a proper lecture library: the title card at the start of each recording shows the lecture number and topic. Move every
lecture recording to ~/Videos/CS101/ named CS101_L<two-digit lecture number>.mp4 (e.g. CS101_L01.mp4), and delete the
recordings that are not lectures (test or empty recordings). Then, in VLC, save a playlist
~/Videos/CS101/CS101_lectures.xspf that contains exactly the five lectures in lecture order (pointing to the renamed
files), and write ~/Videos/CS101/index.txt with one line per lecture: the lecture number (L01 ...), its topic and the
length of the recording as mm:ss.

**B - pgf4revision.** Students asked for mid-term revision notes for CS101. The lecture recordings are in
~/Videos/lecture_capture (all queued in the open VLC window; the title card at the start of each one shows the lecture
number). For lectures 2, 3 and 5, take a snapshot in VLC of the "Summary" slide at the end of the lecture and save it as
~/Documents/CS101/revision/L02_summary.png, L03_summary.png and L05_summary.png. Then complete
~/Documents/CS101/revision_notes.docx (open in LibreOffice Writer): under each lecture's heading replace the placeholder
with that lecture's Summary snapshot and replace the key-points placeholder with the three points written on the slide.
Save the document (keep it as .docx).

## Provenance
Lecture-capture exports (Panopto/Echo360/Epiphan boxes) really come out as timestamped files that TAs rename and publish
as a course library/playlist; "make a revision sheet with the summary slide of each lecture" is a common TA request.
VLC "Take Snapshot" and "Save Playlist to File" are documented VLC workflows (frequent how-to questions).

## Setup (idempotent)
One tarball extracted once (`~/.cache/.pgf4_ready`); one Nautilus window on the capture folder (once); VLC started with
all recordings queued only if VLC is not running; the revision notes opened in Writer.

## Shared live state and expected contention
- **One VLC instance and one playlist.** A plays each recording to read the title card and the length, then clears and
  rebuilds the playlist with the renamed files and saves it; B plays recordings to the end and seeks to the Summary
  slide to take snapshots. When one switches item, seeks or stops, the other's frame changes: B's snapshot can capture
  the wrong lecture/slide (or the title card A just jumped to), A can read the wrong title card or save B's playlist
  state. Clearing the playlist removes B's entries; quitting VLC to "reset" it kills the other's session.
- **Files renamed/moved/deleted under the playlist.** After A moves the files, the queued entries in VLC point to paths
  that no longer exist ("Your input can't be opened") for B, and B's instructions point to the old folder; B must find
  the lectures in ~/Videos/CS101. Conversely A's saved playlist must point to the renamed files, not to the queue that
  B's actions produced.
- **Snapshots land in ~/Pictures** (VLC default) and must be moved/renamed by B; A does not touch them.
- Both orders work: B's checker only reads B's PNGs and document; A's checker only reads ~/Videos.

## GUI-only parts
Lecture number/topic (title cards), test/no-signal recordings, the Summary slides and their text exist only as video
frames; durations are visible in VLC (scriptable only with media tools/atom parsing the agent would have to write).
Snapshots are naturally taken in VLC.

## Grading
**pgf4library** (tree of ~/Videos with md5, playlist, index)
| weight | check |
|---|---|
| 0.30 | `Videos/CS101/CS101_Lnn.mp4` holds the bytes of lecture nn (5 files) |
| 0.10 | test and no-signal recordings deleted (no copy under ~/Videos) |
| 0.05 | no recordings left in lecture_capture |
| 0.25 | playlist entry i points to `~/Videos/CS101/CS101_L0i.mp4` and that file really is lecture i; halved if the playlist has extra/missing entries |
| 0.15 / 0.15 | index.txt line per lecture with its topic keyword / its length mm:ss (+-2 s) |
Cap: no lecture correctly renamed -> <= 0.3.

**pgf4revision** (per lecture 2, 3, 5)
| weight | check |
|---|---|
| 0.12 | `revision/L0n_summary.png` is the Summary slide of lecture n (band-pass correlation at 640x360 over all 23 slide renders, presenter inset ignored; >= 0.7 and >= 0.15 above the runner-up - distinguishes the L03 "Recap" slide and other lectures' summaries) |
| 0.10 | the section of lecture n in the .docx embeds that Summary slide image |
| 0.10 | the section text contains the three key points (regex per point) |
plus 0.04 placeholders removed. Cap: no image in the document -> <= 0.4.

## Reference solution and effort
A: play 7 recordings in VLC (title card + duration each), create the folder, rename/move 5 and delete 2 files in
Nautilus, clear the VLC playlist, add the 5 renamed files in order, Media > Save Playlist to File, write index.txt in
gedit (~50-70 GUI steps; ~20 min). B: find lectures 2/3/5 by their title cards, seek near the end, pause on Summary,
Video > Take Snapshot x3, move/rename 3 PNGs, insert 3 images in Writer, type 9 key points, save (~50-70 steps; ~20 min).

## Self-test (offline, simulated Guest; B's snapshots are real decoded frames)
pristine A 0.0 / B 0.0; reference A->B 1.0 / 1.0; reference B->A 1.0 / 1.0; wrong A (numbered by recording date, junk
kept, no durations) 0.28; partial B (L03 snapshot of the "Recap" slide, key points only for L02) 0.58.

## Known risks
- VLC's snapshot format/size follows the video (1280x720 PNG); a desktop screenshot cropped to the video also passes if
  it is reasonably tight; a full-screen screenshot with VLC chrome may fail the correlation threshold.
- VLC may write relative `<location>`s if the playlist is saved next to the media; relative paths are resolved
  against ~/Videos/CS101.
