"""Streamlit entry point for Fleet PTI Monitoring."""
import streamlit as st

from src.ui import prepare

st.set_page_config(page_title="Fleet PTI Monitoring", page_icon="🚚", layout="wide")
st.sidebar.title("Fleet PTI Monitoring")
navigation = st.navigation([
    st.Page("pages/1_Fleet_Overview.py", title="Fleet overview", default=True),
    st.Page("pages/2_Driver_Consistency.py", title="Driver PTI consistency"),
    st.Page("pages/3_Driver_Profiles.py", title="Driver profiles"),
    st.Page("pages/4_Co_Driver_Analysis.py", title="Co-driver analysis"),
    st.Page("pages/5_Defects_and_Safety.py", title="Defects and safety"),
])
st.session_state["context"] = prepare(
    team_page=navigation.title == "Co-driver analysis",
    consistency_page=navigation.title == "Driver PTI consistency",
)
navigation.run()
