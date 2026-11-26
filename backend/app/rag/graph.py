"""The 4-stage LangGraph RAG agent.

    decompose  ->  retrieve  ->  dedupe  ->  generate

  decompose : LLM splits the question into 2-4 targeted sub-queries (heuristic fallback on failure).
  retrieve  : MiniLM-embeds every sub-query and runs FAISS similarity search on THIS repository's index.
  dedupe    : removes duplicate retrievals (same chunk, contained/overlapping chunks, identical code).
  generate  : answers from the numbered, line-annotated excerpts; citations are verified afterwards.
"""
from __future__ import annotations

import json
import logging
import re
import time
from dataclasses import dataclass
from typing import Any, Callable, Dict, List, Optional, Sequence, Tuple, TypedDict

from langgraph.graph import END, START, StateGraph

from app.core.config import Settings
from app.ingestion.chunker import CodeChunk
from app.ingestion.embedder import Embedder
from app.ingestion.index_store import RepoVectorIndex
from app.llm.base import LLMProvider, Message
from app.rag import duplicates as dup
from app.rag.citations import ContextRef, ground_citations
from app.rag.prompts import (
    ANSWER_FORMAT_REMINDER, DECOMPOSE_MODE_HINTS, DECOMPOSE_SYSTEM, GENERATE_SYSTEM, MODES,
)

log = logging.getLogger(__name__)

MIN_SUBQUERIES, MAX_SUBQUERIES = 2, 4


class RAGState(TypedDict, total=False):
    question: str
    mode: str
    repo_name: str
    history: List[Message]
    sub_queries: List[str]
    raw_hits: List[Dict[str, Any]]  # one entry per (sub-query, chunk) retrieval, BEFORE de-duplication
    contexts: List[Dict[str, Any]]  # de-duplicated chunks passed to the LLM
    dedupe_stats: Dict[str, int]
    duplicate_report: List[Dict[str, Any]]
    answer: str
    citations: List[Dict[str, Any]]
    removed_citations: int
    timings: Dict[str, int]


# --------------------------------------------------------------------------------------
# Stage 1: decompose
# --------------------------------------------------------------------------------------

_STOP = set("""a an the is are was were be been of in on at to for from with by and or not how what where which who why
when does do did can could should would this that these those it its into about me my our your their there here
please show tell explain describe find give list code function class method file repo repository codebase""".split())


def _keywords(text: str) -> str:
    toks = re.findall(r"[A-Za-z_][A-Za-z0-9_./-]*", text)
    kept = [t for t in toks if t.lower() not in _STOP and len(t) > 2]
    return " ".join(dict.fromkeys(kept))[:200]


def _heuristic_subqueries(question: str, mode: str) -> List[str]:
    out = [question.strip()]
    kw = _keywords(question)
    if kw and kw.lower() != question.strip().lower():
        out.append(kw)
    extra = {
        "explain": f"{kw} implementation and usage",
        "optimize": f"{kw} loop performance inefficient database query",
        "duplicates": f"{kw} repeated similar logic",
    }.get(mode)
    if extra:
        out.append(extra)
    if len(out) < MIN_SUBQUERIES:
        out.append(f"{question.strip()} implementation")
    return out[:MAX_SUBQUERIES]


def _parse_subqueries(raw: str) -> List[str]:
    text = raw.strip()
    text = re.sub(r"^```(?:json)?|```$", "", text, flags=re.M).strip()
    items: List[str] = []
    m = re.search(r"\[.*\]", text, flags=re.S)
    if m:
        try:
            data = json.loads(m.group(0))
            items = [str(x).strip() for x in data if isinstance(x, (str, int, float)) and str(x).strip()]
        except ValueError:
            items = []
    if not items:  # tolerate bullet/numbered lists
        items = [re.sub(r"^[\s\-*\d.)]+", "", ln).strip().strip('"') for ln in text.splitlines()]
        items = [i for i in items if len(i) > 2 and not i.startswith(("[", "]"))]
    seen, out = set(), []
    for q in items:
        q = q[:300]
        if q.lower() not in seen:
            seen.add(q.lower())
            out.append(q)
    return out


