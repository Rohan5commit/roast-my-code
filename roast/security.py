"""Security vulnerability detection for roast-my-code."""

from __future__ import annotations

import ast
import re

from roast.analyzer import Issue, SECURITY, _add_issue
from roast.scanner import FileResult, is_test_file

# ---------------------------------------------------------------------------
# Regex patterns (language-agnostic)
# ---------------------------------------------------------------------------

HARDCODED_SECRET_PATTERNS = [
    # Only match at start of line (variable assignments), not inside strings
    (re.compile(r"^\s*password\s*=\s*[\"'][^\"']+[\"']", re.IGNORECASE | re.MULTILINE), "Hardcoded password detected."),
    (re.compile(r"^\s*api_key\s*=\s*[\"'][^\"']+[\"']", re.IGNORECASE | re.MULTILINE), "Hardcoded API key detected."),
    (re.compile(r"^\s*secret\s*=\s*[\"'][^\"']+[\"']", re.IGNORECASE | re.MULTILINE), "Hardcoded secret detected."),
    (re.compile(r"^\s*token\s*=\s*[\"'][^\"']+[\"']", re.IGNORECASE | re.MULTILINE), "Hardcoded token detected."),
    (re.compile(r"^\s*aws_secret_access_key\s*=\s*[\"'][^\"']+[\"']", re.IGNORECASE | re.MULTILINE), "AWS secret access key hardcoded."),
    (re.compile(r"-----BEGIN (?:RSA |EC )?PRIVATE KEY-----"), "Exposed private key in source code."),
]

SQL_INJECTION_PATTERN = re.compile(
    r"(?:execute|cursor\.execute|query)\s*\(\s*(?:f[\"']|['\"].*%s|['\"].*\+)",
    re.IGNORECASE,
)

# ---------------------------------------------------------------------------
# Python AST-based patterns
# ---------------------------------------------------------------------------

_DANGEROUS_PYTHON_CALLS = {
    "eval": "Use of eval() allows arbitrary code execution.",
    "exec": "Use of exec() allows arbitrary code execution.",
    "compile": "Dynamic code compilation detected.",
    "__import__": "Dynamic import via __import__() detected.",
}

_SHELL_INJECTION_CALLS = {"system", "popen"}

# ---------------------------------------------------------------------------
# JavaScript / TypeScript patterns
# ---------------------------------------------------------------------------

# ---------------------------------------------------------------------------
# Go patterns
# ---------------------------------------------------------------------------

GO_SECURITY_PATTERNS = [
    (re.compile(r"\bos\.exec\s*\("), "high", "os/exec usage — verify no shell injection."),
    (re.compile(r"\bexec\.Command\s*\("), "medium", "exec.Command usage — validate arguments carefully."),
    (re.compile(r"\bhttp\.ListenAndServe\s*\("), "medium", "HTTP server without TLS — traffic sent in plaintext."),
    (re.compile(r"\bsql\.Open\s*\("), "medium", "SQL database connection — use parameterized queries."),
]

# ---------------------------------------------------------------------------
# Rust patterns
# ---------------------------------------------------------------------------

RUST_SECURITY_PATTERNS = [
    (re.compile(r"\bunsafe\s*\{"), "high", "Unsafe block detected — verify memory safety invariants."),
    (re.compile(r"\bunsafe\s+fn\b"), "high", "Unsafe function definition — verify memory safety invariants."),
    (re.compile(r"\bstd::process::Command\b"), "medium", "Process command execution — validate arguments for injection."),
    (re.compile(r"\braw pointer\b"), "high", "Raw pointer usage — potential memory safety issue."),
]

# ---------------------------------------------------------------------------
# Java patterns
# ---------------------------------------------------------------------------

JAVA_SECURITY_PATTERNS = [
    (re.compile(r"Runtime\.getRuntime\(\)\.exec\s*\("), "high", "Runtime.exec() — shell injection risk."),
    (re.compile(r"\bProcessBuilder\b"), "medium", "ProcessBuilder — validate command arguments."),
    (re.compile(r"\bClass\.forName\s*\("), "medium", "Dynamic class loading via reflection."),
    (re.compile(r"\bObjectInputStream\b"), "high", "Java deserialization — can execute arbitrary code."),
    (re.compile(r"\bScriptEngine\b"), "high", "Script engine — allows arbitrary code execution."),
    (re.compile(r"\binnerHTML\b"), "medium", "innerHTML usage in Java templates — potential XSS."),
]

# ---------------------------------------------------------------------------
# Ruby patterns
# ---------------------------------------------------------------------------

RUBY_SECURITY_PATTERNS = [
    (re.compile(r"\beval\s*[(']"), "high", "eval() in Ruby — allows arbitrary code execution."),
    (re.compile(r"\bexec\s*[(']"), "high", "exec() in Ruby — shell injection risk."),
    (re.compile(r"\bsystem\s*[(']"), "high", "system() in Ruby — shell injection risk."),
    (re.compile(r"\bKernel\.system\s*\("), "high", "Kernel.system() — shell injection risk."),
    (re.compile(r"\bMarshal\.load\s*\("), "high", "Marshal.load() — insecure deserialization."),
    (re.compile(r"\bYAML\.load\s*\("), "medium", "YAML.load() without safe_load — code execution risk."),
    (re.compile(r"\bsend\s+"), "medium", "Dynamic method dispatch — verify no injection vector."),
]

