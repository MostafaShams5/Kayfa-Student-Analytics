from pymongo import MongoClient
import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
from dateutil.relativedelta import relativedelta

def clean_chart(fig):
    """Strips visual clutter and ensures large, readable labels."""
    fig.update_layout(
        plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)", 
        xaxis=dict(showgrid=True, gridcolor="#E2E8F0", zeroline=False, title_font=dict(size=14, color="#0F172A"), tickfont=dict(size=12, color="#475569")), 
        yaxis=dict(showgrid=True, gridcolor="#E2E8F0", zeroline=False, title_font=dict(size=14, color="#0F172A"), tickfont=dict(size=12, color="#475569")),
        margin=dict(t=50, b=40, l=40, r=30), font=dict(color="#0F172A"),
        hovermode="x unified",
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1, title="")
    )
    return fig

@st.cache_data
def load_growth_data():
    """Loads roster and events from MongoDB to determine true platform operating time."""
    client = MongoClient(st.secrets["mongo"]["uri"])
    db = client["kayfa_analytics"]
    
    roster = pd.DataFrame(list(db["unified_roster"].find({}, {"_id": 0})))
    events = pd.DataFrame(list(db["events_log"].find({}, {"_id": 0})))
    
    if 'enrollment_date' in roster.columns:
        roster['enrollment_date'] = pd.to_datetime(roster['enrollment_date'], errors='coerce')
        roster = roster.dropna(subset=['enrollment_date'])
        
    events['event_datetime'] = pd.to_datetime(events['event_datetime'], errors='coerce')
    
    # Calculate the TRUE active window of the platform
    start_date = roster['enrollment_date'].min()
    end_date = events['event_datetime'].max()
    
    if pd.isnull(end_date):
        end_date = start_date + pd.Timedelta(days=180) # Fallback to 6 months
        
    return roster, start_date, end_date

def calculate_forecast(df, start_date, end_date, end_year=2030, end_month=12):
    """Calculates smoothed growth velocity over the TRUE active term."""
    if df.empty:
        return pd.DataFrame(), pd.DataFrame(), 0

    total_students = len(df)
    
    # 1. Calculate EXACT Months Elapsed
    days_elapsed = (end_date - start_date).days
    if days_elapsed < 30: days_elapsed = 30
    months_elapsed = days_elapsed / 30.44
    
    # Velocity Math (Total Students / True Months Elapsed)
    velocity = total_students / months_elapsed
    
    # 2. Build Historical Timeline
    months_hist = pd.date_range(start=start_date.replace(day=1), end=end_date.replace(day=1), freq='MS')
    hist_cum = []
    
    for m in months_hist:
        count = len(df[df['enrollment_date'] <= (m + pd.offsets.MonthEnd(1))])
        hist_cum.append(count)
        
    hist_df = pd.DataFrame({'Month': months_hist, 'Cumulative': hist_cum})
    
    # 3. Build Forecast Timeline (From end of Term -> 2030)
    target_date = pd.to_datetime(f"{end_year}-{end_month}-01")
    months_fore = pd.date_range(start=end_date.replace(day=1), end=target_date, freq='MS')
    
    fore_cum = []
    current_cum = hist_df['Cumulative'].iloc[-1] if not hist_df.empty else total_students
    
    for i, m in enumerate(months_fore):
        if i == 0:
            fore_cum.append(current_cum) # Connect to last historical point seamlessly
        else:
            current_cum += velocity
            fore_cum.append(current_cum)
            
    fore_df = pd.DataFrame({'Month': months_fore, 'Cumulative': fore_cum})
    
    return hist_df, fore_df, velocity

