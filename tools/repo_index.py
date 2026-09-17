#!/usr/bin/env python3
"""Generate compact and detailed structural views of a Python repository."""

from __future__ import annotations

import argparse
import ast
import subprocess
from dataclasses import dataclass, field
from pathlib import Path


DEFAULT_EXCLUDES = {
    ".git", ".venv", "venv", "__pycache__", ".pytest_cache",
    ".mypy_cache", ".ruff_cache", "node_modules", "build", "dist",
}


@dataclass
class ClassInfo:
    name: str
    line: int
    bases: list[str] = field(default_factory=list)
    methods: list[tuple[str, int]] = field(default_factory=list)


@dataclass
class ModuleInfo:
    path: Path
    docstring: str | None = None
    imports: list[str] = field(default_factory=list)
    classes: list[ClassInfo] = field(default_factory=list)
    functions: list[tuple[str, int]] = field(default_factory=list)


def expr_name(node: ast.AST) -> str:
    try:
        return ast.unparse(node)
    except Exception:
        return "?"


def format_arguments(args: ast.arguments) -> str:
    parts: list[str] = []
    positional = list(args.posonlyargs) + list(args.args)
    defaults_offset = len(positional) - len(args.defaults)
    for index, arg in enumerate(positional):
        text = arg.arg
        if arg.annotation:
            text += f": {expr_name(arg.annotation)}"
        if index >= defaults_offset:
            text += f" = {expr_name(args.defaults[index - defaults_offset])}"
        parts.append(text)
    if args.vararg:
        text = f"*{args.vararg.arg}"
        if args.vararg.annotation:
            text += f": {expr_name(args.vararg.annotation)}"
        parts.append(text)
    elif args.kwonlyargs:
        parts.append("*")
    for arg, default in zip(args.kwonlyargs, args.kw_defaults):
        text = arg.arg
        if arg.annotation:
            text += f": {expr_name(arg.annotation)}"
        if default is not None:
            text += f" = {expr_name(default)}"
        parts.append(text)
    if args.kwarg:
        text = f"**{args.kwarg.arg}"
        if args.kwarg.annotation:
            text += f": {expr_name(args.kwarg.annotation)}"
        parts.append(text)
    return ", ".join(parts)


def function_signature(node: ast.FunctionDef | ast.AsyncFunctionDef) -> str:
    prefix = "async " if isinstance(node, ast.AsyncFunctionDef) else ""
    signature = f"{prefix}{node.name}({format_arguments(node.args)})"
    if node.returns:
        signature += f" -> {expr_name(node.returns)}"
    return signature


def first_docstring_line(node: ast.AST) -> str | None:
    docstring = ast.get_docstring(node, clean=True)
    return docstring.splitlines()[0].strip() if docstring else None


def parse_module(path: Path) -> ModuleInfo | None:
    try:
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    except (UnicodeDecodeError, SyntaxError, OSError) as exc:
        print(f"warning: unable to parse {path}: {exc}")
        return None
    info = ModuleInfo(path=path, docstring=first_docstring_line(tree))
    for node in tree.body:
        if isinstance(node, ast.Import):
            info.imports.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            module = "." * node.level + (node.module or "")
            names = ", ".join(alias.name for alias in node.names)
            info.imports.append(f"{module}: {names}")
        elif isinstance(node, ast.ClassDef):
            cls = ClassInfo(node.name, node.lineno, [expr_name(b) for b in node.bases])
            for child in node.body:
                if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    cls.methods.append((function_signature(child), child.lineno))
            info.classes.append(cls)
        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            info.functions.append((function_signature(node), node.lineno))
    info.imports = sorted(set(info.imports))
    return info


def should_exclude(path: Path, root: Path) -> bool:
    try:
        relative = path.relative_to(root)
    except ValueError:
        return True
    return any(part in DEFAULT_EXCLUDES for part in relative.parts)


