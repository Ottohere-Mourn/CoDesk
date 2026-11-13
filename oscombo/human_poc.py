"""Minimum Human-Agent Shared Desktop PoC on the existing OSWorld Guest + Codex GUI Harness."""
from __future__ import annotations

import argparse
import json
import os
import secrets
import subprocess
import threading
import time
import traceback
import uuid
from pathlib import Path
from typing import Any

from .eventlog import EventLog
from .guest import Guest, InfraError
from .human_actor import GUIAction, ScriptedGUIActor, agent_task_actions as _baseline_agent_actions
from .human_actor import user_task_actions as _baseline_user_actions
from .human_casebook import CASEBOOK, get_case

USER_LINE = "Status verified: PO-441 completed."
USER_TASK = f"Open service-report.txt in LibreOffice Writer. Append exactly {USER_LINE!r} as the final non-empty line and save."
AGENT_TASK = ("In the already-open LibreOffice Calc workbook budget.xlsx, find row 2 for Router. "
              "Change C2 (Quantity) from 2 to 3 and E2 (Notes) to exactly 'Approved PO-441'. "
              "Leave other source values unchanged, save, and verify.")
CLIPBOARD_USER_LINE = "Invoice total: 79"
CLIPBOARD_AGENT_VALUE = "PO-441"
SELECTION_USER_TASK = ("In the already-open Calc workbook, correct the Router unit price in B2 from 39.5 to 42. "
                       "Do not change the item label or other source cells. Save and verify.")
SELECTION_AGENT_TASK = ("In the already-open Calc workbook, find the Router row. Set C2 (Quantity) to 3 and "
                        "E2 (Notes) to exactly 'Approved PO-441'. Leave other source values unchanged, save, "
                        "and verify.")
MODES = ("user-only", "agent-only", "independent", "shared", "shared-lock", "forced-probe")
NS = {
    "office": "urn:oasis:names:tc:opendocument:xmlns:office:1.0",
    "table": "urn:oasis:names:tc:opendocument:xmlns:table:1.0",
    "text": "urn:oasis:names:tc:opendocument:xmlns:text:1.0",
}


class FocusMonitor:
    def __init__(self, guest: Guest, guest_id: str, log: EventLog, out: Path, interval: float = 0.5):
        self.guest, self.guest_id, self.log, self.out = guest, guest_id, log, out
        self.interval = interval
        self.stop_event = threading.Event()
        self.thread = threading.Thread(target=self._run, name=f"focus-{guest_id}", daemon=True)
        self.transitions = 0

    def start(self) -> None:
        self.thread.start()

    def stop(self) -> None:
        self.stop_event.set()
        self.thread.join(timeout=15)

    def _run(self) -> None:
        old = self.guest.active_window_info()
        self.log.emit("monitor", "focus_baseline", guest_id=self.guest_id,
                      window=old.get("title"), window_id=old.get("id"))
        while not self.stop_event.is_set():
            now = self.guest.active_window_info()
            if now.get("id") != old.get("id"):
                self.transitions += 1
                shot = self.out / f"{self.guest_id}-focus-{self.transitions:03d}.png"
                data = b""
                try:
                    data = self.guest.screenshot(patience=30)
                    shot.parent.mkdir(parents=True, exist_ok=True)
                    shot.write_bytes(data)
                except Exception:
                    pass
                windows = None
                try:
                    windows = self.guest.execute(["bash", "-lc", "wmctrl -lG 2>/dev/null || true"],
                                                 timeout=10).get("output", "")[:4000]
                except Exception:
                    pass
                self.log.emit("monitor", "focus_change", guest_id=self.guest_id,
                              previous_window=old.get("title"), window=now.get("title"),
                              previous_window_id=old.get("id"), window_id=now.get("id"),
                              screenshot_path=str(shot) if data else None,
                              screenshot_bytes=len(data), window_inventory=windows)
            elif now.get("title") != old.get("title"):
                self.log.emit("monitor", "window_title_change", guest_id=self.guest_id,
                              window_id=now.get("id"), previous_title=old.get("title"),
                              title=now.get("title"))
            old = now
            self.stop_event.wait(self.interval)


def _exec(guest: Guest, argv: list[str], timeout: float = 60) -> dict:
    r = guest.execute(argv, timeout=timeout)
    if r.get("status") != "success" or int(r.get("returncode", 0)) != 0:
        raise RuntimeError(f"Guest command failed {argv!r}: {r}")
    return r


def _home(guest: Guest) -> Path:
    value = _exec(guest, ["bash", "-lc", "printf %s \"$HOME\""])["output"].strip()
    if not value.startswith("/home/"):
        raise RuntimeError(f"unexpected guest HOME: {value!r}")
    return Path(value)


def _xlsx_parts() -> dict[str, str]:
    main = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"
    rel = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
    strings = ["Item", "Unit price", "Quantity", "Total", "Notes", "Router", "draft"]
    shared = '<sst xmlns="' + main + '" count="7" uniqueCount="7">' + "".join(
        "<si><t>" + x + "</t></si>" for x in strings) + "</sst>"
    sheet = (
        '<worksheet xmlns="' + main + '"><sheetData>'
        '<row r="1"><c r="A1" t="s"><v>0</v></c><c r="B1" t="s"><v>1</v></c>'
        '<c r="C1" t="s"><v>2</v></c><c r="D1" t="s"><v>3</v></c><c r="E1" t="s"><v>4</v></c></row>'
        '<row r="2"><c r="A2" t="s"><v>5</v></c><c r="B2"><v>39.5</v></c>'
        '<c r="C2"><v>2</v></c><c r="D2"><v>79</v></c><c r="E2" t="s"><v>6</v></c></row>'
        '</sheetData></worksheet>')
    return {
        "[Content_Types].xml": (
            '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
            '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
            '<Default Extension="xml" ContentType="application/xml"/>'
            '<Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>'
            '<Override PartName="/xl/worksheets/sheet1.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>'
            '<Override PartName="/xl/sharedStrings.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sharedStrings+xml"/>'
            '</Types>'),
        "_rels/.rels": (
            '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
            '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="xl/workbook.xml"/>'
            '</Relationships>'),
        "xl/workbook.xml": (
            '<workbook xmlns="' + main + '" xmlns:r="' + rel + '">'
            '<sheets><sheet name="Budget" sheetId="1" r:id="rId1"/></sheets></workbook>'),
        "xl/_rels/workbook.xml.rels": (
            '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
            '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet1.xml"/>'
            '<Relationship Id="rId2" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/sharedStrings" Target="sharedStrings.xml"/>'
            '</Relationships>'),
        "xl/worksheets/sheet1.xml": sheet,
        "xl/sharedStrings.xml": shared,
    }


def _png_changed_pixel_ratio(before_png: bytes, after_png: bytes) -> float:
    """Fraction of pixels changed between setup's blank desktop and opened-app screenshot."""
    from io import BytesIO
    from PIL import Image, ImageChops
    before=Image.open(BytesIO(before_png)).convert("RGB")
    after=Image.open(BytesIO(after_png)).convert("RGB")
    if before.size!=after.size:
        after=after.resize(before.size)
    diff=ImageChops.difference(before,after).convert("L")
    hist=diff.histogram()
    return sum(hist[12:])/(before.size[0]*before.size[1])


