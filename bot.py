import os
import json
import base64
import configparser  
from telethon import TelegramClient, events
from telethon.tl.custom import Button
from PIL import Image
from llm import llm
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
        text = "Welcome Back！openAI API Bot 🤖 is ready。"
        await client.send_message(SENDER_ID, text, parse_mode="md")
    else:
        text = "Welcome to openAI API 🤖！\n\nPlease your password"
        await client.send_message(SENDER_ID, text, parse_mode="md")

# Handling password verification
#@client.on(events.NewMessage(pattern='@bot_name')) 
#if you want to handle messages that mention the bot, so you can added it to a group chat.
#However, you still need to send the password directly to the bot in a private chat.
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
        text = "Correct Password！You now can use the Bot。😊"
        await client.send_message(SENDER_ID, text, parse_mode="md")
    else:
        text = "Wrong Passwrod。Please try again or contact bot owner。"
        await client.send_message(SENDER_ID, text, parse_mode="md")


#
# define the main message handler
#
@client.on(events.NewMessage)
async def gpt(event):
    try:
        
        sender = await event.get_sender()
        SENDER = sender.id
        CHAT_ID = event.message.peer_id
        photo = None

        if not is_user_verified(SENDER):
            text = "Please verify tyour password first, send /start to start。"
            await client.send_message(SENDER, text, parse_mode="md")
            return
        
        request = event.raw_text        

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
            else:
                request = request + reply.raw_text
        
        start = time.time()
        response_text = await llm(str(CHAT_ID), request, photo)
        end = time.time()
        print(f"llm processing time is ${end-start}")

        if(len(response_text) > 4000):
            response_list = textwrap.wrap(response_text, width=4000)
            await session.edit(response_list[0], parse_mode="md")
            for i in range(1, len(response_list)):
                await client.send_message(CHAT_ID, response_list[i], parse_mode="md")
        else:
            await session.edit(response_text, parse_mode="md")
        
    except Exception as e:
        await client.send_message(CHAT_ID, f"Sorry, error：{str(e)}", parse_mode="md")

if __name__ == '__main__':
    print("Bot Started!")
    client.run_until_disconnected()