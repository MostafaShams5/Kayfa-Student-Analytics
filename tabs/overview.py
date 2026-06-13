from pymongo import MongoClient
import streamlit as st
import pandas as pd
import plotly.express as px

@st.cache_data
def load_academic_data():
    ast_path = "/home/shams/Pictures/KayfeWeek2/data/unified_assessments.csv"
    roster_path = "/home/shams/Pictures/KayfeWeek2/data/unified_roster.csv"
    df_ast = pd.read_csv(ast_path)
    df_roster = pd.read_csv(roster_path)
    
    # Merge to get course names
    df_merged = df_ast.merge(df_roster[['student_id', 'course_name']], on='student_id', how='left')
    return df_merged

def render(selected_course, selected_group):
    st.subheader("System-Wide Academic Performance")
    
    df = load_academic_data()
    
    if df is None or df.empty:
        st.error("Could not load assessment data.")
        return

    # Apply Filters
    if selected_course != "All Courses":
        df = df[df['course_name'] == selected_course]
    
    # --- Question 3: Course Highs, Lows, and Spread ---
    st.markdown("### Course Performance & Grade Spread")
    
    if selected_course == "All Courses":
        # Calculate Aggregates
        course_stats = df.groupby('course_name')['score'].agg(['mean', 'std']).reset_index()
        course_stats = course_stats.sort_values('mean', ascending=False)
        highest_course = course_stats.iloc[0]
        lowest_course = course_stats.iloc[-1]
        
        c1, c2 = st.columns(2)
        with c1:
            st.info(f"**Highest Average:** {highest_course['course_name']} ({highest_course['mean']:.1f}%)")
        with c2:
            st.warning(f"**Lowest Average:** {lowest_course['course_name']} ({lowest_course['mean']:.1f}%)")
            
        fig_course_spread = px.box(
            df, x='course_name', y='score', color='course_name',
            title="Grade Spread Differences Between Courses",
            labels={'course_name': 'Course', 'score': 'Assessment Score (%)'}
        )
        st.plotly_chart(fig_course_spread, use_container_width=True)
    else:
        st.info("Set 'Select Course Filter' to 'All Courses' to compare cross-course metrics.")

    st.divider()

    # --- Question 2: Assessment Type Volatility ---
    st.markdown("### Assessment Type Volatility")
    st.markdown("Analyzing score stability across quizzes, assignments, practicals, and exams.")
    
    volatility = df.groupby('type')['score'].std().reset_index().rename(columns={'score': 'Std_Dev'})
    most_volatile = volatility.sort_values('Std_Dev', ascending=False).iloc[0]
    
    st.write(f"**Insight:** Performance is most volatile in **{most_volatile['type'].upper()}** assessments (Standard Deviation: ±{most_volatile['Std_Dev']:.1f}).")
    
    fig_ast_type = px.violin(
        df, x='type', y='score', box=True, points="all",
        title="Score Distribution by Assessment Type",
        color='type',
        labels={'type': 'Assessment Type', 'score': 'Score (%)'}
    )
    st.plotly_chart(fig_ast_type, use_container_width=True)
