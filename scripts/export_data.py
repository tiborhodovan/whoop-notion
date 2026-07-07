import os
import json
import time
import requests

NOTION_TOKEN = os.environ["NOTION_TOKEN"]
DATABASE_ID = os.environ["NOTION_DATABASE_ID"]
WORKOUT_DATABASE_ID = os.environ["NOTION_WORKOUT_DATABASE_ID"]

headers = {
    "Authorization": f"Bearer {NOTION_TOKEN}",
    "Content-Type": "application/json",
    "Notion-Version": "2022-06-28"
}

def get_num(props, key):
    return props.get(key, {}).get("number")

def get_date(props, key):
    d = props.get(key, {}).get("date")
    return d.get("start") if d else None

def get_select(props, key):
    s = props.get(key, {}).get("select")
    return s.get("name") if s else None

def query_all(database_id):
    all_pages = []
    cursor = None
    while True:
        body = {"page_size": 100}
        if cursor:
            body["start_cursor"] = cursor
        response = requests.post(
            f"https://api.notion.com/v1/databases/{database_id}/query",
            headers=headers, json=body, timeout=30
        )
        data = response.json()
        all_pages.extend(data.get("results", []))
        if not data.get("has_more"):
            break
        cursor = data.get("next_cursor")
        time.sleep(0.3)
    return all_pages

print("Exporting daily data...")
daily_pages = query_all(DATABASE_ID)
daily_records = []
for page in daily_pages:
    p = page.get("properties", {})
    date = get_date(p, "Date")
    if not date:
        continue
    daily_records.append({
        "date": date,
        "recovery": get_num(p, "Recovery"),
        "hrv": get_num(p, "HRV"),
        "restingHr": get_num(p, "Resting HR"),
        "strain": get_num(p, "Strain"),
        "sleepPerformance": get_num(p, "Sleep Performance"),
        "sleepDuration": get_num(p, "Sleep Duration"),
        "sleepNeed": get_num(p, "Sleep Need"),
        "spo2": get_num(p, "SPO2"),
        "skinTemp": get_num(p, "Skin Temp"),
        "respiratoryRate": get_num(p, "Respiratory Rate"),
        "calories": get_num(p, "Calories"),
        "avgHr": get_num(p, "Avg HR"),
        "maxHr": get_num(p, "Max HR"),
        "sleepEfficiency": get_num(p, "Sleep Efficiency"),
    })
daily_records.sort(key=lambda r: r["date"])
print(f"Daily records: {len(daily_records)}")

print("Exporting workout data...")
workout_pages = query_all(WORKOUT_DATABASE_ID)
workout_records = []
for page in workout_pages:
    p = page.get("properties", {})
    date = get_date(p, "Date")
    if not date:
        continue
    workout_records.append({
        "date": date,
        "sport": get_select(p, "Sport"),
        "strain": get_num(p, "Strain"),
        "avgHr": get_num(p, "Avg HR"),
        "maxHr": get_num(p, "Max HR"),
        "calories": get_num(p, "Calories"),
        "duration": get_num(p, "Duration (min)"),
    })
workout_records.sort(key=lambda r: r["date"])
print(f"Workout records: {len(workout_records)}")

output = {"daily": daily_records, "workouts": workout_records}

os.makedirs("docs", exist_ok=True)
with open("docs/data.json", "w") as f:
    json.dump(output, f)

print(f"OK -> docs/data.json ({len(daily_records)} daily, {len(workout_records)} workouts)")
