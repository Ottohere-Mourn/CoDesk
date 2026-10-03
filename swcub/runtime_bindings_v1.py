"""Auditable workflow-to-legacy-runtime reference map and compile-time binding catalog."""
from __future__ import annotations
from pathlib import Path
import json
from typing import Any, Sequence

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
      "observer_implementation_registered":wid in concrete_observer_ids(),
      "parameterization_status":("INSTANCE_SPEC_RUNTIME_BOUND" if wid in concrete_runtime_binding_ids()
                                  else "INSTANCE_PLAN_BOUND_LEGACY_RUNNER_STATIC"),
      "runtime_adapter_status":"INSTANCE_SPEC_RUNTIME_BOUND" if wid in concrete_runtime_binding_ids()
                                  else "CONFIG_COMPILED_EXACT_EXECUTION_BINDING_INCOMPLETE",
      "required_observers":required_observers_for(wid),
      "concrete_binding_refs": (concrete_binding_refs(wid)),
      "missing_components":(
        ([] if wid in concrete_runtime_binding_ids() else ["workflow_setup_binding"]) +
        ([] if wid in concrete_observer_ids() else ["exact_hidden_state_observer"]) +
        (["legacy_anchor_equivalence_adapter"] if wid in LEGACY_ANCHORS and wid not in {"F-01","F-04","F-02","C-01","C-02","C-03","A-01","A-02","S-01","U-01"} else [])),
      "validation_level":plan["validation_level"],
      "topologies":list(plan["topologies"]),"scheduler_policy_id":plan["topologies"]["ma_sd"]["schedule_policy_id"],
      "reset_binding":plan["reset_binding"],"evaluator_binding":plan["evaluator_binding"],
      "ownership":plan["ownership"],"artifacts":plan["artifact_contract"]}


# Concrete per-workflow runtime bindings. The first migrated binding consumes
# the fixed F-N1 InstanceSpec fixture/goal/target fields directly. Remaining IDs
# stay fail-closed until their own runner and equivalence tests are migrated.
import xml.etree.ElementTree as _ET


def concrete_runtime_binding_ids() -> set[str]:
    return {"F-01", "F-04", "F-02", "C-01", "C-03", "C-02", "A-01", "A-02", "A-N1", "S-01", "S-N1", "U-01", "U-N1", "F-N1", "C-N1"}


def concrete_observer_ids() -> set[str]:
    return {"F-01", "F-04", "F-02", "C-01", "C-03", "C-02", "A-01", "A-02", "A-N1", "S-01", "S-N1", "U-01", "U-N1", "F-N1", "C-N1"}


def required_observers_for(workflow_id: str) -> list[str]:
    if workflow_id == "A-01":
        return ["chromium_top_level_window_identity_v1", "browser_active_tab_and_submission_v1", "browser_context_event_log_v1"]
    if workflow_id == "A-02":
        return ["chromium_top_level_window_identity_v1", "browser_selected_record_revision_v1", "browser_record_event_log_v1"]
    if workflow_id == "S-01":
        return ["uno_active_cell_selection_v1", "calc_target_cell_state_v1", "foreground_window_v1"]
    if workflow_id == "S-N1":
        return ["uno_text_range_selection_v1", "writer_span_style_state_v1", "writer_guard_integrity_v1"]
    if workflow_id == "U-01":
        return ["calc_undo_history_v1", "calc_target_cell_state_v1", "scheduler_action_history_v1"]
    if workflow_id == "U-N1":
        return ["writer_undo_history_v1", "writer_paragraph_state_v1", "scheduler_action_history_v1"]
    if workflow_id == "A-N1":
        return ["chromium_top_level_window_identity_v1", "browser_active_route_revision_v1", "browser_route_event_log_v1"]
    if workflow_id == "F-N1":
        return ["foreground_window_document_identity_v1", "writer_document_content_v1"]
    if workflow_id == "F-01":
        return ["writer_full_document_content_v1", "calc_target_cell_v1"]
    if workflow_id == "F-04":
        return ["calc_target_range_v1", "writer_target_paragraph_v1", "foreground_window_v1"]
    if workflow_id == "C-01":
        return ["x11_clipboard_payload_generation_v1", "writer_paragraph_and_calc_cell_v1", "foreground_window_v1"]
    if workflow_id == "C-02":
        return ["x11_clipboard_payload_generation_v1", "writer_hyperlink_href_v1", "browser_submission_revision_v1"]
    if workflow_id == "C-03":
        return ["x11_clipboard_payload_generation_v1", "calc_source_and_destination_ranges_v1", "writer_paragraph_copy_target_v1"]
    if workflow_id == "C-N1":
        return ["x11_clipboard_mime_payload_digest_v1", "writer_structured_table_oracle_v1", "browser_url_submission_v1"]
    if workflow_id == "F-02":
        return ["writer_comment_anchor_body_v1", "browser_case_decision_revision_v1", "foreground_window_v1"]
    observer = FAMILY_OBSERVERS.get(WORKFLOW_REFERENCES[workflow_id].get("family", ""))
    return [observer] if observer else []


def _writer_paragraphs(raw: bytes | str) -> list[str]:
    root = _ET.fromstring(raw)
    ns = "urn:oasis:names:tc:opendocument:xmlns:text:1.0"
    return ["".join(node.itertext()) for node in root.iter(f"{{{ns}}}p")]


def _replace_exact_paragraph(raw: bytes, initial: str, final: str) -> list[str]:
    paragraphs = _writer_paragraphs(raw)
    found = False
    result = []
    for value in paragraphs:
        if value == initial and not found:
            result.append(final); found = True
        else:
            result.append(value)
    if not found:
        raise ValueError(f"target Writer paragraph not found: {initial!r}")
    return result


class F_N1RuntimeObserver:
    """Read-only, InstanceSpec-driven Writer document observer for F-N1."""
    def __init__(self):
        self.observer_ids = ("foreground_window_document_identity_v1",
                             "writer_document_content_v1")

    @staticmethod
    def _asset_paths(plan: dict[str, Any]) -> dict[str, str]:
        rows = {Path(row["guest_path"]).name: row["guest_path"]
                for row in plan["fixture_assets"] if row["guest_path"].endswith(".fodt")}
        if set(rows) != {"doc-a.fodt", "doc-b.fodt"}:
            raise ValueError(f"F-N1 requires two path-bound Writer fixtures, got {sorted(rows)}")
        return {"doc-a": rows["doc-a.fodt"], "doc-b": rows["doc-b.fodt"]}

    @staticmethod
    def _read(guest: Any, backend: Any, path: str) -> bytes:
        return backend._command(guest, ["cat", path]).encode("utf-8")

    def verify_initial(self, guests: Sequence[Any], plan: dict[str, Any], backend: Any) -> bool:
        paths = self._asset_paths(plan)
        if any(not any(row.get("guest_path") == path and row.get("app") == "Writer"
                       for row in plan["fixture_assets"]) for path in paths.values()):
            return False
        for guest in guests:
            for path in paths.values():
                seeded = guest.fixtures.get(path)
                if seeded is None or _writer_paragraphs(self._read(guest, backend, path)) != _writer_paragraphs(seeded):
                    return False
        return True

    def __call__(self, guests: Sequence[Any], plan: dict[str, Any], backend: Any) -> dict[str, Any]:
        if not guests:
            raise ValueError("F-N1 observer needs at least one Guest")
        paths = self._asset_paths(plan)
        actors = plan["actors"]
        if [row["actor_id"] for row in actors] != ["A", "B"]:
            raise ValueError("F-N1 actor order/identity must be A then B")
        target_doc = {}
        for row in actors:
            joined = " ".join(row["target_objects"])
            doc_id = "doc-a" if "doc-a" in joined else "doc-b" if "doc-b" in joined else None
            if doc_id is None or doc_id in target_doc:
                raise ValueError(f"F-N1 target must bind one distinct document per Actor: {joined!r}")
            target_doc[row["actor_id"]] = doc_id
        guest_for = {row["actor_id"]: guests[i] if len(guests) > 1 else guests[0]
                     for i, row in enumerate(actors)}
        initial_by_doc = {}
        actual_by_guest = {}
        for guest in guests:
            initial_by_doc[id(guest)] = {doc: _writer_paragraphs(guest.fixtures[path])
                                          for doc, path in paths.items()}
            actual_by_guest[id(guest)] = {doc: _writer_paragraphs(self._read(guest, backend, path))
                                           for doc, path in paths.items()}
        actor_state = {}
        intact = True
        for row in actors:
            aid = row["actor_id"]; doc = target_doc[aid]; guest = guest_for[aid]
            initial_value = row["initial_value"]; expected_value = row["expected_value"]
            actual_paragraphs = actual_by_guest[id(guest)][doc]
            if expected_value in actual_paragraphs:
                value = expected_value
            elif initial_value in actual_paragraphs:
                value = initial_value
            else:
                value = "\n".join(actual_paragraphs)
            actor_state[aid] = {"object": row["target_objects"][0], "value": value}
            # A guest's two documents may contain only seeded state or their
            # assigned goal edit; every non-target paragraph must remain exact.
            for other_doc in paths:
                seed = initial_by_doc[id(guest)][other_doc]
                owner_actor = "A" if other_doc == "doc-a" else "B"
                owner = next(item for item in actors if item["actor_id"] == owner_actor)
                owner_expected = _replace_exact_paragraph(
                    guest.fixtures[paths[other_doc]], owner["initial_value"],
                    owner["expected_value"])
                allowed = {tuple(seed), tuple(owner_expected)}
                if tuple(actual_by_guest[id(guest)][other_doc]) not in allowed:
                    intact = False
        guard_state = "PRESERVE" if intact else "CONTAMINATED"
        for guest in guests:
            title = str(guest.episode._active_window_title())
            backend.notify_observer_event({"kind": "workflow_observation",
                "workflow_id": "F-N1", "observer": "foreground_window_document_identity_v1",
                "guest_slot": guest.slot, "active_window": title})
        return {"actors": {**actor_state, "guards": {"main": guard_state}}}


def _setup_f_n1(plan: dict[str, Any], guest: Any, backend: Any) -> None:
    paths = F_N1RuntimeObserver._asset_paths(plan)
    launched = {row.get("target") for row in guest.launched if row.get("app") == "Writer"}
    if not set(paths.values()) <= launched:
        raise RuntimeError("F-N1 readiness requires both fixture-bound Writer documents to be launched")
    titles = backend._command(guest, ["bash", "-lc",
        "for id in $(xdotool search --class soffice 2>/dev/null); do "
        "xdotool getwindowname $id; done"]).splitlines()
    if not all(Path(path).stem.lower() in "\n".join(titles).lower()
               for path in paths.values()):
        raise RuntimeError(f"F-N1 document-window identity check failed: {titles}")
    observation = guest.episode.refresh_observation("f_n1_workflow_readiness")
    if not observation.get("screenshot"):
        raise RuntimeError("F-N1 readiness did not return a nonempty desktop screenshot")
    if not F_N1RuntimeObserver().verify_initial([guest], plan, backend):
        raise RuntimeError("F-N1 exact Writer initial-state verification failed")
    guest.episode.log.record("task_setup", "readiness", "f_n1.two_writer_documents_ready",
        {}, {"document_paths": paths, "window_titles": titles,
             "screenshot_available": True},
        details={"observer_ids": ["foreground_window_document_identity_v1",
                                  "writer_document_content_v1"]})


