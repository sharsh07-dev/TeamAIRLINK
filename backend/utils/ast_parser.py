"""
backend/utils/ast_parser.py
============================
AST-based Python code analysis utilities.
Used by FailureClassifierAgent and RootCauseAgent for deep static analysis.
"""

from __future__ import annotations

import ast
import textwrap
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

from backend.utils.logger import logger


@dataclass
class ASTIssue:
    issue_type: str   # "SYNTAX", "IMPORT", "UNDEFINED_VAR", "TYPE_HINT", etc.
    file_path: str
    line: int
    col: int
    message: str
    node_type: str = ""


@dataclass
class FileImportGraph:
    file_path: str
    imports: List[str] = field(default_factory=list)
    from_imports: List[Tuple[str, str]] = field(default_factory=list)  # (module, name)
    defined_names: Set[str] = field(default_factory=set)
    called_names: Set[str] = field(default_factory=set)


class ASTParser:
    """
    Parses Python source files using the `ast` module to extract:
    - Syntax errors
    - Import issues
    - Undefined variable references
    - Type annotation errors
    - Dependency relationships between files
    """

    def __init__(self, repo_path: str):
        self.repo_path = Path(repo_path)

    # ─────────────────────────────────────────
    # Public API
    # ─────────────────────────────────────────

    def parse_file(self, file_path: str) -> Tuple[Optional[ast.AST], Optional[ASTIssue]]:
        """
        Parse a single Python file.
        Returns (AST tree, None) on success or (None, ASTIssue) on SyntaxError.
        """
        abs_path = Path(file_path)
        try:
            source = abs_path.read_text(encoding="utf-8", errors="replace")
            tree = ast.parse(source, filename=str(file_path))
            return tree, None
        except SyntaxError as e:
            issue = ASTIssue(
                issue_type="SYNTAX",
                file_path=file_path,
                line=e.lineno or 0,
                col=e.offset or 0,
                message=str(e.msg),
                node_type="SyntaxError",
            )
            logger.warning(f"[ASTParser] SyntaxError in {file_path}:{e.lineno} — {e.msg}")
            return None, issue
        except Exception as e:
            issue = ASTIssue(
                issue_type="SYNTAX",
                file_path=file_path,
                line=0,
                col=0,
                message=str(e),
                node_type="ParseError",
            )
            return None, issue

    def extract_imports(self, file_path: str) -> FileImportGraph:
        """
        Extract all import statements and defined/called names from a file.
        """
        graph = FileImportGraph(file_path=file_path)
        tree, err = self.parse_file(file_path)
        if err or tree is None:
            return graph

        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    graph.imports.append(alias.name)
            elif isinstance(node, ast.ImportFrom):
                module = node.module or ""
                for alias in node.names:
                    graph.from_imports.append((module, alias.name))
            elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                graph.defined_names.add(node.name)
            elif isinstance(node, ast.Name):
                if isinstance(node.ctx, ast.Store):
                    graph.defined_names.add(node.id)
                elif isinstance(node.ctx, ast.Load):
                    graph.called_names.add(node.id)

        return graph

    def build_dependency_graph(self, python_files: List[str]) -> Dict[str, List[str]]:
        """
        Build a file-level dependency graph: {file -> [files it imports from]}.
        Uses relative import resolution within the repo.
        """
        module_to_file: Dict[str, str] = {}
        for fp in python_files:
            rel = Path(fp).relative_to(self.repo_path)
            module = str(rel).replace("/", ".").removesuffix(".py")
            module_to_file[module] = fp

        dep_graph: Dict[str, List[str]] = {fp: [] for fp in python_files}
        for fp in python_files:
            ig = self.extract_imports(fp)
            deps: List[str] = []
            all_modules = [m for m in ig.imports] + [m for m, _ in ig.from_imports]
            for mod in all_modules:
                # Resolve relative
                for known_mod, known_fp in module_to_file.items():
                    if known_mod.endswith(mod) or mod.endswith(known_mod):
                        if known_fp != fp:
                            deps.append(known_fp)
                            break
            dep_graph[fp] = list(set(deps))

        return dep_graph

    def find_undefined_names(self, file_path: str) -> List[ASTIssue]:
        """
        Detect names used but never defined (heuristic, not a full scope resolver).
        """
        issues: List[ASTIssue] = []
        ig = self.extract_imports(file_path)
        imported_names: Set[str] = set()

        for imp in ig.imports:
            imported_names.add(imp.split(".")[0])
        for _, name in ig.from_imports:
            if name != "*":
                imported_names.add(name)

        builtins = set(dir(__builtins__)) if isinstance(__builtins__, dict) else set(vars(__builtins__).keys())
        builtin_names = builtins | {"print", "range", "len", "type", "isinstance", "None", "True", "False"}

        undefined = ig.called_names - ig.defined_names - imported_names - builtin_names
        tree, _ = self.parse_file(file_path)
        if tree is None:
            return issues

        for node in ast.walk(tree):
            if isinstance(node, ast.Name) and node.id in undefined:
                issues.append(ASTIssue(
                    issue_type="UNDEFINED_VAR",
                    file_path=file_path,
                    line=getattr(node, "lineno", 0),
                    col=getattr(node, "col_offset", 0),
                    message=f"Name '{node.id}' may not be defined",
                    node_type="Name",
                ))

        return issues

    def get_function_signatures(self, file_path: str) -> List[Dict[str, Any]]:
        """Extract all function/method signatures for context building."""
        sigs = []
        tree, _ = self.parse_file(file_path)
        if not tree:
            return sigs

        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                args = [a.arg for a in node.args.args]
                sigs.append({
                    "name": node.name,
                    "line": node.lineno,
                    "args": args,
                    "is_async": isinstance(node, ast.AsyncFunctionDef),
                    "decorators": [ast.unparse(d) for d in node.decorator_list],
                })

        return sigs

    def get_source_window(self, file_path: str, line: int, window: int = 10) -> str:
        """Return source lines around a specific line number."""
        try:
            lines = Path(file_path).read_text(encoding="utf-8").splitlines()
            start = max(0, line - window - 1)
            end = min(len(lines), line + window)
            snippet = lines[start:end]
            numbered = [f"{start + i + 1:4d} | {ln}" for i, ln in enumerate(snippet)]
            return "\n".join(numbered)
        except Exception as e:
            return f"[Could not read source: {e}]"