def _fixture(guest: Guest, home: Path, case_id: str="focus-route-v1", debug_out: Path | None=None) -> dict[str, Any]:
    docs = home / "Documents"
    report, book = docs / "service-report.txt", docs / "budget.xlsx"
    parts = repr(_xlsx_parts())
    reference = r"\nReference: PO-441" if case_id == "clipboard-handoff-v1" else ""
    if case_id == "writer-undo-stack-v1":
        report_seed = (
            "Quarterly Service Report\nDate: 2026-11-09\nStatus: DRAFT\n"
            "Customer impact: wording under review.\n\nCompliance review: pending.\n"
        )
        report_statement = f"p.write_text({report_seed!r},encoding='utf-8')\n"
    else:
        report_statement = (
            "p.write_text('Quarterly Service Report\\nDate: 2026-11-09\\nStatus: DRAFT\\n"
            f"Owner: Operations\\nNotes: Closeout pending.{reference}\\n',encoding='utf-8')\n"
        )
    code = (
        "from pathlib import Path\nfrom zipfile import ZipFile,ZipInfo,ZIP_DEFLATED\n"
        f"p=Path({str(report)!r}); p.parent.mkdir(parents=True,exist_ok=True); "
        f"{report_statement}"
        f"parts={parts}\n"
        f"with ZipFile({str(book)!r},'w',ZIP_DEFLATED) as z:\n"
        "    for k,v in sorted(parts.items()):\n"
        "        info=ZipInfo(k,date_time=(2020,1,1,0,0,0)); info.compress_type=ZIP_DEFLATED\n"
        "        z.writestr(k,v)\n"
    )
    if debug_out is not None:
        debug_out.mkdir(parents=True, exist_ok=True)
        (debug_out / "fixture-create-command.py").write_text(code, encoding="utf-8")
    create_result = _exec(guest, ["python3", "-c", code], 30)
    if debug_out is not None:
        (debug_out / "fixture-create-response.json").write_text(
            json.dumps(create_result, indent=2, ensure_ascii=False), encoding="utf-8")
        check = guest.execute(["bash", "-lc",
            f"ls -la {str(docs)!r}; test -s {str(report)!r} && echo REPORT_OK; "
            f"test -s {str(book)!r} && echo BOOK_OK"], 20)
        (debug_out / "fixture-create-check.json").write_text(
            json.dumps(check, indent=2, ensure_ascii=False), encoding="utf-8")
    desktop_reference=None
    if case_id == "writer-undo-stack-v1":
        desktop_reference=guest.screenshot(patience=60)
        if debug_out is not None:
            debug_out.mkdir(parents=True,exist_ok=True)
            (debug_out/"fixture-desktop-before-writer.png").write_bytes(desktop_reference)
    # Open task documents through LibreOffice's command line in the Guest display; avoid
    # app-icon clicks or per-run profiles, which left Start Center/Untitled windows.
    # The in-Guest /execute service does not guarantee it inherited the desktop's
    # DISPLAY environment. Set DISPLAY explicitly for these GUI-app setup launches.
    # Undo case needs only Writer: avoid starting an unrelated second LibreOffice
    # document/window while testing the shared Writer undo history.
    launch = (
        "import os,subprocess,time\ndn=subprocess.DEVNULL\nenv=os.environ.copy(); env['DISPLAY']=env.get('DISPLAY') or ':0'\n"
        f"subprocess.Popen(['libreoffice','--writer',{str(report)!r}],stdin=dn,stdout=dn,stderr=dn,env=env,start_new_session=True)\n"
    )
    if case_id != "writer-undo-stack-v1":
        launch += ("time.sleep(3)\n" +
                   f"subprocess.Popen(['libreoffice','--calc',{str(book)!r}],stdin=dn,stdout=dn,stderr=dn,env=env,start_new_session=True)\n")
    if debug_out is not None:
        try:
            display_probe=guest.execute(["bash","-lc","printf 'DISPLAY=%s\\nXAUTHORITY=%s\\nXDG_SESSION_TYPE=%s\\n' \"$DISPLAY\" \"$XAUTHORITY\" \"$XDG_SESSION_TYPE\""] ,timeout=15)
            (debug_out / "fixture-display-environment.json").write_text(json.dumps(display_probe,indent=2),encoding="utf-8")
        except Exception as exc:
            (debug_out / "fixture-display-environment.json").write_text(json.dumps({"error":repr(exc)},indent=2),encoding="utf-8")
    _exec(guest,["python3","-c",launch],30)
    required_windows=("service-report.txt",) if case_id == "writer-undo-stack-v1" else ("service-report.txt","budget.xlsx")
    deadline=time.monotonic()+120
    inventory=""
    while time.monotonic()<deadline:
        inventory=guest.execute(["bash","-lc","wmctrl -lG 2>/dev/null || true"],timeout=15).get("output","")
        if all(title in inventory for title in required_windows): break
        time.sleep(2)
    if any(title not in inventory for title in required_windows):
        failure_diagnostics=""
        if debug_out is not None:
            debug_out.mkdir(parents=True, exist_ok=True)
            try:
                (debug_out / "fixture-window-failure.png").write_bytes(guest.screenshot(patience=45))
            except Exception:
                pass
            try:
                diagnostics=guest.execute(["bash","-lc",
                    "echo FILES; ls -la ~/Documents; "
                    "echo PROCESSES; ps -ef | grep -E '[s]office|[l]ibreoffice'; "
                    "echo WINDOWS; wmctrl -lpGx 2>/dev/null || true; "
                    "echo ACTIVE; xdotool getactivewindow getwindowname 2>/dev/null || true; "
                    "echo WINDOW_TREE; xwininfo -root -tree 2>/dev/null | head -80"],timeout=20).get("output","")
                failure_diagnostics=diagnostics
                (debug_out / "fixture-window-failure.txt").write_text(
                    "INVENTORY\n"+inventory+"\nDIAGNOSTICS\n"+diagnostics,encoding="utf-8")
            except Exception as exc:
                failure_diagnostics=repr(exc)
                (debug_out / "fixture-window-failure.txt").write_text(failure_diagnostics,encoding="utf-8")
        raise InfraError("required document windows not ready: "+inventory[-2000:]+
                         "\nSETUP_DIAGNOSTICS\n"+failure_diagnostics[-4000:])
    focus=("ids=$(xdotool search --onlyvisible --name 'service-report.txt' 2>/dev/null || true); "
           "wid=$(printf '%s\\n' \"$ids\" | tail -n 1); "
           "if [ -n \"$wid\" ]; then xdotool windowactivate --sync \"$wid\"; xdotool windowraise \"$wid\"; fi")
    _exec(guest,["bash","-lc",focus],15)
    visible_change_ratio=None
    if case_id=="writer-undo-stack-v1":
        # The WM title appeared in a previous false-positive run while the visible
        # Guest still showed only the wallpaper. Allow LO a short settling window,
        # then fail setup if no actual document-sized screen change is rendered.
        time.sleep(5)
        opened_screenshot=guest.screenshot(patience=60)
        visible_change_ratio=_png_changed_pixel_ratio(desktop_reference or b"",opened_screenshot)
        if debug_out is not None:
            (debug_out/"fixture-writer-after-open.png").write_bytes(opened_screenshot)
            (debug_out/"fixture-window-visibility.json").write_text(json.dumps({
                "changed_pixel_ratio":visible_change_ratio,"minimum_ratio":0.02,
                "initial_focus":guest.active_window(),"window_inventory":inventory},indent=2),encoding="utf-8")
        if visible_change_ratio < 0.02:
            raise InfraError(f"Writer title exists but its window is not visibly rendered: changed_pixel_ratio={visible_change_ratio:.6f}")
    hash_code=("import hashlib,json\nfrom pathlib import Path\n"
               f"print(json.dumps({{n:hashlib.sha256(Path(p).read_bytes()).hexdigest() for n,p in {{'report':{str(report)!r},'workbook':{str(book)!r}}}.items()}}))\n")
    hashes=json.loads(_exec(guest,["python3","-c",hash_code],30).get("output","{}"))
    result = {"report":str(report),"workbook":str(book),"window_inventory":inventory,
              "initial_focus":guest.active_window() or "","initial_file_sha256":hashes}
    if visible_change_ratio is not None:
        result["visible_window_change_ratio"]=round(visible_change_ratio,6)
    if case_id == "modal-export-v1":
        result["pdf"] = str(docs / "budget-export.pdf")
    return result