def render(selected_course, selected_group):
    roster, start_date, end_date = load_growth_data()
    
    # Premium Forecasting Palette
    c_hist = "#2563EB"      # Solid Blue (Historical)
    c_forecast = "#10B981"  # Emerald Green (Forecast)
    color_palette = px.colors.qualitative.Prism # For Courses

    if selected_course != "All Courses": 
        roster = roster[roster['course_name'] == selected_course]
    if selected_group != "All Groups": 
        roster = roster[roster['group_id'] == selected_group]

    st.markdown("### Objective: Platform Growth & 2030 Forecasting")
    st.markdown("Calculate the smoothed enrollment velocity over the verified 6-month operating term, and map that exact slope to forecast platform and course scaling out to 2030.")
    st.markdown("<br>", unsafe_allow_html=True)

    if roster.empty:
        st.error("No valid enrollment data found.")
        return

    hist_df, forecast_df, avg_growth = calculate_forecast(roster, start_date, end_date)
    current_total = len(roster)
    projected_total = int(forecast_df['Cumulative'].iloc[-1])
    multiplier = (projected_total / current_total) if current_total > 0 else 0

    # --- TOP KPIs ---
    k1, k2, k3, k4 = st.columns(4)
    k1.metric("Verified Current Students", f"{current_total:,}")
    k2.metric("Smoothed Enrollment Velocity", f"+{int(avg_growth)} / month", "Based on 6-Month Term")
    k3.metric("Projected 2030 Scale", f"{projected_total:,} Students", f"{(multiplier*100)-100:.0f}% Growth")
    k4.metric("Platform Multiplier", f"{multiplier:.1f}x Size", "By Dec 2030")
    st.markdown("<br>", unsafe_allow_html=True)

    # ==========================================
    # 1. OVERALL PLATFORM FORECASTING
    # ==========================================
    st.subheader("1. Global Platform Trajectory")
    
    fig_global = go.Figure()
    
    # Solid Historical Line
    fig_global.add_trace(go.Scatter(
        x=hist_df['Month'], y=hist_df['Cumulative'],
        mode='lines', line=dict(color=c_hist, width=4),
        fill='tozeroy', fillcolor='rgba(37, 99, 235, 0.2)', name='Historical Base'
    ))
    
    # Dashed Forecast Line
    fig_global.add_trace(go.Scatter(
        x=forecast_df['Month'], y=forecast_df['Cumulative'],
        mode='lines', line=dict(color=c_forecast, width=4, dash='dash'),
        fill='tozeroy', fillcolor='rgba(16, 185, 129, 0.1)', name='Projected Trajectory'
    ))
    
    fig_global.update_layout(title="Platform Growth: Historical Base to 2030 Projection", xaxis_title="Timeline", yaxis_title="Total Enrolled")
    fig_global.update_yaxes(range=[0, projected_total * 1.1]) 
    st.plotly_chart(clean_chart(fig_global), use_container_width=True)

    st.info(f" **Takeaway:** The solid blue area shows our verified start. Based on the calculated velocity of **+{int(avg_growth)} students/month**, the dashed green line projects platform scale hitting **{projected_total:,} total enrollments** by 2030. Infrastructure and hiring must scale to meet this {multiplier:.1f}x multiplier.")
    st.divider()

    # ==========================================
    # 2. COURSE-LEVEL FORECASTING
    # ==========================================
    st.subheader("2. Course-by-Course Trajectories")
    
    courses = roster['course_name'].unique()
    fig_courses = go.Figure()
    
    for i, course in enumerate(courses):
        c_df = roster[roster['course_name'] == course].copy()
        c_hist, c_fore, c_avg = calculate_forecast(c_df, start_date, end_date)
        
        if not c_hist.empty and not c_fore.empty:
            c_color = color_palette[i % len(color_palette)]
            
            # Solid Historical Line
            fig_courses.add_trace(go.Scatter(
                x=c_hist['Month'], y=c_hist['Cumulative'],
                mode='lines', line=dict(color=c_color, width=3),
                name=f"{course}", legendgroup=course
            ))
            
            # Dashed Forecast Line
            fig_courses.add_trace(go.Scatter(
                x=c_fore['Month'], y=c_fore['Cumulative'],
                mode='lines', line=dict(color=c_color, width=3, dash='dot'),
                name=f"{course} (Projected)", legendgroup=course, showlegend=False
            ))

    fig_courses.update_layout(title="Projected Course Splits to Dec 2030", xaxis_title="Timeline", yaxis_title="Students Enrolled")
    st.plotly_chart(clean_chart(fig_courses), use_container_width=True)
        
    st.info(" **Insight:** Tracking the courses together on the same timeline reveals which curriculums scale the fastest. The steepness of the dashed lines on the far right indicates which specific courses will require the most immediate instructor hiring over the next 4 years.")
