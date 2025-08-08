from tools.general_utils import get_weather, get_current_time, web_crawler
from tools.web_search import web_search
from tools.ytb_transcribe import ytb_transcribe
from tools.decorator import REGISTERED_TOOLS, TOOL_DISPLAY

def call_function(name: str, args: dict):
    fn = REGISTERED_TOOLS.get(name)
    if not fn:
        raise ValueError(f"Unknown tool: {name}")
    return fn(**args)

def tool_msg_beautify(tools: list[dict]):
    lines = []
    for entry in tools:
        raw_name  = entry["name"]
        display   = TOOL_DISPLAY.get(raw_name, raw_name)
        arguments = entry["arguments"]
        lines.append(f"- {display}\n    💾 Input: {arguments}")
    return "\n\n".join(lines)