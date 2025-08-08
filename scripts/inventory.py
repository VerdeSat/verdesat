#!/usr/bin/env python3
"""
inventory.py — Generate a MODULES.md overview of the repo.

Usage:
    poetry run python scripts/inventory.py           # print to stdout
    poetry run python scripts/inventory.py --write   # write to docs/MODULES.md
    poetry run python scripts/inventory.py --root . --package verdesat --exclude tests .venv

What it does:
  - Walks the Python package (default: "verdesat/") and collects modules,
    top-level classes and functions, and the first line of their docstrings.
  - Outputs a Markdown document suitable for docs/MODULES.md.

Limitations:
  - Only inspects top-level classes/functions (no nested method listing).
  - Skips files in excluded directories or names starting with underscore.
"""

from __future__ import annotations

import argparse
import ast
import datetime as dt
from pathlib import Path
from typing import Dict, List, Tuple

DEFAULT_PACKAGE = "verdesat"
DEFAULT_OUTPUT = Path("docs") / "MODULES.md"
DEFAULT_EXCLUDES = {
    ".git",
    ".venv",
    "venv",
    "__pycache__",
    "build",
    "dist",
    ".mypy_cache",
    ".pytest_cache",
    "node_modules",
    "notebooks",
}


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser()
    p.add_argument("--root", type=Path, default=Path("."), help="Repo root")
    p.add_argument(
        "--package",
        type=str,
        default=DEFAULT_PACKAGE,
        help="Top-level package to index",
    )
    p.add_argument(
        "--write",
        action="store_true",
        help="Write to docs/MODULES.md instead of stdout",
    )
    p.add_argument(
        "--output",
        type=Path,
        default=DEFAULT_OUTPUT,
        help="Path to write (when --write)",
    )
    p.add_argument(
        "--exclude",
        nargs="*",
        default=list(DEFAULT_EXCLUDES),
        help="Directories to exclude",
    )
    return p.parse_args()


def should_skip(path: Path, excludes: set[str]) -> bool:
    parts = set(path.parts)
    return any(ex in parts for ex in excludes)


def module_name(pkg_root: Path, file: Path) -> str:
    # e.g., verdesat/webapp/app.py -> webapp.app ; __init__.py -> package path
    rel = file.relative_to(pkg_root)
    parts = list(rel.parts)
    if parts[-1] == "__init__.py":
        parts = parts[:-1]
    else:
        parts[-1] = Path(parts[-1]).stem
    return ".".join([pkg_root.name] + parts)


def extract_symbols(
    py_file: Path,
) -> tuple[str, list[tuple[str, str]], list[tuple[str, str]]]:
    """Return (module_doc, classes, functions) for a file."""
    try:
        text = py_file.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        return "", [], []
    try:
        tree = ast.parse(text)
    except SyntaxError:
        return "", [], []
    mod_doc = (ast.get_docstring(tree) or "").strip().splitlines()
    mod_doc_line = mod_doc[0] if mod_doc else ""

    classes: list[tuple[str, str]] = []
    functions: list[tuple[str, str]] = []
    for node in tree.body:
        if isinstance(node, ast.ClassDef):
            if node.name.startswith("_"):
                continue
            doc = (ast.get_docstring(node) or "").strip().splitlines()
            classes.append((node.name, doc[0] if doc else ""))
        elif isinstance(node, ast.FunctionDef):
            if node.name.startswith("_"):
                continue
            doc = (ast.get_docstring(node) or "").strip().splitlines()
            functions.append((node.name, doc[0] if doc else ""))
    return mod_doc_line, classes, functions


def render_markdown(collected: Dict[str, Dict]) -> str:
    now = dt.datetime.utcnow().isoformat(timespec="seconds") + "Z"
    lines: List[str] = []
    lines.append("# MODULES — Auto-generated overview")
    lines.append("")
    lines.append(f"_Generated: {now}_")
    lines.append("")
    for mod, info in sorted(collected.items()):
        lines.append(f"## `{mod}`")
        if info["doc"]:
            lines.append(f"> {info['doc']}")
        if info["classes"]:
            lines.append("**Classes**")
            for name, doc in info["classes"]:
                lines.append(f"- `{name}` — {doc}")
        if info["functions"]:
            if info["classes"]:
                lines.append("")
            lines.append("**Functions**")
            for name, doc in info["functions"]:
                lines.append(f"- `{name}` — {doc}")
        lines.append("")
    return "\n".join(lines).strip() + "\n"


def main() -> None:
    args = parse_args()
    root: Path = args.root.resolve()
    pkg_root = (root / args.package).resolve()
    excludes = set(args.exclude)

    if not pkg_root.exists():
        raise SystemExit(f"Package root not found: {pkg_root}")

    collected: Dict[str, Dict] = {}
    for py in pkg_root.rglob("*.py"):
        if should_skip(py, excludes):
            continue
        # allow __init__.py (module docs), but skip private modules like _foo.py
        if py.name.startswith("_") and py.name != "__init__.py":
            continue
        mod = module_name(pkg_root, py)
        mod_doc, classes, functions = extract_symbols(py)
        collected[mod] = {"doc": mod_doc, "classes": classes, "functions": functions}

    md = render_markdown(collected)
    if args.write:
        out = (root / args.output).resolve()
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(md, encoding="utf-8")
        print(f"Wrote {out}")
    else:
        print(md)


if __name__ == "__main__":
    main()
