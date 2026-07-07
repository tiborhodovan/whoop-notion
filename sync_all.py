import base64
from nacl import encoding, public

def update_github_secret(secret_name, secret_value):
    gh_pat = os.getenv("GH_PAT")
    repo = os.getenv("GITHUB_REPOSITORY")
    if not gh_pat or not repo:
        print("GH_PAT vagy GITHUB_REPOSITORY hiányzik, secret update kihagyva.")
        return

    headers = {
        "Authorization": f"Bearer {gh_pat}",
        "Accept": "application/vnd.github+json",
    }

    key_resp = requests.get(
        f"https://api.github.com/repos/{repo}/actions/secrets/public-key",
        headers=headers,
        timeout=30,
    )
    key_resp.raise_for_status()
    key_data = key_resp.json()

    public_key = public.PublicKey(key_data["key"], encoding.Base64Encoder())
    sealed_box = public.SealedBox(public_key)
    encrypted = sealed_box.encrypt(secret_value.encode("utf-8"))
    encrypted_value = base64.b64encode(encrypted).decode("utf-8")

    put_resp = requests.put(
        f"https://api.github.com/repos/{repo}/actions/secrets/{secret_name}",
        headers=headers,
        json={"encrypted_value": encrypted_value, "key_id": key_data["key_id"]},
        timeout=30,
    )
    put_resp.raise_for_status()
    print(f"GitHub Secret '{secret_name}' frissítve.")
import os
import sys
import time
import subprocess
import requests
from datetime import datetime, timedelta, timezone

NOTION_TOKEN = os.environ["NOTION_TOKEN"]
DATABASE_ID = os.environ["NOTION_DATABASE_ID"]
WORKOUT_DATABASE_ID = os.environ["NOTION_WORKOUT_DATABASE_ID"]
WHOOP_CLIENT_ID = os.environ["WHOOP_CLIENT_ID"]
WHOOP_CLIENT_SECRET = os.environ["WHOOP_CLIENT_SECRET"]
WHOOP_REFRESH_TOKEN = os.environ["WHOOP_REFRESH_TOKEN"]

notion_headers = {
    "Authorization": f"Bearer {NOTION_TOKEN}",
    "Content-Type": "application/json",
    "Notion-Version": "2022-06-28"
}

SPORT_NAMES = {
    -1: "Activity", 0: "Running", 1: "Cycling", 16: "Baseball", 17: "Basketball",
    18: "Rowing", 19: "Fencing", 20: "Field Hockey", 21: "Football", 22: "Golf",
    24: "Ice Hockey", 25: "Lacrosse", 27: "Rugby", 28: "Sailing", 29: "Skiing",
    30: "Soccer", 31: "Softball", 32: "Squash", 33: "Swimming", 34: "Tennis",
    35: "Track & Field", 36: "Volleyball", 37: "Water Polo", 38: "Wrestling",
    39: "Boxing", 42: "Dance", 43: "Pilates", 44: "Yoga", 45: "Weightlifting",
    47: "Cross Country Skiing", 48: "Functional Fitness", 49: "Duathlon",
    51: "Gymnastics", 52: "Hiking / Rucking", 53: "Horseback Riding",
    55: "Kayaking", 56: "Martial Arts", 57: "Mountain Biking", 59: "Powerlifting",
    60: "Rock Climbing", 61: "Paddleboarding", 62: "Triathlon", 63: "Walking",
    64: "Surfing", 65: "Elliptical", 66: "Stairmaster", 70: "Meditation",
    71: "Other", 73: "Diving", 74: "Operations - Tactical", 75: "Operations - Medical",
    76: "Operations - Flying", 77: "Operations - Water", 82: "Ultimate",
    83: "Climber", 84: "Jumping Rope", 85: "Australian Football",
    86: "Skateboarding", 87: "Coaching", 88: "Ice Bath", 89: "Commuting",
    90: "Gaming", 91: "Snowboarding", 92: "Motocross", 93: "Caddying",
    94: "Obstacle Course Racing", 95: "Motor Racing", 96: "HIIT", 97: "Spin",
    98: "Jiu Jitsu", 99: "Manual Labor", 100: "Cricket", 101: "Pickleball",
    102: "Inline Skating", 103: "Box Fitness", 104: "Spikeball",
    105: "Wheelchair Pushing", 106: "Paddle Tennis", 107: "Barre",
    108: "Stage Performance", 109: "High Stress Work", 110: "Parkour",
    111: "Gaelic Football", 112: "Hurling / Camogie", 113: "Circus Arts",
    121: "Massage Therapy", 125: "Watching Sports", 126: "Assault Bike",
    127: "Kickboxing", 128: "Stretching", 230: "Table Tennis", 231: "Badminton",
    232: "Netball", 233: "Sauna", 234: "Cold Water Immersion",
    235: "Wheelchair Racing",
}

