from oscombo.human_agent_calendar_case_runner import _fixture_equivalence


def _manifest(event_count=0, source_hash="fixture-hash"):
    return {
        "source_content_sha256": source_hash,
        "initial_state": {"calendars": ["personal", "team"], "event_count": event_count},
    }


def test_identical_empty_calendar_fixtures_are_equivalent():
    result = _fixture_equivalence([_manifest(), _manifest()])
    assert result == {
        "fixture_content_sha256_equal": True,
        "initial_state_equal": True,
        "both_calendars_start_empty": True,
    }


def test_nonempty_or_different_calendar_fixtures_are_rejected():
    nonempty = _fixture_equivalence([_manifest(), _manifest(event_count=1)])
    assert nonempty["fixture_content_sha256_equal"] is True
    assert nonempty["initial_state_equal"] is False
    assert nonempty["both_calendars_start_empty"] is False

    different_source = _fixture_equivalence([_manifest(), _manifest(source_hash="other")])
    assert different_source["fixture_content_sha256_equal"] is False
    assert different_source["initial_state_equal"] is True
    assert different_source["both_calendars_start_empty"] is True
