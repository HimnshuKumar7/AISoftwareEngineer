"""Walk a cloned repository and yield source files worth indexing."""
from __future__ import annotations

import logging
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, Iterator, List, Tuple

from app.ingestion.languages import is_doc_path, is_notebook_path, spec_for_path

log = logging.getLogger(__name__)

SKIP_DIRS = {
    ".git", ".hg", ".svn", "node_modules", "vendor", "third_party", "thirdparty", "dist", "build", "out",
    "target", "__pycache__", ".venv", "venv", "env", ".tox", ".mypy_cache", ".pytest_cache", ".next", ".nuxt",
    "coverage", "bin", "obj", ".gradle", ".idea", ".vscode", "bower_components", "Pods", ".dart_tool",
    "site-packages", "__snapshots__", "migrations_old", ".ipynb_checkpoints",
}
SKIP_SUFFIXES = (".min.js", ".min.css", ".bundle.js", ".map", ".lock", ".pb.go", "_pb2.py", "_pb2_grpc.py", ".d.ts")
NOTEBOOK_SIZE_FACTOR = 8
SKIP_NAMES = {"package-lock.json", "yarn.lock", "pnpm-lock.yaml", "poetry.lock", "Cargo.lock", "go.sum"}


@dataclass
class WalkStats:
    files_seen: int = 0
    files_indexed: int = 0
    skipped_large: int = 0
    skipped_binary: int = 0
    truncated: bool = False
    languages: Dict[str, int] = field(default_factory=dict)


def _wanted(rel: str) -> bool:
    name = rel.rsplit("/", 1)[-1]
    if name in SKIP_NAMES or rel.endswith(SKIP_SUFFIXES):
        return False
    return spec_for_path(rel) is not None or is_doc_path(rel) or is_notebook_path(rel)


def walk_repo(root: Path, max_files: int, max_file_kb: int, stats: WalkStats) -> Iterator[Tuple[str, bytes]]:
    """Yield (posix-relative-path, bytes). Symlinks are never followed."""
    root = root.resolve()
    max_bytes = max_file_kb * 1024
    # Code first, docs last, so that file caps never crowd out source files with prose.
    code: List[str] = []
    docs: List[str] = []
    for dirpath, dirnames, filenames in os.walk(root, followlinks=False):
        dirnames[:] = sorted(d for d in dirnames if d not in SKIP_DIRS and not d.startswith(".git"))
        for fn in sorted(filenames):
            full = os.path.join(dirpath, fn)
            rel = os.path.relpath(full, root).replace(os.sep, "/")
            stats.files_seen += 1
            if os.path.islink(full) or not _wanted(rel):
                continue
            (docs if is_doc_path(rel) else code).append(rel)

    for rel in code + docs:
        if stats.files_indexed >= max_files:
            stats.truncated = True
            break
        full = root / rel
        try:
            real = full.resolve()
            if root not in real.parents:  # defensive: never read outside the clone
                continue
            size = real.stat().st_size
            if size == 0:
                continue
            # Notebooks embed outputs (plots as base64), so they are legitimately much larger than source files.
            if size > (max_bytes * NOTEBOOK_SIZE_FACTOR if is_notebook_path(rel) else max_bytes):
                stats.skipped_large += 1
                continue
            data = real.read_bytes()
        except OSError:
            continue
        if b"\x00" in data[:4096]:
            stats.skipped_binary += 1
            continue
        stats.files_indexed += 1
        spec = spec_for_path(rel)
        lang = spec.name if spec else ("jupyter" if is_notebook_path(rel) else "markdown")
        stats.languages[lang] = stats.languages.get(lang, 0) + 1
        yield rel, data