def get_sport_name(sport_id):
    return SPORT_NAMES.get(sport_id, f"Sport {sport_id}")

def safe_json(response):
    try:
        return response.json()
    except Exception:
        return {}

def refresh_whoop_token(refresh_token):
    print("Refreshing WHOOP token...")
    response = requests.post(
        "https://api.prod.whoop.com/oauth/oauth2/token",
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        data={
            "grant_type": "refresh_token",
            "refresh_token": refresh_token,
            "client_id": WHOOP_CLIENT_ID,
            "client_secret": WHOOP_CLIENT_SECRET,
            "scope": "offline read:recovery read:sleep read:workout read:cycles read:body_measurement",
        },
        timeout=30,
    )
    if response.status_code != 200:
        raise RuntimeError(f"Token refresh failed: {response.status_code} {response.text}")
    data = response.json()
    access_token = data.get("access_token")
    new_refresh_token = data.get("refresh_token")
    if not access_token or not new_refresh_token:
        raise RuntimeError("WHOOP refresh valaszban hianyzik token")
    print("Token refreshed OK")
    return access_token, new_refresh_token

WHOOP_ACCESS_TOKEN, NEW_REFRESH_TOKEN = refresh_whoop_token(WHOOP_REFRESH_TOKEN)

def get_whoop_headers():
    return {"Authorization": f"Bearer {WHOOP_ACCESS_TOKEN}"}

def whoop_get(url, max_retries=5):
    global WHOOP_ACCESS_TOKEN, NEW_REFRESH_TOKEN
    for attempt in range(max_retries):
        response = requests.get(url, headers=get_whoop_headers(), timeout=30)
        if response.status_code == 429:
            wait = min(60, 5 * (attempt + 1))
            print(f"WHOOP rate limited, waiting {wait}s...")
            time.sleep(wait)
            continue
        if response.status_code == 401:
            print("WHOOP 401, refreshing token and retrying...")
            WHOOP_ACCESS_TOKEN, NEW_REFRESH_TOKEN = refresh_whoop_token(NEW_REFRESH_TOKEN)
            time.sleep(1)
            continue
        if response.status_code >= 500:
            wait = 3 * (attempt + 1)
            print(f"WHOOP server error {response.status_code}, retry {wait}s...")
            time.sleep(wait)
            continue
        if response.status_code != 200:
            raise RuntimeError(f"WHOOP hiba: {response.status_code} {response.text}")
        return response
    raise RuntimeError(f"WHOOP keres sikertelen: {url}")

def notion_request(method, url, json_body=None, max_retries=5):
    for attempt in range(max_retries):
        response = requests.request(method, url, headers=notion_headers, json=json_body, timeout=30)
        if response.status_code == 429:
            retry_after = response.headers.get("Retry-After")
            wait = int(retry_after) if retry_after and retry_after.isdigit() else min(20, 2 * (attempt + 1))
            print(f"Notion rate limited, waiting {wait}s...")
            time.sleep(wait)
            continue
        if response.status_code >= 500:
            time.sleep(2 * (attempt + 1))
            continue
        if response.status_code not in (200, 201):
            raise RuntimeError(f"Notion hiba: {response.status_code} {response.text}")
        return response
    raise RuntimeError(f"Notion keres sikertelen: {url}")

