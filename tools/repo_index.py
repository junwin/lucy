#!/usr/bin/env python3
"""
Generate a compact structural index of a Python repository.

The index is intended primarily for coding agents: it provides enough
information to locate relevant source without requiring the agent to read
the entire repository.

Usage:
    python tools/repo_index.py
    python tools/repo_index.py --root . --output repo_index.md
"""

from __future__ import annotations

import argparse
import ast
import subprocess
from dataclasses import dataclass, field
from pathlib import Path


DEFAULT_EXCLUDES = {
    ".git",
    ".venv",
    "venv",
    "__pycache__",
    ".pytest_cache",
    ".mypy_cache",
    ".ruff_cache",
    "node_modules",
    "build",
    "dist",
}


@dataclass
class ClassInfo:
    name: str
    line: int
    bases: list[str] = field(default_factory=list)
    methods: list[str] = field(default_factory=list)


@dataclass
class ModuleInfo:
    path: Path
    docstring: str | None = None
    imports: list[str] = field(default_factory=list)
    classes: list[ClassInfo] = field(default_factory=list)
    functions: list[tuple[str, int]] = field(default_factory=list)


def expr_name(node: ast.AST) -> str:
    """Return a readable representation of a Python expression."""
    try:
        return ast.unparse(node)
    except Exception:
        return "?"


def format_arguments(args: ast.arguments) -> str:
    """Return a compact representation of function arguments."""
    parts: list[str] = []

    positional = list(args.posonlyargs) + list(args.args)
    defaults_offset = len(positional) - len(args.defaults)

    for index, arg in enumerate(positional):
        text = arg.arg

        if arg.annotation:
            text += f": {expr_name(arg.annotation)}"

        if index >= defaults_offset:
            default = args.defaults[index - defaults_offset]
            text += f" = {expr_name(default)}"

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

    if not docstring:
        return None

    return docstring.splitlines()[0].strip()


def parse_module(path: Path) -> ModuleInfo | None:
    try:
        source = path.read_text(encoding="utf-8")
        tree = ast.parse(source, filename=str(path))
    except (UnicodeDecodeError, SyntaxError, OSError) as exc:
        print(f"warning: unable to parse {path}: {exc}")
        return None

    info = ModuleInfo(
        path=path,
        docstring=first_docstring_line(tree),
    )

    for node in tree.body:
        if isinstance(node, ast.Import):
            for alias in node.names:
                info.imports.append(alias.name)

        elif isinstance(node, ast.ImportFrom):
            module = "." * node.level + (node.module or "")
            names = ", ".join(alias.name for alias in node.names)
            info.imports.append(f"{module}: {names}")

        elif isinstance(node, ast.ClassDef):
            class_info = ClassInfo(
                name=node.name,
                line=node.lineno,
                bases=[expr_name(base) for base in node.bases],
            )

            for child in node.body:
                if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    class_info.methods.append(
                        f"{function_signature(child)} [line {child.lineno}]"
                    )

            info.classes.append(class_info)

        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            info.functions.append(
                (function_signature(node), node.lineno)
            )

    info.imports = sorted(set(info.imports))

    return info


def should_exclude(path: Path, root: Path) -> bool:
    try:
        relative = path.relative_to(root)
    except ValueError:
        return True

    return any(part in DEFAULT_EXCLUDES for part in relative.parts)


def find_python_files(root: Path) -> list[Path]:
    files = [
        path
        for path in root.rglob("*.py")
        if not should_exclude(path, root)
    ]

    return sorted(files, key=lambda p: str(p.relative_to(root)))


def git_commit(root: Path) -> str | None:
    try:
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=root,
            capture_output=True,
            text=True,
            check=True,
        )
        return result.stdout.strip()
    except (subprocess.CalledProcessError, FileNotFoundError):
        return None


def render_module(info: ModuleInfo, root: Path) -> list[str]:
    relative = info.path.relative_to(root)

    lines = [
        f"## `{relative}`",
        "",
    ]

    if info.docstring:
        lines.extend([
            f"> {info.docstring}",
            "",
        ])

    if info.imports:
        lines.append("**Imports**")
        lines.append("")
        for item in info.imports:
            lines.append(f"- `{item}`")
        lines.append("")

    if info.classes:
        lines.append("**Classes**")
        lines.append("")

        for cls in info.classes:
            bases = f"({', '.join(cls.bases)})" if cls.bases else ""

            lines.append(
                f"- `{cls.name}{bases}` — line {cls.line}"
            )

            for method in cls.methods:
                lines.append(f"  - `{method}`")

        lines.append("")

    if info.functions:
        lines.append("**Functions**")
        lines.append("")

        for signature, line in info.functions:
            lines.append(f"- `{signature}` — line {line}")

        lines.append("")

    return lines


def generate_index(root: Path) -> str:
    root = root.resolve()
    commit = git_commit(root)

    files = find_python_files(root)

    lines = [
        "# Repository Index",
        "",
        f"Repository: `{root.name}`",
        f"Python files: {len(files)}",
    ]

    if commit:
        lines.append(f"Git commit: `{commit}`")

    lines.extend([
        "",
        "---",
        "",
    ])

    parsed_count = 0

    for path in files:
        info = parse_module(path)

        if info is None:
            continue

        parsed_count += 1
        lines.extend(render_module(info, root))

    lines.extend([
        "---",
        "",
        f"Indexed {parsed_count} Python files.",
        "",
    ])

    return "\n".join(lines)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Generate a compact structural index of a Python repository."
    )

    parser.add_argument(
        "--root",
        type=Path,
        default=Path("."),
        help="Repository root (default: current directory)",
    )

    parser.add_argument(
        "--output",
        type=Path,
        default=Path("repo_index.md"),
        help="Output Markdown file (default: repo_index.md)",
    )

    return parser.parse_args()


def main() -> None:
    args = parse_args()

    root = args.root.resolve()
    output = args.output

    if not output.is_absolute():
        output = root / output

    index = generate_index(root)

    output.write_text(index, encoding="utf-8")

    print(f"Repository index written to {output}")


if __name__ == "__main__":
    main()