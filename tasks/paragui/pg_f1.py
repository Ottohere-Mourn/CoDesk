"""F1 - a ceramics shop's product shoot: culling/organising the frames (cull) vs making the webshop images (web).

Shared live state: one Nautilus window on the shoot folder, one LibreOffice Calc window with the photographer's
workbook (task A fills sheet "Shot list", task B fills sheet "Web images" - same open document), one GIMP instance.
"""
from __future__ import annotations

import os
import re

from evaluation_examples.task_class.pg_common import ASSETS, HOME, expected, fetch, result, sh, tree, upload
from evaluation_examples.task_class import pg_fimg as fi

SHOOT = f"{HOME}/Pictures/Shoot_2026-10-14"
WB = f"{SHOOT}/Shoot_2026-10-14.xlsx"
WEB = f"{HOME}/Documents/Webshop"
REL = "Pictures/Shoot_2026-10-14"


def setup(sc):
    upload(sc, [("f1/shoot.tar.gz", "/tmp/pgf1_shoot.tar.gz"), ("f1/webshop/KF-108.jpg", f"{WEB}/web/KF-108.jpg")])
    sh(sc, "mkdir -p ~/Pictures ~/Documents/Webshop/xcf ~/Documents/Webshop/web ~/.cache; "
           "[ -f ~/.cache/.pgf1_ready ] || { tar xzf /tmp/pgf1_shoot.tar.gz -C ~/Pictures && touch ~/.cache/.pgf1_ready; }; "
           "rm -f /tmp/pgf1_shoot.tar.gz")
    sc.launch(f"[ -e /tmp/.pgf1_nautilus ] || {{ touch /tmp/.pgf1_nautilus; exec nautilus '{SHOOT}'; }}", shell=True)
    sc.launch(f"pgrep -x gimp-2.10 >/dev/null || pgrep -x gimp >/dev/null || exec gimp '{WEB}/web/KF-108.jpg'", shell=True)
    sc._open_setup(WB)


def _workbook(env, dest):
    path = fetch(env, WB, dest + ".xlsx")
    if not path:
        path = fetch(env, WB[:-5] + ".ods", dest + ".ods")
    return path


def _norm_sku(v) -> str:
    m = re.search(r"KF\s*[-_ ]?\s*(\d{3})", str(v or ""), re.I)
    return f"KF-{m.group(1)}" if m else ""


def _blank(v) -> bool:
    return fi.cell_text(v).lower() in ("", "-", "--", "n/a", "na", "none", "/")


def _upright(frame):
    from PIL import Image
    im = Image.open(os.path.join(ASSETS, "f1/shoot", frame["name"]))
    im.load()
    return im.transpose(Image.ROTATE_90) if frame["rot"] else im


# ---------------------------------------------------------------- task A: cull and organise
def evaluate_cull(env, dest: str) -> dict:
    from PIL import Image
    exp = expected("f1")
    frames = exp["frames"]
    t = tree(env, ["~/Pictures"])
    low = {k.lower(): (k, v) for k, v in t.items()}
    rejects = [f for f in frames if f["status"] == "reject"]
    keepers = [f for f in frames if f["status"] == "keep"]
    rej_ok = [f["name"] for f in rejects if low.get(f"{REL}/Rejects/{f['name']}".lower(), (0, 0))[1] == f["md5"]]
    keep_ok, rot_detail = [], {}
    for f in keepers:
        rel = f"{REL}/Selects/{f['sku']}/{f['new_name']}".lower()
        if rel not in low:
            continue
        if not f["rot"]:
            if low[rel][1] == f["md5"]:
                keep_ok.append(f["new_name"])
            continue
        p = fetch(env, f"{HOME}/{low[rel][0]}", f"{dest}_{f['new_name']}")
        try:
            got = Image.open(p)
            got.load()
            ref = _upright(f)
            c = fi.thumb_corr(got, ref)
            dc = fi.detail_corr(got, ref, size=(320, 480)) if got.size[1] > got.size[0] else -1.0
            rot_detail[f["new_name"]] = {"size": list(got.size), "corr_upright": round(c, 3), "detail_corr": round(dc, 3)}
            if got.size[1] > got.size[0] and c > 0.9 and dc > 0.6:  # upright, not mirrored/flipped
                keep_ok.append(f["new_name"])
        except Exception as e:  # noqa: BLE001
            rot_detail[f["new_name"]] = f"unreadable: {e}"
    originals = {f["name"] for f in frames}
    left = [k for k in t if k.startswith(REL + "/") and k.count("/") == 2 and k.split("/")[-1] in originals]
    want_sel = {f"{REL}/Selects/{f['sku']}/{f['new_name']}".lower() for f in keepers}
    extra_sel = [k for k in t if k.lower().startswith(f"{REL}/selects/".lower()) and k.lower() not in want_sel
                 and not os.path.basename(k).startswith(".")]
    # the shot list
    path = _workbook(env, dest)
    _, rows = fi.table(fi.sheet_rows(path, "Shot list"), "File")
    by = {fi.cell_text(r.get("file")): r for r in rows}
    n = len(frames)
    sku_ok = status_ok = name_ok = 0
    wrong = []
    for f in frames:
        r = by.get(f["name"], {})
        want_sku = f["sku"] if f["kind"] in ("slate", "product", "copy") else ""
        got_sku = _norm_sku(r.get("sku"))
        st = fi.cell_text(r.get("status")).lower()
        st_ok = st.startswith(f["status"])
        filled = bool(st)  # blank SKU / New name cells only count as answers on rows the agent actually processed
        s_ok = filled and (got_sku == want_sku or (f["kind"] == "copy" and not got_sku))
        nn = os.path.basename(fi.cell_text(r.get("new name")).replace("\\", "/")).lower()
        n_ok = nn == f["new_name"].lower() if f["status"] == "keep" else filled and _blank(r.get("new name"))
        sku_ok += s_ok
        status_ok += st_ok
        name_ok += n_ok
        if not (s_ok and st_ok and n_ok) and len(wrong) < 10:
            wrong.append([f["name"], r.get("sku"), r.get("status"), r.get("new name")])
    sheets = fi.sheet_names(path) if path else []
    both_sheets = {"shot list", "web images"} <= {s.strip().lower() for s in sheets}
    stray_ok = not left and not extra_sel
    score = (0.20 * len(rej_ok) / len(rejects) + 0.30 * len(keep_ok) / len(keepers) + 0.10 * stray_ok
             + 0.10 * sku_ok / n + 0.15 * status_ok / n + 0.15 * name_ok / n)
    if not keep_ok:
        score = min(score, 0.4)
    if path and not both_sheets:  # the workbook was rebuilt/overwritten without the other sheet
        score = min(score, 0.7)
    checks = {"rejects_in_place": f"{len(rej_ok)}/{len(rejects)}", "keepers_in_place": f"{len(keep_ok)}/{len(keepers)}",
              "rotated": rot_detail, "originals_left_at_top": left[:8], "unexpected_in_selects": extra_sel[:8],
              "workbook": bool(path), "sheets": sheets, "shotlist_sku": f"{sku_ok}/{n}",
              "shotlist_status": f"{status_ok}/{n}", "shotlist_new_name": f"{name_ok}/{n}", "shotlist_wrong": wrong}
    return result(score, checks)