def fetch_whoop_paginated(url_base):
    records = []
    next_token = None
    while True:
        url = url_base + (f"?nextToken={next_token}" if next_token else "")
        response = whoop_get(url)
        data = response.json()
        records.extend(data.get("records", []))
        next_token = data.get("next_token")
        time.sleep(0.4)
        if not next_token:
            break
    return records

def fetch_existing_pages(database_id, key_prop="Name"):
    existing = {}
    has_more = True
    start_cursor = None
    while has_more:
        body = {"page_size": 100}
        if start_cursor:
            body["start_cursor"] = start_cursor
        result = safe_json(notion_request("POST", f"https://api.notion.com/v1/databases/{database_id}/query", json_body=body))
        for page in result.get("results", []):
            try:
                title_prop = page["properties"][key_prop]["title"]
                if title_prop:
                    title = title_prop[0]["text"]["content"].strip()
                    existing[title] = page["id"]
            except Exception:
                pass
        has_more = result.get("has_more", False)
        start_cursor = result.get("next_cursor")
        time.sleep(0.3)
    return existing

def sync_daily():
    print("=== DAILY SYNC (recovery/sleep/cycle) ===")
    existing_dates = fetch_existing_pages(DATABASE_ID)
    print(f"Existing Notion pages: {len(existing_dates)}")

    print("FETCHING RECOVERY...")
    recovery_records = fetch_whoop_paginated("https://api.prod.whoop.com/developer/v2/recovery")
    print("FETCHING SLEEP...")
    sleep_records = fetch_whoop_paginated("https://api.prod.whoop.com/developer/v2/activity/sleep")
    print("FETCHING CYCLE...")
    cycle_records = fetch_whoop_paginated("https://api.prod.whoop.com/developer/v2/cycle")

    all_days = {}
    cycle_date_by_id = {}

    for record in cycle_records:
        if not record.get("start"):
            continue
        cycle_id = record.get("id")
        try:
            start_dt = datetime.strptime(record["start"][:10], "%Y-%m-%d")
            date = (start_dt + timedelta(days=1)).strftime("%Y-%m-%d")
        except Exception:
            date = record.get("end", "")[:10]
        if not date:
            continue
        if cycle_id is not None:
            cycle_date_by_id[cycle_id] = date
        all_days.setdefault(date, {})
        score = record.get("score") or {}
        kilojoule = score.get("kilojoule")
        calories = round(kilojoule * 0.239006, 4) if kilojoule is not None else None
        all_days[date].update({
            "Strain": score.get("strain"),
            "Calories": calories,
            "Avg HR": score.get("average_heart_rate"),
            "Max HR": score.get("max_heart_rate"),
        })

    recovery_added = set()
    for record in recovery_records:
        if record.get("score_state") != "SCORED":
            continue
        cycle_id = record.get("cycle_id")
        date = cycle_date_by_id.get(cycle_id)
        if not date:
            date = record.get("created_at", "")[:10]
        if not date:
            continue
        if date in recovery_added:
            continue
        recovery_added.add(date)
        all_days.setdefault(date, {})
        score = record.get("score") or {}
        all_days[date].update({
            "Recovery": score.get("recovery_score"),
            "HRV": score.get("hrv_rmssd_milli"),
            "Resting HR": score.get("resting_heart_rate"),
            "SPO2": score.get("spo2_percentage"),
            "Skin Temp": score.get("skin_temp_celsius"),
        })

    sleep_by_date = {}
    for record in sleep_records:
        if record.get("nap") is True:
            continue
        if record.get("score_state") != "SCORED":
            continue
        cycle_id = record.get("cycle_id")
        date = cycle_date_by_id.get(cycle_id)
        if not date:
            date = record.get("end", "")[:10]
        if not date:
            date = record.get("created_at", "")[:10]
        if not date:
            continue
        score = record.get("score") or {}
        stage = score.get("stage_summary") or {}
        sleep_needed = score.get("sleep_needed") or {}
        duration_milli = stage.get("total_in_bed_time_milli")
        sleep_need_baseline = sleep_needed.get("baseline_milli")
        candidate = {
            "duration": duration_milli or 0,
            "Sleep Performance": score.get("sleep_performance_percentage"),
            "Sleep Efficiency": score.get("sleep_efficiency_percentage"),
            "Sleep Need": round(sleep_need_baseline / 3600000, 4) if sleep_need_baseline is not None else None,
            "Sleep Duration": round(duration_milli / 3600000, 4) if duration_milli is not None else None,
            "Respiratory Rate": score.get("respiratory_rate"),
        }
        if date not in sleep_by_date or candidate["duration"] > sleep_by_date[date]["duration"]:
            sleep_by_date[date] = candidate

    for date, data in sleep_by_date.items():
        all_days.setdefault(date, {})
        all_days[date].update({k: v for k, v in data.items() if k != "duration"})

    processed = created = updated = failed = 0
    for date, metrics in sorted(all_days.items()):
        clean_date = date.strip()
        properties = {
            "Name": {"title": [{"text": {"content": clean_date}}]},
            "Date": {"date": {"start": clean_date}}
        }
        for key, value in metrics.items():
            if value is not None:
                properties[key] = {"number": round(value, 4) if isinstance(value, float) else value}
        try:
            if clean_date in existing_dates:
                notion_request("PATCH", f"https://api.notion.com/v1/pages/{existing_dates[clean_date]}", json_body={"properties": properties})
                updated += 1
                print(f"UPDATED: {clean_date}")
            else:
                response = notion_request("POST", "https://api.notion.com/v1/pages", json_body={"parent": {"database_id": DATABASE_ID}, "properties": properties})
                created_page = safe_json(response)
                existing_dates[clean_date] = created_page["id"]
                created += 1
                print(f"CREATED: {clean_date}")
            processed += 1
            time.sleep(0.35)
        except Exception as e:
            failed += 1
            print(f"FAILED: {clean_date} -> {e}")

    print(f"DAILY SYNC DONE | Processed: {processed} | Created: {created} | Updated: {updated} | Failed: {failed}")
    return existing_dates

