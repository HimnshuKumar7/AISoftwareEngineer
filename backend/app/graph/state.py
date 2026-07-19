from typing import TypedDict


class SourceRef(TypedDict):
    file_path: str
    start_line: int
    end_line: int
    symbol: str
    snippet: str


class AgentState(TypedDict, total=False):
    repo_id: str
    question: str
    plan: list[str]              # sub-questions / search queries from Planner
    retrieved: list[SourceRef]   # deduped chunks from Code Search
    reasoning: str                # scratchpad analysis from Reasoner
    answer: str                   # final answer from Final Answer node
