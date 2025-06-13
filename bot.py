import os
import json
import base64
import asyncio
import configparser  
from telethon import TelegramClient, events
from telethon.tl.custom import Button
from PIL import Image
from llm import llm, read_history, write_history, tool_msg_beautify
from tools.general_utils import get_current_time
import textwrap
import time

#
# Configuration and init Telegram client
#
config = configparser.ConfigParser()
config.read('config.ini')
api_id = config.get('default', 'api_id')
api_hash = config.get('default', 'api_hash')
BOT_TOKEN = config.get('default', 'BOT_TOKEN')
ACCESS_PASSWORD = config.get('default','ACCESS_PASSWORD')

client = TelegramClient('gptsession', api_id, api_hash).start(bot_token=BOT_TOKEN)

VERIFIED_USERS_FILE = 'verified_users.json'

def read_verified_users():
    if not os.path.exists(VERIFIED_USERS_FILE):
        with open(VERIFIED_USERS_FILE, 'w') as file:
            json.dump([], file)
    with open(VERIFIED_USERS_FILE, 'r') as file:
        return json.load(file)

def write_verified_users(verified_users):
    with open(VERIFIED_USERS_FILE, 'w') as file:
        json.dump(verified_users, file, indent=4)

def is_user_verified(user_id):
    verified_users = read_verified_users()
    return user_id in verified_users

def ensure_supported_image(file_path):
    supported_extensions = ['.png']
    filename, ext = os.path.splitext(file_path)
    if ext.lower() not in supported_extensions:
        new_file_path = filename + '.png'
        try:
            img = Image.open(file_path)
            img.save(new_file_path, 'PNG')
            print(f"converted image to {new_file_path}")
            return new_file_path
        except Exception as e:
            raise Exception(f"Faile to conver image: {str(e)}")
    return file_path

def encode_image(image_path):
    with open(image_path, "rb") as image_file:
        return base64.b64encode(image_file.read()).decode("utf-8")

#
# define the start command handler
#
@client.on(events.NewMessage(pattern='(?i)/start'))
async def start(event):
    sender = await event.get_sender()
    SENDER_ID = sender.id
    verified_users = read_verified_users()
    
    if SENDER_ID in verified_users:
        text = "Welcome Back! OpenAI API ChatBot 🤖 is ready."
        await client.send_message(SENDER_ID, text, parse_mode="md")
    else:
        text = "Welcome to OpenAI API ChatBot 🤖！\n\nPlease input your password"
        await client.send_message(SENDER_ID, text, parse_mode="md")

# Handling password verification
@client.on(events.NewMessage)
async def handle_password(event):
    sender = await event.get_sender()
    SENDER_ID = sender.id
    message = event.raw_text.strip()
    verified_users = read_verified_users()
    
    if SENDER_ID in verified_users:
        return
    
    if message.startswith('/'):
        return
    
    if message == ACCESS_PASSWORD:
        verified_users.append(SENDER_ID)
        write_verified_users(verified_users)
        text = "Correct Password! You now can use the Bot.😊"
        await client.send_message(SENDER_ID, text, parse_mode="md")
    else:
        text = "Wrong Passwrod. Please try again or contact bot owner."
        await client.send_message(SENDER_ID, text, parse_mode="md")


#
# define the main message handler
#
#@client.on(events.NewMessage(pattern='@bot_name')) 
#if you want to handle messages that mention the bot, so you can added it to a group chat.
#However, you still need to send the password directly to the bot in a private chat.
@client.on(events.NewMessage)
async def gpt(event):
    try:        
        sender = await event.get_sender()
        SENDER = sender.id
        CHAT_ID = event.message.peer_id
        photo = None

        hist = read_history(CHAT_ID)

        if not is_user_verified(SENDER):
            text = "Please verify your password first, send /start to start."
            await client.send_message(SENDER, text, parse_mode="md")
            return
        
        request = event.raw_text        
        # if you use @bot_name as a trigger, remove it before processing the request
        # request = request.removeprefix('@bot_name')
        print(request)

        if(request==ACCESS_PASSWORD):
            return
        
        session = await client.send_message(CHAT_ID, "Thinking ...", parse_mode="md")
        if event.is_reply:            
            reply = await event.get_reply_message()
            if reply.photo:
                file_path = await reply.download_media()
                file_path = ensure_supported_image(file_path)
                photo = encode_image(file_path)
                user_message = {
                    "role": "user",
                    "content": [
                        {"type": "input_text", "text": request},
                        {"type": "input_image",
                         "image_url": file_path,
                        }
                    ],
                }
            else:
                request = request + reply.raw_text
                user_message = {
                    "role": "user",
                    "content": request
                }
        else:
            user_message = {
                "role": "user",
                "content": request
            }
        
        start = time.time()
        stream, tools = await llm(str(CHAT_ID), request, hist, photo)
        end = time.time()
        
        print("---")
        print(f"Starting Response takes ${end-start}s")
        print("---")

        temp_msg = ""
        previous_total_length = 0 
        update_threshold = 100 # update every 100 characters

        async for event in stream:
            if event.type == "response.output_text.delta":
                delta = event.delta
                if delta is None:
                    delta = ""
                temp_msg += delta
                msg_queue = []
                if len(temp_msg) > 4000:
                    # Telegram message size limit is 4096 characters
                    response_list = textwrap.fill(temp_msg, width=4000)
                    msg_queue.append(response_list[0])                                      
                    temp_msg = response_list[1]                    
                    session = await client.send_message(CHAT_ID, " ", parse_mode="md")                                    

                if len(temp_msg) - previous_total_length >= update_threshold:
                    try:
                        await session.edit(temp_msg)
                    except Exception as e:
                        print("Streaming Message Error:", e)
                    previous_total_length = len(temp_msg)
                    await asyncio.sleep(0.5)
                
        try:
            temp_msg = temp_msg + "\n\n" + f"🔌 Module Used: {tool_msg_beautify(tools)}"
            if len(temp_msg) > 4000:
                response_list = textwrap.fill(temp_msg, width=4000)
                await session.edit(response_list[0])
                await client.send_message(CHAT_ID, response_list[1], parse_mode="md")   
            else:                
                await session.edit(temp_msg)
            msg_queue.append(temp_msg)
        except Exception as e:
            print("final update failed:", e)        

        response = ""
        for item in msg_queue:
            response = response + item
        hist.extend([
            user_message,
            {          
                "role": "assistant",
                "content": f"Time:{get_current_time()} \n {response}"
            }
        ])            

        write_history(CHAT_ID, hist)
        
    except Exception as e:
        await client.send_message(CHAT_ID, f"Sorry, error: {str(e)}", parse_mode="md")

if __name__ == '__main__':
    print("Bot Started!")
    client.run_until_disconnected()