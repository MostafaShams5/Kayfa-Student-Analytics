# 33 Distinct Data-Quality Problems

### Cross-File & Relational Integrity

**1.** **Ghost Students:** Transactions logged for student IDs that do not exist in the main database. **Dropped**

**2.** **Orphaned Submissions:** Assignments successfully submitted but missing entirely from the grading database. **Flagged**

**3.** **Phantom Grades:** Quiz grades awarded on days with absolutely zero platform activity. **Flagged**

**4.** **Ghost Submissions:** Assignments submitted on days with zero platform activity. **Flagged**

**5.** **Chain Breaks:** Grades logged under a course chain the student is not officially enrolled in. **Dropped**

**6.** **Syllabus Hallucinations:** Students evaluated on concepts belonging to a completely different course. **Dropped**

**7.** **Prefix Contradictions:** Assessment or concept ID prefixes directly mismatch the logged Course ID. **Dropped**

**8.** **Schedule Violations:** Attendance marked on weekdays that contradict the official group schedule. **Fixed**

**9.** **Duration Overruns:** Attendance logged weeks after the official course end date. **Flagged**

**10.** **Temporal Collisions:** The same student having two different attendance records at the exact same second. **Dropped**

**11.** **Spam Submissions:** The exact same assignment submitted multiple times by the same student. **Dropped**

**12.** **Absent but Graded:** Students marked strictly absent for a session but receiving a graded score for it. **Flagged**

### Base Table Errors

**13.** **Redundant Columns:** Columns like `short_description` and `group_name` simply repeat data from other columns. **Dropped**

**14.** **Static Columns:** The `is_active` column is true for every single row, adding no value. **Dropped**

**15.** **Primary Key Duplicates:** Duplicate `student_id` and `submission_id` rows breaking unique constraints. **Dropped**

**16.** **Full Row Duplicates:** Exact duplicate event and attendance rows caused by ingestion loops. **Dropped**

**17.** **Dummy Entities:** Test groups (e.g., `G99`) left in production tables. **Dropped**

**18.** **Test Transactions:** Dummy system IDs (e.g., `SUBBAD1`, `CPX00001`) left in transaction logs. **Dropped**

**19.** **Schema Shifts:** Columns arbitrarily renamed (e.g., `session_datetime` to `datetime`) in specific month batches. **Fixed**

**20.** **Format Chaos:** Time, gender, and attendance status mixing multiple formats and encodings. **Fixed**

**21.** **Negative Demographics:** Student ages recorded as negative numbers due to typos. **Fixed**

**22.** **Outlier Demographics:** Student ages recorded as impossibly high for adult learners. **Fixed**

**23.** **Missing Identifiers:** Completely blank student names and emails. **Fixed**

**24.** **Broken Strings:** Malformed email addresses missing domains (e.g., `missing@`). **Fixed**

**25.** **Label Contradictions:** Gender labels strictly contradicting the recognized student names. **Fixed**

**26.** **The Draft Bug:** Submissions missing the final `submitted_at` timestamp despite tracking effort. **Dropped**

**27.** **Logic Inversions:** System calculating the `is_late` flag incorrectly compared to the raw timestamps. **Fixed**

**28.** **Negative Metrics:** Negative time spent on assignments and negative video watch durations. **Fixed**

**29.** **Bot Anomalies:** Video watch durations exceeding 27 hours straight. **Fixed**

**30.** **Scaling Failures:** The `max_score` for grades arbitrarily dropping to 10 instead of 100. **Fixed**

**31.** **Broken Math:** Quiz and concept scores left blank, negative, or exceeding 100%. **Fixed**

**32.** **Time Travelers:** Event timestamps logged months before the term started or years after it ended. **Dropped**

**33.** **Corrupted Text:** Concept names reduced to garbled encoding errors. **Dropped**
