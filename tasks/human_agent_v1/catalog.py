"""Unified catalog of all 17 Human-Agent workflow cases from commit 684c79a."""
from __future__ import annotations

from dataclasses import dataclass
import importlib
from typing import Any

from .actors import GUIAction

SOURCE_BRANCH = "codex/human-agent-normal-user-v1-20261109"
SOURCE_COMMIT = "684c79a6374b19a3851cf83b7d79c8978e5b8118"


@dataclass(frozen=True)
class HumanAgentCaseSpec:
    key: str
    case_id: str
    version: str
    family: str
    title: str
    kind: str  # "single_app" | "po_archive" | "triage" | "ticket"
    app_module: str | None
    initial_path: str
    expected_title: str
    agent_budget: int
    agent_timeout_s: int
    upstream_status: str


MAIL_AGENT_TASK = (
    "In the open CoDesk Mail inbox, review customer conversation CUST-2048 about order SO-7718. "
    "Read all messages in that thread and the visible Warranty and Delivery-Damage Playbook POL-WAR-3. "
    "Apply the supported internal case label and priority. Then reply to Casey Rivera but SAVE THE MESSAGE AS A DRAFT; "
    "do not send it. The draft should acknowledge the damage, apologize, confirm the eligible replacement, and state the "
    "normal dispatch timing. Do not promise a refund or alter any source message."
)
MAIL_USER_TASK = (
    'In the open Inbox, open the Afternoon queue coverage conversation from Ops On-call. Reply to ops-oncall@company.test '
    'with exactly: "I can cover 14:00-16:00 today; please assign me the queue." Send the reply and mark the conversation '
    "as done. Do not edit other threads."
)

CALENDAR_AGENT_TASK = (
    "In the open CoDesk Calendar week view, schedule the 30-minute Release Readiness Review using the visible Meeting brief, "
    "participant availability, and room availability. Invite Ava Chen, Eli Brooks, and Mina Patel; the organizer plus guests "
    "requires a room for at least four people. Put it on the Project Team calendar at a time when every guest and a suitable "
    "room are available. Use the meeting brief agenda and save the invitation as a draft; do not send it."
)
CALENDAR_USER_TASK = (
    'In the open CoDesk Calendar week view, add a personal focus block titled exactly "Finalize November report" on Friday, '
    "November 20, 2026 from 13:00 to 13:45. Set a reminder for 10 minutes before. Save it only on the Personal calendar; "
    "do not invite anyone."
)

PO_ARCHIVE_AGENT_TASK = (
    "Review invoice INV-4831 in the open Procurement Review Queue. Inspect the linked purchase order, receiving report, "
    "vendor invoice, and freight policy. Then complete the Invoice Reconciliation form: choose the supported disposition, "
    "enter the quantity accepted into stock and the freight amount above the authorized cap, cite the source IDs, and write "
    "a concise rationale covering each discrepancy. Save once and verify the visible saved confirmation. This is a review only: "
    "do not release payment or alter any source record."
)
PO_ARCHIVE_USER_TASK = (
    "In the open Vendor Portal, download the signed receiving acknowledgement D-4831. Then attach that downloaded CSV to "
    "Finance / November 2026 in the visible Finance Archive page and submit. Verify the confirmation that it was archived. "
    "Do not edit other records."
)

