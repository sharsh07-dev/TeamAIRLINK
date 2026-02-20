"""
backend/agents/repo_analyzer_agent.py
=======================================
RepoAnalyzerAgent — Universal Polyglot Scanner.

Language Detection:
  package.json            → NODE_JS   (npm / yarn)
  pom.xml / build.gradle  → JAVA      (mvn / gradle)
  requirements.txt /
  pyproject.toml /
  setup.py                → PYTHON    (pytest)

Scans all source files across Python, JavaScript, TypeScript, and Java.
Builds a lightweight dependency graph where possible.
"""

from __future__ import annotations

import os
import time
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from backend.utils.ast_parser import ASTParser
from backend.utils.logger import logger
from backend.utils.models import AgentState, CITimelineEvent, LanguageMode


# ── Directories to skip ───────────────────────────────────────────────────────
IGNORE_DIRS = {
    "__pycache__", ".git", ".tox", "node_modules", ".venv",
    "venv", "env", "dist", "build", ".eggs", "*.egg-info",
    ".mypy_cache", ".pytest_cache", ".gradle", "target",         # Java/Gradle
    ".next", ".nuxt", "coverage", ".nyc_output", "out",          # Node
}

# ── Source extensions per language ────────────────────────────────────────────
LANG_EXTENSIONS: Dict[str, List[str]] = {
    LanguageMode.PYTHON:  [".py"],
    LanguageMode.NODE_JS: [".js", ".jsx", ".ts", ".tsx", ".mjs", ".cjs"],
    LanguageMode.JAVA:    [".java"],
}

# All extensions we care about for "source files"
ALL_SOURCE_EXTS = {
    ext for exts in LANG_EXTENSIONS.values() for ext in exts
}

# ── Test file heuristics ─────────────────────────────────────────────────────
TEST_PATTERNS = {
    LanguageMode.PYTHON:  lambda n: n.startswith("test_") or n.endswith("_test.py"),
    LanguageMode.NODE_JS: lambda n: ".test." in n or ".spec." in n
                                    or n.startswith("test_") or "/tests/" in n or "/__tests__/" in n,
    LanguageMode.JAVA:    lambda n: n.startswith("Test") or n.endswith("Test.java")
                                    or n.endswith("Tests.java") or n.endswith("Spec.java"),
}

# ── Config file names ─────────────────────────────────────────────────────────
CONFIG_NAMES = {
    # Python
    "pyproject.toml", "setup.cfg", "setup.py", ".pylintrc", ".flake8", "tox.ini",
    # Node
    "package.json", "package-lock.json", ".eslintrc", ".eslintrc.js", ".eslintrc.json",
    "tsconfig.json", "jest.config.js", "jest.config.ts", ".babelrc", "webpack.config.js",
    # Java
    "pom.xml", "build.gradle", "build.gradle.kts", "settings.gradle", "gradle.properties",
}


