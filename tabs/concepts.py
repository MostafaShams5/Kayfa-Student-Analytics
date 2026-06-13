from pymongo import MongoClient
import streamlit as st
import pandas as pd
import numpy as np
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
        hovermode="y unified"
    )
    return fig

@st.cache_data
def load_concepts_data():
    """Loads concept mastery logs from MongoDB and joins them with roster context."""
    client = MongoClient(st.secrets["mongo"]["uri"])
    db = client["kayfa_analytics"]
    
    concepts = pd.DataFrame(list(db["concepts_log"].find({}, {"_id": 0})))
    roster = pd.DataFrame(list(db["unified_roster"].find({}, {"_id": 0})))
    
    # --- Do not change anything below this line! ---
    df = concepts.merge(roster[['student_id', 'course_name', 'group_id']], on='student_id', how='left')
    df['timestamp'] = pd.to_datetime(df['timestamp'], errors='coerce')
    
    return df

def render(selected_course, selected_group):
    df = load_concepts_data()
    
    # Vibrant Custom Palette
    c_primary = "#0EA5E9"  # Sky Blue
    c_secondary = "#8B5CF6" # Purple
    c_alert = "#FB7185"    # Soft Rose
    c_dots = "#64748B"     # Slate Gray
    c_trend = "#E11D48"    # Bold Crimson Red

    if selected_course != "All Courses": df = df[df['course_name'] == selected_course]
    if selected_group != "All Groups": df = df[df['group_id'] == selected_group]

    st.markdown("### Objective: Curriculum Concepts & Taxonomy")
    st.markdown("Isolate the exact knowledge nodes where students are failing, determine if the issue is systemic (platform-wide) or isolated to specific groups, and track if retention improves over time.")
    st.markdown("<br>", unsafe_allow_html=True)

    # --- 1. PLATFORM-WIDE VULNERABILITIES (Q6) ---
    st.subheader("1. Curriculum Vulnerability Scanner")
    st.markdown("Calculating the failure rate for every single concept taught on the platform to find the biggest pain points.")

    # Calculate Failure Rates
    concept_stats = df.groupby(['concept_name', 'course_name']).agg(
        total_attempts=('record_id', 'count'),
        fails=('mastery_status', lambda x: (x.str.lower() == 'failed').sum())
    ).reset_index()
    
    # Filter out noise (concepts tested fewer than 5 times)
    concept_stats = concept_stats[concept_stats['total_attempts'] > 5].copy()
    concept_stats['fail_rate'] = (concept_stats['fails'] / concept_stats['total_attempts']) * 100
    concept_stats = concept_stats.sort_values('fail_rate', ascending=False)
    
    if not concept_stats.empty:
        weakest = concept_stats.iloc[0]
        st.error(f" **Curriculum Weak Spot Detected:** The concept **'{weakest['concept_name']}'** (Course: {weakest['course_name']}) has a critical platform-wide failure rate of **{weakest['fail_rate']:.1f}%**.")

        # Plot Top 10 Hardest Concepts
        top_10 = concept_stats.head(10).sort_values('fail_rate', ascending=True) # Sort for horizontal bar
        
        # Color the absolute worst one red, the rest slate
        top_10['color'] = top_10['concept_name'].apply(lambda x: c_alert if x == weakest['concept_name'] else c_dots)
        
        fig_fails = go.Figure(go.Bar(
            x=top_10['fail_rate'], 
            y=top_10['concept_name'], 
            orientation='h',
            marker_color=top_10['color'],
            text=top_10['fail_rate'].apply(lambda x: f"{x:.1f}% Fail Rate")
        ))
        
        fig_fails.update_traces(textposition='outside', cliponaxis=False)
        fig_fails.update_layout(title="Top 10 Highest Failure Rates by Concept", xaxis_title="Failure Rate (%)", yaxis_title="")
        fig_fails.update_xaxes(range=[0, top_10['fail_rate'].max() * 1.2]) # Room for text
        st.plotly_chart(clean_chart(fig_fails), use_container_width=True)
        
        st.info(
    "**Insight:** The chart highlights topics with very high failure rates. For concepts like 'Recursion', the problem could come from either unclear learning materials or how the instructor explains them. At this point, it is important to investigate both sides to understand what is causing the difficulty."
)

        st.divider()

        # --- 2. DEEP DIVE INVESTIGATION (GROUPS & TIME) ---
        st.subheader(f"2. Deep Dive Investigation: '{weakest['concept_name']}'")
        st.markdown(f"We isolated the data for **{weakest['concept_name']}** to understand *who* is failing and if they are learning from their mistakes on subsequent tests.")
        
        # Filter raw data to only look at the weakest concept
        df_weakest = df[df['concept_name'] == weakest['concept_name']].copy()
        
        c_investigate1, c_investigate2 = st.columns(2)
        
        with c_investigate1:
            # Investigation A: Group Breakdown
            st.markdown("#### Is it the material or the instructor?")
            
            group_fails = df_weakest.groupby('group_id').agg(
                attempts=('record_id', 'count'),
                fails=('mastery_status', lambda x: (x.str.lower() == 'failed').sum())
            ).reset_index()
            group_fails['fail_rate'] = (group_fails['fails'] / group_fails['attempts']) * 100
            group_fails = group_fails.sort_values('fail_rate', ascending=False)
            
            fig_groups = px.bar(
                group_fails, x='group_id', y='fail_rate', 
                title=f"Failure Rate by Cohort",
                text=group_fails['fail_rate'].apply(lambda x: f"{x:.1f}%")
            )
            fig_groups.update_traces(marker_color=c_secondary, textposition='outside', cliponaxis=False)
            fig_groups.update_layout(yaxis_title="Failure Rate (%)", xaxis_title="Cohort Group")
            fig_groups.update_yaxes(range=[0, 115])
            st.plotly_chart(clean_chart(fig_groups), use_container_width=True)
            
        with c_investigate2:
            # Investigation B: Longitudinal Tracking (Q7)
            st.markdown("#### Cohort Mastery Over Time")
            
            df_weakest['week'] = df_weakest['timestamp'].dt.to_period('W').dt.start_time
            time_stats = df_weakest.groupby('week').agg(
                total=('record_id', 'count'), 
                passed=('mastery_status', lambda x: (x.str.lower() == 'passed').sum())
            ).reset_index()
            time_stats['pass_rate'] = (time_stats['passed'] / time_stats['total']) * 100
            
            # --- Smart Slope Detection ---
            trend_status = "Not Enough Data"
            trend_color = c_dots
            if len(time_stats) > 1:
                # Calculate days since start to use as numeric X for regression
                time_stats['days_elapsed'] = (time_stats['week'] - time_stats['week'].min()).dt.days
                slope, _ = np.polyfit(time_stats['days_elapsed'], time_stats['pass_rate'], 1)
                
                if slope > 0.15:
                    trend_status = "📈 IMPROVING"
                    trend_color = "#10B981" # Emerald Green
                elif slope < -0.15:
                    trend_status = "📉 DEGRADING (GETTING WORSE)"
                    trend_color = c_trend
                else:
                    trend_status = "➖ FLAT (NO IMPROVEMENT)"
                    trend_color = "#F59E0B" # Amber
            
            st.markdown(f"**Smart Trend Analysis:** Retention is <span style='color:{trend_color}; font-weight:bold;'>{trend_status}</span>", unsafe_allow_html=True)
            
            fig_time = px.scatter(
                time_stats, x='week', y='pass_rate', trendline='ols', 
                title="Pass Rate Across Successive Assessments"
            )
            fig_time.update_traces(mode='lines+markers', line=dict(color=c_primary, width=3), marker=dict(size=8))
            
            if len(fig_time.data) > 1:
                fig_time.data[1].line.color = trend_color
                
            # Add a 50% Threshold line
            fig_time.add_hline(y=50, line_dash="dot", line_color=c_dots, annotation_text="50% Pass Threshold", annotation_position="bottom right")
            fig_time.update_layout(yaxis_title="Pass Rate (%)", xaxis_title="Assessment Week")
            fig_time.update_yaxes(range=[-5, 105])
            st.plotly_chart(clean_chart(fig_time), use_container_width=True)

        st.error(
    "**Action:** High failure rates across all groups indicate the course material needs revision. Group-level gaps point to instructor differences that require review. A continued downward trend in performance signals the content should be redesigned and simplified."
)

    else:
        st.warning("Not enough concept tracking data available to generate insights.")
