"""o3 - one Writer document (NHRF grant proposal) + its budget workbook: applying the funder's revised cost rules
(scanned letter) to the budget and the proposal's budget section vs reformatting the proposal to the funder's
formatting annex (scan) and exporting the submission PDF."""
from __future__ import annotations

import re

from evaluation_examples.task_class import pg_olib as L
from evaluation_examples.task_class.pg_common import HOME, expected, fetch, guest, result, upload

DIR = f"{HOME}/Documents/Grant"
DOCX = f"{DIR}/NHRF_proposal_Osei.docx"
XLSX = f"{DIR}/NHRF_budget_Osei.xlsx"
NOTE = f"{DIR}/budget_changes.txt"


def setup(sc):
    upload(sc, [("o3/Grant/NHRF_proposal_Osei.docx", DOCX), ("o3/Grant/NHRF_budget_Osei.xlsx", XLSX),
                ("o3/Grant/NHRF_cost_rules_letter.pdf", f"{DIR}/NHRF_cost_rules_letter.pdf"),
                ("o3/Grant/NHRF_Annex_C_formatting.pdf", f"{DIR}/NHRF_Annex_C_formatting.pdf")])
    sc._open_setup(DOCX)


NUM = re.compile(r"(?<![\w.])£?\s?(\d{1,3}(?:,\d{3})+(?:\.\d+)?|\d+\.\d+|\d+)(?![\w])")


def _numbers(text):
    out = []
    for m in NUM.finditer(text):
        try:
            out.append(float(m.group(1).replace(",", "")))
        except ValueError:
            pass
    return out


def _has(nums, x, tol=0.011):
    return any(abs(n - x) <= tol for n in nums)


# ---------------------------------------------------------------- task A: revised cost rules
@L.safe
def evaluate_budget(env, dest: str) -> dict:
    exp = expected("o3")
    new, rn = exp["new"], exp["rates_new"]
    checks = {}
    # 1. workbook
    s_wb = 0.0
    xpath = fetch(env, XLSX, dest + ".xlsx")
    if xpath:
        try:
            bk = L.XBook(xpath)
            rs, bs = bk.sheet(r"rates?"), bk.sheet(r"budget")
        except Exception:  # noqa: BLE001
            bk = rs = bs = None
        rates = {}
        if rs:
            for row in bk.wf[rs].iter_rows():
                label = L.norm(row[0].value)
                vals = [L.num(bk.safe(rs, c.coordinate)) for c in row[1:4]]
                vals = [v for v in vals if v is not None]
                for k, pat in (("salary", r"salary"), ("mileage", r"mileage"), ("indirect", r"indirect")):
                    if re.search(pat, label) and vals and k not in rates:
                        rates[k] = vals[0]
        ok_r = {k: rates.get(k) is not None and (L.close(rates[k], rn[k], 1e-6) or
                                                (k == "indirect" and L.close(rates[k], rn[k] * 100, 1e-6)))
                for k in ("salary", "mileage", "indirect")}
        mocap_ok, total_ok, total = True, False, None
        if bs:
            for row in bk.wf[bs].iter_rows():
                label = L.norm(row[0].value)
                vals = [L.num(bk.safe(bs, c.coordinate)) for c in row[1:4]]
                vals = [v for v in vals if v is not None]
                if "motion capture" in label and any(abs(v) > 0.005 for v in vals):
                    mocap_ok = False
                if re.search(r"^total", label) and vals:
                    total = vals[0]
                    total_ok = L.close(total, new["total"], 0.05)
        s_wb = 0.05 * sum(ok_r.values()) + 0.05 * (mocap_ok and bool(bs)) + 0.1 * total_ok
        checks["workbook"] = {"rates": ok_r, "motion_capture_removed": mocap_ok and bool(bs), "total": total,
                              "total_ok": total_ok}
    else:
        checks["workbook"] = "missing"

    # 2. proposal
    path = fetch(env, DOCX, dest + ".docx")
    if not path:
        return result(min(s_wb, 0.3), dict(checks, proposal="missing"))
    dx = L.Docx(path)
    tables = [dx.table_rows(t) for t in dx.tables()]
    btab = next((t for t in tables if any(re.match(r"staff", L.norm(r[0])) for r in t if r)), None)
    row_ok = {}
    if btab:
        labels = {"staff": r"^staff", "travel": r"^travel", "equipment": r"^equipment", "direct": r"^direct",
                  "indirect": r"^indirect", "total": r"^total"}
        for key, pat in labels.items():
            row = next((r for r in btab if r and re.search(pat, L.norm(r[0]))), None)
            nums = [n for c in (row[1:] if row else []) for n in _numbers(c)]
            row_ok[key] = bool(nums) and L.close(nums[-1], new[key], 0.05)
        ind = next((r for r in btab if r and re.search(r"^indirect", L.norm(r[0]))), None)
        row_ok["indirect_label_pct"] = bool(ind) and f"{exp['pct_new']}%" in ind[0].replace(" ", "")
    s_tab = sum(row_ok.values()) / 7 if row_ok else 0.0
    cover = next((r for t in tables for r in t if r and "amount requested" in L.norm(r[0])), None)
    cover_ok = bool(cover) and _has([n for c in cover[1:] for n in _numbers(c)], new["total"], 0.05)

    body_text = " ".join(dx.ptext(p) for p in dx.body_paragraphs())
    all_nums = _numbers(body_text + " " + " ".join(c for t in tables for r in t for c in r))
    fresh = {str(x): _has(all_nums, x) for x in exp["fresh_numbers"] if x != new["equipment"]}
    stale = {str(x): _has(all_nums, x) for x in exp["stale_numbers"]}
    pcts = re.findall(r"(\d+)\s?% of (?:total )?direct costs", L.norm(body_text + " " + " ".join(
        c for t in tables for r in t for c in r)))
    pct_ok = bool(pcts) and all(int(p) == exp["pct_new"] for p in pcts)
    s_text = 0.08 * sum(fresh.values()) / len(fresh) + 0.08 * (1 - sum(stale.values()) / len(stale)) + 0.04 * pct_ok

    note = guest(env, f"cat {NOTE} 2>/dev/null")
    note_ok = [_has(_numbers(note), new["total"], 0.05), bool(re.search(r"motion|capture|equipment", note, re.I))]

    score = s_wb + 0.3 * s_tab + 0.1 * cover_ok + s_text + 0.1 * sum(note_ok) / 2
    checks.update({"budget_table": row_ok if btab else "missing", "cover_amount": cover_ok,
                   "fresh_numbers_present": fresh, "stale_numbers_present": stale, "indirect_pct_mentions": pcts,
                   "note": note_ok})
    return result(score, checks)