def make_decompose(llm: LLMProvider, settings: Settings) -> Callable[[RAGState], Dict]:
    def decompose(state: RAGState) -> Dict:
        t0 = time.monotonic()
        question, mode = state["question"], state["mode"]
        system = DECOMPOSE_SYSTEM + ("\n" + DECOMPOSE_MODE_HINTS[mode] if DECOMPOSE_MODE_HINTS.get(mode) else "")
        history = _history_for_prompt(state.get("history", []), max_chars=1500)
        subs: List[str] = []
        try:
            raw = llm.generate(system, [*history, {"role": "user", "content": question}], temperature=0.0, max_tokens=300)
            subs = _parse_subqueries(raw)
        except Exception as e:  # noqa: BLE001 - planning must never block answering
            log.warning("decompose via LLM failed (%s); using heuristic sub-queries", type(e).__name__)
        if len(subs) < MIN_SUBQUERIES:
            for q in _heuristic_subqueries(question, mode):
                if q.lower() not in {s.lower() for s in subs}:
                    subs.append(q)
                if len(subs) >= MIN_SUBQUERIES:
                    break
        subs = subs[:MAX_SUBQUERIES]
        return {"sub_queries": subs, "timings": {**state.get("timings", {}), "decompose": int((time.monotonic() - t0) * 1000)}}

    return decompose


# --------------------------------------------------------------------------------------
# Stage 2: retrieve
# --------------------------------------------------------------------------------------

def make_retrieve(rvi: RepoVectorIndex, embedder: Embedder, settings: Settings) -> Callable[[RAGState], Dict]:
    def retrieve(state: RAGState) -> Dict:
        t0 = time.monotonic()
        subs = state["sub_queries"]
        vecs = embedder.encode(subs, batch_size=len(subs))
        hits: List[Dict[str, Any]] = []
        for qi, vec in enumerate(vecs):
            for rank, (cid, score) in enumerate(rvi.search(vec, settings.retrieval_top_k)):
                hits.append({"chunk_id": cid, "score": score, "sub_query": qi, "rank": rank})
        return {"raw_hits": hits, "timings": {**state.get("timings", {}), "retrieve": int((time.monotonic() - t0) * 1000)}}

    return retrieve


# --------------------------------------------------------------------------------------
# Stage 3: dedupe
# --------------------------------------------------------------------------------------

def dedupe_hits(chunks: Sequence[CodeChunk], hits: Sequence[Dict[str, Any]]) -> Tuple[List[Dict[str, Any]], Dict[str, int]]:
    """Collapse retrievals into unique, non-redundant chunks.

    1. same chunk retrieved by several sub-queries      -> keep the best score
    2. a chunk fully contained in another kept chunk    -> drop the contained one
    3. different chunks with identical (normalised) code -> keep the best, remember the other locations
    """
    stats = {"retrieved": len(hits), "same_chunk": 0, "contained": 0, "identical_code": 0}

    best: Dict[int, Dict[str, Any]] = {}
    for h in hits:
        cur = best.get(h["chunk_id"])
        if cur is None:
            best[h["chunk_id"]] = {"chunk_id": h["chunk_id"], "score": h["score"], "sub_queries": {h["sub_query"]}}
        else:
            stats["same_chunk"] += 1
            cur["score"] = max(cur["score"], h["score"])
            cur["sub_queries"].add(h["sub_query"])
    ordered = sorted(best.values(), key=lambda x: x["score"], reverse=True)

    kept: List[Dict[str, Any]] = []
    for cand in ordered:
        c = chunks[cand["chunk_id"]]
        contained = False
        for k in kept:
            o = chunks[k["chunk_id"]]
            if o.path == c.path and o.start_line <= c.start_line and c.end_line <= o.end_line:
                contained = True
                k["sub_queries"] |= cand["sub_queries"]
                break
        if contained:
            stats["contained"] += 1
            continue
        kept.append(cand)

    final: List[Dict[str, Any]] = []
    by_hash: Dict[str, Dict[str, Any]] = {}
    for cand in kept:
        c = chunks[cand["chunk_id"]]
        first = by_hash.get(c.content_hash)
        if first is not None:
            stats["identical_code"] += 1
            first.setdefault("also_at", []).append(f"{c.path}:{c.start_line}-{c.end_line}")
            first["sub_queries"] |= cand["sub_queries"]
            continue
        by_hash[c.content_hash] = cand
        final.append(cand)
    return final, stats


