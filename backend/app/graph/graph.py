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

from app.graph.state import AgentState
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
    prompt = (
        "You are the Planner for a codebase Q&A agent. Given the user's "
        "question about a code repository, produce 2 to 4 focused search "
        "queries (keywords / phrases) that would help retrieve the most "
        "relevant code chunks from a vector database. "
        "Respond with ONLY a JSON array of strings, nothing else.\n\n"
        f"Question: {state['question']}"
    )
    resp = llm.invoke([SystemMessage(content=prompt)])
    queries = _extract_json_list(resp.content)
    if not queries:
        queries = [state["question"]]
    return {"plan": queries}


def code_search_node(state: AgentState) -> AgentState:
    seen = set()
    retrieved = []
    for query in state.get("plan") or [state["question"]]:
        for doc in search(state["repo_id"], query):
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
    return {"retrieved": retrieved[:15]}


def reasoner_node(state: AgentState) -> AgentState:
    llm = get_llm()
    context = "\n\n---\n\n".join(
        f"File: {r['file_path']} (lines {r['start_line']}-{r['end_line']}, "
        f"symbol: {r['symbol']})\n{r['snippet']}"
        for r in state.get("retrieved", [])
    ) or "No relevant code was retrieved."

    prompt = (
        "You are a senior software engineer analyzing a codebase. Using ONLY "
        "the code excerpts below, reason step by step about how they answer "
        "the user's question. Note relevant file paths and function/class "
        "names. If the excerpts are insufficient, say so explicitly.\n\n"
        f"QUESTION:\n{state['question']}\n\nCODE EXCERPTS:\n{context}"
    )
    resp = llm.invoke([SystemMessage(content=prompt)])
    return {"reasoning": resp.content}


def final_answer_node(state: AgentState) -> AgentState:
    llm = get_llm()
    prompt = (
        "You are an AI Software Engineer assistant. Write the final answer "
        "for the user based on the analysis below. Be clear and concise, "
        "use markdown, reference specific file paths and function/class "
        "names (e.g. `auth/jwt.py:42`) so the user can navigate the repo. "
        "Do not mention 'the analysis' or your internal process.\n\n"
        f"QUESTION:\n{state['question']}\n\nANALYSIS:\n{state.get('reasoning', '')}"
    )
    resp = llm.invoke([SystemMessage(content=prompt)])
    return {"answer": resp.content}


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
