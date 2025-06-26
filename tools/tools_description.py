from tools.general_utils import get_weather, get_current_time, web_crawler
from tools.web_search import web_search
from tools.ytb_transcribe import ytb_transcribe

TOOL_MAPPING = {
    "get_weather":"🌤️ Weather",
    "get_current_time":"⌚️ Time",
    "web_search":"🚀 Search Engine",
    "web_crawler":"📦 Web Crawler",
    "ytb_transcribe":"📺 Youtube Transcribe"
}

def tool_msg_beautify(tools):
    new_msg = ""
    for tool in tools:
        print(tool)
        name = tool["name"]
        arguments = tool["arguments"]
        if name in TOOL_MAPPING:
            name = TOOL_MAPPING[name]
        new_msg = new_msg + "\n\n" + "- " + name + "\n\n" + "\t\t -" + " 💾 Input: "+ arguments  
    return new_msg

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

tools_description = [
    {
        "type": "function",
        "name": "web_search",
        "description": "Use web search engine to get the content of websites related to the keyword, and return the content of these websites. Use this function when user input has a keyword. If you cannot find the answer, just reply cannot find the answer", 
        "parameters": {
            "type": "object",
            "properties": {
                "keywords": {"type": "string"},
                "question": {"type": "string", "description": "The question to be answered based on the search results, use the same language as the keywords."},
            },
            "required": ["keywords", "question"],
            "additionalProperties": False
        },
        "strict": True
    },
    {
    "type": "function",
    "name": "get_weather",
    "description": "Get weather data for provided coordinates in celsius.",
    "parameters": {
        "type": "object",
        "properties": {
            "latitude": {"type": "number"},
            "longitude": {"type": "number"}
        },
        "required": ["latitude", "longitude"],
        "additionalProperties": False
        },
    "strict": True
    },
    {
    "type": "function",
    "name": "get_current_time",
    "description": "Get current time in a timezone, default is Tokyo Time.", 
    "parameters": {
        "type": "object",
        "properties": {
            "time_zone_hours": {"type": "number"}
        },
        "required": ["time_zone_hours"],
        "additionalProperties": False
    },
    "strict": True
    },
    {
        "type": "function",
        "name": "web_crawler",
        "description": "Get a website content by using request and BeautifulSoup. Use this function when user input has a url.", 
        "parameters": {
            "type": "object",
            "properties": {
                "website_url": {"type": "string"}
            },
            "required": ["website_url"],
            "additionalProperties": False
        },
        "strict": True
    },
    {
        "type": "function",
        "name": "ytb_transcribe",
        "description": "From YouTube video to extract transcription or audio and transcript it to text, support:- https://www.youtube.com/watch?v=videoID - http://youtube.com/watch?v=videoID - https://youtu.be/videoid with other parameters &t=30s、&list=… etc.", 
        "parameters": {
            "type": "object",
            "properties": {
                "url": {"type": "string"}
            },
            "required": ["url"],
            "additionalProperties": False
        },
        "strict": True
    },
]

