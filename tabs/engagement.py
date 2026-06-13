import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
from pymongo import MongoClient

def clean_chart(fig):
    """Strips out visual clutter and enhances axis label visibility."""
    fig.update_layout(
        plot_bgcolor="rgba(0,0,0,0)", 
        paper_bgcolor="rgba(0,0,0,0)", 
        xaxis=dict(
            showgrid=True, gridcolor="#E2E8F0", zeroline=False, 
            title_font=dict(size=15, color="#0F172A"),
            tickfont=dict(size=12, color="#475569")
        ), 
        yaxis=dict(
            showgrid=False, zeroline=False, 
            title_font=dict(size=15, color="#0F172A"),
            tickfont=dict(size=12, color="#475569")
        ),
        margin=dict(t=50, b=50, l=50, r=30),
        font=dict(color="#0F172A"),
        showlegend=False # Hides overlapping legends
    )
    return fig

@st.cache_data
def load_engagement_data():
    """Loads and preprocesses behavioral and outcome data from MongoDB."""
    client = MongoClient(st.secrets["mongo"]["uri"])
    db = client["kayfa_analytics"]
    
    roster = pd.DataFrame(list(db["unified_roster"].find({}, {"_id": 0})))
    ast = pd.DataFrame(list(db["unified_assessments"].find({}, {"_id": 0})))
    att = pd.DataFrame(list(db["attendance_log"].find({}, {"_id": 0})))
    events = pd.DataFrame(list(db["events_log"].find({}, {"_id": 0})))

    # 1. Calculate Average Grades
    grades = ast.groupby('student_id')['score'].mean().reset_index(name='Average Grade (%)')
    
    # 2. Calculate Attendance Rates
    att['is_present'] = att['status'].str.lower() == 'attended'
    attendance = att.groupby('student_id').agg(total=('record_id','count'), attended=('is_present','sum')).reset_index()
    attendance['Attendance Rate (%)'] = (attendance['attended'] / attendance['total']) * 100

    # 3. Calculate Platform Events
    logins = events[events['event_type'] == 'login'].groupby('student_id').size().reset_index(name='Total Logins')
    videos = events[events['event_type'] == 'video_watch'].groupby('student_id')['duration_seconds'].sum().reset_index(name='video_sec')
    videos['Video Watch Time (Hours)'] = videos['video_sec'] / 3600
    
    # Cap watch time at 98th percentile to prevent extreme outliers from warping trendlines
    watch_time_cap = videos['Video Watch Time (Hours)'].quantile(0.98)
    videos['Video Watch Time (Hours)'] = videos['Video Watch Time (Hours)'].clip(upper=watch_time_cap)

    # Merge into a master dataframe
    df = roster[['student_id', 'course_name', 'group_id']].merge(grades, on='student_id', how='left')\
        .merge(attendance[['student_id', 'Attendance Rate (%)']], on='student_id', how='left')\
        .merge(logins, on='student_id', how='left')\
        .merge(videos[['student_id', 'Video Watch Time (Hours)']], on='student_id', how='left')
    
    df.rename(columns={'course_name': 'Course Name', 'group_id': 'Cohort Group'}, inplace=True)
    df.fillna({'Total Logins': 0, 'Video Watch Time (Hours)': 0}, inplace=True)
    
    return df, att, ast

def calculate_impact(df, x_col, y_col, multiplier=1):
    """Calculates the linear regression slope to provide a real number metric."""
    mask = df[x_col].notna() & df[y_col].notna()
    valid_df = df[mask]
    if len(valid_df) > 1:
        slope, _ = np.polyfit(valid_df[x_col], valid_df[y_col], 1)
        return slope * multiplier
    return 0