# ---------------------------------------------------------------------------
# JavaScript / TypeScript patterns
# ---------------------------------------------------------------------------

JS_SECURITY_PATTERNS = [
    (re.compile(r"\beval\s*\("), "high", "Use of eval() allows arbitrary code execution."),
    (re.compile(r"\.innerHTML\s*="), "high", "Assignment to innerHTML enables XSS attacks."),
    (re.compile(r"\bdocument\.write\s*\("), "high", "document.write() enables XSS attacks."),
    (re.compile(r"\bnew\s+Function\s*\("), "medium", "Dynamic function construction via new Function()."),
    (re.compile(r"\bsetTimeout\s*\(['\"]"), "medium", "String-eval setTimeout is a security risk."),
    (re.compile(r"\bsetInterval\s*\(['\"]"), "medium", "String-eval setInterval is a security risk."),
    (re.compile(r"\bdangerouslySetInnerHTML\b"), "medium", "React dangerouslySetInnerHTML may enable XSS."),
    (re.compile(r"\bMath\.random\s*\("), "medium", "Math.random() is not cryptographically secure."),
    (re.compile(r"document\.cookie\s*="), "high", "Direct cookie manipulation without security flags."),
    (re.compile(r"\.src\s*=\s*[^\"']*(?:\+|`\$)"), "medium", "Dynamic src assignment may enable injection."),
]


def _detect_python_security_ast(
    file: FileResult,
    issues: list[Issue],
    tree: ast.AST,
    line_offset: int = 0,
) -> None:
    """Detect security issues in Python files using AST analysis."""
    for node in ast.walk(tree):
        # eval() / exec() / compile() / __import__()
        if isinstance(node, ast.Call):
            func_name = _get_call_name(node)
            if func_name in _DANGEROUS_PYTHON_CALLS:
                _add_issue(
                    issues,
                    file.path,
                    getattr(node, "lineno", None),
                    SECURITY,
                    "high",
                    _DANGEROUS_PYTHON_CALLS[func_name],
                    line_offset=line_offset,
                )

            # subprocess with shell=True
            if func_name in ("run", "call", "check_output", "check_call", "Popen"):
                if _has_shell_true(node):
                    _add_issue(
                        issues,
                        file.path,
                        getattr(node, "lineno", None),
                        SECURITY,
                        "high",
                        "subprocess called with shell=True — shell injection risk.",
                        line_offset=line_offset,
                    )

            # os.system()
            if func_name in _SHELL_INJECTION_CALLS:
                parent_is_os = _parent_is_module(node, "os")
                if parent_is_os:
                    _add_issue(
                        issues,
                        file.path,
                        getattr(node, "lineno", None),
                        SECURITY,
                        "high",
                        "os.system() — use subprocess without shell=True instead.",
                        line_offset=line_offset,
                    )

            # yaml.load() without Loader
            if func_name == "load":
                if _parent_is_module(node, "yaml"):
                    if not _has_loader_argument(node):
                        _add_issue(
                            issues,
                            file.path,
                            getattr(node, "lineno", None),
                            SECURITY,
                            "medium",
                            "yaml.load() without Loader — use yaml.safe_load() instead.",
                            line_offset=line_offset,
                        )

            # tempfile.mktemp()
            if func_name == "mktemp":
                if _parent_is_module(node, "tempfile"):
                    _add_issue(
                        issues,
                        file.path,
                        getattr(node, "lineno", None),
                        SECURITY,
                        "medium",
                        "tempfile.mktemp() is insecure — use tempfile.mkstemp() instead.",
                        line_offset=line_offset,
                    )

        # pickle.loads / pickle.dumps (deserialization)
        if isinstance(node, ast.Call):
            func_name = _get_call_name(node)
            if func_name in ("loads", "load", "Unpickler"):
                if _parent_is_module(node, "pickle") or _parent_is_module(node, "shelve"):
                    _add_issue(
                        issues,
                        file.path,
                        getattr(node, "lineno", None),
                        SECURITY,
                        "high",
                        "Insecure deserialization via pickle/shelve — can execute arbitrary code.",
                        line_offset=line_offset,
                    )

        # assert used for validation in non-test files
        if isinstance(node, ast.Assert):
            if not is_test_file(file.path):
                _add_issue(
                    issues,
                    file.path,
                    getattr(node, "lineno", None),
                    SECURITY,
                    "medium",
                    "assert used for validation — asserts are stripped in optimized mode (-O).",
                    line_offset=line_offset,
                )


def _detect_python_security_regex(
    file: FileResult,
    issues: list[Issue],
    line_offset: int = 0,
) -> None:
    """Detect security issues in Python files using regex (line-based)."""
    lines = file.content.splitlines()
    for idx, line in enumerate(lines, start=1):
        # SQL injection
        if SQL_INJECTION_PATTERN.search(line):
            _add_issue(
                issues,
                file.path,
                idx,
                SECURITY,
                "high",
                "Possible SQL injection — string interpolation in query.",
                line_offset=line_offset,
            )


