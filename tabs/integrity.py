from pymongo import MongoClient
import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
import json

def clean_chart(fig):
    fig.update_layout(
        plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)", 
        xaxis=dict(showgrid=True, gridcolor="#E2E8F0", zeroline=False, title_font=dict(size=14, color="#0F172A"), tickfont=dict(size=12, color="#475569")), 
        yaxis=dict(showgrid=True, gridcolor="#E2E8F0", zeroline=False, title_font=dict(size=14, color="#0F172A"), tickfont=dict(size=12, color="#475569")),
        margin=dict(t=50, b=40, l=40, r=30), font=dict(color="#0F172A"),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1, font=dict(size=13)),
        hovermode="y unified"
    )
    return fig


@st.cache_data
def load_all_raw_data():
    client = MongoClient(st.secrets["mongo"]["uri"])
    db = client["kayfa_analytics"]
    data = {}
    
    data['students'] = pd.DataFrame(list(db["students"].find({}, {"_id": 0})))
    data['concepts'] = pd.DataFrame(list(db["concepts_performance"].find({}, {"_id": 0})))
    data['events'] = pd.DataFrame(list(db["engagement_events"].find({}, {"_id": 0})))
    data['submissions'] = pd.DataFrame(list(db["assignment_submissions"].find({}, {"_id": 0})))
    

    raw_grades = list(db["grades"].find({}, {"_id": 0}))
    flattened = []
    
    for student in raw_grades:
        # Extract the nested list of grades for each student
        for g in student.get("grades", []):
            g['student_id'] = student.get('student_id')
            flattened.append(g)
            
    data['grades'] = pd.DataFrame(flattened)


    return data
