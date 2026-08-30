"""Static analysis rules for roast-my-code."""

from __future__ import annotations

from dataclasses import dataclass
import ast
import re
from typing import Literal

from roast.scanner import FileResult, is_test_file
from roast.custom_rules import load_custom_rules, CustomRule

Severity = Literal["low", "medium", "high"]

AI_SLOP = "AI Slop"
CODE_QUALITY = "Code Quality"
STYLE = "Style"
SECURITY = "Security"

TODO_PATTERN = re.compile(r"#\s*(TODO|FIXME|HACK|XXX)\b", re.IGNORECASE)
PLACEHOLDER_PATTERN = re.compile(r"\b(foo|baz|temp|data2|result2|test123)\b")
COMMENTED_CODE_HINT = re.compile(
    r"\b(if|for|while|return|def|class|function|const|let|var|import|from)\b|[=;{}()]"
)
JS_IMPORT_PATTERN = re.compile(
    r"\bimport\s+(?:.+?\s+from\s+)?[\"'](?P<module>[^\"']+)[\"']|"
    r"\brequire\(\s*[\"'](?P<require_module>[^\"']+)[\"']\s*\)"
)
URL_IN_QUOTES_PATTERN = re.compile(r"[\"'][^\"']*http://[^\"']*[\"']", re.IGNORECASE)
PASSWORD_PATTERN = re.compile(r"password\s*=\s*[\"'][^\"']+[\"']", re.IGNORECASE)
CAMEL_CASE_PATTERN = re.compile(r"^[a-z]+(?:[A-Z][a-z0-9]*)+$")
SNAKE_CASE_PATTERN = re.compile(r"^[a-z]+(?:_[a-z0-9]+)+$")
LINE_MAGIC_INT_PATTERN = re.compile(r"(?<![\w])([1-9]\d+)(?![\w])")
UPPERCASE_ASSIGNMENT_PATTERN = re.compile(r"^\s*[A-Z][A-Z0-9_]*\s*=\s*[1-9]\d*\s*$")
LONG_JS_FUNCTION_PATTERN = re.compile(
    r"\bfunction\s+(?P<name>[A-Za-z_][A-Za-z0-9_]*)\s*\([^)]*\)\s*\{|"
    r"\b(?:const|let|var)\s+(?P<arrow>[A-Za-z_][A-Za-z0-9_]*)\s*=\s*(?:async\s+)?\([^)]*\)\s*=>\s*\{"
)
BAD_FUNCTION_NAMES = {"handle_it", "do_stuff", "process_data", "helper"}
FAKE_IMPORTS = {"magiclib", "utils2", "codemancer", "autocodekit", "aihelpers"}

# --- Language-specific patterns ---

# Go patterns
GO_LONG_FUNCTION_PATTERN = re.compile(
    r"\bfunc\s+(?:\([^)]*\)\s+)?(?P<name>[A-Za-z_][A-Za-z0-9_]*)\s*\([^)]*\)\s*(?:\([^)]*\)\s*)?\{"
)
GO_TODO_PATTERN = re.compile(r"//\s*(TODO|FIXME|HACK|XXX)\b", re.IGNORECASE)
GO_CONSOLE_LOG_PATTERN = re.compile(r"\bfmt\.Print(f|ln)?\s*\(")

# Rust patterns
RUST_LONG_FUNCTION_PATTERN = re.compile(
    r"\b(?:pub\s+)?(?:async\s+)?fn\s+(?P<name>[A-Za-z_][A-Za-z0-9_]*)\s*(?:<[^>]*>)?\s*\([^)]*\)\s*(?:->\s*[^{]+)?\s*\{"
)
RUST_TODO_PATTERN = re.compile(r"//\s*(TODO|FIXME|HACK|XXX)\b", re.IGNORECASE)
RUST_MACRO_PRINT = re.compile(r'\bprintln!\s*\(\s*"\s*"\s*\)')

