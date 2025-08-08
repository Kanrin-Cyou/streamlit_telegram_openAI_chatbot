import streamlit as st
import streamlit_authenticator as stauth
from view.login import authenticator

def reset_state(*args):
    del st.session_state["name"]
    del st.session_state["chatbox_names"]
    del st.session_state["chat_history"]
    del st.session_state["active_chat"]
    del st.session_state["reasoning"]

st.markdown(f'## Hi *{st.session_state.name}*, Are you sure to logout?')
authenticator.logout('Logout', 'main', callback = reset_state)