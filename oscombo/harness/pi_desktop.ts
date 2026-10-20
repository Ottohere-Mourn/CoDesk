// pi extension: the same computer-use tools as the codex MCP server, backed by oscombo.desktop_tools (one process
// per call). Env: OSCOMBO_TOOLS_PY (python that can import oscombo); the backend reads OSCOMBO_GUEST_URL /
// OSCOMBO_ACTION_LOG / OSCOMBO_MAX_STEPS from the inherited environment.
import type { ExtensionAPI } from "@earendil-works/pi-coding-agent";
import { StringEnum } from "@earendil-works/pi-ai";
import { Type } from "typebox";

const PY = process.env.OSCOMBO_TOOLS_PY ?? "python3";

export default function (pi: ExtensionAPI) {
  const call = async (name: string, args: Record<string, unknown>, signal?: AbortSignal) => {
    const r = await pi.exec(PY, ["-m", "oscombo.desktop_tools", name, JSON.stringify(args)], { signal, timeout: 300000 });
    let out: { text?: string; image?: string | null; error?: string };
    try {
      out = JSON.parse(r.stdout.trim().split("\n").pop() ?? "{}");
    } catch {
      throw new Error(`desktop tool failed: ${r.stderr.slice(-500)}`);
    }
    if (out.error) throw new Error(out.error);
    const content: any[] = [{ type: "text", text: out.text ?? "OK." }];
    if (out.image) content.push({ type: "image", data: out.image, mimeType: "image/png" });
    return { content, details: {} };
  };
  const tool = (name: string, description: string, parameters: any) =>
    pi.registerTool({
      name,
      label: name,
      description,
      promptSnippet: description,
      parameters,
      async execute(_id, params, signal) {
        return call(name, params as Record<string, unknown>, signal);
      },
    });

  tool("screenshot", "Take a screenshot of the whole desktop (1280x720).", Type.Object({}));
  tool("click", "Move the mouse to (x, y) and click. button: left|right|middle. clicks: 1 or 2 (double click).",
    Type.Object({
      x: Type.Number(), y: Type.Number(),
      button: Type.Optional(StringEnum(["left", "right", "middle"] as const)),
      clicks: Type.Optional(Type.Number()),
    }));
  tool("drag", "Press the left button at (x1, y1), drag to (x2, y2), release.",
    Type.Object({ x1: Type.Number(), y1: Type.Number(), x2: Type.Number(), y2: Type.Number() }));
  tool("move", "Move the mouse to (x, y) without clicking (hover).", Type.Object({ x: Type.Number(), y: Type.Number() }));
  tool("type_text", "Type text at the current keyboard focus. Use key() for Enter/Tab/shortcuts.",
    Type.Object({ text: Type.String() }));
  tool("key", "Press a key or chord, e.g. 'Return', 'Tab', 'ctrl+s', 'alt+F4'. Several presses separated by spaces.",
    Type.Object({ keys: Type.String() }));
  tool("scroll", "Scroll at (x, y). direction: up|down|left|right. amount: number of wheel notches.",
    Type.Object({
      x: Type.Number(), y: Type.Number(),
      direction: Type.Optional(StringEnum(["up", "down", "left", "right"] as const)),
      amount: Type.Optional(Type.Number()),
    }));
  tool("wait", "Wait for the UI to update (seconds, max 30), then take a screenshot.",
    Type.Object({ seconds: Type.Optional(Type.Number()) }));
  tool("declare_infeasible", "Call this (instead of acting) if you are confident the task cannot be done as specified.",
    Type.Object({ reason: Type.String() }));
}