# Java patterns
JAVA_LONG_FUNCTION_PATTERN = re.compile(
    r"\b(?:(?:public|private|protected|static|final|abstract|synchronized)\s+)*\w+(?:<[^>]*>)?\s+(?P<name>[A-Za-z_][A-Za-z0-9_]*)\s*\([^)]*\)\s*(?:throws\s+[\w,\s]+)?\s*\{"
)
JAVA_TODO_PATTERN = re.compile(r"//\s*(TODO|FIXME|HACK|XXX)\b", re.IGNORECASE)
JAVA_SYS_OUT_PATTERN = re.compile(r"System\.out\.print(ln)?\s*")

# Ruby patterns
RUBY_LONG_FUNCTION_PATTERN = re.compile(
    r"\b(?:def\s+)(?P<name>[A-Za-z_!?][A-Za-z0-9_!?]*)\s*(?:\([^)]*\))?\s*$"
)
RUBY_TODO_PATTERN = re.compile(r"#\s*(TODO|FIXME|HACK|XXX)\b", re.IGNORECASE)
RUBY_PUTS_PATTERN = re.compile(r"\bputs\s+")
RUBY_EVAL_PATTERN = re.compile(r"\beval\s*[(']")


@dataclass(slots=True)
class Issue:
    file: str
    line: int | None
    category: str
    severity: Severity
    description: str


@dataclass(slots=True)
class AnalysisReport:
    total_files: int
    total_lines: int
    issues: list[Issue]
    scores: dict[str, int]


class _ParentNodeVisitor(ast.NodeVisitor):
    """Attach parent pointers so checks can inspect context."""

    def generic_visit(self, node: ast.AST) -> None:
        for child in ast.iter_child_nodes(node):
            setattr(child, "_parent", node)
        super().generic_visit(node)


def _add_issue(
    issues: list[Issue],
    file_path: str,
    line: int | None,
    category: str,
    severity: Severity,
    description: str,
    line_offset: int = 0,
) -> None:
    adjusted_line = (line + line_offset) if line is not None else None
    issues.append(
        Issue(
            file=file_path,
            line=adjusted_line,
            category=category,
            severity=severity,
            description=description,
        )
    )


# _is_test_file is now imported from roast.scanner as is_test_file


def _module_from_import(import_name: str) -> str:
    return import_name.split(".", 1)[0]


def _safe_parse_python(content: str) -> ast.AST | None:
    try:
        tree = ast.parse(content)
    except SyntaxError:
        return None
    _ParentNodeVisitor().visit(tree)
    return tree


def _iter_python_functions(tree: ast.AST) -> list[ast.FunctionDef | ast.AsyncFunctionDef]:
    return [node for node in ast.walk(tree) if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))]


def _detect_python_high_severity(file: FileResult, issues: list[Issue], tree: ast.AST | None, line_offset: int = 0) -> None:
    lines = file.content.splitlines()
    for idx, line in enumerate(lines, start=1):
        if TODO_PATTERN.search(line):
            _add_issue(
                issues,
                file.path,
                idx,
                AI_SLOP,
                "high",
                "Left a TODO/FIXME/HACK marker in code.",
                line_offset=line_offset,
            )

    for idx, line in enumerate(lines, start=1):
        if PLACEHOLDER_PATTERN.search(line):
            _add_issue(
                issues,
                file.path,
                idx,
                AI_SLOP,
                "high",
                "Placeholder identifier suggests unfinished AI-generated code.",
                line_offset=line_offset,
            )

    if tree is None:
        return

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if _module_from_import(alias.name) in FAKE_IMPORTS:
                    _add_issue(
                        issues,
                        file.path,
                        getattr(node, "lineno", None),
                        AI_SLOP,
                        "high",
                        f"Suspicious hallucinated import: {alias.name}",
                        line_offset=line_offset,
                    )
        elif isinstance(node, ast.ImportFrom):
            module = _module_from_import(node.module or "")
            if module in FAKE_IMPORTS:
                _add_issue(
                    issues,
                    file.path,
                    getattr(node, "lineno", None),
                    AI_SLOP,
                    "high",
                    f"Suspicious hallucinated import: {node.module}",
                    line_offset=line_offset,
                )

    for fn in _iter_python_functions(tree):
        if fn.name in BAD_FUNCTION_NAMES:
            _add_issue(
                issues,
                file.path,
                fn.lineno,
                AI_SLOP,
                "high",
                f"Function name `{fn.name}` is generic AI-slop naming.",
                line_offset=line_offset,
            )

    for node in ast.walk(tree):
        if not isinstance(node, ast.Try):
            continue
        for handler in node.handlers:
            if len(handler.body) == 1 and isinstance(handler.body[0], ast.Pass):
                _add_issue(
                    issues,
                    file.path,
                    getattr(handler, "lineno", None),
                    AI_SLOP,
                    "high",
                    "Empty except block swallows errors with pass.",
                    line_offset=line_offset,
                )


