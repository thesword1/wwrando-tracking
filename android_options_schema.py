#!/usr/bin/env python3
"""Generate the Android settings-screen options schema.

Usage: python android_options_schema.py [--check]

Writes ``android/app/src/main/assets/options_schema.json`` (committed). ``--check`` exits 1 when the
committed file is missing or stale (byte comparison), so CI/tests can fail on an unregenerated file.
Only the repo's normal deps (stdlib) are used so it runs on Python 3.12 and 3.14 alike.
"""

import argparse
import html
import inspect
import json
import re
import sys
import typing
from enum import StrEnum
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent
OUTPUT_PATH = REPO_ROOT / "android" / "app" / "src" / "main" / "assets" / "options_schema.json"

_BR_TAG = re.compile(r"<br\s*/?>", re.IGNORECASE)
_HTML_TAG = re.compile(r"<[^>]+>")
_FIELD_LINE = re.compile(r"^\s*([A-Za-z_][A-Za-z0-9_]*)\s*:")
_REGION = re.compile(r"#region\s+(.+?)\s*$")


def clean_html(text: str) -> str:
    """Strip HTML tags, turning <br> into newlines and unescaping entities."""
    text = _BR_TAG.sub("\n", text)
    text = _HTML_TAG.sub("", text)
    return html.unescape(text).strip()


def _is_enum_type(tp) -> bool:
    return inspect.isclass(tp) and issubclass(tp, StrEnum)


def _type_name_and_payload(tp, field):
    """Return (type_name, choices, choice_descriptions, minimum, maximum) for an option field."""
    origin = typing.get_origin(tp)
    args = typing.get_args(tp)
    if tp is bool:
        return "bool", None, None, None, None
    if _is_enum_type(tp):
        choices = [member.value for member in tp]
        raw = field.choice_descriptions or {}
        choice_descriptions = [
            clean_html(raw.get(tp(value), "")) for value in choices
        ]
        return "enum", choices, choice_descriptions, None, None
    if tp is int:
        return "int", None, None, field.minimum, field.maximum
    if origin is list and args == (str,) and field.choices is not None:
        return "multi", list(field.choices), None, None, None
    return None, None, None, None, None


def _itemlist_payload():
    """Allowed items and per-item max counts for starting_gear (mirrors wwr_ui.inventory)."""
    from wwr_ui.inventory import INVENTORY_ITEMS

    choices = sorted(set(INVENTORY_ITEMS))
    max_counts = {item: INVENTORY_ITEMS.count(item) for item in choices}
    return choices, max_counts


def _field_source_lines():
    from options.wwrando_options import Options

    lines, start = inspect.getsourcelines(Options)
    return lines, start


def _field_line_index(lines, name):
    for i, line in enumerate(lines):
        match = _FIELD_LINE.match(line)
        if match and match.group(1) == name:
            return i
    raise RuntimeError("option field %r not found in Options source" % name)


def _group_for_field(lines, field_index):
    for j in range(field_index - 1, -1, -1):
        match = _REGION.search(lines[j])
        if match:
            return match.group(1).strip()
    raise RuntimeError("option field at source index %d has no #region" % field_index)


def build_schema():
    from options.wwrando_options import Options

    lines, _start = _field_source_lines()
    defaults = Options()
    by_name = Options.by_name()

    options = []
    skipped = []
    for field in Options.all():
        name = field.name
        if field.hidden and name != "randomize_enemies":
            skipped.append(name)
            continue
        if name == "starting_gear":
            choices, max_counts = _itemlist_payload()
            entry = {
                "name": name,
                "group": _group_for_field(lines, _field_line_index(lines, name)),
                "type": "itemlist",
                "default": defaults[name],
                "description": clean_html(field.description or ""),
                "choices": choices,
                "max_counts": max_counts,
                "permalink": bool(field.permalink),
            }
            options.append(entry)
            continue
        type_name, choices, choice_descriptions, minimum, maximum = _type_name_and_payload(field.type, field)
        if type_name is None:
            skipped.append(name)
            continue
        entry = {
            "name": name,
            "group": _group_for_field(lines, _field_line_index(lines, name)),
            "type": type_name,
            "default": defaults[name],
            "description": clean_html(field.description or ""),
        }
        if choices is not None:
            entry["choices"] = choices
        if choice_descriptions is not None:
            entry["choice_descriptions"] = choice_descriptions
        if minimum is not None:
            entry["minimum"] = minimum
        if maximum is not None:
            entry["maximum"] = maximum
        entry["permalink"] = bool(field.permalink)
        options.append(entry)

    return {"options": options, "skipped": skipped}


def render_schema() -> str:
    return json.dumps(build_schema(), indent=1, ensure_ascii=False) + "\n"


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--check",
        action="store_true",
        help="Exit 1 if the committed options_schema.json is missing or stale.",
    )
    args = parser.parse_args(argv)

    rendered = render_schema()
    if args.check:
        if not OUTPUT_PATH.exists():
            print("options_schema.json is missing", file=sys.stderr)
            return 1
        if OUTPUT_PATH.read_text(encoding="utf-8") != rendered:
            print("options_schema.json is stale; run: python android_options_schema.py", file=sys.stderr)
            return 1
        return 0

    OUTPUT_PATH.write_text(rendered, encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main())