TRIAGE_AGENT_TASK_TEMPLATE = (
    "Review ticket T-1042 in Case Desk. Inspect the ticket, linked order and delivery evidence, and refund policy. "
    "Then create a short internal triage brief using this form in the current browser window: {brief_url}. "
    "Select the issue classification and recommended next step supported by the source records, cite both the delivery "
    "evidence and policy IDs, and give a concise rationale. The brief is advisory only: do not issue a refund, create a "
    "formal Case Review, or change ticket/order status. Preserve all unrelated state."
)
TICKET_AGENT_TASK = (
    "Complete only the evidence-review stage for ticket T-1042 in the open Case Desk application. Inspect the ticket, "
    "linked order and line items, delivery evidence, and return policy. Save one traceable Case Review recording the "
    "eligible line, supporting evidence and policy, the supported item-level refund amount (excluding shipping), and a "
    "concise rationale. Use the visible Case Desk navigation links to move among Ticket, Order, Policy, and Reviews; "
    "the long review form may require scrolling. Submit the review once and verify its saved confirmation. Do not issue "
    "any refund, create a processor pre-check, or resolve the ticket; those later actions are outside this task."
)
HANDOFF_USER_TASK = (
    "For ticket T-1043, enter this internal update note exactly: Asked carrier for Tuesday delivery window; follow up at 16:00. "
    "Set the local follow-up time to 2026-11-10 16:00, submit, and verify the saved confirmation."
)


