import streamlit as st
import asyncio
import time
import json
from llm import llm, encode_image, read_history, write_history
from tools.general_utils import get_current_time
import sys
from io import BytesIO
import os
from PIL import Image

CHAT_FILE = "chat_list.json"

def read_chat_list():
    if not os.path.exists(CHAT_FILE):
        with open(CHAT_FILE, 'w') as file:
            json.dump(["default"], file)
    with open(CHAT_FILE, 'r') as file:
        return json.load(file)

def write_chat_list(chat_list):
    with open(CHAT_FILE, 'w') as file:
        json.dump(chat_list, file, indent=4)

def delete_chat(chat_name):
    with open(CHAT_FILE, 'r') as file:
        chat_list = json.load(file)
        i = chat_list.index(chat_name)
        chat_list.pop(i)
        if(len(chat_list)==0):
            write_chat_list(["default"])
        else:
            write_chat_list(chat_list)
        os.remove(f"hist_{chat_name}.json")

async def main() -> int:
    
    # ----------------------- UI Interface ----------------------- 
    # Theme
    st.set_page_config(page_title="Chat with AI", page_icon=":speech_balloon:")
    
    if 'chatbox_names' not in st.session_state:
        st.session_state.chatbox_names = read_chat_list()
    if 'active_chat' not in st.session_state:
        st.session_state.active_chat = st.session_state.chatbox_names[0]

    # 2. Sidebar: list chatbox name items as a column of buttons
    with st.sidebar:
        st.header(f"Current Chat: {st.session_state.active_chat}")
        new_chat_name = st.text_input("New Chat")
        if st.button("Create a New Chat", use_container_width=True):
            st.session_state.chatbox_names.append(new_chat_name)
            write_chat_list(st.session_state.chatbox_names)
            st.session_state.active_chat = new_chat_name
            st.session_state.chat_history = read_history(st.session_state.active_chat)
            st.rerun()
        
        option = st.selectbox(
            "Select Chat History",
            st.session_state.chatbox_names,
        )
        if st.button("Enter the Chat", use_container_width=True):
            st.session_state.active_chat = option
            st.session_state.chat_history = read_history(st.session_state.active_chat)
        if st.button("Delete the Chat", use_container_width=True):
            delete_chat(option)
            st.session_state.chatbox_names = read_chat_list()
            st.session_state.active_chat = st.session_state.chatbox_names[0]
            st.session_state.chat_history = read_history(st.session_state.active_chat)        

    # Conversations
    if "chat_history" not in st.session_state:
        st.session_state.chat_history = read_history(st.session_state.active_chat)   
    
    st.title(st.session_state.active_chat)
    for message in st.session_state.chat_history:
        if type(message["content"]) == list:
            for item in message["content"]:
                if item["type"] == "input_text":
                    with st.chat_message("user"):
                        st.markdown(item["text"])
                if item["type"] == "input_image":
                    with st.chat_message("user"):
                        st.image(item["image_url"])
        elif message["role"] == "system":
            continue
        elif message["role"] == "user":
            with st.chat_message("user"):
                st.markdown(message["content"])
        else:
            with st.chat_message("AI"):
                st.markdown(message["content"])

    user_input = st.chat_input("Type a message...", accept_file=True, file_type=["jpg", "jpeg", "png"])
    if user_input is not None:         
        with st.chat_message("user"):
            print("---")
            print(user_input.text)
            print("---")
            st.markdown(user_input.text)
            photo = None
            # if input has photo          
            if user_input["files"]:
                bytes_data = user_input["files"][0].read()
                img = Image.open(BytesIO(bytes_data))
                if not os.path.exists(st.session_state.active_chat):
                    os.mkdir(st.session_state.active_chat)
                new_file_name = user_input["files"][0].name + '.png'
                new_file_name = f'{st.session_state.active_chat}/{new_file_name}'
                img.save(new_file_name, 'PNG')
                photo = encode_image(new_file_name)
                st.image(new_file_name) 
                user_message = {
                    "role": "user",
                    "content": [
                        {"type": "input_text", "text": user_input.text},
                        {"type": "input_image",
                         "image_url": new_file_name,
                        },
                    ],
                }
            else:                   
                user_message = {          
                    "role": "user",
                    "content": user_input.text
                }            
          
        with st.chat_message("AI"):
            start = time.time()
            stream = await llm(st.session_state.active_chat, user_input.text, st.session_state.chat_history, photo)     
            end = time.time()            
            print("---")
            print(f"Starting Response takes {end-start}s")
            print("---")
            placeholder = st.empty()
            placeholder.markdown("Thinking...")
            temp_msg = ""
            previous_total_length = 0 
            update_threshold = 0 

            async for event in stream:
                if event.type == "response.output_text.delta":
                    delta = event.delta
                    if delta is None:
                        delta = ""
                    temp_msg += delta
                    if len(temp_msg) - previous_total_length >= update_threshold:
                        try:
                            placeholder.markdown(temp_msg)
                        except Exception as e:
                            print("Streaming Message Error:", e)
                        previous_total_length = len(temp_msg)
                    
            try:
                temp_msg = temp_msg + "\n\n" + f"[Answered at: {get_current_time()}]"
                placeholder.markdown(temp_msg)
            except Exception as e:
                print("final waiting update failed:", e)
                    
        st.session_state.chat_history.extend([
            user_message,
            {          
                "role": "assistant",
                "content": temp_msg
            }
        ])

        write_history(st.session_state.active_chat, st.session_state.chat_history)

if __name__ == "__main__":
    
    sys.exit(asyncio.run(main()))

# streamlit run main.py