def _context_entry(chunks: Sequence[CodeChunk], cand: Dict[str, Any]) -> Dict[str, Any]:
    c = chunks[cand["chunk_id"]]
    return {
        "chunk_id": cand["chunk_id"], "score": round(float(cand["score"]), 4), "path": c.path,
        "start_line": c.start_line, "end_line": c.end_line, "kind": c.kind, "name": c.qualified_name or c.name,
        "language": c.language, "code": c.code, "also_at": cand.get("also_at", []),
        "sub_queries": sorted(cand.get("sub_queries", [])), "truncated": c.truncated,
    }


def make_dedupe(rvi: RepoVectorIndex, settings: Settings) -> Callable[[RAGState], Dict]:
    def dedupe(state: RAGState) -> Dict:
        t0 = time.monotonic()
        chunks = rvi.chunks
        unique, stats = dedupe_hits(chunks, state["raw_hits"])

        selected: List[Dict[str, Any]] = []
        used_chars = 0
        for cand in unique:
            size = len(chunks[cand["chunk_id"]].code) + 120
            if selected and (len(selected) >= settings.max_context_chunks or used_chars + size > settings.max_context_chars):
                continue
            selected.append(cand)
            used_chars += size

        report: List[Dict[str, Any]] = []
        if state["mode"] == "duplicates":
            ids = [c["chunk_id"] for c in selected]
            pairs = dup._exact_pairs_by_hash(rvi, ids) + dup.find_pairs(rvi, ids, settings.near_duplicate_threshold)
            seen_pairs = set()
            for p in pairs:
                key = tuple(sorted((p["a"]["chunk_id"], p["b"]["chunk_id"])))
                if key in seen_pairs:
                    continue
                seen_pairs.add(key)
                report.append(p)
                # The model must see BOTH sides of every reported pair.
                for side in (p["a"], p["b"]):
                    if side["chunk_id"] not in {c["chunk_id"] for c in selected} and len(selected) < settings.max_context_chunks + 6:
                        selected.append({"chunk_id": side["chunk_id"], "score": 0.0, "sub_queries": set()})
            report = report[:15]

        contexts = [_context_entry(chunks, c) for c in selected]
        return {
            "contexts": contexts, "dedupe_stats": {**stats, "kept": len(contexts)}, "duplicate_report": report,
            "timings": {**state.get("timings", {}), "dedupe": int((time.monotonic() - t0) * 1000)},
        }

    return dedupe


# --------------------------------------------------------------------------------------
# Stage 4: generate
# --------------------------------------------------------------------------------------

def _numbered(ctx: Dict[str, Any]) -> str:
    start = ctx["start_line"]
    lines = ctx["code"].split("\n")
    width = len(str(start + len(lines)))
    return "\n".join(f"{start + i:>{width}}| {ln}" for i, ln in enumerate(lines))