class RepoAnalyzerAgent:
    """
    Universal repo scanner supporting Python, Node.js, and Java.
    Detects language, discovers source/test files, and builds a dep graph.
    """

    def __init__(self, state: AgentState):
        self.state = state
        self.repo_path = Path(state.repo_path)
        self.ast_parser = ASTParser(str(self.repo_path))

    # ─────────────────────────────────────────
    def run(self) -> AgentState:
        t0 = time.time()
        logger.info(f"[RepoAnalyzerAgent] Scanning repo: {self.repo_path}")

        # 1. Detect language
        language, test_tool = self._detect_language()
        self.state.repo_language = language
        self.state.test_runner_tool = test_tool
        logger.info(f"[RepoAnalyzerAgent] Detected language={language}, test_tool={test_tool}")

        # 2. Walk and discover all source files
        all_source_files = self._discover_source_files(language)
        test_files = self._classify_test_files(all_source_files, language)
        source_only = [f for f in all_source_files if f not in test_files]
        config_files = self._discover_config_files()

        # 3. Build dependency graph (Python only via AST; others get empty graph)
        if language == LanguageMode.PYTHON:
            dep_graph = self.ast_parser.build_dependency_graph(all_source_files)
        else:
            dep_graph = {f: [] for f in all_source_files}

        elapsed = time.time() - t0

        # 4. Persist into state (back-compat: keep python_files alias for Python repos)
        self.state.source_files = all_source_files
        if language == LanguageMode.PYTHON:
            self.state.python_files = all_source_files
        self.state.test_files = test_files
        self.state.config_files = config_files
        self.state.dependency_graph = dep_graph

        lang_label = {
            LanguageMode.PYTHON:  "Python",
            LanguageMode.NODE_JS: "Node.js/TS",
            LanguageMode.JAVA:    "Java",
        }.get(language, language)

        self.state.timeline.append(CITimelineEvent(
            iteration=self.state.iteration,
            event_type="ANALYSIS",
            description=(
                f"[{lang_label}] Discovered {len(all_source_files)} source files, "
                f"{len(test_files)} test files, {len(config_files)} config files"
            ),
            duration_seconds=elapsed,
        ))

        logger.success(
            f"[RepoAnalyzerAgent] Done in {elapsed:.2f}s — "
            f"{lang_label}: {len(all_source_files)} src, {len(test_files)} tests, "
            f"{len(config_files)} configs"
        )
        return self.state

    # ─────────────────────────────────────────
    def _detect_language(self) -> Tuple[str, str]:
        """
        Inspects root-level files to determine the language/runtime.
        Returns (LanguageMode, test_runner_tool).
        Priority: Node > Java > Python > UNKNOWN
        """
        root = self.repo_path

        # ── Node.js / TypeScript ──
        if (root / "package.json").exists():
            # Check if yarn is preferred
            tool = "yarn test" if (root / "yarn.lock").exists() else "npm test"
            return LanguageMode.NODE_JS, tool

        # ── Java (Maven or Gradle) ──
        if (root / "pom.xml").exists():
            return LanguageMode.JAVA, "mvn test"
        if (root / "build.gradle").exists() or (root / "build.gradle.kts").exists():
            return LanguageMode.JAVA, "gradle test"

        # ── Python ──
        python_signals = [
            "requirements.txt", "requirements-dev.txt", "pyproject.toml",
            "setup.py", "setup.cfg", "Pipfile",
        ]
        if any((root / s).exists() for s in python_signals):
            return LanguageMode.PYTHON, "pytest"

        # ── Fallback: count file extensions ──
        ext_counts: Dict[str, int] = {}
        for f in root.rglob("*"):
            if f.suffix in ALL_SOURCE_EXTS and not any(
                part in IGNORE_DIRS for part in f.parts
            ):
                ext_counts[f.suffix] = ext_counts.get(f.suffix, 0) + 1

        py_count   = sum(ext_counts.get(e, 0) for e in LANG_EXTENSIONS[LanguageMode.PYTHON])
        node_count = sum(ext_counts.get(e, 0) for e in LANG_EXTENSIONS[LanguageMode.NODE_JS])
        java_count = sum(ext_counts.get(e, 0) for e in LANG_EXTENSIONS[LanguageMode.JAVA])

        if java_count > py_count and java_count > node_count:
            return LanguageMode.JAVA, "mvn test"
        if node_count > py_count:
            return LanguageMode.NODE_JS, "npm test"
        if py_count > 0:
            return LanguageMode.PYTHON, "pytest"

        logger.warning("[RepoAnalyzerAgent] Could not detect language — defaulting to PYTHON")
        return LanguageMode.PYTHON, "pytest"

    # ─────────────────────────────────────────
    def _discover_source_files(self, language: str) -> List[str]:
        """Walk the repo and return all source files for the detected language."""
        exts = set(LANG_EXTENSIONS.get(language, []))
        if not exts:
            # UNKNOWN: gather everything we know about
            exts = ALL_SOURCE_EXTS

        files: List[str] = []
        for root, dirs, filenames in os.walk(self.repo_path):
            # Prune ignored directories in-place
            dirs[:] = [
                d for d in dirs
                if d not in IGNORE_DIRS and not d.startswith(".")
            ]
            for fname in filenames:
                if Path(fname).suffix in exts:
                    files.append(os.path.join(root, fname))

        if not files:
            logger.warning(
                f"[RepoAnalyzerAgent] No {language} source files found in {self.repo_path}. "
                f"Root contents: {list(self.repo_path.iterdir())[:10]}"
            )

        return sorted(files)

    # ─────────────────────────────────────────
    def _classify_test_files(self, files: List[str], language: str) -> List[str]:
        """Identify test files using language-specific naming heuristics."""
        matcher = TEST_PATTERNS.get(language, lambda n: False)
        test_files = []
        for fp in files:
            name = Path(fp).name
            # Also check if inside a 'tests', '__tests__', 'test' directory
            parts_lower = [p.lower() for p in Path(fp).parts]
            in_test_dir = any(p in ("tests", "test", "__tests__", "spec") for p in parts_lower)
            if matcher(name) or in_test_dir:
                test_files.append(fp)
        return test_files

    # ─────────────────────────────────────────
    def _discover_config_files(self) -> List[str]:
        results: List[str] = []
        for root, dirs, filenames in os.walk(self.repo_path):
            dirs[:] = [d for d in dirs if d not in IGNORE_DIRS]
            for fname in filenames:
                if fname in CONFIG_NAMES or fname.startswith("requirements"):
                    results.append(os.path.join(root, fname))
        return sorted(results)
