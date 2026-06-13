# Kayfa Analytics

The ETL and data processing pipeline is available here:
https://colab.research.google.com/drive/1uFt6v2lDsH_8FJs9hPKZapn2gqeG-4qF?usp=sharing

For a complete breakdown of the raw data issues, bugs, and edge cases we addressed during the cleaning phase, see the `33 Distinct Data Quality.md` file in this repository.

### Project Structure

```text
kayfa_analytics/
├── app.py                          # Main Streamlit app and routing
├── 33 Distinct Data Quality.md     # Log of data anomalies
├── assets/                         # Brand files
└── tabs/                           # Analytical modules
    ├── academics.py                # Grade variance
    ├── engagement.py               # Behavior and outcomes
    ├── trends.py                   # Term trajectories
    ├── concepts.py                 # Curriculum vulnerabilities
    ├── advanced.py                 # Segmentation and at-risk targets
    ├── admin.py                    # Cohort sizing and merges
    └── integrity.py                # System auditing
    ....
```

### Architecture Details

Analytics are precomputed and stored in MongoDB Atlas. The dashboard reads directly from Atlas (with authentication configured), features functional filters and useful KPIs, and is fully deployed and shareable.
