"""Citation grounding: every `[path:start-end]` in an answer is verified against retrieved chunks.

Invalid citations (unknown file, or lines outside any retrieved excerpt for that file) are removed
from the answer text rather than shown to the user as if they were real references.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Dict, List, Optional, Sequence, Tuple

BRACKET = re.compile(r"\[([^\[\]\n]{3,400})\]")
PART = re.compile(r"^\s*`?(?P<path>[^\s:`\]]+?)`?\s*:\s*(?:L|lines?\s*)?(?P<s>\d+)(?:\s*[-–—]\s*(?:L)?(?P<e>\d+))?\s*$", re.I)


@dataclass(frozen=True)
class ContextRef:
    chunk_id: int
    path: str
    start_line: int
    end_line: int
    kind: str
    name: str


def _match_path(cited: str, known: Sequence[str]) -> Optional[str]:
    cited = cited.lstrip("./")
    if cited in known:
        return cited
    suffix = [k for k in known if k.endswith("/" + cited)]
    return suffix[0] if len(suffix) == 1 else None


def _resolve(path: str, s: int, e: int, refs: Sequence[ContextRef]) -> Optional[Tuple[ContextRef, int, int]]:
    """Return the best-overlapping context chunk and the cited range clamped to the retrieved lines."""
    if e < s:
        s, e = e, s
    best: Optional[Tuple[int, ContextRef]] = None
    for r in refs:
        if r.path != path:
            continue
        overlap = min(e, r.end_line) - max(s, r.start_line) + 1
        if overlap > 0 and (best is None or overlap > best[0]):
            best = (overlap, r)
    if best is None:
        return None
    r = best[1]
    return r, max(s, r.start_line), min(e, r.end_line)


def ground_citations(answer: str, refs: Sequence[ContextRef]) -> Tuple[str, List[Dict], int]:
    """Return (rewritten answer, verified citations in first-use order, number of removed citations)."""
    known_paths = sorted({r.path for r in refs})
    found: Dict[Tuple[str, int, int], Dict] = {}
    removed = 0

    def rewrite(m: re.Match) -> str:
        nonlocal removed
        parts = [p for p in re.split(r"[;,](?=\s*[^\s\d])", m.group(1)) if p.strip()]
        matches = [PART.match(p) for p in parts]
        if not parts or not all(matches):
            return m.group(0)  # ordinary bracketed text, not a citation
        good: List[str] = []
        for pm in matches:
            path = _match_path(pm.group("path"), known_paths)
            s = int(pm.group("s"))
            e = int(pm.group("e") or s)
            res = _resolve(path, s, e, refs) if path else None
            if res is None:
                removed += 1
                continue
            ref, cs, ce = res
            key = (ref.path, cs, ce)
            if key not in found:
                found[key] = {"path": ref.path, "start_line": cs, "end_line": ce, "chunk_id": ref.chunk_id,
                              "kind": ref.kind, "name": ref.name}
            good.append(f"{ref.path}:{cs}" if cs == ce else f"{ref.path}:{cs}-{ce}")
        return "[" + ", ".join(good) + "]" if good else ""

    rewritten = BRACKET.sub(rewrite, answer)
    rewritten = re.sub(r"[ \t]{2,}", " ", rewritten)
    rewritten = re.sub(r" +([.,;:])", r"\1", rewritten)
    return rewritten.strip(), list(found.values()), removed