HUMAN_AGENT_17_CATALOG: tuple[HumanAgentCaseSpec, ...] = (
    HumanAgentCaseSpec(
        key="ha-ticket",
        case_id="ha-ticket-normal-user-v1",
        version="0.4.0",
        family="ticket_review",
        title="Evidence review while a user updates a shift handoff (upstream frozen complex variant)",
        kind="ticket",
        app_module=None,
        initial_path="/login?actor=S",
        expected_title="Case queue",
        agent_budget=40,
        agent_timeout_s=900,
        upstream_status="frozen_no_go",
    ),
    HumanAgentCaseSpec(
        key="ha-triage",
        case_id="ha-evidence-triage-normal-user-v1",
        version="0.1.0",
        family="ticket_triage",
        title="Advisory ticket triage brief while a user updates a shift handoff",
        kind="triage",
        app_module="triage_brief",
        initial_path="/login?actor=S",
        expected_title="Case queue",
        agent_budget=40,
        agent_timeout_s=900,
        upstream_status="validated_pilot",
    ),
    HumanAgentCaseSpec(
        key="ha-po-archive",
        case_id="ha-po-reconcile-normal-user-v1",
        version="0.1.5",
        family="procurement_archive",
        title="Reconcile a vendor invoice while a user downloads and archives a receipt CSV",
        kind="po_archive",
        app_module="po_reconcile",
        initial_path="/agent",
        expected_title="Procurement Review Queue",
        agent_budget=40,
        agent_timeout_s=900,
        upstream_status="validated_pilot",
    ),
    HumanAgentCaseSpec(
        key="ha-mail",
        case_id="ha-mail-review-normal-user-v1",
        version="0.1.0",
        family="mail",
        title="Customer damage review & draft reply while a user replies to ops mail",
        kind="single_app",
        app_module="mail_workflow",
        initial_path="/mail",
        expected_title="CoDesk Mail - Inbox",
        agent_budget=40,
        agent_timeout_s=900,
        upstream_status="validated_pilot",
    ),
    HumanAgentCaseSpec(
        key="ha-calendar",
        case_id="ha-calendar-meeting-focus-v1",
        version="0.1.0",
        family="calendar",
        title="Schedule a multi-guest release meeting while adding a personal focus block",
        kind="single_app",
        app_module="calendar_planning",
        initial_path="/calendar",
        expected_title="CoDesk Calendar - Week view",
        agent_budget=40,
        agent_timeout_s=900,
        upstream_status="validated_pilot",
    ),
    HumanAgentCaseSpec(
        key="ha-inventory",
        case_id="ha-inventory-replenishment-receiving-v1",
        version="0.1.0",
        family="inventory",
        title="Draft three SKU replenishments while a user records a packing-slip receipt",
        kind="single_app",
        app_module="inventory_ops",
        initial_path="/dashboard",
        expected_title="CoDesk Warehouse - Dashboard",
        agent_budget=50,
        agent_timeout_s=900,
        upstream_status="runnable_low_overlap",
    ),
    HumanAgentCaseSpec(
        key="code-review",
        case_id="ha-code-review-v1",
        version="0.2.2",
        family="engineering_qa",
        title="Line-level pull-request boundary review while a user posts QA staging signoff",
        kind="single_app",
        app_module="code_review",
        initial_path="/",
        expected_title="CoDesk Code Review",
        agent_budget=40,
        agent_timeout_s=900,
        upstream_status="validated_pilot",
    ),
    HumanAgentCaseSpec(
        key="access-review",
        case_id="ha-access-review-v1",
        version="0.2.2",
        family="identity_security",
        title="Least-privilege identity review while a user updates own security profile",
        kind="single_app",
        app_module="access_review",
        initial_path="/",
        expected_title="CoDesk Identity Console",
        agent_budget=40,
        agent_timeout_s=900,
        upstream_status="validated_pilot",
    ),
    HumanAgentCaseSpec(
        key="transit-itinerary",
        case_id="ha-transit-itinerary-v1",
        version="0.2.2",
        family="transit_accessibility",
        title="Step-free museum itinerary planning while a user saves a personal station favorite",
        kind="single_app",
        app_module="transit_planner",
        initial_path="/",
        expected_title="CoDesk Transit Planner",
        agent_budget=40,
        agent_timeout_s=900,
        upstream_status="validated_pilot",
    ),
    HumanAgentCaseSpec(
        key="consumer-banking",
        case_id="ha-consumer-banking-v1",
        version="0.1.4",
        family="finance",
        title="Card transaction policy reconciliation while a user schedules an electric bill",
        kind="single_app",
        app_module="consumer_banking",
        initial_path="/",
        expected_title="CoDesk Personal Finance",
        agent_budget=45,
        agent_timeout_s=900,
        upstream_status="validated_pilot",
    ),
    HumanAgentCaseSpec(
        key="lab-qc",
        case_id="ha-lab-qc-v1",
        version="0.1.4",
        family="laboratory",
        title="Laboratory QC batch review while a user accessions an environmental water sample",
        kind="single_app",
        app_module="lab_qc",
        initial_path="/",
        expected_title="CoDesk Lab Sample Console",
        agent_budget=35,
        agent_timeout_s=900,
        upstream_status="validated_pilot",
    ),
    HumanAgentCaseSpec(
        key="home-energy",
        case_id="ha-home-energy-v1",
        version="0.1.1",
        family="smart_home",
        title="Overnight EV off-peak schedule while a user sets weekday study thermostat hours",
        kind="single_app",
        app_module="home_energy",
        initial_path="/",
        expected_title="CoDesk Home Energy",
        agent_budget=35,
        agent_timeout_s=900,
        upstream_status="validated_pilot",
    ),
    HumanAgentCaseSpec(
        key="edu-grade",
        case_id="ha-edu-grade-v1",
        version="0.1.0",
        family="education",
        title="ENG-204 rubric draft grading while a user records BIO-118 lab attendance",
        kind="single_app",
        app_module="edu_grade",
        initial_path="/",
        expected_title="CoDesk Learning Hub",
        agent_budget=35,
        agent_timeout_s=900,
        upstream_status="validated_pilot",
    ),
    HumanAgentCaseSpec(
        key="media-library",
        case_id="ha-media-library-v1",
        version="0.1.0",
        family="media_catalog",
        title="Campaign license screening & draft collection while a user edits photo caption/alt",
        kind="single_app",
        app_module="media_library",
        initial_path="/",
        expected_title="CoDesk Media Library",
        agent_budget=35,
        agent_timeout_s=900,
        upstream_status="validated_pilot",
    ),
    HumanAgentCaseSpec(
        key="facility-wo",
        case_id="ha-facility-wo-v1",
        version="0.1.0",
        family="facilities",
        title="AHU-3 vibration HVAC work order while a user reports classroom AV projector fault",
        kind="single_app",
        app_module="facility_wo",
        initial_path="/",
        expected_title="CoDesk Facilities Desk",
        agent_budget=35,
        agent_timeout_s=900,
        upstream_status="validated_pilot",
    ),
    HumanAgentCaseSpec(
        key="volunteer-ops",
        case_id="ha-volunteer-ops-v1",
        version="0.2.0",
        family="volunteer",
        title="Pantry Packing role draft assignments while a user logs River Cleanup check-ins",
        kind="single_app",
        app_module="volunteer_ops",
        initial_path="/",
        expected_title="CoDesk Volunteer Hub",
        agent_budget=35,
        agent_timeout_s=900,
        upstream_status="validated_pilot",
    ),
    HumanAgentCaseSpec(
        key="garden-ops",
        case_id="ha-garden-ops-v1",
        version="0.2.0",
        family="community_garden",
        title="North-12 fall pea planting draft while a user logs South-03 soil watering",
        kind="single_app",
        app_module="garden_ops",
        initial_path="/",
        expected_title="CoDesk Community Garden",
        agent_budget=35,
        agent_timeout_s=900,
        upstream_status="validated_pilot",
    ),
)

