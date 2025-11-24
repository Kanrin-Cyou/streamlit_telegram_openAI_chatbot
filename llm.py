# -*- coding: utf-8 -*-
import os
import json
import re
import time
from openai import AsyncOpenAI
from hist import hist_handler
from tools.general_utils import get_current_time
from tools.tools_description import call_function
from tools.decorator import REGISTERED_TOOL_DESCRIPTIONS

from dotenv import load_dotenv
load_dotenv()
openai = AsyncOpenAI(api_key=os.environ.get("OPENAI_API_KEY"))
tools_description = REGISTERED_TOOL_DESCRIPTIONS

# Model configuration
MODEL_NANO = "gpt-5-nano"    # High-throughput tasks, simple instruction-following or classification
MODEL_MINI = "gpt-5-mini"    # Cost-optimized reasoning and chat; balances speed, cost, and capability
MODEL_STANDARD = "gpt-5.1"   # Complex reasoning, broad world knowledge, code-heavy or multi-step agentic tasks

async def select_model_and_reasoning(user_message: str, has_tools: bool = True) -> tuple[str, str, str]:
    """
    Use a small model to intelligently select the best model, reasoning effort, and verbosity.

    Args:
        user_message: The user's input message
        has_tools: Whether tools are available for this request

    Returns:
        Tuple of (model_name, reasoning_effort, verbosity)
    """

    selection_prompt = f"""You are a model selector. Analyze the user's query and return ONLY a JSON object with three fields:

Available models (all support: minimal, low, medium, high):
- "gpt-5-nano": High-throughput tasks, simple instruction-following or classification (fastest, cheapest)
- "gpt-5-mini": Cost-optimized reasoning and chat; balances speed, cost, and capability (balanced)
- "gpt-5.1": Complex reasoning, broad world knowledge, code-heavy or multi-step agentic tasks (most capable)
  ONLY gpt-5.1 also supports "none" reasoning

- "reasoning": one of "minimal" (fastest), "low", "medium", "high" (use "none" ONLY for gpt-5.1)
- "verbosity": one of "low" (concise), "medium" (balanced), or "high" (detailed)

Selection guidelines:
- Simple greetings/acknowledgments (<50 chars): {{"model": "gpt-5-nano", "reasoning": "minimal", "verbosity": "low"}}
- Simple factual questions: {{"model": "gpt-5-nano", "reasoning": "minimal", "verbosity": "low"}}
- General conversation/chat: {{"model": "gpt-5-mini", "reasoning": "minimal", "verbosity": "medium"}}
- Tool usage (search, weather, youtube): {{"model": "gpt-5-mini", "reasoning": "low", "verbosity": "low"}}
- Basic explanation/summarization: {{"model": "gpt-5-mini", "reasoning": "low", "verbosity": "medium"}}
- Complex analysis/comparison: {{"model": "gpt-5.1", "reasoning": "medium", "verbosity": "medium"}}
- Coding/debugging tasks: {{"model": "gpt-5.1", "reasoning": "high", "verbosity": "medium"}}
- Multi-step reasoning: {{"model": "gpt-5.1", "reasoning": "medium", "verbosity": "medium"}}
- Very simple queries that need fastest response: {{"model": "gpt-5.1", "reasoning": "none", "verbosity": "low"}}

User query: "{user_message}"

Return ONLY the JSON object, no other text."""

    try:
        response = await openai.responses.create(
            model="gpt-5-nano",  # Use fast model for selection
            reasoning={"effort": "minimal"},  # Minimal reasoning for fast classification
            text={"verbosity": "low"},
            input=[{"role": "user", "content": selection_prompt}],
        )

        result_text = response.output_text.strip()
        # Extract JSON from response (in case model adds extra text)
        json_match = re.search(r'\{[^}]+\}', result_text)
        if json_match:
            result_text = json_match.group(0)

        selection = json.loads(result_text)
        model = selection.get("model", MODEL_MINI)
        reasoning = selection.get("reasoning", "minimal")
        verbosity = selection.get("verbosity", "medium")

        # Validate values
        if model not in [MODEL_NANO, MODEL_MINI, MODEL_STANDARD]:
            model = MODEL_MINI  # Default to balanced model

        # Validate reasoning based on model
        if model == MODEL_STANDARD:
            # gpt-5.1 supports none, minimal, low, medium, high
            if reasoning not in ["none", "minimal", "low", "medium", "high"]:
                reasoning = "none"
        else:
            # nano and mini only support minimal, low, medium, high (no "none")
            if reasoning not in ["minimal", "low", "medium", "high"]:
                reasoning = "minimal"

        if verbosity not in ["low", "medium", "high"]:
            verbosity = "medium"

        # IMPORTANT: web_search tool requires reasoning >= "low"
        # If reasoning is "minimal" or "none", upgrade to "low" when tools are available
        if has_tools and reasoning in ["minimal", "none"]:
            reasoning = "low"
            print(f"⚠️ Upgraded reasoning to 'low' (required for web_search tool)")

        # Determine emoji based on model and reasoning level
        emoji_map = {
            (MODEL_NANO, "minimal"): "⚡",
            (MODEL_NANO, "low"): "⚡",
            (MODEL_MINI, "minimal"): "💬",
            (MODEL_MINI, "low"): "🔧",
            (MODEL_STANDARD, "none"): "⚡",  # fastest option for 5.1
            (MODEL_STANDARD, "minimal"): "📊",
            (MODEL_STANDARD, "low"): "⚙️",
            (MODEL_STANDARD, "medium"): "🧠",
            (MODEL_STANDARD, "high"): "💻",
        }
        emoji = emoji_map.get((model, reasoning), "📊")

        print(f"{emoji} Model: {model} | Reasoning: {reasoning} | Verbosity: {verbosity}")
        return model, reasoning, verbosity

    except Exception as e:
        # Fallback to safe defaults if selection fails
        print(f"⚠️ Model selection failed ({str(e)}), using defaults")
        # Use "low" reasoning when tools are available (required for web_search)
        fallback_reasoning = "low" if has_tools else "minimal"
        print(f"💬 Model: {MODEL_MINI} | Reasoning: {fallback_reasoning} | Verbosity: medium")
        return MODEL_MINI, fallback_reasoning, "medium"