def _detect_js_high_severity(file: FileResult, issues: list[Issue], line_offset: int = 0) -> None:
    lines = file.content.splitlines()

    for idx, line in enumerate(lines, start=1):
        if PLACEHOLDER_PATTERN.search(line):
            _add_issue(
                issues,
                file.path,
                idx,
                AI_SLOP,
                "high",
                "Placeholder identifier suggests unfinished AI-generated code.",
                line_offset=line_offset,
            )

    for idx, line in enumerate(lines, start=1):
        if re.search(r"\bfunction\s+(handle_it|do_stuff|process_data|helper)\b", line):
            _add_issue(
                issues,
                file.path,
                idx,
                AI_SLOP,
                "high",
                "Function name is overly generic AI-slop naming.",
                line_offset=line_offset,
            )
        if re.search(
            r"\b(?:const|let|var)\s+(handle_it|do_stuff|process_data|helper)\s*=\s*(?:async\s+)?\([^)]*\)\s*=>",
            line,
        ):
            _add_issue(
                issues,
                file.path,
                idx,
                AI_SLOP,
                "high",
                "Function name is overly generic AI-slop naming.",
                line_offset=line_offset,
            )

    for idx, line in enumerate(lines, start=1):
        for match in JS_IMPORT_PATTERN.finditer(line):
            module_name = match.group("module") or match.group("require_module")
            if module_name and _module_from_import(module_name) in FAKE_IMPORTS:
                _add_issue(
                    issues,
                    file.path,
                    idx,
                    AI_SLOP,
                    "high",
                    f"Suspicious hallucinated import: {module_name}",
                    line_offset=line_offset,
                )


def _detect_commented_out_blocks(file: FileResult, issues: list[Issue], line_offset: int = 0) -> None:
    lines = file.content.splitlines()
    start_line: int | None = None
    count = 0

    def flush() -> None:
        nonlocal start_line, count
        if start_line is not None and count >= 3:
            _add_issue(
                issues,
                file.path,
                start_line,
                AI_SLOP,
                "high",
                f"Commented-out code block appears to span {count} lines.",
                line_offset=line_offset,
            )
        start_line = None
        count = 0

    for idx, raw_line in enumerate(lines, start=1):
        stripped = raw_line.strip()
        if not stripped.startswith(("#", "//")):
            flush()
            continue
        comment_body = stripped.lstrip("#/ ").strip()
        if COMMENTED_CODE_HINT.search(comment_body):
            if start_line is None:
                start_line = idx
            count += 1
        else:
            flush()
    flush()


