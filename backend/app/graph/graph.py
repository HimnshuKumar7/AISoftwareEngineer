"""
Builds the LangGraph pipeline:

    Planner -> Code Search -> Reasoner -> Final Answer

Planner:      breaks the user's question into 2-4 targeted search queries.
Code Search:  runs FAISS similarity search for each query, dedupes results.
Reasoner:     reads the retrieved code and drafts an internal analysis.
Final Answer: turns the analysis into a clean, cited answer for the user.
"""
import json
import re

from langchain_core.messages import HumanMessage, SystemMessage
from langgraph.graph import StateGraph, START, END

from app.config import settings
from app.graph.state import AgentState
from app.llm.context import invoke_bounded, truncate_text
from app.llm.provider import get_llm
from app.vectorstore.faiss_store import search


def _extract_json_list(text: str) -> list[str]:
    match = re.search(r"\[.*\]", text, re.DOTALL)
    if not match:
        return [text.strip()]
    try:
        data = json.loads(match.group(0))
        return [str(x) for x in data][:5]
    except json.JSONDecodeError:
        return [text.strip()]


def planner_node(state: AgentState) -> AgentState:
    llm = get_llm()
    system_prompt = (
        "You are the Planner for a codebase Q&A agent. Your job is to extract 2 to 4 targeted search queries "
        "from the user's question to retrieve relevant code snippets and documentation from a vector database.\n"
        "- Include key domain terms, algorithm/model names, or technical concepts mentioned in or implied by the question.\n"
        "- If the question asks what the codebase is about, what algorithms/models exist, or for an overview, "
        "include relevant keywords like 'algorithm', 'model', 'class', 'README', or main topic terms.\n"
        "- Respond with ONLY a JSON array of 2 to 4 strings, nothing else."
    )
    user_prompt = f"Question: {truncate_text(state['question'], settings.MAX_QUESTION_CHARS)}"
    resp = invoke_bounded(llm, [
        SystemMessage(content=system_prompt),
        HumanMessage(content=user_prompt),
    ])
    queries = _extract_json_list(resp.content)
    if not queries:
        queries = [state["question"]]
    print(f"Planner node executed. Generated plan: {queries}")
    return {"plan": queries[:4]}


def code_search_node(state: AgentState) -> AgentState:
    seen = set()
    retrieved = []
    
    # 1. ALWAYS search the user's original question first so intent is never lost
    queries = [state["question"]]

    # 2. Add the plan's sub-queries
    for q in (state.get("plan") or []):
        if q and q not in queries:
            queries.append(q)

    # 3. For broad questions (overview, what is, algorithms, architecture), include baseline terms
    q_lower = state["question"].lower()
    if any(term in q_lower for term in [
        "about", "what is", "overview", "summary", "explain", "end to end",
        "working", "architecture", "flow", "how does", "algorithm", "model", "project"
    ]):
        for kw in ["README", "model"]:
            if kw not in queries:
                queries.append(kw)

    for query in queries[:5]:
        for doc in search(state["repo_id"], query, k=settings.TOP_K):
            key = (doc.metadata["file_path"], doc.metadata["start_line"], doc.metadata["end_line"])
            if key in seen:
                continue
            seen.add(key)
            retrieved.append({
                "file_path": doc.metadata["file_path"],
                "start_line": doc.metadata["start_line"],
                "end_line": doc.metadata["end_line"],
                "symbol": doc.metadata.get("symbol", ""),
                "snippet": doc.page_content,
            })
    print(f"Code Search node executed. Retrieved {len(retrieved)} chunks across {len(queries)} queries.")
    return {"retrieved": retrieved[:settings.MAX_RETRIEVED_CHUNKS]}


def _rag_context(retrieved: list[dict]) -> str:
    """Send only the most relevant, bounded code excerpts to the Reasoner."""
    excerpts = []
    used = 0
    for source in retrieved[:settings.MAX_RETRIEVED_CHUNKS]:
        header = (
            f"File: {source['file_path']} (lines {source['start_line']}-{source['end_line']}, "
            f"symbol: {source['symbol']})\n"
        )
        available = settings.MAX_RAG_CONTEXT_CHARS - used - len(header)
        if available <= 0:
            break
        snippet = truncate_text(
            source["snippet"], min(settings.MAX_RAG_CHUNK_CHARS, available)
        )
        excerpt = header + snippet
        excerpts.append(excerpt)
        used += len(excerpt) + 5  # separator
    return "\n\n---\n\n".join(excerpts) or "No relevant code was retrieved."