# ---------------------------------------------------------------- task B: web images
def evaluate_web(env, dest: str) -> dict:
    from PIL import Image
    exp = expected("f1")
    frames = exp["frames"]
    path = _workbook(env, dest)
    _, rows = fi.table(fi.sheet_rows(path, "Web images"), "SKU")
    by = {_norm_sku(r.get("sku")): r for r in rows}
    per, checks, any_jpg = [], {}, False
    for sku in exp["web_skus"]:
        c = {}
        cand = [f for f in frames if f["sku"] == sku and f["kind"] == "product"]
        jp = fetch(env, f"{WEB}/web/{sku}.jpg", f"{dest}_{sku}.jpg")
        size_ok = q_ok = crop_ok = sharp_ok = wm_ok = False
        if jp:
            try:
                out = Image.open(jp)
                out.load()
                any_jpg = True
                size_ok = out.size == (1200, 1200) and out.format == "JPEG"
                q = fi.jpeg_quality(jp)
                q_ok = q is not None and 84 <= q <= 86
                c.update(size=list(out.size), quality=q)
                out = out.convert("RGB")
                best = None
                for f in cand:
                    src = _upright(f)
                    sc, x, y, side = fi.find_square_crop(out, src)
                    if best is None or sc > best[0]:
                        best = (sc, x, y, side, f, src)
                sc, x, y, side, f, src = best
                bx0, by0, bx1, by1 = f["box"]
                tol = 6
                inside = x <= bx0 + tol and y <= by0 + tol and x + side >= bx1 - tol and y + side >= by1 - tol
                fill = max(bx1 - bx0, by1 - by0) / side
                crop_ok = sc >= 0.85 and inside and fill >= 0.45
                sharp_ok = crop_ok and not f["blurred"]
                mask = fi.overlay_mask(out, src, (x, y, side))
                wm = fi.text_overlay_in_corner(mask, "br")
                wm_ok = sc >= 0.8 and wm["ok"]
                c.update(match=round(sc, 3), source=f["name"], crop=[x, y, side], product_inside=inside,
                         product_fill=round(fill, 2), blurred_source=f["blurred"], watermark=wm)
            except Exception as e:  # noqa: BLE001
                c["error"] = repr(e)
        xp = fetch(env, f"{WEB}/xcf/{sku}.xcf", f"{dest}_{sku}.xcf")
        info = fi.xcf_info(xp) if xp else None
        xcf_ok = bool(info) and (info["width"], info["height"]) == (1200, 1200) and len(info["layers"]) >= 2 and any(
            ly["text"] and re.search(r"kestrel\s*(&|and)\s*fern", ly["text"], re.I) for ly in info["layers"])
        c["xcf"] = None if not info else {"size": [info["width"], info["height"]],
                                          "layers": [(ly["name"], ly["text"]) for ly in info["layers"]][:6]}
        r = by.get(sku, {})
        srcname = os.path.basename(fi.cell_text(r.get("source frame")).replace("\\", "/")).lower()
        sharp_names = {f["name"].lower() for f in cand if not f["blurred"]} | {
            f["new_name"].lower() for f in cand if f.get("new_name")}
        src_ok = srcname in sharp_names
        dims_ok = fi.num(r.get("width px")) == 1200 and fi.num(r.get("height px")) == 1200
        c.update(sheet_source=r.get("source frame"), sheet_source_ok=src_ok, sheet_dims_ok=dims_ok)
        s = (0.10 * size_ok + 0.10 * q_ok + 0.25 * crop_ok + 0.10 * sharp_ok + 0.15 * wm_ok + 0.15 * xcf_ok
             + 0.10 * src_ok + 0.05 * dims_ok)
        c.update(jpg=bool(jp), size_ok=size_ok, quality_ok=q_ok, crop_ok=crop_ok, sharp_ok=sharp_ok,
                 watermark_ok=wm_ok, xcf_ok=xcf_ok, score=round(s, 3))
        per.append(s)
        checks[sku] = c
    score = sum(per) / len(per)
    if not any_jpg:
        score = 0.0
    checks["workbook"] = bool(path)
    return result(score, checks)
