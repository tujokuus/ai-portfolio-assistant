"""Refresh the deployment source snapshot without network or model calls."""

import argparse
import json
import os
from pathlib import Path
import tempfile

from backend.source_documents import load_source_documents


def _replace_file(path: Path, content: bytes) -> None:
    """Replace one file atomically, keeping temporary files on the same volume."""
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(dir=path.parent, delete=False) as stream:
            temporary = Path(stream.name)
            stream.write(content)
        os.replace(temporary, path)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


def update_sources(
    manifest: Path, output_dir: Path, *, dry_run: bool = False,
) -> list[str]:
    """Validate all inputs before writing; retain unlisted files for manual review."""
    manifest = Path(manifest).resolve()
    output_dir = Path(output_dir).resolve()
    sources = load_source_documents(manifest)
    entries = json.loads(manifest.read_text(encoding="utf-8-sig"))["sources"]
    originals = {(manifest.parent / entry["path"]).resolve() for entry in entries}
    originals.add(manifest)
    names = [source.document.source for source in sources]
    if len({name.casefold() for name in names}) != len(names):
        raise ValueError("Source filenames must also be unique ignoring case.")
    # Windows treats device names as special even when they have an extension.
    reserved = {"con", "prn", "aux", "nul"} | {
        f"{prefix}{number}" for prefix in ("com", "lpt") for number in range(1, 10)
    }
    if any(name.split(".")[0].casefold() in reserved for name in names):
        raise ValueError("Source filenames cannot use Windows device names.")
    public_manifest = {"sources": [
        {"name": source.document.source, "title": source.document.title,
         "path": source.document.source}
        for source in sources
    ]}
    files = [(source.document.source, source.original) for source in sources]
    files.append(("sources.json", (json.dumps(
        public_manifest, ensure_ascii=False, indent=2,
    ) + "\n").encode("utf-8")))
    changes = []
    messages = []
    # Prepare every write before changing anything, including checking destinations.
    for name, content in files:
        target = output_dir / name
        if target.is_symlink() or target.resolve() in originals:
            raise ValueError(f"Output would overwrite an original or symlink: {name}")
        if target.exists() and not target.is_file():
            raise ValueError(f"Output is not a regular file: {name}")
        old = target.read_bytes() if target.exists() else None
        status = "unchanged" if old == content else "added" if old is None else "updated"
        messages.append(f"{status}: {name}")
        if old != content:
            changes.append((target, content))
    if output_dir.exists():
        expected = {name.casefold() for name, _ in files}
        for path in sorted(output_dir.iterdir()):
            if path.name.casefold() not in expected:
                messages.append(f"unlisted (retained; review manually): {path.name}")
    if not dry_run:
        output_dir.mkdir(parents=True, exist_ok=True)
        # The manifest is written last. Each file replacement is atomic, but the
        # whole bundle is not a transaction; rerun after an interrupted update.
        for target, content in changes:
            _replace_file(target, content)
    return messages


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--sources", type=Path, default=Path("sources.local.json"))
    parser.add_argument("--output-dir", type=Path, default=Path("deployment_bundle"))
    parser.add_argument("--dry-run", action="store_true", help="Validate and preview without writing.")
    args = parser.parse_args()
    try:
        messages = update_sources(args.sources, args.output_dir, dry_run=args.dry_run)
    except (ValueError, OSError) as exc:
        parser.exit(1, f"Source update failed: {exc}\n")
    print("Preview only; no files changed." if args.dry_run else "Source bundle updated.")
    print("\n".join(messages))
    print("No Git operations or API calls were made.")


if __name__ == "__main__":
    main()