def _event_gate_f_n1(plan: dict[str, Any], run: dict[str, Any]):
    from .runtime_execution_v1 import EventGate
    if run["topology"] not in {"ma_sd", "ma_id"}:
        return None
    return EventGate([{"kind": "action_complete", "actor_id": "A"},
                      {"kind": "action_complete", "actor_id": "B"},
                      {"kind": "action_complete", "actor_id": "A"}])


class _ODFRuntimeObserver:
    def __init__(self, workflow_id: str):
        self.workflow_id = workflow_id
        self.observer_ids = tuple(required_observers_for(workflow_id))

    @staticmethod
    def _assets(plan):
        return {row["app"]: row for row in plan["fixture_assets"] if row["app"] in {"Writer", "Calc"}}

    @staticmethod
    def _read(guest, backend, path):
        return backend._command(guest, ["cat", path]).encode("utf-8")

    @staticmethod
    def _grid(raw):
        root = _ET.fromstring(raw)
        ns_t = "urn:oasis:names:tc:opendocument:xmlns:table:1.0"
        ns_o = "urn:oasis:names:tc:opendocument:xmlns:office:1.0"
        ns_x = "urn:oasis:names:tc:opendocument:xmlns:text:1.0"
        grid = {}
        for ri, row in enumerate(root.iter(f"{{{ns_t}}}table-row")):
            ci = 0
            for cell in list(row):
                if cell.tag not in {f"{{{ns_t}}}table-cell", f"{{{ns_t}}}covered-table-cell"}:
                    continue
                col_rep = int(cell.get(f"{{{ns_t}}}number-columns-repeated", "1"))
                row_rep = int(row.get(f"{{{ns_t}}}number-rows-repeated", "1"))
                value = cell.get(f"{{{ns_o}}}string-value")
                if value is None:
                    value = "".join("".join(x.itertext()) for x in cell.findall(f".//{{{ns_x}}}p"))
                for rr in range(row_rep):
                    for cc in range(col_rep):
                        grid[(ri+rr,ci+cc)] = value
                ci += col_rep
        return grid

    @staticmethod
    def _cell(cell):
        from .production_v1 import _cell_coord
        return _cell_coord(cell)

    @staticmethod
    def _range(target):
        from .production_v1 import _range_cells
        return [_ODFRuntimeObserver._cell(x) for x in _range_cells(target)]

    @staticmethod
    def _writer_target(paras, actor):
        target = actor["target_objects"][0]
        if target == "writer/document-content":
            return "\n".join(paras)
        initial = actor["initial_value"]
        return initial if initial in paras else "\n".join(paras)

    def verify_initial(self, guests, plan, backend):
        assets = self._assets(plan)
        if set(assets) != set(plan["required_apps"]):
            return False
        actors = plan["actors"]
        expected_files = {r["guest_path"]: r["sha256"] for r in plan["fixture_assets"]}
        for guest in guests:
            if set(guest.fixtures) != set(expected_files):
                return False
            for actor in actors:
                app = actor["task_domain"]
                path = assets[app]["guest_path"]
                raw = self._read(guest, backend, path)
                seeded = guest.fixtures[path]
                if app == "Writer":
                    if _writer_paragraphs(raw) != _writer_paragraphs(seeded):
                        return False
                elif self._grid(raw) != self._grid(seeded):
                    return False
            for app, row in assets.items():
                launched = any(x.get("app") == app and x.get("target") == row["guest_path"]
                               for x in guest.launched)
                if not launched:
                    return False
        if self.workflow_id=="C-03":
            calc_asset=assets["Calc"]["guest_path"];writer_asset=assets["Writer"]["guest_path"]
            a,b=actors
            for guest in guests:
                paras=_writer_paragraphs(self._read(guest,backend,writer_asset))
                if len(paras)<2 or paras[0]!="NOTE-571" or paras[1]!="":return False
                grid=self._grid(self._read(guest,backend,calc_asset))
                source=grid.get((0,0)),grid.get((0,1)),grid.get((1,0)),grid.get((1,1))
                if source!=("Q1","Q2","17","29"):return False
                dest=self._range(a["target_objects"][0].split("/",1)[1])
                if any(grid.get(rc,"") not in ("",None) for rc in dest):return False
        if self.workflow_id=="C-01":
            writer_asset=assets["Writer"]["guest_path"]
            calc_asset=assets["Calc"]["guest_path"]
            a,b=plan["actors"]
            for guest in guests:
                paras=_writer_paragraphs(self._read(guest,backend,writer_asset))
                grid=self._grid(self._read(guest,backend,calc_asset))
                target=self._range(b["target_objects"][0].split("/",1)[1])[0]
                target_index=int(a["target_objects"][0].split("[",1)[1].split("]",1)[0])
                source_index=target_index-1
                if len(paras)<=target_index or paras[source_index]!=a["expected_value"]:
                    return False
                if paras[target_index]!=a["initial_value"] or grid.get((0,0))!=b["expected_value"] or grid.get(target,"")!="":
                    return False
        return True

    def __call__(self, guests, plan, backend):
        assets = self._assets(plan)
        actors = plan["actors"]
        if len(actors) != 2:
            raise ValueError(f"{self.workflow_id} requires actors A/B")
        guest_for = {a["actor_id"]: guests[i] if len(guests)>1 else guests[0]
                     for i,a in enumerate(actors)}
        state = {}
        intact = True
        for actor in actors:
            aid = actor["actor_id"]; guest = guest_for[aid]; app = actor["task_domain"]
            path = assets[app]["guest_path"]
            raw = self._read(guest, backend, path)
            seed = guest.fixtures[path]
            target = actor["target_objects"][0].removeprefix("writer/").removeprefix("calc/")
            if app == "Writer":
                paras = _writer_paragraphs(raw); seed_paras = _writer_paragraphs(seed)
                if target == "document-content":
                    value = "\n".join(paras)
                    intact &= len(paras) == 1
                elif target.startswith("paragraph["):
                    index=int(target[len("paragraph["):].split("]",1)[0])
                    actual_value=paras[index] if index<len(paras) else None
                    value=actor["expected_value"] if actual_value==actor["expected_value"] else (
                        actor["initial_value"] if actual_value==actor["initial_value"] else str(actual_value))
                    allowed_indices={index}
                    if len(guests)==1:
                        allowed_indices={int(row["target_objects"][0].removeprefix("writer/" )[len("paragraph["):].split("]",1)[0])
                            for row in actors if row["task_domain"]=="Writer" and row["target_objects"][0].removeprefix("writer/").startswith("paragraph[")}
                    intact &= len(seed_paras)==len(paras) and all(
                        i in allowed_indices or seed_paras[i]==paras[i] for i in range(min(len(seed_paras),len(paras))))
                    if self.workflow_id=="C-01":
                        source_index=index-1
                        intact &= len(paras)>index and paras[source_index]==seed_paras[source_index]
                else:
                    value = actor["expected_value"] if actor["expected_value"] in paras else (
                        actor["initial_value"] if actor["initial_value"] in paras else "\n".join(paras))
                    changed = [i for i,(x,y) in enumerate(zip(seed_paras,paras)) if x != y]
                    intact &= len(seed_paras)==len(paras) and len(changed)<=1 and (
                        not changed or seed_paras[changed[0]] == actor["initial_value"])
                obj = actor["target_objects"][0]
            else:
                grid = self._grid(raw); seed_grid = self._grid(seed)
                cells = self._range(target)
                values = [grid.get(rc,"") for rc in cells]
                seed_values = [seed_grid.get(rc,"") for rc in cells]
                try:
                    expected_values = __import__("json").loads(actor["expected_value"])
                except Exception:
                    expected_values = actor["expected_value"]
                coordinates=self._range(target)
                row_count=max(r for r,_ in coordinates)-min(r for r,_ in coordinates)+1
                col_count=max(c for _,c in coordinates)-min(c for _,c in coordinates)+1
                rows=[values[i:i+col_count] for i in range(0,len(values),col_count)]
                if len(rows)!=row_count or any(len(row)!=col_count for row in rows):
                    raise RuntimeError(f"{self.workflow_id} target range is not a rectangular matrix: {target}")
                if isinstance(expected_values,list):
                    value = actor["expected_value"] if rows == expected_values else (
                        actor["initial_value"] if all(x in ("",None) for x in values) else
                        __import__("json").dumps(rows,separators=(",",":")))
                else:
                    value = actor["expected_value"] if all(x == expected_values for x in values) else (
                        actor["initial_value"] if all(x == actor["initial_value"] for x in values) else "\n".join(values))
                changed = {k for k in set(grid)|set(seed_grid) if grid.get(k,"") != seed_grid.get(k,"")}
                if len(guests)==1:
                    allowed = set().union(*(set(self._range(row["target_objects"][0].removeprefix("calc/")))
                        for row in actors if row["task_domain"]=="Calc"))
                else:
                    allowed = set(cells)
                intact &= changed <= allowed
                obj = actor["target_objects"][0]
            state[aid] = {"object": obj, "value": value}
        for guest in guests:
            title = str(guest.episode._active_window_title())
            backend.notify_observer_event({"kind":"workflow_observation","workflow_id":self.workflow_id,
                "observer":self.observer_ids[0] if self.observer_ids else "odf_state_v1",
                "guest_slot":guest.slot,"active_window":title})
        if len(guests)>1:
            for i,guest in enumerate(guests):
                assigned=actors[i]
                for other in actors:
                    if other["task_domain"]==assigned["task_domain"]:
                        continue
                    row=assets[other["task_domain"]]
                    raw=self._read(guest,backend,row["guest_path"])
                    seed=guest.fixtures[row["guest_path"]]
                    if other["task_domain"]=="Writer":
                        intact &= _writer_paragraphs(raw)==_writer_paragraphs(seed)
                    else:
                        intact &= self._grid(raw)==self._grid(seed)
        state["guards"] = {"main":"PRESERVE" if intact else "CONTAMINATED"}
        return {"actors":state}

    def verify_initial_values(self, guests, plan, backend):
        return self.verify_initial(guests,plan,backend)


