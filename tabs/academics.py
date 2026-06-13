from pymongo import MongoClient
import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go

def clean_chart(fig):
    """Strips out visual clutter for an enterprise-grade look."""
    fig.update_layout(
        plot_bgcolor="rgba(0,0,0,0)", 
        paper_bgcolor="rgba(0,0,0,0)", 
        xaxis=dict(showgrid=True, gridcolor="#E2E8F0", zeroline=False, title_font=dict(size=14, color="#0F172A"), tickfont=dict(size=12, color="#475569")), 
        yaxis=dict(showgrid=False, zeroline=False, title_font=dict(size=14, color="#0F172A"), tickfont=dict(size=12, color="#475569")),
        margin=dict(t=50, b=20, l=10, r=10),
        font=dict(color="#0F172A")
    )
    return fig

@st.cache_data
def load_academic_data():
    # Connect to Mongo
    client = MongoClient(st.secrets["mongo"]["uri"])
    db = client["kayfa_analytics"]
    
    # Read from DB instead of CSV
    df_ast = pd.DataFrame(list(db["unified_assessments"].find({}, {"_id": 0})))
    df_roster = pd.DataFrame(list(db["unified_roster"].find({}, {"_id": 0})))
    df_att = pd.DataFrame(list(db["attendance_log"].find({}, {"_id": 0})))
    df_events = pd.DataFrame(list(db["events_log"].find({}, {"_id": 0})))
    
    # ... rest of your exact logic remains completely untouched!
    
    # Merge to ensure we have the human-readable course name and instructor
    df_merged = df_ast.merge(df_roster[['student_id', 'course_name', 'instructor']], on='student_id', how='left')
    
    # Clean up column names for the UI
    df_merged.rename(columns={
        'score': 'Score', 
        'course_name': 'Course Name', 
        'type': 'Assessment Type',
        'group_id': 'Cohort Group'
    }, inplace=True)
    
    df_merged['Assessment Type'] = df_merged['Assessment Type'].str.title()
    
    return df_merged, df_roster, df_att, df_events

