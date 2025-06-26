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

def encode_image(image_path):
    with open(image_path, "rb") as image_file:
        return base64.b64encode(image_file.read()).decode("utf-8") 

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
        Some of the content includes image_url of photos. I will convert them to base64 later if you consider the session is relevant.
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

async def hist_handler(user_message, hist_input):
                       
    hist = copy.deepcopy(hist_input)[-TOTAL_HIST_LIMIT:]

    for item in hist:
        if type(item["content"]) == str:
            item["content"] = item["content"].split("🔌 Module Used")[0]
    
    hist_record_pairs = []
    for i in range(0, len(hist), 2):
        pair = hist[i:i+2]
        hist_record_pairs.append(pair)

    short_term_memory = []
    #processing short time history
    short_time_pairs = hist_record_pairs[-SHORT_HIST_LIMIT:] 

    # if photo included, first check the relationship.
    # if not, then directly add to memory.
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
                    break
            short_term_memory += pairs   

    #processing long time history
    long_term_memory = []
    if (len(hist_record_pairs) > SHORT_HIST_LIMIT):
        long_time_pairs = hist_record_pairs[:-SHORT_HIST_LIMIT]
        
        async def evaluate_content(record_pair, user_message):
            if_relevant = await hist_evaluate(str(record_pair), user_message)         
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
        print("hist_evaluation")
        print(f"Cost:{round(e1-start,2)}s")
        print("---")
    
    return short_term_memory, long_term_memory