class CN1RuntimeObserver:
    """Exact rich-table structure and independent Browser URL submission observer."""
    observer_ids=tuple(required_observers_for("C-N1"))
    @staticmethod
    def _apps(plan):
        return {row["app"]:row for row in plan["fixture_assets"] if row["app"] in {"Writer","Browser"}}
    @staticmethod
    def _support(plan):
        return {Path(row["guest_path"]).name:row["guest_path"] for row in plan["fixture_assets"] if row["app"]=="Support"}
    @staticmethod
    def _read(guest,backend,path):return backend._command(guest,["cat",path]).encode()
    @staticmethod
    def _outside_paragraphs(raw):
        root=_ET.fromstring(raw);tns="urn:oasis:names:tc:opendocument:xmlns:table:1.0";xns="urn:oasis:names:tc:opendocument:xmlns:text:1.0"
        inside={id(p) for table in root.iter(f"{{{tns}}}table") for p in table.iter(f"{{{xns}}}p")}
        return ["".join(p.itertext()) for p in root.iter(f"{{{xns}}}p") if id(p) not in inside]
    @staticmethod
    def _table(raw):
        root=_ET.fromstring(raw);tns="urn:oasis:names:tc:opendocument:xmlns:table:1.0";xns="urn:oasis:names:tc:opendocument:xmlns:text:1.0"
        tables=list(root.iter(f"{{{tns}}}table"));table=next((x for x in tables if x.get(f"{{{tns}}}name")=="CoDeskDestination"),tables[0] if tables else None)
        if table is None:return []
        result=[]
        for row in table.findall(f"{{{tns}}}table-row"):
            cells=[]
            for cell in row:
                if cell.tag not in {f"{{{tns}}}table-cell",f"{{{tns}}}covered-table-cell"}:continue
                cells.append("".join("".join(p.itertext()) for p in cell.findall(f".//{{{xns}}}p")))
            if cells:result.append(cells)
        return result
    def verify_initial(self,guests,plan,backend):
        try:
            apps=self._apps(plan);support=self._support(plan)
            if set(apps)!={"Writer","Browser"} or "browser-initial-state.json" not in support:return False
            goals={x["actor_id"]:x for x in plan["actors"]};expected=json.loads(goals["A"]["expected_value"])
            for guest in guests:
                writer=self._read(guest,backend,apps["Writer"]["guest_path"]);browser=self._read(guest,backend,apps["Browser"]["guest_path"]).decode()
                shape=(len(expected),len(expected[0]));table=self._table(writer)
                if len(table)!=shape[0] or any(len(row)!=shape[1] for row in table) or any(v for row in table for v in row):return False
                if "source-table" not in browser or "text/html" not in str(plan["initial_gui_state"]["semantic_parameters"]["object_schema"].get("mime",[])):return False
                if any(value not in browser for row in expected for value in row):return False
                state=json.loads(self._read(guest,backend,support["browser-initial-state.json"]))
                if state.get("revision")!=0 or state.get("submission")!={}:return False
                for app in ("Writer","Browser"):
                    if not any(x.get("app")==app for x in guest.launched):return False
            return True
        except Exception:return False
    def __call__(self,guests,plan,backend):
        apps=self._apps(plan);support=self._support(plan);actors={x["actor_id"]:x for x in plan["actors"]}
        guest_for={a:guests[i] if len(guests)>1 else guests[0] for i,a in enumerate(("A","B"))}
        expected_table=json.loads(actors["A"]["expected_value"]);out={};intact=True;clipboard=[]
        for aid,guest in guest_for.items():
            raw=self._read(guest,backend,apps["Writer"]["guest_path"]);table=self._table(raw);seed_table=self._table(guest.fixtures[apps["Writer"]["guest_path"]])
            paras=self._outside_paragraphs(raw);seed_paras=self._outside_paragraphs(guest.fixtures[apps["Writer"]["guest_path"]])
            if aid=="A":
                val=actors["A"]["expected_value"] if table==expected_table else actors["A"]["initial_value"] if table==seed_table else json.dumps(table,separators=(",",":"),ensure_ascii=False)
                out["A"]={"object":actors["A"]["target_objects"][0],"value":val}
            else:
                if table!=seed_table:out["A"]={"object":actors["A"]["target_objects"][0],"value":json.dumps(table,separators=(",",":"),ensure_ascii=False)}
            intact &= table in (seed_table,expected_table) and paras==seed_paras
            state=json.loads(self._read(guest,backend,support["browser-initial-state.json"]))
            events_raw=self._read(guest,backend,support.get("browser-events.jsonl","")).decode() if "browser-events.jsonl" in support else ""
            submissions=[json.loads(x) for x in events_raw.splitlines() if x.strip()]
            revision=state.get("revision",0);url=state.get("submission",{}).get("url","")
            if aid=="B":
                bval=actors["B"]["expected_value"] if revision==1 and url==actors["B"]["expected_value"] else actors["B"]["initial_value"] if revision==0 else url
                out["B"]={"object":actors["B"]["target_objects"][0],"value":bval}
            elif revision:
                out["B"]={"object":actors["B"]["target_objects"][0],"value":url if revision!=1 or url!=actors["B"]["expected_value"] else actors["B"]["expected_value"]}
            intact &= revision in (0,1) and ((revision==0 and not state.get("submission")) or (revision==1 and url==actors["B"]["expected_value"] and len(submissions)==1))
            sampler=getattr(guest.episode,"clipboard_sampler",None)
            if sampler is not None:
                snap=sampler.sample();clipboard.append({"guest_slot":guest.slot,"snapshot":snap,"hidden_from_actor":True})
                backend.notify_observer_event({"kind":"workflow_observation","workflow_id":"C-N1","observer":"x11_clipboard_mime_payload_digest_v1","snapshot":snap,"hidden_from_actor":True,"read_only":True})
        out.setdefault("A",{"object":actors["A"]["target_objects"][0],"value":actors["A"]["initial_value"]})
        out.setdefault("B",{"object":actors["B"]["target_objects"][0],"value":actors["B"]["initial_value"]})
        out["guards"]={"main":"PRESERVE" if intact else "CONTAMINATED"}
        return {"actors":out,"clipboard_observations":clipboard}


class C02RuntimeObserver:
    observer_ids=("x11_clipboard_payload_generation_v1","writer_hyperlink_href_v1",
                  "browser_submission_revision_v1")
    @staticmethod
    def _assets(plan):
        return {row["app"]:row for row in plan["fixture_assets"] if row["app"] in {"Writer","Browser"}}
    @staticmethod
    def _support(plan):
        return {Path(row["guest_path"]).name:row["guest_path"] for row in plan["fixture_assets"]
                if row["app"]=="Support"}
    @staticmethod
    def _read(guest,backend,path): return backend._command(guest,["cat",path]).encode()
    @staticmethod
    def _href_state(raw,index):
        root=_ET.fromstring(raw)
        text_ns="urn:oasis:names:tc:opendocument:xmlns:text:1.0"
        xlink_ns="http://www.w3.org/1999/xlink"
        body=root.find(".//{urn:oasis:names:tc:opendocument:xmlns:office:1.0}body/{urn:oasis:names:tc:opendocument:xmlns:office:1.0}text")
        paras=[] if body is None else body.findall(f"{{{text_ns}}}p")
        if index>=len(paras): return {"paragraphs":[],"links":[]}
        para=paras[index]
        return {"paragraphs":["".join(p.itertext()) for p in paras],
                "visible_text":"".join(para.itertext()),
                "links":[{"text":"".join(a.itertext()),"href":a.get(f"{{{xlink_ns}}}href")}
                         for a in para.findall(f".//{{{text_ns}}}a")]}
    def verify_initial(self,guests,plan,backend):
        assets=self._assets(plan); support=self._support(plan)
        if set(assets)!={"Writer","Browser"} or "browser-initial-state.json" not in support:return False
        for guest in guests:
            for row in plan["fixture_assets"]:
                if guest.fixtures.get(row["guest_path"]) is None:return False
                if self._read(guest,backend,row["guest_path"])!=guest.fixtures[row["guest_path"]]:return False
            initial=json.loads(self._read(guest,backend,support["browser-initial-state.json"]))
            if initial!={"submission":{},"revision":0}:return False
        return True
    def __call__(self,guests,plan,backend):
        assets=self._assets(plan); support=self._support(plan); actors=plan["actors"]
        guest_for={a["actor_id"]:guests[i] if len(guests)>1 else guests[0] for i,a in enumerate(actors)}
        state={}; intact=True
        for actor in actors:
            aid=actor["actor_id"]; guest=guest_for[aid]
            if aid=="A":
                path=assets["Writer"]["guest_path"]
                target=actor["target_objects"][0]
                index=int(target.split("[",1)[1].split("]",1)[0])
                actual=self._href_state(self._read(guest,backend,path),index)
                links=actual["links"]
                value=actor["expected_value"] if links==[json.loads(actor["expected_value"])] else (
                    actor["initial_value"] if actual["visible_text"]==actor["initial_value"] and not links
                    else __import__("json").dumps({"text":actual["visible_text"],"links":links},sort_keys=True,separators=(",",":")))
                intact &= len(actual["paragraphs"])==2 and (
                    actual["paragraphs"][1-index]=="Guard paragraph" if index in (0,1) else False)
                state[aid]={"object":target,"value":value}
            else:
                raw=json.loads(self._read(guest,backend,support["browser-initial-state.json"]))
                submission=raw.get("submission"); url=actor["expected_value"]
                if submission=={"url":url} and raw.get("revision")==1:value=url
                elif submission=={} and raw.get("revision")==0:value=actor["initial_value"]
                else:value=__import__("json").dumps(raw,sort_keys=True,separators=(",",":"))
                state[aid]={"object":actor["target_objects"][0],"value":value}
                intact &= isinstance(submission,dict) and raw.get("revision") in (0,1)
        if len(guests)>1:
            for i,guest in enumerate(guests):
                assigned=actors[i]
                other_app="Browser" if assigned["task_domain"]=="Writer" else "Writer"
                row=assets[other_app]
                intact &= self._read(guest,backend,row["guest_path"])==guest.fixtures[row["guest_path"]]
                if other_app=="Browser":
                    state_path=support["browser-initial-state.json"]
                    intact &= json.loads(self._read(guest,backend,state_path))=={"submission":{},"revision":0}
        for guest in guests:
            title=str(guest.episode._active_window_title())
            backend.notify_observer_event({"kind":"workflow_observation","workflow_id":"C-02",
                "observer":"browser_submission_revision_v1","guest_slot":guest.slot,
                "active_window":title})
        state["guards"]={"main":"PRESERVE" if intact else "CONTAMINATED"}
        return {"actors":state}


