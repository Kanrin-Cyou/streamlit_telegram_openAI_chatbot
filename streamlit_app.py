import streamlit as st

if "authentication_status" not in st.session_state:
    st.session_state.authentication_status = False

login_page = st.Page("view/login.py", title="Log in", icon=":material/login:")
logout_page = st.Page("view/logout.py", title="Log out", icon=":material/logout:")

chat_page = st.Page(
    "view/chat.py", title="Chatbox", icon=":material/dashboard:", default=True
)

tools = st.Page("view/tools.py", title="tools", icon=":material/search:")

if st.session_state.authentication_status:
    pg = st.navigation(
        {
            "Account": [logout_page],
            "ChatBox": [chat_page],
            "Tools": [tools],
        }
    )
else:
    pg = st.navigation([login_page])

pg.run()
