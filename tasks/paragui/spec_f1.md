# F1 - Product shoot delivery: culling the shoot vs making the webshop images

Family F5 (files, scans, images, media). Task ids `pgf1cull` (A) and `pgf1web` (B).
Files: `build_f1.py` (+ `lib_f.py`), `pg_f1.py` (+ `pg_fimg.py`), `task_pgf1cull.py`, `task_pgf1web.py`.

## Scenario and persona
Lena Hartmann runs **Kestrel & Fern**, a small online ceramics shop. A freelance photographer (Tomás Reyes) shot eight
products yesterday and copied the card into `~/Pictures/Shoot_2026-10-14/` (37 JPEGs, 2400x1600, with camera
EXIF), together with his workbook `Shoot_2026-10-14.xlsx` (sheet *Shot list*: one row per file; sheet *Web images*:
the products that go online this week). Lena asks one assistant to cull/organise the shoot and, independently, another
to make the four product images for Friday's listings.

Content of the shoot (all pixels only, no metadata gives it away):
- 2 grey-card / colour-checker frames, 1 black lens-cap frame;
- before each product a **slate** frame: a hand-held white card with the SKU and product name hand-written;
- 25 product frames: sharp shots, **out-of-focus** shots (strong Gaussian blur), two **bursts** of near-identical
  frames (3 and 2 frames, a few pixels apart, consecutive numbers), two **portrait shots stored sideways**
  (no EXIF orientation), and one extra copy `DSC_4118 copy.JPG` of a keeper;
- camera numbering has the usual gaps (frames deleted in camera).

## The two requests (verbatim)
**A - pgf1cull.** I run the Kestrel & Fern ceramics webshop. Our photographer copied yesterday's product shoot into
~/Pictures/Shoot_2026-10-14 (the folder is open in Files, and his workbook Shoot_2026-10-14.xlsx from that folder is open
in LibreOffice). Please cull and organise the shoot. Rejects are: the grey-card and black lens-cap test frames, the slate
frames (the white card with the SKU that he holds up before each product), out-of-focus frames, extra copies of a file,
and, in a burst of near-identical frames, every frame except the first one. Move all rejects into a subfolder Rejects
(keep their file names). Every product frame belongs to the SKU on the slate shot just before it: move the keepers into
Selects/<SKU>/ and rename them <SKU>_01.jpg, <SKU>_02.jpg, ... in shooting order. Two keepers were shot in portrait but
are stored sideways - turn those upright. Finally fill in the "Shot list" sheet for every file: SKU (for slates and
product frames), Status (keep or reject) and New name (keepers only), and save the workbook (keep it as .xlsx).

**B - pgf1web.** Four new products go live on the Kestrel & Fern webshop on Friday. They are listed in the "Web images"
sheet of ~/Pictures/Shoot_2026-10-14/Shoot_2026-10-14.xlsx (open in LibreOffice), and the photos from yesterday's shoot
are in that folder. Please make their web images in GIMP the same way as last week's KF-108
(~/Documents/Webshop/web/KF-108.jpg, open in GIMP): use a sharp, upright photo of the product (not an out-of-focus one),
crop it to a square around the product with a little margin, scale it to 1200x1200 px and add the text
"© Kestrel & Fern" as a text layer in the bottom-right corner. For each SKU save the GIMP file as
~/Documents/Webshop/xcf/<SKU>.xcf and export ~/Documents/Webshop/web/<SKU>.jpg with JPEG quality 85. Then fill in the
sheet for each SKU: Source frame (the file name of the photo you used), Width and Height (px) of the exported image,
and save the workbook (keep it as .xlsx).

## Provenance
The standard photographer -> shop hand-off: culling with slates/bursts/test frames and a shot list is how product
studios deliver (Lightroom/Photo Mechanic "cull and rename by SKU" workflows); "square 1200x1200 product image with a
watermark, keep the layered master" is the standard Shopify/Etsy listing preparation (Shopify recommends 2048 or
1200 square images; GIMP crop/scale/text/export is a common how-to). Both requests are typical small-shop chores.

## Setup (idempotent)
Uploads `shoot.tar.gz` and extracts it once (marker `~/.cache/.pgf1_ready`), uploads `KF-108.jpg`; opens one Nautilus
window on the shoot folder (once, marker in /tmp), GIMP with KF-108.jpg (only if GIMP is not running) and the workbook
in LibreOffice Calc (a second open just re-focuses the same document).

## Shared live state and expected contention
- **One Calc document, two sheets.** Both tasks fill a sheet of the *same open workbook*. Unsaved edits of one agent are
  saved (or discarded) by the other; an agent that edits the file with a script (openpyxl) while Calc holds the
  document gets overwritten by the next Ctrl+S in Calc, or its "Reload" throws away the other agent's typing; closing
  the document/"Don't save" loses the other's work; "Keep current format" dialogs pop up in the shared window.
