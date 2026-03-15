#!/usr/bin/env python3
"""Build script: renders HTML dashboards from data/conflict-data.json + templates."""

import json
import os
from copy import deepcopy
from datetime import datetime, timedelta
from pathlib import Path

from jinja2 import Environment, FileSystemLoader

ROOT = Path(__file__).resolve().parent.parent
DATA_FILE = ROOT / "data" / "conflict-data.json"
TEMPLATE_DIR = ROOT / "templates"
OUTPUT_DIR = ROOT

PERSIAN_DIGITS = '۰۱۲۳۴۵۶۷۸۹'
MONTH_EN_TO_FA = {
    'January': 'ژانویه', 'February': 'فوریه', 'March': 'مارس',
    'April': 'آوریل', 'May': 'مه', 'June': 'ژوئن',
    'July': 'ژوئیه', 'August': 'اوت', 'September': 'سپتامبر',
    'October': 'اکتبر', 'November': 'نوامبر', 'December': 'دسامبر',
    'Jan': 'ژانویه', 'Feb': 'فوریه', 'Mar': 'مارس',
    'Apr': 'آوریل', 'May': 'مه', 'Jun': 'ژوئن',
    'Jul': 'ژوئیه', 'Aug': 'اوت', 'Sep': 'سپتامبر',
    'Oct': 'اکتبر', 'Nov': 'نوامبر', 'Dec': 'دسامبر',
}


def fa_num(value):
    """Convert Western digits (0-9) to Persian digits (۰-۹)."""
    if value is None:
        return ''
    s = str(value)
    for i, d in enumerate('0123456789'):
        s = s.replace(d, PERSIAN_DIGITS[i])
    return s


def fa_text(value):
    """Convert digits to Persian and translate month names."""
    if value is None:
        return ''
    s = str(value)
    for en, fa in MONTH_EN_TO_FA.items():
        s = s.replace(en, fa)
    for i, d in enumerate('0123456789'):
        s = s.replace(d, PERSIAN_DIGITS[i])
    return s


def _fa_convert_labels(obj):
    """Recursively convert chart label strings to Farsi numbers/months.
    If a labels_fa key exists, use it instead of auto-converting."""
    if isinstance(obj, dict):
        result = {}
        for k, v in obj.items():
            if k == 'labels' and isinstance(v, list):
                # Use labels_fa if provided, otherwise auto-convert
                if 'labels_fa' in obj:
                    result[k] = obj['labels_fa']
                else:
                    result[k] = [fa_text(x) for x in v]
            elif k == 'labels_fa':
                continue  # skip, already handled
            elif k == 'title' and isinstance(v, str) and 'title_fa' in obj:
                result[k] = obj['title_fa']
            elif k == 'title_fa':
                continue
            else:
                result[k] = _fa_convert_labels(v)
        return result
    elif isinstance(obj, list):
        return [_fa_convert_labels(x) for x in obj]
    return obj


def prepare_fa_data(data):
    """Prepare a copy of data with Farsi chart labels."""
    fa_data = deepcopy(data)
    if 'charts' in fa_data:
        fa_data['charts'] = _fa_convert_labels(fa_data['charts'])
    return fa_data


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
    env.filters['fa'] = fa_num
    env.filters['fa_text'] = fa_text

    for template_name, output_name in [("en.html", "index.html"), ("fa.html", "fa.html")]:
        template = env.get_template(template_name)
        render_data = prepare_fa_data(data) if template_name == "fa.html" else data
        rendered = template.render(d=render_data, meta=render_data["meta"])
        output_path = OUTPUT_DIR / output_name
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(rendered)
        print(f"Built {output_path}")


if __name__ == "__main__":
    build()
