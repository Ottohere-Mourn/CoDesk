"""Shared-desktop GUI/CLI client for native Codex MCP and Freehand Bash tools."""
from __future__ import annotations

import base64
import json
import os
from pathlib import Path
import sys
import urllib.request


def perform(arguments):
    request = urllib.request.Request(os.environ["PARAGUI_DESKTOP_URL"],
        data=json.dumps(arguments).encode(), headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(request, timeout=180) as response:
        return json.load(response)


def mcp_reply(message, schema):
    method = message.get("method")
    if method == "initialize":
        return {"protocolVersion": message["params"]["protocolVersion"],
            "capabilities": {"tools": {}}, "serverInfo": {"name": "paragui-desktop", "version": "1.0"}}
    if method == "ping":
        return {}
    if method == "tools/list":
        return {"tools": [{"name": "desktop", "description": schema["description"],
            "inputSchema": schema["parameters"]}]}
    if method == "tools/call":
        if message["params"]["name"] != "desktop":
            raise ValueError("Unknown desktop tool")
        result = perform(message["params"].get("arguments", {}))
        image = result.pop("image", None)
        content = [{"type": "text", "text": json.dumps(result)}]
        if image:
            content.append({"type": "image", "data": image, "mimeType": "image/png"})
        return {"content": content, "isError": bool(result.get("error"))}
    raise ValueError("Unsupported MCP method")


def main():
    if sys.argv[1:] == ["--mcp"]:
        schema = json.loads(Path("/bridge/schema.json").read_text())
        for line in sys.stdin:
            message = json.loads(line)
            if "id" not in message:
                continue
            reply = {"jsonrpc": "2.0", "id": message["id"]}
            try:
                reply["result"] = mcp_reply(message, schema)
            except Exception as error:
                reply["error"] = {"code": -32603, "message": str(error)}
            print(json.dumps(reply), flush=True)
        return
    result = perform(json.loads(sys.argv[1]))
    image = result.pop("image", None)
    if image:
        path = Path("/session/desktop.png")
        path.write_bytes(base64.b64decode(image, validate=True))
        manifest = os.environ.get("FREEHAND_IMAGE_MANIFEST")
        if manifest:
            Path(manifest).write_text(json.dumps([str(path)]))
        result["screenshot"] = str(path)
    print(json.dumps(result))


if __name__ == "__main__":
    main()
