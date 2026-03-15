#!/usr/bin/env python3
"""
Daily auto-update script for the Iran-Israel-US Conflict Tracker.
Uses OpenAI API with web search to research latest developments,
verify existing data accuracy, and update conflict-data.json.

Runs daily at 00:00 ET via GitHub Actions.
"""

import json
import os
import sys
import subprocess
from datetime import datetime, timezone, timedelta
from pathlib import Path
from copy import deepcopy

from openai import OpenAI

ROOT = Path(__file__).resolve().parent.parent
DATA_FILE = ROOT / "data" / "conflict-data.json"
CHANGELOG_FILE = ROOT / "data" / "changelog.json"

ET = timezone(timedelta(hours=-5))


def load_data():
    with open(DATA_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


def save_data(data):
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def load_changelog():
    if CHANGELOG_FILE.exists():
        with open(CHANGELOG_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return []


def save_changelog(log):
    with open(CHANGELOG_FILE, "w", encoding="utf-8") as f:
        json.dump(log, f, indent=2, ensure_ascii=False)


def get_current_date_str():
    now = datetime.now(ET)
    return now.strftime("%Y-%m-%d")


def research_and_update(data):
    """Use OpenAI to research latest developments and return updated data."""
    client = OpenAI()
    current_date = get_current_date_str()
    day_number = data["meta"]["day_number"]

    current_data_summary = json.dumps({
        "last_updated": data["meta"]["last_updated"],
        "day_number": day_number,
        "overview_killed": data["overview"]["total_killed"],
        "overview_wounded": data["overview"]["total_wounded"],
        "iran_munitions": data["overview"]["iran_missiles_drones"],
        "us_israel_strikes": data["overview"]["us_israel_strikes"],
        "us_deaths": data["us_casualties"]["kpis"]["total_deaths"],
        "phase3_iran_killed_hengaw": data["phase3"]["kpis"]["iran_killed_hengaw"],
        "phase3_israel_kw": data["phase3"]["kpis"]["israel_killed_wounded"],
        "phase3_iran_munitions": data["phase3"]["kpis"]["iran_munitions"],
        "oil_brent": data["costs"]["kpis"]["oil_brent"],
        "scenario_a_pct": data["scenarios"]["options"][0]["probability"],
        "scenario_b_pct": data["scenarios"]["options"][1]["probability"],
        "scenario_c_pct": data["scenarios"]["options"][2]["probability"],
        "latest_day_events": data["phase3"]["days"][-1]["events"] if data["phase3"]["days"] else "",
    }, indent=2)

    prompt = f"""You are a military intelligence analyst updating the Iran-Israel-US Conflict Tracker dashboard.

TODAY'S DATE: {current_date}
CURRENT DATA (last updated {data['meta']['last_updated']}, Day {day_number}):
{current_data_summary}

YOUR TASKS:
1. RESEARCH: Search for the latest developments in the Iran-Israel-US conflict since {data['meta']['last_updated']}.
2. VERIFY: Check if any previously reported figures (casualties, costs, strikes) have been corrected or updated by authoritative sources.
3. UPDATE: Provide corrected/new data.

IMPORTANT GUIDELINES:
- Use ONLY Tier 1-3 sources: official government/military (CENTCOM, IDF, Pentagon), established news (Reuters, AP, BBC, NPR, Bloomberg, WaPo, NYT), and verified OSINT (Hengaw, HRANA, ACLED, CSIS, FDD, IISS).
- When sources disagree, report the RANGE and note the disagreement.
- Maintain strict NEUTRALITY — do not take sides. Report facts from all parties equally. Use balanced language: describe military actions uniformly regardless of which side performs them. Avoid valorizing or demonizing any party.
- If the conflict has ended or there's a ceasefire, note that.
- If no significant changes since last update, say "NO_CHANGES".

Respond with a JSON object (and nothing else) with this exact structure:
{{
  "status": "UPDATED" or "NO_CHANGES",
  "changes_summary": "Brief description of what changed",
  "corrections": [
    {{"field": "json.path.to.field", "old_value": "...", "new_value": "...", "source": "...", "reason": "..."}}
  ],
  "new_day": {{
    "needed": true/false,
    "day": <number>,
    "date": "e.g. 16 Mar",
    "waves": "...",
    "iran_dead": "...",
    "isr_dead": "...",
    "us_dead": "...",
    "other": "...",
    "iran_bms": "...",
    "iran_drones": "...",
    "targets": "...",
    "events": "...",
    "highlight": false
  }},
  "meta_updates": {{
    "last_updated": "{current_date}",
    "update_time": "00:00 EST",
    "day_number": <new day number if applicable>
  }},
  "overview_updates": {{<any fields to update in overview, or empty>}},
  "phase3_kpi_updates": {{<any fields to update in phase3.kpis, or empty>}},
  "cost_updates": {{<any fields to update in costs.kpis, or empty>}},
  "scenario_updates": [
    {{"id": "A", "probability": <new %>, "description": "updated description if needed"}},
    {{"id": "B", "probability": <new %>, "description": "updated description if needed"}},
    {{"id": "C", "probability": <new %>, "description": "updated description if needed"}}
  ],
  "chart_data_updates": {{
    "brent_oil_append": [<new oil prices to append>],
    "hormuz_append": [<new hormuz % values>],
    "phase3_bm_append": [<new daily BM counts>],
    "phase3_drones_append": [<new daily drone counts>],
    "phase3_waves_append": [<new daily wave counts>],
    "phase3_hengaw_append": [<new cumulative hengaw totals>],
    "phase3_hrana_append": [<new cumulative HRANA totals>],
    "us_cost_append": [<new cumulative US cost points>]
  }},
  "new_us_casualties": [
    {{"name": "...", "rank": "...", "age": 0, "hometown": "...", "unit": "...", "date": "...", "location": "...", "cause": "..."}}
  ],
  "new_aircraft_losses": [],
  "indicator_updates": [
    {{"indicator": "...", "status": "...", "a": "...", "b": "...", "c": "..."}}
  ]
}}"""

    print(f"Researching latest developments as of {current_date}...")

    response = client.responses.create(
        model="gpt-4o",
        tools=[{"type": "web_search_preview"}],
        input=prompt,
        temperature=0.1,
    )

    raw_text = ""
    for item in response.output:
        if item.type == "message":
            for block in item.content:
                if block.type == "output_text":
                    raw_text = block.text

    # Extract JSON from response (handle markdown code blocks)
    json_text = raw_text.strip()
    if json_text.startswith("```"):
        lines = json_text.split("\n")
        json_text = "\n".join(lines[1:-1])

    return json.loads(json_text)


def apply_updates(data, updates):
    """Apply the OpenAI-provided updates to the data."""
    changes = []

    if updates.get("status") == "NO_CHANGES":
        print("No changes detected. Updating timestamp only.")
        data["meta"]["last_updated"] = updates.get("meta_updates", {}).get("last_updated", data["meta"]["last_updated"])
        data["meta"]["update_time"] = updates.get("meta_updates", {}).get("update_time", "00:00 EST")
        return ["Timestamp updated, no data changes"]

    # Apply meta updates
    if "meta_updates" in updates:
        for k, v in updates["meta_updates"].items():
            if v is not None:
                old = data["meta"].get(k)
                data["meta"][k] = v
                if old != v:
                    changes.append(f"meta.{k}: {old} -> {v}")

    # Apply corrections
    for correction in updates.get("corrections", []):
        field_path = correction["field"].split(".")
        obj = data
        for part in field_path[:-1]:
            if isinstance(obj, dict):
                obj = obj.get(part, {})
            elif isinstance(obj, list) and part.isdigit():
                obj = obj[int(part)]
        last_key = field_path[-1]
        if isinstance(obj, dict) and last_key in obj:
            old_val = obj[last_key]
            obj[last_key] = correction["new_value"]
            changes.append(f"CORRECTION {correction['field']}: {old_val} -> {correction['new_value']} (source: {correction.get('source', 'N/A')})")

    # Add new day if needed
    new_day = updates.get("new_day", {})
    if new_day.get("needed"):
        day_entry = {
            "day": new_day["day"],
            "date": new_day["date"],
            "waves": new_day.get("waves", "~8+"),
            "iran_dead": new_day.get("iran_dead", "TBD"),
            "isr_dead": new_day.get("isr_dead", "0"),
            "us_dead": new_day.get("us_dead", "0"),
            "other": new_day.get("other", "\u2014"),
            "iran_bms": new_day.get("iran_bms", "TBD"),
            "iran_drones": new_day.get("iran_drones", "TBD"),
            "targets": new_day.get("targets", "TBD"),
            "events": new_day.get("events", ""),
            "highlight": new_day.get("highlight", False),
        }
        data["phase3"]["days"].append(day_entry)
        changes.append(f"NEW DAY {new_day['day']}: {new_day.get('events', '')[:80]}...")

        # Update chart labels
        new_label = new_day["date"]
        for chart_key in ["phase3_daily_timeline", "phase3_cumulative_casualties", "bm_degradation", "us_cost_cumulative"]:
            if chart_key in data["charts"]:
                data["charts"][chart_key]["labels"].append(new_label)

    # Apply overview updates
    for k, v in updates.get("overview_updates", {}).items():
        if v is not None and k in data["overview"]:
            old = data["overview"][k]
            data["overview"][k] = v
            if old != v:
                changes.append(f"overview.{k}: {old} -> {v}")

    # Apply phase3 KPI updates
    for k, v in updates.get("phase3_kpi_updates", {}).items():
        if v is not None and k in data["phase3"]["kpis"]:
            old = data["phase3"]["kpis"][k]
            data["phase3"]["kpis"][k] = v
            if old != v:
                changes.append(f"phase3.kpis.{k}: {old} -> {v}")

    # Apply cost updates
    for k, v in updates.get("cost_updates", {}).items():
        if v is not None and k in data["costs"]["kpis"]:
            old = data["costs"]["kpis"][k]
            data["costs"]["kpis"][k] = v
            if old != v:
                changes.append(f"costs.kpis.{k}: {old} -> {v}")

    # Apply scenario updates
    for su in updates.get("scenario_updates", []):
        for opt in data["scenarios"]["options"]:
            if opt["id"] == su.get("id"):
                if "probability" in su and su["probability"] is not None:
                    old = opt["probability"]
                    opt["probability"] = su["probability"]
                    if old != su["probability"]:
                        changes.append(f"scenario {su['id']} prob: {old}% -> {su['probability']}%")
                        # Update chart data too
                        idx = {"A": 0, "B": 1, "C": 2}.get(su["id"])
                        if idx is not None:
                            data["charts"]["scenario_probabilities"]["data"][idx] = su["probability"]
                if "description" in su and su["description"]:
                    opt["description"] = su["description"]

    # Append chart data
    chart_updates = updates.get("chart_data_updates", {})

    append_mappings = {
        "brent_oil_append": ("brent_oil", "data"),
        "hormuz_append": ("hormuz_transit", "data"),
        "phase3_bm_append": ("bm_degradation", "daily_bm"),
        "phase3_drones_append": ("phase3_daily_timeline", "iran_drones"),
        "phase3_waves_append": ("phase3_daily_timeline", "us_israel_waves"),
        "phase3_hengaw_append": ("phase3_cumulative_casualties", "hengaw_total"),
        "phase3_hrana_append": ("phase3_cumulative_casualties", "hrana_civilian"),
        "us_cost_append": ("us_cost_cumulative", "data"),
    }

    for update_key, (chart_name, data_key) in append_mappings.items():
        new_values = chart_updates.get(update_key, [])
        if new_values and chart_name in data["charts"]:
            data["charts"][chart_name][data_key].extend(new_values)
            changes.append(f"chart {chart_name}.{data_key}: appended {len(new_values)} values")

    # Also append BM data to phase3_daily_timeline
    bm_append = chart_updates.get("phase3_bm_append", [])
    if bm_append:
        data["charts"]["phase3_daily_timeline"]["iran_bms"].extend(bm_append)

    # Add new US casualties
    for cas in updates.get("new_us_casualties", []):
        if cas.get("name"):
            num = len(data["us_casualties"]["service_members"]) + 1
            cas["num"] = num
            data["us_casualties"]["service_members"].append(cas)
            changes.append(f"NEW US CASUALTY: {cas['name']}")

    # Add new aircraft losses
    for al in updates.get("new_aircraft_losses", []):
        if al.get("aircraft"):
            data["us_casualties"]["aircraft_losses"].append(al)
            changes.append(f"NEW AIRCRAFT LOSS: {al['aircraft']}")

    # Update indicators
    for iu in updates.get("indicator_updates", []):
        for ind in data["scenarios"]["indicators"]:
            if ind["indicator"] == iu.get("indicator"):
                for key in ["status", "a", "b", "c"]:
                    if key in iu and iu[key]:
                        ind[key] = iu[key]
                changes.append(f"indicator '{iu['indicator']}' updated")

    return changes


def run_build():
    """Run the build script to regenerate HTML."""
    build_script = ROOT / "scripts" / "build.py"
    subprocess.run([sys.executable, str(build_script)], check=True, cwd=str(ROOT))


def main():
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        print("ERROR: OPENAI_API_KEY not set")
        sys.exit(1)

    print(f"=== Conflict Tracker Daily Update ===")
    print(f"Date: {get_current_date_str()}")

    # Load current data
    data = load_data()
    original = deepcopy(data)
    print(f"Current data: Day {data['meta']['day_number']}, updated {data['meta']['last_updated']}")

    # Research and get updates
    try:
        updates = research_and_update(data)
    except Exception as e:
        print(f"ERROR during research: {e}")
        # On error, just update timestamp
        data["meta"]["last_updated"] = get_current_date_str()
        data["meta"]["update_time"] = "00:00 EST"
        save_data(data)
        run_build()
        print("Updated timestamp only due to research error.")
        return

    # Apply updates
    changes = apply_updates(data, updates)

    # Save updated data
    save_data(data)
    print(f"\nApplied {len(changes)} changes:")
    for c in changes:
        print(f"  - {c}")

    # Log to changelog
    changelog = load_changelog()
    changelog.append({
        "date": get_current_date_str(),
        "timestamp": datetime.now(ET).isoformat(),
        "status": updates.get("status", "UPDATED"),
        "summary": updates.get("changes_summary", ""),
        "changes": changes,
    })
    save_changelog(changelog)

    # Rebuild HTML
    run_build()
    print("\nHTML files regenerated.")
    print("Update complete.")


if __name__ == "__main__":
    main()
