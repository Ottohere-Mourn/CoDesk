# m4: HTML customer newsletter vs. support queue (family F2, one Thunderbird)

## Scenario and persona
Hana Kim owns Fern & Fennel, a small online plant and pottery shop in Portland (`hello@fernandfennel.shop`). Her
business partner Marco has sent the December promo sheet. Over the last days about ten customer-support e-mails have
piled up. Hana gives the newsletter to one assistant and the support queue to the other.

Thunderbird 115 runs an offline POP3 profile with 16 Inbox messages. Manual "mark as junk" moves mail to the Junk
folder.

Setup uploads:
- `~/Pictures/newsletter/`: 3 correct product photos and 3 decoys (last year's shot, another size, another plant);
- `~/Documents/customers.csv`: 24 customers, 16 opted in;
- `~/Documents/KB/Support_Macros.docx`: 7 macros, KB-01 to KB-07.

## User requests (verbatim)
**pgm4newsletter (A)**
> Please prepare the Fern & Fennel December newsletter in Thunderbird (my shop account hello@fernandfennel.shop). Marco's email "December newsletter - featured products" has the promo sheet with the three featured products, their December prices, the product links, which photos to use and the coupon code. Write an HTML email with the subject "Fern & Fennel - December picks": a short greeting, then for each product its photo (from ~/Pictures/newsletter/, shown inline in the message, not as an attachment), its name, the December price and a link to its product page, then the coupon code, and at the bottom an unsubscribe link to https://fernandfennel.shop/unsubscribe. Address it to hello@fernandfennel.shop and put every customer who opted in to the newsletter in ~/Documents/customers.csv in Bcc - but leave out anyone who has asked us by email to unsubscribe, and use the new address of anyone who told us their email address changed. Save it as a template (I want to reuse the layout next month) and also save it as a draft, ready to send on 1 December. Don't send it.

**pgm4support (B)**
> Please work through the customer support emails in my shop's Thunderbird inbox (hello@fernandfennel.shop). Answer each one with the matching macro from ~/Documents/KB/Support_Macros.docx (one macro per email; fill in the customer's first name and the order number where the macro has placeholders) and save each reply as a draft - don't send anything. Then move every handled support email into a folder Support/Done (create it under my account: Support with the subfolder Done). Mark the scam and spam emails as junk so that they end up in the Junk folder, and leave all other non-support emails in the Inbox. Finally, log every support email you handled in ~/Documents/support_log.xlsx with the columns Date, Customer Email, Order No and Macro (the macro code, e.g. KB-03).

## Content (hidden facts)
**Promo sheet** (`December_Promo_Sheet.pdf`, **image-only**):

| Product | December price | Product URL slug | Photo |
|---|---|---|---|
| Monstera Deliciosa (6-inch) | $34.00 | monstera-6in | monstera_dec.jpg |
| Speckled Stoneware Planter - Large | $28.50 | speckled-planter-l | planter_speckled_L.jpg |
| Pothos 'Marble Queen' Hanging Basket | $22.00 | marble-queen-basket | marble_queen_basket.jpg |

- Coupon code: COZYDEC15.
- The sheet says to use the December photos, not last year's.

**Recipients** (13): the 16 opted-in customers, minus the 3 who e-mailed "unsubscribe" (S5, S6, S10), with one
customer's address replaced by the new address from their S7 mail.

**Support e-mails** and the expected macro:

| Mail | Request | Macro | Order no. |
|---|---|---|---|
| S1 | cracked pot | KB-01 | FF-10517, **only on the packing slip in the photo** |
| S2 | where is my order | KB-02 | FF-10482 |
| S3 | yellow leaves | KB-03 | |
| S4 | return 80 days after delivery | KB-04 (not eligible) | FF-10233 |
| S5, S6, S10 | unsubscribe | KB-05 | |
| S7 | e-mail address change | KB-06 | |
| S8 | broken basket | KB-01 | FF-10561, **only in the photo** |
| S9 | wholesale inquiry | KB-07 | |

- Junk: a phishing "Shopify payout on hold" and an SEO spam mail.
- Non-support mails that stay in the Inbox: Marco's promo mail, a supplier invoice, the real Shopify community digest,
  and a UPS pickup notice.

## Shared resources and expected contention
- **Same Thunderbird, same Drafts folder.**
  - A spends a long time in an HTML composer window: inserting images, links and Bcc recipients, then "Save as
    Template".
  - B opens ten reply composers in a row.
  - Composer windows and their dialogs (file picker, link properties, save prompts) steal focus from each other.
- **B moves A's inputs.** The unsubscribe and address-change mails A needs are support mails that B answers and moves
  into Support/Done, possibly while A is reading them. A has to find them in another folder.
