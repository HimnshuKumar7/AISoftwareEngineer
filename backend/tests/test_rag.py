"""4-stage LangGraph pipeline: decomposition, retrieval, de-duplication, grounded generation."""
import json

import pytest

from app.ingestion.chunker import CodeChunk
from app.llm.base import LLMProvider
from app.rag.citations import ContextRef, ground_citations
from app.rag.graph import (
    MAX_SUBQUERIES, MIN_SUBQUERIES, _parse_subqueries, build_context_block, build_graph, dedupe_hits, run_rag,
)
from tests.sample_repo import FILES, build_index


@pytest.fixture
def rvi(fake_embedder):
    idx, _ = build_index(fake_embedder)
    return idx


class FixedPlanLLM(LLMProvider):
    """Returns a fixed planning response; fails or echoes for generation."""

    name = "fixed"

    def __init__(self, plan, fail_plan=False):
        super().__init__("m")
        self.plan, self.fail_plan = plan, fail_plan

    def _build_request(self, *a, **k): ...
    def _parse_response(self, d): ...

    def generate(self, system, messages, *, temperature=0.1, max_tokens=1800):
        if system.startswith("You are the query-planning stage"):
            if self.fail_plan:
                raise RuntimeError("planner down")
            return self.plan
        return "ok [auth/jwt_utils.py:1-5]"


def test_graph_has_exactly_the_four_stages_in_order(rvi, fake_embedder, scripted_llm, settings):
    g = build_graph(rvi, fake_embedder, scripted_llm, settings).get_graph()
    names = [n for n in g.nodes if not n.startswith("__")]
    assert names == ["decompose", "retrieve", "dedupe", "generate"]
    edges = {(e.source, e.target) for e in g.edges}
    assert {("__start__", "decompose"), ("decompose", "retrieve"), ("retrieve", "dedupe"),
            ("dedupe", "generate"), ("generate", "__end__")} <= edges


def test_end_to_end_run(rvi, fake_embedder, scripted_llm, settings):
    state = run_rag(rvi, fake_embedder, scripted_llm, settings, question="How is the JWT token verified?",
                    mode="qa", repo_name="acme/sample")
    assert MIN_SUBQUERIES <= len(state["sub_queries"]) <= MAX_SUBQUERIES
    assert state["contexts"][0]["path"] == "auth/jwt_utils.py"
    assert set(state["timings"]) == {"decompose", "retrieve", "dedupe", "generate"}
    # 1 planning call + 1 generation call
    assert len(scripted_llm.calls) == 2

    # grounded citations: real ones kept & normalised, fabricated one removed, ordinary brackets untouched
    assert "does/not/exist.py" not in state["answer"]
    assert state["removed_citations"] == 1
    assert "[1, 2]" in state["answer"]
    top = state["contexts"][0]
    assert any(c["path"] == top["path"] and top["start_line"] <= c["start_line"] <= c["end_line"] <= top["end_line"]
               for c in state["citations"])


def test_retrieval_only_uses_the_given_repo_index(rvi, fake_embedder, scripted_llm, settings):
    state = run_rag(rvi, fake_embedder, scripted_llm, settings, question="delete user sessions", mode="qa", repo_name="r")
    allowed = {c.path for c in rvi.chunks}
    assert {c["path"] for c in state["contexts"]} <= allowed
    assert all(h["chunk_id"] < len(rvi.chunks) for h in state["raw_hits"])


@pytest.mark.parametrize("plan,expected", [
    ('["only one"]', (2, 4)),
    (json.dumps([f"query {i}" for i in range(9)]), (4, 4)),
    ("```json\n[\"a thing\", \"b thing\", \"c thing\"]\n```", (3, 3)),
    ("1. find the jwt code\n2. find the token expiry\n- check secrets", (3, 3)),
    ("garbage", (2, 4)),
])
def test_subquery_count_is_always_2_to_4(rvi, fake_embedder, settings, plan, expected):
    state = run_rag(rvi, fake_embedder, FixedPlanLLM(plan), settings, question="how does jwt token auth work",
                    mode="qa", repo_name="r")
    lo, hi = expected
    assert lo <= len(state["sub_queries"]) <= hi
    assert len(state["sub_queries"]) == len({q.lower() for q in state["sub_queries"]})


def test_planner_failure_falls_back_to_heuristics(rvi, fake_embedder, settings):
    state = run_rag(rvi, fake_embedder, FixedPlanLLM("", fail_plan=True), settings,
                    question="where is the database connection opened", mode="qa", repo_name="r")
    assert 2 <= len(state["sub_queries"]) <= 4 and state["contexts"]


def test_parse_subqueries_handles_noise():
    assert _parse_subqueries('Sure! ["a b", "c d"] hope that helps') == ["a b", "c d"]


def _chunk(path, s, e, code="x = 1", kind="function", h=None, truncated=False):
    return CodeChunk(path, "python", kind, "n", "n", s, e, code, content_hash=h or str(hash((path, s, e, code))),
                     truncated=truncated)


