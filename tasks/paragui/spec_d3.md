# Pair D3 — kestrel-site: landing-page restyle from a design hand-over vs new content pages from a Writer document

Family F4 (software development: VS Code + terminal + git + running local service + Chrome). Port 8113.

## Scenario and persona
Mareike Holst owns *Kestrel Physio*, a physiotherapy practice in Bremen. The website (`~/projects/kestrel-site`) is
static HTML produced by a tiny stdlib generator (Markdown pages in `content/`, `templates/base.html` with header,
navigation and footer, design tokens in `static/css/tokens.css`) with a **live preview server** on 8113 that rebuilds
`_site/` whenever a source file changes. Her web agency delivered the 2026 design (mockup PNG + a scanned style-guide
page), and her practice manager Ilka sent the texts for three new pages as a Word/Writer document whose price list is
a scanned picture. Each assistant gets one of the two.

## The two requests (verbatim instructions)
**pgd3restyle (A)**
> I run the Kestrel Physio practice. Our website's source is in ~/projects/kestrel-site (open in VS Code) and its live preview runs at http://127.0.0.1:8113 (open in Chrome; it rebuilds automatically when files change). Our designer has handed over the 2026 design: the mockup docs/design/landing-2026-mockup.png and the style guide page docs/design/styleguide-2026-p7.pdf. Please restyle the site accordingly: put the style guide's colours, type sizes and spacing into the design tokens in static/css/tokens.css, change the landing page (templates/home.html) to match the mockup's texts, button and cards, and add the phone button shown in the mockup to the header of every page. Leave the navigation items as they are. Check the result in the preview in Chrome, then commit your changes, and nothing else, with the message 'Restyle landing page to the 2026 design'.

**pgd3pages (B)**
> Our practice manager Ilka has sent the texts for three new pages of the Kestrel Physio website: ~/Documents/Website_update_Oct2026.docx. The site's source is in ~/projects/kestrel-site (open in VS Code) and its live preview runs at http://127.0.0.1:8113 (open in Chrome; it rebuilds automatically when files change). Please add the Treatments, Team and Prices pages as described in her document (as Markdown pages in content/, with the price list as a proper table), change the navigation in templates/base.html to the order she asks for, and fix every broken link that tools/linkcheck.py reports for the preview. Check the pages in Chrome, then commit your changes, and nothing else, with the message 'Add treatments, team and prices pages'.

## Provenance
- A: the standard agency hand-over for a small-business site: a static mockup plus a style-guide excerpt (colour
  swatches with HEX/RGB, type scale, spacing, radius), implemented through design tokens (CSS custom properties).
- B: the most common content-update request of small businesses: "here is a Word document with the texts for the
  new pages" — including a phone photo/scan of the printed price list — plus "the agency says there are broken
  links" (a link-check script in the repo, as in many static-site setups).

## Shared live resources and expected contention
- **templates/base.html** is the frame of every page: A adds the phone button to its header, B rewrites the `<nav>`
  block and fixes the broken footer link (`/imprint.htm`). Same file, adjacent hunks; whoever commits first must stage
  only its own hunk (VS Code "Stage Selected Ranges" or `git add -p`), and unsaved VS Code buffers of one overwrite
  the other's saved edits.
- **One live preview**: every save by either agent triggers a rebuild of the shared `_site/`; a half-edited template
  (e.g. a mistyped `{{ placeholder }}`) turns every page of the preview into "Build failed" for both, and B's link
  checker crawls whatever state A's restyle is in.
- **One Chrome tab**, one VS Code window, one git index (`git commit -a` sweeps the other's work in).

## GUI-only information
- A: colours, type sizes, spacing, radii only as pixels in the image-only PDF; hero headline/subline, CTA text and
  target, card titles/texts and the phone button only in the mockup PNG (with the designer's red-line notes).
- B: page texts in a .docx (LibreOffice Writer); the price list (7 rows, two "Lymphatic drainage" durations) only as a
  scanned image embedded in the document; the required navigation order is stated in the document.

## Grading (`pg_d3.py`)
Guest-side inspection: commits since base, per-commit diffs of `templates/base.html`, tokens parsed from
`static/css/tokens.css` (and from the preview's served copy), the served pages `/`, `/contact.html`, `/news.html`,
`/treatments.html`, `/team.html`, `/prices.html`, and a crawler (own copy of the link checker) from `/`.

**pgd3restyle (A)** — commit = subject mentions restyle/landing/design
1. commit exists (1)
2. commit focused: only tokens.css, site.css, home.html, base.html, content/index.md, static/img/; its base.html
   hunks add no new nav pages / footer fix (1)
3. the 4 colour tokens equal the style guide (HEX/RGB normalised) (1.5)
4. the 7 type/spacing/shape tokens equal the style guide (button radius: any pill value >= 100px/50%) (1.5)
5. tokens.css committed (0.5)
6. hero headline + subline from the mockup on the served landing page (1)
7. CTA "Book an appointment" links to /contact.html (1)
8. three cards in mockup order; old "Welcome..." hero and "Massage" card gone (1)
9. tel: link to 0421 555 0193 in the header of /, /contact.html and /news.html (1)
10. the preview serves the new tokens (0.5)
Caps: no token group right -> <= 0.4; no restyle commit -> <= 0.5.

**pgd3pages (B)** — commit = subject mentions treatments/team/prices/pages
1. commit exists (1)
2. commit focused: none of A's files except base.html, and its base.html hunks add no tel: button (1)
3. /treatments.html, /team.html, /prices.html served with the right `<title>` (1)
4. all 6 treatments on the Treatments page (1)
5. all 4 therapists with their qualifications on the Team page (1)
6. all 7 price rows (name + duration + price in the same row/line) on the Prices page — as text, not the picture (2)
7. nav on /, /contact.html, /prices.html is exactly Home, Treatments, Team, Prices, News, Contact (non-page links such
   as the phone button ignored) (1)
8. no broken internal link or image reachable from / (1)
9. the three content files are committed (0.5)
Caps: fewer than 2 pages served -> <= 0.4; no pages commit -> <= 0.5.

## Reference solution (lib_dref_d3.py)
A: replace the 11 token values; new hero/cards in home.html; phone button after `</nav>` in base.html; commit the
three files. B: three Markdown pages (list, table, table), new nav block, `/imprint.htm` -> `/imprint.html`,
`/privacy` -> `/privacy.html`, news image -> existing `team-summer-run-2026.svg`; link checker reports 0; commit.

## Self-test results
pristine 0.000 / 0.000; A then B 1.000 / 1.000; B then A 1.000 / 1.000; partial A (colours + hero only, no phone
button) 0.700; partial B (price list embedded as a picture, nav appended at the end, links not fixed) 0.579; mixing
(A's restyle uncommitted, B commits with `git commit -a`) A 0.500 / B 0.895.

## Expected effort
Solo: A ~35-55 steps (open PDF in a viewer, PNG in VS Code, edit 11 tokens, rewrite hero/cards, header button, check
the preview, stage, commit). B ~45-70 steps (open the .docx in Writer, transcribe 3 pages incl. the price table from
the scan, edit nav, run the link checker, fix 3 broken links, check in Chrome, commit).

## Known risks
- The landing-page copy is matched on key phrases ("move without pain again", "Bremen-Neustadt", "appointments within
  five working days"); paraphrasing the mockup fails check A6.
- Prices accept "€ 38.00", "38,00 €", "EUR 38", "38.-", but the row must keep name, duration and price together.
