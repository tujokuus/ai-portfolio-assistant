"""Source packaging tests use temporary files, without APIs or personal data."""

import json

import pytest

from backend.source_documents import load_source_documents
from backend.update_sources import update_sources


def setup_sources(tmp_path):
    original = tmp_path / "README.md"
    original.write_bytes(b"# Project\r\nOriginal details.\r\n")
    manifest = tmp_path / "local.json"
    manifest.write_text(json.dumps({"sources": [
        {"name": "project.md", "title": "Project", "path": str(original)},
    ]}), encoding="utf-8")
    return manifest, original, tmp_path / "bundle"


def test_round_trip_preserves_bytes_and_uses_relative_paths(tmp_path):
    manifest, original, bundle = setup_sources(tmp_path)
    update_sources(manifest, bundle)
    data = json.loads((bundle / "sources.json").read_text(encoding="utf-8"))
    assert data["sources"][0]["path"] == "project.md"
    assert load_source_documents(bundle / "sources.json")[0].original == original.read_bytes()
    before = (bundle / "project.md").stat().st_mtime_ns
    assert all(line.startswith("unchanged:") for line in update_sources(manifest, bundle))
    assert (bundle / "project.md").stat().st_mtime_ns == before
    original.write_bytes(b"Updated details")
    assert "updated: project.md" in update_sources(manifest, bundle)
    assert (bundle / "project.md").read_bytes() == b"Updated details"


def test_preview_does_not_create_output(tmp_path):
    manifest, _, bundle = setup_sources(tmp_path)
    assert "added: project.md" in update_sources(manifest, bundle, dry_run=True)
    assert not bundle.exists()


def test_missing_input_leaves_existing_bundle_unchanged(tmp_path):
    manifest, original, bundle = setup_sources(tmp_path)
    update_sources(manifest, bundle)
    before = {p.name: p.read_bytes() for p in bundle.iterdir()}
    original.write_bytes(b"New details")
    data = json.loads(manifest.read_text())
    data["sources"].append({"name": "missing.md", "title": "Missing", "path": "missing.md"})
    manifest.write_text(json.dumps(data), encoding="utf-8")
    with pytest.raises(ValueError):
        update_sources(manifest, bundle)
    assert before == {p.name: p.read_bytes() for p in bundle.iterdir()}


def test_unlisted_files_are_retained_but_not_loaded(tmp_path):
    manifest, _, bundle = setup_sources(tmp_path)
    update_sources(manifest, bundle)
    (bundle / "old.md").write_bytes(b"Old details")
    assert any("unlisted" in line for line in update_sources(manifest, bundle))
    assert (bundle / "old.md").exists()
    assert len(load_source_documents(bundle / "sources.json")) == 1


def test_original_cannot_be_overwritten(tmp_path):
    manifest, original, _ = setup_sources(tmp_path)
    data = json.loads(manifest.read_text())
    data["sources"][0]["name"] = original.name
    manifest.write_text(json.dumps(data), encoding="utf-8")
    with pytest.raises(ValueError, match="overwrite an original"):
        update_sources(manifest, tmp_path)


def test_case_collisions_rejected_before_writing(tmp_path):
    manifest, _, bundle = setup_sources(tmp_path)
    data = json.loads(manifest.read_text())
    data["sources"].append(dict(data["sources"][0], name="PROJECT.md"))
    manifest.write_text(json.dumps(data), encoding="utf-8")
    with pytest.raises(ValueError, match="ignoring case"):
        update_sources(manifest, bundle)
    assert not bundle.exists()