def sync_workouts(daily_pages):
    print("=== WORKOUT SYNC ===")
    existing_workouts = {}
    has_more = True
    start_cursor = None
    while has_more:
        body = {"page_size": 100}
        if start_cursor:
            body["start_cursor"] = start_cursor
        result = safe_json(notion_request("POST", f"https://api.notion.com/v1/databases/{WORKOUT_DATABASE_ID}/query", json_body=body))
        for page in result.get("results", []):
            try:
                whoop_id_prop = page["properties"].get("WHOOP ID", {})
                rt = whoop_id_prop.get("rich_text", [])
                if rt:
                    whoop_id = rt[0]["text"]["content"].strip()
                    existing_workouts[whoop_id] = page["id"]
            except Exception:
                pass
        has_more = result.get("has_more", False)
        start_cursor = result.get("next_cursor")
        time.sleep(0.3)
    print(f"Existing workout pages found: {len(existing_workouts)}")

    print("Fetching WHOOP workouts...")
    workout_records = fetch_whoop_paginated("https://api.prod.whoop.com/developer/v2/activity/workout")
    print(f"Workouts fetched: {len(workout_records)}")

    processed = created = updated = failed = 0
    for record in workout_records:
        if record.get("score_state") != "SCORED":
            continue
        workout_id = record.get("id")
        if workout_id is None:
            continue
        start_raw = record.get("start", "")
        end_raw = record.get("end", "")
        date = start_raw[:10] if start_raw else ""
        if not date:
            continue
        score = record.get("score") or {}
        kilojoule = score.get("kilojoule")
        calories = round(kilojoule * 0.239006, 2) if kilojoule is not None else None

        duration_minutes = None
        if start_raw and end_raw:
            try:
                fmt = "%Y-%m-%dT%H:%M:%S.%fZ"
                t_start = datetime.strptime(start_raw, fmt).replace(tzinfo=timezone.utc)
                t_end = datetime.strptime(end_raw, fmt).replace(tzinfo=timezone.utc)
                duration_minutes = round((t_end - t_start).total_seconds() / 60, 2)
            except Exception:
                pass

        sport_id = record.get("sport_id")
        sport_name = get_sport_name(sport_id) if sport_id is not None else "Unknown"

        relation_value = []
        if date in daily_pages:
            relation_value = [{"id": daily_pages[date]}]

        properties = {
            "Name": {"title": [{"text": {"content": f"{date} – {sport_name}"}}]},
            "Date": {"date": {"start": date}},
            "Sport": {"select": {"name": sport_name}},
            "WHOOP ID": {"rich_text": [{"text": {"content": str(workout_id)}}]},
            "Day": {"relation": relation_value},
        }

        def add_number(prop_name, value):
            if value is not None:
                properties[prop_name] = {"number": value}

        add_number("Strain", score.get("strain"))
        add_number("Avg HR", score.get("average_heart_rate"))
        add_number("Max HR", score.get("max_heart_rate"))
        add_number("Calories", calories)
        add_number("Duration (min)", duration_minutes)

        try:
            workout_key = str(workout_id)
            if workout_key in existing_workouts:
                notion_request("PATCH", f"https://api.notion.com/v1/pages/{existing_workouts[workout_key]}", json_body={"properties": properties})
                updated += 1
                print(f"UPDATED: {date} | {sport_name}")
            else:
                response = notion_request("POST", "https://api.notion.com/v1/pages", json_body={"parent": {"database_id": WORKOUT_DATABASE_ID}, "properties": properties})
                created_page = safe_json(response)
                existing_workouts[workout_key] = created_page.get("id")
                created += 1
                print(f"CREATED: {date} | {sport_name}")
            processed += 1
            time.sleep(0.35)
        except Exception as e:
            failed += 1
            print(f"FAILED: {date} | {sport_name} -> {e}")

    print(f"WORKOUT SYNC DONE | Processed: {processed} | Created: {created} | Updated: {updated} | Failed: {failed}")

def update_github_secret(new_refresh_token):
    gh_pat = os.environ.get("GH_PAT")
    repo = os.environ.get("GITHUB_REPOSITORY")
    if not gh_pat or not repo:
        print("GH_PAT nincs beallitva, a refresh token NEM lett automatikusan frissitve a Secretben.")
        print("Ha ez a futas sikeres volt, de a token nem frissul, a KOVETKEZO futas hibat fog adni.")
        return
    os.environ["GH_TOKEN"] = gh_pat
    try:
        subprocess.run(
            ["gh", "secret", "set", "WHOOP_REFRESH_TOKEN", "--repo", repo, "--body", new_refresh_token],
            check=True
        )
        print("WHOOP_REFRESH_TOKEN secret frissitve GitHub-on.")
    except Exception as e:
        print(f"Nem sikerult a secret frissitese: {e}")

def main():
    start = datetime.now()
    print(f"Sync started: {start}")
    daily_pages = sync_daily()
    sync_workouts(daily_pages)
    update_github_secret(NEW_REFRESH_TOKEN)
    elapsed = round((datetime.now() - start).total_seconds())
    print(f"ALL DONE in {elapsed}s")

if __name__ == "__main__":
    main()