def _read(guest: Guest, path: str) -> str:
    code = f"from pathlib import Path; print(Path({path!r}).read_text(encoding='utf-8'))"
    return _exec(guest, ["python3", "-c", code], 30).get("output", "")


def _read_workbook_cells(guest: Guest, path: str) -> dict[str, str]:
    import json
    code = """
import json
from zipfile import ZipFile
from xml.etree import ElementTree as ET
p=__BOOK__
z=ZipFile(p)
main="{http://schemas.openxmlformats.org/spreadsheetml/2006/main}"
strings=[]
try:
    root=ET.fromstring(z.read("xl/sharedStrings.xml"))
    for si in root.findall(main+"si"):
        strings.append("".join((x.text or "") for x in si.findall(".//"+main+"t")))
except KeyError:
    pass
sheet=ET.fromstring(z.read("xl/worksheets/sheet1.xml"))
cells={}
for c in sheet.findall(".//"+main+"c"):
    v=c.find(main+"v")
    value="" if v is None else (v.text or "")
    kind=c.attrib.get("t")
    if kind=="s" and value:
        value=strings[int(value)]
    elif kind=="inlineStr":
        inline=c.find(main+"is")
        value="" if inline is None else "".join((x.text or "") for x in inline.findall(".//"+main+"t"))
    cells[c.attrib.get("r","")]=value
print(json.dumps(cells))
""".replace("__BOOK__",repr(path))
    return json.loads(_exec(guest,["python3","-c",code],30).get("output","{}"))


def _writer_undo_report_oracle(report: str) -> dict[str, Any]:
    lines=report.lstrip(chr(0xfeff)).splitlines()
    base=["Quarterly Service Report","Date: 2026-11-09","Status: DRAFT",
          "Customer impact: wording under review.","","Compliance review: pending."]
    source_preserved=lines[:len(base)]==base
    original_count=lines.count("Customer impact: wording under review.")
    replacement_count=lines.count("Customer impact: customer notified")
    note="Compliance review: PO-441 verified."
    note_count=lines.count(note)
    return {
        "user":{"success":source_preserved and original_count==1 and replacement_count==0,
                "source_sections_preserved":source_preserved,"original_wording_count":original_count,
                "temporary_wording_count":replacement_count,"report_text":report},
        "agent":{"success":source_preserved and note_count==1,
                  "source_sections_preserved":source_preserved,"note_count":note_count,"report_text":report},
    }


def _case_user_actions(case_id: str) -> list[GUIAction]:
    if case_id == "focus-route-v1":
        return _baseline_user_actions()
    if case_id == "clipboard-handoff-v1":
        return [
            GUIAction("focus_calc", "pyautogui.click(24, 405)", "Calc"),
            GUIAction("invoice_calc_home", "pyautogui.hotkey('ctrl','home')", "Calc"),
            GUIAction("select_invoice_total_column", "pyautogui.press('right', presses=3, interval=0.08)", "Calc"),
            GUIAction("select_invoice_total_row", "pyautogui.press('down')", "Calc"),
            GUIAction("copy_invoice_total", "pyautogui.hotkey('ctrl','c')", "Calc"),
            GUIAction("focus_writer", "pyautogui.click(24, 338)", "Writer"),
            GUIAction("writer_document_end", "pyautogui.hotkey('ctrl','end')", "Writer"),
            GUIAction("begin_invoice_line", "pyautogui.press('enter')", "Writer"),
            GUIAction("type_invoice_label", "pyautogui.write('Invoice total: ')", "Writer"),
            GUIAction("paste_invoice_total_refocus_writer",
                      "pyautogui.click(24, 338); pyautogui.hotkey('ctrl','end'); pyautogui.hotkey('ctrl','v')"),
            GUIAction("save_writer_refocus",
                      "pyautogui.click(24, 338); pyautogui.hotkey('ctrl','s')"),
        ]
    if case_id == "calc-selection-drift-v1":
        return [
            GUIAction("focus_calc", "pyautogui.click(24, 405)", "Calc"),
            GUIAction("user_calc_home", "pyautogui.hotkey('ctrl','home')", "Calc"),
            GUIAction("select_user_price_column", "pyautogui.press('right')", "Calc"),
            GUIAction("select_user_price_row", "pyautogui.press('down')", "Calc"),
            GUIAction("enter_user_price_b2", "pyautogui.write('42')", "Calc"),
            GUIAction("commit_user_price_b2", "pyautogui.press('enter')", "Calc"),
            GUIAction("save_workbook", "pyautogui.hotkey('ctrl','s')", "Calc"),
        ]
    if case_id == "writer-undo-stack-v1":
        return [
            # Fixture setup already activates this single Writer document. Do not
            # click a hard-coded dock coordinate: GNOME icon order varies by image.
            GUIAction("find_user_wording", "pyautogui.hotkey('ctrl','f')", "Writer"),
            GUIAction("search_user_wording", "pyautogui.write('wording under review')", "Writer"),
            GUIAction("select_user_wording", "pyautogui.press('enter'); pyautogui.press('esc')", "Writer"),
            GUIAction("replace_user_wording", "pyautogui.write('customer notified')", "Writer"),
            GUIAction("save_temporary_user_edit", "pyautogui.hotkey('ctrl','s')", "Writer"),
            GUIAction("undo_user_temporary_edit", "pyautogui.hotkey('ctrl','z')", "Writer"),
            GUIAction("save_writer", "pyautogui.hotkey('ctrl','s')", "Writer"),
        ]
    if case_id == "modal-export-v1":
        return _baseline_user_actions()
    raise ValueError(f"no scripted User actions for {case_id}")