class F02RuntimeObserver:
    observer_ids=("writer_comment_anchor_body_v1","browser_case_decision_revision_v1")
    @staticmethod
    def _assets(plan):
        return {row["app"]:row for row in plan["fixture_assets"] if row["app"] in {"Writer","Browser"}}
    @staticmethod
    def _support(plan):
        return {Path(row["guest_path"]).name:row["guest_path"] for row in plan["fixture_assets"] if row["app"]=="Support"}
    @staticmethod
    def _read(guest,backend,path): return backend._command(guest,["cat",path]).encode()
    def verify_initial(self,guests,plan,backend):
        assets=self._assets(plan); support=self._support(plan)
        if set(assets)!={"Writer","Browser"} or "browser-initial-state.json" not in support:return False
        for guest in guests:
            for row in plan["fixture_assets"]:
                if self._read(guest,backend,row["guest_path"])!=guest.fixtures.get(row["guest_path"]):return False
            if json.loads(self._read(guest,backend,support["browser-initial-state.json"]))!={"submission":{},"revision":0}:return False
            paras=_writer_paragraphs(self._read(guest,backend,assets["Writer"]["guest_path"]))
            if len(paras)!=2 or not any(a["initial_value"] in paras for a in plan["actors"] if a["actor_id"]=="A"):
                return False
        return True
    def __call__(self,guests,plan,backend):
        assets=self._assets(plan); support=self._support(plan); actors=plan["actors"]
        guest_for={a["actor_id"]:guests[i] if len(guests)>1 else guests[0] for i,a in enumerate(actors)}
        state={}; intact=True
        office="urn:oasis:names:tc:opendocument:xmlns:office:1.0"
        text="urn:oasis:names:tc:opendocument:xmlns:text:1.0"
        for actor in actors:
            aid=actor["actor_id"];guest=guest_for[aid]
            if aid=="A":
                writer_raw=self._read(guest,backend,assets["Writer"]["guest_path"])
                root=_ET.fromstring(writer_raw)
                body=root.find(f".//{{{office}}}body/{{{office}}}text")
                nodes=[] if body is None else body.findall(f"{{{text}}}p")
                paras=[]
                for pnode in nodes:
                    visible=pnode.text or ""
                    for child in pnode:
                        if child.tag!=f"{{{office}}}annotation":
                            visible += "".join(child.itertext())
                        visible += child.tail or ""
                    paras.append(visible)
                seed=_writer_paragraphs(guest.fixtures[assets["Writer"]["guest_path"]])
                index=next((i for i,x in enumerate(seed) if x==actor["initial_value"]),None)
                comments=[] if index is None or index>=len(nodes) else nodes[index].findall(f".//{{{office}}}annotation")
                ends=[] if index is None or index>=len(nodes) else nodes[index].findall(f".//{{{office}}}annotation-end")
                comment_rows=[]
                for ann in comments:
                    ps=ann.findall(f".//{{{text}}}p")
                    comment_rows.append({"name":ann.get(f"{{{office}}}name"),
                        "body":"\n".join("".join(p.itertext()) for p in ps)})
                anchor_ok=index is not None and index<len(paras) and paras[index]==actor["initial_value"]
                good=(anchor_ok and len(comment_rows)==1 and comment_rows[0]["body"]==json.loads(actor["expected_value"])["comment"]
                    and comment_rows[0]["name"] in [x.get(f"{{{office}}}name") for x in ends])
                value=actor["expected_value"] if good else actor["initial_value"] if anchor_ok and not comments else json.dumps({"paragraphs":paras,"comments":comment_rows},sort_keys=True,separators=(",",":"))
                intact &= len(paras)==len(seed) and all(paras[i]==seed[i] for i in range(len(seed)))
                state[aid]={"object":actor["target_objects"][0],"value":value}
            else:
                raw=json.loads(self._read(guest,backend,support["browser-initial-state.json"]))
                expected=json.loads(actor["expected_value"])
                if raw.get("submission")==expected and raw.get("revision")==1:value=actor["expected_value"]
                elif raw.get("submission")=={} and raw.get("revision")==0:value=actor["initial_value"]
                else:value=json.dumps(raw,sort_keys=True,separators=(",",":"))
                intact &= isinstance(raw.get("submission"),dict) and raw.get("revision") in (0,1)
                state[aid]={"object":actor["target_objects"][0],"value":value}
        if len(guests)>1:
            for i,guest in enumerate(guests):
                assigned=actors[i]
                other="Browser" if assigned["task_domain"]=="Writer" else "Writer"
                row=assets[other]
                intact &= self._read(guest,backend,row["guest_path"])==guest.fixtures[row["guest_path"]]
                if other=="Browser":intact &= json.loads(self._read(guest,backend,support["browser-initial-state.json"]))=={"submission":{},"revision":0}
        state["guards"]={"main":"PRESERVE" if intact else "CONTAMINATED"}
        return {"actors":state}


class C01RuntimeObserver(_ODFRuntimeObserver):
    def __init__(self): super().__init__("C-01")
class C03RuntimeObserver(_ODFRuntimeObserver):
    def __init__(self): super().__init__("C-03")



class S01RuntimeObserver(_ODFRuntimeObserver):
    def __init__(self):
        super().__init__("S-01")
        self.observer_ids=tuple(required_observers_for("S-01"))
    def __call__(self,guests,plan,backend):
        result=super().__call__(guests,plan,backend)
        probe=("import json,uno; c=uno.getComponentContext(); r=c.ServiceManager.createInstanceWithContext('com.sun.star.bridge.UnoUrlResolver',c); "
               "x=r.resolve('uno:socket,host=localhost,port=2002;urp;StarOffice.ComponentContext'); "
               "d=x.ServiceManager.createInstanceWithContext('com.sun.star.frame.Desktop',x); "
               "a=d.getCurrentComponent().getCurrentSelection().getRangeAddress(); "
               "print(json.dumps({'sheet':a.Sheet,'start_column':a.StartColumn,'start_row':a.StartRow,'end_column':a.EndColumn,'end_row':a.EndRow}))")
        for guest in guests:
            raw=backend._command(guest,["python3","-c",probe])
            try:selection=json.loads(raw.splitlines()[-1])
            except Exception as exc:raise RuntimeError(f"S-01 UNO selection observer failed: {raw}") from exc
            backend.notify_observer_event({"kind":"workflow_observation","workflow_id":"S-01",
                "observer":"uno_active_cell_selection_v1","guest_slot":guest.slot,"selection":selection,
                "hidden_from_actor":True,"read_only":True})
        return result


class F01RuntimeObserver(_ODFRuntimeObserver):
    def __init__(self): super().__init__("F-01")


class F04RuntimeObserver(_ODFRuntimeObserver):
    def __init__(self): super().__init__("F-04")



def _setup_s01(plan,guest,backend):
    _setup_odf(plan,guest,backend,"S-01")
    probe=backend._command(guest,["python3","-c","import uno; print('UNO_READY')"])
    if "UNO_READY" not in probe:raise RuntimeError("S-01 UNO observer dependency unavailable")
    observer=S01RuntimeObserver()
    observer([guest],plan,backend)
    guest.episode.log.record("task_setup","readiness","s01_uno_selection_ready",{},
        {"available":True},details={"observer_ids":list(observer.observer_ids)})


def _setup_odf(plan, guest, backend, workflow_id):
    observer = {"F-01": F01RuntimeObserver, "F-04": F04RuntimeObserver, "S-01": S01RuntimeObserver, "U-01": U01RuntimeObserver, "U-N1": UN1RuntimeObserver,
        "C-03": C03RuntimeObserver}[workflow_id]()
    if not observer.verify_initial([guest],plan,backend):
        raise RuntimeError(f"{workflow_id} exact ODF initial-state verification failed")
    titles = backend._command(guest,["bash","-lc",
        "for id in $(xdotool search --class soffice 2>/dev/null); do xdotool getwindowname $id; done"])
    combined=titles.lower()
    if not titles.strip():
        raise RuntimeError(f"{workflow_id} has no active LibreOffice document window")
    for app, row in observer._assets(plan).items():
        if Path(row["guest_path"]).stem.lower() not in combined:
            raise RuntimeError(f"{workflow_id} {app} document identity absent from live window titles: {titles}")
    shot = guest.episode.refresh_observation(f"{workflow_id.lower()}_readiness")
    if not shot.get("screenshot"):
        raise RuntimeError(f"{workflow_id} readiness screenshot missing")
    guest.episode.log.record("task_setup","readiness",f"{workflow_id.lower()}.odf_ready",{},
        {"applications":list(observer._assets(plan)),"screenshot_available":True},
        details={"observer_ids":list(observer.observer_ids)})
    return None


def _setup_f01(plan,guest,backend): return _setup_odf(plan,guest,backend,"F-01")
def _setup_f04(plan,guest,backend): return _setup_odf(plan,guest,backend,"F-04")
def _setup_c01(plan,guest,backend):
    result=_setup_odf(plan,guest,backend,"C-01")
    if True:
        from pathlib import Path
        from .clipboard_observer import GuestCommandClipboardSampler, install_guest_probe
        repo=Path(__file__).resolve().parents[1]
        probe,state=install_guest_probe(lambda argv: backend._command(guest,argv),
            repo/"scripts/guest_clipboard_probe.py",plan["run_id"]+"-"+guest.slot)
        sampler=GuestCommandClipboardSampler(lambda argv:backend._command(guest,argv),
            probe_path=probe,state_path=state)
        guest.episode.attach_clipboard_sampler(sampler,required=True)
        first=sampler.sample()
        if not first: raise RuntimeError("C-01 clipboard observer returned no initial sample")
    observer=C01RuntimeObserver()
    if not observer.verify_initial([guest],plan,backend):
        raise RuntimeError("C-01 exact Writer/Calc source and destination readiness failed")
    return result


def _setup_c03(plan,guest,backend):
    result=_setup_odf(plan,guest,backend,"C-03")
    from pathlib import Path
    from .clipboard_observer import GuestCommandClipboardSampler,install_guest_probe
    repo=Path(__file__).resolve().parents[1]
    probe,state=install_guest_probe(lambda argv:backend._command(guest,argv),
        repo/"scripts/guest_clipboard_probe.py",plan["run_id"]+"-"+guest.slot)
    sampler=GuestCommandClipboardSampler(lambda argv:backend._command(guest,argv),probe_path=probe,state_path=state)
    guest.episode.attach_clipboard_sampler(sampler,required=True)
    if not sampler.sample():raise RuntimeError("C-03 read-only clipboard observer returned no initial sample")
    observer=C03RuntimeObserver()
    if not observer.verify_initial([guest],plan,backend):raise RuntimeError("C-03 historical Calc/Writer fixture validation failed")
    return result


def _cn1_server_source(html,state,events):
    return f'''from http.server import BaseHTTPRequestHandler,HTTPServer
from pathlib import Path
from datetime import datetime,timezone
import json
HTML=Path({html!r});STATE=Path({state!r});EVENTS=Path({events!r})
def event(x):
 x["utc"]=datetime.now(timezone.utc).isoformat()
 with EVENTS.open("a") as f:f.write(json.dumps(x,sort_keys=True)+"\\n")
class H(BaseHTTPRequestHandler):
 def reply(self,x,status=200):
  b=json.dumps(x).encode();self.send_response(status);self.send_header("Content-Type","application/json");self.send_header("Content-Length",str(len(b)));self.end_headers();self.wfile.write(b)
 def do_GET(self):
  if self.path=="/health":return self.reply({{"ok":True}})
  if self.path!="/workspace":return self.reply({{"error":"not found"}},404)
  b=HTML.read_bytes();self.send_response(200);self.send_header("Content-Type","text/html; charset=utf-8");self.send_header("Content-Length",str(len(b)));self.end_headers();self.wfile.write(b)
 def do_POST(self):
  if self.path!="/submit":return self.reply({{"error":"not found"}},404)
  p=json.loads(self.rfile.read(int(self.headers.get("Content-Length","0"))));s=json.loads(STATE.read_text())
  if p.get("url")!=s.get("expected_url"):return self.reply({{"error":"wrong url"}},409)
  s["submission"]={{"url":p["url"]}};s["revision"]+=1;STATE.write_text(json.dumps(s,sort_keys=True));event({{"kind":"url_submitted","revision":s["revision"]}});return self.reply({{"ok":True}})
 def log_message(self,*args):pass
HTTPServer(("127.0.0.1",8771),H).serve_forever()
'''


