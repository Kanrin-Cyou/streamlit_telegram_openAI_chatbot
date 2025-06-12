# -*- coding: utf-8 -*-
import os
import json
import copy
import time
import asyncio
import base64
from openai import AsyncOpenAI
from tools.tools_description import tools_description
from tools.general_utils import get_weather, get_current_time, web_crawler
from tools.web_search import web_search
from tools.ytb_transcribe import ytb_transcribe

import configparser
config = configparser.ConfigParser()
config.read('config.ini')
OPENAI_API_KEY = config.get('default', 'OPENAI_API_KEY')
openai = AsyncOpenAI(api_key=OPENAI_API_KEY)

def call_function(name, args):
    if name == "get_weather":
        return get_weather(**args)
    if name == "get_current_time":
        return get_current_time(**args)
    if name == "web_search":
        return web_search(**args)
    if name == "web_crawler":
        return web_crawler(**args)
    if name == "ytb_transcribe":
        return ytb_transcribe(**args)

def encode_image(image_path):
    with open(image_path, "rb") as image_file:
        return base64.b64encode(image_file.read()).decode("utf-8") 

def read_history(user_id: str) -> list:
    
    fn = f"hist_{user_id}.json"
        
    if not os.path.exists(fn):
        init_chat = []
        with open(fn,"w") as f: json.dump(init_chat,f)
    with open(fn) as f:
        return json.load(f)

def write_history(user_id: str, hist: list):
    with open(f"hist_{user_id}.json","w") as f:
        json.dump(hist,f,indent=2,ensure_ascii=False)

async def hist_evaluate(hist_message, current_request):
    """
    Evaluate if the history message is relevant to the latest request.
    """
    command = f"""
        You are a "Relevance Discriminator".
        
        Input:
        hist_message (historical information): "{hist_message}"
        current_request (current user request): "{current_request}"
        
        Current time is {get_current_time}.
        Please determine whether the history contains information that is relevant to or helpful for answering the current_request. 
        Time also should be considered, if the history is too old, it may not be relevant.
        If it is relevant, output only:
        True
        If it is not relevant, output only:
        False
        Do not output any other text, and do not explain your reasoning.
    """
    init_chat = [
        {
            "role": "user",
            "content": command,
        }
    ]
    response = await openai.responses.create(
        model="gpt-4.1-nano",
        temperature=0.3,
        input=init_chat,
    )
    if response.output_text.lower() in ["true", "yes", "relevant"]:
        return True
    else:
        return False

async def llm(user_id, user_message, hist_input, photo=None, tools=tools_description):    
          
    hist = copy.deepcopy(hist_input)[-12:]

    for item in hist:
        if type(item["content"]) == str:
            item["content"] = item["content"].split("🔌 Module Used:")[0]
    
    hist_record_pairs = []
    for i in range(0, len(hist), 2):
        pair = hist[i:i+2]
        hist_record_pairs.append(pair)

    print("---")
    print(hist_record_pairs)
    print("---")

    #processing long time history
    long_term_memory = []
    if (len(hist_record_pairs) > 3):
        long_time_pairs = hist_record_pairs[:-3]
        
        async def evaluate_content(record_pair, user_message):
            if_relevant = await hist_evaluate(str(record_pair), user_message)
            print(if_relevant)            
            if if_relevant:
                for record in record_pair:
                    if type(record["content"]) == list:
                        for item in record["content"]:                        
                            if item["type"] == "input_image":
                                photo = encode_image(item["image_url"])
                                item["image_url"] = f"data:image/jpeg;base64,{photo}"
                    long_term_memory.append(record)        
        
        start = time.time()
        coros_hist_evaluation = [evaluate_content(record_pair, user_message) for record_pair in long_time_pairs]
        await asyncio.gather(*coros_hist_evaluation)
        e1 = time.time()
        print("---")
        print("evaluated_results")
        print(f"Cost:{round(e1-start,2)}s")
        print("---")

    short_term_memory = []
    #processing short time history
    short_time_pairs = hist_record_pairs[-3:] 
    for pairs in short_time_pairs:
        for record in pairs:
            if type(record["content"]) == list:
                if_relevant = await hist_evaluate(str(record), user_message)
                if if_relevant:
                    for item in record["content"]:                        
                        if item["type"] == "input_image":
                            photo = encode_image(item["image_url"])
                            item["image_url"] = f"data:image/jpeg;base64,{photo}"
                else:
                    continue
            short_term_memory.append(record) 
    
    # print("---")
    # print(hist_record_pairs)
    # print("---")


    prompt = """
    You are a helpful AI assistant. When a user asks a question:
    1. If needed, perform a web search to find accurate, up-to-date information.  
    2. If user asks for a specific topic, use the keyword in the language that will yield the best search results.
    3. Provide the URL(s) of the source(s) you consulted.  
    4. If you cannot answer with confidence, reply with 'I don't know'.
    """

    prompt_messages = []
    tool_used = []
    
    prompt_messages.append({
        "role": "system",
        "content": prompt,
    })

    prompt_messages.append({
        "role": "system",
        "content": f"Current Tokyo time is {get_current_time()}",
    })
    
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

    stream = await openai.responses.create(
        model="gpt-4.1-mini",
        temperature=0.1,
        input= long_term_memory + short_term_memory + prompt_messages,
        stream=True,
        tools=tools,
    )

    final_tool_calls = []
    async for event in stream:
        if event.type == 'response.content_part.added':
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

        tool_used.append({f"{name}":f"{arguments}"})
        print(f"Calling function: {name} with arguments: {arguments}")
        
    stream = await openai.responses.create(
        model="gpt-4.1-mini",
        input= long_term_memory + short_term_memory + prompt_messages,
        temperature=0.3,
        stream=True
    )                
    
    return stream, tool_used