def _detect_python_medium_severity(file: FileResult, issues: list[Issue], tree: ast.AST | None, custom_rules: list[CustomRule], line_offset: int = 0, skip_large_file_check: bool = False) -> None:
    if not skip_large_file_check and file.line_count > 300:
        _add_issue(
            issues,
            file.path,
            None,
            CODE_QUALITY,
            "medium",
            f"Large file ({file.line_count} lines) hurts maintainability.",
        )

    lines = file.content.splitlines()
    if not is_test_file(file.path):
        for idx, line in enumerate(lines, start=1):
            for rule in custom_rules:
                if re.search(rule.pattern, line):
                    _add_issue(issues, file.path, idx, rule.category, rule.severity, rule.message, line_offset=line_offset)

            if re.search(r"\bprint\s*\(", line):
                _add_issue(
                    issues,
                    file.path,
                    idx,
                    CODE_QUALITY,
                    "medium",
                    "print() statement found in non-test Python file.",
                    line_offset=line_offset,
                )

    for idx, line in enumerate(lines, start=1):
        if URL_IN_QUOTES_PATTERN.search(line):
            _add_issue(
                issues,
                file.path,
                idx,
                CODE_QUALITY,
                "medium",
                "Hardcoded URL string detected.",
                line_offset=line_offset,
            )
        if PASSWORD_PATTERN.search(line):
            _add_issue(
                issues,
                file.path,
                idx,
                CODE_QUALITY,
                "medium",
                "Possible hardcoded credential detected.",
                line_offset=line_offset,
            )

    if tree is None:
        return

    for fn in _iter_python_functions(tree):
        end = getattr(fn, "end_lineno", fn.lineno)
        if end - fn.lineno + 1 > 50:
            _add_issue(
                issues,
                file.path,
                fn.lineno,
                CODE_QUALITY,
                "medium",
                f"Function `{fn.name}` exceeds 50 lines.",
                line_offset=line_offset,
            )

    for node in ast.walk(tree):
        if not isinstance(node, ast.Constant):
            continue
        if not isinstance(node.value, int) or node.value <= 9:
            continue
        parent = getattr(node, "_parent", None)
        if isinstance(parent, ast.Assign):
            # Ignore constants used in constant-style assignments (e.g. VERSION = 3).
            targets = [t for t in parent.targets if isinstance(t, ast.Name)]
            if targets and all(target.id.isupper() for target in targets):
                continue
        if isinstance(parent, ast.AnnAssign) and isinstance(parent.target, ast.Name) and parent.target.id.isupper():
            continue
        _add_issue(
            issues,
            file.path,
            getattr(node, "lineno", None),
            CODE_QUALITY,
            "medium",
            f"Magic number `{node.value}` found outside constant assignment.",
            line_offset=line_offset,
        )


def _detect_js_medium_severity(file: FileResult, issues: list[Issue], line_offset: int = 0, skip_large_file_check: bool = False) -> None:
    if not skip_large_file_check and file.line_count > 300:
        _add_issue(
            issues,
            file.path,
            None,
            CODE_QUALITY,
            "medium",
            f"Large file ({file.line_count} lines) hurts maintainability.",
        )

    lines = file.content.splitlines()
    if not is_test_file(file.path):
        for idx, line in enumerate(lines, start=1):
            if "console.log(" in line:
                _add_issue(
                    issues,
                    file.path,
                    idx,
                    CODE_QUALITY,
                    "medium",
                    "console.log() found in non-test JS/TS file.",
                    line_offset=line_offset,
                )

    for idx, line in enumerate(lines, start=1):
        if URL_IN_QUOTES_PATTERN.search(line):
            _add_issue(
                issues,
                file.path,
                idx,
                CODE_QUALITY,
                "medium",
                "Hardcoded URL string detected.",
                line_offset=line_offset,
            )
        if PASSWORD_PATTERN.search(line):
            _add_issue(
                issues,
                file.path,
                idx,
                CODE_QUALITY,
                "medium",
                "Possible hardcoded credential detected.",
                line_offset=line_offset,
            )

    for idx, line in enumerate(lines, start=1):
        if UPPERCASE_ASSIGNMENT_PATTERN.match(line.strip()):
            continue
        for match in LINE_MAGIC_INT_PATTERN.finditer(line):
            if int(match.group(1)) > 9:
                _add_issue(
                    issues,
                    file.path,
                    idx,
                    CODE_QUALITY,
                    "medium",
                    f"Magic number `{match.group(1)}` found outside constant assignment.",
                    line_offset=line_offset,
                )

    _detect_long_js_functions(file, issues, line_offset=line_offset)