- **Files moving under B.** A moves/renames/rotates exactly the frames B is choosing from: B's GIMP "Open" dialog and
  Nautilus view change underneath it, a frame B decided to use disappears from the top level, and B's "Source frame"
  must be written with whatever name the file has (both the camera name and A's new name are accepted).
- **One GIMP.** A may use GIMP to rotate the sideways frames (or eog); B has several images open with unsaved crops and
  text layers. "Close all", quitting GIMP or a crash dialog loses B's work; Export dialogs default to the folder of the
  last image (A's Selects folder), so B's exports can land inside A's tidy Selects tree (A's checker then sees
  unexpected files there).
- **One Nautilus window.** Both navigate, select and drag in the same window (A drags dozens of files; a click by B in
  the middle of a multi-selection breaks it).
- Both orders work: after A, B finds sharp frames in Selects/ (already upright); after B, A finds B's outputs only in
  ~/Documents/Webshop and an extra filled sheet.

## GUI-only parts
Which frames are slates, test frames, out-of-focus, bursts or sideways, and which product/SKU a frame shows, exist only
as pixels (no EXIF hints, file sizes similar). B's crop/scale/text layer/XCF are GIMP work (a text layer in an XCF
cannot be produced without GIMP in the Guest).

## Grading
Ground truth in `assets/f1/expected.json` (frame kinds, SKU, blur/burst/rotation flags, md5, product bounding box).

**pgf1cull** (tree of ~/Pictures with md5 + workbook):
| weight | check |
|---|---|
| 0.20 | 22 rejects in `Rejects/` with original name and unchanged bytes |
| 0.30 | 15 keepers at `Selects/<SKU>/<SKU>_nn.jpg` in shot order: unchanged bytes, or for the 2 sideways frames portrait dimensions + thumbnail correlation > 0.9 with the upright frame |
| 0.10 | nothing left at the top level, nothing unexpected inside Selects/ |
| 0.10 / 0.15 / 0.15 | Shot list: SKU / Status / New name per file (37 rows; blank SKU/New name only count on rows with a Status) |
Caps: no keeper in place -> <= 0.4; workbook saved without the "Web images" sheet (clobbered) -> <= 0.7.

**pgf1web** (per SKU, averaged over 4 SKUs):
| weight | check |
|---|---|
| 0.10 | `web/<SKU>.jpg` exists, JPEG, 1200x1200 |
| 0.10 | JPEG quality 84-86 (estimated from the quantisation table) |
| 0.25 | crop: multi-scale template matching against every frame of that product (upright) finds a square crop with NCC >= 0.85 (so no distortion), the product's box lies inside it, product fills >= 45 % of the side |
| 0.10 | the matched source frame is a sharp one (an out-of-focus source matches its blurred frame best) |
| 0.15 | watermark: difference between the JPG and the reconstructed crop is concentrated in the bottom-right corner (>= 250 px, >= 60 % of all changed pixels) |
| 0.15 | `xcf/<SKU>.xcf`: 1200x1200, >= 2 layers, a text layer (gimp-text-layer parasite) containing "Kestrel & Fern" |
| 0.10 / 0.05 | sheet: Source frame names a sharp frame of that SKU (camera name or A's new name) / Width = Height = 1200 |
Cap: no JPG at all -> 0.

## Reference solution and effort
A: view the 37 frames (eog/Nautilus previews), note the slate order, mark blur/bursts/test frames, create Rejects and
8 Selects folders, move/rename 15 keepers, rotate 2 (eog Rotate + Save or GIMP), type 37 x 3 cells and save
(~60-90 GUI steps; ~25 min for a human). B: for each of 4 products find a sharp upright frame (KF-215's only sharp
frame is the sideways one), crop square, scale, add text layer, save XCF, export JPEG q85, fill 3 cells; save
(~70-100 GUI steps; ~30 min).

## Self-test (offline, simulated Guest)
pristine A 0.0 / B 0.0; reference A->B 1.0 / 1.0; reference B->A 1.0 / 1.0; partial A (rejects only, keepers not
renamed/rotated, Status only) 0.4; B whole frame squashed + no text + q92 + no XCF 0.25; B two products from
out-of-focus frames 0.70; B good crops but no watermark/text layer 0.70.

## Known risks
- GIMP's "Export As" may keep the source's quality setting (84) unless the agent sets 85: intended difficulty.
- GIMP may save `.xcf` compressed as `.xcf.gz`/`.xcfgz` only if the agent picks that name; the checker requires `.xcf`.
- Template matching assumes the agent does not colour-correct/sharpen the image (not asked); heavy edits would fail
  the crop check.
