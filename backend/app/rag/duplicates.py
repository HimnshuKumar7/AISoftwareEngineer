"""Duplicate-code detection.

Two signals, combined:
  1. exact duplicates   - identical whitespace-normalised code (content hash), and
  2. near duplicates    - FAISS nearest neighbours over MiniLM embeddings as *candidates*, confirmed by
                          a lexical token-shingle Jaccard score so that "semantically similar but
                          different" functions are not reported as copy-paste.
"""
from __future__ import annotations

import re
from collections import defaultdict
from typing import Dict, Iterable, List, Optional, Sequence, Set, Tuple

from app.ingestion.chunker import CodeChunk
from app.ingestion.index_store import RepoVectorIndex

MIN_LINES = 4
MIN_NONSPACE_CHARS = 120
LEXICAL_THRESHOLD = 0.5
SCAN_NEIGHBOURS = 6
MAX_SCAN_CHUNKS = 8000

_TOKEN = re.compile(r"\w+|[^\s\w]")


def comparable(c: CodeChunk) -> bool:
    """Only whole functions/methods are compared (not class headers, windows, docs or module code)."""
    if c.kind not in ("function", "method") or c.part:
        return False
    if c.end_line - c.start_line + 1 < MIN_LINES:
        return False
    return len(re.sub(r"\s+", "", c.code)) >= MIN_NONSPACE_CHARS


def _shingles(code: str, n: int = 3) -> Set[Tuple[str, ...]]:
    toks = _TOKEN.findall(code)
    if len(toks) < n:
        return {tuple(toks)} if toks else set()
    return {tuple(toks[i:i + n]) for i in range(len(toks) - n + 1)}


def lexical_similarity(a: str, b: str) -> float:
    sa, sb = _shingles(a), _shingles(b)
    if not sa or not sb:
        return 0.0
    return len(sa & sb) / len(sa | sb)


def _overlaps(a: CodeChunk, b: CodeChunk) -> bool:
    return a.path == b.path and a.start_line <= b.end_line and b.start_line <= a.end_line


def _summary(c: CodeChunk, idx: int) -> Dict:
    return {
        "chunk_id": idx, "path": c.path, "start_line": c.start_line, "end_line": c.end_line,
        "name": c.qualified_name or c.name, "kind": c.kind, "language": c.language,
    }


def find_pairs(
    rvi: RepoVectorIndex, candidate_ids: Sequence[int], threshold: float, neighbours: int = SCAN_NEIGHBOURS,
    batch: int = 256,
) -> List[Dict]:
    """Near/exact duplicate pairs among `candidate_ids` and their neighbours in the same repo index."""
    chunks = rvi.chunks
    ids = [i for i in candidate_ids if comparable(chunks[i])]
    if not ids:
        return []
    allvec = rvi.vectors()
    seen: Set[Tuple[int, int]] = set()
    pairs: List[Dict] = []
    k = min(neighbours + 1, len(chunks))
    for start in range(0, len(ids), batch):
        sub = ids[start:start + batch]
        scores, nbrs = rvi.index.search(allvec[sub], k)
        for qi, row_ids, row_scores in zip(sub, nbrs, scores):
            for j, s in zip(row_ids, row_scores):
                j = int(j)
                if j < 0 or j == qi or float(s) < threshold:
                    continue
                a, b = chunks[qi], chunks[j]
                if not comparable(b) or _overlaps(a, b):
                    continue
                key = (min(qi, j), max(qi, j))
                if key in seen:
                    continue
                seen.add(key)
                exact = a.content_hash == b.content_hash
                lex = 1.0 if exact else lexical_similarity(a.code, b.code)
                if not exact and lex < LEXICAL_THRESHOLD:
                    continue
                pairs.append({
                    "a": _summary(a, qi), "b": _summary(b, j),
                    "embedding_similarity": round(float(s), 4), "lexical_similarity": round(lex, 4), "exact": exact,
                })
    pairs.sort(key=lambda p: (p["exact"], p["lexical_similarity"], p["embedding_similarity"]), reverse=True)
    return pairs


def _exact_pairs_by_hash(rvi: RepoVectorIndex, ids: Iterable[int]) -> List[Dict]:
    """Exact duplicates are found by hash so that they never depend on neighbour-list truncation."""
    by_hash: Dict[str, List[int]] = defaultdict(list)
    for i in ids:
        c = rvi.chunks[i]
        if comparable(c):
            by_hash[c.content_hash].append(i)
    out: List[Dict] = []
    for members in by_hash.values():
        for x in range(len(members)):
            for y in range(x + 1, len(members)):
                a, b = rvi.chunks[members[x]], rvi.chunks[members[y]]
                if _overlaps(a, b):
                    continue
                out.append({"a": _summary(a, members[x]), "b": _summary(b, members[y]),
                            "embedding_similarity": 1.0, "lexical_similarity": 1.0, "exact": True})
    return out


def scan_repository(rvi: RepoVectorIndex, threshold: float, limit: int = 50) -> Dict:
    """Whole-repository duplicate scan, returned as groups (connected components of duplicate pairs)."""
    all_ids = [i for i, c in enumerate(rvi.chunks) if comparable(c)]
    truncated = len(all_ids) > MAX_SCAN_CHUNKS
    scan_ids = all_ids[:MAX_SCAN_CHUNKS]

    pairs = _exact_pairs_by_hash(rvi, scan_ids) + find_pairs(rvi, scan_ids, threshold)
    # Merge pair lists; exact wins.
    merged: Dict[Tuple[int, int], Dict] = {}
    for p in pairs:
        key = tuple(sorted((p["a"]["chunk_id"], p["b"]["chunk_id"])))
        if key not in merged or (p["exact"] and not merged[key]["exact"]):
            merged[key] = p

    parent: Dict[int, int] = {}

    def find(x: int) -> int:
        parent.setdefault(x, x)
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    for (a, b) in merged:
        parent[find(a)] = find(b)
    groups: Dict[int, Set[int]] = defaultdict(set)
    for (a, b) in merged:
        groups[find(a)].update((a, b))

    out_groups = []
    for members in groups.values():
        member_pairs = [p for k, p in merged.items() if k[0] in members]
        out_groups.append({
            "size": len(members),
            "exact": all(p["exact"] for p in member_pairs),
            "min_lexical_similarity": min(p["lexical_similarity"] for p in member_pairs),
            "locations": [_summary(rvi.chunks[m], m) | {"code_preview": "\n".join(rvi.chunks[m].code.splitlines()[:6])}
                          for m in sorted(members, key=lambda m: (rvi.chunks[m].path, rvi.chunks[m].start_line))],
        })
    out_groups.sort(key=lambda g: (g["exact"], g["size"], g["min_lexical_similarity"]), reverse=True)
    return {
        "threshold": threshold, "scanned_chunks": len(scan_ids), "scan_truncated": truncated,
        "group_count": len(out_groups), "groups": out_groups[:limit],
    }
