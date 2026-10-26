"""HTTP/MCP client tools that expose the run-scoped collaboration API to an Actor."""
from __future__ import annotations

import base64
import hashlib
import json
import os
import urllib.error
import urllib.parse
import urllib.request
from typing import Any


class CollaborationClient:
    """Actor-scoped client for messages and attachments; it has no evaluator access."""

    def __init__(self, base_url: str, actor: str, token: str, timeout: float = 15):
        self.base_url = base_url.rstrip("/")
        self.actor = actor
        self.token = token
        self.timeout = timeout
        if actor not in {"A", "B", "S"}:
            raise ValueError(f"invalid actor identity: {actor}")

    def _request(self, path: str, method: str = "GET", payload: dict | None = None) -> tuple[Any, bytes]:
        data = json.dumps(payload).encode() if payload is not None else None
        request = urllib.request.Request(
            self.base_url + path, data=data, method=method,
            headers={"Authorization": f"Bearer {self.token}",
                     "Content-Type": "application/json"})
        try:
            with urllib.request.urlopen(request, timeout=self.timeout) as response:
                body = response.read()
                if response.headers.get_content_type() == "application/octet-stream":
                    return None, body
                return json.loads(body or b"{}"), body
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", "replace")[:500]
            raise RuntimeError(f"collaboration API returned HTTP {exc.code}: {detail}") from exc

    def send_message(self, recipient: str, body: str,
                     attachment_ids: list[str] | None = None) -> dict[str, Any]:
        result, _ = self._request("/messages", "POST", {
            "recipient": recipient, "body": body,
            "attachment_ids": list(attachment_ids or [])})
        return result

    def read_messages(self, after: float = 0) -> list[dict[str, Any]]:
        result, _ = self._request("/messages?" + urllib.parse.urlencode({"after": after}))
        return result

    def send_attachment(self, filename: str, content: bytes) -> dict[str, Any]:
        result, _ = self._request("/attachments", "POST", {
            "filename": filename,
            "content_base64": base64.b64encode(content).decode("ascii")})
        return result

    def read_attachment(self, attachment_id: str) -> dict[str, Any]:
        _, body = self._request("/attachments/" + urllib.parse.quote(attachment_id, safe=""))
        try:
            text = body.decode("utf-8")
            encoding = "utf-8"
        except UnicodeDecodeError:
            text = base64.b64encode(body).decode("ascii")
            encoding = "base64"
        return {"attachment_id": attachment_id, "encoding": encoding, "content": text,
                "bytes": len(body), "sha256": hashlib.sha256(body).hexdigest()}

    def publish_saved_artifact(self) -> dict[str, Any]:
        result, _ = self._request("/artifacts/publish", "POST", {})
        return result

    def list_saved_artifacts(self) -> dict[str, Any]:
        result, _ = self._request("/artifacts")
        return result


def _client_from_env() -> CollaborationClient:
    try:
        return CollaborationClient(os.environ["CODESK_COLLAB_URL"],
                                   os.environ["CODESK_COLLAB_ACTOR"],
                                   os.environ["CODESK_COLLAB_TOKEN"])
    except KeyError as exc:
        raise RuntimeError(f"missing Actor collaboration environment variable: {exc.args[0]}") from exc


def mcp_main() -> None:
    """Optional MCP entrypoint; mcp is installed by the project's [mcp] extra."""
    from mcp.server.fastmcp import FastMCP

    mcp = FastMCP("codesk-collaboration")

    @mcp.tool(description="Send a task-related message to the other Actor. Use recipient A, B, or all.")
    def send_message(recipient: str, body: str, attachment_ids: list[str] | None = None) -> dict[str, Any]:
        return _client_from_env().send_message(recipient, body, attachment_ids)

    @mcp.tool(description="Read messages addressed to this Actor after a Unix timestamp; after=0 reads all.")
    def read_messages(after: float = 0) -> list[dict[str, Any]]:
        return _client_from_env().read_messages(after)

    @mcp.tool(description="Attach a UTF-8 or binary file supplied as base64. Returns an attachment ID and SHA-256.")
    def send_attachment(filename: str, content_base64: str) -> dict[str, Any]:
        try:
            content = base64.b64decode(content_base64, validate=True)
        except ValueError as exc:
            raise ValueError("content_base64 must be valid base64") from exc
        return _client_from_env().send_attachment(filename, content)

    @mcp.tool(description="Read an attachment by ID. UTF-8 content is returned as text; other files as base64.")
    def read_attachment(attachment_id: str) -> dict[str, Any]:
        return _client_from_env().read_attachment(attachment_id)

    @mcp.tool(description="Publish your own already saved output to the peer Guest. Returns the verified revision/hash; cannot write document contents or choose another role's path.")
    def publish_saved_artifact() -> dict[str, Any]:
        return _client_from_env().publish_saved_artifact()

    @mcp.tool(description="List published output revisions, hashes and Guest paths. Open files through the GUI to read their contents.")
    def list_saved_artifacts() -> dict[str, Any]:
        return _client_from_env().list_saved_artifacts()

    mcp.run()


if __name__ == "__main__":
    mcp_main()
