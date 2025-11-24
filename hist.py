# thanks to reference https://embracethered.com/blog/posts/2025/chatgpt-how-does-chat-history-memory-preferences-work/

import os
import json
import copy
import time
import asyncio
import base64
from openai import AsyncOpenAI
from tools.general_utils import get_current_time

from dotenv import load_dotenv

load_dotenv()
openai = AsyncOpenAI(
    api_key=os.environ.get("OPENAI_API_KEY")
)

TOTAL_HIST_LIMIT = 12
SHORT_HIST_LIMIT = 3
RECENT_CHAT_LIMIT = 40  # mirrors how ChatGPT surfaces recent conversation content
PROFILE_SOURCE_LIMIT = 80
PROFILE_MODEL = "gpt-5-nano"

# Profile limits matching ChatGPT's architecture
MAX_RESPONSE_PREFERENCES = 15
MAX_TOPIC_HIGHLIGHTS = 8
MAX_USER_INSIGHTS = 5

def read_history(user_id: str, chat_id: str = None) -> list:
    if chat_id is None:
        chat_id = user_id
    # Ensure history directory exists
    if not os.path.exists("history"):
        os.makedirs("history", exist_ok=True)
    fn = f"history/{user_id}/hist_{chat_id}.json"
    if not os.path.exists(fn):
        init_chat = []
        with open(fn,"w") as f: json.dump(init_chat,f)
    with open(fn) as f:
        return json.load(f)

def write_history(user_id: str, chat_id: str = None, hist: list = None):
    if chat_id is None:
        chat_id = user_id
    if hist is None:
        hist = []
    # Ensure history directory exists
    if not os.path.exists(f"history/{user_id}"):
        os.makedirs(f"history/{user_id}", exist_ok=True)
    with open(f"history/{user_id}/hist_{chat_id}.json","w") as f:
        json.dump(hist,f,indent=2,ensure_ascii=False)

def encode_image(image_path):
    with open(image_path, "rb") as image_file:
        return base64.b64encode(image_file.read()).decode("utf-8") 

def clear_history(user_id: str, chat_id: str = None):
    if chat_id is None:
        chat_id = user_id
    fn = f"history/{user_id}"
    if os.path.exists(fn):
        os.remove(fn)

def _ensure_parent_dir(path: str):
    parent = os.path.dirname(path)
    if parent and not os.path.exists(parent):
        os.makedirs(parent, exist_ok=True)

def _load_profile_sections(profile_path: str) -> dict:
    if not profile_path or not os.path.exists(profile_path):
        return {}
    try:
        with open(profile_path) as f:
            data = json.load(f)
            return {k: v for k, v in data.items() if k != "meta"}
    except Exception:
        return {}


def _save_profile_sections(profile_path: str, sections: dict, hist_len: int):
    if not profile_path:
        return
    try:
        _ensure_parent_dir(profile_path)
        payload = dict(sections)
        payload["meta"] = {
            "last_updated": time.time(),
            "source_messages": hist_len,
        }
        with open(profile_path, "w") as f:
            json.dump(payload, f, indent=2, ensure_ascii=False)
    except Exception:
        # Do not break chat flow if persistence fails
        pass

def _normalize_text_blob(content) -> str:
    """
    Render message content to plain text for downstream summarization.
    Keeps image placeholders so the model knows an image existed without reloading it.
    """
    if isinstance(content, str):
        return content.strip()
    if isinstance(content, list):
        parts = []
        for item in content:
            if not isinstance(item, dict):
                continue
            if item.get("type") == "input_text":
                parts.append(item.get("text", ""))
            elif item.get("type") == "input_image":
                parts.append("[image attached]")
        return " ".join(parts).strip()
    return ""


def _clean_history_messages(hist: list) -> list:
    """Strip noisy tool audit text and return a shallow copy of messages."""
    cleaned = []
    for item in hist:
        new_item = dict(item)
        if isinstance(new_item.get("content"), str):
            new_item["content"] = new_item["content"].split("🔌 Module Used")[0].strip()
        cleaned.append(new_item)
    return cleaned


def _recent_conversation_content(hist: list) -> list:
    """
    Return the last N conversation pairs with enhanced structure:
    - Conversation number
    - User message preview (first 100 chars)
    - Timestamp (if available in future)

    Mirrors ChatGPT's recent conversation content format.
    """
    # Group messages into conversation pairs (user + assistant)
    pairs = []
    i = 0
    while i < len(hist):
        if i < len(hist) and hist[i].get("role") == "user":
            user_msg = hist[i]
            assistant_msg = hist[i+1] if i+1 < len(hist) and hist[i+1].get("role") == "assistant" else None
            pairs.append((user_msg, assistant_msg))
            i += 2
        else:
            i += 1

    # Take last RECENT_CHAT_LIMIT pairs
    trimmed_pairs = pairs[-RECENT_CHAT_LIMIT:]
    start_idx = len(pairs) - len(trimmed_pairs) + 1

    recent_lines = []
    for idx, (user_msg, assistant_msg) in enumerate(trimmed_pairs, start=start_idx):
        user_content = _normalize_text_blob(user_msg.get("content"))

        # Create preview (first 100 chars for compactness)
        preview = user_content[:100]
        if len(user_content) > 100:
            preview += "..."

        # Format: "N. [preview]"
        recent_lines.append(f"{idx}. {preview}")

    return recent_lines


