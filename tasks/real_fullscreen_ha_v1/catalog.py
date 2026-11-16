"""5 Full-Screen User + Background All-Tools Agent Preemption Cases (Real Websites + Real Software)."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from tasks.human_agent_v1.actors import GUIAction
from tasks.real_macos_ha_v1.odf_utils import create_seed_ods, create_seed_odt, extract_odf_text


@dataclass(frozen=True)
class RealFullscreenCaseSpec:
    key: str
    title: str
    category: str  # "background_deliverable" | "desktop_open_deliverable"
    prototype_ref: str
    user_url: str
    user_doc_rel: str
    user_app_kind: str  # "writer" | "calc"
    agent_target_urls: tuple[str, ...]
    agent_doc_rel: str
    agent_app_kind: str  # "calc" | "writer" | "inkscape"
    require_agent_window_keyword: str | None
    user_task: str
    agent_task: str
    agent_budget: int = 35
    agent_timeout_s: int = 720


REAL_FULLSCREEN_5_CATALOG: tuple[RealFullscreenCaseSpec, ...] = (
    RealFullscreenCaseSpec(
        key="fs-arxiv-github-calc",
        title="Full-Screen arXiv Transformer PDF Reading vs Background GitHub Repo Audit (.ods)",
        category="background_deliverable",
        prototype_ref="code-review / ha-triage",
        user_url="https://arxiv.org/pdf/1706.03762",
        user_doc_rel="user_docs/transformer_notes.odt",
        user_app_kind="writer",
        agent_target_urls=("https://github.com/Ottohere-Mourn/CoDesk/tree/codex/human-agent-normal-user-v1-20261109",),
        agent_doc_rel="agent_work/codesk_repo_audit.ods",
        agent_app_kind="calc",
        require_agent_window_keyword=None,
        user_task=(
            "Read the full-screen live arXiv PDF 'Attention Is All You Need' (1706.03762) in Chromium, "
            "Alt+Tab to your full-screen LibreOffice Writer document (transformer_notes.odt) to jot down two reading notes, and save."
        ),
        agent_task=(
            "Inspect the live GitHub repository "
            "https://github.com/Ottohere-Mourn/CoDesk/tree/codex/human-agent-normal-user-v1-20261109 "
            "(README.md and pyproject.toml), and populate the LibreOffice Calc spreadsheet "
            "'/workspace/agent_work/codesk_repo_audit.ods' with the verified repository name ('Ottohere-Mourn/CoDesk'), "
            "Python package name ('oscombo'), minimum Python version ('>=3.10'), and supported run modes "
            "('solo', 'sequential', 'parallel'). Save '/workspace/agent_work/codesk_repo_audit.ods' as a valid Calc .ods file."
        ),
    ),
    RealFullscreenCaseSpec(
        key="fs-pydocs-pypi-calc",
        title="Full-Screen Python sqlite3 Docs Reading vs Background JS-Protected PyPI License Ledger (.ods)",
        category="background_deliverable",
        prototype_ref="ha-inventory",
        user_url="https://docs.python.org/3/library/sqlite3.html",
        user_doc_rel="user_docs/sqlite3_memo.odt",
        user_app_kind="writer",
        agent_target_urls=("https://pypi.org/project/requests/", "https://pypi.org/project/pillow/"),
        agent_doc_rel="agent_work/pypi_dependency_ledger.ods",
        agent_app_kind="calc",
        require_agent_window_keyword=None,
        user_task=(
            "Read the full-screen live Python 3 sqlite3 documentation in Chromium, "
            "Alt+Tab to your full-screen LibreOffice Writer memo (sqlite3_memo.odt) to record two SQL-safety notes, and save."
        ),
        agent_task=(
            "Check the live PyPI package pages 'https://pypi.org/project/requests/' and "
            "'https://pypi.org/project/pillow/', verify each package's exact open-source license "
            "('Apache-2.0' for requests, 'MIT-CMU' or 'HPND' for pillow), and save an approved dependency ledger "
            "to '/workspace/agent_work/pypi_dependency_ledger.ods' (valid LibreOffice Calc .ods)."
        ),
    ),
    RealFullscreenCaseSpec(
        key="fs-arxiv-inkscape-poster",
        title="Full-Screen arXiv ResNet PDF Reading vs Background GitHub + Inkscape Release Poster (.svg/.png)",
        category="background_deliverable",
        prototype_ref="facility-wo / multi-app",
        user_url="https://arxiv.org/pdf/1512.03385",
        user_doc_rel="user_docs/resnet_notes.odt",
        user_app_kind="writer",
        agent_target_urls=("https://github.com/Ottohere-Mourn/CoDesk/tree/codex/human-agent-normal-user-v1-20261109",),
        agent_doc_rel="agent_work/codesk_release_poster.svg",
        agent_app_kind="inkscape",
        require_agent_window_keyword=None,
        user_task=(
            "Read the full-screen live arXiv PDF 'Deep Residual Learning for Image Recognition' (1512.03385) in Chromium, "
            "Alt+Tab to your full-screen LibreOffice Writer notes (resnet_notes.odt) to record two notes, and save."
        ),
        agent_task=(
            "Inspect the live GitHub repository "
            "'https://github.com/Ottohere-Mourn/CoDesk/tree/codex/human-agent-normal-user-v1-20261109', "
            "update the SVG template '/workspace/agent_work/codesk_release_poster.svg' so its visible text includes "
            "'CoDesk', 'oscombo', and 'Shared Desktop Benchmark', and export an 800x450 PNG poster using Inkscape "
            "to '/workspace/agent_work/codesk_release_poster.png'."
        ),
    ),
    RealFullscreenCaseSpec(
        key="fs-paper-hf-browser-tab",
        title="Full-Screen arXiv GPT-3 PDF Reading vs Hugging Face License Sheet + Open Model Card in Browser",
        category="desktop_open_deliverable",
        prototype_ref="media-library",
        user_url="https://arxiv.org/pdf/2005.14165",
        user_doc_rel="user_docs/gpt3_reading_notes.odt",
        user_app_kind="writer",
        agent_target_urls=(
            "https://huggingface.co/openai-community/gpt2",
            "https://huggingface.co/google-bert/bert-base-uncased",
        ),
        agent_doc_rel="agent_work/hf_license_audit.ods",
        agent_app_kind="calc",
        require_agent_window_keyword="gpt2",
        user_task=(
            "Read the full-screen live arXiv PDF 'Language Models are Few-Shot Learners' (2005.14165) in Chromium, "
            "Alt+Tab to your full-screen LibreOffice Writer notes (gpt3_reading_notes.odt) to write two notes, and save."
        ),
        agent_task=(
            "Check the live Hugging Face model cards 'https://huggingface.co/openai-community/gpt2' and "
            "'https://huggingface.co/google-bert/bert-base-uncased', save both model IDs, their verified open-source licenses "
            "('mit' and 'apache-2.0'), and 'commercial_allowed=yes' into '/workspace/agent_work/hf_license_audit.ods' "
            "(valid LibreOffice Calc .ods), and leave 'https://huggingface.co/openai-community/gpt2' open in Chromium on the desktop so it is ready to read next."
        ),
    ),
    RealFullscreenCaseSpec(
        key="fs-wiki-pep-writer-open",
        title="Full-Screen Wikipedia Reading + Calc Schedule vs Python PEP Brief Opened in LibreOffice Writer",
        category="desktop_open_deliverable",
        prototype_ref="ha-calendar / edu-grade",
        user_url="https://en.wikipedia.org/wiki/Transformer_(deep_learning_architecture)",
        user_doc_rel="user_docs/study_calendar.ods",
        user_app_kind="calc",
        agent_target_urls=("https://peps.python.org/pep-0020/", "https://peps.python.org/pep-0008/"),
        agent_doc_rel="agent_work/pep_standards_brief.odt",
        agent_app_kind="writer",
        require_agent_window_keyword="pep_standards_brief",
        user_task=(
            "Read the full-screen live Wikipedia article on Transformer architecture in Chromium, "
            "Alt+Tab to your full-screen LibreOffice Calc sheet (study_calendar.ods) to enter Friday's seminar slot, and save."
        ),
        agent_task=(
            "Read the live Python Enhancement Proposals 'https://peps.python.org/pep-0020/' and "
            "'https://peps.python.org/pep-0008/', write a concise engineering standards brief to "
            "'/workspace/agent_work/pep_standards_brief.odt' (valid LibreOffice Writer .odt mentioning 'PEP 20', "
            "author 'Tim Peters', 'PEP 8', and max code line length '79'), and leave 'pep_standards_brief.odt' open "
            "in LibreOffice Writer on the desktop."
        ),
    ),
)

FULLSCREEN_CASE_BY_KEY: dict[str, RealFullscreenCaseSpec] = {c.key: c for c in REAL_FULLSCREEN_5_CATALOG}


def build_fullscreen_workspace(spec: RealFullscreenCaseSpec, workspace: Path) -> None:
    user_dir = workspace / "user_docs"
    agent_dir = workspace / "agent_work"
    user_dir.mkdir(parents=True, exist_ok=True)
    agent_dir.mkdir(parents=True, exist_ok=True)

    u_doc = workspace / spec.user_doc_rel
    if spec.user_app_kind == "writer":
        create_seed_odt(u_doc, f"Reading Notes — {spec.key}")
    else:
        create_seed_ods(u_doc, "Slot,Date,TimeWindow,Topic")

    a_doc = workspace / spec.agent_doc_rel
    if spec.agent_app_kind == "calc":
        create_seed_ods(a_doc, "Item,Field1,Field2,Status")
    elif spec.agent_app_kind == "writer":
        create_seed_odt(a_doc, f"Engineering Standards Brief — {spec.key}")
    elif spec.agent_app_kind == "inkscape":
        svg = """<?xml version="1.0" encoding="UTF-8"?>
