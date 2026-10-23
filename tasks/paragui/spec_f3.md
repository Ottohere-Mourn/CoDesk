# F3 - Community fair photos: recap slideshow + photo album vs next year's poster

Family F5 (files, scans, images, media). Task ids `pgf3slides` (A) and `pgf3poster` (B).
Files: `build_f3.py` (+ `lib_f.py`), `pg_f3.py` (+ `pg_fimg.py`), `task_pgf3slides.py`, `task_pgf3poster.py`.

## Scenario and persona
Sam Okoro coordinates the volunteers of the **Riverside Makers Collective**, which ran a one-day makers' fair on
Saturday 17 October 2026. Volunteers sent their phone photos through a messenger (22 JPEGs
`IMG-20261017-WA00NN.jpg`, 1600x1200, no EXIF times, shuffled order) - now in `~/Pictures/MakersFair_2026/`. The photos
show the programme items (stage with banner "Falmouth Ukulele Club", gazebo "Stall 4 - Penhallow Pottery", marquee
"Harbour Street Bakery - Bread masterclass", church hall "REPAIR CAFE", raffle drum ...), general shots (entrance arch,
food trucks, crowd) and the forge with a "Blacksmith demo CANCELLED" sign. Four photos show a family under a **red
umbrella** that asked not to be published. `~/Documents/MakersFair/` holds the image-only scan of the printed
programme with **handwritten changes** (Blacksmith demo struck out "CANCELLED - rain!", Bread masterclass 14:00 struck
out -> "14:30"), a phone photo of a **handwritten sticky note** with next year's booking ("Sat 9 Oct" struck out ->
"Sat 16 Oct 2027", Princess Pavilion, 10am - 4pm), the recap deck template `MakersFair_2026_recap.pptx` (title +
closing slide) and the poster template `poster_2027.docx` ([DATE] | [TIME] | [VENUE], a 2x3 table with [photo] /
[caption] cells).

## The two requests (verbatim)
**A - pgf3slides.** I coordinate the volunteers of the Riverside Makers Collective. The photos people sent me from
Saturday's fair are in ~/Pictures/MakersFair_2026, and the scanned programme with my handwritten changes on the day is
~/Documents/MakersFair/programme_scan.pdf. Please do three things. 1) The family with the red umbrella asked us not to
keep or publish any photo of them - delete those photos. 2) Sort the remaining photos into subfolders of
~/Pictures/MakersFair_2026 named "HH-MM <programme item>" after the programme item they show, using the time the item
actually took place (e.g. "10-30 Pottery wheel demo"); photos that don't show a programme item that took place go into a
subfolder "General". 3) In the thank-you slideshow ~/Documents/MakersFair/MakersFair_2026_recap.pptx (open in
LibreOffice Impress) add, between the title slide and the closing slide, one slide per programme item that took place,
in programme order, with the title "HH:MM <programme item>" (the actual time) and one photo of that item. Save the
slideshow in its current format.

**B - pgf3poster.** We've booked next year's Riverside Makers Fair - the details are on the sticky note I photographed,
~/Documents/MakersFair/committee_note.jpg. Please finish the "save the date" poster ~/Documents/MakersFair/poster_2027.docx
(open in LibreOffice Writer): replace [DATE], [TIME] and [VENUE] with the details from the note, and in the table put one
photo from this year's fair (~/Pictures/MakersFair_2026) of each of these acts - the pottery wheel demo, the children's
choir and the ukulele club - with a caption under each photo naming the group or stall as written on their banner.
Don't use any photo showing the family with the red umbrella; they asked not to be published. The poster must stay a
single A4 page. Save the document (keep it as .docx) and also export it as ~/Documents/MakersFair/poster_2027.pdf.

## Provenance
Post-event volunteer chores of any club or school PTA: "make a thank-you slideshow from everyone's photos, sort the shared
album per act", "make next year's save-the-date flyer with a few photos". Photo-consent opt-outs (GDPR) are a standard
part of event photography policies. Last-minute handwritten programme changes are how the day really goes.

## Setup (idempotent)
One tarball extracted once (`~/.cache/.pgf3_ready`); one Nautilus window on the photo folder (once); the deck is opened
in Impress and the poster in Writer - **two windows of the same soffice process** (a second open just re-focuses).

