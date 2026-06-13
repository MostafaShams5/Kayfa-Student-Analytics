from pymongo import MongoClient
import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
from sklearn.preprocessing import MinMaxScaler

def clean_chart(fig):
    fig.update_layout(
        plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)", 
        xaxis=dict(showgrid=True, gridcolor="#E2E8F0", zeroline=False, title_font=dict(size=14, color="#0F172A"), tickfont=dict(size=12, color="#475569")), 
        yaxis=dict(showgrid=True, gridcolor="#E2E8F0", zeroline=False, title_font=dict(size=14, color="#0F172A"), tickfont=dict(size=12, color="#475569")),
        margin=dict(t=50, b=40, l=40, r=30), font=dict(color="#0F172A"),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1, font=dict(size=13))
    )
    return fig

@st.cache_data
def build_student_profiles():
    client = MongoClient(st.secrets["mongo"]["uri"])
    db = client["kayfa_analytics"]
    
    roster = pd.DataFrame(list(db["unified_roster"].find({}, {"_id": 0})))
    ast = pd.DataFrame(list(db["unified_assessments"].find({}, {"_id": 0})))
    att = pd.DataFrame(list(db["attendance_log"].find({}, {"_id": 0})))
    events = pd.DataFrame(list(db["events_log"].find({}, {"_id": 0})))
    concepts = pd.DataFrame(list(db["concepts_log"].find({}, {"_id": 0})))

    # 1. Base Metrics
    grades = ast.groupby('student_id')['score'].mean().reset_index(name='Average Grade (%)')

    att['is_present'] = att['status'].str.lower() == 'attended'
    attendance = att.groupby('student_id').agg(total=('record_id','count'), present=('is_present','sum')).reset_index()
    attendance['Attendance Rate (%)'] = (attendance['present'] / attendance['total']) * 100
    events_count = events.groupby('student_id').size().reset_index(name='Platform Events')
    fails = concepts[concepts['mastery_status'].str.lower() == 'failed'].groupby('student_id').size().reset_index(name='Failed Concepts')

    #  THE FIX: Calculate DECLINING Engagement
    events['event_datetime'] = pd.to_datetime(events['event_datetime'], errors='coerce')
    mid_date = events['event_datetime'].min() + (events['event_datetime'].max() - events['event_datetime'].min()) / 2
    
    first_half = events[events['event_datetime'] < mid_date].groupby('student_id').size().reset_index(name='H1_Events')
    second_half = events[events['event_datetime'] >= mid_date].groupby('student_id').size().reset_index(name='H2_Events')

    df = roster[['student_id', 'full_name', 'email', 'course_name', 'group_id']].copy()
    df = df.merge(grades, on='student_id', how='left').merge(attendance[['student_id', 'Attendance Rate (%)']], on='student_id', how='left')\
           .merge(events_count, on='student_id', how='left').merge(fails, on='student_id', how='left')\
           .merge(first_half, on='student_id', how='left').merge(second_half, on='student_id', how='left')
    
    df.fillna({'Average Grade (%)': 0, 'Attendance Rate (%)': 0, 'Platform Events': 0, 'Failed Concepts': 0, 'H1_Events': 0, 'H2_Events': 0}, inplace=True)
    
    # Calculate exactly how many fewer events they did in the second half of the term
    df['Engagement Drop'] = df['H1_Events'] - df['H2_Events']
    df['Engagement Drop'] = df['Engagement Drop'].clip(lower=0) # We only penalize drops, not increases
    
    scaler = MinMaxScaler(feature_range=(0, 100))
    df['Normalized Events'] = scaler.fit_transform(df[['Platform Events']])
    df['Effort Score'] = (df['Attendance Rate (%)'] * 0.6) + (df['Normalized Events'] * 0.4)
    
    return df