def find_python_files(root: Path) -> list[Path]:
    return sorted(
        (p for p in root.rglob("*.py") if not should_exclude(p, root)),
        key=lambda p: str(p.relative_to(root)),
    )


def is_test_path(path: Path, root: Path) -> bool:
    """Return True for conventional test files/directories."""
    relative = path.relative_to(root)
    return "tests" in relative.parts or relative.name.startswith("test_")


def git_commit(root: Path) -> str | None:
    try:
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"], cwd=root,
            capture_output=True, text=True, check=True,
        )
        return result.stdout.strip()
    except (subprocess.CalledProcessError, FileNotFoundError):
        return None


def render_map(modules: list[ModuleInfo], root: Path, commit: str | None) -> str:
    """Render a prompt-sized orientation map: production Python file paths only."""
    mapped = [info for info in modules if not is_test_path(info.path, root)]
    lines = [
        "# Repository Map", "", f"Repository: `{root.name}`",
        f"Python files: {len(mapped)} (tests excluded)",
    ]
    if commit:
        lines.append(f"Git commit: `{commit}`")
    lines.extend(["", "## Python files", ""])
    lines.extend(f"- `{info.path.relative_to(root)}`" for info in mapped)
    lines.append("")
    return "\n".join(lines)


def render_index(modules: list[ModuleInfo], root: Path, commit: str | None) -> str:
    lines = [
        "# Repository Index", "", f"Repository: `{root.name}`",
        f"Python files: {len(modules)}",
    ]
    if commit:
        lines.append(f"Git commit: `{commit}`")
    lines.extend(["", "---", ""])
    for info in modules:
        lines.extend([f"## `{info.path.relative_to(root)}`", ""])
        if info.docstring:
            lines.extend([f"> {info.docstring}", ""])
        if info.imports:
            lines.extend(["**Imports**", ""])
            lines.extend(f"- `{item}`" for item in info.imports)
            lines.append("")
        if info.classes:
            lines.extend(["**Classes**", ""])
            for cls in info.classes:
                bases = f"({', '.join(cls.bases)})" if cls.bases else ""
                lines.append(f"- `{cls.name}{bases}` — line {cls.line}")
                for signature, line in cls.methods:
                    lines.append(f"  - `{signature}` — line {line}")
            lines.append("")
        if info.functions:
            lines.extend(["**Functions**", ""])
            for signature, line in info.functions:
                lines.append(f"- `{signature}` — line {line}")
            lines.append("")
    return "\n".join(lines)


def estimate_tokens(text: str) -> int:
    return max(1, len(text) // 4)


def print_stats(name: str, text: str) -> None:
    print(
        f"{name:20} {len(text):>10,} chars  "
        f"{text.count(chr(10)) + 1:>7,} lines  "
        f"~{estimate_tokens(text):>8,} tokens"
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Generate compact and detailed structural repository views."
    )
    parser.add_argument("--root", type=Path, default=Path("."))
    parser.add_argument("--map-output", type=Path, default=Path("repo_map.md"))
    parser.add_argument("--index-output", type=Path, default=Path("repo_index.md"))
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    root = args.root.resolve()
    modules = []
    for path in find_python_files(root):
        info = parse_module(path)
        if info is not None:
            modules.append(info)
    commit = git_commit(root)
    repo_map = render_map(modules, root, commit)
    repo_index = render_index(modules, root, commit)
    map_output = args.map_output if args.map_output.is_absolute() else root / args.map_output
    index_output = args.index_output if args.index_output.is_absolute() else root / args.index_output
    map_output.write_text(repo_map, encoding="utf-8")
    index_output.write_text(repo_index, encoding="utf-8")
    print()
    print(f"Indexed {len(modules)} Python files")
    print(f"Git commit: {commit or 'unknown'}")
    print()
    print_stats("repo_map.md", repo_map)
    print_stats("repo_index.md", repo_index)
    print()
    print(f"Map:   {map_output}")
    print(f"Index: {index_output}")


if __name__ == "__main__":
    main()
