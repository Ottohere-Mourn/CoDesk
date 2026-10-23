"""o2 - one Writer document: resolving three reviewers' tracked changes per the call notes (scan) vs inserting the new
Data Protection clause from the client's rider (scan), renumbering, updating the TOC and exporting a PDF."""
from __future__ import annotations

import re

from evaluation_examples.task_class import pg_olib as L
from evaluation_examples.task_class.pg_common import HOME, expected, fetch, guest, result, upload

DIR = f"{HOME}/Documents/Contracts"
DOCX = f"{DIR}/Brightline_MSA_v4.docx"
PDF = f"{DIR}/Brightline_MSA_DPA_review.pdf"
REJECTED = f"{DIR}/Brightline_rejected_points.txt"


def setup(sc):
    upload(sc, [("o2/Contracts/Brightline_MSA_v4.docx", DOCX),
                ("o2/Contracts/Email_from_Hannah.txt", f"{DIR}/Email_from_Hannah.txt"),
                ("o2/Contracts/call_notes_2026-10-14.pdf", f"{DIR}/call_notes_2026-10-14.pdf"),
                ("o2/Contracts/Rider_DP-1_Data_Protection.pdf", f"{DIR}/Rider_DP-1_Data_Protection.pdf")])
    sc._open_setup(DOCX)


def _open(env, dest):
    path = fetch(env, DOCX, dest + ".docx")
    if not path:
        return None, "missing"
    try:
        return L.Docx(path), None
    except Exception as e:  # noqa: BLE001
        return None, f"unreadable: {e}"


# ---------------------------------------------------------------- task A: resolve the tracked changes
@L.safe
def evaluate_redlines(env, dest: str) -> dict:
    exp = expected("o2")
    dx, err = _open(env, dest)
    if dx is None:
        return result(0.0, {"document": err})
    text = L.norm(dx.full_text())
    revs = [(k, a, L.norm(t)) for k, a, t in dx.revisions()]
    reviewers = set(exp["authors"])
    left = [(k, a, t[:60]) for k, a, t in revs if a in reviewers]

    per, detail = [], {}
    for ch in exp["changes"]:
        def hit(frag, t):
            return t.strip() == frag[1:] if frag.startswith("=") else frag in t
        pending = any(hit(L.norm(f), t) for f in ch["frags"] for _, _, t in revs)
        ok_yes = ch["yes"] is None or L.norm(ch["yes"]) in text
        ok_no = ch["no"] is None or L.norm(ch["no"]) not in text
        ok = ok_yes and ok_no and not pending
        per.append(ok)
        detail[ch["id"]] = ("ok" if ok else "pending" if pending else "wrong outcome") + \
            f" ({'accept' if ch['accept'] else 'reject'}: {ch['topic']})"
    resolved = not left
    comments = [(a, t[:50]) for _, a, t in dx.comments() if a in reviewers]

    note = guest(env, f"cat {REJECTED} 2>/dev/null")
    low = note.lower()
    points = {k: bool(re.search(p, low)) for k, p in exp["rejected_points"].items()}
    lines = [ln for ln in note.splitlines() if ln.strip()]
    s_note = sum(points.values()) / len(points) if note.strip() else 0.0

    score = 0.6 * sum(per) / len(per) + 0.1 * resolved + 0.1 * (not comments) + 0.2 * s_note
    if sum(per) == 0:
        score = min(score, 0.2)
    checks = {"changes": detail, "correct": f"{sum(per)}/{len(per)}", "reviewer_revisions_left": left[:8],
              "all_resolved": resolved, "reviewer_comments_left": comments, "rejected_points_file": points,
              "rejected_points_lines": len(lines)}
    return result(score, checks)


# ---------------------------------------------------------------- task B: data protection clause, renumbering, TOC, PDF
def _is_toc(dx, p):
    sid = (dx.para_style(p) or "") + " " + dx.para_style_name(p)
    if re.search(r"\b(toc|contents) ?\d", sid, re.I):
        return True
    for a in p.iterancestors(L.q("w:sdt")):
        g = a.find(".//w:docPartGallery", L.WNS)
        if g is not None and "content" in (g.get(L.q("w:val")) or "").lower():
            return True
    return False


def _heading_re(title):
    return re.compile(r"^\s*(\d+)\.?\s+" + re.escape(L.norm(title)) + r"\s*$")


