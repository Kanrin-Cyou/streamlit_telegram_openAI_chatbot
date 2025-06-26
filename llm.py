# -*- coding: utf-8 -*-
import os
import json
from openai import AsyncOpenAI
from hist import hist_handler
from tools.general_utils import get_current_time
from tools.tools_description import tools_description, call_function

from dotenv import load_dotenv

load_dotenv()
openai = AsyncOpenAI(api_key=os.environ.get("OPENAI_API_KEY"))

def assemble_photo_request(prompt_messages, user_message, photo):
    if photo is not None:
        prompt_messages.append({
            "role": "user",
            "content": [
                { "type": "input_text", "text": user_message},
                {
                    "type": "input_image",
                    "image_url": f"data:image/jpeg;base64,{photo}",
                },
            ],
        })
    else:
        prompt_messages.append({"role":"user","content":user_message}) 

    return prompt_messages

async def reasoning_llm(user_message, hist_input, photo=None):        
    
    prompt_messages = []
    prompt_messages = assemble_photo_request(prompt_messages, user_message, photo)
    
    short_term_memory, long_term_memory = await hist_handler(user_message, hist_input)

    stream = await openai.responses.create(
        model="o4-mini",
        input= short_term_memory + prompt_messages,
        reasoning={
            "effort": "high",
            "summary": "detailed"
        },
        stream=True
    )
    return stream, []  

    
async def llm(user_message, hist_input, photo=None):                

    prompt = """
    You are a helpful AI assistant. When a user asks a question:
    1. If needed, perform a web search to find accurate, up-to-date information.  
    2. If user asks for a specific topic, use the keyword in the language that will yield the best search results.
    3. Provide the URL(s) of the source(s) you consulted.  
    4. If you cannot answer with confidence, reply with 'I don't know'.
    """

    prompt_messages = []
    tool_used = []
    short_term_memory, long_term_memory = await hist_handler(user_message, hist_input)

    prompt_messages.append({
        "role": "system",
        "content": prompt,
    })

    prompt_messages.append({
        "role": "system",
        "content": f"Current Tokyo time is {get_current_time()}",
    })
    
    prompt_messages = assemble_photo_request(prompt_messages, user_message, photo)

    print(short_term_memory + prompt_messages)

    stream = await openai.responses.create(
        model="gpt-4.1-mini",
        temperature=0.1,
        input= short_term_memory + prompt_messages,
        stream=True,
        tools= tools_description,
    )
    
    final_tool_calls = []
    async for event in stream:
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
        
    stream = await openai.responses.create(
        model="gpt-4.1-mini",
        input= long_term_memory + short_term_memory + prompt_messages,
        temperature=0.3,
        stream=True
    )                
    
    return stream, tool_used