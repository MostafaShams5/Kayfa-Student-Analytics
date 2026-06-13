import pandas as pd
from pymongo import MongoClient
import json
import toml
import os

# 1. Connect to MongoDB using your secrets file
secrets = toml.load(".streamlit/secrets.toml")
client = MongoClient(secrets["mongo"]["uri"])
db = client["kayfa_analytics"]

print("Connected to MongoDB Atlas...")

# 2. Create the Authentication User
db["users"].drop()
db["users"].insert_one({"username": "admin", "password": "password123"})
print("Created login user: admin / password123")

# 3. Upload all CSV files
csv_files = [
    "unified_roster", "unified_assessments", "attendance_log", 
    "events_log", "concepts_log", "concepts_performance", 
    "engagement_events", "assignment_submissions", "students", "courses", "groups"
]

for file in csv_files:
    path = f"data/{file}.csv"
    if os.path.exists(path):
        df = pd.read_csv(path)
        records = df.to_dict(orient='records')
        db[file].drop() # Clear old data
        if records:
            db[file].insert_many(records)
        print(f"Successfully uploaded {file}.csv")

# 4. Upload JSON file
if os.path.exists("data/grades.json"):
    with open("data/grades.json", "r") as f:
        grades_data = json.load(f)
        db["grades"].drop()
        if grades_data:
            db["grades"].insert_many(grades_data)
        print("Successfully uploaded grades.json")

print("Database migration complete! You can now run the app.")