def render(selected_course, selected_group):
    df = build_student_profiles()
    
    c_high, c_struggle, c_coast, c_risk, c_dots, c_secondary = "#10B981", "#F59E0B", "#0EA5E9", "#E11D48", "#64748B", "#8B5CF6"

    if selected_course != "All Courses": df = df[df['course_name'] == selected_course]
    if selected_group != "All Groups": df = df[df['group_id'] == selected_group]

    st.markdown("### Objective: Advanced Telemetry & Intervention")
    st.markdown("Use multi-variable algorithms to segment the student population into psychological profiles, run an At-Risk ranking engine, and automatically detect failing cohorts.")
    st.markdown("<br>", unsafe_allow_html=True)

    # --- 1. SEGMENTATION ---
    st.subheader("1. Population Psychological Segmentation")
    med_grade = df['Average Grade (%)'].median()
    med_effort = df['Effort Score'].median()

    def assign_segment(row):
        if row['Average Grade (%)'] >= med_grade and row['Effort Score'] >= med_effort: return 'High Achievers'
        if row['Average Grade (%)'] < med_grade and row['Effort Score'] >= med_effort: return 'Struggling but Engaged'
        if row['Average Grade (%)'] >= med_grade and row['Effort Score'] < med_effort: return 'Independent / Coasting'
        return 'Disengaged & At-Risk'

    df['Student Segment'] = df.apply(assign_segment, axis=1)
    seg_palette = {'High Achievers': c_high, 'Struggling but Engaged': c_struggle, 'Independent / Coasting': c_coast, 'Disengaged & At-Risk': c_risk}

    c_seg1, c_seg2 = st.columns([1.2, 1])
    with c_seg1:
        fig_scatter = px.scatter(
            df, x='Effort Score', y='Average Grade (%)', color='Student Segment',
            hover_data=['full_name', 'Failed Concepts'], title="Outcomes vs. Effort Matrix", color_discrete_map=seg_palette
        )
        fig_scatter.add_vline(x=med_effort, line_dash="dash", line_color=c_dots, opacity=0.5)
        fig_scatter.add_hline(y=med_grade, line_dash="dash", line_color=c_dots, opacity=0.5)
        st.plotly_chart(clean_chart(fig_scatter), use_container_width=True)

    with c_seg2:
        seg_profiles = df.groupby('Student Segment')[['Average Grade (%)', 'Attendance Rate (%)']].mean().reset_index()
        fig_bars = go.Figure()
        fig_bars.add_trace(go.Bar(name='Avg Grade', x=seg_profiles['Student Segment'], y=seg_profiles['Average Grade (%)'], marker_color=c_coast))
        fig_bars.add_trace(go.Bar(name='Avg Attendance', x=seg_profiles['Student Segment'], y=seg_profiles['Attendance Rate (%)'], marker_color=c_dots))
        fig_bars.update_layout(barmode='group', title="What defines these segments?", xaxis_title="", yaxis_title="Percentage (%)")
        st.plotly_chart(clean_chart(fig_bars), use_container_width=True)

    segment_pcts = (df['Student Segment'].value_counts(normalize=True) * 100).to_dict()
    pct_string = ", ".join([f"**{k}** ({v:.1f}%)" for k, v in segment_pcts.items()])
    st.info(f" **Takeaway:** Population Breakdown: {pct_string}. It's all good")

    st.divider()

    # --- 2. THE FIX: URGENT AT-RISK ENGINE (WITH DECLINING ENGAGEMENT) ---
    st.subheader("2. Urgent Intervention Target List")
    st.markdown("The algorithm flags students based on: **Low Grades (30%) + Low Attendance (25%) + Failed Concepts (25%) + Declining Engagement (20%)**.")

    max_fails = df['Failed Concepts'].max() if df['Failed Concepts'].max() > 0 else 1
    max_drop = df['Engagement Drop'].max() if df['Engagement Drop'].max() > 0 else 1
    
    df['Risk Score'] = (
        ((100 - df['Average Grade (%)']) / 100 * 30) + 
        ((100 - df['Attendance Rate (%)']) / 100 * 25) + 
        ((df['Failed Concepts'] / max_fails) * 25) +
        ((df['Engagement Drop'] / max_drop) * 20)  # Added Declining Engagement!
    ) * 100 

    dup_emails = df[df.duplicated('email', keep=False)]['email'].dropna().unique()
    df['Contact Email'] = df['email'].apply(lambda x: "" if pd.isna(x) or x in dup_emails else x)

    top_10 = df.sort_values('Risk Score', ascending=False).head(10).copy()
    display_cols = ['student_id', 'full_name', 'Contact Email', 'group_id', 'Average Grade (%)', 'Attendance Rate (%)', 'Failed Concepts', 'Engagement Drop']
    
    clean_top10 = top_10[display_cols].rename(columns={
        'student_id': 'ID', 'full_name': 'Student Name', 'group_id': 'Cohort',
        'Average Grade (%)': 'Academic Avg', 'Attendance Rate (%)': 'Attendance', 'Engagement Drop': 'Recent Drop (Events)'
    })
    
    clean_top10['Academic Avg'] = clean_top10['Academic Avg'].round(1).astype(str) + "%"
    clean_top10['Attendance'] = clean_top10['Attendance'].round(1).astype(str) + "%"
    clean_top10['Recent Drop (Events)'] = "-" + clean_top10['Recent Drop (Events)'].astype(int).astype(str) + " acts"

    st.dataframe(clean_top10, use_container_width=True, hide_index=True)

    # --- 3. SMART ANOMALY DETECTOR ---
    c_comp1, c_comp2 = st.columns(2)
    with c_comp1:
        df['Is Top 10'] = df['student_id'].isin(top_10['student_id'])
        comp_stats = df.groupby('Is Top 10').agg(Grade=('Average Grade (%)', 'mean'), Attendance=('Attendance Rate (%)', 'mean')).reset_index()
        comp_stats['Group'] = comp_stats['Is Top 10'].apply(lambda x: "Top 10 At-Risk" if x else "Rest of Platform")

        fig_comp = go.Figure()
        fig_comp.add_trace(go.Bar(name='Average Grade', x=comp_stats['Group'], y=comp_stats['Grade'], marker_color=c_secondary))
        fig_comp.add_trace(go.Bar(name='Average Attendance', x=comp_stats['Group'], y=comp_stats['Attendance'], marker_color=c_dots))
        fig_comp.update_layout(barmode='group', title="Top 10 vs Platform Reality", xaxis_title="")
        st.plotly_chart(clean_chart(fig_comp), use_container_width=True)

    with c_comp2:
        most_common_group = top_10['group_id'].mode()[0]
        group_count = len(top_10[top_10['group_id'] == most_common_group])
        
        if group_count >= 3:
            anomaly_df = df[df['group_id'] == most_common_group].copy()
            anomaly_df['Status'] = anomaly_df['student_id'].isin(top_10['student_id']).apply(lambda x: "At-Risk Target" if x else "Healthy Classmates")
            anom_stats = anomaly_df.groupby('Status').agg(Grade=('Average Grade (%)', 'mean'), Fails=('Failed Concepts', 'mean')).reset_index()

            fig_anom = go.Figure()
            fig_anom.add_trace(go.Bar(name='Avg Grade', x=anom_stats['Status'], y=anom_stats['Grade'], marker_color=c_risk))
            fig_anom.add_trace(go.Bar(name='Avg Concept Fails', x=anom_stats['Status'], y=anom_stats['Fails'], marker_color=c_dots))
            fig_anom.update_layout(barmode='group', title=f"Internal Comparison: Inside {most_common_group} ({group_count} At-Risk)", xaxis_title="")
            st.plotly_chart(clean_chart(fig_anom), use_container_width=True)
        else:
            effort_comp = df.groupby('Is Top 10').agg(Effort=('Effort Score', 'mean')).reset_index()
            effort_comp['Group'] = effort_comp['Is Top 10'].apply(lambda x: "Top 10 At-Risk" if x else "Rest of Platform")
            fig_eff = px.bar(effort_comp, x='Group', y='Effort', title="Effort Score Comparison", text=effort_comp['Effort'].apply(lambda x: f"{x:.1f} pts"), color_discrete_sequence=[c_coast])
            fig_eff.update_traces(textposition='outside')
            st.plotly_chart(clean_chart(fig_eff), use_container_width=True)
            
    st.error(
    "**Action:** A meeting is required with the G07 instructor to review performance issues, understand the underlying causes, and agree on corrective steps to improve student outcomes."
)
