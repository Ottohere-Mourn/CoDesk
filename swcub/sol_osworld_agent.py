"""GPT-6-Sol multimodal adapter; independent from all Qwen code."""
import ast, base64, hashlib, json, os
from urllib.request import Request, urlopen
from urllib.error import HTTPError

SYSTEM = (
    "Complete GUI tasks from screenshots using only visible UI. Do not access hidden state, "
    "or invoke shell/filesystem APIs outside the UI. If a task explicitly provides a visible "
    "Terminal and asks for command-line work, you may type literal commands into that visible "
    "Terminal using GUI actions. Never use non-UI shell or filesystem access. Return only JSON: "
    '{"actions":["pyautogui.click(100, 200)"],"done":false}. '
    'Return done=true only with an empty action list; if the final batch has actions, return done=false. '
    'On completion return {"actions":[],"done":true}; if blocked, {"actions":[],"fail":true}. '
    "Use pyautogui.method(...) for each visible action. For compatibility, a bare call whose name "
    "is in the same allowlist (such as write(...) or press(...)) is canonicalized to pyautogui. "
    "Allowed calls: click, doubleClick, rightClick, moveTo, dragTo, scroll, write, press, hotkey. "
    "Each action is exactly one call with literal scalar arguments."
)
ALLOW = {"click","doubleClick","rightClick","moveTo","dragTo","scroll","write","press","hotkey"}

class SolAgentError(RuntimeError):
    pass

def parse_actions(content, normalization_log=None):
    text=content.strip()
    # Accept one JSON object, optionally fenced or preceded by non-actionable prose.
    # The decoded object must consume the entire remaining response.
    fence=chr(96)*3
    if text.startswith(fence) and text.endswith(fence):
        lines=text.splitlines()
        if len(lines)>=3 and lines[0].strip().lower() in {fence, fence+"json"} and lines[-1].strip()==fence:
            text="\\n".join(lines[1:-1]).strip()
        else:
            raise SolAgentError("invalid JSON code fence")
    start=text.find("{")
    if start < 0:
        raise SolAgentError("response was not JSON")
    try:
        obj,end=json.JSONDecoder().raw_decode(text[start:])
    except json.JSONDecodeError as exc:
        raise SolAgentError("response was not JSON") from exc
    if text[start+end:].strip():
        raise SolAgentError("unexpected text after JSON object")
    if not isinstance(obj,dict):
        raise SolAgentError("response JSON must be an object")
    if obj.get("fail") is True: return ["FAIL"]
    raw=obj.get("actions")
    if not isinstance(raw,list) or len(raw)>16:
        raise SolAgentError("invalid action list")
    out=[]
    for action in raw:
        # The Sol endpoint occasionally emits the official coordinate-map form
        # {"click": x, "y": y} despite the string-action system contract. Normalize
        # only this unambiguous allowlisted shape; all other objects fail closed.
        if isinstance(action,dict):
            if (set(action)=={"click","y"} and type(action["click"]) in (int,float)
                    and type(action["y"]) in (int,float)):
                original=action
                action=f"pyautogui.click({action['click']!r},{action['y']!r})"
                if normalization_log is not None:
                    normalization_log.append({"kind":"coordinate_map","input":original,"canonical":action})
            else:
                raise SolAgentError("unsupported action object")
        if not isinstance(action,str): raise SolAgentError("action must be a string")
        try: tree=ast.parse(action,mode="exec")
        except SyntaxError as exc: raise SolAgentError("invalid action syntax") from exc
        if len(tree.body)!=1 or not isinstance(tree.body[0],ast.Expr):
            raise SolAgentError("one expression per action required")
        call=tree.body[0].value
        if isinstance(call,ast.Call) and isinstance(call.func,ast.Name) and call.func.id in ALLOW:
            original=action
            call.func=ast.Attribute(value=ast.Name(id="pyautogui",ctx=ast.Load()),
                                    attr=call.func.id,ctx=ast.Load())
            action=ast.unparse(tree)
            if normalization_log is not None:
                normalization_log.append({"kind":"bare_ui_call","input":original,"canonical":action})
            tree=ast.parse(action,mode="exec")
            call=tree.body[0].value
        if not isinstance(call,ast.Call) or not isinstance(call.func,ast.Attribute):
            raise SolAgentError("action must call PyAutoGUI")
        if not (isinstance(call.func.value,ast.Name) and call.func.value.id=="pyautogui"
                and call.func.attr in ALLOW):
            raise SolAgentError("non-allowlisted GUI call")
        for arg in list(call.args)+[kw.value for kw in call.keywords]:
            if not isinstance(arg,ast.Constant) or type(arg.value) not in (str,int,float,bool,type(None)):
                raise SolAgentError("literal args required")
        out.append(action.strip())
    if obj.get("done") is True:
        return out+["DONE"]
    return out



