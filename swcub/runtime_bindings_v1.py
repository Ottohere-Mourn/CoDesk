"""Auditable workflow-to-legacy-runtime reference map and compile-time binding catalog."""
from __future__ import annotations
from pathlib import Path
from typing import Any

# These are reference points to preserve/reuse; they are not claims that the
# legacy runner has already been parameterized for arbitrary generated instances.
LEGACY_ANCHORS={"F-01","F-04","F-02","C-01","C-03","C-02","A-01","A-02","S-01","U-01"}
WORKFLOW_REFERENCES={
 "F-01":{"runner":"scripts/run_writer_calc_v1.py","setup":"Writer/Calc fixture and app setup","actor":"ScriptedWriterActor / ScriptedCalcActor / OSWorldAgentActor","evaluator":"GuestLibreOfficeBindingEvaluator","observer":"foreground window + ODF Writer/Calc state","reset":"DesktopEnv.reset + fixture reseed","cleanup":"DesktopEnv.close via owned-resource provider"},
 "F-04":{"runner":"scripts/run_workflows_v1.py","setup":"Calc range + Writer target setup","actor":"workflow scripted actors","evaluator":"workflow-specific state evaluator","observer":"foreground window + selected Calc range + ODF","reset":"runner reset path","cleanup":"owned DesktopEnv close"},
 "F-02":{"runner":"scripts/run_browser_writer_workflows_v1.py","setup":"Browser review form + Writer comment anchor","actor":"browser/writer workflow actors","evaluator":"browser state + Writer document evaluator","observer":"window focus + browser form state + ODF","reset":"browser/writer runner reset","cleanup":"owned DesktopEnv close"},
 "C-01":{"runner":"scripts/run_clipboard_v1_round1.py","setup":"Writer source + Calc destination + clipboard probe","actor":"clipboard workflow actors","evaluator":"clipboard event log + ODF final-state evaluator","observer":"read-only X11 clipboard observer + focused GUI target","reset":"clipboard runner reset","cleanup":"owned DesktopEnv close"},
 "C-03":{"runner":"scripts/run_workflows_v1.py","setup":"Calc matrix + Writer destination","actor":"structured clipboard workflow actors","evaluator":"ODF range/table evaluator","observer":"clipboard formats + selected range + destination document","reset":"runner reset path","cleanup":"owned DesktopEnv close"},
 "C-02":{"runner":"scripts/run_browser_writer_workflows_v1.py","setup":"Writer hyperlink + Browser URL destination","actor":"hyperlink transfer actors","evaluator":"ODF href + Browser destination state","observer":"clipboard payload formats + Browser form state","reset":"browser/writer runner reset","cleanup":"owned DesktopEnv close"},
 "A-01":{"runner":"scripts/run_browser_context_v1.py","setup":"one Chrome window with tab-specific local pages","actor":"browser context actors","evaluator":"per-tab submitted state oracle","observer":"top-level window + active tab/page + local state endpoint","reset":"Browser context runner reset","cleanup":"owned DesktopEnv close"},
 "A-02":{"runner":"scripts/run_browser_record_context_v1.py","setup":"single-page record list/detail state","actor":"record context actors","evaluator":"record-specific values/revision oracle","observer":"route/record selection + page state endpoint","reset":"record context runner reset","cleanup":"owned DesktopEnv close"},
 "S-01":{"runner":"scripts/probe_selection_active_object_v1.py","setup":"Calc active-cell targets","actor":"selection probe actors","evaluator":"Calc final cells + ODF guard integrity","observer":"UNO selected object/range + active window","reset":"probe reset path","cleanup":"owned DesktopEnv close"},
 "U-01":{"runner":"scripts/probe_undo_history_v1.py","setup":"Calc edits and undo history","actor":"undo probe actors","evaluator":"full Calc grid + undo depth/order","observer":"UNO undo/history state + ODF final grid","reset":"probe reset path","cleanup":"owned DesktopEnv close"},
 "F-N1":{"runner":"scripts/run_matrix_workflow_v1.py","setup":"two Writer documents and foreground order","actor":"F-N1 workflow actors","evaluator":"per-document ODF exact state","observer":"document/window identities + foreground transitions","reset":"matrix runner reset","cleanup":"owned DesktopEnv close"},
 "C-N1":{"runner":"scripts/run_matrix_workflow_v1.py","setup":"Writer table + Browser rich payload endpoint","actor":"C-N1 workflow actors","evaluator":"HTML MIME structure + destination exact state","observer":"X11 selection MIME + clipboard generation","reset":"matrix runner reset","cleanup":"owned DesktopEnv close"},
 "A-N1":{"runner":"scripts/run_matrix_workflow_v1.py","setup":"single-page route-changing app state","actor":"A-N1 workflow actors","evaluator":"route/revision exact state","observer":"same-window route + record revision endpoint","reset":"matrix runner reset","cleanup":"owned DesktopEnv close"},
 "S-N1":{"runner":"scripts/run_matrix_workflow_v1.py","setup":"single Writer document with two ranges","actor":"S-N1 workflow actors","evaluator":"ODF range formatting + untouched-range oracle","observer":"UNO text selection/caret + window identity","reset":"matrix runner reset","cleanup":"owned DesktopEnv close"},
 "U-N1":{"runner":"scripts/run_matrix_workflow_v1.py","setup":"single Writer document and ordered edit history","actor":"U-N1 workflow actors","evaluator":"ODF paragraphs + undo history oracle","observer":"UNO undo action/history + document identity","reset":"matrix runner reset","cleanup":"owned DesktopEnv close"},
}