- **Shared files.** Both read files under `~/Documents`. B writes a workbook. A reads `customers.csv`, possibly in
  LibreOffice Calc while B uses Calc for the log.
- **Order independence.** A's checker reads Drafts and Templates by subject. B's checker finds replies by In-Reply-To.
  Neither checker depends on where the other task's mails were moved. Both orders work.

## GUI-only parts
- **A:**
  - The promo sheet is pixels only.
  - Inline images in an HTML draft or template are built by Thunderbird's composer. Thunderbird embeds them as
    multipart/related parts when saving.
- **B:**
  - Two order numbers exist only in customers' photos.
  - Drafts and junk handling happen inside Thunderbird.

## Grading
**pgm4newsletter** (`evaluate_newsletter`). The checker parses the raw Drafts and Templates mbox messages. It finds
images by md5 or file name, and they must be referenced as `cid:` (or `data:`) from the HTML.

| Check | Weight |
|---|---|
| Draft exists | 0.05 |
| Template exists | 0.08 |
| Template has 3 inline photos and 3 product links | 0.07 |
| In the draft (or the template if there is no draft): each correct inline photo | 0.06 each |
| Each decoy photo (penalty) | −0.03 each |
| Each product link (href) | 0.05 each |
| Unsubscribe link | 0.04 |
| Each December price ("$34" accepted for $34.00) | 0.03 each |
| Coupon code | 0.04 |
| Product names | 0.05 |
| Recipients: (correct Bcc − wrong Bcc)/13 | 0.25 |

- The recipients check scores 0 if any customer is in To or Cc (privacy leak).
- **Cap:** no draft → ≤ 0.5.

**pgm4support** (`evaluate_support`). Replies are checked on the user's own text, with the quoted customer mail
stripped.

| Check | Weight |
|---|---|
| Per support mail: reply draft to the customer | 0.015 each |
| Per support mail: exactly the right macro (distinctive sentence; pasting several macros fails) | 0.03 each |
| Per support mail: moved only to Support/Done | 0.015 each |
| Order number in the reply, for the 4 order cases | 0.02 each |
| Junk: per scam in Junk (Trash or deleted earns half) | 0.04 each |
| Non-support mails still in the Inbox (only once there is progress) | 0.04 |
| Log row (by customer e-mail) with the right macro code | 0.014 each |
| Log row with the right order number, for the 4 order cases | 0.015 each |

**Cap:** no log workbook → ≤ 0.7.

## Reference solution and expected effort
**A:**
- read the promo sheet and the CSV (about 8 steps)
- find the 4 unsubscribe or address-change mails (about 8)
- compose: greeting, 3 × (insert image, name, price, link) and footer (about 40)
- Bcc of 13 addresses (about 6)
- save as template, then save as draft (about 6)

About **70 GUI steps**; 30–40 minutes.

**B:**
- 10 × (open the mail, reply, paste the macro, fill placeholders, save the draft): about 8 each, 80 steps
- folder creation and moves (about 10)
- junk (about 4)
- the log in Calc (about 20)

About **110 steps**. This is the longest task of the family; 35–45 minutes for a person.

## Provenance
- **A** is the routine small-shop marketing task: monthly newsletter from a promo sheet, inline product photos,
  CAN-SPAM unsubscribe link, Bcc list from a CRM export, honouring opt-outs.
- **B** is a standard help-desk macro workflow (Zendesk or Gmail templates style), done in a desktop mail client with
  a KB document, triage, junk and a ticket log.

## Self-test (offline, simulated Guest; `lib_m4test.py`)
| Case | Score |
|---|---|
| Pristine: newsletter / support | 0.000 / 0.000 |
| A then B: newsletter / support | 1.000 / 1.000 |
| B then A: support / newsletter | 1.000 / 1.000 |
| Partial A: whole opt-in list (ignores opt-outs and the address change) and last year's monstera photo | 0.714 |
| Partial A: photos attached instead of inline, customers in To, no template | 0.420 |
| Partial B: no order numbers (photos unread), 2 wrong macros, scams deleted | 0.732 |
| Partial B: replies only (no moves, no log) | 0.650 |

## Known risks
- Manual junk marking: we set `mail.spam.manualMark=true` and `manualMarkMode=0` (move). Thunderbird should create
  and use the account's Junk folder. This was not verified on a live Thunderbird.
  - If the agent ends up deleting the scams instead, they earn half credit.
- Inline images: Thunderbird stores composer images as related parts with a `cid:` reference, keeping the original
  file bytes. The checker also accepts a file-name match and `data:` URIs, in case Thunderbird re-encodes an image
  (for example a pasted one).
