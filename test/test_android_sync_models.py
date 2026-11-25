"""Tests for android_run.py --sync-models (the model manifest installer run.sh drives)."""

import json
import os
import zipfile
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]

import sys
sys.path.insert(0, str(REPO_ROOT))

import android_run


def _make_zip(path: Path, entries: dict[str, str]) -> Path:
    with zipfile.ZipFile(path, "w") as zf:
        for name, data in entries.items():
            zf.writestr(name, data)
    return path


def _manifest(path: Path, entries) -> None:
    path.write_text(json.dumps(entries), encoding="utf-8")


def _md5_file(models_dir: Path, name: str) -> Path:
    return models_dir / name / ".md5"


def test_install_writes_model_and_md5(tmp_path):
    models = tmp_path / "models"
    models.mkdir()
    zf = _make_zip(
        tmp_path / "m.zip",
        {"Link.arc": "ARC", "metadata.txt": "hero_custom_colors: {}\n", "preview/preview_hero.png": "PNG"},
    )
    manifest = tmp_path / "manifest.json"
    _manifest(manifest, [{"name": "Foo", "md5": "abc", "path": str(zf)}])

    assert android_run.sync_models(str(models), str(manifest)) == 1
    assert (models / "Foo" / "Link.arc").read_text(encoding="utf-8") == "ARC"
    assert (models / "Foo" / "preview" / "preview_hero.png").read_text(encoding="utf-8") == "PNG"
    assert _md5_file(models, "Foo").read_text(encoding="utf-8") == "abc"


def test_unchanged_md5_is_skipped(tmp_path):
    models = tmp_path / "models"
    (models / "Foo").mkdir(parents=True)
    _md5_file(models, "Foo").write_text("abc", encoding="utf-8")
    (models / "Foo" / "Link.arc").write_text("OLD", encoding="utf-8")

    manifest = tmp_path / "manifest.json"
    # No zip path needed for an unchanged model.
    _manifest(manifest, [{"name": "Foo", "md5": "abc", "path": ""}])

    assert android_run.sync_models(str(models), str(manifest)) == 1
    assert (models / "Foo" / "Link.arc").read_text(encoding="utf-8") == "OLD"


def test_replace_extracts_over_old_model(tmp_path):
    models = tmp_path / "models"
    (models / "Foo").mkdir(parents=True)
    (models / "Foo" / "Link.arc").write_text("OLD", encoding="utf-8")
    (models / "Foo" / "stale.txt").write_text("x", encoding="utf-8")

    zf = _make_zip(tmp_path / "m.zip", {"Link.arc": "NEW", "metadata.txt": ""})
    manifest = tmp_path / "manifest.json"
    _manifest(manifest, [{"name": "Foo", "md5": "new", "path": str(zf)}])

    assert android_run.sync_models(str(models), str(manifest)) == 1
    assert (models / "Foo" / "Link.arc").read_text(encoding="utf-8") == "NEW"
    assert not (models / "Foo" / "stale.txt").exists()
    assert _md5_file(models, "Foo").read_text(encoding="utf-8") == "new"


def test_prune_deletes_models_absent_from_manifest(tmp_path):
    models = tmp_path / "models"
    (models / "Old").mkdir(parents=True)
    (models / "Old" / "Link.arc").write_text("OLD", encoding="utf-8")

    manifest = tmp_path / "manifest.json"
    _manifest(manifest, [])

    assert android_run.sync_models(str(models), str(manifest)) == 0
    assert not (models / "Old").exists()


def test_zip_slip_rejected(tmp_path):
    models = tmp_path / "models"
    models.mkdir()
    zf = _make_zip(tmp_path / "m.zip", {"../evil.txt": "x", "Link.arc": "ARC"})
    manifest = tmp_path / "manifest.json"
    _manifest(manifest, [{"name": "Foo", "md5": "abc", "path": str(zf)}])

    with pytest.raises(ValueError, match="path escape"):
        android_run.sync_models(str(models), str(manifest))
    assert not (models / "Foo").exists()
    assert not (tmp_path / "evil.txt").exists()


def test_absolute_path_rejected(tmp_path):
    models = tmp_path / "models"
    models.mkdir()
    zf = _make_zip(tmp_path / "m.zip", {"/etc/pwned": "x"})
    manifest = tmp_path / "manifest.json"
    _manifest(manifest, [{"name": "Foo", "md5": "abc", "path": str(zf)}])

    with pytest.raises(ValueError, match="absolute path"):
        android_run.sync_models(str(models), str(manifest))


def test_reserved_model_name_rejected(tmp_path):
    models = tmp_path / "models"
    models.mkdir()
    manifest = tmp_path / "manifest.json"
    _manifest(manifest, [{"name": "Link", "md5": "abc", "path": ""}])

    with pytest.raises(ValueError, match="invalid model name"):
        android_run.sync_models(str(models), str(manifest))
