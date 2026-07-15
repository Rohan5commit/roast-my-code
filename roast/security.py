"""Security vulnerability detection for roast-my-code."""

from __future__ import annotations

import ast
import re

from roast.analyzer import Issue, SECURITY, _add_issue
from roast.scanner import FileResult

# ---------------------------------------------------------------------------
# Regex patterns (language-agnostic)
# ---------------------------------------------------------------------------

HARDCODED_SECRET_PATTERNS = [
    (re.compile(r"password\s*=\s*[\"'][^\"']+[\"']", re.IGNORECASE), "Hardcoded password detected."),
    (re.compile(r"api_key\s*=\s*[\"'][^\"']+[\"']", re.IGNORECASE), "Hardcoded API key detected."),
    (re.compile(r"secret\s*=\s*[\"'][^\"']+[\"']", re.IGNORECASE), "Hardcoded secret detected."),
    (re.compile(r"token\s*=\s*[\"'][^\"']+[\"']", re.IGNORECASE), "Hardcoded token detected."),
    (re.compile(r"aws_secret_access_key\s*=\s*[\"'][^\"']+[\"']", re.IGNORECASE), "AWS secret access key hardcoded."),
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
                    )

        # assert used for validation in non-test files
        if isinstance(node, ast.Assert):
            if not _is_test_file(file.path):
                _add_issue(
                    issues,
                    file.path,
                    getattr(node, "lineno", None),
                    SECURITY,
                    "medium",
                    "assert used for validation — asserts are stripped in optimized mode (-O).",
                )


def _detect_python_security_regex(
    file: FileResult,
    issues: list[Issue],
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
            )


def _detect_js_security(
    file: FileResult,
    issues: list[Issue],
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
                )


def _detect_generic_security(
    file: FileResult,
    issues: list[Issue],
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


def _is_test_file(path: str) -> bool:
    lowered = path.lower()
    return "test" in lowered or "/tests/" in lowered or lowered.startswith("tests/")


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------


def detect_security_issues(
    file: FileResult,
    issues: list[Issue],
    tree: ast.AST | None,
) -> None:
    """Run all security detection checks on a file."""
    _detect_generic_security(file, issues)

    if file.language == "python":
        _detect_python_security_regex(file, issues)
        if tree is not None:
            _detect_python_security_ast(file, issues, tree)
    elif file.language in {"javascript", "typescript"}:
        _detect_js_security(file, issues)