def render(selected_course, selected_group):
    # Load Data
    df, roster, att, events = load_academic_data()
    
    c_primary = "#0EA5E9"  # Vibrant Sky Blue
    c_secondary = "#8B5CF6" # Vibrant Purple
    c_alert = "#FB7185"    # Soft Rose
    c_dots = "#64748B"     # Slate Gray

    # Apply Sidebar Filters
    if selected_course != "All Courses": 
        df = df[df['Course Name'] == selected_course]
        roster = roster[roster['course_name'] == selected_course]
    if selected_group != "All Groups": 
        df = df[df['Cohort Group'] == selected_group]
        roster = roster[roster['group_id'] == selected_group]

    # --- HEADER & OBJECTIVE ---
    st.markdown("### Academic Overview & Platform Scale")
    st.markdown(
        "Establish a baseline understanding of the platform's operational scale, student demographics, "
        "and overall grading variance across different courses and assessment types."
    )
    st.markdown("<br>", unsafe_allow_html=True)

    # --- PLATFORM QUICK STATS (KPIs) ---
    st.subheader("1. Operational Scale & Student Base")
    
    # Base Scale Metrics
    total_students = roster['student_id'].nunique()
    total_instructors = roster['instructor'].nunique()
    total_courses = roster['course_name'].nunique()
    total_groups = roster['group_id'].nunique()
    
    # New Behavioral & Demographic Metrics
    avg_age = roster['age'].mean() if 'age' in roster.columns else 0
    
    att['is_present'] = att['status'].str.lower() == 'attended'
    avg_att = (att['is_present'].sum() / len(att)) * 100 if len(att) > 0 else 0
    
    vid_events = events[events['event_type'] == 'video_watch']
    total_vid_hours = vid_events['duration_seconds'].sum() / 3600
    avg_vid_time = total_vid_hours / roster['student_id'].nunique() if roster['student_id'].nunique() > 0 else 0
    
    # Display Top Row (Scale)
    kpi1, kpi2, kpi3, kpi4 = st.columns(4)
    kpi1.metric("Total Enrolled Students", f"{total_students:,}")
    kpi2.metric("Active Instructors", f"{total_instructors:,}")
    kpi3.metric("Live Courses", f"{total_courses:,}")
    kpi4.metric("Active Cohort Groups", f"{total_groups:,}")
    
    st.markdown("<br>", unsafe_allow_html=True)
    
    # Display Bottom Row (Behaviors)
    kpi5, kpi6, kpi7 = st.columns(3)
    kpi5.metric("Average Student Age", f"{avg_age:.1f} Years")
    kpi6.metric("Global Live Attendance", f"{avg_att:.1f}%")
    kpi7.metric("Average Watch Time (Per Student)", f"{avg_vid_time:.1f} Hours")
    
    st.markdown("<br>", unsafe_allow_html=True)

    # --- DISTRIBUTION CHARTS (Scale Breakdown) ---
    col_dist1, col_dist2 = st.columns(2)
    
    with col_dist1:
        course_sizes = roster.groupby('course_name').size().reset_index(name='Students').sort_values('Students', ascending=True)
        fig_course = px.bar(
            course_sizes, x='Students', y='course_name', orientation='h',
            title="Student Distribution per Course",
            text='Students'
        )
        fig_course.update_traces(marker_color=c_primary, textposition='outside', cliponaxis=False)
        fig_course.update_layout(yaxis_title="", xaxis_title="Total Enrolled")
        fig_course.update_xaxes(range=[0, course_sizes['Students'].max() * 1.2])
        st.plotly_chart(clean_chart(fig_course), use_container_width=True)

    with col_dist2:
        group_sizes = roster.groupby('group_id').size().reset_index(name='Students').sort_values('Students', ascending=True)
        fig_group = px.bar(
            group_sizes, x='Students', y='group_id', orientation='h',
            title="Student Distribution per Cohort Group",
            text='Students'
        )
        fig_group.update_traces(marker_color=c_secondary, textposition='outside', cliponaxis=False)
        fig_group.update_layout(yaxis_title="", xaxis_title="Total Enrolled")
        fig_group.update_xaxes(range=[0, group_sizes['Students'].max() * 1.2])
        st.plotly_chart(clean_chart(fig_group), use_container_width=True)

    st.info( "**Takeaway:** Multiple groups are enrolled in the same course, which is expected in a shared learning environment. However, Group G10 stands out and warrants further investigation.")
    st.divider()

    # --- COURSE GRADE SPREAD ---
    st.subheader("2. Academic Performance & Consistency")
    st.markdown("Visualizing the highest, lowest, and average grades across courses to detect grading inconsistencies.")
    
    if selected_course == "All Courses" and not df.empty:
        course_stats = df.groupby('Course Name')['Score'].mean().reset_index().sort_values('Score', ascending=False)
        highest = course_stats.iloc[0]
        lowest = course_stats.iloc[-1]
        
        c1, c2 = st.columns(2)
        c1.success(f"**Highest Average Course:** {highest['Course Name']} ({highest['Score']:.1f}%)")
        c2.error(f"**Lowest Average Course:** {lowest['Course Name']} ({lowest['Score']:.1f}%)")
        
        fig_spread = px.box(
            df, x='Score', y='Course Name', orientation='h',
            title="Grade Ranges & Outliers by Course",
            points="outliers" # Only show outliers to keep it clean
        )
        fig_spread.update_traces(marker_color=c_dots)
        fig_spread.update_layout(yaxis={'categoryorder':'total ascending'}, yaxis_title="", xaxis_title="Assessment Score (%)")
        st.plotly_chart(clean_chart(fig_spread), use_container_width=True)
        
        st.info(
    "**Takeaway:** Performance distributions look healthy and fairly consistent across most courses. Digital Marketing shows slightly greater variation and deserves a closer look."
)
    elif selected_course != "All Courses":
        st.info("Filter is set to a specific course. Set the sidebar filter to 'All Courses' to compare performance across the curriculum.")

    st.divider()

    # --- ASSESSMENT VOLATILITY (REDESIGNED) ---
    st.subheader("3. Assessment Type Volatility")
    st.markdown("Identifying which test formats (Quizzes, Assignments, Exams) result in the most unpredictable scoring.")
    
    if not df.empty:
        # Calculate Standard Deviation to measure volatility
        volatility = df.groupby('Assessment Type')['Score'].std().reset_index().rename(columns={'Score': 'Fluctuation (Std Dev)'})
        volatility = volatility.sort_values('Fluctuation (Std Dev)', ascending=True) # Sort ascending for horizontal bar chart
        
        # Smart Coloring: Color the most volatile format RED, and the rest BLUE
        max_volatility = volatility['Fluctuation (Std Dev)'].max()
        volatility['Color'] = volatility['Fluctuation (Std Dev)'].apply(lambda x: c_alert if x == max_volatility else c_primary)
        
        fig_ast_type = go.Figure(go.Bar(
            x=volatility['Fluctuation (Std Dev)'], 
            y=volatility['Assessment Type'], 
            orientation='h',
            marker_color=volatility['Color'],
            text=volatility['Fluctuation (Std Dev)'].apply(lambda x: f"±{x:.1f} pts")
        ))
        
        fig_ast_type.update_traces(textposition='outside', cliponaxis=False)
        fig_ast_type.update_layout(
            title="Grade Predictability by Format (Standard Deviation)",
            yaxis_title="", 
            xaxis_title="Standard Deviation (Points Variance)"
        )
        fig_ast_type.update_xaxes(range=[0, max_volatility * 1.2]) # Add room for the text labels
        
        st.plotly_chart(clean_chart(fig_ast_type), use_container_width=True)
        
        most_volatile = volatility.iloc[-1] # Grabbing the top bar (highest value)
        st.info(f"**Takeaway:** **{most_volatile['Assessment Type']}s** (highlighted in red) are the least predictable tests. Scores randomly jump up and down by an average of ±{most_volatile['Fluctuation (Std Dev)']:.1f} points. High volatility indicates that the difficulty of these assessments varies or the formatting is confusing to students.")