def _case_agent_actions(case_id: str) -> list[GUIAction]:
    if case_id == "focus-route-v1":
        return _baseline_agent_actions()
    if case_id == "clipboard-handoff-v1":
        return [
            GUIAction("focus_writer", "pyautogui.click(24, 338)", "Writer"),
            GUIAction("writer_find_reference", "pyautogui.hotkey('ctrl','f')", "Writer"),
            GUIAction("type_reference_search", "pyautogui.write('PO-441')", "Writer"),
            GUIAction("execute_reference_search", "pyautogui.press('enter')", "Writer"),
            GUIAction("close_reference_search", "pyautogui.press('esc')", "Writer"),
            GUIAction("copy_po_reference", "pyautogui.hotkey('ctrl','c')", "Writer"),
            GUIAction("focus_calc", "pyautogui.click(24, 405)", "Calc"),
            GUIAction("receiving_calc_home", "pyautogui.hotkey('ctrl','home')", "Calc"),
            GUIAction("select_receiving_row", "pyautogui.press('down', presses=2, interval=0.08)", "Calc"),
            GUIAction("select_receiving_register_e3", "pyautogui.press('right', presses=4, interval=0.08)", "Calc"),
            GUIAction("paste_po_reference_e3_refocus_calc",
                      "pyautogui.click(24, 405); pyautogui.hotkey('ctrl','home'); "
                      "pyautogui.press('down', presses=2, interval=0.08); "
                      "pyautogui.press('right', presses=4, interval=0.08); "
                      "pyautogui.hotkey('ctrl','v'); pyautogui.press('enter')"),
            GUIAction("save_workbook_refocus",
                      "pyautogui.click(24, 405); pyautogui.hotkey('ctrl','s')"),
        ]
    if case_id == "calc-selection-drift-v1":
        return [
            GUIAction("focus_calc", "pyautogui.click(24, 405)", "Calc"),
            GUIAction("agent_calc_home", "pyautogui.hotkey('ctrl','home')", "Calc"),
            GUIAction("select_agent_quantity_column", "pyautogui.press('right', presses=2, interval=0.08)", "Calc"),
            GUIAction("select_agent_quantity_row", "pyautogui.press('down')", "Calc"),
            GUIAction("enter_agent_quantity_c2", "pyautogui.write('3')", "Calc"),
            GUIAction("commit_agent_quantity_c2", "pyautogui.press('enter')", "Calc"),
            GUIAction("select_agent_quantity_again", "pyautogui.press('up')", "Calc"),
            GUIAction("select_agent_note_e2", "pyautogui.press('right', presses=2, interval=0.08)", "Calc"),
            GUIAction("enter_agent_note_e2", "pyautogui.write('Approved PO-441')", "Calc"),
            GUIAction("commit_agent_note_e2", "pyautogui.press('enter')", "Calc"),
            GUIAction("save_workbook", "pyautogui.hotkey('ctrl','s')", "Calc"),
        ]
    if case_id == "writer-undo-stack-v1":
        return [
            # The fixture is one Writer document; use its verified initial focus.
            GUIAction("writer_document_end", "pyautogui.hotkey('ctrl','end')", "Writer"),
            GUIAction("begin_compliance_note", "pyautogui.press('enter')", "Writer"),
            GUIAction("type_compliance_note", "pyautogui.write('Compliance review: PO-441 verified.')", "Writer"),
            GUIAction("save_writer", "pyautogui.hotkey('ctrl','s')", "Writer"),
        ]
    if case_id == "modal-export-v1":
        return [
            GUIAction("focus_calc", "pyautogui.click(24, 405)", "Calc"),
            GUIAction("open_pdf_export_dialog", "pyautogui.hotkey('ctrl','shift','e')"),
            GUIAction("hold_export_dialog", "pyautogui.sleep(2.0)"),
            GUIAction("enter_pdf_basename", "pyautogui.hotkey('ctrl','a'); pyautogui.write('budget-export.pdf')"),
            GUIAction("confirm_pdf_filename", "pyautogui.press('enter')"),
            GUIAction("hold_pdf_options", "pyautogui.sleep(1.5)"),
            GUIAction("confirm_pdf_options", "pyautogui.press('enter')"),
        ]
    raise ValueError(f"no scripted Agent actions for {case_id}")


def _writer_undo_delivery_check(mode: str, action_events: list[dict[str,Any]]) -> dict[str,Any]:
    required={
        "user":{"find_user_wording","search_user_wording","select_user_wording",
                "replace_user_wording","save_temporary_user_edit","undo_user_temporary_edit","save_writer"},
        "agent":{"writer_document_end","begin_compliance_note","type_compliance_note","save_writer"},
    }
    actors=("user",) if mode=="user-only" else ("agent",) if mode=="agent-only" else ("user","agent")
    actor_audits={}
    for actor in actors:
        rows=[r for r in action_events if r.get("actor_id")==actor]
        by_name={}
        for row in rows:
            by_name.setdefault(row.get("action_name"),[]).append(row)
        missing=sorted(name for name in required[actor] if len(by_name.get(name,[]))!=1)
        wrong_window=[]
        action_errors=[]
        for name in sorted(required[actor]):
            for row in by_name.get(name,[]):
                before=(row.get("window_before") or "")
                if "Writer" not in before:
                    wrong_window.append({"action":name,"window_before":before or None})
                if row.get("error") or row.get("status")=="error":
                    action_errors.append({"action":name,"error":row.get("error")})
        actor_audits[actor]={"required_actions":sorted(required[actor]),"missing_or_duplicate_actions":missing,
                             "wrong_foreground_actions":wrong_window,"action_errors":action_errors,
                             "valid":not missing and not wrong_window and not action_errors}
    valid=all(x["valid"] for x in actor_audits.values())
    return {"valid":valid,"mode":mode,"actors":actor_audits,
            "rule":"Each required undo-case action must be recorded exactly once with LibreOffice Writer in the focused-window title and no GUI error."}


def _case_tasks(case_id: str) -> tuple[str,str]:
    if case_id == "focus-route-v1":
        return USER_TASK, AGENT_TASK
    if case_id == "clipboard-handoff-v1":
        return ("In the already-open Calc workbook, copy the total in D2 and append it to the Writer report's "
                "expense note as the exact final line: 'Invoice total: 79'. Preserve all existing report content and save.",
                "In Writer, find and copy the purchase-order reference PO-441. Paste it into the receiving-register cell E3 "
                "in the open Calc workbook. Preserve the other workbook values and save.")
    if case_id == "calc-selection-drift-v1":
        return SELECTION_USER_TASK, SELECTION_AGENT_TASK
    if case_id == "writer-undo-stack-v1":
        return ("In the Writer handoff, temporarily change 'wording under review' to 'customer notified'. "
                "After reconsidering, undo that temporary correction so the original wording remains; save.",
                "Add exactly 'Compliance review: PO-441 verified.' at the end of the open Writer handoff and save.")
    if case_id == "modal-export-v1":
        return (USER_TASK,
                "Export the open Calc budget workbook as a PDF named budget-export.pdf in Documents. "
                "Accept the standard PDF options and verify the exported file.")
    raise ValueError(f"no task text for {case_id}")


