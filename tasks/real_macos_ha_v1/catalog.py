"""5 Real-Webpage + Real-Software Human-Agent cases on a 2-Space macOS-style desktop."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from tasks.human_agent_v1.actors import GUIAction
from .odf_utils import create_seed_ods, create_seed_odt, extract_odf_text


@dataclass(frozen=True)
class RealMacOSCaseSpec:
    key: str
    title: str
    prototype_ref: str
    user_url: str
    user_doc_rel: str
    user_app_kind: str  # "writer" | "calc"
    agent_url: str
    agent_doc_rel: str
    agent_app_kind: str  # "calc" | "writer" | "inkscape"
    user_task: str
    agent_task: str
    agent_budget: int = 35
    agent_timeout_s: int = 720


REAL_MACOS_5_CATALOG: tuple[RealMacOSCaseSpec, ...] = (
    RealMacOSCaseSpec(
        key="rw-arxiv-code-review",
        title="Reading arXiv Transformer PDF + Writer Notes vs Live GitHub Repo Audit in Calc",
        prototype_ref="code-review / ha-triage",
        user_url="https://arxiv.org/pdf/1706.03762",
        user_doc_rel="user_docs/transformer_notes.odt",
        user_app_kind="writer",
        agent_url="https://github.com/Ottohere-Mourn/CoDesk/tree/codex/human-agent-normal-user-v1-20261109",
        agent_doc_rel="agent_work/codesk_repo_audit.ods",
        agent_app_kind="calc",
        user_task=(
            "On Space 1, read the live arXiv PDF 'Attention Is All You Need' (1706.03762) on the left "
            "and type two structured reading notes into LibreOffice Writer (transformer_notes.odt) on the right, then save."
        ),
        agent_task=(
            "Switch to Space 2 ('Space 2: Agent Desk'), inspect the open live GitHub repository "
            "https://github.com/Ottohere-Mourn/CoDesk/tree/codex/human-agent-normal-user-v1-20261109 (check README and pyproject.toml), and update the LibreOffice Calc "
            "spreadsheet '/workspace/agent_work/codesk_repo_audit.ods' with verified repository metadata: "
            "repo name 'Ottohere-Mourn/CoDesk', Python package name ('oscombo'), minimum Python version ('>=3.10'), "
            "and supported run modes ('solo', 'sequential', 'parallel'). Save '/workspace/agent_work/codesk_repo_audit.ods' "
            "as a valid Calc .ods file and verify Space 2 visually on screen. Do not modify '/workspace/user_docs'."
        ),
    ),
    RealMacOSCaseSpec(
        key="rw-paper-hf-license",
        title="Reading arXiv GPT-3 PDF + Writer Notes vs Live Hugging Face Model License Screening in Calc",
        prototype_ref="media-library",
        user_url="https://arxiv.org/pdf/2005.14165",
        user_doc_rel="user_docs/gpt3_reading_notes.odt",
        user_app_kind="writer",
        agent_url="https://huggingface.co/openai-community/gpt2",
        agent_doc_rel="agent_work/hf_license_audit.ods",
        agent_app_kind="calc",
        user_task=(
            "On Space 1, read the live arXiv PDF 'Language Models are Few-Shot Learners' (2005.14165) on the left "
            "and record two summary notes in LibreOffice Writer (gpt3_reading_notes.odt) on the right, then save."
        ),
        agent_task=(
            "Switch to Space 2 ('Space 2: Agent Desk'), use the open Chromium browser on Space 2 to inspect the live "
            "Hugging Face model cards 'https://huggingface.co/openai-community/gpt2' and "
            "'https://huggingface.co/google-bert/bert-base-uncased'. Verify each model's exact open-source license tag "
            "('mit' and 'apache-2.0') and record both model IDs, their verified licenses, and 'commercial_allowed=yes' "
            "into '/workspace/agent_work/hf_license_audit.ods' (valid LibreOffice Calc .ods). Verify Space 2 visually "
            "on screen and do not modify '/workspace/user_docs'."
        ),
    ),
    RealMacOSCaseSpec(
        key="rw-wiki-study-calendar",
        title="Reading Live Wikipedia Transformer Article + Calc Schedule vs Live Python PEP Standards Brief in Writer",
        prototype_ref="ha-calendar / edu-grade",
        user_url="https://en.wikipedia.org/wiki/Transformer_(deep_learning_architecture)",
        user_doc_rel="user_docs/study_calendar.ods",
        user_app_kind="calc",
        agent_url="https://peps.python.org/pep-0020/",
        agent_doc_rel="agent_work/pep_standards_brief.odt",
        agent_app_kind="writer",
        user_task=(
            "On Space 1, read the live Wikipedia article on Transformer architecture on the left and enter Friday's "
            "reading block (2026-11-20, 14:00-15:30, Self-Attention Seminar) into LibreOffice Calc (study_calendar.ods) on the right, then save."
        ),
        agent_task=(
            "Switch to Space 2 ('Space 2: Agent Desk'), inspect the live Python Enhancement Proposals "
            "'https://peps.python.org/pep-0020/' and 'https://peps.python.org/pep-0008/' in Chromium on Space 2. "
            "Verify the author of PEP 20 ('Tim Peters') and PEP 8's maximum code line length ('79' characters), and save "
            "a concise engineering brief into '/workspace/agent_work/pep_standards_brief.odt' (valid LibreOffice Writer .odt "
            "mentioning 'PEP 20', 'Tim Peters', 'PEP 8', and '79'). Verify Space 2 on screen and do not modify '/workspace/user_docs'."
        ),
    ),
    RealMacOSCaseSpec(
        key="rw-pydocs-pypi-inventory",
        title="Reading Live Python sqlite3 Docs + Writer Memo vs Live PyPI Package Ledger in Calc",
        prototype_ref="ha-inventory",
        user_url="https://docs.python.org/3/library/sqlite3.html",
        user_doc_rel="user_docs/sqlite3_memo.odt",
        user_app_kind="writer",
        agent_url="https://pypi.org/project/requests/",
        agent_doc_rel="agent_work/pypi_dependency_ledger.ods",
        agent_app_kind="calc",
        user_task=(
            "On Space 1, read the live Python 3 official sqlite3 documentation on the left and type two safe-query "
            "notes into LibreOffice Writer (sqlite3_memo.odt) on the right, then save."
        ),
        agent_task=(
            "Switch to Space 2 ('Space 2: Agent Desk'), inspect the live PyPI package pages "
            "'https://pypi.org/project/requests/' and 'https://pypi.org/project/pillow/' in Chromium on Space 2. "
            "Record both package names ('requests', 'pillow'), their verified licenses ('Apache-2.0' for requests, "
            "'MIT-CMU' or 'HPND' for pillow), and status 'approved' into '/workspace/agent_work/pypi_dependency_ledger.ods' "
            "(valid LibreOffice Calc .ods). Verify Space 2 visually on screen and do not modify '/workspace/user_docs'."
        ),
    ),
    RealMacOSCaseSpec(
        key="rw-arxiv-design-poster",
        title="Reading arXiv ResNet PDF + Writer Notes vs Live GitHub + Inkscape Release Poster Export",
        prototype_ref="facility-wo / multi-app",
        user_url="https://arxiv.org/pdf/1512.03385",
        user_doc_rel="user_docs/resnet_notes.odt",
        user_app_kind="writer",
        agent_url="https://github.com/Ottohere-Mourn/CoDesk/tree/codex/human-agent-normal-user-v1-20261109",
        agent_doc_rel="agent_work/codesk_release_poster.svg",
        agent_app_kind="inkscape",
        user_task=(
            "On Space 1, read the live arXiv PDF 'Deep Residual Learning for Image Recognition' (1512.03385) on the left "
            "and type two residual-learning notes into LibreOffice Writer (resnet_notes.odt) on the right, then save."
        ),
        agent_task=(
            "Switch to Space 2 ('Space 2: Agent Desk'), inspect the live GitHub repository "
            "'https://github.com/Ottohere-Mourn/CoDesk/tree/codex/human-agent-normal-user-v1-20261109' in Chromium and the open Inkscape SVG template "
            "'/workspace/agent_work/codesk_release_poster.svg' on Space 2. Update 'codesk_release_poster.svg' so its text "
            "includes 'CoDesk', 'oscombo', and 'Shared Desktop Benchmark', and export an 800x450 PNG poster using Inkscape "
            "to '/workspace/agent_work/codesk_release_poster.png'. Verify Space 2 visually on screen and do not modify '/workspace/user_docs'."
        ),
    ),
)

REAL_CASE_BY_KEY: dict[str, RealMacOSCaseSpec] = {c.key: c for c in REAL_MACOS_5_CATALOG}


def build_initial_workspace(spec: RealMacOSCaseSpec, workspace: Path) -> None:
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


def get_real_user_actions(spec: RealMacOSCaseSpec) -> list[GUIAction]:
    """Realistic ~60-68s human reading & note-taking trajectory on Space 1."""
    if spec.key == "rw-arxiv-code-review":
        n1 = "Note 1: Transformer uses N=6 encoder-decoder layers with d_model=512."
        n2 = "Note 2: Multi-head attention runs h=8 heads scaled by sqrt(d_k)."
    elif spec.key == "rw-paper-hf-license":
        n1 = "Note 1: GPT-3 scales autoregressive transformer to 175B parameters."
        n2 = "Note 2: Few-shot in-context learning uses demonstrations without gradient updates."
    elif spec.key == "rw-pydocs-pypi-inventory":
        n1 = "Note 1: Use ? placeholders in cur.execute to prevent SQL injection."
        n2 = "Note 2: Call con.commit() to persist transaction changes to disk."
    elif spec.key == "rw-arxiv-design-poster":
        n1 = "Note 1: Residual blocks learn F(x) = H(x) - x with identity shortcut x."
        n2 = "Note 2: 152-layer ResNet achieves lower complexity than VGG nets."
    else:
        return [
            GUIAction("focus_wikipedia_article", "pyautogui.click(560, 420)", "Wikipedia", 2.0),
            GUIAction("scroll_article_overview", "pyautogui.moveTo(560, 460); pyautogui.scroll(-5)", "Wikipedia", 7.5),
            GUIAction("scroll_architecture_section", "pyautogui.moveTo(560, 460); pyautogui.scroll(-6)", "Wikipedia", 8.5),
            GUIAction(
                "focus_calc_b2",
                "pyautogui.click(1480, 420); time.sleep(0.3); pyautogui.hotkey('ctrl','home'); "
                "pyautogui.press('down'); pyautogui.press('right')",
                "LibreOffice Calc",
                5.5,
            ),
            GUIAction("enter_study_date", "pyautogui.write('2026-11-20', interval=0.05); pyautogui.press('tab')", "LibreOffice Calc", 6.0),
            GUIAction("read_attention_details", "pyautogui.moveTo(560, 500); pyautogui.scroll(-4)", "Wikipedia", 8.0),
            GUIAction("refocus_calc_c2", "pyautogui.click(1480, 420); time.sleep(0.2)", "LibreOffice Calc", 4.0),
            GUIAction(
                "enter_time_and_topic",
                "pyautogui.write('14:00-15:30', interval=0.05); pyautogui.press('tab'); "
                "pyautogui.write('Self-Attention Seminar', interval=0.04); pyautogui.press('enter')",
                "LibreOffice Calc",
                5.5,
            ),
            GUIAction("save_study_calendar", "pyautogui.hotkey('ctrl','s'); time.sleep(1.2)", "LibreOffice Calc", 4.0),
        ]

    return [
        GUIAction("focus_paper_page1", "pyautogui.click(560, 420)", "Chromium", 2.0),
        GUIAction("scroll_paper_section1", "pyautogui.moveTo(560, 460); pyautogui.scroll(-5)", "Chromium", 7.5),
        GUIAction("scroll_paper_section2", "pyautogui.moveTo(560, 460); pyautogui.scroll(-6)", "Chromium", 8.5),
        GUIAction(
            "focus_writer_and_append_note1",
            f"pyautogui.click(1520, 420); time.sleep(0.35); pyautogui.hotkey('ctrl','end'); "
            f"pyautogui.press('enter'); pyautogui.write({n1!r}, interval=0.03)",
            "LibreOffice Writer",
            5.0,
        ),
        GUIAction("return_to_paper_figures", "pyautogui.click(560, 500); pyautogui.scroll(-6)", "Chromium", 8.5),
        GUIAction("scroll_paper_experiments", "pyautogui.moveTo(560, 500); pyautogui.scroll(-6)", "Chromium", 8.5),
        GUIAction(
            "focus_writer_and_append_note2",
            f"pyautogui.click(1520, 460); time.sleep(0.35); pyautogui.hotkey('ctrl','end'); "
            f"pyautogui.press('enter'); pyautogui.write({n2!r}, interval=0.03)",
            "LibreOffice Writer",
            5.0,
        ),
        GUIAction("save_reading_notes", "pyautogui.hotkey('ctrl','s'); time.sleep(1.4)", "LibreOffice Writer", 4.0),
    ]


def evaluate_workspace(spec: RealMacOSCaseSpec, workspace: Path, events: list[dict[str, Any]]) -> dict[str, Any]:
    u_path = workspace / spec.user_doc_rel
    u_text = extract_odf_text(u_path)
    u_low = u_text.lower()

    if spec.key == "rw-arxiv-code-review":
        u_checks = {
            "odt_exists": u_path.is_file(),
            "note1_layers_and_dmodel": ("n=6" in u_low and "512" in u_low),
            "note2_heads_and_sqrtdk": ("h=8" in u_low and "sqrt(d_k)" in u_low),
        }
    elif spec.key == "rw-paper-hf-license":
        u_checks = {
            "odt_exists": u_path.is_file(),
            "note1_175b": ("175b" in u_low and "gpt-3" in u_low),
            "note2_fewshot_no_grad": ("few-shot" in u_low and "gradient" in u_low),
        }
    elif spec.key == "rw-wiki-study-calendar":
        u_checks = {
            "ods_exists": u_path.is_file(),
            "date_recorded": "2026-11-20" in u_text,
            "time_recorded": "14:00-15:30" in u_text,
            "topic_recorded": "self-attention seminar" in u_low,
        }
    elif spec.key == "rw-pydocs-pypi-inventory":
        u_checks = {
            "odt_exists": u_path.is_file(),
            "note1_placeholders": ("cur.execute" in u_low and "injection" in u_low),
            "note2_commit": "con.commit()" in u_low,
        }
    elif spec.key == "rw-arxiv-design-poster":
        u_checks = {
            "odt_exists": u_path.is_file(),
            "note1_residual_fx": ("f(x)" in u_low and "shortcut" in u_low),
            "note2_152_layer": ("152-layer" in u_low and "vgg" in u_low),
        }
    else:
        raise ValueError(spec.key)

    agent_gui_space2 = any(
        e.get("actor_id") == "agent"
        and e.get("event_type") == "agent_gui_action"
        and (e.get("space_after") == 1 or e.get("space_before") == 1)
        for e in events
    )

    a_path = workspace / spec.agent_doc_rel
    if spec.key == "rw-arxiv-code-review":
        a_txt = extract_odf_text(a_path).lower()
        a_checks = {
            "ods_exists": a_path.is_file(),
            "package_oscombo": "oscombo" in a_txt,
            "python_310": "3.10" in a_txt,
            "modes_recorded": ("parallel" in a_txt and "sequential" in a_txt),
            "visited_space_2_gui": agent_gui_space2,
        }
    elif spec.key == "rw-paper-hf-license":
        a_txt = extract_odf_text(a_path).lower()
        a_checks = {
            "ods_exists": a_path.is_file(),
            "gpt2_mit": ("gpt2" in a_txt and "mit" in a_txt),
            "bert_apache2": ("bert" in a_txt and "apache" in a_txt),
            "visited_space_2_gui": agent_gui_space2,
        }
    elif spec.key == "rw-wiki-study-calendar":
        a_txt = extract_odf_text(a_path).lower()
        a_checks = {
            "odt_exists": a_path.is_file(),
            "pep20_tim_peters": ("tim peters" in a_txt and "20" in a_txt),
            "pep8_line_79": ("79" in a_txt and "8" in a_txt),
            "visited_space_2_gui": agent_gui_space2,
        }
    elif spec.key == "rw-pydocs-pypi-inventory":
        a_txt = extract_odf_text(a_path).lower()
        a_checks = {
            "ods_exists": a_path.is_file(),
            "requests_apache": ("requests" in a_txt and "apache" in a_txt),
            "pillow_license": ("pillow" in a_txt and any(k in a_txt for k in ("mit", "hpnd", "cmu"))),
            "visited_space_2_gui": agent_gui_space2,
        }
    elif spec.key == "rw-arxiv-design-poster":
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
            "visited_space_2_gui": agent_gui_space2,
        }
    else:
        raise ValueError(spec.key)

    return {
        "user": {"success": all(u_checks.values()), "checks": u_checks, "extracted_text_preview": u_text[:300]},
        "agent": {"success": all(a_checks.values()), "checks": a_checks},
    }
