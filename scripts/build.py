#!/usr/bin/env python3
"""Build script: renders HTML dashboards from data/conflict-data.json + templates."""

import json
import os
from datetime import datetime, timedelta
from pathlib import Path

from jinja2 import Environment, FileSystemLoader

ROOT = Path(__file__).resolve().parent.parent
DATA_FILE = ROOT / "data" / "conflict-data.json"
TEMPLATE_DIR = ROOT / "templates"
OUTPUT_DIR = ROOT


def load_data():
    with open(DATA_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


def compute_derived(data):
    """Add computed fields to data."""
    meta = data["meta"]
    start = datetime.strptime(meta["conflict_start"], "%Y-%m-%d")
    updated = datetime.strptime(meta["last_updated"], "%Y-%m-%d")
    meta["day_number"] = (updated - start).days + 1
    meta["formatted_date"] = updated.strftime("%-d %B %Y")
    return data


def build():
    data = load_data()
    data = compute_derived(data)

    env = Environment(
        loader=FileSystemLoader(str(TEMPLATE_DIR)),
        autoescape=False,
        keep_trailing_newline=True,
    )

    for template_name, output_name in [("en.html", "index.html"), ("fa.html", "fa.html")]:
        template = env.get_template(template_name)
        rendered = template.render(d=data, meta=data["meta"])
        output_path = OUTPUT_DIR / output_name
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(rendered)
        print(f"Built {output_path}")


if __name__ == "__main__":
    build()
