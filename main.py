import streamlit as st
import asyncio
import time
from llm import llm, encode_image, read_history, write_history
from tools.general_utils import get_current_time
import sys
from io import BytesIO
import base64
import os
from PIL import Image

async def main() -> int:

    # ----------------------- Init -----------------------
    user_id = "Allen"
  
    # ----------------------- UI Interface ----------------------- 
    # Theme
    st.set_page_config(page_title="Chat with AI", page_icon=":speech_balloon:")
    st.title("Ask me anything")
      
    # Conversations
    if "chat_history" not in st.session_state:
        st.session_state.chat_history = read_history(user_id)
   
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
        with st.chat_message(user_id):
            print("---")
            print(user_input.text)
            print("---")
            st.markdown(user_input.text)
            photo = None
            # if input has photo          
            if user_input["files"]:
                bytes_data = user_input["files"][0].read()
                img = Image.open(BytesIO(bytes_data))
                if not os.path.exists(user_id):
                    os.mkdir(user_id)
                new_file_name = user_input["files"][0].name + '.png'
                new_file_name = f'{user_id}/{new_file_name}'
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
            stream = await llm(user_id, user_input.text, st.session_state.chat_history, photo)     
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
            placeholder.markdown(temp_msg)
        except Exception as e:
            print("final waiting update failed:", e)
                    
        st.session_state.chat_history.extend([
            user_message,
            {          
                "role": "assistant",
                "content": f"Time:{get_current_time()} \n {temp_msg}"
            }
        ])

        write_history(user_id, st.session_state.chat_history)

if __name__ == "__main__":
    
    sys.exit(asyncio.run(main()))

# streamlit run main.py