def _setup_cn1(plan,guest,backend):
    import base64,shlex,time
    from pathlib import Path
    from .clipboard_observer import GuestCommandClipboardSampler,install_guest_probe
    observer=CN1RuntimeObserver();apps=observer._apps(plan);support=observer._support(plan)
    if not observer.verify_initial([guest],plan,backend):raise RuntimeError("C-N1 exact empty Writer table / Browser rich source readiness failed")
    html=apps["Browser"]["guest_path"];state=support["browser-initial-state.json"];events=support.get("browser-events.jsonl")
    server=html.rsplit("/",1)[0]+"/codesk-cn1-server.py"
    src=_cn1_server_source(html,state,events)
    b64=base64.b64encode(src.encode()).decode();writer="from pathlib import Path;import base64;p=Path("+repr(server)+");p.write_bytes(base64.b64decode("+repr(b64)+"))"
    backend._command(guest,["python3","-c",writer]);backend._command(guest,["bash","-lc",f"nohup python3 {shlex.quote(server)} >/tmp/codesk-cn1-server.log 2>&1 </dev/null &"])
    deadline=time.monotonic()+10;health=""
    while time.monotonic()<deadline:
        health=backend._command(guest,["bash","-lc","curl -fsS --max-time 1 http://127.0.0.1:8771/health || true"])
        if '"ok"' in health:break
        time.sleep(.25)
    if '"ok"' not in health:raise RuntimeError(f"C-N1 Browser server readiness failed: {health}")
    url="http://127.0.0.1:8771/workspace"
    command=("wid=$(xdotool search --class chromium 2>/dev/null | head -1); test -n \"$wid\" && xdotool windowactivate --sync \"$wid\" && xdotool key --window \"$wid\" ctrl+l && xdotool type --window \"$wid\" "+shlex.quote(url)+" && xdotool key --window \"$wid\" Return; sleep 2")
    backend._command(guest,["bash","-lc",command]);shot=guest.episode.refresh_observation("cn1_browser_writer_readiness")
    title=str(guest.episode._active_window_title())
    if not shot.get("screenshot") or "Chromium" not in title:raise RuntimeError("C-N1 Browser screenshot/navigation readiness failed")
    writer_titles=backend._command(guest,["bash","-lc","for id in $(xdotool search --class soffice 2>/dev/null); do xdotool getwindowname $id; done"])
    if Path(apps["Writer"]["guest_path"]).stem.lower() not in writer_titles.lower():raise RuntimeError("C-N1 Writer document identity/readiness failed")
    probe,probe_state=install_guest_probe(lambda argv:backend._command(guest,argv),Path(__file__).resolve().parents[1]/"scripts/guest_clipboard_probe.py",plan["run_id"]+"-"+guest.slot)
    sampler=GuestCommandClipboardSampler(lambda argv:backend._command(guest,argv),probe_path=probe,state_path=probe_state)
    guest.episode.attach_clipboard_sampler(sampler,required=True)
    sampler.sample()
    if not observer.verify_initial([guest],plan,backend):raise RuntimeError("C-N1 Browser navigation changed initial rich payload/table state")
    guest.episode.log.record("task_setup","readiness","cn1_rich_table_and_url_ready",{}, {"url":url,"health":health},details={"observer_ids":list(observer.observer_ids),"clipboard_read_only":True})


def _setup_c02(plan,guest,backend):
    import base64, shlex, time
    from pathlib import Path
    observer=C02RuntimeObserver()
    if not observer.verify_initial([guest],plan,backend):
        raise RuntimeError("C-02 exact Writer/Browser initial fixture validation failed")
    assets=observer._assets(plan); support=observer._support(plan)
    html_path=assets["Browser"]["guest_path"]
    state_path=support["browser-initial-state.json"]
    server_path=html_path.rsplit("/",1)[0]+"/codesk-c02-server.py"
    source=f"""from http.server import BaseHTTPRequestHandler,HTTPServer
from pathlib import Path
import json
HTML=Path({html_path!r}); STATE=Path({state_path!r})
class H(BaseHTTPRequestHandler):
 def reply(self,obj,status=200):
  raw=json.dumps(obj).encode();self.send_response(status);self.send_header('Content-Type','application/json');self.send_header('Content-Length',str(len(raw)));self.end_headers();self.wfile.write(raw)
 def do_GET(self):
  if self.path=='/health':return self.reply({{'ok':True}})
  if self.path!='/workspace':return self.reply({{'error':'not found'}},404)
  raw=HTML.read_bytes();self.send_response(200);self.send_header('Content-Type','text/html; charset=utf-8');self.send_header('Content-Length',str(len(raw)));self.end_headers();self.wfile.write(raw)
 def do_POST(self):
  if self.path!='/submit':return self.reply({{'error':'not found'}},404)
  p=json.loads(self.rfile.read(int(self.headers.get('Content-Length','0'))));s=json.loads(STATE.read_text())
  s['submission']=p;s['revision']+=1;STATE.write_text(json.dumps(s,sort_keys=True));return self.reply({{'ok':True}})
 def log_message(self,*args):pass
HTTPServer(('127.0.0.1',8768),H).serve_forever()
"""
    import base64
    data=base64.b64encode(source.encode()).decode()
    code="from pathlib import Path;import base64;p=Path("+repr(server_path)+");p.write_text(base64.b64decode("+repr(data)+").decode())"
    backend._command(guest,["python3","-c",code])
    backend._command(guest,["bash","-lc",f"nohup python3 {shlex.quote(server_path)} >/tmp/codesk-c02-server.log 2>&1 </dev/null &"])
    deadline=time.monotonic()+10; health=""
    while time.monotonic()<deadline:
        health=backend._command(guest,["bash","-lc","curl -fsS --max-time 1 http://127.0.0.1:8768/health || true"])
        if '"ok": true' in health or '"ok":true' in health:break
        time.sleep(.25)
    if '"ok"' not in health:raise RuntimeError(f"C-02 local Browser server not ready: {health}")
    url="http://127.0.0.1:8768/workspace"
    backend._command(guest,["bash","-lc","wid=$(xdotool search --class chromium 2>/dev/null | tail -1); "
        "test -n \"$wid\" && xdotool windowactivate --sync \"$wid\" && "
        "xdotool key --window \"$wid\" ctrl+l && xdotool type --window \"$wid\" "+shlex.quote(url)+
        " && xdotool key --window \"$wid\" Return; sleep 3"])
    screenshot=guest.episode.refresh_observation("c02_browser_readiness")
    if not screenshot.get("screenshot") or "Chromium" not in str(guest.episode._active_window_title()):
        raise RuntimeError("C-02 Browser GUI did not navigate to task server")
    if getattr(guest.episode,"clipboard_sampler",None) is None:
        from .clipboard_observer import GuestCommandClipboardSampler,install_guest_probe
        probe,state=install_guest_probe(lambda argv:backend._command(guest,argv),
            Path(__file__).resolve().parents[1]/"scripts/guest_clipboard_probe.py",
            plan["run_id"]+"-"+guest.slot)
        sampler=GuestCommandClipboardSampler(lambda argv:backend._command(guest,argv),probe_path=probe,state_path=state)
        guest.episode.attach_clipboard_sampler(sampler,required=True)
        snap=sampler.sample()
        guest.episode.log.record("clipboard_observer","healthcheck","c02.clipboard_observer_ready",{},snap,
            details={"hidden_from_actor":True,"read_only":True})
    if not observer.verify_initial([guest],plan,backend):
        raise RuntimeError("C-02 setup changed hidden initial state")
    guest.episode.log.record("task_setup","readiness","c02.browser_writer_ready",{},{"url":url,"health":health},
        details={"observer_ids":list(observer.observer_ids)})
    return None


def _setup_f02(plan,guest,backend):
    import base64,shlex,time
    observer=F02RuntimeObserver()
    if not observer.verify_initial([guest],plan,backend):raise RuntimeError("F-02 initial Writer/Browser oracle failed")
    assets=observer._assets(plan); support=observer._support(plan)
    html=assets["Browser"]["guest_path"]; state=support["browser-initial-state.json"]
    server=html.rsplit("/",1)[0]+"/codesk-f02-server.py"
    code_src=f"""from http.server import BaseHTTPRequestHandler,HTTPServer
from pathlib import Path
import json
HTML=Path({html!r});STATE=Path({state!r})
class H(BaseHTTPRequestHandler):
 def sendj(self,x,status=200):
  b=json.dumps(x).encode();self.send_response(status);self.send_header('Content-Type','application/json');self.send_header('Content-Length',str(len(b)));self.end_headers();self.wfile.write(b)
 def do_GET(self):
  if self.path=='/health':return self.sendj({{'ok':True}})
  if self.path!='/workspace':return self.sendj({{'error':'not found'}},404)
  b=HTML.read_bytes();self.send_response(200);self.send_header('Content-Type','text/html; charset=utf-8');self.send_header('Content-Length',str(len(b)));self.end_headers();self.wfile.write(b)
 def do_POST(self):
  if self.path!='/submit':return self.sendj({{'error':'not found'}},404)
  p=json.loads(self.rfile.read(int(self.headers.get('Content-Length','0'))));s=json.loads(STATE.read_text())
  s['submission']=p;s['revision']+=1;STATE.write_text(json.dumps(s,sort_keys=True));return self.sendj({{'ok':True}})
 def log_message(self,*x):pass
HTTPServer(('127.0.0.1',8769),H).serve_forever()
"""
    b64=base64.b64encode(code_src.encode()).decode()
    write="from pathlib import Path;import base64;p=Path("+repr(server)+");p.write_text(base64.b64decode("+repr(b64)+").decode())"
    backend._command(guest,["python3","-c",write])
    backend._command(guest,["bash","-lc",f"nohup python3 {shlex.quote(server)} >/tmp/codesk-f02-server.log 2>&1 </dev/null &"])
    deadline=time.monotonic()+10;health=""
    while time.monotonic()<deadline:
        health=backend._command(guest,["bash","-lc","curl -fsS --max-time 1 http://127.0.0.1:8769/health || true"])
        if '"ok"' in health:break
        time.sleep(.25)
    if '"ok"' not in health:raise RuntimeError(f"F-02 local form server readiness failed: {health}")
    url="http://127.0.0.1:8769/workspace"
    command=("wid=$(xdotool search --class chromium 2>/dev/null | tail -1); test -n \"$wid\" && "
        "xdotool windowactivate --sync \"$wid\" && xdotool key --window \"$wid\" ctrl+l && "
        "xdotool type --window \"$wid\" "+shlex.quote(url)+" && xdotool key --window \"$wid\" Return; sleep 3")
    backend._command(guest,["bash","-lc",command])
    shot=guest.episode.refresh_observation("f02_browser_readiness")
    title=str(guest.episode._active_window_title())
    if not shot.get("screenshot") or "Chromium" not in title:raise RuntimeError(f"F-02 Browser readiness failed: {title}")
    if not observer.verify_initial([guest],plan,backend):raise RuntimeError("F-02 Browser navigation changed task state")
    guest.episode.log.record("task_setup","readiness","f02.comment_form_ready",{},{"url":url,"browser_title":title},
        details={"observer_ids":list(observer.observer_ids)})
    return None