def build_context_block(contexts: Sequence[Dict[str, Any]], report: Sequence[Dict[str, Any]]) -> str:
    parts: List[str] = []
    for n, c in enumerate(contexts, start=1):
        extra = f" (identical code also at: {', '.join(c['also_at'])})" if c.get("also_at") else ""
        trunc = " (class header only; members are separate sources)" if c.get("truncated") else ""
        parts.append(
            f"### Source {n}: {c['path']} lines {c['start_line']}-{c['end_line']} "
            f"[{c['language']} {c['kind']} `{c['name']}`]{extra}{trunc}\n{_numbered(c)}"
        )
    if report:
        lines = ["## Static duplicate analysis"]
        for p in report:
            a, b = p["a"], p["b"]
            kind = "EXACT duplicate" if p["exact"] else (
                f"near-duplicate (embedding {p['embedding_similarity']}, lexical {p['lexical_similarity']})")
            lines.append(f"- {kind}: {a['path']}:{a['start_line']}-{a['end_line']} ({a['name']}) <-> "
                         f"{b['path']}:{b['start_line']}-{b['end_line']} ({b['name']})")
        parts.append("\n".join(lines))
    return "\n\n".join(parts)


def _history_for_prompt(history: Sequence[Message], max_chars: int) -> List[Message]:
    out: List[Message] = []
    for m in history:
        content = m["content"]
        out.append({"role": m["role"], "content": content if len(content) <= max_chars else content[:max_chars] + " …"})
    return out


def make_generate(llm: LLMProvider, settings: Settings) -> Callable[[RAGState], Dict]:
    def generate(state: RAGState) -> Dict:
        t0 = time.monotonic()
        contexts = state["contexts"]
        mode = state["mode"]
        if not contexts:
            return {"answer": "I couldn't find any indexed code relevant to this question in the repository.",
                    "citations": [], "removed_citations": 0,
                    "timings": {**state.get("timings", {}), "generate": 0}}
        system = GENERATE_SYSTEM[mode].replace("{repo}", state["repo_name"])
        block = build_context_block(contexts, state.get("duplicate_report", []))
        user = (f"Code excerpts from the repository:\n\n{block}\n\n---\nQuestion: {state['question']}\n\n"
                f"{ANSWER_FORMAT_REMINDER}")
        history = _history_for_prompt(state.get("history", []), max_chars=2500)
        raw = llm.generate(system, [*history, {"role": "user", "content": user}],
                           temperature=settings.llm_temperature, max_tokens=settings.llm_max_tokens)
        refs = [ContextRef(c["chunk_id"], c["path"], c["start_line"], c["end_line"], c["kind"], c["name"]) for c in contexts]
        answer, citations, removed = ground_citations(raw, refs)
        return {"answer": answer, "citations": citations, "removed_citations": removed,
                "timings": {**state.get("timings", {}), "generate": int((time.monotonic() - t0) * 1000)}}

    return generate


# --------------------------------------------------------------------------------------
# Graph assembly
# --------------------------------------------------------------------------------------

def build_graph(rvi: RepoVectorIndex, embedder: Embedder, llm: LLMProvider, settings: Settings):
    g = StateGraph(RAGState)
    g.add_node("decompose", make_decompose(llm, settings))
    g.add_node("retrieve", make_retrieve(rvi, embedder, settings))
    g.add_node("dedupe", make_dedupe(rvi, settings))
    g.add_node("generate", make_generate(llm, settings))
    g.add_edge(START, "decompose")
    g.add_edge("decompose", "retrieve")
    g.add_edge("retrieve", "dedupe")
    g.add_edge("dedupe", "generate")
    g.add_edge("generate", END)
    return g.compile()


def run_rag(rvi: RepoVectorIndex, embedder: Embedder, llm: LLMProvider, settings: Settings, *, question: str,
            mode: str, repo_name: str, history: Optional[List[Message]] = None) -> RAGState:
    if mode not in MODES:
        raise ValueError(f"unknown mode {mode}")
    graph = build_graph(rvi, embedder, llm, settings)
    return graph.invoke({"question": question, "mode": mode, "repo_name": repo_name,
                         "history": history or [], "timings": {}})
