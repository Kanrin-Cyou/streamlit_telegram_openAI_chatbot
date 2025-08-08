import streamlit as st
import asyncio
import time
import json
from llm import llm, reasoning_llm
from hist import read_history, write_history, encode_image
from tools.tools_description import tool_msg_beautify
import sys
from io import BytesIO
import os
from PIL import Image

CHAT_FILE = "chat_list.json"

def check_path(user_id:str):
    if not os.path.exists(f"history/{user_id}"):
        os.makedirs(f"history/{user_id}")

def read_chat_list(user_id:str):
    check_path(user_id)
    if not os.path.exists(f"history/{user_id}/{CHAT_FILE}"):
        with open(f"history/{user_id}/{CHAT_FILE}", 'w') as file:
            json.dump(["default"], file)
    with open(f"history/{user_id}/{CHAT_FILE}", 'r') as file:
        return json.load(file)

def write_chat_list(user_id:str, chat_list):
    with open(f"history/{user_id}/{CHAT_FILE}", 'w') as file:
        json.dump(chat_list, file, indent=4)

def delete_chat(user_id:str, chat_name):
    with open(f"history/{user_id}/{CHAT_FILE}", 'r') as file:
        chat_list = json.load(file)
        i = chat_list.index(chat_name)
        chat_list.pop(i)
        if(len(chat_list)==0):
            write_chat_list(user_id, ["default"])
        else:
            write_chat_list(user_id, chat_list)
        os.remove(f"history/{user_id}/hist_{chat_name}.json")

async def main() -> int:    
    
    # ----------------------- UI Interface ----------------------- 
    # Theme
    st.set_page_config(page_title="Chat with AI", page_icon=":speech_balloon:")
    
    auth_placeholder = st.empty()
    body_placeholder = st.empty()
    body = body_placeholder.container()

    if st.session_state.authentication_status:
        ## ログイン成功
        
        auth_placeholder.empty()
        
        if 'chatbox_names' not in st.session_state:
            st.session_state.chatbox_names = read_chat_list(st.session_state.name)
        if 'active_chat' not in st.session_state:
            st.session_state.active_chat = st.session_state.chatbox_names[0]
        if 'reasoning' not in st.session_state:
            st.session_state.reasoning = False
        if 'reasoning_checkbox' not in st.session_state:
            st.session_state.reasoning_checkbox = False

        # 2. Sidebar: list chatbox name items as a column of buttons        
        
        with st.sidebar:
        
            st.markdown(f'## Welcome *{st.session_state.name}*')
            
            new_chat_name = st.text_input("New Chat Name")

            if st.button("Create New Chat", use_container_width=True):
                body_placeholder.empty()
                st.session_state.chatbox_names.append(new_chat_name)
                write_chat_list(st.session_state.name, st.session_state.chatbox_names)            
                st.session_state.active_chat = new_chat_name
                st.session_state.chat_history = read_history(st.session_state.name, st.session_state.active_chat)
                st.rerun()
            
            option = st.selectbox(
                "Select Chat History",
                st.session_state.chatbox_names,
            )
            if st.button("Enter the Chat", use_container_width=True):
                body_placeholder.empty()
                st.session_state.active_chat = option
                st.session_state.chat_history = read_history(st.session_state.name, st.session_state.active_chat)  
                st.rerun()      

            if st.button("Delete the Chat", use_container_width=True):
                body_placeholder.empty()
                delete_chat(st.session_state.name, option)
                st.session_state.chatbox_names = read_chat_list(st.session_state.name)
                st.session_state.active_chat = st.session_state.chatbox_names[0]
                st.session_state.chat_history = read_history(st.session_state.name, st.session_state.active_chat)
                st.rerun()

            def reasoning_check():
                body_placeholder.empty()
                st.session_state.reasoning = st.session_state.reasoning_checkbox

            st.checkbox(label="Reasoning Mode", key="reasoning_checkbox", on_change = reasoning_check)            

        # 3. Chatbox
        user_input = st.chat_input("Type a message...", accept_file=True, file_type=["jpg", "jpeg", "png"]) 
        
        with body:
            # Conversations
            if "chat_history" not in st.session_state:
                st.session_state.chat_history = read_history(st.session_state.name, st.session_state.active_chat)   
            
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
                
            # New　Message
            if user_input is not None:
                with st.chat_message("user"):
                    placeholder_user = st.empty()
                    print("---")
                    print(user_input.text)
                    print("---")
                    placeholder_user.markdown(user_input.text)
                    photo = None
                    # if input has photo          
                    if user_input["files"]:
                        bytes_data = user_input["files"][0].read()
                        img = Image.open(BytesIO(bytes_data))
                        if not os.path.exists(st.session_state.active_chat):
                            os.mkdir(st.session_state.active_chat)
                        new_file_name = user_input["files"][0].name + '.png'
                        new_file_name = f'{st.session_state.name}/{st.session_state.active_chat}/{new_file_name}'
                        img.save(new_file_name, 'PNG')
                        photo = encode_image(new_file_name)
                        st.image(new_file_name) 
                        hist_user_message = {
                            "role": "user",
                            "content": [
                                {"type": "input_text", "text": user_input.text},
                                {"type": "input_image",
                                "image_url": new_file_name,
                                },
                            ],
                        }
                    else:                   
                        hist_user_message = {          
                            "role": "user",
                            "content": user_input.text
                        }
                
                with st.chat_message("AI"):
                                    
                    # 1. Create two place holder
                    placeholder_reasoning = st.empty()
                    placeholder_output    = st.empty()

                    # 2. initial two buffer
                    reasoning_msg = "### 🧠 Reasoning\n"
                    output_msg    = "### 💬 Output\n"

                    # 3. obtain streaming response
                    start = time.time()
                    if st.session_state.reasoning:
                        stream, tools = await reasoning_llm(user_input.text, st.session_state.chat_history, photo)
                    else:
                        stream, tools = await llm(user_input.text, st.session_state.chat_history, photo)
                    print("---")
                    print(f"Starting Response takes {time.time() - start}s")
                    print("---")
                    
                    # 4. streaming update 
                    async for event in stream:
                        if event.type != "response.reasoning_summary_text.delta" and event.type != "response.output_text.delta":
                            continue
                        delta = event.delta or ""               
                        if event.type == "response.reasoning_summary_text.delta":
                            reasoning_msg += delta
                            placeholder_reasoning.markdown(
                                reasoning_msg
                            )
                        elif event.type == "response.output_text.delta":
                            output_msg += delta
                            placeholder_output.markdown(
                                output_msg
                            )
                            
                    # 5. if tools is used, show which tool is used.
                    if tools:
                        output_msg += "\n\n---\n\n" +  "### 🔌 Module Used \n" + tool_msg_beautify(tools)
                        placeholder_output.markdown(
                            output_msg
                        )
                    
                    # formating the 
                    if len(reasoning_msg) > 20:
                        history_content = reasoning_msg + "\n\n" + output_msg                                 
                    else:
                        history_content = output_msg       

                st.session_state.chat_history.extend([
                    hist_user_message,
                    {          
                        "role": "assistant",
                        "content": history_content
                    }
                ])

                write_history(st.session_state.name, st.session_state.active_chat, st.session_state.chat_history)

if __name__ == "__main__":
    sys.exit(asyncio.run(main()))

# streamlit run main.py