def assemble_photo_request(prompt_messages, user_message, photo):
    if photo is not None:
        prompt_messages.append({
            "role": "user",
            "content": [
                { "type": "text_content", "text": user_message},
                {
                    "type": "input_image",
                    "image_url": f"data:image/jpeg;base64,{photo}",
                },
            ],
        })
    else:
        prompt_messages.append({"role":"user","content":user_message})

    return prompt_messages

    
async def llm(user_message, user_id, hist_input, photo=None):                

    prompt = """
    You are a helpful AI assistant. 
    """

    prompt_messages = []
    tool_used = []
    short_term_memory, long_term_memory = await hist_handler(user_message, user_id, hist_input)

    prompt_messages = assemble_photo_request(prompt_messages, user_message, photo)

    # Debug: print message count instead of full content
    # print(short_term_memory + prompt_messages)  # Commented out to avoid JSON output
    print(f"📝 Context loaded: {len(short_term_memory)} system messages, {len(prompt_messages)} user messages")

    # Select appropriate model, reasoning effort, and verbosity based on query complexity
    selected_model, reasoning_effort, verbosity = await select_model_and_reasoning(user_message, has_tools=True)

    stream = await openai.responses.create(
        model=selected_model,
        text={
            "verbosity": verbosity
        },
        reasoning={
            "effort": reasoning_effort
        },
        instructions= f"Current Tokyo time is {get_current_time()}. " + prompt,
        input= short_term_memory + long_term_memory + prompt_messages,
        tools= tools_description + [{ "type": "web_search_preview" }],
        stream=True,
    )

    final_tool_calls = []
    async for event in stream:
        print(event.type)
        if event.type == 'response.content_part.added':
            # No Tool is needed, the response is the answer, thus directly return the stream object
            return stream, tool_used
        if event.type == 'response.output_item.added':
            final_tool_calls.append(event.item)
        elif event.type == 'response.function_call_arguments.delta':
            index = event.output_index
            if final_tool_calls[index]:
                final_tool_calls[index].arguments += event.delta
    
    print(f"Final Tool call: {final_tool_calls}")

    tool_used = []
    for tool_call in final_tool_calls:
        print(tool_call.type)
        if tool_call.type == "reasoning":
            prompt_messages.append(tool_call)
        if tool_call.type == "function_call":
            call_id = tool_call.call_id
            name = tool_call.name
            arguments = tool_call.arguments
            args = json.loads(arguments)
            if name == "web_search":
                result = await call_function(name, args)                                                         
            else:
                result = call_function(name, args)
            
            prompt_messages.append(tool_call)
            prompt_messages.append({
                "type": "function_call_output",
                "call_id": call_id,
                "output": str(result)
            })

            tool_used.append({"name":f"{name}", "arguments":f"{arguments}"})
            print(f"Calling function: {name} with arguments: {arguments}")

    # Return empty stream
    stream = await openai.responses.create(
        model=selected_model,
        text={"verbosity": verbosity},
        reasoning={"effort": reasoning_effort},
        instructions= f"Current Tokyo time is {get_current_time()}. " + prompt,
        input= short_term_memory + long_term_memory + prompt_messages,
        stream=True,
    )
    return stream, tool_used