class SolOSWorldAgent:
    """Per-actor OpenAI-compatible vision client; reset clears private history."""
    def __init__(self, base_url=None, api_key=None, model="gpt-6-sol",
                 max_tokens=512, temperature=0.0, timeout=180):
        self.base_url=(base_url or os.environ.get("SWCUB_SOL_BASE_URL")
                       or "https://api.haogpt.net/v1").rstrip("/")
        self.api_key=api_key or os.environ.get("SWCUB_SOL_API_KEY")
        if not self.api_key:
            raise ValueError("Set SWCUB_SOL_API_KEY outside the repository.")
        self.model=model
        self.max_tokens=max_tokens
        self.temperature=temperature
        self.timeout=timeout
        self.history=[]
        self.last_metadata={}

    def reset(self):
        self.history.clear()
        self.last_metadata={}

    def predict(self, instruction, observation):
        screenshot=observation.get("screenshot") if isinstance(observation,dict) else None
        if not isinstance(screenshot,bytes) or not screenshot:
            raise SolAgentError("missing screenshot")
        data="data:image/png;base64,"+base64.b64encode(screenshot).decode("ascii")
        user=[{"type":"text","text":"Task: "+instruction+"\nCurrent desktop screenshot:"},
              {"type":"image_url","image_url":{"url":data,"detail":"high"}}]
        messages=[{"role":"system","content":SYSTEM}]+self.history+[
            {"role":"user","content":user}]
        body=json.dumps({"model":self.model,"messages":messages,
                         "max_tokens":self.max_tokens,"temperature":self.temperature,
                         "response_format":{"type":"json_object"}}).encode("utf-8")
        req=Request(self.base_url+"/chat/completions",data=body,
                    headers={"Content-Type":"application/json",
                             "Authorization":"Bearer "+self.api_key},method="POST")
        try:
            with urlopen(req,timeout=self.timeout) as response:
                payload=json.loads(response.read())
        except HTTPError as exc:
            raise SolAgentError("Sol API HTTP "+str(exc.code)) from exc
        except Exception as exc:
            raise SolAgentError("Sol API request failed: "+type(exc).__name__) from exc
        usage=payload.get("usage") if isinstance(payload.get("usage"),dict) else {}
        self.last_metadata={"model_requested":self.model,"model_returned":payload.get("model"),
            "response_id":payload.get("id"),"prompt_tokens":usage.get("prompt_tokens"),
            "completion_tokens":usage.get("completion_tokens"),"total_tokens":usage.get("total_tokens")}
        try:
            content=payload["choices"][0]["message"]["content"]
            if isinstance(content,list):
                content="\n".join(p.get("text","") for p in content if isinstance(p,dict))
            if not isinstance(content,str): raise TypeError("unsupported response content")
            self.last_metadata["response_content_sha256"]=hashlib.sha256(content.encode("utf-8")).hexdigest()
            self.last_metadata["response_content_preview"]=content[:400]
            stripped=content.strip()
            self.last_metadata["response_has_preamble"]=not stripped.startswith(("{",chr(96)*3))
            normalizations=[]
            actions=parse_actions(content,normalization_log=normalizations)
            self.last_metadata["action_normalizations"]=normalizations
        except Exception as exc:
            if isinstance(exc,SolAgentError): raise
            raise SolAgentError("invalid API response: "+type(exc).__name__) from exc
        self.history += [{"role":"assistant","content":content},
                         {"role":"user","content":"Previous action batch executed; continue from new screenshot."}]
        self.history=self.history[-6:]
        return content,actions