FAMILY_OBSERVERS={
 "focus_input_routing":"foreground_window_and_input_target_v1",
 "clipboard_state":"x11_selection_owner_payload_generation_v1",
 "application_context":"browser_active_context_and_revision_v1",
 "selection_active_object":"uno_selection_active_object_v1",
 "undo_redo_history":"uno_undo_history_v1",
}

def compile_workflow_binding(plan: dict[str,Any], repo_root: Path) -> dict[str,Any]:
    wid=plan["workflow_id"]
    if wid not in WORKFLOW_REFERENCES: raise ValueError(f"no workflow runtime reference for {wid}")
    ref=WORKFLOW_REFERENCES[wid]; runner=repo_root/ref["runner"]
    exists=runner.is_file()
    family=plan["family"]
    observer=FAMILY_OBSERVERS.get(family)
    app_specs=[]
    for asset in plan["fixture_assets"]:
        app=asset["app"]
        if app=="Support": continue
        app_specs.append({"app":app,"fixture_host_path":asset["host_path"],
          "fixture_guest_path":asset["guest_path"],"launch_target":asset["guest_path"],
          "readiness_profile":{"Writer":"libreoffice_writer","Calc":"libreoffice_calc",
            "Browser":"chromium_page","Terminal":"terminal_x11"}.get(app,"unsupported")})
    return {"workflow_id":wid,"legacy_reference":ref,"legacy_runner_exists":exists,
      "app_setup_specs":app_specs,"observer_id":observer,
      "observer_implementation_registered":False,
      "parameterization_status":"INSTANCE_PLAN_BOUND_LEGACY_RUNNER_STATIC",
      "runtime_adapter_status":"CONFIG_COMPILED_EXACT_EXECUTION_BINDING_INCOMPLETE",
      "required_observers":[observer] if observer else [],
      "missing_components":["workflow_setup_binding","exact_hidden_state_observer"] +
        (["legacy_anchor_equivalence_adapter"] if wid in LEGACY_ANCHORS else []),
      "validation_level":plan["validation_level"],
      "topologies":list(plan["topologies"]),"scheduler_policy_id":plan["topologies"]["ma_sd"]["schedule_policy_id"],
      "reset_binding":plan["reset_binding"],"evaluator_binding":plan["evaluator_binding"],
      "ownership":plan["ownership"],"artifacts":plan["artifact_contract"]}