CASE_BY_KEY: dict[str, HumanAgentCaseSpec] = {c.key: c for c in HUMAN_AGENT_17_CATALOG}
ACTIVE_16_KEYS: tuple[str, ...] = tuple(c.key for c in HUMAN_AGENT_17_CATALOG if c.upstream_status != "frozen_no_go")


def load_app_module(spec: HumanAgentCaseSpec) -> Any:
    if not spec.app_module:
        return None
    return importlib.import_module(f".human_apps.{spec.app_module}", package=__package__)


def get_case_prompts(spec: HumanAgentCaseSpec, urls: dict[str, str]) -> tuple[str, str]:
    if spec.key == "ha-mail":
        return MAIL_AGENT_TASK, MAIL_USER_TASK
    if spec.key == "ha-calendar":
        return CALENDAR_AGENT_TASK, CALENDAR_USER_TASK
    if spec.key == "ha-po-archive":
        return PO_ARCHIVE_AGENT_TASK, PO_ARCHIVE_USER_TASK
    if spec.key == "ha-triage":
        return TRIAGE_AGENT_TASK_TEMPLATE.format(brief_url=urls["triage_url"] + "/"), HANDOFF_USER_TASK
    if spec.key == "ha-ticket":
        return TICKET_AGENT_TASK, HANDOFF_USER_TASK
    app = load_app_module(spec)
    return str(app.AGENT_TASK), str(app.USER_TASK)


