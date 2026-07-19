"""Clone a GitHub repository to local disk and return a stable repo_id."""
import hashlib
import shutil
from pathlib import Path

import git

from app.config import settings

# File extensions we bother to parse / index
SUPPORTED_EXTENSIONS = {
    ".py", ".js", ".jsx", ".ts", ".tsx", ".java", ".go", ".rb", ".rs",
    ".c", ".h", ".cpp", ".hpp", ".cs", ".php", ".md", ".json", ".yaml",
    ".yml", ".txt",
}

IGNORED_DIRS = {
    ".git", "node_modules", "venv", ".venv", "__pycache__", "dist",
    "build", ".next", "target", "vendor", ".idea", ".vscode", "coverage",
}


def repo_id_from_url(repo_url: str) -> str:
    """Deterministic short id for a repo URL, used as folder name / index key."""
    return hashlib.sha1(repo_url.encode("utf-8")).hexdigest()[:16]


def clone_repo(repo_url: str, branch: str | None = None) -> tuple[str, Path]:
    """Clone (or reuse an existing clone of) a repo. Returns (repo_id, local_path)."""
    repo_id = repo_id_from_url(repo_url + (branch or ""))
    dest = Path(settings.DATA_DIR) / "repos" / repo_id

    if dest.exists():
        shutil.rmtree(dest)  # always re-clone fresh to keep index consistent
    dest.mkdir(parents=True, exist_ok=True)

    clone_kwargs = {"depth": 1}
    if branch:
        clone_kwargs["branch"] = branch

    git.Repo.clone_from(repo_url, dest, **clone_kwargs)
    return repo_id, dest


def iter_source_files(repo_path: Path):
    """Yield Path objects for every file worth indexing."""
    for path in repo_path.rglob("*"):
        if not path.is_file():
            continue
        if any(part in IGNORED_DIRS for part in path.parts):
            continue
        if path.suffix.lower() not in SUPPORTED_EXTENSIONS:
            continue
        try:
            if path.stat().st_size > 500_000:  # skip huge generated files
                continue
        except OSError:
            continue
        yield path
