from __future__ import annotations

import importlib.util
import json
from pathlib import Path
from types import ModuleType

import pytest


def load_builder() -> ModuleType:
    script = Path(__file__).resolve().parents[1] / "scripts" / "build-secute-anon-artifact.py"
    spec = importlib.util.spec_from_file_location("build_secute_anon_artifact", script)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_anonymous_artifact_copy_tree_rejects_symlink_escape(tmp_path: Path) -> None:
    builder = load_builder()
    outside = tmp_path / "outside-secret.txt"
    outside.write_text("secret", encoding="utf-8")
    source = tmp_path / "source"
    source.mkdir()
    link = source / "leak.txt"
    try:
        link.symlink_to(outside)
    except OSError as exc:
        pytest.skip(f"symlink unavailable: {exc}")

    with pytest.raises(ValueError, match="refusing to copy symlink"):
        builder.copy_tree(source, tmp_path / "dest")

    assert not (tmp_path / "dest" / "leak.txt").exists()


def test_anonymous_artifact_manifest_lists_itself_consistently(tmp_path: Path) -> None:
    builder = load_builder()
    stage = tmp_path / "stage"
    stage.mkdir()
    (stage / "README.md").write_text("hello\n", encoding="utf-8")

    manifest = builder.write_manifest(stage)
    manifest_path = stage / "artifact-manifest.json"
    written = json.loads(manifest_path.read_text(encoding="utf-8"))

    assert written == manifest
    assert len(written) == 2
    self_entries = [entry for entry in written if entry["path"] == "artifact-manifest.json"]
    assert len(self_entries) == 1
    assert self_entries[0]["bytes"] == manifest_path.stat().st_size
    assert self_entries[0]["sha256"] == builder.SELF_REFERENTIAL_SHA256


def test_anonymous_artifact_copy_tree_skips_secret_filenames(tmp_path: Path) -> None:
    builder = load_builder()
    source = tmp_path / "source"
    source.mkdir()
    (source / "README.md").write_text("ok\n", encoding="utf-8")
    (source / ".env").write_text("TOKEN=secret\n", encoding="utf-8")
    (source / "private.pem").write_text("secret\n", encoding="utf-8")

    dest = tmp_path / "dest"
    builder.copy_tree(source, dest)

    assert (dest / "README.md").is_file()
    assert not (dest / ".env").exists()
    assert not (dest / "private.pem").exists()