async def _profile_sections_from_history(hist: list) -> dict:
    """
    Build lightweight profile sections inspired by ChatGPT's memory architecture:
    - assistant_response_preferences (with confidence metrics)
    - notable_topic_highlights (with confidence tags)
    - helpful_user_insights
    """
    user_msgs = [msg for msg in hist if msg.get("role") == "user"]
    if not user_msgs:
        return {}

    samples = []
    total_chars = 0
    # Take up to PROFILE_SOURCE_LIMIT user turns while keeping payload bounded
    for msg in user_msgs[-PROFILE_SOURCE_LIMIT:]:
        rendered = _normalize_text_blob(msg.get("content"))
        total_chars += len(rendered)
        if total_chars > 4000:
            break
        samples.append(rendered)

    history_blob = "\n".join(samples[-PROFILE_SOURCE_LIMIT:])
    prompt = f"""
You maintain compact memory sections modeled after ChatGPT's chat history features.
Analyze the user's recent messages (newest last) and extract:

1. assistant_response_preferences: What formatting/style/language preferences did the USER explicitly request for responses? Return as list of objects with "preference" and "confidence" (high/medium/low). Max {MAX_RESPONSE_PREFERENCES} entries.
   Example: {{"preference": "use Chinese for responses", "confidence": "high"}}
   Do NOT include meta-instructions about this JSON format itself.

2. notable_topic_highlights: What topics did the user discuss? Return as list of objects with "topic" and "confidence" (high/medium/low). Max {MAX_TOPIC_HIGHLIGHTS} entries.
   Example: {{"topic": "Stefan Zweig's literary influence", "confidence": "high"}}

3. helpful_user_insights: What facts about the user are revealed in their messages? List up to {MAX_USER_INSIGHTS} short, grounded facts as simple strings.
   Example: "User is reading Stefan Zweig's World of Yesterday"

Return ONLY a JSON object with these three keys. Be terse and only include details directly supported by the messages below.

User messages:
{history_blob}
"""

    try:
        response = await openai.responses.create(
            model=PROFILE_MODEL,
            reasoning={ "effort": "low" },
            text={"verbosity": "low" },
            input=[{"role": "user", "content": prompt}],
        )
        raw = response.output_text.strip()
        data = json.loads(raw)
    except Exception:
        return {}

    normalized = {}

    # Handle assistant_response_preferences with confidence
    prefs = data.get("assistant_response_preferences", [])
    if isinstance(prefs, list):
        normalized_prefs = []
        for item in prefs[:MAX_RESPONSE_PREFERENCES]:
            if isinstance(item, dict) and "preference" in item:
                confidence = item.get("confidence", "medium")
                if confidence not in ["high", "medium", "low"]:
                    confidence = "medium"
                normalized_prefs.append({
                    "preference": str(item["preference"]).strip(),
                    "confidence": confidence
                })
            elif isinstance(item, str):
                # Backward compatibility: convert plain strings
                normalized_prefs.append({
                    "preference": item.strip(),
                    "confidence": "medium"
                })
        normalized["assistant_response_preferences"] = normalized_prefs
    else:
        normalized["assistant_response_preferences"] = []

    # Handle notable_topic_highlights with confidence
    topics = data.get("notable_topic_highlights", [])
    if isinstance(topics, list):
        normalized_topics = []
        for item in topics[:MAX_TOPIC_HIGHLIGHTS]:
            if isinstance(item, dict) and "topic" in item:
                confidence = item.get("confidence", "medium")
                if confidence not in ["high", "medium", "low"]:
                    confidence = "medium"
                normalized_topics.append({
                    "topic": str(item["topic"]).strip(),
                    "confidence": confidence
                })
            elif isinstance(item, str):
                # Backward compatibility: convert plain strings
                normalized_topics.append({
                    "topic": item.strip(),
                    "confidence": "medium"
                })
        normalized["notable_topic_highlights"] = normalized_topics
    else:
        normalized["notable_topic_highlights"] = []

    # Handle helpful_user_insights (simple strings)
    insights = data.get("helpful_user_insights", [])
    if isinstance(insights, str):
        insights = [line.strip(" -•") for line in insights.split("\n") if line.strip()]
    elif not isinstance(insights, list):
        insights = []
    normalized["helpful_user_insights"] = [str(item).strip() for item in insights[:MAX_USER_INSIGHTS] if str(item).strip()]

    return normalized


