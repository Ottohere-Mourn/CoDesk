import pytest

from swcub.local_vlm import parse_gui_action


@pytest.mark.parametrize("raw, expected", [
    ('{"op":"key","key":"ctrl+a"}', {"op": "key", "key": "ctrl+a"}),
    ('```json\n{"op":"click","x":120,"y":42}\n```',
     {"op": "click", "x": 120, "y": 42}),
    ('reasoning: {"op":"type","text":"Approved"}',
     {"op": "type", "text": "Approved"}),
    ('{"op":"click","x":1034,350}}',
     {"op": "click", "x": 1034, "y": 350}),
    ('{"op":"click","x":1000,y:300}',
     {"op": "click", "x": 1000, "y": 300}),
])
def test_parse_gui_action(raw, expected):
    assert parse_gui_action(raw) == expected


@pytest.mark.parametrize("raw", [
    "I would click the field",
    '{"op":"click","x":1.5,"y":2}',
    '{"op":"type","text":"x","shell":"rm"}',
    '{"op":"key","key":"alt+f4"}',
    '{"op":"scroll","dy":500}',
    '{"op":"click","x":1,"y":2',
])
def test_reject_invalid_or_unsafe_model_actions(raw):
    with pytest.raises(ValueError):
        parse_gui_action(raw)
