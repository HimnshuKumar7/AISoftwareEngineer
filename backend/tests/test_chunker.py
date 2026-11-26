"""Tree-sitter chunking across all supported languages, with exact line-range verification."""
import pytest

from app.ingestion.chunker import chunk_source
from app.ingestion.languages import SPECS, supported_languages

SAMPLES = {
    "python": ("m.py", '''import os

@decorator
def top(a, b):
    """Doc."""
    return a + b

class Foo(Base):
    x = 1

    def method(self, y):
        return y * 2

    async def other(self):
        pass
''', {("function", "top"), ("class", "Foo"), ("method", "Foo.method"), ("method", "Foo.other")}),
    "javascript": ("m.js", '''// Adds numbers
function add(a, b) {
  return a + b;
}

const mul = (a, b) => {
  return a * b;
};

export class Calc {
  constructor(x) { this.x = x; }
  double() {
    return this.x * 2;
  }
}
''', {("function", "add"), ("function", "mul"), ("class", "Calc"), ("method", "Calc.constructor"), ("method", "Calc.double")}),
    "typescript": ("m.ts", '''interface Shape { area(): number; }
export function area(s: Shape): number {
  return s.area();
}
class Circle implements Shape {
  area(): number { return 3.14; }
}
''', {("class", "Shape"), ("function", "area"), ("class", "Circle"), ("method", "Circle.area")}),
    "tsx": ("m.tsx", '''export const Hello = () => {
  return <div>hello</div>;
};
''', {("function", "Hello")}),
    "java": ("M.java", '''public class Greeter {
    private final String name;
    public Greeter(String name) { this.name = name; }
    public String greet() {
        return "Hello " + name;
    }
}
interface Speaker { void speak(); }
''', {("class", "Greeter"), ("method", "Greeter.Greeter"), ("method", "Greeter.greet"), ("class", "Speaker")}),
    "go": ("m.go", '''package main

type Server struct {
	Port int
}

func (s *Server) Start() error {
	return nil
}

func main() {
	s := &Server{}
	s.Start()
}
''', {("class", "Server"), ("method", "Start"), ("function", "main")}),
    "rust": ("m.rs", '''struct Point { x: i32 }

impl Point {
    fn new(x: i32) -> Self { Point { x } }
    fn get(&self) -> i32 { self.x }
}

fn helper() -> i32 { 1 }
''', {("class", "Point"), ("method", "Point.new"), ("method", "Point.get"), ("function", "helper")}),
    "c": ("m.c", '''struct Node { int v; };
int add(int a, int b) {
    return a + b;
}
''', {("class", "Node"), ("function", "add")}),
    "cpp": ("m.cpp", '''class Foo {
public:
  int bar() { return 1; }
};
int Foo_baz(int x) { return x; }
''', {("class", "Foo"), ("method", "Foo.bar"), ("function", "Foo_baz")}),
    "c_sharp": ("m.cs", '''namespace App {
  class Svc {
    public int Run() { return 1; }
  }
}
''', {("class", "Svc"), ("method", "Svc.Run")}),
    "ruby": ("m.rb", '''class Dog
  def bark
    puts "woof"
  end
end

def helper
  1
end
''', {("class", "Dog"), ("method", "Dog.bark"), ("function", "helper")}),
    "php": ("m.php", '''<?php
class User {
    public function name() { return "x"; }
}
function util() { return 1; }
''', {("class", "User"), ("method", "User.name"), ("function", "util")}),
    "kotlin": ("m.kt", '''class Box {
    fun open(): Int { return 1 }
}
fun top(): Int = 2
''', {("class", "Box"), ("method", "Box.open"), ("function", "top")}),
    "swift": ("m.swift", '''class Animal {
    func speak() -> String { return "x" }
}
func free() -> Int { return 1 }
''', {("class", "Animal"), ("method", "Animal.speak"), ("function", "free")}),
    "scala": ("m.scala", '''class Counter {
  def inc(x: Int): Int = x + 1
}
object Main {
  def main(args: Array[String]): Unit = {}
}
''', {("class", "Counter"), ("method", "Counter.inc"), ("class", "Main"), ("method", "Main.main")}),
    "bash": ("m.sh", '''greet() {
  echo "hi $1"
}
function other {
  echo x
}
''', {("function", "greet"), ("function", "other")}),
    "lua": ("m.lua", '''function add(a, b)
  return a + b
end
local function sub(a, b)
  return a - b
end
''', {("function", "add"), ("function", "sub")}),
}


