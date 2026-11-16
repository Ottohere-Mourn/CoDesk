import io
import json
import tomllib

import pytest

from experiments.codex_vm10 import config_text
from experiments.responses_relay import relay_stream


def test_native_sse_is_forwarded_unchanged_with_usage_and_output():
    events = [
        {"type": "response.output_item.done", "output_index": 0,
         "item": {"type": "function_call", "name": "exec_command", "arguments": '{"cmd":"pwd"}'}},
        {"type": "response.completed", "response": {"status": "completed", "output": [],
                                                      "usage": {"total_tokens": 18}}},
    ]
    raw = b": keepalive\n\n" + b"".join(b"data: " + json.dumps(e).encode() + b"\n\n" for e in events)
    forwarded = []
    response = relay_stream(io.BytesIO(raw), forwarded.append)
    assert b"".join(forwarded) == raw
    assert response["usage"]["total_tokens"] == 18
    assert response["output"][0]["name"] == "exec_command"


def test_truncated_sse_cannot_be_reported_as_success():
    with pytest.raises(ValueError, match="without a terminal"):
        relay_stream(io.BytesIO(b'data: {"type":"response.created"}\n\n'), lambda line: None)


def test_codex_guest_config_keeps_shell_and_disables_additional_agents():
    config = tomllib.loads(config_text("gpt-6-astra", "high", "http://192.168.1.1/session/v1"))
    assert config["model"] == "gpt-6-astra"
    assert config["features"]["shell_tool"]
    assert not config["features"]["multi_agent"]
    assert config["sandbox_mode"] == "workspace-write"
    assert config["approval_policy"] == "never"
    assert config["sandbox_workspace_write"]["network_access"] is True
    provider = config["model_providers"]["paragui"]
    assert provider["wire_api"] == "responses"
    assert "env_key" not in provider and "experimental_bearer_token" not in provider