def _detect_long_js_functions(file: FileResult, issues: list[Issue], line_offset: int = 0) -> None:
    lines = file.content.splitlines()
    index = 0
    while index < len(lines):
        line = lines[index]
        match = LONG_JS_FUNCTION_PATTERN.search(line)
        if not match:
            index += 1
            continue

        function_name = match.group("name") or match.group("arrow") or "anonymous"
        brace_balance = line[match.end() - 1 :].count("{") - line[match.end() - 1 :].count("}")
        end_index = index
        while brace_balance > 0 and end_index + 1 < len(lines):
            end_index += 1
            brace_balance += lines[end_index].count("{")
            brace_balance -= lines[end_index].count("}")

        length = end_index - index + 1
        if length > 50:
            _add_issue(
                issues,
                file.path,
                index + 1,
                CODE_QUALITY,
                "medium",
                f"Function `{function_name}` exceeds 50 lines.",
                line_offset=line_offset,
            )
        index = max(end_index + 1, index + 1)


def _collect_identifier_names(file: FileResult, tree: ast.AST | None) -> set[str]:
    names: set[str] = set()
    if file.language == "python" and tree is not None:
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                names.add(node.name)
            elif isinstance(node, ast.Name):
                names.add(node.id)
        return names

    for match in re.finditer(
        r"\b(?:const|let|var|function)\s+([A-Za-z_][A-Za-z0-9_]*)|\b([A-Za-z_][A-Za-z0-9_]*)\s*:",
        file.content,
    ):
        name = match.group(1) or match.group(2)
        if name:
            names.add(name)
    return names


def _detect_style_issues(file: FileResult, issues: list[Issue], tree: ast.AST | None, line_offset: int = 0) -> None:
    names = _collect_identifier_names(file, tree)
    has_camel = any(CAMEL_CASE_PATTERN.match(name) for name in names)
    has_snake = any(SNAKE_CASE_PATTERN.match(name) for name in names)
    if has_camel and has_snake:
        _add_issue(
            issues,
            file.path,
            None,
            STYLE,
            "low",
            "Mixed camelCase and snake_case naming in one file.",
        )

    for idx, line in enumerate(file.content.splitlines(), start=1):
        if len(line) > 120:
            _add_issue(
                issues,
                file.path,
                idx,
                STYLE,
                "low",
                "Line exceeds 120 characters.",
                line_offset=line_offset,
            )

    if file.language != "python" or tree is None:
        return

    for fn in _iter_python_functions(tree):
        if fn.name.startswith("_"):
            continue
        if ast.get_docstring(fn) is None:
            _add_issue(
                issues,
                file.path,
                fn.lineno,
                STYLE,
                "low",
                f"Public function `{fn.name}` is missing a docstring.",
                line_offset=line_offset,
            )


def _compute_score_for_category(issues: list[Issue], category: str) -> int:
    high_count = sum(1 for issue in issues if issue.category == category and issue.severity == "high")
    medium_count = sum(1 for issue in issues if issue.category == category and issue.severity == "medium")
    low_count = sum(1 for issue in issues if issue.category == category and issue.severity == "low")
    raw = 100 - (high_count * 15) - (medium_count * 7) - (low_count * 2)
    return max(0, raw)


def _line_offset(file: FileResult) -> int:
    """Return the line offset to apply for chunked files (0-based)."""
    return file.chunk_start - 1 if file.chunk_start > 1 else 0


def _detect_generic_language_high_severity(file: FileResult, issues: list[Issue], line_offset: int = 0) -> None:
    """Detect high-severity AI slop issues across all languages (TODOs, placeholders)."""
    todo_pattern = {
        "python": TODO_PATTERN,
        "go": GO_TODO_PATTERN,
        "rust": RUST_TODO_PATTERN,
        "java": JAVA_TODO_PATTERN,
        "ruby": RUBY_TODO_PATTERN,
    }.get(file.language, TODO_PATTERN)

    lines = file.content.splitlines()
    for idx, line in enumerate(lines, start=1):
        if todo_pattern.search(line):
            _add_issue(
                issues, file.path, idx, AI_SLOP, "high",
                "Left a TODO/FIXME/HACK marker in code.",
                line_offset=line_offset,
            )
        if PLACEHOLDER_PATTERN.search(line):
            _add_issue(
                issues, file.path, idx, AI_SLOP, "high",
                "Placeholder identifier suggests unfinished AI-generated code.",
                line_offset=line_offset,
            )