def test_supports_at_least_13_languages():
    assert len(supported_languages()) >= 13
    assert {s.name for s in SPECS} >= set(SAMPLES) - {"tsx"} | {"tsx"}


@pytest.mark.parametrize("lang", sorted(SAMPLES))
def test_extracts_definitions_with_exact_lines(lang):
    path, src, expected = SAMPLES[lang]
    chunks = chunk_source(path, src.encode())
    got = {(c.kind, c.qualified_name) for c in chunks if c.kind != "module"}
    assert expected <= got, f"{lang}: missing {expected - got}; got {got}"

    lines = src.split("\n")
    for c in chunks:
        assert 1 <= c.start_line <= c.end_line <= len(lines)
        assert c.code == "\n".join(lines[c.start_line - 1:c.end_line]), f"{lang}: line range mismatch for {c.qualified_name}"
        assert c.content_hash


def test_every_language_is_covered_by_a_sample():
    assert {s.name for s in SPECS} == set(SAMPLES)


def test_python_decorator_and_comment_ranges():
    src = b"# helper docs\n@deco\ndef f():\n    return 1\n"
    (c,) = [c for c in chunk_source("x.py", src) if c.kind == "function"]
    assert (c.start_line, c.end_line) == (1, 4)  # decorator AND the directly attached comment are included

    detached = b"# unrelated note\n\n@deco\ndef f():\n    return 1\n"
    (c,) = [c for c in chunk_source("x.py", detached) if c.kind == "function"]
    assert (c.start_line, c.end_line) == (3, 5)  # a blank line detaches the comment

    js = b"/** Adds */\nexport function add(a,b){\n return a+b;\n}\n"
    (c,) = [c for c in chunk_source("x.js", js) if c.kind == "function"]
    assert c.start_line == 1 and c.code.startswith("/** Adds */") and "export function add" in c.code


def test_long_function_is_split_into_windows_with_exact_lines():
    body = "\n".join(f"    x{i} = {i}" for i in range(150))
    src = f"def big():\n{body}\n    return 0\n".encode()
    chunks = [c for c in chunk_source("big.py", src, max_lines=60) if c.kind == "function"]
    assert len(chunks) >= 3
    assert all(c.parts == len(chunks) for c in chunks)
    lines = src.decode().split("\n")
    for c in chunks:
        assert c.code == "\n".join(lines[c.start_line - 1:c.end_line])
    assert chunks[0].start_line == 1 and chunks[-1].end_line == 152  # full coverage
    for a, b in zip(chunks, chunks[1:]):
        assert b.start_line <= a.end_line + 1  # no gaps


def test_long_class_keeps_header_only_but_methods_are_separate():
    methods = "\n".join(f"    def m{i}(self):\n        return {i}\n" for i in range(40))
    src = f"class Big:\n    '''doc'''\n{methods}".encode()
    chunks = chunk_source("big.py", src, max_lines=60)
    cls = [c for c in chunks if c.kind == "class"]
    assert len(cls) == 1 and cls[0].truncated and cls[0].end_line - cls[0].start_line + 1 == 60
    assert len([c for c in chunks if c.kind == "method"]) == 40


def test_module_level_code_and_docs():
    src = b"import os\nimport sys\n\nCONFIG = {'a': 1, 'b': 2}\nprint('starting up the service now')\n\ndef f():\n    return 1\n"
    kinds = {c.kind for c in chunk_source("s.py", src)}
    assert {"module", "function"} <= kinds

    md = b"# Title\n\nSome introduction text for the project.\n\n## Install\n\nRun the installer.\n"
    (d,) = chunk_source("README.md", md)
    assert d.kind == "doc" and d.start_line == 1 and d.end_line == 7 and d.name == "Title"
    assert d.code.splitlines()[-1] == "Run the installer."


def test_unsupported_and_empty_files():
    assert chunk_source("a.bin", b"\x00\x01") == []
    assert chunk_source("a.py", b"   \n") == []
    assert chunk_source("Makefile", b"all:\n\techo hi\n") == []


def test_syntax_errors_do_not_crash():
    chunks = chunk_source("bad.py", b"def ok():\n    return 1\n\ndef broken(:\n    ???\n")
    assert any(c.qualified_name == "ok" for c in chunks)
