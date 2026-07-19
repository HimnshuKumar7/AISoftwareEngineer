"""
Parse source files into semantically meaningful chunks (functions, classes,
methods) using tree-sitter. Falls back to plain-text windowing for languages
without a grammar, or if parsing fails for any reason.
"""
from dataclasses import dataclass
from pathlib import Path

from tree_sitter_languages import get_parser

EXT_TO_LANGUAGE = {
    ".py": "python",
    ".js": "javascript",
    ".jsx": "javascript",
    ".ts": "typescript",
    ".tsx": "tsx",
    ".java": "java",
    ".go": "go",
    ".rb": "ruby",
    ".rs": "rust",
    ".c": "c",
    ".h": "c",
    ".cpp": "cpp",
    ".hpp": "cpp",
    ".cs": "c_sharp",
    ".php": "php",
}

# Node types that represent a "definition" worth its own chunk, per language.
DEFINITION_NODE_TYPES = {
    "python": {"function_definition", "class_definition"},
    "javascript": {"function_declaration", "class_declaration", "method_definition"},
    "typescript": {"function_declaration", "class_declaration", "method_definition", "interface_declaration"},
    "tsx": {"function_declaration", "class_declaration", "method_definition", "interface_declaration"},
    "java": {"method_declaration", "class_declaration", "interface_declaration"},
    "go": {"function_declaration", "method_declaration", "type_declaration"},
    "ruby": {"method", "class"},
    "rust": {"function_item", "impl_item", "struct_item", "enum_item"},
    "c": {"function_definition", "struct_specifier"},
    "cpp": {"function_definition", "class_specifier", "struct_specifier"},
    "c_sharp": {"method_declaration", "class_declaration"},
    "php": {"function_definition", "class_declaration", "method_declaration"},
}

NAME_FIELD_CANDIDATES = ("name", "identifier")


@dataclass
class CodeChunk:
    file_path: str
    start_line: int
    end_line: int
    symbol: str | None
    node_type: str
    text: str


def _extract_name(node, source_bytes: bytes) -> str | None:
    for child in node.children:
        if child.type in ("identifier", "type_identifier", "property_identifier"):
            return source_bytes[child.start_byte:child.end_byte].decode("utf-8", "ignore")
    return None


def parse_file_to_chunks(path: Path, repo_root: Path) -> list[CodeChunk]:
    rel_path = str(path.relative_to(repo_root)).replace("\\", "/")
    raw = path.read_bytes()
    lang = EXT_TO_LANGUAGE.get(path.suffix.lower())

    if lang is None:
        return _fallback_chunks(rel_path, raw)

    try:
        parser = get_parser(lang)
        tree = parser.parse(raw)
    except Exception:
        return _fallback_chunks(rel_path, raw)

    interesting_types = DEFINITION_NODE_TYPES.get(lang, set())
    chunks: list[CodeChunk] = []

    def walk(node, depth=0):
        if node.type in interesting_types:
            text = raw[node.start_byte:node.end_byte].decode("utf-8", "ignore")
            if text.strip():
                chunks.append(CodeChunk(
                    file_path=rel_path,
                    start_line=node.start_point[0] + 1,
                    end_line=node.end_point[0] + 1,
                    symbol=_extract_name(node, raw),
                    node_type=node.type,
                    text=text,
                ))
            # still recurse to catch nested functions/methods
        for child in node.children:
            walk(child, depth + 1)

    walk(tree.root_node)

    if not chunks:
        # No definitions found (e.g. config/script file) -> whole-file fallback
        return _fallback_chunks(rel_path, raw)

    return chunks


def _fallback_chunks(rel_path: str, raw: bytes, window_lines: int = 60) -> list[CodeChunk]:
    """Simple line-window chunking for files with no tree-sitter grammar."""
    text = raw.decode("utf-8", "ignore")
    lines = text.splitlines()
    chunks = []
    for i in range(0, len(lines), window_lines):
        window = lines[i:i + window_lines]
        body = "\n".join(window)
        if not body.strip():
            continue
        chunks.append(CodeChunk(
            file_path=rel_path,
            start_line=i + 1,
            end_line=min(i + window_lines, len(lines)),
            symbol=None,
            node_type="text_window",
            text=body,
        ))
    return chunks