def test_dedupe_removes_same_contained_and_identical():
    chunks = [
        _chunk("a.py", 1, 10, h="h1"),                 # 0: class-like container
        _chunk("a.py", 3, 6, h="h2"),                  # 1: contained in 0
        _chunk("b.py", 1, 10, h="h1"),                 # 2: identical code to 0
        _chunk("c.py", 1, 5, h="h3"),                  # 3: unique
    ]
    hits = [
        {"chunk_id": 0, "score": 0.9, "sub_query": 0, "rank": 0},
        {"chunk_id": 0, "score": 0.8, "sub_query": 1, "rank": 0},   # same chunk via another sub-query
        {"chunk_id": 1, "score": 0.7, "sub_query": 1, "rank": 1},
        {"chunk_id": 2, "score": 0.6, "sub_query": 2, "rank": 0},
        {"chunk_id": 3, "score": 0.5, "sub_query": 2, "rank": 1},
    ]
    final, stats = dedupe_hits(chunks, hits)
    assert [f["chunk_id"] for f in final] == [0, 3]
    assert final[0]["score"] == 0.9 and final[0]["sub_queries"] == {0, 1, 2}
    assert final[0]["also_at"] == ["b.py:1-10"]
    assert stats == {"retrieved": 5, "same_chunk": 1, "contained": 1, "identical_code": 1}


def test_context_block_shows_true_line_numbers(rvi, fake_embedder, scripted_llm, settings):
    state = run_rag(rvi, fake_embedder, scripted_llm, settings, question="verify jwt token", mode="qa", repo_name="r")
    block = build_context_block(state["contexts"], [])
    ctx = state["contexts"][0]
    src_lines = FILES[ctx["path"]].split("\n")
    first = ctx["start_line"]
    assert f"{first}| {src_lines[first - 1]}".strip() in block.replace("  ", " ") or f"| {src_lines[first - 1]}" in block


def test_duplicates_mode_reports_exact_and_near_pairs_and_includes_both_sides(rvi, fake_embedder, scripted_llm, settings):
    state = run_rag(rvi, fake_embedder, scripted_llm, settings, question="slugify title url slug", mode="duplicates",
                    repo_name="r")
    report = state["duplicate_report"]
    assert report, "expected duplicate pairs"
    exact = [p for p in report if p["exact"]]
    assert exact and {exact[0]["a"]["path"], exact[0]["b"]["path"]} == {"utils/strings.py", "utils/text.py"}
    in_ctx = {c["chunk_id"] for c in state["contexts"]}
    for p in report:
        assert p["a"]["chunk_id"] in in_ctx and p["b"]["chunk_id"] in in_ctx
    prompt = scripted_llm.calls[-1]["messages"][-1]["content"]
    assert "Static duplicate analysis" in prompt and "EXACT duplicate" in prompt


def test_mode_changes_the_generation_prompt(rvi, fake_embedder, scripted_llm, settings):
    systems = {}
    for mode in ("qa", "explain", "optimize", "duplicates"):
        scripted_llm.calls.clear()
        run_rag(rvi, fake_embedder, scripted_llm, settings, question="user service", mode=mode, repo_name="acme/sample")
        systems[mode] = scripted_llm.calls[-1]["system"]
    assert len(set(systems.values())) == 4 and all("acme/sample" in s for s in systems.values())
    assert "documentation" in systems["explain"] and "improvements" in systems["optimize"]


def test_conversation_history_reaches_the_llm(rvi, fake_embedder, scripted_llm, settings):
    hist = [{"role": "user", "content": "what is UserService"}, {"role": "assistant", "content": "A CRUD class."}]
    run_rag(rvi, fake_embedder, scripted_llm, settings, question="and how does it delete?", mode="qa",
            repo_name="r", history=hist)
    gen = scripted_llm.calls[-1]["messages"]
    assert [m["role"] for m in gen] == ["user", "assistant", "user"]


def test_empty_retrieval_yields_graceful_answer(fake_embedder, scripted_llm, settings):
    from app.ingestion.index_store import RepoVectorIndex
    import faiss
    empty = RepoVectorIndex(faiss.IndexFlatIP(384), [])
    state = run_rag(empty, fake_embedder, scripted_llm, settings, question="anything at all", mode="qa", repo_name="r")
    assert "couldn't find" in state["answer"] and state["citations"] == []


# ---------------------------------------------------------------- citation grounding unit tests
REFS = [ContextRef(0, "src/a.py", 10, 30, "function", "f"), ContextRef(1, "src/b.py", 5, 9, "method", "C.m")]


def test_ground_citations_variants():
    ans = ("See [src/a.py:12-15], [a.py:20], [src/a.py:L25-L40], [`src/b.py`:5-9] and [src/b.py:50-60], "
           "[src/a.py:12-15, src/b.py:6]. Also [note] and [x y: z].")
    out, cites, removed = ground_citations(ans, REFS)
    assert "[src/a.py:12-15]" in out
    assert "[src/a.py:20]" in out                   # suffix path 'a.py' resolved uniquely
    assert "[src/a.py:25-30]" in out                # clamped to retrieved lines
    assert "[src/b.py:5-9]" in out
    assert "src/b.py:50" not in out and removed == 1
    assert "[src/a.py:12-15, src/b.py:6]" in out
    assert "[note]" in out and "[x y: z]" in out    # non-citations untouched
    assert [c["path"] for c in cites] == ["src/a.py", "src/a.py", "src/a.py", "src/b.py", "src/b.py"]
    assert all(c["chunk_id"] in (0, 1) for c in cites)


def test_ground_citations_rejects_ambiguous_suffix_and_unknown():
    refs = REFS + [ContextRef(2, "lib/a.py", 1, 50, "function", "g")]
    out, cites, removed = ground_citations("x [a.py:12] y [zzz.py:1]", refs)
    assert removed == 2 and cites == [] and "[" not in out