## Shared live state and expected contention
- **One LibreOffice process.** A works in Impress, B in Writer, in the same soffice instance: a modal dialog (Insert
  Image, Keep format, Export PDF) in one window can block or steal the other's input; "Exit LibreOffice", a crash or a
  `killall soffice` to "restart Impress" closes the other's unsaved document (and brings up Document Recovery for both).
- **The photos move and disappear under B.** A deletes the red-umbrella photos and moves all others into time-named
  subfolders while B browses the folder in Nautilus/eog/the Insert Image dialog to pick 3 photos: the file B was about
  to insert is gone or moved. If B links instead of embedding, the poster loses its image.
- **One Nautilus window** used by both (A creates 8 folders and drags 18 files; B navigates/previews).
- **Same consent rule, same pixels.** Both must recognise the red-umbrella photos; for the ukulele and pottery acts one
  of the three candidates is an umbrella photo.
- Both orders work: B after A finds the photos in subfolders (umbrella ones already gone); A after B is unaffected (B's
  poster embeds copies).

## GUI-only parts
Which photo shows which act and which show the umbrella family; the actual times / cancellation (handwritten on an
image-only scan); next year's date and venue (handwritten sticky note with a crossed-out date). The deck/poster editing is
natural GUI work (Impress/Writer), though scriptable.

## Grading
Photos are identified by thumbnail correlation (>= 0.85) of every embedded/exported image against the 22 originals.

**pgf3slides**
| weight | check |
|---|---|
| 0.25 | 18 non-umbrella photos (unchanged bytes) in the right subfolder: `HH-MM` with the actual time + item keyword, or `General` (general shots and the cancelled forge) |
| 0.10 | 4 umbrella photos deleted (no copy left under ~/Pictures) |
| 0.20 | 7 slides whose text has the item keyword and the actual time (14:30 for the bread masterclass) |
| 0.25 | each of those slides shows a photo of that item that is not an umbrella photo |
| 0.05 | slides in programme order |
| 0.05 | no slide for the cancelled blacksmith demo |
| 0.05 | title slide first, closing slide last |
| 0.05 | deck changed (more than the 2 template slides) |
Caps: an umbrella photo in the deck -> <= 0.5; deck unchanged/missing -> <= 0.4.

**pgf3poster**
| weight | check |
|---|---|
| 0.10 | poster_2027.pdf is one A4 portrait page |
| 0.15 / 0.05 / 0.05 | PDF text: 16 Oct 2027 (not the crossed-out 9 Oct) / Princess Pavilion / 10am-4pm |
| 0.05 | no [DATE]/[TIME]/[VENUE]/[photo]/[caption] placeholders left |
| 0.30 | PDF contains a non-umbrella photo of each act (pottery, choir, ukulele), 0.10 each |
| 0.15 | captions name Penhallow Pottery / St Mary's (Primary School Choir) / Falmouth Ukulele Club |
| 0.15 | poster_2027.docx saved with >= 3 images, no placeholders, venue present |
Caps: no PDF -> <= 0.3; an umbrella photo on the poster -> <= 0.5.

## Reference solution and effort
A: read the programme scan (zoom), open 22 photos, delete 4, create 8 folders, move 18 photos, add 7 slides with title
+ image in Impress, save in pptx format (~70-100 GUI steps; ~30 min). B: read the sticky note, find 3 suitable photos,
fill 3 placeholders, insert 3 images into table cells (resize to fit), 3 captions, save .docx (Keep format), Export as
PDF (~40-60 steps; ~20 min).

## Self-test (offline, simulated Guest)
pristine A 0.0 / B 0.0; reference A->B 1.0 / 1.0; reference B->A 1.0 / 1.0; wrong A (printed times, slide for the
cancelled item, umbrella photos in the deck) 0.5 (cap); wrong B (crossed-out date, umbrella photo) 0.5 (cap); partial B
(PDF only, no captions, docx not saved) 0.7.

## Known risks
- If the agent re-saves the deck as .odp next to the .pptx the checker falls back to the .odp (same stem).
- LibreOffice may downsample images in the PDF export; identification uses small thumbnails, so this is fine; heavy
  cropping of the photos in the poster could fall below the 0.85 correlation threshold (cropping was not requested).
