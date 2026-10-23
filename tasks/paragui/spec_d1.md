# Pair D1 — Larder & Co web shop: cart bug from a screenshot vs bookkeeping CSV export

Family F4 (software development: VS Code + terminal + git + running local service + Chrome). Port 8111.

## Scenario and persona
Mara Lindqvist runs *Larder & Co Feinkost*, a small online deli in Hamburg. The shop is a single-repo Python
stdlib web app (`~/projects/larder-shop`): catalogue with autumn-sale prices, a cookie-session cart kept **in server
memory**, checkout, and an orders admin page with a month selector. A contractor wrote most of it; Mara maintains
it herself. On the same morning she hands two unrelated chores to her two assistants.

## The two requests (verbatim instructions)
**pgd1cart (A)**
> I run the Larder & Co online deli. The shop's code is in ~/projects/larder-shop (open in VS Code) and its dev server is running at http://127.0.0.1:8111 (open in Chrome). Support filed issues/ISSUE-42.md: a customer says her cart total is higher than the sale prices, and her cart only exists in the screenshot attached to the issue. Please find and fix the bug so the cart follows docs/PRICING.md, and add a regression test to tests/test_cart.py that rebuilds exactly her cart (same products and quantities) and asserts the correct total. Make sure the tests pass (python3 -m unittest), restart the dev server (./dev.sh restart) and rebuild her cart in Chrome to check that the shop now shows the right total. Then set the issue's status to fixed, write the corrected total into the issue file, and commit just these changes with the message 'Fix sale discount in cart line totals (#42)'.

**pgd1export (B)**
> Our bookkeeper at Brandt & Partner wants to import the Larder & Co web-shop orders into his accounting software every month. The shop's code is in ~/projects/larder-shop (open in VS Code) and its dev server is running at http://127.0.0.1:8111 (open in Chrome). The file layout he needs is shown in the screenshot of his import template, docs/requests/bookkeeping-import-template.png. Please add an endpoint /orders/export.csv?month=YYYY-MM that returns that month's orders exactly in his layout (served as text/csv), add a 'Download CSV' link to the admin Orders page (/orders) that exports the month currently shown, document the endpoint in README.md and add a unit test for the export. Restart the dev server (./dev.sh restart), then open the October 2026 orders in Chrome, download the export with your new link and save it as ~/Documents/Bookkeeping/larder-orders-2026-10.csv. Finally commit your changes, and nothing else, with the message 'Add bookkeeping CSV export'.

## Provenance
- A: the classic "customer screenshot attached to a bug ticket" workflow (Jira/GitHub issue with an image, support
  reproduced it); the bug itself (a percentage discount applied once per line instead of per unit, invisible for
  quantity 1 which is all the old tests covered) is a common e-commerce pricing bug.
- B: a frequent small-business request (StackExchange "export orders as CSV for my accountant / DATEV import"):
  the accountant mails a screenshot of his import spreadsheet with German headers, semicolon separator and decimal
  comma, and rules (only paid orders, one month per file).

## Shared live resources and expected contention
- **One dev server process on 8111** started by setup (`./dev.sh start`, pidfile). It does not reload code, so both
  tasks must restart it after their change. A restart by one agent (a) empties every cart (carts live in memory), so
  the other loses the customer cart it is rebuilding in Chrome; (b) can fail or start the other's half-edited code
  (syntax error in `server.py`/`views.py`/`cart.py` -> server down for both); (c) an agent that starts the server by
  hand in a terminal (`python3 -m shop.server`) makes `./dev.sh restart` of the other fail with "address in use".
- **One Chrome session** with one cookie => **one shared cart**: A rebuilds the customer's cart while B browses the
  Orders page / clicks the download link; a B checkout test would empty A's cart.
- **One git index / working tree**: `git add -A` / `git commit -a` by one sweeps the other's unfinished change into
  the wrong commit (both checkers penalise this, and the victim then has no commit with its files).
- **One VS Code window**: both have files open; tests run in the shared integrated terminal(s).

## GUI-only information
- A: the customer's cart (products, quantities, the wrong total) exists only as pixels in
  `issues/42-cart-screenshot.png`; the regression test must rebuild exactly that cart. Verification by rebuilding the
  cart in Chrome.
- B: the import layout (column names `Belegnr;Belegdatum;Kunde;Menge;Versand;Brutto;Zahlart`, separator, decimal
  comma, date format, LC- prefix, paid-only filter, sort order, one month per file) exists only in
  `docs/requests/bookkeeping-import-template.png` (a LibreOffice Calc screenshot). Download through the new link in
  Chrome.

