from experiments.audit_professional_benchmarks import atif_counts, weave_counts


def test_weave_counts_notes_but_does_not_number_them():
    data = {"steps": [
        {"kind": "note"}, {"kind": "note"},
        {"kind": "gui", "action": "(no-op)", "shot": "001.webp"},
        {"kind": "cli", "action": "xdotool click 1"},
        {"kind": "note"}, {"kind": "cli"},
        {"kind": "gui", "action": "click; click", "shot": "002.webp"},
    ]}
    result = weave_counts(data)
    assert result["raw_events"] == 7
    assert result["numbered_events"] == 4
    assert result["kind_counts"] == {"cli": 2, "gui": 2, "note": 3}
    assert result["events_with_shot"] == 2
    assert result["gui_noop_events"] == 1
    assert result["gui_cli_switches_ignoring_notes"] == 2


def test_atif_counts_only_explicit_calls_and_separates_images():
    data = {"schema_version": "ATIF-v1.8", "steps": [
        {"source": "user"},
        {"source": "agent", "tool_calls": [{"function_name": "bash_command"}],
         "observation": {"results": [{"content": "screenshot"}]}},
        {"source": "agent", "observation": {"results": [{"content": [
            {"type": "text"}, {"type": "image", "source": {"path": "screen.webp"}},
        ]}]}},
        {"source": "agent", "tool_calls": [{"function_name": "mark_task_complete"}]},
    ]}
    result = atif_counts(data)
    assert result["raw_steps"] == 4
    assert result["explicit_tool_calls"] == 2
    assert result["tool_counts"] == {"bash_command": 1, "mark_task_complete": 1}
    assert result["image_observation_blocks"] == 1
