"""Tests for the Android options-schema generator (android_options_schema.py)."""

import inspect
import json
import re
import subprocess
import sys
import typing
from enum import StrEnum
from pathlib import Path

import android_options_schema
from options.wwrando_options import Options

REPO_ROOT = Path(__file__).resolve().parents[1]
SCHEMA_PATH = REPO_ROOT / "android" / "app" / "src" / "main" / "assets" / "options_schema.json"


def _expected_type(field):
    if field.name == "starting_gear":
        return "itemlist"
    tp = field.type
    origin = typing.get_origin(tp)
    args = typing.get_args(tp)
    if tp is bool:
        return "bool"
    if inspect.isclass(tp) and issubclass(tp, StrEnum):
        return "enum"
    if tp is int:
        return "int"
    if origin is list and args == (str,) and field.choices is not None:
        return "multi"
    return None


def _expected_group(name):
    lines, _ = inspect.getsourcelines(Options)
    index = next(i for i, line in enumerate(lines) if re.match(rf"^\s*{name}\s*:", line))
    for j in range(index - 1, -1, -1):
        match = re.search(r"#region\s+(.+?)\s*$", lines[j])
        if match:
            return match.group(1).strip()
    raise AssertionError("no region for %s" % name)


def test_check_passes_on_the_committed_file():
    proc = subprocess.run(
        [sys.executable, str(REPO_ROOT / "android_options_schema.py"), "--check"],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        timeout=120,
    )
    assert proc.returncode == 0, proc.stderr


def test_schema_covers_every_non_skipped_field_with_the_right_type_and_group():
    schema = android_options_schema.build_schema()
    by_name = {entry["name"]: entry for entry in schema["options"]}

    for field in Options.all():
        expected = _expected_type(field)
        if field.name == "randomize_enemies":
            # hidden+unbeatable on desktop, but surfaced on the Android Logic screen with a warning.
            assert field.name in by_name, field.name
            assert by_name[field.name]["type"] == "bool", field.name
            continue
        if field.hidden or expected is None:
            assert field.name in schema["skipped"], field.name
            assert field.name not in by_name, field.name
            continue
        assert field.name in by_name, field.name
        entry = by_name[field.name]
        assert entry["type"] == expected, field.name
        assert entry["group"] == _expected_group(field.name), field.name
        if entry["type"] == "itemlist":
            assert entry["choices"], field.name
            assert entry["max_counts"], field.name
            assert all(isinstance(n, int) for n in entry["max_counts"].values()), field.name
            assert set(entry["max_counts"]) == set(entry["choices"]), field.name

    assert schema["skipped"] == [
        "randomized_gear",
        "custom_player_model", "custom_color_preset", "custom_colors",
    ]


def test_committed_file_is_byte_identical_to_the_generator_output():
    assert SCHEMA_PATH.read_text(encoding="utf-8") == android_options_schema.render_schema()


def test_enum_entries_have_parallel_choices_and_descriptions():
    schema = android_options_schema.build_schema()
    for entry in schema["options"]:
        if entry["type"] == "enum":
            assert entry["choices"], entry["name"]
            assert len(entry["choice_descriptions"]) == len(entry["choices"]), entry["name"]
            assert all(isinstance(choice, str) for choice in entry["choices"])
