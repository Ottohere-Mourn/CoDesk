from oscombo.human_agent_inventory_case_runner import _fixture_equivalence


def _manifest(*, source_hash="source", drafts=0, receipts=0, inventory=None):
    return {
        "source_content_sha256": source_hash,
        "initial_state": {
            "draft_count": drafts,
            "receipt_count": receipts,
            "inventory_on_hand": inventory or {"SKU-A": 11, "SKU-B": 46, "SKU-C": 7, "SKU-D": 20},
        },
    }


def test_identical_empty_inventory_fixtures_are_equivalent():
    result = _fixture_equivalence([_manifest(), _manifest()])
    assert result == {
        "fixture_content_sha256_equal": True,
        "initial_state_equal": True,
        "no_initial_drafts_or_receipts": True,
        "initial_inventory_equal": True,
    }


def test_unequal_or_dirty_inventory_fixtures_are_rejected():
    different_state = _fixture_equivalence([_manifest(), _manifest(inventory={"SKU-A": 12})])
    assert different_state["initial_state_equal"] is False
    assert different_state["initial_inventory_equal"] is False

    dirty = _fixture_equivalence([_manifest(), _manifest(receipts=1)])
    assert dirty["initial_state_equal"] is False
    assert dirty["no_initial_drafts_or_receipts"] is False

    different_content = _fixture_equivalence([_manifest(), _manifest(source_hash="other")])
    assert different_content["fixture_content_sha256_equal"] is False


def test_fixed_user_replay_uses_character_intervals_for_reliable_receipt_entry():
    from oscombo.human_agent_inventory_case_runner import _user_actions

    actions = _user_actions()
    fill = next(action for action in actions if action.name == "fill_receipt")
    assert "pyautogui.write('LOT-7721', interval=0.06)" in fill.code
    assert "pyautogui.write('12', interval=0.06)" in fill.code
    assert "pyautogui.write('B-14', interval=0.06)" in fill.code