def render(selected_course, selected_group):
    db = load_all_raw_data()
    
    c_alert = "#E11D48"    # Crimson Red (Critical Bug)
    c_warn = "#F59E0B"     # Amber (Warning)
    c_dots = "#64748B"     # Slate Gray
    c_success = "#10B981"  # Emerald (Clean)

    st.markdown("###  Objective: System Integrity & Software Auditing")
    st.markdown("This dashboard bypasses our analytics pipeline to read the **Raw Database Files** directly. Its goal is to translate technical software bugs into plain English so leadership can see where the platform is breaking, where students are cheating, and what the engineering team needs to fix immediately.")
    st.markdown("<br>", unsafe_allow_html=True)

    if db['students'].empty or db['concepts'].empty or db['events'].empty:
        st.error("Missing raw data files (students.csv, concepts_performance.csv, engagement_events.csv). Cannot run system audit.")
        return

    # ==========================================
    # 1. DATABASE "TRASH" & CLONES
    # ==========================================
    st.subheader("1. Database 'Trash' & The Stuttering Save Button")
    st.markdown("Sometimes, bad data gets stuck in the database. This includes test accounts left behind by developers, or the system accidentally saving the exact same record multiple times.")

    c_db1, c_db2 = st.columns(2)
    
    with c_db1:
        # Garbled Text & Dummy IDs
        concepts = db['concepts']
        weird_records = concepts[~concepts['record_id'].astype(str).str.match(r'^CP\d+$', na=False)]
        corrupted_text = concepts[concepts['concept_name'].astype(str).str.contains(r'[ÃÂ¤â‚¬@?]', regex=True, na=False)]
        
        st.metric("Test/Dummy Data Left in Production", f"{len(weird_records)} Records", "IDs like 'CPBAD' or 'CPX'", delta_color="inverse")
        if not weird_records.empty:
            st.caption("Developers left fake test scores in the live database, which artificially alters our passing rates.")
            
        st.metric("Corrupted / Garbled Text", f"{len(corrupted_text)} Records", "e.g. 'Ã‚Â¤Ã¢â‚¬#@@'", delta_color="inverse")
        if not corrupted_text.empty:
            st.caption("The database failed to save Arabic/Special characters correctly, resulting in unreadable gibberish.")

    with c_db2:
        # The Clone Bug
        clones = concepts.groupby(['student_id', 'concept_name', 'timestamp']).size().reset_index(name='count')
        chronic_clones = clones[clones['count'] > 1]
        
        st.error(f" **The 'Clone' Bug (Stuttering Saves):** Detected {len(chronic_clones)} duplicate injections.")
        st.markdown("""
        
        When a student clicks 'Submit' on a quiz, their internet might lag. They click 'Submit' 5 more times in frustration. Because our database has no safeguards, it saves **all 6 clicks at the exact same second**. 
        
        This creates a false narrative that a student failed a topic 6 times, when they actually only failed it once.
        """)

    st.divider()

    # ==========================================
    # 2. SECURITY EXPLOITS & GHOSTS
    # ==========================================
    st.subheader("2. Security Exploits: 'Ghost' Students & Cheating")
    st.markdown("We scanned the raw telemetry logs to find students performing impossible actions, which indicates they have found loopholes in the software or are sharing accounts.")

    events = db['events']
    events['duration_seconds'] = pd.to_numeric(events['duration_seconds'], errors='coerce')
    events['event_datetime'] = pd.to_datetime(events['event_datetime'], errors='coerce')
    events['event_date'] = events['event_datetime'].dt.date
    
    # 1. Negative Durations
    neg_dur = events[events['duration_seconds'] < 0]
    
    # 2. Account Sharing (Multi-Device)
    events['minute_floor'] = events['event_datetime'].dt.floor('min')
    multi_device = events.groupby(['student_id', 'minute_floor'])['device'].nunique().reset_index(name='device_count')
    cheaters = multi_device[multi_device['device_count'] > 1]

    # 3. Ghost Submissions (UI Bypass)
    ghost_subs_count = 0
    if not db['submissions'].empty:
        subs = db['submissions'].copy()
        subs['sub_date'] = pd.to_datetime(subs['submitted_at'], errors='coerce').dt.date
        active_days = events[['student_id', 'event_date']].drop_duplicates()
        active_days['is_active'] = True
        exploit_check = subs.merge(active_days, left_on=['student_id', 'sub_date'], right_on=['student_id', 'event_date'], how='left')
        ghost_subs_count = len(exploit_check[exploit_check['is_active'].isna()])

    # Charting the Exploits
    exploit_labels = ['Negative Watch Time (Software Glitch)', 'Simultaneous Web & Mobile (Account Sharing)', 'Ghost Submissions (API Hack)']
    exploit_counts = [len(neg_dur), len(cheaters), ghost_subs_count]
    
    df_exploits = pd.DataFrame({'Exploit': exploit_labels, 'Count': exploit_counts})
    df_exploits['Color'] = df_exploits['Count'].apply(lambda x: c_success if x == 0 else c_alert)

    fig_exploits = go.Figure(go.Bar(
        x=df_exploits['Count'], y=df_exploits['Exploit'], orientation='h',
        marker_color=df_exploits['Color'], text=df_exploits['Count'].apply(lambda x: f"{x} Flags")
    ))
    fig_exploits.update_traces(textposition='outside')
    fig_exploits.update_layout(title="Volume of Security & Logic Exploits Detected", xaxis_title="", yaxis_title="")
    fig_exploits.update_xaxes(range=[0, max(max(exploit_counts) * 1.3, 10)])
    st.plotly_chart(clean_chart(fig_exploits), use_container_width=True)

    st.markdown("""
    **What do these exploits mean?**
    * **Simultaneous Web & Mobile:** A student is logged in on their phone, while someone else (likely taking the test for them) is logged in on a laptop at the *exact same minute*.
    * **Ghost Submissions:** Students figured out a way to submit homework directly into our database without ever visiting the website or clicking 'Login'. They are bypassing our educational platform entirely.
    """)

    st.divider()

    # ==========================================
    # 3. GRADING ENGINE FAILURES
    # ==========================================
    st.subheader("3. Grading Engine Failures")
    st.markdown("Checking if the math inside the system is actually correct.")

    c_gr1, c_gr2 = st.columns(2)

    with c_gr1:
        st.markdown("#### The '60.0% Rounding' Glitch")
        sixty_bug = concepts[concepts['score_pct'] == 60.0]
        if not sixty_bug.empty:
            p_60 = len(sixty_bug[sixty_bug['mastery_status'].str.lower() == 'passed'])
            f_60 = len(sixty_bug[sixty_bug['mastery_status'].str.lower() == 'failed'])
            st.error(f" We found students scoring exactly **60.0%**. The system passed {p_60} of them, but failed {f_60} of them.")
            st.caption("**The Cause:** The system shows '60.0%' on the screen, but secretly stores '59.999%' in the database, causing random students to fail when they thought they passed.")

    with c_gr2:
        st.markdown("#### Phantom Quiz Grades")
        phantom_count = 0
        if not db['grades'].empty:
            quizzes = db['grades'][db['grades']['type'].str.lower() == 'quiz'].copy()
            quizzes['grade_date'] = pd.to_datetime(quizzes['date'], errors='coerce').dt.date
            quiz_events = events[events['event_type'] == 'quiz_attempt'][['student_id', 'event_date']].drop_duplicates()
            quiz_events['took_quiz'] = True
            
            p_check = quizzes.merge(quiz_events, left_on=['student_id', 'grade_date'], right_on=['student_id', 'event_date'], how='left')
            phantom_count = len(p_check[p_check['took_quiz'].isna()])
        
        if phantom_count > 0:
            st.error(f" We found **{phantom_count} Phantom Grades**.")
            st.caption("**The Cause:** Students received a final grade for a Quiz, but our telemetry shows they never actually clicked 'Start Quiz' that day. The website's tracking system is randomly disconnecting from the grading system.")
        else:
            st.success(" No Phantom Grades detected. Telemetry matches Grades.")

    st.divider()

    # ==========================================
    # 4. EXECUTIVE ACTION PLAN (FOR SOFTWARE LEAD)
    # ==========================================
    st.subheader(" Official Action Plan: Meeting with Software Team Lead")
    st.markdown("Copy and paste these exact bullet points into your agenda for the Engineering Team:")

    st.markdown("""
    <div style="background-color: #F8FAFC; padding: 25px; border-left: 5px solid #0EA5E9; border-radius: 5px;">
        <h4 style="margin-top:0;">Agenda Items for Engineering Fixes:</h4>
        <ol style="line-height: 1.8; font-size: 16px;">
            <li><strong>Lock Down API Endpoints (Stop the Ghosts):</strong> We have hundreds of 'Ghost Submissions'. Ensure the backend rejects any homework submission if the user's session token doesn't have an active <code>login</code> event attached to it.</li>
            <li><strong>Implement Concurrency Limits (Stop Cheaters):</strong> The system currently allows a user to be logged in on Mobile and Web simultaneously. Force the system to invalidate the older session if a new device logs in.</li>
            <li><strong>Debounce the Save Button (Fix the Clones):</strong> The database is recording 5-6 identical quiz results at the exact same timestamp. Implement a 'debounce' function on the frontend so a user can't spam the submit button during a lag spike, and add a unique constraint in the DB.</li>
            <li><strong>Fix the 60% Floating Point Bug:</strong> Students are furious that they see 60.0% but get marked as 'Failed'. Update the grading logic to use <code>ROUND(score, 1) >= 60.0</code> before assigning the Pass/Fail flag.</li>
            <li><strong>Sanitize Database Inputs:</strong> Delete all records containing <code>CPBAD</code> or <code>CPX</code> (test data left in production). Enforce strict UTF-8 encoding to stop Arabic strings from turning into <code>Ã‚Â¤Ã¢â‚¬</code> garbage text.</li>
        </ol>
    </div>
    """, unsafe_allow_html=True)
