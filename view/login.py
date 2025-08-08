
import streamlit as st
import streamlit_authenticator as stauth

import yaml
from yaml.loader import SafeLoader

yaml_path = "auth_tools/config.yaml"

with open(yaml_path) as file:
    config = yaml.load(file, Loader=SafeLoader)

authenticator = stauth.Authenticate(
    credentials=config['credentials'],
    cookie_name=config['cookie']['name'],
    cookie_key=config['cookie']['key'],
    cookie_expiry_days=config['cookie']['expiry_days'],
)

## UI 
authenticator.login()
# if st.session_state.authentication_status:
#     st.write('# Login Successful!')

if st.session_state.authentication_status is False:
    ## ログイン成功ログイン失敗
    st.error('Username/password is incorrect')

if st.session_state.authentication_status is None:
    ## デフォルト
    st.warning('Please enter your username and password')