def _oracle(guest: Guest, files: dict[str,str], case_id: str="focus-route-v1") -> dict[str,Any]:
    report=_read(guest,files["report"])
    lines=report.lstrip("\ufeff").splitlines()
    nonblank=[line for line in lines if line.strip()]
    values=_read_workbook_cells(guest,files["workbook"])
    source_prefix=["Quarterly Service Report","Date: 2026-11-09","Status: DRAFT",
                   "Owner: Operations","Notes: Closeout pending."]
    base_report_preserved=lines[:len(source_prefix)]==source_prefix
    if case_id == "focus-route-v1":
        user_count=lines.count(USER_LINE)
        preserved={"A1":"Item","B1":"Unit price","C1":"Quantity","D1":"Total","E1":"Notes",
                   "A2":"Router","B2":"39.5","D2":"79"}
        unchanged={cell:values.get(cell)==expected for cell,expected in preserved.items()}
        return {"user":{"success":user_count==1 and bool(nonblank) and nonblank[-1]==USER_LINE and base_report_preserved,
                        "target_line_count":user_count,"last_nonempty_line":nonblank[-1] if nonblank else None,
                        "source_content_preserved":base_report_preserved,"report_text":report},
                "agent":{"success":values.get("C2") in {"3","3.0"} and values.get("E2")=="Approved PO-441"
                         and all(unchanged.values()),"quantity_cell":values.get("C2"),"notes_cell":values.get("E2"),
                         "preserved_cells":unchanged,"workbook_cells":values}}
    if case_id == "clipboard-handoff-v1":
        user_count=lines.count(CLIPBOARD_USER_LINE)
        user_success=(user_count==1 and bool(nonblank) and nonblank[-1]==CLIPBOARD_USER_LINE
                      and base_report_preserved and "Reference: PO-441" in lines)
        preserved={"A1":"Item","B1":"Unit price","C1":"Quantity","D1":"Total","E1":"Notes",
                   "A2":"Router","B2":"39.5","C2":"2","D2":"79","E2":"draft"}
        unchanged={cell:values.get(cell)==expected for cell,expected in preserved.items()}
        unexpected={cell:value for cell,value in values.items()
                    if cell not in preserved and cell!="E3" and value not in {"",None}}
        contaminated={cell:values.get(cell) for cell,expected in preserved.items()
                      if values.get(cell)!=expected}
        contaminated.update(unexpected)
        return {"user":{"success":user_success,"target_line_count":user_count,
                        "last_nonempty_line":nonblank[-1] if nonblank else None,
                        "source_content_preserved":base_report_preserved,"report_text":report,
                        "cross_artifact_workbook_cells":contaminated},
                "agent":{"success":values.get("E3")==CLIPBOARD_AGENT_VALUE and all(unchanged.values()) and not unexpected,
                         "paste_target":values.get("E3"),"preserved_cells":unchanged,
                         "unexpected_workbook_cells":unexpected,"workbook_cells":values}}
    if case_id == "calc-selection-drift-v1":
        user_success=values.get("B2") in {"42","42.0"}
        agent_success=(values.get("C2") in {"3","3.0"} and values.get("E2")=="Approved PO-441"
                       and values.get("A2")=="Router")
        return {"user":{"success":user_success,"target_cell":"B2","target_value":values.get("B2"),
                        "workbook_cells":values},
                "agent":{"success":agent_success,"quantity_cell":values.get("C2"),
                         "notes_cell":values.get("E2"),"item_label_preserved":values.get("A2")=="Router",
                         "workbook_cells":values}}
    if case_id == "writer-undo-stack-v1":
        return _writer_undo_report_oracle(report)
    if case_id == "modal-export-v1":
        user_count=lines.count(USER_LINE)
        user_success=user_count==1 and bool(nonblank) and nonblank[-1]==USER_LINE and base_report_preserved
        pdf_path=Path(files.get("pdf",str(Path(files["report"]).parent / "budget-export.pdf")))
        try:
            pdf_bytes=pdf_path.read_bytes()
            pdf_ok=pdf_bytes.startswith(b"%PDF") and len(pdf_bytes)>1000
            pdf_size=len(pdf_bytes)
        except OSError:
            pdf_ok,pdf_size=False,0
        return {"user":{"success":user_success,"target_line_count":user_count,
                        "last_nonempty_line":nonblank[-1] if nonblank else None,"report_text":report},
                "agent":{"success":pdf_ok,"pdf_path":str(pdf_path),"pdf_bytes":pdf_size,
                         "pdf_signature_ok":pdf_ok}}
    raise ValueError(f"no Oracle for {case_id}")


def _prepare(env: Any, guest: Guest, gid: str, out: Path, case_id: str="focus-route-v1") -> dict[str, str]:
    out.mkdir(parents=True, exist_ok=True)
    # Every condition boots a new OSWorld container + qcow2 overlay from the same immutable base.
    # Avoid DesktopEnv.reset on this clean first episode; its no-op task setup is expensive and
    # the actual snapshot reset path was separately verified with a Guest-side sentinel preflight.
    ready_started=time.monotonic()
    guest.wait_desktop(patience=300)
    (out / "guest-readiness.json").write_text(json.dumps({"ready_wait_s":round(time.monotonic()-ready_started,3),
        "screenshot_bytes":len(guest.screenshot(patience=60))},indent=2)+"\n",encoding="utf-8")
    home = _home(guest)
    files = _fixture(guest, home, case_id, out)
    out.mkdir(parents=True, exist_ok=True)
    (out / "setup.png").write_bytes(guest.screenshot(patience=60))
    files["home"] = str(home)
    files["initialization"] = "fresh base-image Guest/container and new overlay; no in-episode reset"
    return files


def _boot(image: str, gid: str, out: Path, case_id: str="focus-route-v1") -> tuple[Any, Guest, dict[str,str]]:
    from . import combo
    env = combo.boot(image, str(out / "cache"))
    guest = Guest(env)
    return env, guest, _prepare(env, guest, gid, out, case_id)


def _agent_harness(guest: Guest, out: Path, lock_path: Path | None, budget: int,
                   endpoint: str | None, model: str, timeout: float, case_id: str="focus-route-v1"):
    import shutil
    from .harness import AgentContext, make_harness
    binary = os.environ.get("CODEX_CLI_BIN") or shutil.which("codex")
    if not binary:
        raise RuntimeError("Codex CLI not found; set CODEX_CLI_BIN to pinned 0.155.0")
    user_task, agent_task = _case_tasks(case_id)
    expected_app = ("Calc" if case_id in {"focus-route-v1", "calc-selection-drift-v1", "modal-export-v1"}
                    else "Writer" if case_id == "writer-undo-stack-v1" else None)
    options = {"codex_bin": binary, "node_bin": os.environ.get("CODEX_NODE_BIN"),
               "base_url": endpoint, "api_key_env": "OPENAI_API_KEY", "wire_api": "responses",
               "timeout": timeout, "run_id": os.environ.get("OSCOMBO_RUN_ID"), "expected_app": expected_app,
               "codex_home_base": os.environ.get("CODEX_HOME_BASE", "/home/mjh/.cache/codesk-ha-poc-codex-home")}
    spec = {"harness":"codex", "model":model, "effort":"low", "base_url":endpoint, "options":options}
    ctx = AgentContext(name="agent", task_id=case_id, instruction=agent_task,
                       guest=guest, out=out, max_steps=budget, spec=spec,
                       action_lock_file=str(lock_path) if lock_path else None)
    harness=make_harness(spec)
    harness.prepare(ctx)
    return harness, ctx