class A01RuntimeObserver:
    """InstanceSpec-driven hidden-state oracle for two pages in one Chromium window."""
    observer_ids=("chromium_top_level_window_identity_v1",
                  "browser_active_tab_and_submission_v1",
                  "browser_context_event_log_v1")

    @staticmethod
    def _paths(plan):
        rows={Path(x["guest_path"]).name:x["guest_path"] for x in plan["fixture_assets"]}
        html=next((x["guest_path"] for x in plan["fixture_assets"] if x["app"]=="Browser"),None)
        if not html or "browser-initial-state.json" not in rows or "browser-events.jsonl" not in rows:
            raise ValueError("A-01 needs Browser page plus state/event support assets")
        return html.rsplit("/",1)[0],rows["browser-initial-state.json"],rows["browser-events.jsonl"]

    @staticmethod
    def _state(guest,backend,path):
        return json.loads(backend._command(guest,["cat",path]))

    @staticmethod
    def _window_ids(guest,backend):
        raw=backend._command(guest,["bash","-lc","xdotool search --class chromium 2>/dev/null || true"])
        return [x.strip() for x in raw.splitlines() if x.strip().isdigit()]

    def verify_initial(self,guests,plan,backend):
        try:
            for guest in guests:
                _,state_path,_=self._paths(plan)
                state=self._state(guest,backend,state_path)
                if state.get("active_tab")!="tab-a" or set(state.get("tabs",{}))!={"tab-a","tab-b"}:return False
                if any(v.get("goal")!="" or v.get("revision")!=0 for v in state["tabs"].values()):return False
                if len(self._window_ids(guest,backend))!=1:return False
            return True
        except Exception:
            return False

    def __call__(self,guests,plan,backend):
        if not guests:raise ValueError("A-01 observer requires at least one Guest")
        actors=plan["actors"]
        if [x["actor_id"] for x in actors]!=["A","B"]:raise ValueError("A-01 Actor order must be A then B")
        values={};guards_ok=True;window_events=[]
        for i,guest in enumerate(guests):
            folder,state_path,event_path=self._paths(plan)
            state=self._state(guest,backend,state_path)
            ids=self._window_ids(guest,backend)
            active=backend._command(guest,["bash","-lc","xdotool getactivewindow 2>/dev/null || true"]).strip()
            titles=[]
            for xid in ids:
                title=backend._command(guest,["bash","-lc",f"xdotool getwindowname {xid} 2>/dev/null || true"]).strip()
                titles.append({"window_id":xid,"title":title})
            event_raw=backend._command(guest,["bash","-lc",f"cat {event_path} 2>/dev/null || true"])
            events=[]
            for line in event_raw.splitlines():
                try:events.append(json.loads(line))
                except Exception:continue
            recorded=state.get("window_id")
            one_window=len(ids)==1 and str(recorded)==str(ids[0])
            guards_ok &= one_window and active in ids and all(
                0<=state.get("tabs",{}).get(t,{}).get("revision",0)<=1 for t in ("tab-a","tab-b"))
            window_events.append({"guest":guest.slot,"window_ids":ids,"recorded_window_id":recorded,
                "active_window_id":active,"titles":titles,"active_tab":state.get("active_tab"),
                "context_changes":[e for e in events if e.get("kind")=="active_tab_changed"]})
            assigned=[actors[i]] if len(guests)>1 else actors
            for actor in assigned:
                aid=actor["actor_id"];tab="tab-a" if aid=="A" else "tab-b"
                actual=state.get("tabs",{}).get(tab,{})
                values[aid]={"object":actor["target_objects"][0],
                    "value":actual.get("goal","") if actual.get("revision",0)==1 else actor["initial_value"]}
        expected={"actors":{x["actor_id"]:x["expected_value"] for x in actors}}
        for aid in ("A","B"):
            if aid not in values:
                values[aid]={"object":next(x["target_objects"][0] for x in actors if x["actor_id"]==aid),
                             "value":next(x["initial_value"] for x in actors if x["actor_id"]==aid)}
        values["guards"]={"main":"PRESERVE" if guards_ok else "CONTAMINATED"}
        backend.notify_observer_event({"kind":"workflow_observation","workflow_id":"A-01",
            "observer":"chromium_top_level_window_identity_v1","windows":window_events})
        return {"actors":values,"application_context":window_events}


def _setup_a01(plan,guest,backend):
    import base64,shlex,time
    observer=A01RuntimeObserver()
    folder,state_path,event_path=observer._paths(plan)
    html=next(x["guest_path"] for x in plan["fixture_assets"] if x["app"]=="Browser")
    server=folder+"/browser-server.py"
    source=next((x for x in plan["fixture_assets"] if Path(x["guest_path"]).name=="browser-server.py"),None)
    if source is None:raise RuntimeError("A-01 server source fixture missing")
    server_bytes=Path(source["host_path"]).read_bytes()
    writer="from pathlib import Path;import base64;p=Path("+repr(server)+");p.write_bytes(base64.b64decode("+repr(base64.b64encode(server_bytes).decode())+"))"
    backend._command(guest,["python3","-c",writer])
    backend._command(guest,["bash","-lc",f"nohup python3 {shlex.quote(server)} >/tmp/codesk-a01-server.log 2>&1 </dev/null &"])
    deadline=time.monotonic()+10;health=""
    while time.monotonic()<deadline:
        health=backend._command(guest,["bash","-lc","curl -fsS --max-time 1 http://127.0.0.1:8766/health || true"])
        if '"ok"' in health:break
        time.sleep(.25)
    if '"ok"' not in health:raise RuntimeError(f"A-01 local Browser server not ready: {health}")
    command=("ids=$(xdotool search --class chromium 2>/dev/null); wid=$(printf '%s\\n' \"$ids\" | head -1); "
       "test -n \"$wid\" || exit 31; xdotool windowactivate --sync \"$wid\"; "
       "xdotool key --window \"$wid\" ctrl+l; xdotool type --window \"$wid\" http://127.0.0.1:8766/actor-a; xdotool key --window \"$wid\" Return; sleep 1; "
       "xdotool key --window \"$wid\" ctrl+t; xdotool type --window \"$wid\" http://127.0.0.1:8766/actor-b; xdotool key --window \"$wid\" Return; sleep 2; "
       "xdotool key --window \"$wid\" ctrl+1; sleep 1; printf '%s' \"$wid\"")
    window_id=backend._command(guest,["bash","-lc",command]).strip().splitlines()[-1]
    ids=observer._window_ids(guest,backend)
    if len(ids)!=1 or ids[0]!=window_id:raise RuntimeError(f"A-01 requires one stable Chromium top-level window: {ids}, launched={window_id}")
    state=json.loads(backend._command(guest,["cat",state_path]))
    state["window_id"]=window_id
    code="from pathlib import Path;import json;p=Path("+repr(state_path)+");p.write_text(json.dumps("+repr(state)+",sort_keys=True))"
    backend._command(guest,["python3","-c",code])
    shot=guest.episode.refresh_observation("a01_two_tab_readiness")
    title=str(guest.episode._active_window_title())
    if not shot.get("screenshot") or "Chromium" not in title:raise RuntimeError(f"A-01 Browser screenshot/readiness failed: {title}")
    if not observer.verify_initial([guest],plan,backend):raise RuntimeError("A-01 initial per-tab state verification failed")
    guest.episode.log.record("task_setup","readiness","a01_same_window_two_tabs_ready",{},
        {"window_id":window_id,"tab_a":"http://127.0.0.1:8766/actor-a","tab_b":"http://127.0.0.1:8766/actor-b"},
        details={"observer_ids":list(observer.observer_ids),"screenshot_available":True})



class AN1RuntimeObserver:
    observer_ids=("chromium_top_level_window_identity_v1","browser_active_route_revision_v1","browser_route_event_log_v1")
    @staticmethod
    def _paths(plan):
        rows={Path(x["guest_path"]).name:x["guest_path"] for x in plan["fixture_assets"]}
        page=next((x["guest_path"] for x in plan["fixture_assets"] if x["app"]=="Browser"),None)
        if not page or not {"browser-initial-state.json","browser-events.jsonl"}<=set(rows):
            raise ValueError("A-N1 Browser route state/event assets missing")
        return page.rsplit("/",1)[0],rows["browser-initial-state.json"],rows["browser-events.jsonl"]
    @staticmethod
    def _ids(g,b):
        raw=b._command(g,["bash","-lc","xdotool search --class chromium 2>/dev/null || true"])
        return [x.strip() for x in raw.splitlines() if x.strip().isdigit()]
    def verify_initial(self,guests,plan,backend):
        try:
            for g in guests:
                _,sp,_=self._paths(plan);s=json.loads(backend._command(g,["cat",sp]))
                if s.get("active_route")!="route-a" or s.get("tab_hash")!="/workspace#route-a":return False
                if s.get("routes")!={"route-a":{"value":"","revision":0},"route-b":{"value":"","revision":0}}:return False
                if len(self._ids(g,backend))!=1:return False
            return True
        except Exception:return False
    def __call__(self,guests,plan,backend):
        actors=plan["actors"];out={};rows=[];intact=True
        for i,g in enumerate(guests):
            _,sp,ep=self._paths(plan);state=json.loads(backend._command(g,["cat",sp]))
            raw=backend._command(g,["bash","-lc",f"cat {ep} 2>/dev/null || true"]);events=[]
            for line in raw.splitlines():
                try:events.append(json.loads(line))
                except Exception:pass
            ids=self._ids(g,backend);active=backend._command(g,["bash","-lc","xdotool getactivewindow 2>/dev/null || true"]).strip()
            rows.append({"guest":g.slot,"window_ids":ids,"active_window_id":active,"active_route":state.get("active_route"),
                "tab_hash":state.get("tab_hash"),"route_changes":[e for e in events if e.get("kind")=="route_changed"]})
            assigned=[actors[i]] if len(guests)>1 else actors
            for a in assigned:
                aid=a["actor_id"];route="route-a" if aid=="A" else "route-b";other="route-b" if aid=="A" else "route-a"
                q=state["routes"][route]
                out[aid]={"object":a["target_objects"][0],"value":q["value"] if q["revision"]==1 else a["initial_value"]}
                intact &= 0<=q["revision"]<=1
                if len(guests)>1: intact &= state["routes"][other]=={"value":"","revision":0}
        for a in actors:out.setdefault(a["actor_id"],{"object":a["target_objects"][0],"value":a["initial_value"]})
        intact &= all(len(x["window_ids"])==1 for x in rows)
        out["guards"]={"main":"PRESERVE" if intact else "CONTAMINATED"}
        backend.notify_observer_event({"kind":"workflow_observation","workflow_id":"A-N1",
            "observer":"browser_active_route_revision_v1","routes":rows})
        return {"actors":out,"application_context":rows}