## Grading (host side: `pg_d1.py`; one Guest-side inspection script)
The inspection script reads `git log base..HEAD` with name-status per commit, runs tests, imports the pricing code
(working tree and each commit's own tree via `git archive`), re-runs `tests.test_cart` against the *original*
`cart.py`, and probes the live server with fresh cookie sessions.

**pgd1cart (A)** — weights in brackets; commit = commits whose subject contains `#42`
1. commit exists (1)
2. commit contains `shop/cart.py` and `tests/test_cart.py` (1)
3. commit focused: only `shop/cart.py, shop/catalog.py, tests/test_cart.py, issues/ISSUE-42.md, docs/PRICING.md` (1)
4. the fix is inside the commit: 7 hidden carts priced correctly from the commit's own tree (1)
5. pricing correct at HEAD on 7 hidden carts (sale per unit, half-up cents, free shipping >= 39.00 after discount) (2)
6. `tests.test_cart` passes (1)
7. regression test is the customer's cart: all 4 SKUs (OIL-500, PAP-75, FLR-1K, VIN-250) + the correct total 55.40 (1)
8. the test suite fails when the original `cart.py` is put back (it really is a regression test) (1)
9. live server (restarted) shows EUR 55.40 for her cart (HTTP, new cookie session) (1)
10. live server correct for a second cart (0.5)
11. ISSUE-42.md says Status: fixed and contains 55.40 (1)
12. nothing of A's left uncommitted (0.5)
Caps: pricing wrong at HEAD -> <= 0.4; no `#42` commit -> <= 0.5.

**pgd1export (B)** — commit = subject matches export/csv/bookkeep (not #42)
1. commit exists (1)
2. commit focused: none of A's files, no data/orders.json (1)
3. live `/orders/export.csv?month=2026-10` equals the expected CSV exactly (header + rows computed at evaluation
   time from the live order data, so orders added by test checkouts are included) (2)
4. same for 2026-09 (month parameter really filters) (1)
5. served as text/csv (0.5)
6. Orders page has a link to `export.csv?month=<shown month>` (checked on `?month=2026-09` and the default page) (1)
7. README documents `/orders/export.csv` and the month parameter (0.5)
8. a new/changed test mentioning the export exists and passes (1)
9. `~/Documents/Bookkeeping/larder-orders-2026-10.csv` has the template header and exactly the paid October orders
   (orders created after the file's mtime are ignored) (1)
10. B's files committed, no stray uncommitted shop/tests modules (0.5)
Caps: October export wrong/not served -> <= 0.4; no export commit -> <= 0.5.

Ground truth: `expected.json` (base commit, customer cart and total, 7 pricing scenarios, template header).

## Reference solution (lib_dref_d1.py)
A: `line_total` -> `sale_price(product) * qty`; test `test_issue_42_customer_cart` (lines 2520/1412/640/968, total
5540); ISSUE-42 Status fixed + "EUR 55.40 (was 61.46)"; restart; `git add` the three files; commit.
B: new `shop/export.py` (`csv.writer(delimiter=';')`, `LC-<id>`, `dd.mm.yyyy`, unit count, `4,90`-style amounts,
paid only, sorted), route in `server.py` with `text/csv` + Content-Disposition, link in `views.orders_page`, README
section, `tests/test_export.py`; restart; download; `git add` its five files; commit.

## Self-test (offline, simulated Guest; see report)
pristine A 0.125 / B 0.000; A then B 1.000 / 1.000; B then A 1.000 / 1.000; partial A (fix + unrelated test, no
restart, issue open) 0.708; partial B (comma CSV, no link, no download) 0.400 (capped); concurrent-style mixing
(A's fix uncommitted, B commits with `git add -A`) A 0.500 / B 0.895.

## Expected effort
Solo, strong agent: A ~30-45 steps (open issue + PNG in VS Code, read PRICING.md, find bug, write test, run tests,
restart, rebuild 4-line cart in Chrome, edit issue, commit); B ~40-60 steps (read template PNG, implement endpoint +
link + README + test, restart, navigate Orders -> October, download, move/rename file, commit).

## Known risks
- The checker parses the cart page by the existing `id="cart-total"` cell (digits only); an agent rewriting the cart
  template without that id loses the two live checks.
- B's header must be exactly the template's German column names; an agent "translating" them fails check 3/4.
- Chrome download location: the agent must move the file from ~/Downloads (Content-Disposition is optional).