def _run_parallel(named: list[tuple[str,Any]]) -> dict[str,Any]:
    barrier = threading.Barrier(len(named)) if len(named)>1 else None
    result, errors = {}, {}
    def call(name, fn):
        try:
            if barrier:
                barrier.wait()
            result[name]=fn()
        except Exception as e:
            errors[name]=f"{type(e).__name__}: {e}\n{traceback.format_exc()[-1600:]}"
    threads=[threading.Thread(target=call,args=x,name=x[0]) for x in named]
    for t in threads:t.start()
    for t in threads:t.join()
    return {"results":result,"errors":errors}


def _codex_run(harness: Any, ctx: Any) -> dict[str,Any]:
    ctx.t0=time.time()
    r=harness.run(ctx)
    return {"status":r.status,"error":r.error,"steps":r.steps,"extra":r.extra}


def _actor_rollup(out: Path, mode: str, results: dict, errors: dict, oracle: dict,
                  monitors: list[FocusMonitor]) -> dict[str,Any]:
    rows=[]
    event_file=out/"events.jsonl"
    if event_file.exists():
        for line in event_file.read_text(encoding="utf-8").splitlines():
            try: rows.append(json.loads(line))
            except json.JSONDecodeError: pass
    misroute={a:sum(1 for r in rows if r.get("actor_id")==a
                    and r.get("event_type") in {"gui_action", "agent_gui_action"}
                    and r.get("misrouted_focus_before")) for a in ("user","agent")}
    return {
        "mode":mode,"actor_results":results,"actor_errors":errors,"oracle":oracle,
        "misrouted_actions_by_focus":misroute,
        "actor_costs":{a:{
            "action_count":sum(1 for r in rows if r.get("actor_id")==a and r.get("event_type") in {"gui_action","agent_gui_action"}),
            "input_misroutes":misroute.get(a,0),
            "api_or_action_errors":sum(1 for r in rows if r.get("actor_id")==a and (r.get("error") or r.get("status")=="error")),
            "rework_actions":sum(1 for r in rows if r.get("actor_id")==a and (r.get("recovery") or str(r.get("action_name","")).startswith("recovery_"))),
            "elapsed_s":next((r.get("elapsed_s") for r in reversed(rows) if r.get("actor_id")==a and r.get("event_type")=="actor_finished"),None),
        } for a in ("user","agent")},
        "focus_transitions":sum(m.transitions for m in monitors),
        "focus_event_count":sum(1 for r in rows if r.get("event_type")=="focus_change"),
        "user_lock_wait_s":round(sum(float(r.get("lock_wait_s",0)) for r in rows
            if r.get("actor_id")=="user" and r.get("event_type")=="gui_action"),6),
        "agent_lock_wait_s":round(sum(float(r.get("lock_wait_s",0)) for r in rows
            if r.get("actor_id")=="agent" and r.get("event_type") in {"gui_action","agent_gui_action"}),6),
        "event_count":len(rows)
    }


def _run_probe(env: Any, guest: Guest, files: dict, out: Path, log: EventLog,
               lock: Path | None, recover: bool) -> dict[str,Any]:
    ready, resume = threading.Event(), threading.Event()
    user = ScriptedGUIActor(actor_id="user",guest=guest,actions=user_task_actions(natural_delays=False),
        event_log=log,out=out,guest_id="guest-shared",lock_path=lock,
        strategy="recoverable" if recover else "fixed",report_line=USER_LINE,
        pause_after={"navigate_report_end":(ready,resume)})
    probe_result={}
    def switch_focus():
        try:
            if not ready.wait(240): raise TimeoutError("User did not reach focus boundary")
            actor=ScriptedGUIActor(actor_id="probe-agent",guest=guest,
                actions=[GUIAction("probe_focus_calc","pyautogui.click(24, 405)","Calc")],
                event_log=log,out=out,guest_id="guest-shared",lock_path=lock)
            probe_result.update(actor.run())
        except Exception as e:
            probe_result["error"]=repr(e)
        finally:
            resume.set()
    monitor=FocusMonitor(guest,"guest-shared",log,out/"focus")
    monitor.start()
    thread=threading.Thread(target=switch_focus,name="forced-focus-probe"); thread.start()
    user_result=user.run()
    thread.join(240); monitor.stop()
    oracle=_oracle(guest,files)
    events=[json.loads(x) for x in log.path.read_text().splitlines()]
    recovery=[e.get("recovery_duration_s") for e in events if e.get("event_type")=="recovery_finished"]
    return {"probe_type":"forced mechanism interleaving, not natural incidence",
            "user_strategy":user.strategy,"user_result":user_result,"probe_agent":probe_result,
            "oracle":oracle,"focus_transitions":monitor.transitions,"recovery_duration_s":recovery}