def render(selected_course, selected_group):
    df, att_raw, ast_raw = load_engagement_data()
    
    # Vibrant, eye-catchy custom palette for this specific tab
    c_healthy = "#0EA5E9"  # Vibrant Sky Blue
    c_alert = "#FB7185"    # Soft Rose
    c_dots = "#64748B"     # Slate Gray
    c_trend = "#E11D48"    # Bold Crimson Red
    
    if selected_course != "All Courses": df = df[df['Course Name'] == selected_course]
    if selected_group != "All Groups": df = df[df['Cohort Group'] == selected_group]

    st.markdown("### Engagement Behaviors & Academic Outcomes")
    st.markdown("Quantify exactly how much student effort—showing up to live sessions, logging in, and watching videos—impacts their final grades. Identify actionable metrics to encourage better habits.")
    st.markdown("<br>", unsafe_allow_html=True)

    # --- 1. COHORT ATTENDANCE HEALTH ---
    st.subheader("1. Platform Attendance Health")
    st.markdown("Visualizing live attendance per cohort to identify highly engaged groups vs. those falling behind.")
    
    platform_avg = (att_raw['is_present'].sum() / len(att_raw)) * 100 if len(att_raw) > 0 else 0
    
    # Create a combined label so viewers know which group takes which course
    df['Group Label'] = df['Cohort Group'] + " (" + df['Course Name'] + ")"
    group_att = df.groupby('Group Label')['Attendance Rate (%)'].mean().reset_index().sort_values('Attendance Rate (%)', ascending=True)
    
    # Color mapping: Vibrant Blue if healthy, Rose if below average
    group_att['Color'] = group_att['Attendance Rate (%)'].apply(lambda x: c_healthy if x >= platform_avg else c_alert)
    
    fig_g_att = go.Figure(go.Bar(
        x=group_att['Attendance Rate (%)'], y=group_att['Group Label'], orientation='h', 
        marker_color=group_att['Color'], text=group_att['Attendance Rate (%)'].apply(lambda x: f"{x:.1f}%")
    ))
    
    # Fixed the overlap: Positioned annotation text to the top left of the line
    fig_g_att.add_vline(
        x=platform_avg, line_dash="dash", line_color=c_dots, 
        annotation_text=f"Platform Avg: {platform_avg:.1f}%", 
        annotation_position="top left"
    )
    
    fig_g_att.update_traces(textposition='outside', cliponaxis=False)
    fig_g_att.update_layout(title="Average Attendance Rate by Cohort Group", xaxis_title="Attendance Rate (%)", yaxis_title="")
    fig_g_att.update_xaxes(range=[0, 115]) # Extra room for the text label
    
    st.plotly_chart(clean_chart(fig_g_att), use_container_width=True)
    
    st.info(
    "**Takeaway:** G7 stands out with lower attendance and should be investigated further. G10 appears as an outlier, but with only one student, its results are not statistically meaningful."
)

    st.divider()

    # --- 2. BEHAVIORAL CORRELATIONS ---
    st.subheader("2. Does Effort Equal Better Grades?")
    st.markdown("We calculated the exact mathematical impact of student habits. The bold red line shows the performance trend.")
    
    col1, col2, col3 = st.columns(3)
    
    # Calculate impacts to display real numbers
    att_impact = calculate_impact(df, 'Attendance Rate (%)', 'Average Grade (%)', multiplier=10)
    login_impact = calculate_impact(df, 'Total Logins', 'Average Grade (%)', multiplier=10)
    watch_impact = calculate_impact(df, 'Video Watch Time (Hours)', 'Average Grade (%)', multiplier=1)
    
    with col1:
        st.success(f"**Metric:** +10% Attendance = **+{att_impact:.1f}% Grade**")
        fig1 = px.scatter(df, x='Attendance Rate (%)', y='Average Grade (%)', trendline="ols", trendline_color_override=c_trend)
        fig1.update_traces(marker=dict(color=c_dots, size=6, opacity=0.7))
        st.plotly_chart(clean_chart(fig1), use_container_width=True)
        
    with col2:
        st.success(f"**Metric:** +10 Logins = **+{login_impact:.1f}% Grade**")
        fig2 = px.scatter(df, x='Total Logins', y='Average Grade (%)', trendline="ols", trendline_color_override=c_trend)
        fig2.update_traces(marker=dict(color=c_dots, size=6, opacity=0.7))
        st.plotly_chart(clean_chart(fig2), use_container_width=True)
        
    with col3:
        st.success(f"**Metric:** +1 Hour Watched = **+{watch_impact:.1f}% Grade**")
        fig3 = px.scatter(df, x='Video Watch Time (Hours)', y='Average Grade (%)', trendline="ols", trendline_color_override=c_trend)
        fig3.update_traces(marker=dict(color=c_dots, size=6, opacity=0.7))
        st.plotly_chart(clean_chart(fig3), use_container_width=True)

    st.info(
    "**Takeaway:** This is a strong green flag for instructor quality—higher engagement consistently translates into better grades."
)

    st.divider()

    # --- 3. PROCRASTINATION EFFECT ---
    st.subheader("3. The Cost of Procrastination")
    st.markdown("""
    Measuring the academic penalty of submitting late vs the reward of finishing days in advance. 
    """)
    
    assignments = ast_raw[(ast_raw['type'] == 'assignment') & (ast_raw['deadline'].notna()) & (ast_raw['submitted_at'].notna())].copy()
    
    if not assignments.empty:
        assignments['deadline'] = pd.to_datetime(assignments['deadline'])
        assignments['submitted_at'] = pd.to_datetime(assignments['submitted_at'])
        assignments['Hours Before Deadline'] = (assignments['deadline'] - assignments['submitted_at']).dt.total_seconds() / 3600
        
        # Strip outliers
        buffer_cap = assignments['Hours Before Deadline'].quantile(0.98)
        assignments = assignments[assignments['Hours Before Deadline'] <= buffer_cap]

        assignments['Submission Status'] = assignments['Hours Before Deadline'].apply(lambda x: "Late Submission" if x < 0 else "On-Time")
        assignments.rename(columns={'score': 'Assignment Score'}, inplace=True)

        c_late1, c_late2 = st.columns(2)
        
        with c_late1:
            fig_late = px.box(
                assignments, x='Assignment Score', y='Submission Status', orientation='h',
                title="Score Variances: On-Time vs Late", color='Submission Status',
                color_discrete_map={"On-Time": c_healthy, "Late Submission": c_alert}
            )
            fig_late.update_layout(yaxis_title="")
            st.plotly_chart(clean_chart(fig_late), use_container_width=True)
            
        with c_late2:
            on_time_df = assignments[assignments['Hours Before Deadline'] >= 0]
            
            # Calculate the impact of finishing 1 day (24 hours) early
            buffer_impact = calculate_impact(on_time_df, 'Hours Before Deadline', 'Assignment Score', multiplier=24)
            st.success(f"**Metric:** Submitting 1 Day Early = **+{buffer_impact:.1f}% Score**")
            
            fig_buffer = px.scatter(
                on_time_df, x='Hours Before Deadline', y='Assignment Score', trendline="ols", 
                trendline_color_override=c_trend
            )
            fig_buffer.update_xaxes(autorange="reversed") # 0 hours left on the right
            fig_buffer.update_traces(marker=dict(color=c_dots, size=6, opacity=0.7))
            fig_buffer.update_layout(title="Buffer Analysis (On-Time Submissions Only)")
            st.plotly_chart(clean_chart(fig_buffer), use_container_width=True)

    st.info(
    "**Takeaway:** Submission timing has only a modest impact on grades. The relatively small differences may indicate that assessments were not difficult enough to strongly separate early, well-prepared students from last-minute submissions."
)
