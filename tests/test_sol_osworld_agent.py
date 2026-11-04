import base64, json
from unittest.mock import patch
import pytest
from swcub.sol_osworld_agent import SolAgentError, SolOSWorldAgent, parse_actions
from swcub.tasks.cwd_bundle_schedule_v1 import is_relative_release_write_action, is_submission_action

def test_parse_actions_and_done():
    assert parse_actions('{"actions":["pyautogui.press(\\"enter\\")"],"done":false}') == ['pyautogui.press("enter")']
    assert parse_actions('{"actions":[],"done":true}') == ["DONE"]
    assert parse_actions(json.dumps({"actions": ['pyautogui.press("enter")'], "done": True})) == [
        'pyautogui.press("enter")', "DONE"]
    assert parse_actions('```json\n{"actions":[],"done":true}\n```') == ["DONE"]

def test_parse_actions_accepts_one_object_after_prose_but_rejects_trailing_text():
    assert parse_actions('Plan: type in the visible terminal. {"actions":["pyautogui.press(\\"enter\\")"],"done":false}') == [
        'pyautogui.press("enter")']
    with pytest.raises(SolAgentError,match="unexpected text"):
        parse_actions('{"actions":[],"done":true} trailing text')
    with pytest.raises(SolAgentError,match="unexpected text"):
        parse_actions('{"actions":[],"done":true} {"actions":[],"fail":true}')

@pytest.mark.parametrize("action", [
    'import os', '__import__("os").system("id")',
    'pyautogui.write(open("/etc/passwd").read())',
    'pyautogui.screenshot()', 'pyautogui.click(1,2);pyautogui.press("enter")'])
def test_reject_unsafe_action(action):
    with pytest.raises(SolAgentError):
        parse_actions(json.dumps({"actions":[action],"done":False}))

def test_normalize_official_coordinate_map_action():
    assert parse_actions(json.dumps({"actions":[{"click":35,"y":337}],"done":False})) == [
        "pyautogui.click(35,337)"]
    with pytest.raises(SolAgentError,match="unsupported action object"):
        parse_actions(json.dumps({"actions":[{"type":"shell","cmd":"id"}],"done":False}))

def test_multimodal_request():
    class Response:
        def __enter__(self): return self
        def __exit__(self,*args): return False
        def read(self):
            return json.dumps({"id":"r1","model":"gpt-6-sol",
                "choices":[{"message":{"content":'{"actions":["pyautogui.click(10,20)"],"done":false}'}}],
                "usage":{"total_tokens":9}}).encode()
    agent=SolOSWorldAgent(api_key="not-a-real-secret")
    with patch("swcub.sol_osworld_agent.urlopen",return_value=Response()) as mocked:
        response,actions=agent.predict("click button",{"screenshot":b"png-bytes"})
    assert actions==["pyautogui.click(10,20)"]
    req=mocked.call_args.args[0]
    body=json.loads(req.data)
    assert body["model"]=="gpt-6-sol"
    image=body["messages"][-1]["content"][1]["image_url"]["url"]
    assert base64.b64decode(image.split(",",1)[1])==b"png-bytes"
    assert agent.last_metadata["total_tokens"]==9
    assert "not-a-real-secret" not in response

def test_missing_secret_fails_closed(monkeypatch):
    monkeypatch.delenv("SWCUB_SOL_API_KEY",raising=False)
    with pytest.raises(ValueError,match="SWCUB_SOL_API_KEY"):
        SolOSWorldAgent()


def test_api_http_error_is_sanitized_without_body():
    from urllib.error import HTTPError
    agent=SolOSWorldAgent(api_key="not-a-real-secret")
    err=HTTPError("https://example.invalid",400,"bad request",{},None)
    with patch("swcub.sol_osworld_agent.urlopen",side_effect=err):
        with pytest.raises(SolAgentError,match="HTTP 400") as raised:
            agent.predict("task",{"screenshot":b"fake-image"})
    assert "not-a-real-secret" not in str(raised.value)

def test_reset_clears_only_this_actor_history():
    first=SolOSWorldAgent(api_key="fake")
    second=SolOSWorldAgent(api_key="fake")
    first.history.append({"role":"assistant","content":"actor a"})
    second.history.append({"role":"assistant","content":"actor b"})
    first.reset()
    assert first.history==[]
    assert second.history==[{"role":"assistant","content":"actor b"}]


def test_normalize_bare_allowlisted_cua_calls_and_record_mapping():
    normalizations=[]
    content=json.dumps({"actions":[
        'write("printf TOKEN > deliverables/release-note.txt")',
        'press("ENTER")'], "done":False})
    normalized=parse_actions(content,normalization_log=normalizations)
    assert len(normalized)==2
    assert normalized[0].startswith("pyautogui.write(") and "printf TOKEN" in normalized[0]
    assert normalized[1].startswith("pyautogui.press(") and "ENTER" in normalized[1]
    assert [row["kind"] for row in normalizations]==["bare_ui_call","bare_ui_call"]
    assert normalizations[0]["input"].startswith("write(")
    assert normalizations[0]["canonical"].startswith("pyautogui.write(")
    exact=json.dumps({"actions":[
        "write(\"printf '%s' RELEASE-OK > deliverables/release-note.txt\")",
        "press(\"ENTER\")"],"done":False})
    canonical=parse_actions(exact)
    assert is_relative_release_write_action(canonical[0])
    assert is_submission_action(canonical[1])
    with pytest.raises(SolAgentError,match="action must call PyAutoGUI"):
        parse_actions(json.dumps({"actions":['shell("id")'],"done":False}))
