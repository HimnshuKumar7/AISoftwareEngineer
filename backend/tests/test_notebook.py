"""Jupyter notebook (.ipynb) extraction: cell parsing, exact line ranges in the flattened view."""
import json

from app.ingestion.chunker import chunk_files, chunk_source, notebook_to_text
from app.ingestion.walker import WalkStats, walk_repo


def nb(cells, language="python", fmt=4):
    meta = {"kernelspec": {"language": language, "name": language}, "language_info": {"name": language}}
    return json.dumps({"nbformat": fmt, "metadata": meta, "cells": cells}).encode()


def code(src):
    return {"cell_type": "code", "source": src.splitlines(True), "outputs": [
        {"output_type": "display_data", "data": {"image/png": "iVBORw0KGgo" + "A" * 5000}}], "execution_count": 1}


def md(src):
    return {"cell_type": "markdown", "source": src.splitlines(True)}


SAMPLE = nb([
    md("# Data cleaning\n\nThis notebook loads the raw sales data and removes invalid rows.\n"),
    code("%matplotlib inline\n!pip install pandas\nimport pandas as pd\nDATA = 'sales.csv'\n"),
    code("def clean(df):\n    \"\"\"Drop rows without an id.\"\"\"\n    df = df.dropna(subset=['id'])\n    return df\n\n"
         "class Loader:\n    def read(self, path):\n        return pd.read_csv(path)\n"),
    code("df = Loader().read(DATA)\nprint(clean(df).shape)"),
    {"cell_type": "code", "source": "", "outputs": []},  # empty cell is skipped
])


def test_view_and_chunks_match_exactly():
    lines, cells = notebook_to_text(SAMPLE)
    assert [c["type"] for c in cells] == ["markdown", "code", "code", "code"]
    chunks = chunk_source("analysis/clean.ipynb", SAMPLE)
    assert chunks
    for c in chunks:
        assert 1 <= c.start_line <= c.end_line <= len(lines)
        assert c.code == "\n".join(lines[c.start_line - 1:c.end_line]), (c.kind, c.qualified_name)
        assert c.content_hash


def test_definitions_are_extracted_with_cell_context():
    chunks = chunk_source("n.ipynb", SAMPLE)
    got = {(c.kind, c.qualified_name) for c in chunks}
    assert ("function", "cell 3: clean") in got
    assert ("class", "cell 3: Loader") in got
    assert ("method", "cell 3: Loader.read") in got
    assert any(c.kind == "doc" and c.name == "Data cleaning" for c in chunks)
    # a short top-level cell is still indexed (notebook cells are small)
    assert any(c.kind == "module" and "Loader().read(DATA)" in c.code for c in chunks)


def test_magics_do_not_break_parsing_and_text_is_original():
    chunks = chunk_source("n.ipynb", SAMPLE)
    first = next(c for c in chunks if "import pandas" in c.code)
    assert "%matplotlib inline" in first.code and "!pip install pandas" in first.code  # original text kept
    assert first.language == "python"


def test_outputs_are_never_indexed():
    for c in chunk_source("n.ipynb", SAMPLE):
        assert "iVBOR" not in c.code and "image/png" not in c.code


def test_other_kernels_and_nbformat3():
    r = nb([code("x <- c(1, 2, 3)\nmean(x)\n")], language="R")
    (c,) = chunk_source("r.ipynb", r)
    assert c.kind == "cell" and c.language == "r"
    js = nb([code("function add(a, b) {\n  return a + b;\n}\n")], language="javascript")
    assert any(c.kind == "function" and c.language == "javascript" for c in chunk_source("j.ipynb", js))
    legacy = json.dumps({"nbformat": 3, "metadata": {}, "worksheets": [{"cells": [
        {"cell_type": "code", "language": "python", "input": ["def f():\n", "    return 1\n"], "outputs": []}]}]}).encode()
    assert any(c.kind == "function" and c.name == "f" for c in chunk_source("old.ipynb", legacy))


def test_source_as_string_and_crlf():
    raw = nb([{"cell_type": "code", "source": "def g(x):\r\n    return x * 2\r\n", "outputs": []}])
    assert any(c.name == "g" for c in chunk_source("s.ipynb", raw))


def test_invalid_and_empty_notebooks_do_not_abort_indexing():
    assert chunk_source("e.ipynb", b"   ") == []
    assert chunk_source("e.ipynb", nb([])) == []
    files = [("bad.ipynb", b"{not json"), ("ok.py", b"def f():\n    return 1\n    # padding\n    pass\n")]
    out = list(chunk_files(files))  # bad notebook is logged and skipped, other files still indexed
    assert [c.path for c in out] == ["ok.py"]


def test_walker_picks_up_notebooks_and_skips_checkpoints(tmp_path):
    (tmp_path / "nb").mkdir()
    (tmp_path / "nb" / "a.ipynb").write_bytes(SAMPLE)
    (tmp_path / ".ipynb_checkpoints").mkdir()
    (tmp_path / ".ipynb_checkpoints" / "a-checkpoint.ipynb").write_bytes(SAMPLE)
    big = nb([code("x = 1\n" * 3)]) + b" " * (300 * 1024)  # > 256 KB source limit, < notebook limit
    (tmp_path / "nb" / "big.ipynb").write_bytes(big)
    stats = WalkStats()
    got = [p for p, _ in walk_repo(tmp_path, 100, 256, stats)]
    assert sorted(got) == ["nb/a.ipynb", "nb/big.ipynb"]
    assert stats.languages == {"jupyter": 2}
