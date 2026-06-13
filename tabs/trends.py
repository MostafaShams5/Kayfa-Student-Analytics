from pymongo import MongoClient
import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go

def clean_chart(fig):
    """Strips visual clutter and ensures large, readable labels."""
    fig.update_layout(
        plot_bgcolor="rgba(0,0,0,0)", 
        paper_bgcolor="rgba(0,0,0,0)", 
        xaxis=dict(
            showgrid=True, gridcolor="#E2E8F0", zeroline=False, 
            title_font=dict(size=15, color="#0F172A"),
            tickfont=dict(size=12, color="#475569")
        ), 
        yaxis=dict(
            showgrid=True, gridcolor="#E2E8F0", zeroline=False, 
            title_font=dict(size=15, color="#0F172A"),
            tickfont=dict(size=12, color="#475569")
        ),
        margin=dict(t=50, b=50, l=50, r=30),
        font=dict(color="#0F172A"),
        legend=dict(
            orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1,
            font=dict(size=13)
        ),
        hovermode="x unified"
    )
    return fig

@st.cache_data
def load_trends_data():
    """Loads and preprocesses data, combining engagement with demographics from MongoDB."""
    client = MongoClient(st.secrets["mongo"]["uri"])
    db = client["kayfa_analytics"]
    
    roster = pd.DataFrame(list(db["unified_roster"].find({}, {"_id": 0})))
    att = pd.DataFrame(list(db["attendance_log"].find({}, {"_id": 0})))
    events = pd.DataFrame(list(db["events_log"].find({}, {"_id": 0})))
    ast = pd.DataFrame(list(db["unified_assessments"].find({}, {"_id": 0})))
    
    # 1. Roster Outcomes
    grades = ast.groupby('student_id')['score'].mean().reset_index(name='Average Grade (%)')
    
    att['is_present'] = att['status'].str.lower() == 'attended'
    attendance = att.groupby('student_id').agg(total=('record_id','count'), attended=('is_present','sum')).reset_index()
    attendance['Attendance Rate (%)'] = (attendance['attended'] / attendance['total']) * 100
    
    logins = events[events['event_type'] == 'login'].groupby('student_id').size().reset_index(name='Total Logins')
    videos = events[events['event_type'] == 'video_watch'].groupby('student_id')['duration_seconds'].sum().reset_index(name='video_sec')
    videos['Video Watch Time (Hours)'] = videos['video_sec'] / 3600

    df_demographics = roster.merge(grades, on='student_id', how='left')\
                            .merge(attendance[['student_id', 'Attendance Rate (%)']], on='student_id', how='left')\
                            .merge(logins, on='student_id', how='left')\
                            .merge(videos[['student_id', 'Video Watch Time (Hours)']], on='student_id', how='left')
                            
    df_demographics.rename(columns={'course_name': 'Course Name', 'group_id': 'Cohort Group', 'age': 'Student Age'}, inplace=True)
    df_demographics.fillna({'Total Logins': 0, 'Video Watch Time (Hours)': 0}, inplace=True)

    # 2. Timeline Data (FIXED TO INCLUDE QUIZZES & EXAMS)
    ev_timeline = events[['event_datetime']].copy().rename(columns={'event_datetime': 'Date'})
    ev_timeline['Action Type'] = 'Platform Event (Login/Video)'
    
    # Smart Fallback: If 'submitted_at' is empty (like for live Quizzes/Exams), use the scheduled 'date' instead.
    ast['Timeline Date'] = pd.to_datetime(ast['submitted_at'], errors='coerce').fillna(pd.to_datetime(ast['date'], errors='coerce'))
    ast_timeline = ast[['Timeline Date']].dropna().copy().rename(columns={'Timeline Date': 'Date'})
    ast_timeline['Action Type'] = 'Assessments Taken (All Types)'
    
    timeline_df = pd.concat([ev_timeline, ast_timeline])
    timeline_df['Date'] = pd.to_datetime(timeline_df['Date'], errors='coerce')
    timeline_df = timeline_df.dropna()
    
    return df_demographics, timeline_df, ast, att, roster