def _profile_message(profile_sections: dict) -> str:
    """
    Compose a single system message summarizing profile sections.
    Supports both new format (with confidence) and legacy format (plain strings).
    """
    if not profile_sections:
        return ""
    lines = ["User profile from prior chats (do not fabricate beyond this list):"]

    # Assistant Response Preferences (with confidence)
    prefs = profile_sections.get("assistant_response_preferences", [])
    if prefs:
        lines.append("Assistant Response Preferences:")
        for item in prefs:
            if isinstance(item, dict):
                # New format with confidence
                pref = item.get("preference", "")
                confidence = item.get("confidence", "medium")
                lines.append(f"- [{confidence}] {pref}")
            else:
                # Legacy format (plain string)
                lines.append(f"- {item}")

    # Notable Past Conversation Topic Highlights (with confidence)
    topics = profile_sections.get("notable_topic_highlights", [])
    if topics:
        lines.append("Notable Past Conversation Topic Highlights:")
        for item in topics:
            if isinstance(item, dict):
                # New format with confidence
                topic = item.get("topic", "")
                confidence = item.get("confidence", "medium")
                lines.append(f"- [{confidence}] {topic}")
            else:
                # Legacy format (plain string)
                lines.append(f"- {item}")

    # Helpful User Insights (simple strings)
    insights = profile_sections.get("helpful_user_insights", [])
    if insights:
        lines.append("Helpful User Insights:")
        lines.extend([f"- {item}" for item in insights])

    return "\n".join(lines)

async def hist_evaluate(hist_message, current_request):
    """
    Evaluate if the history message is relevant to the latest request.
    Optimized for speed using minimal reasoning.
    """
    command = f"""Is this history relevant to the current request?

History: {hist_message}
Current: {current_request}

Output ONLY: true or false"""

    init_chat = [{"role": "user", "content": command}]

    response = await openai.responses.create(
        model=PROFILE_MODEL,
        reasoning={"effort": "minimal"},  # Changed from "low" to "minimal" for speed
        text={"verbosity": "low"},
        input=init_chat,
    )

    content = response.output_text.lower().strip()
    return content in ["true", "yes", "relevant", "1"]

async def update_profile(user_id: str, hist_input: list):
    """
    Update user profile based on complete conversation history.
    Should be called AFTER assistant response is saved to history.
    """
    hist_cleaned = _clean_history_messages(copy.deepcopy(hist_input))
    profile_path = os.path.join("history", f"{user_id}/profile.json")

    profile_sections = await _profile_sections_from_history(hist_cleaned)
    if profile_sections:
        _save_profile_sections(profile_path, profile_sections, len(hist_cleaned))
        print(f"✅ Profile updated for user {user_id}")

async def hist_handler(user_message, user_id, hist_input):
    hist_cleaned = _clean_history_messages(copy.deepcopy(hist_input))
    hist = hist_cleaned[-TOTAL_HIST_LIMIT:]

    hist_record_pairs = []
    for i in range(0, len(hist), 2):
        pair = hist[i:i+2]
        hist_record_pairs.append(pair)

    short_term_memory = []

    # Load cached profile (do NOT update here - will update after response)
    profile_path = os.path.join("history", f"{user_id}/profile.json")
    cached_profile = _load_profile_sections(profile_path)

    profile_msg = _profile_message(cached_profile)
    if profile_msg:
        short_term_memory.append({"role": "system", "content": profile_msg})

    recent_lines = _recent_conversation_content(hist_cleaned)
    if recent_lines:
        short_term_memory.append({
            "role": "system",
            "content": "Recent conversation content (user-only, newest last):\n" + "\n".join(recent_lines)
        })

    # Short-term memory: always include recent messages without evaluation (faster)
    short_time_pairs = hist_record_pairs[-SHORT_HIST_LIMIT:]
    for pairs in short_time_pairs:
        for record in pairs:
            if isinstance(record.get("content"), list):
                for item in record["content"]:
                    if item.get("type") == "input_image":
                        photo = encode_image(item["image_url"])
                        item["image_url"] = f"data:image/jpeg;base64,{photo}"
        short_term_memory += pairs

    # Processing long time history with parallel evaluation
    long_term_memory = []
    if len(hist_record_pairs) > SHORT_HIST_LIMIT:
        long_time_pairs = hist_record_pairs[:-SHORT_HIST_LIMIT]

        async def evaluate_content(record_pair, user_message):
            if_relevant = await hist_evaluate(str(record_pair), user_message)
            if if_relevant:
                for record in record_pair:
                    if isinstance(record.get("content"), list):
                        for item in record["content"]:
                            if item.get("type") == "input_image":
                                photo = encode_image(item["image_url"])
                                item["image_url"] = f"data:image/jpeg;base64,{photo}"
                return record_pair
            return []

        start = time.time()
        coros_hist_evaluation = [evaluate_content(record_pair, user_message) for record_pair in long_time_pairs]
        results = await asyncio.gather(*coros_hist_evaluation)
        for res in results:
            long_term_memory += res
        e1 = time.time()
        print("---")
        print(f"📚 Hist evaluation: {len(long_time_pairs)} pairs | Cost: {round(e1-start,2)}s")
        print("---")

    return short_term_memory, long_term_memory
