# Pair o4 - one Impress talk: advisor's handout comments vs. AV-team preparation

Family F1 (office documents). Tasks `pgo4comments` (A) and `pgo4avprep` (B). Files: `build_o4.py`, `pg_o4.py`
(helpers `pg_olib.py`, scans `lib_oscan.py`), `task_pgo4comments.py`, `task_pgo4avprep.py`.

## Scenario and persona

Lina Park, PhD student at the (fictional) Institute for Data Systems, gives a 15-minute talk "StreamJoin: Low-Latency
Joins over Bursty Data Streams" at the DSSW 2026 workshop. `~/Documents/Talk/StreamJoin_DSSW.pptx` (12 slides, 4:3,
title + bullet layouts, no notes) is open in Impress.

- **A**: her advisor annotated a printed 4-up handout in red pen (`handout_comments_MW.pdf`, 3 image-only pages):
  fix the title typo "Motivaton", strike the bullet "We assume a single-node setting", 82.1% -> 84.3%, CPU "Xeon 6248"
  -> "Xeon Gold 6338", swap the two results slides (throughput first), drop the backup slide "Parameter Sweep", add
  "Chen et al., VLDB 2025" to Related Work, add the code link github.com/lpark/streamjoin, closing slide "Thank You"
  -> "Questions?". Save, and export a slides PDF for the advisor.
- **B**: the institute's AV rules (`IDS_talk_rules.txt`): 16:9, speaker notes on every slide (text from her scanned
  speaker script `speaker_script.pdf`, 2 pages, one block per slide of the original deck), an "Acknowledgements" slide
  with the DFG grant PA 4471/2-1 right before the closing slide, save, export a notes-pages PDF.

Provenance: integrating an advisor's marked-up printout, converting an old 4:3 deck to 16:9 and adding speaker notes
for captioning / an AV team are standard conference-preparation chores (conference "speaker guidelines" pages ask for
16:9 and notes; "how to export notes pages to PDF in Impress" is a frequent Ask LibreOffice question).

## Requests (verbatim)

**A - pgo4comments**
> I'm Lina Park, a PhD student at the Institute for Data Systems. My advisor Markus went through a printout of my DSSW workshop talk and wrote his comments on it in red; the scan is ~/Documents/Talk/handout_comments_MW.pdf. Please make all of his changes in the presentation that is open in LibreOffice Impress (~/Documents/Talk/StreamJoin_DSSW.pptx), save it in place as .pptx, and export a PDF of the slides to ~/Documents/Talk/StreamJoin_DSSW_v2_for_Markus.pdf so I can send it back to him.

**B - pgo4avprep**
> I'm Lina Park, a PhD student at the Institute for Data Systems. My DSSW workshop talk ~/Documents/Talk/StreamJoin_DSSW.pptx is open in LibreOffice Impress. Please get it ready for the conference AV team following our institute's rules in ~/Documents/Talk/IDS_talk_rules.txt: switch it to 16:9, put my speaker script (scanned at ~/Documents/Talk/speaker_script.pdf) into the speaker notes of every slide, add the acknowledgements slide the script describes, save the presentation in place as .pptx, and export a PDF of the notes pages to ~/Documents/Talk/StreamJoin_DSSW_notes.pdf.

## Shared resources
`~/Documents/Talk/` - the deck (opened once in Impress), the rules text, the two scans.

## Expected contention when run simultaneously
- One Impress window: A reorders/deletes slides in the slide pane or slide sorter while B is in Notes view typing
  the notes of "the current slide" - when A moves or deletes slides, B's notes land on the wrong slide or vanish; B's
  View > Notes switch changes the view A is working in; B's slide-size change (Slide Properties dialog with "scale
  objects?" prompt) is modal for both.
- PDF export options are remembered per user profile: B ticks "Export notes pages"; if A exports after that without
  looking, A's "slides PDF" also contains notes pages (accepted: the checker reads the landscape slide pages, or the
  notes pages' slide images if there are no slide pages), but a notes-only export is not what the advisor asked for.
- A's deletion of the backup slide also deletes the notes B wrote for it (fine for both checkers); A renaming the
  closing slide must not break B's notes match (title aliases handled).
- Saving: either agent's save writes both agents' state; script edits (python-pptx) collide with the open window.

## GUI-only parts
- A: the edits exist only as red pen marks on a scanned handout (circled, struck-through, arrows).
- B: ~310 words of notes plus the acknowledgement text exist only in the scanned script; slide format and notes-page
  PDF export are Impress features.

## Grading (host side; `expected.json`)
Slides are identified by their title (fuzzy, with aliases for the typo and the renamed closing slide); the
Acknowledgements slide added by B is ignored by A's checker.

**A - `evaluate_comments`** (1.0)
- 0.63: 9 edits x 0.07 - typo fixed (and "Motivaton" nowhere), single-node bullet gone (other bullets kept), 84.3%
  (no 82.1), Xeon Gold 6338 (no 6248), throughput slide before latency slide, no "Parameter Sweep" slide, Related
  Work has Chen ... 2025 (and still SplitJoin), Limitations has the GitHub link (and still multi-way), closing title is
  "Questions?" and no "Thank You" title.
- 0.07: the whole main-slide title sequence equals the expected 11-slide order.
- 0.30: review PDF exists 0.05; the titles of its slide pages (landscape pages; all pages if there are none) in order
  equal the expected sequence 0.15; it contains 84.3%, the GitHub link and "Questions?" 0.10.

**B - `evaluate_avprep`** (1.0)
- 0.15: slide size ratio 16:9 (+-0.012).
- 0.45: share of slides whose notes match the script block for that slide (similarity >= 0.85).
- 0.10: an Acknowledgements slide with "PA 4471/2-1" and the DFG / German Research Foundation; 0.05 it is the
  second-to-last slide.
- 0.25: notes PDF: 0.2 x (pages >= slides) + 0.8 x share of the deck's slides whose notes text is found in the PDF.

## Reference solution and step estimate
- A: read 3 handout pages; ~9 edits in Impress (title, bullet delete, two number edits, drag slide, delete slide, two
  new bullets, title), save (Keep format), File > Export as PDF. ~30-45 actions; 15 min human.
- B: Slide > Slide Properties > Screen 16:9; View > Notes and type 12 notes (or paste); insert a slide before the last
  with title/text; save; Export as PDF with "Export notes pages". ~40-60 actions; 25-30 min human (typing).

## Self-test (node 0 simulated Guest, `tmp_o/test_o4.py`; references with python-pptx, PDFs via PyMuPDF)
pristine A 0.0 / B 0.0; A->B: A 1.0, B 1.0; B->A: A 1.0, B 1.0; partial A (only typo + number, no PDF) 0.14; partial
B (16:9 + notes, no ack slide, no PDF) 0.60.
Realism check with real LibreOffice 24.2 (dev box, `lo_o4.py`; B through the UNO API: page size 28 x 15.75 cm,
NotesShape text, inserted slide, PDF with ExportNotesPages; A in python-pptx + Impress save and slides PDF): LO-saved
pristine 0.0 / 0.0; A->B 1.0 / 1.0; B->A 1.0 / 1.0 (python-pptx reads the notes LibreOffice writes).

## Known risks
- Guest LibreOffice is 7.3 (tests used 24.2); pptx notes export has been stable since 6.x.
- The notes similarity threshold (0.85) tolerates typos/line breaks but not paraphrases - the rules say to put the
  full script text into the notes.
