"""One run-owned real Guest probe for LibreOffice Open and dirty-window reset.

This is a diagnostic scripted smoke, never a model task score. It uses the
existing OSWorld provider and Lite public fixture; no evaluator data or key.
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import time
import traceback

from oscombo.collab.data_to_deck.provenance import RunLedger
from oscombo.collab.data_to_deck.live_pilot import (
    _boot_guest, _install_fixture, _launch, _missing_container,
    _verify_container, _shell,
)
from oscombo.collab.data_to_deck_lite_v1.fixtures import build_fixture


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-root", type=Path, required=True)
    args = parser.parse_args()
    root = args.run_root.resolve()
    root.mkdir(parents=True, exist_ok=False)
    run_id = root.name
    fixture_dir = root / "fixtures"
    build_fixture(fixture_dir)
    ledger = RunLedger(root, {"run_id": run_id, "kind": "lite_gui_open_and_reset_smoke",
                              "case_id": "CDD-LITE-001", "model_called": False})
    (root / "ownership.json").write_text(json.dumps({"project": "CoDesk Data-to-Deck",
        "run_id": run_id, "owner": os.environ.get("USER"), "resources": [],
        "cleanup": "only full-ID + exact oscombo.run label resources"}, indent=2) + "\n")
    provider = Path(os.environ["OSWORLD_DIR"]).resolve()
    image = str(Path(os.environ["OSCOMBO_GUEST_IMAGE"]).resolve())
    runtime = os.environ["OSCOMBO_RUNTIME_IMAGE"]
    env = None
    cid = None
    result: dict = {"run_id": run_id, "model_called": False, "steps": []}
    try:
        env, guest, cid = _boot_guest(root, run_id, "B", image, provider, runtime, ledger)
        task_root = "/tmp/codesk-data-to-deck-lite-v1"
        _install_fixture(guest, fixture_dir, task_root)
        source = task_root + "/outputs/agent_A/verified_analysis.ods"
        draft = task_root + "/outputs/agent_B/final_management_brief.odp"
        _launch(guest, "impress", draft, f"/tmp/{run_id}/impress.log")
        guest.actor = "system"

        def act(label: str, code: str, delay: float = 0) -> str:
            guest.run_pyautogui(code)
            if delay:
                time.sleep(delay)
            title = guest.active_window() or ""
            result["steps"].append({"label": label, "active_window": title})
            return title

        act("open_dialog", "import pyautogui, time; pyautogui.hotkey('ctrl','o'); time.sleep(5)")
        act("location_entry", "import pyautogui, time; pyautogui.hotkey('ctrl','l'); time.sleep(1)")
        act("type_full_path", f"import pyautogui, time; pyautogui.write({source!r}, interval=0.02); time.sleep(1)")
        title = act("return_once", "import pyautogui, time; pyautogui.press('enter'); time.sleep(6)")
        if "verified_analysis.ods" not in title:
            title = act("return_twice", "import pyautogui, time; pyautogui.press('enter'); time.sleep(6)")
        if "verified_analysis.ods" not in title:
            title = act("alt_o", "import pyautogui, time; pyautogui.hotkey('alt','o'); time.sleep(6)")
        result["opened_analysis_in_gui"] = "verified_analysis.ods" in title
        result["source_bytes_in_guest"] = len(env.controller.get_file(source) or b"")

        if result["opened_analysis_in_gui"]:
            act("dirty_document", "import pyautogui, time; pyautogui.hotkey('ctrl','home'); "
                "pyautogui.write('temporary_unsaved_probe'); time.sleep(1)")
            act("close_dirty_document", "import pyautogui, time; pyautogui.hotkey('ctrl','w'); time.sleep(2)")
        result["pre_reset_active_window"] = guest.active_window()
        env.is_environment_used = True
        reset_started = time.monotonic()
        env.reset()
        result["reset_elapsed_s"] = round(time.monotonic() - reset_started, 2)
        new_container = _verify_container(env.provider.container.id, run_id)
        result["reset_new_owned_container"] = new_container.id != cid and _missing_container(cid)
        result["reset_clean_workspace"] = _shell(guest, f"test ! -e {task_root}", timeout=30)["status"] == "success"
        if not result["reset_new_owned_container"] or not result["reset_clean_workspace"]:
            raise RuntimeError("Guest reset did not replace the run-owned VM with a clean workspace")
        result["status"] = "PASS" if result["opened_analysis_in_gui"] else "OPEN_FAILED_RESET_PASS"
    except Exception as exc:
        result["status"] = "ERROR"
        result["error"] = f"{type(exc).__name__}: {exc}"
        result["traceback"] = traceback.format_exc()
    finally:
        if env is not None:
            active_cid = getattr(getattr(env.provider, "container", None), "id", None)
            if active_cid:
                _verify_container(active_cid, run_id)
            env.close()
            result["exact_owned_container_removed"] = not active_cid or _missing_container(active_cid)
        (root / "repair_gui_smoke_result.json").write_text(json.dumps(result, indent=2) + "\n")
        print(json.dumps({k: v for k, v in result.items() if k != "traceback"}, indent=2))


if __name__ == "__main__":
    main()