def run_condition(*, mode: str, out: Path, agent: str="replay", user_strategy: str="fixed",
                  budget: int=10, timeout: float=600, model: str="gpt-6-sol",
                  endpoint: str|None=None, image: str|None=None,
                  case_id: str="focus-route-v1") -> dict[str,Any]:
    if mode not in MODES: raise ValueError(f"mode must be one of {MODES}")
    get_case(case_id)
    if mode == "forced-probe" and case_id != "focus-route-v1":
        raise ValueError("the legacy forced focus probe is only implemented for focus-route-v1")
    if user_strategy != "fixed" and case_id != "focus-route-v1":
        raise ValueError("recoverable User strategy is only implemented for focus-route-v1")
    out.mkdir(parents=True,exist_ok=True)
    rid=f"ha-poc-{mode}-{time.strftime('%Y%m%dT%H%M%S')}-{uuid.uuid4().hex[:8]}"
    started=time.monotonic()
    log=EventLog(out/"events.jsonl",rid,out,started)
    log.emit("orchestrator","run_started",mode=mode,case_id=case_id,agent_kind=agent,user_strategy=user_strategy)
    os.environ["SWCUB_RUN_ID"]=rid
    os.environ["OSCOMBO_RUN_ID"]=rid
    os.environ["OSCOMBO_RUN_START_MONO"]=str(started)
    os.environ["SWCUB_OWNER_TOKEN"]=secrets.token_hex(32)
    os.environ["SWCUB_RESOURCE_LEDGER"]=str(out/"resource-ledger.jsonl")
    os.environ.setdefault("SWCUB_OSWORLD_OVERLAY_HOST_DIR",str(out/"overlays"))
    os.environ.setdefault("SWCUB_OSWORLD_DOCKER_RUNTIME_IMAGE","swcub/osworld-v2.1-qemu-runtime:local")
    # Recent Guest-ready times were 9-10 min under unrelated host load; OSWorld's
    # 300 s default expired before any task actor ran. Preserve an override if set.
    os.environ.setdefault("SWCUB_OSWORLD_VM_READY_TIMEOUT","600")
    os.environ.setdefault("OSWORLD_DIR","/home/mjh/Projects/_deps/OSWorld-V2-osworld-v2.1")
    image=image or os.environ.get("OSCOMBO_GUEST_IMAGE","/mnt/raid1/mjh/Projects/_deps/osworld-v2.1/docker_vm_data/osworld-v2-ubuntu-x86.qcow2")
    if not Path(image).is_file(): raise FileNotFoundError(image)
    from . import osworld
    osworld.activate()
    guestspec=[("guest-user",out/"guests"/"guest-user")]
    needs_user=mode in {"user-only","independent","shared","shared-lock","forced-probe"}
    needs_agent=mode in {"agent-only","independent","shared","shared-lock"}
    if mode=="independent": guestspec=[("guest-user",out/"guests"/"guest-user"),("guest-agent",out/"guests"/"guest-agent")]
    envs, guests, files, errors={}, {}, {}, {}
    monitors=[]
    try:
        def boot_one(spec):
            gid,gout=spec
            envs[gid],guests[gid],files[gid]=_boot(image,gid,gout,case_id)
        if mode=="independent":
            th=[threading.Thread(target=boot_one,args=(s,),name="boot-"+s[0]) for s in guestspec]
            [t.start() for t in th]; [t.join() for t in th]
        else: boot_one(guestspec[0])
        if mode=="forced-probe":
            lock=Path(f"/tmp/{rid}.gui-action.lock") if agent=="locked-probe" else None
            p1=_run_probe(envs["guest-user"],guests["guest-user"],files["guest-user"],out/"probe-fixed",log,lock,False)
            envs["guest-user"].is_environment_used=True  # direct GUI API actions bypass DesktopEnv.step bookkeeping
            envs["guest-user"].reset(task_config={"id":"probe-reset","instruction":"reset","config":[],"evaluator":{},"proxy":False})
            guests["guest-user"].wait_desktop(patience=240)
            files["guest-user"]=_fixture(guests["guest-user"],_home(guests["guest-user"]),case_id)
            p2=_run_probe(envs["guest-user"],guests["guest-user"],files["guest-user"],out/"probe-recoverable",log,lock,True)
            result={"run_id":rid,"mode":mode,"fixed_probe":p1,"recoverable_probe":p2,
                    "natural_interference_claim":False,"elapsed_s":round(time.monotonic()-started,3)}
            (out/"run.json").write_text(json.dumps(result,indent=2,ensure_ascii=False)+"\n",encoding="utf-8")
            return result

        ug=guests.get("guest-user")
        aid="guest-agent" if mode=="independent" else "guest-user"
        ag=guests.get(aid)
        lock=Path(f"/tmp/{rid}.gui-action.lock") if mode=="shared-lock" else None
        if lock:
            os.environ["OSCOMBO_ACTION_LOCK_FILE"]=str(lock)
            os.environ["OSCOMBO_ACTION_LOCK_EVENTS_FILE"]=str(out/"locks"/"agent-action-lock-events.jsonl")
        else:
            os.environ.pop("OSCOMBO_ACTION_LOCK_FILE",None)
            os.environ.pop("OSCOMBO_ACTION_LOCK_EVENTS_FILE",None)
        unique=[("guest-user",ug)] if aid=="guest-user" else [("guest-user",ug),(aid,ag)]
        for gid,g in unique:
            m=FocusMonitor(g,gid,log,out/"focus"); monitors.append(m); m.start()
        functions=[]
        user_actor=None
        if needs_user:
            user_actions=_case_user_actions(case_id)
            if case_id != "focus-route-v1":
                user_actions=[GUIAction(a.name,a.code,a.expected_app,0.7) for a in user_actions]
            user_hook=None
            if case_id=="writer-undo-stack-v1":
                def user_hook(actor_id,action,row):
                    if action.name not in {"save_temporary_user_edit","save_writer"}:
                        return {"checkpoint":"not-requested"}
                    read_started=time.monotonic()
                    report_text=""
                    read_error=None
                    # Save may flush asynchronously; observe without sending more GUI input.
                    deadline=time.monotonic()+5
                    while time.monotonic()<deadline:
                        try:
                            report_text=_read(ug,files["guest-user"]["report"])
                            read_error=None
                            if ((action.name=="save_temporary_user_edit" and "Customer impact: customer notified" in report_text)
                                or (action.name=="save_writer" and "Customer impact: wording under review." in report_text)):
                                break
                        except Exception as exc:
                            read_error=f"{type(exc).__name__}: {exc}"
                        time.sleep(0.25)
                    audit_dir=out/"evaluator-checkpoints"/"writer-undo"
                    audit_dir.mkdir(parents=True,exist_ok=True)
                    label="temporary-edit" if action.name=="save_temporary_user_edit" else "post-undo-final"
                    (audit_dir/f"{label}.txt").write_text(report_text,encoding="utf-8")
                    obs={"checkpoint":label,"report_text":report_text,"read_error":read_error,
                         "elapsed_s":round(time.monotonic()-read_started,6),
                         "temporary_phrase_present":report_text.count("Customer impact: customer notified")==1,
                         "original_phrase_present":report_text.count("Customer impact: wording under review.")==1}
                    log.emit("evaluator","task_checkpoint",episode_id="user",guest_id="guest-user",
                             actor_action=action.name,**obs)
                    return obs
            user_actor=ScriptedGUIActor(actor_id="user",guest=ug,actions=user_actions,
                event_log=log,out=out,guest_id="guest-user",lock_path=lock,strategy=user_strategy,
                report_line=USER_LINE,post_action_hook=user_hook)
            functions.append(("user",user_actor.run))
        harness=ctx=None
        if needs_agent:
            if agent=="replay":
                agent_actions=_case_agent_actions(case_id)
                if case_id != "focus-route-v1":
                    agent_actions=[GUIAction(a.name,a.code,a.expected_app,0.9) for a in agent_actions]
                aa=ScriptedGUIActor(actor_id="agent",guest=ag,actions=agent_actions,
                    event_log=log,out=out,guest_id=aid,lock_path=lock)
                functions.append(("agent",aa.run))
            elif agent=="codex":
                harness,ctx=_agent_harness(ag,out,lock,budget,endpoint,model,timeout,case_id)
                def codex_actor():
                    actor_started=time.monotonic()
                    log.emit("agent","actor_started",guest_id=aid,actor_kind="codex_gui")
                    try:
                        result=_codex_run(harness,ctx)
                        log.emit("agent","actor_finished",guest_id=aid,actor_kind="codex_gui",
                                 elapsed_s=round(time.monotonic()-actor_started,6),status=result.get("status"),
                                 steps=result.get("steps"))
                        return result
                    except Exception as exc:
                        log.emit("agent","actor_finished",guest_id=aid,actor_kind="codex_gui",
                                 elapsed_s=round(time.monotonic()-actor_started,6),status="error",error=str(exc)[:500])
                        raise
                functions.append(("agent",codex_actor))
            else: raise ValueError("agent must be replay or codex")
        actor_runs=_run_parallel(functions)
        # GUI saves can take a short disk-flush interval on the CPU-only Guest.
        time.sleep(1.0)
        for m in monitors:m.stop()
        oracle={}
        if needs_user: oracle["user"]=_oracle(ug,files["guest-user"],case_id)["user"]
        if needs_agent: oracle["agent"]=_oracle(ag,files[aid],case_id)["agent"]
        result=_actor_rollup(out,mode,actor_runs["results"],actor_runs["errors"],oracle,monitors)
        if case_id == "writer-undo-stack-v1":
            action_events=[]
            for line in log.path.read_text(encoding="utf-8").splitlines():
                try:
                    event=json.loads(line)
                    if event.get("event_type")=="gui_action" and event.get("actor_id") in {"user","agent"}:
                        action_events.append(event)
                except json.JSONDecodeError:
                    pass
            delivery=_writer_undo_delivery_check(mode,action_events)
            checkpoints={}
            for line in log.path.read_text(encoding="utf-8").splitlines():
                try:
                    event=json.loads(line)
                    if event.get("event_type")=="task_checkpoint" and event.get("actor_id")=="evaluator":
                        checkpoints[event.get("checkpoint")]=event
                except json.JSONDecodeError:
                    pass
            user_sequence={"temporary_edit_saved":bool(checkpoints.get("temporary-edit",{}).get("temporary_phrase_present")),
                           "final_original_restored":bool(checkpoints.get("post-undo-final",{}).get("original_phrase_present")),
                           "checkpoint_events":sorted(checkpoints)}
            if "user" in oracle:
                oracle["user"]["temporary_edit_checkpoint"]=user_sequence["temporary_edit_saved"]
                oracle["user"]["post_undo_checkpoint"]=user_sequence["final_original_restored"]
                oracle["user"]["final_artifact_success"]=oracle["user"].get("success",False)
                oracle["user"]["success"]=(oracle["user"].get("success",False)
                    and user_sequence["temporary_edit_saved"] and user_sequence["final_original_restored"])
            mechanism_valid=delivery["valid"]
            result["mechanism_delivery_valid"]=mechanism_valid
            result["mechanism_delivery_audit"]=delivery
            result["user_sequence_audit"]=user_sequence
            result["experiment_valid"]=mechanism_valid
            if not mechanism_valid:
                result["status"]="invalid-gui-delivery"
                result["invalid_reason"]="Writer undo-stack outcome is not attributable: required edit/undo actions did not execute with Writer foreground."
            elif "user" in oracle and not oracle["user"].get("success"):
                result["status"]="valid-task-failure"
            else:
                result["status"]="finished"
        else:
            result["experiment_valid"]=True
        initial_equivalence=(files["guest-user"].get("initial_file_sha256")==files["guest-agent"].get("initial_file_sha256")
                             if mode=="independent" else None)
        user_task, agent_task = _case_tasks(case_id)
        result.update({"run_id":rid,"case_id":case_id,"agent_kind":agent,"user_strategy":user_strategy,"elapsed_s":round(time.monotonic()-started,3),
            "initial_fixture_equivalence":initial_equivalence,
            "budget_per_agent":budget if agent=="codex" else None,"guest_count":len(guests),
            "fixture_paths":files,"base_image":image,"base_image_bytes":Path(image).stat().st_size,
            "resource_ledger":str(out/"resource-ledger.jsonl"),"overlay_root":str(out/"overlays"),
            "user_task":user_task,"agent_task":agent_task,"shared_lock_scope":
            "one complete action/tool call plus screenshot; not a task/think-time lock" if lock else "none"})
        (out/"run.json").write_text(json.dumps(result,indent=2,ensure_ascii=False,default=str)+"\n",encoding="utf-8")
        log.emit("orchestrator","run_finished",status=result.get("status","finished"),elapsed_s=result["elapsed_s"],oracle=oracle)
        return result
    except Exception as exc:
        from .guest import InfraError
        status="infrastructure-invalid" if isinstance(exc,InfraError) else "orchestrator-error"
        failure={"run_id":rid,"case_id":case_id,"mode":mode,"agent_kind":agent,
                 "status":status,"task_result_valid":False,"elapsed_s":round(time.monotonic()-started,3),
                 "error":f"{type(exc).__name__}: {exc}","resource_ledger":str(out/"resource-ledger.jsonl"),
                 "overlay_root":str(out/"overlays"),"base_image":image}
        if not (out/"run.json").exists():
            (out/"run.json").write_text(json.dumps(failure,indent=2,ensure_ascii=False,default=str)+"\n",encoding="utf-8")
        log.emit("orchestrator","run_failed",status=status,elapsed_s=failure["elapsed_s"],error=failure["error"][:1000])
        raise
    finally:
        for m in monitors:m.stop()
        for env in envs.values():
            try: env.close()
            except Exception: pass
        # Some OSWorld close paths leave their container running after task/setup errors.
        # Stop only containers both created in this run ledger and carrying our exact labels.
        try:
            from swcub.resource_safety import ResourceIdentity, cleanup_docker_cli_container
            ledger=out/"resource-ledger.jsonl"
            token=os.environ.get("SWCUB_OWNER_TOKEN")
            if ledger.exists() and token:
                identity=ResourceIdentity(rid,token,ledger)
                rows=[json.loads(x) for x in ledger.read_text(encoding="utf-8").splitlines() if x.strip()]
                ids=sorted({r.get("resource_id") for r in rows if r.get("event")=="created"
                            and r.get("resource_type")=="container" and r.get("run_id")==rid})
                for cid in ids:
                    try:
                        cleanup_docker_cli_container(cid,identity,reason="Human-Agent PoC teardown")
                    except Exception as cleanup_error:
                        # A container already removed by env.close is benign; mismatched identities are not.
                        check=subprocess.run(["docker","inspect","--type","container",cid],capture_output=True,text=True)
                        if check.returncode==0:
                            raise cleanup_error
        except Exception as cleanup_error:
            log.emit("orchestrator","safe_teardown_warning",error=str(cleanup_error)[:500])
        os.environ.pop("OSCOMBO_ACTION_LOCK_FILE",None)
        os.environ.pop("OSCOMBO_ACTION_LOCK_EVENTS_FILE",None)
        os.environ.pop("OSCOMBO_RUN_ID",None)
        os.environ.pop("OSCOMBO_RUN_START_MONO",None)


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--mode",choices=MODES,required=True)
    p.add_argument("--case",choices=tuple(c.case_id for c in CASEBOOK),default="focus-route-v1")
    p.add_argument("--agent",choices=("replay","codex","locked-probe"),default="replay")
    p.add_argument("--user-strategy",choices=("fixed","recoverable"),default="fixed")
    p.add_argument("--out",type=Path,required=True)
    p.add_argument("--image")
    p.add_argument("--budget",type=int,default=10)
    p.add_argument("--timeout",type=float,default=600)
    p.add_argument("--model",default="gpt-6-sol")
    p.add_argument("--base-url",default=os.environ.get("OPENAI_BASE_URL"))
    a=p.parse_args()
    result=run_condition(mode=a.mode,out=a.out,agent=a.agent,user_strategy=a.user_strategy,
        budget=a.budget,timeout=a.timeout,model=a.model,endpoint=a.base_url,image=a.image,case_id=a.case)
    print(json.dumps(result,indent=2,ensure_ascii=False,default=str))


if __name__=="__main__": main()