# ---------------------------------------------------------------- task B: funder formatting
def _sname(dx, p):
    return re.sub(r"\s+", "", dx.para_style_name(p).lower())


def _title_match(title, text):
    core = re.sub(r"^\d+(\.\d+)?\.?\s+", "", L.norm(title))
    return bool(re.fullmatch(r"(\d+(\.\d+)?\.?\s+)?" + re.escape(core), L.norm(text)))


def _first_run(p):
    for r in p.iter(L.q("w:r")):
        if "".join(t.text or "" for t in r.iter(L.q("w:t"))).strip():
            return r
    return None


def _jc(dx, p):
    v = dx.ppr_val(p, "w:jc", "w:val")
    return (v or "left").lower()


@L.safe
def evaluate_format(env, dest: str) -> dict:
    exp = expected("o3")
    path = fetch(env, DOCX, dest + ".docx")
    if not path:
        return result(0.0, {"proposal": "missing"})
    dx = L.Docx(path)
    checks = {}
    sect = dx.body.find(L.q("w:sectPr"))
    sects = dx.sections()
    sect = sect if sect is not None else (sects[-1] if sects else None)

    def attr(el, name):
        return L.twips(el.get(L.q(f"w:{name}"))) if el is not None else None
    pg = sect.find(L.q("w:pgSz")) if sect is not None else None
    mar = sect.find(L.q("w:pgMar")) if sect is not None else None
    w, h = attr(pg, "w"), attr(pg, "h")
    a4 = w is not None and h is not None and abs(w - 11906) <= 60 and abs(h - 16838) <= 60
    near = lambda v: v is not None and abs(v - 1417) <= 45  # noqa: E731  2.5 cm
    m = {k: attr(mar, k) for k in ("top", "bottom", "left", "right", "header", "footer")}
    # LibreOffice writes "top" = margin + header height when a header is on; its "header" distance is the margin then
    margins = {"left": near(m["left"]), "right": near(m["right"]),
               "top": near(m["top"]) or (near(m["header"]) and (m["top"] or 0) >= 1417),
               "bottom": near(m["bottom"]) or (near(m["footer"]) and (m["bottom"] or 0) >= 1417)}
    checks["page"] = {"size_twips": [w, h], "a4": a4, "margins_twips": m, "margins_ok": margins}

    title_norm = None
    h1_ok, h2_ok, body_chars, size_ok, font_ok, sp_ok, sp_n = {}, {}, 0, 0, 0, 0, 0
    paras = dx.body_paragraphs()
    in_tables = [p for t in dx.tables() for p in t.iter(L.q("w:p"))]
    for p in paras + in_tables:
        text = dx.ptext(p).strip()
        if not text:
            continue
        hit1 = next((t for t in exp["heading1"] if _title_match(t, text)), None)
        hit2 = next((t for t in exp["heading2"] if _title_match(t, text)), None)
        r = _first_run(p)
        if hit1 and hit1 not in h1_ok and p in paras:
            h1_ok[hit1] = (_sname(dx, p) == "heading1", abs(dx.run_size(p, r) - 14) <= 0.5, dx.run_bold(p, r))
            continue
        if hit2 and hit2 not in h2_ok and p in paras:
            h2_ok[hit2] = (_sname(dx, p) == "heading2", abs(dx.run_size(p, r) - 12) <= 0.5, dx.run_bold(p, r))
            continue
        if title_norm is None and L.similar(text, "TeleRehab-Home: a randomised feasibility study") > 0.5 \
                and text.startswith("TeleRehab"):
            title_norm = text
            continue
        for run in p.iter(L.q("w:r")):
            n = len("".join(t.text or "" for t in run.iter(L.q("w:t"))))
            if not n:
                continue
            body_chars += n
            size_ok += n * (abs(dx.run_size(p, run) - 11) <= 0.25)
            font_ok += n * (dx.run_font(p, run).lower() in ("liberation sans", "arial"))
        if p in paras:
            sp_n += 1
            line, rule = dx.ppr_val(p, "w:spacing", "w:line"), dx.ppr_val(p, "w:spacing", "w:lineRule")
            sp_ok += line is not None and abs(int(float(line)) - 276) <= 8 and (rule or "auto") == "auto"
    f_size = size_ok / body_chars if body_chars else 0
    f_font = font_ok / body_chars if body_chars else 0
    f_sp = sp_ok / sp_n if sp_n else 0
    s_h1 = sum(all(v) for v in h1_ok.values()) / len(exp["heading1"])
    s_h2 = sum(all(v) for v in h2_ok.values()) / len(exp["heading2"])
    checks["body"] = {"chars": body_chars, "11pt": round(f_size, 3), "sans_font": round(f_font, 3),
                      "spacing_1.15": round(f_sp, 3)}
    checks["heading1"] = {k: v for k, v in h1_ok.items()}
    checks["heading2"] = {k: v for k, v in h2_ok.items()}

    # header / footer
    htexts, _, hroots = dx.header_footer("header")
    ftexts, finstr, froots = dx.header_footer("footer")
    head_ref = any(exp["ref"] in t for t in htexts)
    head_clean = head_ref and not any(re.search(r"draft|internal", t, re.I) for t in htexts)
    head_right = any(_jc(dx, p) in ("right", "end") for root in hroots for p in root.iter(L.q("w:p"))
                     if exp["ref"] in dx.ptext(p))
    fields = " ".join(finstr).upper()
    foot_fields = "PAGE" in fields.replace("NUMPAGES", "") and "NUMPAGES" in fields
    foot_text = any(re.search(r"page.*of", t, re.I) for t in ftexts)
    foot_center = any(_jc(dx, p) == "center" for root in froots for p in root.iter(L.q("w:p"))
                      if "page" in dx.ptext(p).lower())
    checks["header"] = {"texts": [t[:60] for t in htexts], "has_ref": head_ref, "no_draft": head_clean,
                        "right_aligned": head_right}
    checks["footer"] = {"texts": [t[:40] for t in ftexts], "fields": fields[:80], "page_x_of_y": foot_fields and foot_text,
                        "centred": foot_center}

    # references
    refs_idx = next((i for i, p in enumerate(paras) if _title_match("7. References", dx.ptext(p).strip())), None)
    refs = [p for p in paras[refs_idx + 1:] if dx.ptext(p).strip()] if refs_idx is not None else []
    surnames = [L.norm(dx.ptext(p)).split()[0].strip(",.") for p in refs]
    want = [L.norm(r).split()[0].strip(",.") for r in exp["refs_sorted"]]
    order_ok = surnames[:len(want)] == want
    hang = 0
    for p in refs:
        hv = dx.ppr_val(p, "w:ind", "w:hanging")
        left = dx.ppr_val(p, "w:ind", "w:left") or dx.ppr_val(p, "w:ind", "w:start")
        hang += hv is not None and abs(int(float(hv)) - 567) <= 30 and left is not None and abs(int(float(left)) - 567) <= 30
    hang_ok = bool(refs) and hang >= len(want) - 1
    checks["references"] = {"order": surnames, "alphabetical": order_ok, "hanging_1cm": f"{hang}/{len(refs)}"}

    # submission PDF
    pdf = fetch(env, f"{DIR}/{exp['pdf_name']}", dest + ".pdf")
    s_pdf, pinfo = 0.0, {"exists": bool(pdf)}
    if pdf:
        meta, pages = L.pdf_meta(pdf), L.pdf_pages(pdf)
        if meta and pages:
            fits = meta["pages"] <= 6 and all(abs(a - 595) <= 3 and abs(b - 842) <= 3 for a, b in meta["sizes"])
            marks = all(exp["ref"] in t and re.search(r"page\s*\d+\s*of\s*\d+", t, re.I) for t in pages)
            s_pdf = (1 + fits + marks) / 3
            pinfo.update(pages=meta["pages"], a4_and_max6=fits, ref_and_page_numbers_on_every_page=marks)
    checks["pdf"] = pinfo

    score = (0.05 * a4 + 0.1 * sum(margins.values()) / 4 + 0.1 * f_size + 0.05 * f_font + 0.05 * f_sp +
             0.15 * s_h1 + 0.05 * s_h2 + 0.05 * head_ref + 0.03 * head_clean + 0.02 * head_right +
             0.07 * (foot_fields and foot_text) + 0.03 * foot_center + 0.05 * order_ok + 0.05 * hang_ok + 0.15 * s_pdf)
    return result(score, checks)