<svg xmlns="http://www.w3.org/2000/svg" width="800" height="450" viewBox="0 0 800 450">
  <rect width="800" height="450" fill="#101a2e"/>
  <rect x="28" y="28" width="744" height="394" rx="14" fill="#182744" stroke="#3b82f6" stroke-width="3"/>
  <text x="64" y="130" fill="#f8fafc" font-family="DejaVu Sans" font-size="36" font-weight="bold">DRAFT RELEASE CARD</text>
  <text x="64" y="205" fill="#93c5fd" font-family="DejaVu Sans" font-size="22">Replace with verified repository name &amp; package</text>
</svg>
"""
        a_doc.write_text(svg, encoding="utf-8")


def get_fullscreen_user_actions(spec: RealFullscreenCaseSpec) -> list[GUIAction]:
    """Realistic ~55-65s human trajectory using 100% full-screen windows (toggling between Paper & Notes via Alt+Tab)."""
    if spec.key == "fs-arxiv-github-calc":
        n1 = "Note 1: Transformer uses N=6 encoder-decoder layers with d_model=512."
        n2 = "Note 2: Multi-head attention runs h=8 heads scaled by sqrt(d_k)."
    elif spec.key == "fs-paper-hf-browser-tab":
        n1 = "Note 1: GPT-3 scales autoregressive transformer to 175B parameters."
        n2 = "Note 2: Few-shot in-context learning uses demonstrations without gradient updates."
    elif spec.key == "fs-pydocs-pypi-calc":
        n1 = "Note 1: Use ? placeholders in cur.execute to prevent SQL injection."
        n2 = "Note 2: Call con.commit() to persist transaction changes to disk."
    elif spec.key == "fs-arxiv-inkscape-poster":
        n1 = "Note 1: Residual blocks learn F(x) = H(x) - x with identity shortcut x."
        n2 = "Note 2: 152-layer ResNet achieves lower complexity than VGG nets."
    elif spec.key == "fs-wiki-pep-writer-open":
        return [
            GUIAction("focus_fullscreen_wiki", "pyautogui.click(960, 540)", "Chromium", 2.0),
            GUIAction("scroll_wiki_overview", "pyautogui.moveTo(960, 540); pyautogui.scroll(-5)", "Chromium", 7.5),
            GUIAction("scroll_wiki_architecture", "pyautogui.moveTo(960, 540); pyautogui.scroll(-6)", "Chromium", 8.5),
            GUIAction(
                "alttab_to_fullscreen_calc_b2",
                "pyautogui.hotkey('alt','tab'); time.sleep(0.5); pyautogui.click(420, 360); time.sleep(0.25); "
                "pyautogui.hotkey('ctrl','home'); pyautogui.press('down'); pyautogui.press('right')",
                "Chromium",
                5.5,
            ),
            GUIAction(
                "enter_study_date",
                "pyautogui.write('2026-11-20', interval=0.05); pyautogui.press('tab')",
                "LibreOffice Calc",
                5.0,
            ),
            GUIAction(
                "alttab_back_to_fullscreen_wiki",
                "pyautogui.hotkey('alt','tab'); time.sleep(0.5); pyautogui.click(960, 540); pyautogui.scroll(-5)",
                "LibreOffice Calc",
                7.5,
            ),
            GUIAction(
                "alttab_back_to_fullscreen_calc_c2",
                "pyautogui.hotkey('alt','tab'); time.sleep(0.5); pyautogui.click(420, 360); time.sleep(0.25); "
                "pyautogui.hotkey('ctrl','home'); pyautogui.press('down'); pyautogui.press('right', presses=2, interval=0.08)",
                "Chromium",
                5.5,
            ),
            GUIAction(
                "enter_time_and_topic",
                "pyautogui.write('14:00-15:30', interval=0.05); pyautogui.press('tab'); "
                "pyautogui.write('Self-Attention Seminar', interval=0.04); pyautogui.press('enter')",
                "LibreOffice Calc",
                5.5,
            ),
            GUIAction("save_study_calendar", "pyautogui.hotkey('ctrl','s'); time.sleep(1.3)", "LibreOffice Calc", 4.0),
        ]
    else:
        raise ValueError(spec.key)

    return [
        GUIAction("focus_fullscreen_paper", "pyautogui.click(960, 540)", "Chromium", 2.0),
        GUIAction("scroll_paper_section1", "pyautogui.moveTo(960, 540); pyautogui.scroll(-5)", "Chromium", 7.5),
        GUIAction("scroll_paper_section2", "pyautogui.moveTo(960, 540); pyautogui.scroll(-6)", "Chromium", 8.5),
        GUIAction(
            "alttab_to_fullscreen_writer_note1",
            f"pyautogui.hotkey('alt','tab'); time.sleep(0.5); pyautogui.click(960, 480); time.sleep(0.25); "
            f"pyautogui.hotkey('ctrl','end'); pyautogui.press('enter'); pyautogui.write({n1!r}, interval=0.03)",
            "Chromium",
            5.5,
        ),
        GUIAction(
            "alttab_back_to_fullscreen_paper",
            "pyautogui.hotkey('alt','tab'); time.sleep(0.5); pyautogui.click(960, 540); pyautogui.scroll(-6)",
            "LibreOffice Writer",
            7.5,
        ),
        GUIAction("scroll_paper_experiments", "pyautogui.moveTo(960, 540); pyautogui.scroll(-6)", "Chromium", 8.0),
        GUIAction(
            "alttab_to_fullscreen_writer_note2",
            f"pyautogui.hotkey('alt','tab'); time.sleep(0.5); pyautogui.click(960, 520); time.sleep(0.25); "
            f"pyautogui.hotkey('ctrl','end'); pyautogui.press('enter'); pyautogui.write({n2!r}, interval=0.03)",
            "Chromium",
            5.5,
        ),
        GUIAction("save_reading_notes", "pyautogui.hotkey('ctrl','s'); time.sleep(1.4)", "LibreOffice Writer", 4.0),
    ]


def evaluate_fullscreen_workspace(
    spec: RealFullscreenCaseSpec,
    workspace: Path,
    final_windows_text: str = "",
    final_ps_text: str = "",
) -> dict[str, Any]:
    u_path = workspace / spec.user_doc_rel
    u_text = extract_odf_text(u_path)
    u_low = u_text.lower()

    if spec.key == "fs-arxiv-github-calc":
        u_checks = {
            "odt_exists": u_path.is_file(),
            "note1_layers_and_dmodel": ("n=6" in u_low and "512" in u_low),
            "note2_heads_and_sqrtdk": ("h=8" in u_low and "sqrt(d_k)" in u_low),
        }
    elif spec.key == "fs-paper-hf-browser-tab":
        u_checks = {
            "odt_exists": u_path.is_file(),
            "note1_175b": ("175b" in u_low and "gpt-3" in u_low),
            "note2_fewshot_no_grad": ("few-shot" in u_low and "gradient" in u_low),
        }
    elif spec.key == "fs-wiki-pep-writer-open":
        u_checks = {
            "ods_exists": u_path.is_file(),
            "date_recorded": "2026-11-20" in u_text,
            "time_recorded": "14:00-15:30" in u_text,
            "topic_recorded": "self-attention seminar" in u_low,
        }
    elif spec.key == "fs-pydocs-pypi-calc":
        u_checks = {
            "odt_exists": u_path.is_file(),
            "note1_placeholders": ("cur.execute" in u_low and "injection" in u_low),
            "note2_commit": "con.commit()" in u_low,
        }
    elif spec.key == "fs-arxiv-inkscape-poster":
        u_checks = {
            "odt_exists": u_path.is_file(),
            "note1_residual_fx": ("f(x)" in u_low and "shortcut" in u_low),
            "note2_152_layer": ("152-layer" in u_low and "vgg" in u_low),
        }
    else:
        raise ValueError(spec.key)

    a_path = workspace / spec.agent_doc_rel
    win_ps_low = (final_windows_text + "\n" + final_ps_text).lower()

    if spec.key == "fs-arxiv-github-calc":
        a_txt = extract_odf_text(a_path).lower()
        a_checks = {
            "ods_exists": a_path.is_file(),
            "package_oscombo": "oscombo" in a_txt,
            "python_310": "3.10" in a_txt,
            "modes_recorded": ("parallel" in a_txt and "sequential" in a_txt),
        }
    elif spec.key == "fs-paper-hf-browser-tab":
        a_txt = extract_odf_text(a_path).lower()
        win_ok = ("gpt2" in final_windows_text.lower() or "hugging face" in final_windows_text.lower() or "gpt2" in win_ps_low)
        a_checks = {
            "ods_exists": a_path.is_file(),
            "gpt2_mit": ("gpt2" in a_txt and "mit" in a_txt),
            "bert_apache2": ("bert" in a_txt and "apache" in a_txt),
            "browser_opened_gpt2": win_ok,
        }
    elif spec.key == "fs-wiki-pep-writer-open":
        a_txt = extract_odf_text(a_path).lower()
        win_ok = "pep_standards_brief" in final_windows_text.lower()
        a_checks = {
            "odt_exists": a_path.is_file(),
            "pep20_tim_peters": ("tim peters" in a_txt and "20" in a_txt),
            "pep8_line_79": ("79" in a_txt and "8" in a_txt),
            "writer_window_opened": win_ok,
        }
    elif spec.key == "fs-pydocs-pypi-calc":
        a_txt = extract_odf_text(a_path).lower()
        a_checks = {
            "ods_exists": a_path.is_file(),
            "requests_apache": ("requests" in a_txt and "apache" in a_txt),
            "pillow_license": ("pillow" in a_txt and any(k in a_txt for k in ("mit", "hpnd", "cmu"))),
        }
    elif spec.key == "fs-arxiv-inkscape-poster":
        from PIL import Image, ImageStat
        svg_txt = a_path.read_text(encoding="utf-8", errors="replace").lower() if a_path.is_file() else ""
        png_path = workspace / "agent_work/codesk_release_poster.png"
        png_ok = False
        if png_path.is_file():
            try:
                im = Image.open(png_path).convert("RGB")
                png_ok = im.size == (800, 450) and max(ImageStat.Stat(im).stddev) > 8.0
            except Exception:
                png_ok = False
        a_checks = {
            "svg_updated": ("codesk" in svg_txt and "oscombo" in svg_txt),
            "png_800x450_nonblank": png_ok,
        }
    else:
        raise ValueError(spec.key)

    return {
        "user": {"success": all(u_checks.values()), "checks": u_checks, "extracted_text_preview": u_text[:300]},
        "agent": {"success": all(a_checks.values()), "checks": a_checks},
    }