@L.safe
def evaluate_dpa(env, dest: str) -> dict:
    exp = expected("o2")
    dx, err = _open(env, dest)
    if dx is None:
        return result(0.0, {"document": err})
    titles = exp["titles_new"]
    paras = [p for p in dx.body_paragraphs()]
    body = [(p, L.norm(dx.ptext(p))) for p in paras if not _is_toc(dx, p)]
    toc = [L.norm(dx.ptext(p)) for p in paras if _is_toc(dx, p)]

    # headings in the body (first match per title)
    heads = {}
    for i, (p, t) in enumerate(body):
        for title in titles:
            m = _heading_re(title).match(t)
            if m and title not in heads:
                heads[title] = (i, int(m.group(1)), p)
    ordered = sorted(heads.items(), key=lambda kv: kv[1][0])
    dp = heads.get("Data Protection")
    conf, warr = heads.get("Confidentiality"), heads.get("Warranties")
    new_ok = bool(dp and dp[1] == 8 and conf and warr and conf[0] < dp[0] < warr[0])
    styled = bool(dp and conf and dx.para_style_name(dp[2]) == dx.para_style_name(conf[2]))
    renum = [title for n, title in enumerate(titles, 1) if heads.get(title, (0, None))[1] == n]
    renum_after = [t for t in titles[8:] if t in renum]

    # sub-clause numbers inside each clause = clause number
    sub_ok, sub_detail = 0, {}
    for k, (title, (i, n, _)) in enumerate(ordered):
        if title not in titles[7:]:
            continue
        end = ordered[k + 1][1][0] if k + 1 < len(ordered) else len(body)
        nums = [int(m.group(1)) for _, t in body[i + 1:end] for m in [re.match(r"^\s*(\d+)\.\d+\b", t)] if m]
        good = bool(nums) and all(x == titles.index(title) + 1 for x in nums)
        sub_ok += good
        sub_detail[title] = nums[:6]
    n_sub = len(titles[7:])

    # new clause text and definition
    sec8 = []
    if dp:
        nxt = next((v[0] for t, v in ordered if v[0] > dp[0]), len(body))
        sec8 = [t for _, t in body[dp[0] + 1:nxt]]
    rider_hits = 0
    for para in exp["rider"]:
        want = re.sub(r"^\d+\.\d+\s*", "", para)
        best = max([L.similar(re.sub(r"^\s*\d+\.\d+\s*", "", t), want) for t in sec8] + [0.0])
        rider_hits += best >= 0.9
    sec1 = []
    if "Definitions and Interpretation" in heads:
        i1 = heads["Definitions and Interpretation"][0]
        nxt = next((v[0] for t, v in ordered if v[0] > i1), len(body))
        sec1 = [t for _, t in body[i1 + 1:nxt]]
    def_ok = max([L.similar(t, exp["rider_def"]) for t in sec1] + [0.0]) >= 0.88

    # cross references
    full = L.norm(" ".join(t for _, t in body))
    xr_ok, xr_detail = 0, {}
    for k, (pat, want) in enumerate(exp["xrefs"], 1):
        m = re.search(pat, full)
        got = list(m.groups()) if m else None
        xr_ok += got == want
        xr_detail[f"x{k}"] = f"{got} (want {want})"
    m = re.search(r"clauses ([\d ,and]+?) shall survive termination", full)
    surv = sorted(int(x) for x in re.findall(r"\d+", m.group(1))) if m else []
    surv_ok = surv == sorted(exp["survive_new"])
    n_xr = len(exp["xrefs"]) + 1
    xr_ok += surv_ok

    # TOC inside the document
    toc_hits = 0
    for n, title in enumerate(titles, 1):
        toc_hits += any(re.match(rf"^\s*{n}\.?\s+{re.escape(L.norm(title))}\s*(\.|…|\s)*\d*\s*$", t) for t in toc)

    # exported PDF: contains the clause, its own TOC page numbers agree with where the headings are
    s_pdf, pdf_info = 0.0, {"exists": False}
    ppath = fetch(env, PDF, dest + ".pdf")
    if ppath:
        try:
            pages = L.pdf_lines(ppath)
        except Exception:  # noqa: BLE001
            pages = None
        if pages:
            pdf_info["exists"] = True
            flat = " ".join(t for pg in pages for _, t in pg)
            clause = L.best_window(flat, re.sub(r"^\d+\.\d+\s*", "", exp["rider"][2])) >= 0.85
            toc_pages = {i for i, pg in enumerate(pages) if any(L.norm(t) in ("contents", "table of contents") for _, t in pg)}
            entries = {}
            for i in toc_pages:
                for _, t in pages[i]:
                    m = re.match(r"^\s*(\d+)\.?\s+(.+?)[\s.…]*?(\d+)\s*$", t)
                    if m:
                        entries[(int(m.group(1)), L.norm(m.group(2)).rstrip(". "))] = int(m.group(3))
            agree, offsets = 0, []
            for n, title in enumerate(titles, 1):
                tp = entries.get((n, L.norm(title)))
                bp = next((i + 1 for i, pg in enumerate(pages) if i not in toc_pages
                           for _, t in pg if _heading_re(title).match(L.norm(t)) and
                           int(_heading_re(title).match(L.norm(t)).group(1)) == n), None)
                if tp is not None and bp is not None:
                    offsets.append(tp - bp)
            if offsets:
                off = max(set(offsets), key=offsets.count)
                agree = sum(1 for o in offsets if o == off)
            pdf_info.update(clause_text=clause, toc_entries=len(entries), toc_matches_pages=f"{agree}/{len(titles)}")
            s_pdf = 0.5 * clause + 0.5 * agree / len(titles)

    score = (0.1 * new_ok + 0.05 * styled + 0.15 * rider_hits / len(exp["rider"]) + 0.05 * def_ok +
             0.1 * len(renum_after) / len(titles[8:]) + 0.1 * sub_ok / n_sub + 0.15 * xr_ok / n_xr +
             0.1 * toc_hits / len(titles) + 0.2 * s_pdf)
    if not dp:
        score = min(score, 0.3)
    checks = {"clause8_heading_in_place": new_ok, "same_heading_style": styled,
              "rider_paragraphs": f"{rider_hits}/{len(exp['rider'])}", "definition_added": def_ok,
              "headings": {t: v[1] for t, v in heads.items()}, "subclause_numbers": sub_detail,
              "xrefs": xr_detail, "survival_list": surv, "toc_entries_ok": f"{toc_hits}/{len(titles)}", "pdf": pdf_info}
    return result(score, checks)
