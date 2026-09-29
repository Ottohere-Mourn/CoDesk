from swcub.evaluator import GuestLibreOfficeBindingEvaluator


WRITER_NS = "urn:oasis:names:tc:opendocument:xmlns:office:1.0"
TEXT_NS = "urn:oasis:names:tc:opendocument:xmlns:text:1.0"
TABLE_NS = "urn:oasis:names:tc:opendocument:xmlns:table:1.0"


def writer(text):
    return (f'<office:document xmlns:office="{WRITER_NS}" xmlns:text="{TEXT_NS}">'
            f'<office:body><office:text><text:p>{text}</text:p></office:text></office:body>'
            '</office:document>')


def calc(b2):
    return (f'<office:document xmlns:office="{WRITER_NS}" xmlns:text="{TEXT_NS}" '
            f'xmlns:table="{TABLE_NS}"><office:body><office:spreadsheet>'
            '<table:table><table:table-row>'
            '<table:table-cell><text:p>Record</text:p></table:table-cell>'
            '<table:table-cell><text:p>Status</text:p></table:table-cell>'
            '</table:table-row><table:table-row>'
            '<table:table-cell><text:p>Quarterly</text:p></table:table-cell>'
            f'<table:table-cell><text:p>{b2}</text:p></table:table-cell>'
            '</table:table-row></table:table></office:spreadsheet></office:body>'
            '</office:document>')


def test_binding_evaluator_checks_goal_and_non_goal_application_state():
    files = {
        ("writer_desktop", "/tmp/swcub_office/document.fodt"): writer("Approved by GUI actor"),
        ("writer_desktop", "/tmp/swcub_office/table.fods"): calc("Draft"),
        ("calc_desktop", "/tmp/swcub_office/document.fodt"): writer("Quarterly status report"),
        ("calc_desktop", "/tmp/swcub_office/table.fods"): calc("Approved"),
    }
    evaluator = GuestLibreOfficeBindingEvaluator(
        lambda binding, path: files[(binding, path)],
        {"writer_desktop": {"writer_text": "Approved by GUI actor",
                             "calc_cells": [["Record", "Status"], ["Quarterly", "Draft"]]},
         "calc_desktop": {"writer_text": "Quarterly status report",
                           "calc_cells": [["Record", "Status"], ["Quarterly", "Approved"]]}},
        {"writer_actor": {"desktop_binding": "writer_desktop", "field": "writer_text",
                          "expected": "Approved by GUI actor"},
         "calc_actor": {"desktop_binding": "calc_desktop", "field": "calc_cells",
                        "expected": [["Record", "Status"], ["Quarterly", "Approved"]]}},
        {"writer_desktop": {"writer_text": "Quarterly status report",
                             "calc_cells": [["Record", "Status"], ["Quarterly", "Draft"]]},
         "calc_desktop": {"writer_text": "Quarterly status report",
                           "calc_cells": [["Record", "Status"], ["Quarterly", "Draft"]]}})
    result = evaluator.evaluate()
    assert result["success"] is True
    assert all(row["success"] for row in result["actor_goal_success"].values())
    assert result["contamination_events"] == []


def test_binding_evaluator_detects_writer_text_in_calc_non_goal_state():
    files = {
        ("shared", "/tmp/swcub_office/document.fodt"): writer("Quarterly status report"),
        ("shared", "/tmp/swcub_office/table.fods"): calc("Approved by GUI actor"),
    }
    evaluator = GuestLibreOfficeBindingEvaluator(
        lambda binding, path: files[(binding, path)],
        {"shared": {"writer_text": "Approved by GUI actor",
                     "calc_cells": [["Record", "Status"], ["Quarterly", "Approved"]]}},
        {"writer_actor": {"desktop_binding": "shared", "field": "writer_text",
                           "expected": "Approved by GUI actor"},
         "calc_actor": {"desktop_binding": "shared", "field": "calc_cells",
                        "expected": [["Record", "Status"], ["Quarterly", "Approved"]]}},
        {"shared": {"writer_text": "Quarterly status report",
                     "calc_cells": [["Record", "Status"], ["Quarterly", "Draft"]]}})
    result = evaluator.evaluate()
    assert result["success"] is False
    assert result["actor_goal_success"]["writer_actor"]["success"] is False
    assert result["actor_goal_success"]["calc_actor"]["success"] is False
    assert {row["field"] for row in result["contamination_events"]} == {"calc_cells"}
    assert result["actor_goal_success"]["calc_actor"]["success"] is False


def test_goal_miss_that_preserves_initial_state_is_not_contamination():
    files = {
        ("calc_desktop", "/tmp/swcub_office/document.fodt"): writer("Quarterly status report"),
        ("calc_desktop", "/tmp/swcub_office/table.fods"): calc("Draft"),
    }
    initial = {"calc_desktop": {"writer_text": "Quarterly status report",
                                 "calc_cells": [["Record", "Status"], ["Quarterly", "Draft"]]}}
    evaluator = GuestLibreOfficeBindingEvaluator(
        lambda binding, path: files[(binding, path)],
        {"calc_desktop": {"writer_text": "Quarterly status report",
                           "calc_cells": [["Record", "Status"], ["Quarterly", "Approved"]]}},
        {"calc_actor": {"desktop_binding": "calc_desktop", "field": "calc_cells",
                        "expected": [["Record", "Status"], ["Quarterly", "Approved"]]}},
        initial)
    result = evaluator.evaluate()
    assert result["success"] is False
    assert result["actor_goal_success"]["calc_actor"]["success"] is False
    assert result["contamination_events"] == []