def _detect_go_medium_severity(file: FileResult, issues: list[Issue], line_offset: int = 0) -> None:
    """Detect code quality issues in Go files."""
    lines = file.content.splitlines()
    for idx, line in enumerate(lines, start=1):
        if GO_CONSOLE_LOG_PATTERN.search(line):
            if not is_test_file(file.path):
                _add_issue(
                    issues, file.path, idx, CODE_QUALITY, "medium",
                    "fmt.Print/Println left in non-test Go file.",
                    line_offset=line_offset,
                )
        if URL_IN_QUOTES_PATTERN.search(line):
            _add_issue(
                issues, file.path, idx, CODE_QUALITY, "medium",
                "Hardcoded URL string detected.",
                line_offset=line_offset,
            )
        if PASSWORD_PATTERN.search(line):
            _add_issue(
                issues, file.path, idx, CODE_QUALITY, "medium",
                "Possible hardcoded credential detected.",
                line_offset=line_offset,
            )
        # Magic numbers (skip common Go patterns like port numbers in const blocks)
        if not line.strip().startswith("//"):
            for match in LINE_MAGIC_INT_PATTERN.finditer(line):
                val = int(match.group(1))
                if val > 9 and not line.strip().startswith("const"):
                    _add_issue(
                        issues, file.path, idx, CODE_QUALITY, "medium",
                        f"Magic number `{match.group(1)}` found.",
                        line_offset=line_offset,
                    )


def _detect_rust_medium_severity(file: FileResult, issues: list[Issue], line_offset: int = 0) -> None:
    """Detect code quality issues in Rust files."""
    lines = file.content.splitlines()
    for idx, line in enumerate(lines, start=1):
        if RUST_MACRO_PRINT.search(line):
            if not is_test_file(file.path):
                _add_issue(
                    issues, file.path, idx, CODE_QUALITY, "medium",
                    "Empty println! macro left in non-test Rust file.",
                    line_offset=line_offset,
                )
        if URL_IN_QUOTES_PATTERN.search(line):
            _add_issue(
                issues, file.path, idx, CODE_QUALITY, "medium",
                "Hardcoded URL string detected.",
                line_offset=line_offset,
            )
        if PASSWORD_PATTERN.search(line):
            _add_issue(
                issues, file.path, idx, CODE_QUALITY, "medium",
                "Possible hardcoded credential detected.",
                line_offset=line_offset,
            )


def _detect_java_medium_severity(file: FileResult, issues: list[Issue], line_offset: int = 0) -> None:
    """Detect code quality issues in Java files."""
    lines = file.content.splitlines()
    for idx, line in enumerate(lines, start=1):
        if JAVA_SYS_OUT_PATTERN.search(line):
            if not is_test_file(file.path):
                _add_issue(
                    issues, file.path, idx, CODE_QUALITY, "medium",
                    "System.out.print/println left in non-test Java file.",
                    line_offset=line_offset,
                )
        if URL_IN_QUOTES_PATTERN.search(line):
            _add_issue(
                issues, file.path, idx, CODE_QUALITY, "medium",
                "Hardcoded URL string detected.",
                line_offset=line_offset,
            )
        if PASSWORD_PATTERN.search(line):
            _add_issue(
                issues, file.path, idx, CODE_QUALITY, "medium",
                "Possible hardcoded credential detected.",
                line_offset=line_offset,
            )