def reasoner_node(state: AgentState) -> AgentState:
    llm = get_llm()
    retrieved = state.get("retrieved", [])
    actual_files = sorted(set(r["file_path"] for r in retrieved))
    files_list_str = ", ".join(f"`{f}`" for f in actual_files) if actual_files else "None"

    context = _rag_context(retrieved)

    system_prompt = (
        "Analyze the codebase using only the verified files and excerpts. Do not "
        "invent files, modules, or code, and do not generate hypothetical code. "
        f"Verified files: {files_list_str}"
    )
    user_prompt = (
        f"QUESTION:\n{truncate_text(state['question'], settings.MAX_QUESTION_CHARS)}"
        f"\n\nVERIFIED REPO FILES:\n{files_list_str}\n\nCODE EXCERPTS:\n{context}"
    )
    resp = invoke_bounded(llm, [
        SystemMessage(content=system_prompt),
        HumanMessage(content=user_prompt),
    ])
    print("Reasoner node executed")
    return {"reasoning": resp.content}


def _clean_html_tags(text: str) -> str:
    """Normalize generated answers into clean, readable plain-text sections."""
    if not text:
        return ""
    # Convert <br>, <br/>, <br /> into standard newlines
    cleaned = re.sub(r"<br\s*/?>", "\n", text, flags=re.IGNORECASE)
    # Remove any other HTML tags
    cleaned = re.sub(r"</?[a-zA-Z0-9]+[^>]*>", "", cleaned)
    # Models occasionally escape Markdown markers; make headings and emphasis
    # readable even when a provider returns the escapes literally.
    cleaned = re.sub(r"\\([#*-])", r"\1", cleaned)
    cleaned = cleaned.replace("**", "")
    cleaned = re.sub(r"(?m)^\s*#{1,6}\s+", "", cleaned)
    cleaned = re.sub(r"(?m)\\\s*$", "", cleaned)
    return cleaned.strip()


def final_answer_node(state: AgentState) -> AgentState:
    llm = get_llm()
    retrieved = state.get("retrieved", [])
    actual_files = sorted(set(r["file_path"] for r in retrieved))
    files_list_str = ", ".join(f"`{f}`" for f in actual_files) if actual_files else "None"

    system_prompt = (
        "Provide a concise, accurate, grounded response. Use plain-text section "
        "titles (no # or ##) and no bold markers such as **. Use no HTML, "
        "invented files, or hypothetical code. Prefer bullets over tables. Cover "
        "Overview, Repository Files & Content, and Algorithms / Models Identified "
        f"when supported by these verified files: {files_list_str}"
    )
    user_prompt = (
        f"QUESTION:\n{truncate_text(state['question'], settings.MAX_QUESTION_CHARS)}\n\n"
        f"VERIFIED REPO FILES:\n{files_list_str}\n\n"
        f"ANALYSIS:\n{truncate_text(state.get('reasoning', ''), settings.MAX_REASONING_CHARS)}"
    )
    resp = invoke_bounded(llm, [SystemMessage(content=system_prompt), HumanMessage(content=user_prompt)])
    answer_text = _clean_html_tags(resp.content)
    print("Final Answer node executed")
    return {"answer": answer_text}



def build_graph():
    graph = StateGraph(AgentState)
    graph.add_node("planner", planner_node)
    graph.add_node("code_search", code_search_node)
    graph.add_node("reasoner", reasoner_node)
    graph.add_node("final_answer", final_answer_node)

    graph.add_edge(START, "planner")
    graph.add_edge("planner", "code_search")
    graph.add_edge("code_search", "reasoner")
    graph.add_edge("reasoner", "final_answer")
    graph.add_edge("final_answer", END)

    return graph.compile()


_COMPILED_GRAPH = None


def get_graph():
    global _COMPILED_GRAPH
    if _COMPILED_GRAPH is None:
        _COMPILED_GRAPH = build_graph()
    return _COMPILED_GRAPH
