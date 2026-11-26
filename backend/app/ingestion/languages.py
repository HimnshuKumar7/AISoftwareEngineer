"""Language registry for Tree-sitter parsing.

Every grammar is loaded from its own PyPI wheel (tree-sitter-python, tree-sitter-java, ...), which
bundles the compiled grammar. This is deliberate: grammar bundles that download parsers at runtime
cannot be relied on in Render's ephemeral, build-then-run environment.
"""
from __future__ import annotations

import importlib
import logging
from dataclasses import dataclass, field
from functools import lru_cache
from typing import Dict, FrozenSet, Optional, Tuple

from tree_sitter import Language, Parser

log = logging.getLogger(__name__)


@dataclass(frozen=True)
class LangSpec:
    name: str  # label stored in chunk metadata
    module: str  # python module providing the grammar
    func: str  # function in that module returning the language pointer
    extensions: Tuple[str, ...]
    function_types: FrozenSet[str] = frozenset()  # function-like (becomes "method" when nested in a class)
    method_types: FrozenSet[str] = frozenset()  # always methods
    class_types: FrozenSet[str] = frozenset()  # class / struct / interface / trait / impl / module
    wrapper_types: FrozenSet[str] = frozenset()  # parents whose range should include the definition (decorators/export)
    var_function_types: FrozenSet[str] = frozenset()  # `const f = () => {}` style declarations
    comment_prefixes: Tuple[str, ...] = ("//", "/*", "*", "#")


def _fs(*items: str) -> FrozenSet[str]:
    return frozenset(items)


_JS_FUNCS = _fs("function_declaration", "generator_function_declaration")
_JS_VARDECL = _fs("lexical_declaration", "variable_declaration")