def render(selected_course, selected_group):
    df_demo, timeline_df, ast, att, roster = load_trends_data()
    
    # Vibrant Palette
    c_primary = "#0EA5E9"  # Vibrant Sky Blue
    c_secondary = "#8B5CF6" # Vibrant Purple
    c_alert = "#FB7185"    # Soft Rose
    c_dots = "#64748B"     # Slate Gray
    c_trend = "#E11D48"    # Bold Crimson Red

    if selected_course != "All Courses": 
        df_demo = df_demo[df_demo['Course Name'] == selected_course]
    if selected_group != "All Groups": 
        df_demo = df_demo[df_demo['Cohort Group'] == selected_group]

    st.markdown("### Objective: Demographics & Temporal Trends")
    st.markdown("Track digital engagement over time, investigate format difficulty (why grades drop in March), and understand how different age demographics engage with the platform.")
    st.markdown("<br>", unsafe_allow_html=True)

    # --- 1. THE 6-MONTH ACTIVITY TREND (FIXED: NOW SHOWS ALL ASSESSMENTS) ---
    st.subheader("1. Digital Activity Timeline")
    st.markdown("An overlapping area chart showing asynchronous platform usage vs. **All Assessments** (Quizzes, Assignments, and Exams) over the entire term.")
    
    weekly_counts = timeline_df.groupby([pd.Grouper(key='Date', freq='W-MON'), 'Action Type']).size().reset_index(name='Total Actions')
    weekly_counts.rename(columns={'Date': 'Week'}, inplace=True)
    
    df_events = weekly_counts[weekly_counts['Action Type'] == 'Platform Event (Login/Video)']
    df_assign = weekly_counts[weekly_counts['Action Type'] == 'Assessments Taken (All Types)']

    fig_trend = go.Figure()
    
    fig_trend.add_trace(go.Scatter(
        x=df_events['Week'], y=df_events['Total Actions'], 
        fill='tozeroy', mode='lines', line=dict(color=c_primary, width=3, shape='spline'),
        name='Platform Events (Logins/Videos)', opacity=0.5
    ))
    
    fig_trend.add_trace(go.Scatter(
        x=df_assign['Week'], y=df_assign['Total Actions'], 
        fill='tozeroy', mode='lines', line=dict(color=c_secondary, width=4, shape='spline'),
        name='Assessments Taken (Quizzes/Exams/Assignments)', opacity=0.8
    ))

    fig_trend.update_layout(xaxis_title="Calendar Week", yaxis_title="Total Action Volume")
    st.plotly_chart(clean_chart(fig_trend), use_container_width=True)


    st.divider()

    # --- 2. INVESTIGATING THE MARCH GRADE DROP ---
    st.subheader("2. Investigating the March Anomaly: Why do grades suddenly drop?")
    st.markdown("You may have noticed that system-wide grades crash specifically in March. We investigated the data and found two overlapping causes: **Format Difficulty** and **Student Ghosting**.")

    c_anom1, c_anom2 = st.columns(2)
    
    with c_anom1:
        # Cause 1: Assessment Type Difficulty
        st.markdown("#### Cause 1: The Format Shift")
        
        # Calculate average score by test type
        ast_types = ast.groupby('type')['score'].mean().reset_index().sort_values('score', ascending=False)
        ast_types['type'] = ast_types['type'].str.title()
        
        # Color assignments red to highlight the problem
        ast_types['Color'] = ast_types['type'].apply(lambda x: c_alert if x == 'Assignment' else c_dots)
        
        fig_type = go.Figure(go.Bar(
            x=ast_types['score'], y=ast_types['type'], orientation='h',
            marker_color=ast_types['Color'], text=ast_types['score'].apply(lambda x: f"{x:.1f}%")
        ))
        fig_type.update_traces(textposition='outside', cliponaxis=False)
        fig_type.update_layout(title="Average Score by Test Format", xaxis_title="Average Grade (%)", yaxis_title="")
        fig_type.update_xaxes(range=[0, 110])
        st.plotly_chart(clean_chart(fig_type), use_container_width=True)

    with c_anom2:
        # Cause 2: Ghosting (Disconnecting from live classes)
        st.markdown("#### Cause 2: Disconnecting from Class")
        
        ast_march = ast[ast['type'].str.lower() == 'assignment'].copy()
        ast_march['date'] = pd.to_datetime(ast_march['date'], errors='coerce')
        ast_march = ast_march[ast_march['date'].dt.month == 3] 
        
        if not ast_march.empty:
            ast_march = ast_march.merge(roster[['student_id', 'full_name']], on='student_id', how='left')
            att_present = att[att['is_present'] == True].copy()
            att_present['session_datetime'] = pd.to_datetime(att_present['session_datetime'], errors='coerce')
            
            ast_march = ast_march.sort_values('date')
            att_present = att_present.sort_values('session_datetime')
            
            smart_df = pd.merge_asof(
                ast_march.dropna(subset=['date']),
                att_present.dropna(subset=['session_datetime'])[['student_id', 'session_datetime']],
                by='student_id', left_on='date', right_on='session_datetime', direction='backward'
            )
            
            smart_df['Days Since Last Attended'] = (smart_df['date'] - smart_df['session_datetime']).dt.days
            plot_df = smart_df.dropna(subset=['Days Since Last Attended']).copy()
            
            fig_scatter = px.scatter(
                plot_df, x='Days Since Last Attended', y='score', 
                trendline='ols', color_discrete_sequence=[c_dots],
                title="Impact of Skipping Class on Assignments",
                hover_data=['full_name']
            )
            fig_scatter.update_traces(marker=dict(size=8, opacity=0.7))
            if len(fig_scatter.data) > 1:
                fig_scatter.data[1].line.color = c_trend
            
            fig_scatter.update_layout(yaxis_title="March Assignment Score (%)")
            st.plotly_chart(clean_chart(fig_scatter), use_container_width=True)
        else:
            st.warning("No assignment data found for the month of March.")

    st.info(
    "**Insight:** Students do fine on quizzes, but performance drops on heavier assignments when many skip live classes to focus on submissions.  \n\n"
    "**Recommendation:** Split assignment deadlines into multiple windows like exams to spread workload, keep students attending classes, and improve overall performance."
)
    st.divider()

    # --- 3. DEMOGRAPHICS (AGE VS OUTCOMES & ENGAGEMENT) ---
    st.subheader("3. Does Age Affect Performance & Engagement Strategies?")
    st.markdown("We bucketed students into dynamic age brackets to see if different generations rely on different learning inputs (Live vs Video).")
    
    if df_demo['Student Age'].nunique() > 3:
        bins = pd.qcut(df_demo['Student Age'], q=4, precision=0, duplicates='drop')
        df_demo['Age Bracket'] = bins.apply(lambda x: f"{int(x.left + 1)} to {int(x.right)} Yrs" if pd.notna(x) else "Unknown")
    else:
        df_demo['Age Bracket'] = df_demo['Student Age'].astype(str) + " Yrs"
    
    age_stats = df_demo.groupby('Age Bracket').agg(
        avg_grade=('Average Grade (%)', 'mean'), 
        avg_attendance=('Attendance Rate (%)', 'mean'),
        avg_watch=('Video Watch Time (Hours)', 'mean')
    ).reset_index()

    c_age1, c_age2, c_age3 = st.columns(3)
    
    with c_age1:
        fig_g = px.bar(
            age_stats, x='avg_grade', y='Age Bracket', orientation='h', title="Average Grade", 
            text=age_stats['avg_grade'].apply(lambda x: f"{x:.1f}%" if pd.notnull(x) else "0%")
        )
        fig_g.update_traces(marker_color=c_secondary, textposition='outside', cliponaxis=False)
        fig_g.update_layout(xaxis_title="Grade (%)", yaxis_title="", showlegend=False)
        fig_g.update_xaxes(range=[0, 105])
        st.plotly_chart(clean_chart(fig_g), use_container_width=True)
        
    with c_age2:
        fig_a = px.bar(
            age_stats, x='avg_attendance', y='Age Bracket', orientation='h', title="Live Attendance", 
            text=age_stats['avg_attendance'].apply(lambda x: f"{x:.1f}%" if pd.notnull(x) else "0%")
        )
        fig_a.update_traces(marker_color=c_dots, textposition='outside', cliponaxis=False)
        fig_a.update_layout(xaxis_title="Attendance Rate (%)", yaxis_title="", showlegend=False)
        fig_a.update_xaxes(range=[0, 115])
        st.plotly_chart(clean_chart(fig_a), use_container_width=True)
        
    with c_age3:
        fig_w = px.bar(
            age_stats, x='avg_watch', y='Age Bracket', orientation='h', title="Video Engagement", 
            text=age_stats['avg_watch'].apply(lambda x: f"{x:.1f} Hrs" if pd.notnull(x) else "0")
        )
        fig_w.update_traces(marker_color=c_primary, textposition='outside', cliponaxis=False)
        fig_w.update_layout(xaxis_title="Watch Time (Hours)", yaxis_title="", showlegend=False)
        fig_w.update_xaxes(range=[0, age_stats['avg_watch'].max() * 1.3])
        st.plotly_chart(clean_chart(fig_w), use_container_width=True)
        
    st.info(
    "**Insight:** When comparing the charts, younger students may rely more on external learning sources. This is shown by lower live attendance but higher video watch time, while still maintaining strong grades. It suggests they are substituting live classes with self-paced learning instead of relying only on synchronous teaching."
)
