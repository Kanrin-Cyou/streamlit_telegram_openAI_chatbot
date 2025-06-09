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
        input=init_chat,
    )
    if response.output_text.lower() in ["true", "yes", "relevant"]:
        return True
    else:
        return False

async def llm(user_id, user_message, hist_input, photo=None, tools=tools_description):    
        
    medium = []    
    hist = copy.deepcopy(hist_input)[-12:]
    
    hist_record_pairs = []
    for i in range(0, len(hist), 2):
        pair = hist[i:i+2]
        hist_record_pairs.append(pair)

    print("---")
    print(hist_record_pairs)
    print("---")

    #processing long time history
    if (len(hist_record_pairs) > 3):
        long_time_pairs = hist_record_pairs[:-3]
        
        async def evaluate_content(record_pair, user_message):
            if_relevant = await hist_evaluate(str(record_pair), user_message)
            print(if_relevant, record_pair)            
            if if_relevant:
                for record in record_pair:
                    if type(record["content"]) == list:
                        for item in record["content"]:                        
                            if item["type"] == "input_image":
                                photo = encode_image(item["image_url"])
                                item["image_url"] = f"data:image/jpeg;base64,{photo}"
                    medium.append(record)        
        
        start = time.time()
        coros_hist_evaluation = [evaluate_content(record_pair, user_message) for record_pair in long_time_pairs]
        await asyncio.gather(*coros_hist_evaluation)
        e1 = time.time()
        print("---")
        print("evaluated_results")
        print(f"Cost:{round(e1-start,2)}s")
        print("---")

    #processing short time history
    short_time_pairs = hist_record_pairs[-3:] 
    for pairs in short_time_pairs:
        for record in pairs:
            if type(record["content"]) == list:
                for item in record["content"]:                        
                    if item["type"] == "input_image":
                        photo = encode_image(item["image_url"])
                        item["image_url"] = f"data:image/jpeg;base64,{photo}"
            medium.append(record) 
    
    print("---")
    print(hist_record_pairs)
    print("---")


    prompt = """
    You are a helpful AI assistant. When a user asks a question:
    1. If needed, perform a web search to find accurate, up-to-date information.  
    2. If user asks for a specific topic, use the keyword in the language that will yield the best search results.
    3. Provide the URL(s) of the source(s) you consulted.  
    4. If you cannot answer with confidence, reply with 'I don't know'.
    """
    
    medium.append({
        "role": "system",
        "content": prompt,
    })

    medium.append({
        "role": "system",
        "content": f"Current Tokyo time is {get_current_time()}",
    })
    
    if photo is not None:
        medium.append({
            "role": "user",
            "content": [
                { "type": "input_text", "text": user_message},
                {
                    "type": "input_image",
                    "image_url": f"data:image/jpeg;base64,{photo}",
                },
            ],
        })
        stream = await openai.responses.create(
            model="o4-mini",
            input=medium,
            stream=True
        )      
    else:
        medium.append({"role":"user","content":user_message})        
        response = await openai.responses.create(
            model="gpt-4.1-mini",
            input=medium,
            tools=tools,
        )
        
        if (hasattr(response.output[0],"arguments")):
            for tool_call in response.output:
                if tool_call.type != "function_call":
                    continue
                medium.append(tool_call)
                name = tool_call.name
                print(f"Calling function: {name} with arguments: {tool_call.arguments}")
                args = json.loads(tool_call.arguments)
                if name == "web_search":
                    result = await call_function(name, args)                                                         
                else:
                    result = call_function(name, args)
                medium.append({
                    "type": "function_call_output",
                    "call_id": tool_call.call_id,
                    "output": str(result)
                })
            
        stream = await openai.responses.create(
            model="o4-mini",
            input=medium,
            stream=True
        )                
    
    return stream