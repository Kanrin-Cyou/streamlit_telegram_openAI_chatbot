import streamlit as st

if "authentication_status" not in st.session_state:
    st.session_state.authentication_status = False

login_page = st.Page("view/login.py", title="Log in", icon=":material/login:")
logout_page = st.Page("view/logout.py", title="Log out", icon=":material/logout:")

chat_page = st.Page(
    "view/chat.py", title="Chatbox", icon=":material/dashboard:", default=True
)
# bugs = st.Page("reports/bugs.py", title="Bug reports", icon=":material/bug_report:")
# alerts = st.Page(
#     "reports/alerts.py", title="System alerts", icon=":material/notification_important:"
# )

tools = st.Page("view/tools.py", title="tools", icon=":material/search:")
# history = st.Page("tools/history.py", title="History", icon=":material/history:")

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
