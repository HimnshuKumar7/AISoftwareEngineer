"""Validated, sandboxed cloning of public GitHub repositories."""
from __future__ import annotations

import logging
import os
import re
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from app.core.errors import IngestionError, ValidationFailure

log = logging.getLogger(__name__)

_URL_RE = re.compile(
    r"^(?:https://)?(?:www\.)?github\.com/(?P<owner>[A-Za-z0-9](?:[A-Za-z0-9-]{0,38}))/"
    r"(?P<name>[A-Za-z0-9._-]{1,100}?)(?:\.git)?(?:/tree/(?P<branch>[A-Za-z0-9._/-]{1,100}))?/?$"
)
_BRANCH_RE = re.compile(r"^(?!-)[A-Za-z0-9._/-]{1,100}$")


@dataclass(frozen=True)
class RepoRef:
    owner: str
    name: str
    branch: Optional[str]

    @property
    def clone_url(self) -> str:
        return f"https://github.com/{self.owner}/{self.name}.git"

    @property
    def canonical_url(self) -> str:
        return f"https://github.com/{self.owner}/{self.name}"


def parse_github_url(url: str, branch: Optional[str] = None) -> RepoRef:
    """Accept only https://github.com/<owner>/<repo>[.git][/tree/<branch>]; reject everything else."""
    m = _URL_RE.match(url.strip())
    if not m:
        raise ValidationFailure("Enter a public GitHub repository URL like https://github.com/owner/repo")
    name = m.group("name")
    if name in (".", "..") or name.startswith("-"):
        raise ValidationFailure("Invalid repository name")
    chosen = branch or m.group("branch")
    if chosen:
        chosen = chosen.strip()
        if not _BRANCH_RE.match(chosen) or ".." in chosen:
            raise ValidationFailure("Invalid branch name")
    return RepoRef(m.group("owner"), name, chosen or None)


def _dir_size_mb(path: Path) -> float:
    total = 0
    for root, _dirs, files in os.walk(path):
        for f in files:
            try:
                total += os.lstat(os.path.join(root, f)).st_size
            except OSError:
                pass
    return total / (1024 * 1024)


def clone_repo(ref: RepoRef, dest: Path, timeout: int, max_size_mb: int) -> str:
    """Shallow-clone into `dest` and return the HEAD commit sha.

    Security notes: arguments are passed as a list (no shell); the URL is rebuilt from validated
    components; hooks, submodules, credential prompts and non-HTTPS protocols are disabled.
    """
    if dest.exists():
        shutil.rmtree(dest, ignore_errors=True)
    dest.parent.mkdir(parents=True, exist_ok=True)

    cmd = [
        "git", "-c", "core.hooksPath=/dev/null", "-c", "protocol.allow=never", "-c", "protocol.https.allow=always",
        "-c", "core.symlinks=false", "clone", "--depth", "1", "--single-branch", "--no-tags",
        "--no-recurse-submodules", "--quiet",
    ]
    if ref.branch:
        cmd += ["--branch", ref.branch]
    cmd += ["--", ref.clone_url, str(dest)]
    env = {**os.environ, "GIT_TERMINAL_PROMPT": "0", "GIT_ASKPASS": "echo", "GIT_LFS_SKIP_SMUDGE": "1"}

    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout, env=env, check=False)
    except subprocess.TimeoutExpired:
        shutil.rmtree(dest, ignore_errors=True)
        raise IngestionError(f"Cloning timed out after {timeout}s. The repository may be too large.")
    if proc.returncode != 0:
        shutil.rmtree(dest, ignore_errors=True)
        stderr = (proc.stderr or "").strip().lower()
        if "not found" in stderr or "could not read username" in stderr or "authentication" in stderr:
            raise IngestionError("Repository not found or not public. Only public GitHub repositories are supported.")
        if "remote branch" in stderr:
            raise IngestionError(f"Branch '{ref.branch}' was not found in the repository.")
        log.warning("git clone failed for %s: %s", ref.canonical_url, proc.stderr.strip()[:500])
        raise IngestionError("Could not clone the repository from GitHub.")

    size = _dir_size_mb(dest)
    if size > max_size_mb:
        shutil.rmtree(dest, ignore_errors=True)
        raise IngestionError(f"Repository is {size:.0f} MB, above the {max_size_mb} MB limit for this deployment.")

    sha = subprocess.run(
        ["git", "-C", str(dest), "rev-parse", "HEAD"], capture_output=True, text=True, timeout=20, check=False
    ).stdout.strip()
    return sha[:40]