def _setup_an1(plan,guest,backend):
    import base64,shlex,time
    obs=AN1RuntimeObserver();folder,sp,ep=obs._paths(plan)
    row=next((x for x in plan["fixture_assets"] if Path(x["guest_path"]).name=="browser-server.py"),None)
    if not row:raise RuntimeError("A-N1 route server fixture missing")
    server=folder+"/browser-server.py";payload=base64.b64encode(Path(row["host_path"]).read_bytes()).decode()
    backend._command(guest,["python3","-c","from pathlib import Path;import base64;p=Path("+repr(server)+");p.write_bytes(base64.b64decode("+repr(payload)+"))"])
    backend._command(guest,["bash","-lc",f"nohup python3 {shlex.quote(server)} >/tmp/codesk-an1-server.log 2>&1 </dev/null &"])
    deadline=time.monotonic()+10;health=""
    while time.monotonic()<deadline:
        health=backend._command(guest,["bash","-lc","curl -fsS --max-time 1 http://127.0.0.1:8770/health || true"])
        if '"ok"' in health:break
        time.sleep(.25)
    if '"ok"' not in health:raise RuntimeError(f"A-N1 route server not ready: {health}")
    url="http://127.0.0.1:8770/workspace#route-a"
    cmd=("wid=$(xdotool search --class chromium 2>/dev/null | head -1); test -n \"$wid\" && "
        "xdotool windowactivate --sync \"$wid\" && xdotool key --window \"$wid\" ctrl+l && "
        "xdotool type --window \"$wid\" "+shlex.quote(url)+" && xdotool key --window \"$wid\" Return; sleep 2")
    wid=backend._command(guest,["bash","-lc",cmd]).strip().splitlines()[-1]
    if len(obs._ids(guest,backend))!=1:raise RuntimeError("A-N1 expected exactly one Chromium top-level window")
    state=json.loads(backend._command(guest,["cat",sp]));state["window_id"]=wid
    backend._command(guest,["python3","-c","from pathlib import Path;import json;p=Path("+repr(sp)+");p.write_text(json.dumps("+repr(state)+",sort_keys=True))"])
    shot=guest.episode.refresh_observation("an1_same_tab_route_readiness")
    if not shot.get("screenshot") or "Chromium" not in str(guest.episode._active_window_title()):raise RuntimeError("A-N1 Browser readiness failed")
    if not obs.verify_initial([guest],plan,backend):raise RuntimeError("A-N1 exact initial route state mismatch")
    guest.episode.log.record("task_setup","readiness","an1_single_tab_two_routes_ready",{},
        {"url":url,"window_id":wid},details={"observer_ids":list(obs.observer_ids)})


class SN1RuntimeObserver:
    observer_ids=("uno_text_range_selection_v1","writer_span_style_state_v1","writer_guard_integrity_v1")
    @staticmethod
    def _asset(plan):
        return next(x for x in plan["fixture_assets"] if x["app"]=="Writer")
    @staticmethod
    def _parse(raw):
        root=_ET.fromstring(raw);text_ns="urn:oasis:names:tc:opendocument:xmlns:text:1.0"
        style_ns="urn:oasis:names:tc:opendocument:xmlns:style:1.0";fo_ns="urn:oasis:names:tc:opendocument:xmlns:xsl-fo-compatible:1.0"
        styles={}
        for st in root.iter(f"{{{style_ns}}}style"):
            props=st.find(f"{{{style_ns}}}text-properties")
            styles[st.get(f"{{{style_ns}}}name")]=props.get(f"{{{fo_ns}}}font-weight","normal") if props is not None else "normal"
        spans=[]
        for span in root.iter(f"{{{text_ns}}}span"):
            style_name=span.get(f"{{{text_ns}}}style-name")
            if style_name:
                spans.append({"text":"".join(span.itertext()),"style":style_name,"weight":styles.get(style_name,"normal")})
        paras=["".join(p.itertext()) for p in root.iter(f"{{{text_ns}}}p")]
        return spans,paras
    @staticmethod
    def _read(g,b,path):return b._command(g,["cat",path]).encode()
    def verify_initial(self,guests,plan,backend):
        try:
            row=self._asset(plan)
            for g in guests:
                current=self._read(g,backend,row["guest_path"]);seed=g.fixtures[row["guest_path"]]
                spans,paras=self._parse(current);seed_spans,seed_paras=self._parse(seed)
                if [(x["text"],x["weight"]) for x in spans]!=[(x["text"],x["weight"]) for x in seed_spans]:return False
                if len(spans)!=2 or any(x["weight"]!="normal" for x in spans) or "Guard: PRESERVE" not in paras:return False
            return True
        except Exception:return False
    def __call__(self,guests,plan,backend):
        row=self._asset(plan);actors=plan["actors"];out={};intact=True;selected=[]
        probe=("import json,uno; c=uno.getComponentContext(); r=c.ServiceManager.createInstanceWithContext('com.sun.star.bridge.UnoUrlResolver',c); "
          "x=r.resolve('uno:socket,host=localhost,port=2002;urp;StarOffice.ComponentContext');d=x.ServiceManager.createInstanceWithContext('com.sun.star.frame.Desktop',x); "
          "q=d.getCurrentComponent().getCurrentSelection();print(json.dumps({'selected_text':q.getString()}))")
        for g in guests:
            raw=self._read(g,backend,row["guest_path"]);spans,paras=self._parse(raw);seed_spans,seed_paras=self._parse(g.fixtures[row["guest_path"]])
            assigned=[actors[len(out)]] if len(guests)>1 else actors
            intact &= len(spans)==len(seed_spans)==2 and len(paras)==len(seed_paras) and "Guard: PRESERVE" in paras
            for actor in assigned:
                aid=actor["actor_id"];idx=0 if aid=="A" else 1;span=spans[idx] if idx<len(spans) else {"text":"","weight":"missing"}
                out[aid]={"object":actor["target_objects"][0],"value":"bold" if span["weight"]=="bold" else "normal"}
            rawsel=backend._command(g,["python3","-c",probe])
            try:selection=json.loads(rawsel.splitlines()[-1])
            except Exception as exc:raise RuntimeError(f"S-N1 UNO range selection unavailable: {rawsel}") from exc
            selected.append({"guest":g.slot,**selection})
            backend.notify_observer_event({"kind":"workflow_observation","workflow_id":"S-N1",
                "observer":"uno_text_range_selection_v1","selection":selection,"hidden_from_actor":True})
        for actor in actors:out.setdefault(actor["actor_id"],{"object":actor["target_objects"][0],"value":actor["initial_value"]})
        out["guards"]={"main":"PRESERVE" if intact else "CONTAMINATED"}
        return {"actors":out,"selection":selected}


def _setup_sn1(plan,guest,backend):
    import shlex
    row=SN1RuntimeObserver._asset(plan)
    if not SN1RuntimeObserver().verify_initial([guest],plan,backend):raise RuntimeError("S-N1 exact initial Writer span/oracle mismatch")
    titles=backend._command(guest,["bash","-lc","for id in $(xdotool search --class soffice 2>/dev/null); do xdotool getwindowname $id; done"])
    if Path(row["guest_path"]).stem.lower() not in titles.lower():raise RuntimeError("S-N1 Writer document identity missing")
    backend._command(guest,["bash","-lc","soffice --accept='socket,host=localhost,port=2002;urp;StarOffice.ServiceManager' >/tmp/codesk-sn1-uno.log 2>&1 </dev/null &"])
    shot=guest.episode.refresh_observation("sn1_writer_range_readiness")
    if not shot.get("screenshot"):raise RuntimeError("S-N1 screenshot unavailable")
    # Use the same read-only UNO selection endpoint required during scoring.
    SN1RuntimeObserver()([guest],plan,backend)
    guest.episode.log.record("task_setup","readiness","sn1_writer_range_ready",{},
        {"title":titles},details={"observer_ids":list(SN1RuntimeObserver.observer_ids)})




class UN1RuntimeObserver(_ODFRuntimeObserver):
    def __init__(self):
        super().__init__("U-N1")
        self.observer_ids=tuple(required_observers_for("U-N1"))
    @staticmethod
    def _action_text(event):
        return str(event.get("action_payload","")).lower()
    def __call__(self,guests,plan,backend):
        result=super().__call__(guests,plan,backend)
        actors={x["actor_id"]:x for x in plan["actors"]}
        events=list(getattr(backend,"scheduler_event_history",[]))
        complete=[(i,e) for i,e in enumerate(events) if e.get("kind")=="action_complete"]
        text=lambda e:self._action_text(e)
        temp=actors["A"]["expected_value"].lower()
        bvalue=actors["B"]["expected_value"].lower()
        a_temp=next((i for i,e in complete if e.get("actor_id")=="A" and temp in text(e)),None)
        b_edit=next((i for i,e in complete if e.get("actor_id")=="B" and bvalue in text(e)),None)
        a_undo=next((i for i,e in complete if e.get("actor_id")=="A" and
            any(token in text(e).replace("'","") for token in ("ctrl+z","ctrl z","control+z","ctrl,z","control,z","undo"))),None)
        evidence={"temporary_edit_observed":a_temp is not None,
            "undo_after_temporary_edit":a_temp is not None and a_undo is not None and a_temp<a_undo,
            "undo_after_actor_b":a_temp is not None and b_edit is not None and a_undo is not None and a_temp<b_edit<a_undo,
            "action_event_count":len(complete)}
        result["workflow_evidence"]={"A":evidence}
        result["history_timeline"]=[e for _,e in complete]
        for guest in guests:
            backend.notify_observer_event({"kind":"workflow_observation","workflow_id":"U-N1",
                "observer":"writer_undo_history_v1","workflow_evidence":evidence,
                "history_event_count":len(complete),"hidden_from_actor":True})
        return result


def _setup_un1(plan,guest,backend):
    _setup_odf(plan,guest,backend,"U-N1")
    guest.episode.log.record("task_setup","readiness","un1_writer_history_ready",{},
        {"documents":1,"operation_schema_revision":1},details={"observer_ids":list(required_observers_for("U-N1"))})


