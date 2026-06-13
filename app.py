import streamlit as st
import pandas as pd
import base64
import os
from pymongo import MongoClient

st.set_page_config(
    page_title="Kayfa Analytics | Academic Dashboard",
    page_icon="assets/Kayfa.png",
    layout="wide",
    initial_sidebar_state="expanded"
)


st.session_state.colors = {
    "primary": "#2563EB",      
    "secondary": "#93C5FD",    
    "slate": "#0F172A",        
    "alert": "#E11D48",        
    "neutral": "#E2E8F0"       
}


custom_css = """
<style>
    .block-container { padding-top: 2rem !important; }
    header[data-testid="stHeader"] { background-color: transparent !important; }
    
    .kayfa-navbar {
        background: linear-gradient(135deg, #0F172A 0%, #1E3A8A 50%, #2563EB 100%);
        border-radius: 12px;
        padding: 30px 40px;
        display: flex;
        align-items: center;
        justify-content: space-between;
        box-shadow: 0 20px 25px -5px rgba(0, 0, 0, 0.1), 0 10px 10px -5px rgba(0, 0, 0, 0.04);
        margin-bottom: 30px;
        color: white;
    }
    .kayfa-navbar-left { flex: 1; padding-right: 30px; }
    .kayfa-navbar h1 {
        color: #FFFFFF !important; margin: 0 0 8px 0 !important;
        padding: 0 !important; font-size: 32px !important; font-weight: 700 !important;
    }
    .week-badge { font-size: 20px; color: #93C5FD; font-weight: 400; margin-left: 10px; }
    .kayfa-navbar p {
        color: #CBD5E1 !important; margin: 0 !important;
        font-size: 16px !important; line-height: 1.6 !important; font-weight: 400 !important;
    }
    .kayfa-navbar-right { display: flex; align-items: center; justify-content: flex-end; }
    .kayfa-navbar-right img { filter: drop-shadow(0px 4px 6px rgba(0,0,0,0.3)); }
</style>
"""
st.markdown(custom_css, unsafe_allow_html=True)


from tabs import academics, engagement, trends, concepts, advanced, admin, growth, integrity


@st.cache_data
def load_sidebar_filters():
    try:
        data = list(db["unified_roster"].find({}, {"_id": 0, "course_name": 1, "group_id": 1}))
        df_roster = pd.DataFrame(data)
        return ["All Courses"] + sorted(df_roster['course_name'].dropna().unique().tolist()), ["All Groups"] + sorted(df_roster['group_id'].dropna().unique().tolist())
    except Exception:
        return ["All Courses"], ["All Groups"]

filter_courses_list, filter_groups_list = load_sidebar_filters()

with st.sidebar:
    st.image("assets/Kayfa.svg", use_container_width=True)
    st.markdown("<br>", unsafe_allow_html=True)
    selected_course = st.selectbox("Course Filter", filter_courses_list)
    selected_group = st.selectbox("Cohort Filter", filter_groups_list)


def get_base64_image(image_path):
    if os.path.exists(image_path):
        with open(image_path, "rb") as img_file:
            return base64.b64encode(img_file.read()).decode()
    return ""

logo_base64 = get_base64_image("assets/Kayfa.png")
img_html = f'<img src="data:image/png;base64,{logo_base64}" width="90">' if logo_base64 else ''


navbar_html = f"""
<div class="kayfa-navbar">
    <div class="kayfa-navbar-left">
        <h1>Student Analytics</h1>
        <p><strong>Kayfa Systems:</strong> A simple, powerful dashboard that brings all your student data together. See how your students are learning, track their attendance, watch their progress, and easily spot who needs help to succeed.</p>
    </div>
    <div class="kayfa-navbar-right">
        {img_html}
    </div>
</div>
"""
st.markdown(navbar_html, unsafe_allow_html=True)


@st.cache_resource
def init_connection():
    return MongoClient(st.secrets["mongo"]["uri"])

client = init_connection()
db = client["kayfa_analytics"]


if "logged_in" not in st.session_state:
    st.session_state.logged_in = False

if not st.session_state.logged_in:
    st.markdown("<br><br>", unsafe_allow_html=True)
    col1, col2, col3 = st.columns([1, 1, 1])
    with col2:
        st.image("assets/Kayfa.png", use_container_width=True)
        st.markdown("<h3 style='text-align: center; color: white;'>System Login</h3>", unsafe_allow_html=True)
        
        username = st.text_input("Username")
        password = st.text_input("Password", type="password")
        
        if st.button("Secure Login", use_container_width=True):
            user = db["users"].find_one({"username": username, "password": password})
            if user:
                st.session_state.logged_in = True
                st.rerun()
            else:
                st.error("Invalid credentials")
    st.stop() # This entirely stops the app from rendering the dashboard



tab_acad, tab_eng, tab_trend, tab_conc, tab_adv, tab_adm, tab_int, tab_growth = st.tabs([
    "Academic Overview", 
    "Engagement Behaviors", 
    "Demographics & Trends", 
    "Curriculum Concepts", 
    "Advanced Analytics", 
    "Cohort Administration",
    "System Integrity",
    "Kayfa Growth"
])

with tab_acad: 
    academics.render(selected_course, selected_group)
with tab_eng: 
    engagement.render(selected_course, selected_group)
with tab_trend: 
    trends.render(selected_course, selected_group)
with tab_conc: 
    concepts.render(selected_course, selected_group)
with tab_adv: 
    advanced.render(selected_course, selected_group)
with tab_adm: 
    admin.render(selected_course, selected_group)
with tab_int:
    integrity.render(selected_course, selected_group)
with tab_growth:
    growth.render(selected_course, selected_group)  


st.markdown("<br><br><br>", unsafe_allow_html=True)
st.divider()
col_f1, col_f2, col_f3 = st.columns([5, 2, 5])
with col_f2:
    st.image("assets/Kayfa.png", use_container_width=True)
    st.markdown(f"<p style='text-align: center; color: {st.session_state.colors['slate']}; font-size: 11px; margin-top: 5px;'>© 2026 Kayfa Platforms</p>", unsafe_allow_html=True)