def _detect_ruby_medium_severity(file: FileResult, issues: list[Issue], line_offset: int = 0) -> None:
    """Detect code quality issues in Ruby files."""
    lines = file.content.splitlines()
    for idx, line in enumerate(lines, start=1):
        if RUBY_PUTS_PATTERN.search(line):
            if not is_test_file(file.path):
                _add_issue(
                    issues, file.path, idx, CODE_QUALITY, "medium",
                    "puts statement left in non-test Ruby file.",
                    line_offset=line_offset,
                )
        if RUBY_EVAL_PATTERN.search(line):
            _add_issue(
                issues, file.path, idx, CODE_QUALITY, "medium",
                "eval() usage in Ruby — potential code injection.",
                line_offset=line_offset,
            )
        if URL_IN_QUOTES_PATTERN.search(line):
            _add_issue(
                issues, file.path, idx, CODE_QUALITY, "medium",
                "Hardcoded URL string detected.",
                line_offset=line_offset,
            )
        if PASSWORD_PATTERN.search(line):
            _add_issue(
                issues, file.path, idx, CODE_QUALITY, "medium",
                "Possible hardcoded credential detected.",
                line_offset=line_offset,
            )


def analyze(files: list[FileResult]) -> AnalysisReport:
    """Analyze scanned files and return issues and scoring."""
    issues: list[Issue] = []
    custom_rules = load_custom_rules()

    # Import here to avoid circular dependency at module level.
    # security.py imports from analyzer.py, so we defer this import.
    from roast.security import detect_security_issues  # noqa: E402

    # Track which chunked files we've already emitted a "large file" warning for.
    large_file_warned: set[str] = set()

    for file in files:
        offset = _line_offset(file)
        is_chunk = file.original_line_count > 0

        # Emit a single "large file" warning for the original file, not per chunk.
        if is_chunk and file.path not in large_file_warned:
            large_file_warned.add(file.path)
            _add_issue(
                issues,
                file.path,
                None,
                CODE_QUALITY,
                "medium",
                f"Large file ({file.original_line_count} lines) hurts maintainability.",
            )

        tree: ast.AST | None = None
        if file.language == "python":
            tree = _safe_parse_python(file.content)

        if file.language == "python":
            _detect_python_high_severity(file, issues, tree, line_offset=offset)
            # Don't re-detect "large file" inside medium severity — we already did it above.
            _detect_python_medium_severity(file, issues, tree, custom_rules, line_offset=offset, skip_large_file_check=is_chunk)
        elif file.language in {"javascript", "typescript"}:
            _detect_js_high_severity(file, issues, line_offset=offset)
            _detect_js_medium_severity(file, issues, line_offset=offset, skip_large_file_check=is_chunk)
        elif file.language == "go":
            _detect_generic_language_high_severity(file, issues, line_offset=offset)
            _detect_go_medium_severity(file, issues, line_offset=offset)
        elif file.language == "rust":
            _detect_generic_language_high_severity(file, issues, line_offset=offset)
            _detect_rust_medium_severity(file, issues, line_offset=offset)
        elif file.language == "java":
            _detect_generic_language_high_severity(file, issues, line_offset=offset)
            _detect_java_medium_severity(file, issues, line_offset=offset)
        elif file.language == "ruby":
            _detect_generic_language_high_severity(file, issues, line_offset=offset)
            _detect_ruby_medium_severity(file, issues, line_offset=offset)
        else:
            _detect_generic_language_high_severity(file, issues, line_offset=offset)

        _detect_commented_out_blocks(file, issues, line_offset=offset)
        _detect_style_issues(file, issues, tree, line_offset=offset)

        detect_security_issues(file, issues, tree, line_offset=offset)

    slop_score = _compute_score_for_category(issues, AI_SLOP)
    quality_score = _compute_score_for_category(issues, CODE_QUALITY)
    security_score = _compute_score_for_category(issues, SECURITY)
    style_score = _compute_score_for_category(issues, STYLE)
    overall_score = round((slop_score * 0.35) + (quality_score * 0.25) + (security_score * 0.25) + (style_score * 0.15))

    scores = {
        AI_SLOP: slop_score,
        CODE_QUALITY: quality_score,
        SECURITY: security_score,
        STYLE: style_score,
        "Overall": overall_score,
    }

    # Count unique original files, not chunks.
    unique_files = len({file.path for file in files})
    return AnalysisReport(
        total_files=unique_files,
        total_lines=sum(file.original_line_count if file.original_line_count > 0 else file.line_count for file in files),
        issues=issues,
        scores=scores,
    )
