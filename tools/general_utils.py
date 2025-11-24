import re
import requests
import subprocess
from datetime import datetime, timezone, timedelta
from bs4 import BeautifulSoup
import aiohttp
import asyncio
from tools.decorator import tool

@tool(
    name = "get_weather",
    description = "Get weather data for provided coordinates in celsius.",
    parameters = {
        "type": "object",
        "properties": {
            "latitude": {"type": "number"},
            "longitude": {"type": "number"}
        },
        "required": ["latitude", "longitude"],
        "additionalProperties": False
        },
    strict = True,
    display_name = "🌤️ Weather"
)
def get_weather(latitude, longitude):
    response = requests.get(f"https://api.open-meteo.com/v1/forecast?latitude={latitude}&longitude={longitude}&hourly=temperature_2m,weather_code,rain")
    data = response.json()
    return data

@tool(
    name = "get_current_time",
    description = "Get current time in a timezone, default is Tokyo Time.", 
    parameters = {
        "type": "object",
        "properties": {
            "time_zone_hours": {"type": "number"}
        },
        "required": ["time_zone_hours"],
        "additionalProperties": False
    },
    strict = True,
    display_name = "⌚️ Time"
)
def get_current_time(time_zone_hours=9) -> str:
    tz = timezone(timedelta(hours=time_zone_hours))
    return datetime.now(tz).strftime("%Y-%m-%d %H:%M:%S")

@tool(
    name = "web_crawler",
    description =  "Get a website text by using request and BeautifulSoup. Use this function when user input has a url. Get a website text by using request and BeautifulSoup. Use this function when user input has a url. Do not use for youtube or weixin or wechat website.",
    parameters = {
        "type": "object",
        "properties": {
            "website_url": {"type": "string"}
        },
        "required": ["website_url"],
        "additionalProperties": False
    },
    strict = True,
    display_name = "📦 Web Crawler"
)
def web_crawler(website_url) -> str:
    try:
        response = requests.get(website_url)
        if response.status_code == 200:
            soup = BeautifulSoup(response.text, "html.parser")
            text = soup.get_text(separator="\n", strip=True)
            return text
        else:
            print("Unable to obtain website content, status code:", response.status_code)
    except Exception as e:
        print("Request Failed", str(e))
    return None

def get_website_http_status(website_url: str) -> str:
    try:
        proc = subprocess.run(
            [
                "curl",
                "-L",                    # follow redirects
                "-o", "/dev/null",       # discard response body
                "-k",                    # ignore SSL certificate errors
                "-s",                    # silent mode (no progress meter)
                "-w", "%{http_code}",    # write out only the HTTP status code
                website_url
            ],
            check=True,
            capture_output=True,
            text=True
        )
        print(proc.stdout.strip())
        return proc.stdout.strip()
    except subprocess.CalledProcessError as e:
        return f"Error: curl command failed with exit code {e.returncode}"

async def async_web_crawler(website_url) -> str:
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(website_url, timeout=5) as response:
                if response.status == 200:
                    html = await response.text()
                    soup = BeautifulSoup(html, "html.parser")
                    text = soup.get_text(separator="\n", strip=True)
                    return text
                else:
                    print(f"Unable to obtain website content, status code: {response.status}")
    except asyncio.TimeoutError:
        print("Request timed out.")
    except Exception as e:
        print("Request Failed", e)

    return None