class U01RuntimeObserver(_ODFRuntimeObserver):
    def __init__(self):
        super().__init__("U-01")
        self.observer_ids=tuple(required_observers_for("U-01"))
    @staticmethod
    def _action_text(e):
        return str(e.get("action_payload","")).lower()
    def __call__(self,guests,plan,backend):
        result=super().__call__(guests,plan,backend)
        actors={x["actor_id"]:x for x in plan["actors"]}
        events=list(getattr(backend,"scheduler_event_history",[]))
        completed=[(i,e) for i,e in enumerate(events) if e.get("kind")=="action_complete"]
        a_temp=next((i for i,e in completed if e.get("actor_id")=="A" and actors["A"]["expected_value"].lower() in self._action_text(e)),None)
        b_goal=next((i for i,e in completed if e.get("actor_id")=="B" and actors["B"]["expected_value"].lower() in self._action_text(e)),None)
        a_undo=next((i for i,e in completed if e.get("actor_id")=="A" and
            any(token in self._action_text(e).replace("\'","") for token in ("ctrl+z","ctrl z","control+z","ctrl,z","control,z","undo"))),None)
        active=set(getattr(backend,"active_actor_ids",["A","B"]))
        evidence={"temporary_edit_observed":a_temp is not None,
            "undo_after_temporary_edit":a_temp is not None and a_undo is not None and a_temp<a_undo,
            "undo_after_actor_b":a_temp is not None and b_goal is not None and a_undo is not None and a_temp<b_goal<a_undo,
            "action_event_count":len(completed)}
        result["workflow_evidence"]={"A":evidence}
        result["history_timeline"]=[e for _,e in completed if e.get("actor_id") in active]
        for guest in guests:
            backend.notify_observer_event({"kind":"workflow_observation","workflow_id":"U-01",
                "observer":"calc_undo_history_v1","workflow_evidence":evidence,
                "hidden_from_actor":True})
        return result


def _setup_u01(plan,guest,backend):
    _setup_odf(plan,guest,backend,"U-01")
    backend._command(guest,["bash","-lc","soffice --accept='socket,host=localhost,port=2002;urp;StarOffice.ServiceManager' >/tmp/codesk-u01-uno.log 2>&1 </dev/null &"])
    if "UNO_READY" not in backend._command(guest,["python3","-c","import uno; print('UNO_READY')"]):
        raise RuntimeError("U-01 Calc/UNO readiness unavailable")
    guest.episode.log.record("task_setup","readiness","u01_calc_history_ready",{},
       {"operation_schema_revision":2},details={"observer_ids":list(required_observers_for("U-01"))})



class A02RuntimeObserver:
    """InstanceSpec-driven hidden-state oracle for two records on one Browser page."""
    observer_ids=("chromium_top_level_window_identity_v1","browser_selected_record_revision_v1",
                  "browser_record_event_log_v1")
    @staticmethod
    def _paths(plan):
        rows={Path(x["guest_path"]).name:x["guest_path"] for x in plan["fixture_assets"]}
        page=next((x["guest_path"] for x in plan["fixture_assets"] if x["app"]=="Browser"),None)
        if not page or not {"browser-initial-state.json","browser-events.jsonl"}<=set(rows):
            raise ValueError("A-02 Browser fixture/state/events are required")
        return page.rsplit("/",1)[0],rows["browser-initial-state.json"],rows["browser-events.jsonl"]
    @staticmethod
    def _window_ids(guest,backend):
        raw=backend._command(guest,["bash","-lc","xdotool search --class chromium 2>/dev/null || true"])
        return [x.strip() for x in raw.splitlines() if x.strip().isdigit()]
    def verify_initial(self,guests,plan,backend):
        try:
            for guest in guests:
                _,state_path,_=self._paths(plan);state=json.loads(backend._command(guest,["cat",state_path]))
                if state.get("selected_record")!="record-a" or state.get("records")!={"record-a":{"goal":"","revision":0},"record-b":{"goal":"","revision":0}}:return False
                if len(self._window_ids(guest,backend))!=1:return False
            return True
        except Exception:return False
    def __call__(self,guests,plan,backend):
        if not guests:raise ValueError("A-02 observer requires a Guest")
        actors=plan["actors"];output={};event_rows=[];intact=True
        for i,guest in enumerate(guests):
            _,state_path,event_path=self._paths(plan)
            state=json.loads(backend._command(guest,["cat",state_path]))
            raw=backend._command(guest,["bash","-lc",f"cat {event_path} 2>/dev/null || true"])
            ev=[]
            for line in raw.splitlines():
                try:ev.append(json.loads(line))
                except Exception:pass
            ids=self._window_ids(guest,backend)
            event_rows.append({"guest":guest.slot,"window_ids":ids,"selected_record":state.get("selected_record"),
                "record_selections":[x for x in ev if x.get("kind")=="record_selected"]})
            assigned=[actors[i]] if len(guests)>1 else actors
            for actor in assigned:
                aid=actor["actor_id"];rec="record-a" if aid=="A" else "record-b";other="record-b" if aid=="A" else "record-a"
                value=state["records"][rec]["goal"] if state["records"][rec]["revision"]==1 else actor["initial_value"]
                output[aid]={"object":actor["target_objects"][0],"value":value}
                intact &= state["records"][rec]["revision"] in (0,1)
                if len(guests)>1 or len(actors)==1:
                    intact &= state["records"][other]=={"goal":"","revision":0}
        for actor in actors:
            output.setdefault(actor["actor_id"],{"object":actor["target_objects"][0],"value":actor["initial_value"]})
        output["guards"]={"main":"PRESERVE" if intact and all(len(x["window_ids"])==1 for x in event_rows) else "CONTAMINATED"}
        backend.notify_observer_event({"kind":"workflow_observation","workflow_id":"A-02",
            "observer":"browser_selected_record_revision_v1","records":event_rows})
        return {"actors":output,"application_context":event_rows}


def _setup_a02(plan,guest,backend):
    import base64,shlex,time
    observer=A02RuntimeObserver();folder,state_path,event_path=observer._paths(plan)
    rows={Path(x["guest_path"]).name:x for x in plan["fixture_assets"]}
    server_row=rows.get("browser-server.py")
    if not server_row:raise RuntimeError("A-02 parameterized record server fixture missing")
    server=folder+"/browser-server.py";raw=Path(server_row["host_path"]).read_bytes()
    writer="from pathlib import Path;import base64;p=Path("+repr(server)+");p.write_bytes(base64.b64decode("+repr(base64.b64encode(raw).decode())+"))"
    backend._command(guest,["python3","-c",writer])
    backend._command(guest,["bash","-lc",f"nohup python3 {shlex.quote(server)} >/tmp/codesk-a02-server.log 2>&1 </dev/null &"])
    deadline=time.monotonic()+10;health=""
    while time.monotonic()<deadline:
        health=backend._command(guest,["bash","-lc","curl -fsS --max-time 1 http://127.0.0.1:8767/health || true"])
        if '"ok"' in health:break
        time.sleep(.25)
    if '"ok"' not in health:raise RuntimeError(f"A-02 record server not ready: {health}")
    url="http://127.0.0.1:8767/workspace"
    cmd=("wid=$(xdotool search --class chromium 2>/dev/null | head -1); test -n \"$wid\" && "
         "xdotool windowactivate --sync \"$wid\" && xdotool key --window \"$wid\" ctrl+l && "
         "xdotool type --window \"$wid\" "+shlex.quote(url)+" && xdotool key --window \"$wid\" Return; sleep 2")
    backend._command(guest,["bash","-lc",cmd])
    shot=guest.episode.refresh_observation("a02_record_context_readiness");title=str(guest.episode._active_window_title())
    if not shot.get("screenshot") or "Chromium" not in title:raise RuntimeError(f"A-02 Browser page readiness failed: {title}")
    if not observer.verify_initial([guest],plan,backend):raise RuntimeError("A-02 initial record oracle mismatch")
    guest.episode.log.record("task_setup","readiness","a02_single_page_two_records_ready",{},
        {"url":url,"title":title},details={"observer_ids":list(observer.observer_ids)})

def _event_gate_odf(plan,run):
    if run["topology"] not in {"ma_sd","ma_id"}: return None
    from .runtime_execution_v1 import EventGate
    return EventGate([{"kind":"action_complete","actor_id":"A"},
                      {"kind":"action_complete","actor_id":"B"},
                      {"kind":"action_complete","actor_id":"A"}])


def build_runtime_binding_registry() -> dict[str, dict[str, Any]]:
    bindings = {}
    for wid, observer, setup in (
        ("F-01", F01RuntimeObserver(), _setup_f01),
        ("S-01", S01RuntimeObserver(), _setup_s01),
        ("U-01", U01RuntimeObserver(), _setup_u01),
        ("F-04", F04RuntimeObserver(), _setup_f04),
        ("F-02", F02RuntimeObserver(), _setup_f02),
        ("C-01", C01RuntimeObserver(), _setup_c01),
        ("C-03", C03RuntimeObserver(), _setup_c03),
        ("C-02", C02RuntimeObserver(), _setup_c02),
        ("A-01", A01RuntimeObserver(), _setup_a01),
        ("A-02", A02RuntimeObserver(), _setup_a02),
        ("A-N1", AN1RuntimeObserver(), _setup_an1),
        ("S-N1", SN1RuntimeObserver(), _setup_sn1),
        ("F-N1", F_N1RuntimeObserver(), _setup_f_n1),
        ("U-N1", UN1RuntimeObserver(), _setup_un1),
        ("C-N1", CN1RuntimeObserver(), _setup_cn1),
    ):
        bindings[wid] = {"setup": setup, "initial_verifier": observer.verify_initial,
            "evaluator": observer,
            "event_gate": _event_gate_f_n1 if wid=="F-N1" else _event_gate_odf}
    return bindings


def concrete_binding_refs(workflow_id: str) -> dict[str, str]:
    classes = {"F-01": "F01RuntimeObserver", "F-04": "F04RuntimeObserver", "F-02": "F02RuntimeObserver",
               "C-01": "C01RuntimeObserver", "C-03": "C03RuntimeObserver", "C-02": "C02RuntimeObserver",
               "F-N1": "F_N1RuntimeObserver", "A-01": "A01RuntimeObserver", "A-02": "A02RuntimeObserver", "A-N1": "AN1RuntimeObserver", "S-01": "S01RuntimeObserver", "S-N1": "SN1RuntimeObserver", "U-01": "U01RuntimeObserver", "U-N1": "UN1RuntimeObserver", "C-N1": "CN1RuntimeObserver"}
    if workflow_id not in classes:
        return {"reset": "swcub.osworld_guest_backend_v1.A6000OSWorldBackend.reset_guest",
                "cleanup": "swcub.osworld_guest_backend_v1.A6000OSWorldBackend.cleanup_owned_guest"}
    setup = {"F-01": "_setup_f01", "F-04": "_setup_f04", "C-01": "_setup_c01",
             "C-02": "_setup_c02", "C-03": "_setup_c03", "F-02": "_setup_f02",
             "F-N1": "_setup_f_n1", "A-01": "_setup_a01", "A-02": "_setup_a02", "A-N1": "_setup_an1", "S-01": "_setup_s01", "S-N1": "_setup_sn1", "U-01": "_setup_u01", "U-N1": "_setup_un1", "C-N1": "_setup_cn1"}[workflow_id]
    return {"setup": f"swcub.runtime_bindings_v1.{setup}",
            "observer": f"swcub.runtime_bindings_v1.{classes[workflow_id]}",
            "evaluator": "swcub.production_v1.evaluate_oracle",
            "reset": "swcub.osworld_guest_backend_v1.A6000OSWorldBackend.reset_guest",
            "cleanup": "swcub.osworld_guest_backend_v1.A6000OSWorldBackend.cleanup_owned_guest"}