def _detect_js_security(
    file: FileResult,
    issues: list[Issue],
    line_offset: int = 0,
) -> None:
    """Detect security issues in JS/TS files."""
    lines = file.content.splitlines()
    for idx, line in enumerate(lines, start=1):
        for pattern, severity, description in JS_SECURITY_PATTERNS:
            if pattern.search(line):
                _add_issue(
                    issues,
                    file.path,
                    idx,
                    SECURITY,
                    severity,
                    description,
                    line_offset=line_offset,
                )


def _detect_generic_security(
    file: FileResult,
    issues: list[Issue],
    line_offset: int = 0,
) -> None:
    """Detect hardcoded secrets and keys (language-agnostic)."""
    lines = file.content.splitlines()
    for idx, line in enumerate(lines, start=1):
        for pattern, description in HARDCODED_SECRET_PATTERNS:
            if pattern.search(line):
                _add_issue(
                    issues,
                    file.path,
                    idx,
                    SECURITY,
                    "high",
                    description,
                    line_offset=line_offset,
                )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _get_call_name(node: ast.Call) -> str:
    """Extract the function name from a Call node."""
    func = node.func
    if isinstance(func, ast.Name):
        return func.id
    if isinstance(func, ast.Attribute):
        return func.attr
    return ""


def _parent_is_module(node: ast.Call, module_name: str) -> bool:
    """Check if a Call's parent Attribute refers to a module (e.g. os.system)."""
    func = node.func
    if isinstance(func, ast.Attribute) and isinstance(func.value, ast.Name):
        return func.value.id == module_name
    return False


def _has_shell_true(node: ast.Call) -> bool:
    """Check if a subprocess call has shell=True."""
    for kw in node.keywords:
        if kw.arg == "shell":
            if isinstance(kw.value, ast.Constant) and kw.value.value is True:
                return True
    return False


def _has_loader_argument(node: ast.Call) -> bool:
    """Check if yaml.load() has a Loader argument."""
    for kw in node.keywords:
        if kw.arg and kw.arg.lower() == "loader":
            return True
    if len(node.args) >= 2:
        return True
    return False


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------


def _detect_go_security(
    file: FileResult,
    issues: list[Issue],
    line_offset: int = 0,
) -> None:
    """Detect security issues in Go files."""
    lines = file.content.splitlines()
    for idx, line in enumerate(lines, start=1):
        for pattern, severity, description in GO_SECURITY_PATTERNS:
            if pattern.search(line):
                _add_issue(
                    issues, file.path, idx, SECURITY, severity, description,
                    line_offset=line_offset,
                )


def _detect_rust_security(
    file: FileResult,
    issues: list[Issue],
    line_offset: int = 0,
) -> None:
    """Detect security issues in Rust files."""
    lines = file.content.splitlines()
    for idx, line in enumerate(lines, start=1):
        for pattern, severity, description in RUST_SECURITY_PATTERNS:
            if pattern.search(line):
                _add_issue(
                    issues, file.path, idx, SECURITY, severity, description,
                    line_offset=line_offset,
                )


def _detect_java_security(
    file: FileResult,
    issues: list[Issue],
    line_offset: int = 0,
) -> None:
    """Detect security issues in Java files."""
    lines = file.content.splitlines()
    for idx, line in enumerate(lines, start=1):
        for pattern, severity, description in JAVA_SECURITY_PATTERNS:
            if pattern.search(line):
                _add_issue(
                    issues, file.path, idx, SECURITY, severity, description,
                    line_offset=line_offset,
                )


def _detect_ruby_security(
    file: FileResult,
    issues: list[Issue],
    line_offset: int = 0,
) -> None:
    """Detect security issues in Ruby files."""
    lines = file.content.splitlines()
    for idx, line in enumerate(lines, start=1):
        for pattern, severity, description in RUBY_SECURITY_PATTERNS:
            if pattern.search(line):
                _add_issue(
                    issues, file.path, idx, SECURITY, severity, description,
                    line_offset=line_offset,
                )


def detect_security_issues(
    file: FileResult,
    issues: list[Issue],
    tree: ast.AST | None,
    line_offset: int = 0,
) -> None:
    """Run all security detection checks on a file."""
    _detect_generic_security(file, issues, line_offset=line_offset)

    if file.language == "python":
        _detect_python_security_regex(file, issues, line_offset=line_offset)
        if tree is not None:
            _detect_python_security_ast(file, issues, tree, line_offset=line_offset)
    elif file.language in {"javascript", "typescript"}:
        _detect_js_security(file, issues, line_offset=line_offset)
    elif file.language == "go":
        _detect_go_security(file, issues, line_offset=line_offset)
    elif file.language == "rust":
        _detect_rust_security(file, issues, line_offset=line_offset)
    elif file.language == "java":
        _detect_java_security(file, issues, line_offset=line_offset)
    elif file.language == "ruby":
        _detect_ruby_security(file, issues, line_offset=line_offset)