SPECS: Tuple[LangSpec, ...] = (
    LangSpec("python", "tree_sitter_python", "language", (".py", ".pyi"),
             function_types=_fs("function_definition"), class_types=_fs("class_definition"),
             wrapper_types=_fs("decorated_definition"), comment_prefixes=("#",)),
    LangSpec("javascript", "tree_sitter_javascript", "language", (".js", ".jsx", ".mjs", ".cjs"),
             function_types=_JS_FUNCS, method_types=_fs("method_definition"), class_types=_fs("class_declaration"),
             wrapper_types=_fs("export_statement"), var_function_types=_JS_VARDECL),
    LangSpec("typescript", "tree_sitter_typescript", "language_typescript", (".ts", ".mts", ".cts"),
             function_types=_JS_FUNCS, method_types=_fs("method_definition"),
             class_types=_fs("class_declaration", "abstract_class_declaration", "interface_declaration", "enum_declaration"),
             wrapper_types=_fs("export_statement"), var_function_types=_JS_VARDECL),
    LangSpec("tsx", "tree_sitter_typescript", "language_tsx", (".tsx",),
             function_types=_JS_FUNCS, method_types=_fs("method_definition"),
             class_types=_fs("class_declaration", "abstract_class_declaration", "interface_declaration", "enum_declaration"),
             wrapper_types=_fs("export_statement"), var_function_types=_JS_VARDECL),
    LangSpec("java", "tree_sitter_java", "language", (".java",),
             method_types=_fs("method_declaration", "constructor_declaration"),
             class_types=_fs("class_declaration", "interface_declaration", "enum_declaration",
                             "record_declaration", "annotation_type_declaration")),
    LangSpec("go", "tree_sitter_go", "language", (".go",),
             function_types=_fs("function_declaration"), method_types=_fs("method_declaration"),
             class_types=_fs("type_declaration")),
    LangSpec("rust", "tree_sitter_rust", "language", (".rs",),
             function_types=_fs("function_item"),
             class_types=_fs("struct_item", "enum_item", "trait_item", "impl_item", "union_item"),
             comment_prefixes=("//", "///", "//!", "/*", "*")),
    LangSpec("c", "tree_sitter_c", "language", (".c", ".h"),
             function_types=_fs("function_definition"),
             class_types=_fs("struct_specifier", "union_specifier", "enum_specifier")),
    LangSpec("cpp", "tree_sitter_cpp", "language", (".cpp", ".cc", ".cxx", ".hpp", ".hh", ".hxx"),
             function_types=_fs("function_definition"),
             class_types=_fs("class_specifier", "struct_specifier", "union_specifier"),
             wrapper_types=_fs("template_declaration")),
    LangSpec("c_sharp", "tree_sitter_c_sharp", "language", (".cs",),
             function_types=_fs("local_function_statement"),
             method_types=_fs("method_declaration", "constructor_declaration", "destructor_declaration",
                              "operator_declaration"),
             class_types=_fs("class_declaration", "interface_declaration", "struct_declaration",
                             "record_declaration", "enum_declaration")),
    LangSpec("ruby", "tree_sitter_ruby", "language", (".rb",),
             function_types=_fs("method", "singleton_method"), class_types=_fs("class", "module"),
             comment_prefixes=("#",)),
    LangSpec("php", "tree_sitter_php", "language_php", (".php",),
             function_types=_fs("function_definition"), method_types=_fs("method_declaration"),
             class_types=_fs("class_declaration", "interface_declaration", "trait_declaration", "enum_declaration")),
    LangSpec("kotlin", "tree_sitter_kotlin", "language", (".kt", ".kts"),
             function_types=_fs("function_declaration"), class_types=_fs("class_declaration", "object_declaration")),
    LangSpec("swift", "tree_sitter_swift", "language", (".swift",),
             function_types=_fs("function_declaration", "init_declaration", "deinit_declaration"),
             class_types=_fs("class_declaration", "protocol_declaration")),
    LangSpec("scala", "tree_sitter_scala", "language", (".scala", ".sc"),
             function_types=_fs("function_definition", "function_declaration"),
             class_types=_fs("class_definition", "object_definition", "trait_definition", "enum_definition")),
    LangSpec("bash", "tree_sitter_bash", "language", (".sh", ".bash"),
             function_types=_fs("function_definition"), comment_prefixes=("#",)),
    LangSpec("lua", "tree_sitter_lua", "language", (".lua",),
             function_types=_fs("function_declaration"), comment_prefixes=("--",)),
)

SPEC_BY_NAME: Dict[str, LangSpec] = {s.name: s for s in SPECS}
EXT_TO_SPEC: Dict[str, LangSpec] = {ext: s for s in SPECS for ext in s.extensions}

# Prose that is useful for repository Q&A (README, docs). Chunked by line windows, not by AST.
DOC_EXTENSIONS = (".md", ".mdx", ".rst", ".txt")
DOC_LANGUAGE = "markdown"


def spec_for_path(path: str) -> Optional[LangSpec]:
    lower = path.lower()
    dot = lower.rfind(".")
    if dot == -1:
        return None
    return EXT_TO_SPEC.get(lower[dot:])


NOTEBOOK_EXTENSION = ".ipynb"


def is_notebook_path(path: str) -> bool:
    return path.lower().endswith(NOTEBOOK_EXTENSION)


def is_doc_path(path: str) -> bool:
    return path.lower().endswith(DOC_EXTENSIONS)


@lru_cache(maxsize=None)
def get_language(spec_name: str) -> Language:
    spec = SPEC_BY_NAME[spec_name]
    mod = importlib.import_module(spec.module)
    return Language(getattr(mod, spec.func)())


_parsers: Dict[str, Parser] = {}


def get_parser(spec_name: str) -> Parser:
    parser = _parsers.get(spec_name)
    if parser is None:
        parser = Parser(get_language(spec_name))
        _parsers[spec_name] = parser
    return parser


def supported_languages() -> Tuple[str, ...]:
    return tuple(s.name for s in SPECS)
