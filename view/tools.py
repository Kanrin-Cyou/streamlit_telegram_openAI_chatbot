from tools.decorator import REGISTERED_TOOL_DESCRIPTIONS, TOOL_DISPLAY
import streamlit as st
import pandas as pd

rows = []
for item in REGISTERED_TOOL_DESCRIPTIONS:
    rows.append({
        'name':     TOOL_DISPLAY[item['name']],
        'description':      item['description'],
        'param_props': ','.join(item['parameters']['properties'].keys()),
    })

df = pd.DataFrame(rows)
st.dataframe(df)