def get_user_actions(spec: HumanAgentCaseSpec) -> list[GUIAction]:
    """Chromium-156 (1920x1080 X11, DejaVu Sans) calibrated open-loop User GUI actions."""
    delay = 0.75
    if spec.key == "ha-mail":
        return [
            GUIAction("open_ops_thread", "pyautogui.click(750, 582); time.sleep(1.2)", "CoDesk Mail", delay),
            GUIAction("open_reply_composer", "pyautogui.click(534, 512); time.sleep(1.2)", "CoDesk Mail", delay),
            GUIAction(
                "type_ops_reply",
                "pyautogui.click(750, 655); pyautogui.write('I can cover 14:00-16:00 today; please assign me the queue.', interval=0.02)",
                "CoDesk Mail",
                delay,
            ),
            GUIAction("send_ops_reply", "pyautogui.click(722, 773); time.sleep(1.2)", "CoDesk Mail", delay),
            GUIAction("mark_ops_done", "pyautogui.click(669, 572); time.sleep(1.0)", "CoDesk Mail", delay),
        ]
    if spec.key == "ha-calendar":
        fill_code = """pyautogui.click(750, 397)
pyautogui.press('p'); pyautogui.press('enter')
pyautogui.press('tab'); pyautogui.write('Finalize November report')
pyautogui.press('tab'); pyautogui.write('2026-11-20')
pyautogui.press('tab'); pyautogui.press('tab'); pyautogui.write('13:00')
pyautogui.press('tab'); pyautogui.write('13:45')
pyautogui.press('tab'); pyautogui.press('tab'); pyautogui.press('tab')
pyautogui.press('down'); pyautogui.press('enter')
pyautogui.press('tab'); time.sleep(.5)"""
        return [
            GUIAction("open_new_event", "pyautogui.click(522, 355); time.sleep(1.0)", "CoDesk Calendar", delay),
            GUIAction("fill_personal_block", fill_code, "CoDesk Calendar", delay),
            GUIAction("save_personal_block", "pyautogui.click(545, 981); time.sleep(1.5)", "CoDesk Calendar", delay),
        ]
    if spec.key == "ha-inventory":
        return [
            GUIAction("open_receiving_queue", "pyautogui.click(846, 197); time.sleep(1.0)", "CoDesk Warehouse", delay),
            GUIAction("open_packing_slip", "pyautogui.click(555, 453); time.sleep(1.0)", "CoDesk Warehouse", delay),
            GUIAction("open_receipt_form", "pyautogui.click(740, 571); time.sleep(1.0)", "CoDesk Warehouse", delay),
            GUIAction(
                "fill_receipt",
                "pyautogui.click(750, 450); pyautogui.press('end'); pyautogui.press('enter'); pyautogui.press('tab'); "
                "pyautogui.write('LOT-7721', interval=0.06); pyautogui.press('tab'); pyautogui.write('12', interval=0.06); "
                "pyautogui.press('tab'); pyautogui.write('B-14', interval=0.06); time.sleep(.5)",
                "CoDesk Warehouse",
                delay,
            ),
            GUIAction("submit_receipt", "pyautogui.click(562, 816); time.sleep(1.5)", "CoDesk Warehouse", delay),
        ]
    if spec.key == "ha-po-archive":
        return [
            GUIAction("switch_to_vendor_portal", "pyautogui.hotkey('alt','tab')", "Vendor Portal", 0.8),
            GUIAction("download_receipt", "pyautogui.click(773, 436); time.sleep(1.2)", "Vendor Portal", 1.2),
            GUIAction("open_finance_archive", "pyautogui.click(658, 535); time.sleep(1.0)", "Finance Archive", 1.0),
            GUIAction("open_receipt_picker", "pyautogui.click(620, 533); time.sleep(1.2)", None, 0.8),
            GUIAction(
                "select_downloaded_receipt",
                "pyautogui.hotkey('ctrl','l'); time.sleep(0.4); "
                "pyautogui.write('/home/gui/Downloads/D-4831-receipt.csv', interval=0.02); "
                "time.sleep(0.35); pyautogui.press('enter'); time.sleep(0.35); pyautogui.press('enter'); time.sleep(0.9)",
                "Finance Archive",
                0.8,
            ),
            GUIAction("submit_receipt_archive", "pyautogui.click(647, 590); time.sleep(2.0)", "Finance Archive", 1.0),
        ]
    if spec.key in {"ha-triage", "ha-ticket"}:
        return [
            GUIAction("switch_to_shift_handoff", "pyautogui.hotkey('alt','tab')", None, 1.2),
            GUIAction("focus_handoff_note", "pyautogui.click(800, 578)", "Shift Handoff", 1.2),
            GUIAction(
                "type_handoff_note",
                "pyautogui.write('Asked carrier for Tuesday delivery window; follow up at 16:00.', interval=0.025)",
                "Shift Handoff",
                2.0,
            ),
            GUIAction("tab_to_follow_up", "pyautogui.press('tab')", "Shift Handoff", 1.2),
            GUIAction("enter_follow_up", "pyautogui.write('2026-11-10 16:00')", "Shift Handoff", 2.2),
            GUIAction("submit_handoff", "pyautogui.press('tab'); pyautogui.press('enter')", "Shift Handoff", 1.6),
        ]
    app = load_app_module(spec)
    if spec.key == "access-review":
        user_email = getattr(app, "USER_EMAIL", "sam.alerts@northstar.test")
        return [
            GUIAction("open_own_security_profile", "pyautogui.click(632, 207)", app.APP_TITLE, 0.8),
            GUIAction("inspect_current_recovery_setting", "pyautogui.moveTo(850, 503)", app.APP_TITLE, 5.0),
            GUIAction("open_account_security_guide", "pyautogui.click(842, 207)", app.APP_TITLE, 4.0),
            GUIAction("read_recovery_address_guidance", "pyautogui.moveTo(1450, 680); pyautogui.scroll(-2)", app.APP_TITLE, 9.0),
            GUIAction("read_signin_alert_guidance", "pyautogui.moveTo(1450, 680); pyautogui.scroll(-2)", app.APP_TITLE, 8.0),
            GUIAction("return_to_own_profile", "pyautogui.hotkey('alt', 'left')", app.APP_TITLE, 5.0),
            GUIAction("enter_recovery_email", f"pyautogui.click(850, 503); pyautogui.hotkey('ctrl','a'); pyautogui.write({user_email!r}, interval=0.035)", app.APP_TITLE, 5.0),
            GUIAction("enable_alerts_and_save", "pyautogui.press('tab'); pyautogui.press('space'); pyautogui.press('tab'); pyautogui.press('enter')", app.APP_TITLE, 2.0),
            GUIAction("reopen_profile_after_confirmation", "pyautogui.click(632, 207)", app.APP_TITLE, 5.0),
            GUIAction("verify_persisted_security_settings", "pyautogui.moveTo(850, 503)", app.APP_TITLE, 6.0),
        ]
    if spec.key == "home-energy":
        return [
            GUIAction("open_study_thermostat", "pyautogui.click(503, 207)", app.APP_TITLE, 0.8),
            GUIAction("inspect_current_study_schedule", "pyautogui.moveTo(1758, 408)", app.APP_TITLE, 6.0),
            GUIAction("open_comfort_guidance", "pyautogui.click(642, 207)", app.APP_TITLE, 4.0),
            GUIAction("read_occupied_room_guidance", "pyautogui.moveTo(1617, 464); pyautogui.scroll(-2)", app.APP_TITLE, 9.0),
            GUIAction("return_to_study_thermostat", "pyautogui.hotkey('alt','left')", app.APP_TITLE, 5.0),
            GUIAction("open_weekday_schedule_form", "pyautogui.click(610, 460)", app.APP_TITLE, 4.0),
            GUIAction("choose_weekdays", "pyautogui.click(994, 435); pyautogui.press('home'); pyautogui.press('enter')", app.APP_TITLE, 5.0),
            GUIAction("choose_start_and_end_times", "pyautogui.click(994, 518); pyautogui.press('home'); pyautogui.press('down'); pyautogui.press('enter'); pyautogui.click(994, 601); pyautogui.press('home'); pyautogui.press('down'); pyautogui.press('enter')", app.APP_TITLE, 5.0),
            GUIAction("choose_temperature_and_review", "pyautogui.click(994, 684); pyautogui.press('home'); pyautogui.press('down'); pyautogui.press('enter'); pyautogui.moveTo(1547, 843)", app.APP_TITLE, 5.0),
            GUIAction("save_study_schedule", "pyautogui.click(601, 738)", app.APP_TITLE, 2.0),
            GUIAction("reopen_study_thermostat", "pyautogui.click(503, 207)", app.APP_TITLE, 5.0),
            GUIAction("verify_saved_study_hours", "pyautogui.moveTo(1547, 408)", app.APP_TITLE, 5.0),
        ]
    if spec.key == "lab-qc":
        return [
            GUIAction("open_accession_queue", "pyautogui.click(412, 207)", app.APP_TITLE, 0.8),
            GUIAction("open_sample_receipt", "pyautogui.click(843, 412)", app.APP_TITLE, 4.0),
            GUIAction("inspect_receipt_fields", "pyautogui.moveTo(1758, 900)", app.APP_TITLE, 7.0),
            GUIAction("open_intake_guide", "pyautogui.click(568, 207)", app.APP_TITLE, 4.0),
            GUIAction("read_chain_of_custody_steps", "pyautogui.moveTo(1758, 950); pyautogui.scroll(-2)", app.APP_TITLE, 9.0),
            GUIAction("return_to_receipt", "pyautogui.hotkey('alt','left')", app.APP_TITLE, 5.0),
            GUIAction("open_new_accession_form", "pyautogui.click(540, 662)", app.APP_TITLE, 4.0),
            GUIAction("enter_accession_id", "pyautogui.click(994, 437); pyautogui.hotkey('ctrl','a'); pyautogui.write('AC-508', interval=0.1)", app.APP_TITLE, 3.0),
            GUIAction("enter_collection_date", "pyautogui.click(505, 524); pyautogui.write('10112026', interval=0.15)", app.APP_TITLE, 4.0),
            GUIAction("select_sample_type", "pyautogui.click(994, 609); pyautogui.press('home'); pyautogui.press('down'); pyautogui.press('enter')", app.APP_TITLE, 3.0),
            GUIAction("enter_collection_site", "pyautogui.click(994, 694); pyautogui.write('North Meadow station NM-2', interval=0.06)", app.APP_TITLE, 3.0),
            GUIAction("enter_coc_and_storage", "pyautogui.click(994, 780); pyautogui.write('COC-8841', interval=0.08); pyautogui.click(994, 864); pyautogui.press('home'); pyautogui.press('down'); pyautogui.press('enter')", app.APP_TITLE, 4.0),
            GUIAction("save_accession", "pyautogui.click(575, 918)", app.APP_TITLE, 2.0),
            GUIAction("review_confirmation", "pyautogui.moveTo(1547, 900)", app.APP_TITLE, 5.0),
            GUIAction("reopen_accession_queue", "pyautogui.click(412, 207)", app.APP_TITLE, 1.5),
            GUIAction("open_saved_accession_record", "pyautogui.click(994, 412)", app.APP_TITLE, 4.0),
            GUIAction("verify_persisted_accession", "pyautogui.moveTo(1547, 900)", app.APP_TITLE, 5.0),
        ]
    if spec.key in {"edu-grade", "media-library", "facility-wo", "volunteer-ops", "garden-ops"}:
        from .human_apps._next_workflow_factory import DATA
        mod_key = spec.app_module
        uf = DATA[mod_key]["uf"]
        title = app.APP_TITLE
        acts = [
            GUIAction("open_user_checklist", "pyautogui.click(586, 207)", title, 2.5),
            GUIAction("read_user_checklist", "pyautogui.moveTo(1350, 450); pyautogui.scroll(-2)", title, 11.0),
            GUIAction("continue_to_user_form", "pyautogui.click(710, 207)", title, 5.0),
            GUIAction("review_user_form", "pyautogui.moveTo(1450, 500)", title, 5.0),
            GUIAction("focus_first_user_field", "pyautogui.click(987, 563)", title, 2.0),
        ]
        for idx, (k, _label, value) in enumerate(uf):
            acts.append(
                GUIAction(
                    "enter_" + k,
                    f"pyautogui.write({str(value)!r}, interval=0.025); pyautogui.press('tab')",
                    title,
                    3.0 if idx else 2.0,
                )
            )
        acts.extend(
            [
                GUIAction("submit_user_record", "pyautogui.press('enter')", title, 2.0),
                GUIAction("review_confirmation", "pyautogui.moveTo(1450, 380)", title, 6.0),
                GUIAction("reopen_user_record", "pyautogui.click(560, 410)", title, 3.0),
                GUIAction("verify_user_record", "pyautogui.moveTo(1400, 500)", title, 8.0),
            ]
        )
        return acts
    return list(app.user_actions())
