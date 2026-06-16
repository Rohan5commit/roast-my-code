import json
import os
import re
import tempfile
import urllib.request
import urllib.error
from http.server import BaseHTTPRequestHandler
from pathlib import Path
from dataclasses import dataclass, asdict, field
from typing import List, Optional, Dict, Any

# ============================================================
# Data structures
# ============================================================

SKIP_DIRS = {"node_modules", ".git", "__pycache__", "dist", "build", "venv", ".venv", ".roast", "vendor", "testdata"}
CONFIG_EXTENSIONS = {".toml", ".yaml", ".yml", ".json", ".cfg", ".ini", ".md", ".rst", ".txt"}
MAX_FILE_LINES = 500

LANGUAGE_BY_EXTENSION = {
    ".py": "python", ".js": "javascript", ".ts": "typescript",
    ".jsx": "javascript", ".tsx": "typescript", ".rb": "ruby",
    ".go": "go", ".rs": "rust", ".java": "java", ".c": "c",
    ".cpp": "cpp", ".h": "c", ".hpp": "cpp", ".cs": "csharp",
    ".php": "php", ".swift": "swift", ".kt": "kotlin", ".scala": "scala",
}

@dataclass
class FileResult:
    path: str
    content: str
    language: str
    line_count: int

@dataclass
class Issue:
    file: str
    line: Optional[int]
    category: str
    severity: str
    description: str

@dataclass
class AnalysisReport:
    total_files: int
    total_lines: int
    issues: List[Issue]
    scores: Dict[str, int]

# ============================================================
# Scanner
# ============================================================

def _is_binary_file(path: str) -> bool:
    try:
        with open(path, "rb") as f:
            chunk = f.read(4096)
            return b"\x00" in chunk
    except Exception:
        return True

def _infer_language(path: str) -> str:
    ext = Path(path).suffix.lower()
    return LANGUAGE_BY_EXTENSION.get(ext, "unknown")

def _is_test_file(path: str) -> bool:
    lower = path.lower()
    return any(x in lower for x in ["test_", "_test.", "/test/", "/tests/", "spec.", "_spec.", "/__tests__/"])

def scan_repo(path: str, max_files: int = 50) -> List[FileResult]:
    results = []
    root = Path(path)
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS]
        rel_dir = os.path.relpath(dirpath, root)
        if rel_dir.startswith("."):
            continue
        for fname in sorted(filenames):
            if len(results) >= max_files:
                return results
            fpath = os.path.join(dirpath, fname)
            ext = Path(fname).suffix.lower()
            if ext not in LANGUAGE_BY_EXTENSION:
                continue
            if _is_binary_file(fpath):
                continue
            try:
                with open(fpath, "r", encoding="utf-8", errors="ignore") as f:
                    lines = f.readlines()
                if len(lines) > MAX_FILE_LINES:
                    continue
                rel_path = os.path.relpath(fpath, root)
                results.append(FileResult(
                    path=rel_path,
                    content="".join(lines),
                    language=_infer_language(fpath),
                    line_count=len(lines),
                ))
            except Exception:
                continue
    return results

# ============================================================
# Analyzer
# ============================================================

TODO_PATTERN = re.compile(r"#\s*(TODO|FIXME|HACK|XXX)\b", re.IGNORECASE)
PLACEHOLDER_PATTERN = re.compile(r"\b(foo|bar|baz|temp|data2|result2|test123)\b")
FAKE_IMPORTS = {"magiclib", "utils2", "codemancer", "autocodekit", "aihelpers"}
BAD_FUNCTION_NAMES = {"handle_it", "do_stuff", "process_data", "helper"}
PASSWORD_PATTERN = re.compile(r"(password|passwd|secret|api_key)\s*=\s*['\"][^'\"]+['\"]", re.IGNORECASE)
URL_PATTERN = re.compile(r"(https?://[^\s'\"]+)")
CONSOLE_LOG_PATTERN = re.compile(r"console\.(log|warn|error)\(")
PRINT_PATTERN = re.compile(r"\bprint\(")
LONG_LINE_THRESHOLD = 120
LONG_FUNCTION_LINES = 50
MAGIC_NUMBER_PATTERN = re.compile(r"\b\d{3,}\b")

def _detect_high_severity(content: str, path: str, language: str) -> List[Issue]:
    issues = []
    lines = content.split("\n")
    is_test = _is_test_file(path)

    for i, line in enumerate(lines, 1):
        if TODO_PATTERN.search(line):
            issues.append(Issue(file=path, line=i, category="AI Slop", severity="high", description="TODO/FIXME/HACK marker found"))

        if not is_test and PLACEHOLDER_PATTERN.search(line):
            issues.append(Issue(file=path, line=i, category="AI Slop", severity="high", description=f"Placeholder name detected: {line.strip()[:60]}"))

        if PASSWORD_PATTERN.search(line):
            issues.append(Issue(file=path, line=i, category="Code Quality", severity="high", description="Hardcoded password/secret/key detected"))

    if language == "python":
        for i, line in enumerate(lines, 1):
            stripped = line.strip()
            if stripped.startswith("import ") or stripped.startswith("from "):
                for fake in FAKE_IMPORTS:
                    if fake in stripped:
                        issues.append(Issue(file=path, line=i, category="AI Slop", severity="high", description=f"Fake/hallucinated import: {fake}"))

    return issues

def _detect_medium_severity(content: str, path: str, language: str) -> List[Issue]:
    issues = []
    lines = content.split("\n")
    line_count = len(lines)
    is_test = _is_test_file(path)

    if line_count > 300:
        issues.append(Issue(file=path, line=None, category="Code Quality", severity="medium", description=f"Large file: {line_count} lines"))

    if language == "python" and not is_test:
        for i, line in enumerate(lines, 1):
            if PRINT_PATTERN.search(line):
                issues.append(Issue(file=path, line=i, category="Code Quality", severity="medium", description="print() statement in non-test code"))

    if language in ("javascript", "typescript"):
        for i, line in enumerate(lines, 1):
            if CONSOLE_LOG_PATTERN.search(line):
                issues.append(Issue(file=path, line=i, category="Code Quality", severity="medium", description="console.log/warn/error left in code"))

    for i, line in enumerate(lines, 1):
        if len(line) > LONG_LINE_THRESHOLD:
            issues.append(Issue(file=path, line=i, category="Style", severity="low", description=f"Line too long ({len(line)} chars)"))

    if not is_test:
        for i, line in enumerate(lines, 1):
            stripped = line.strip()
            if URL_PATTERN.search(line) and ("'" in stripped or '"' in stripped) and not stripped.startswith("#"):
                issues.append(Issue(file=path, line=i, category="Code Quality", severity="medium", description="Hardcoded URL found"))

    return issues

def analyze(files: List[FileResult]) -> AnalysisReport:
    all_issues: List[Issue] = []
    total_lines = 0
    for f in files:
        total_lines += f.line_count
        all_issues.extend(_detect_high_severity(f.content, f.path, f.language))
        all_issues.extend(_detect_medium_severity(f.content, f.path, f.language))

    def score_for(category: str) -> int:
        cat_issues = [i for i in all_issues if i.category == category]
        high = sum(1 for i in cat_issues if i.severity == "high")
        med = sum(1 for i in cat_issues if i.severity == "medium")
        low = sum(1 for i in cat_issues if i.severity == "low")
        raw = 100 - (high * 15) - (med * 7) - (low * 2)
        return max(0, min(100, raw))

    scores = {
        "AI Slop": score_for("AI Slop"),
        "Code Quality": score_for("Code Quality"),
        "Style": score_for("Style"),
    }
    overall = round(scores["AI Slop"] * 0.5 + scores["Code Quality"] * 0.3 + scores["Style"] * 0.2)
    scores["Overall"] = max(0, min(100, overall))

    return AnalysisReport(total_files=len(files), total_lines=total_lines, issues=all_issues, scores=scores)

# ============================================================
# LLM Roast generator (NVIDIA NIM)
# ============================================================

NIM_BASE_URL = "https://integrate.api.nvidia.com/v1"
NIM_MODEL = "microsoft/phi-4-mini-instruct"

FALLBACK_ROAST_LINES_LOW = [
    "I've seen better code from a first-day bootcamp student. And I'm being generous.",
    "This code has more red flags than a bullfighting convention.",
    "If this code were a restaurant, it'd be shut down by the health inspector. Twice.",
    "I'm not saying this is bad, but I've seen better error handling in a 404 page.",
    "This codebase is what happens when you let Stack Overflow write your architecture.",
    "Somewhere, a senior developer just felt a disturbance in the force.",
    "This code is like a house of cards in a wind tunnel.",
    "If code could talk, this one would be screaming for help.",
    "This isn't code, it's a cry for help written in Python.",
    "The only thing this code is missing is a 'please don't look at me' comment.",
]

FALLBACK_ROAST_LINES_MED = [
    "It's not terrible, but it's not winning any beauty contests either.",
    "Your code is the programming equivalent of a participation trophy.",
    "I've seen worse, but I've also seen much, much better.",
    "This code is like fast food - it works, but you feel guilty about it afterward.",
    "There's potential here, buried under several layers of 'why did you do it this way?'",
]

FALLBACK_ROAST_LINES_HIGH = [
    "Well, it's not a complete disaster. I've seen worse from junior devs on day one.",
    "Your code is... acceptable. Barely. Like a C- student who studied the night before.",
    "There's a decent foundation here, but some of these choices are... choices.",
    "Not bad! A few rough edges, but who am I to judge? Oh wait, that's literally my job.",
]

def _verdict_from_score(score: int) -> tuple:
    if score >= 75:
        return "SHIP IT", " "
    if score >= 40:
        return "NEEDS WORK", " "
    return "BURN IT DOWN", " "

def _top_issues_for_prompt(report: AnalysisReport, limit: int = 10) -> List[Issue]:
    severity_order = {"high": 0, "medium": 1, "low": 2}
    return sorted(report.issues, key=lambda i: (severity_order.get(i.severity, 3), i.file, i.line or 0))[:limit]

def _worst_file(report: AnalysisReport) -> Optional[str]:
    if not report.issues:
        return None
    from collections import Counter
    counts = Counter(i.file for i in report.issues)
    return counts.most_common(1)[0][0]

def _sample_from_file(files: List[FileResult], target: Optional[str], max_lines: int = 30) -> str:
    if not target:
        return "No issues found."
    for f in files:
        if f.path == target:
            return "\n".join(f.content.splitlines()[:max_lines]) or "<empty>"
    return "Unable to locate file."

def _build_llm_prompt(report: AnalysisReport, files: List[FileResult]) -> str:
    top = _top_issues_for_prompt(report)
    issue_lines = [f"- {i.file}:{i.line or '-'} [{i.severity}] {i.description}" for i in top]
    issues_block = "\n".join(issue_lines) if issue_lines else "- No issues found."
    worst = _worst_file(report) or "None"
    sample = _sample_from_file(files, worst)
    return (
        "Here is a summary of a codebase scan:\n"
        f"- Total files: {report.total_files}, Total lines: {report.total_lines}\n"
        f"- Overall score: {report.scores.get('Overall', 0)}/100\n"
        f"- Top issues found:\n{issues_block}\n"
        f"- Worst file: {worst}\n"
        f"- Sample of actual code from worst file:\n{sample}\n\n"
        "Generate:\n"
        "1. A one-liner headline roast (funny, specific to this code)\n"
        "2. 5-6 specific roast bullets referencing actual files and issues\n"
        "3. A verdict: SHIP IT (score >= 75), NEEDS WORK (40-74), BURN IT DOWN (<40)\n"
        "4. A verdict emoji:  for SHIP IT,  for NEEDS WORK,  for BURN IT DOWN\n\n"
        "Respond strictly as JSON with keys: headline, roast_lines (array of strings), verdict, verdict_emoji."
    )

def _extract_json(content: str) -> Dict[str, Any]:
    text = content.strip()
    # Strip markdown fences if present
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*\n?", "", text)
        text = re.sub(r"\n?```\s*$", "", text)
        text = text.strip()
    try:
        obj = json.loads(text)
        if isinstance(obj, dict):
            return obj
    except json.JSONDecodeError:
        pass
    # Try to find JSON object in the text
    match = re.search(r"\{[\s\S]*\}", text)
    if match:
        raw = match.group(0)
        try:
            obj = json.loads(raw)
            if isinstance(obj, dict):
                return obj
        except json.JSONDecodeError:
            # Try fixing common JSON issues
            fixed = raw.replace("\n", " ").replace("\r", "")
            # Remove trailing commas before } or ]
            fixed = re.sub(r",\s*([}\]])", r"\1", fixed)
            # Fix unescaped quotes inside strings
            fixed = re.sub(r'(?<=[^\\])"(?=[^:}\],])', '\\"', fixed)
            try:
                obj = json.loads(fixed)
                if isinstance(obj, dict):
                    return obj
            except json.JSONDecodeError:
                pass
    raise ValueError("Model response was not valid JSON")

def _call_llm(report: AnalysisReport, files: List[FileResult]) -> Optional[Dict[str, Any]]:
    """Call NVIDIA NIM API. Returns parsed JSON or None on failure."""
    api_key = os.environ.get("NVIDIA_NIM_API_KEY") or os.environ.get("NIM_API_KEY")
    if not api_key:
        return None

    try:
        payload = json.dumps({
            "model": NIM_MODEL,
            "temperature": 0.8,
            "max_tokens": 500,
            "messages": [
                {
                    "role": "system",
                    "content": (
                        "You are a senior developer who has seen too much bad code. "
                        "You are brutally honest but funny, like a Gordon Ramsay for codebases. "
                        "Be specific, reference actual file names and issues found. Never be generic. "
                        "Keep roast lines under 25 words each. "
                        "Return strict JSON only, no markdown fences."
                    ),
                },
                {"role": "user", "content": _build_llm_prompt(report, files)},
            ],
        }).encode("utf-8")

        req = urllib.request.Request(
            f"{NIM_BASE_URL}/chat/completions",
            data=payload,
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {api_key}",
            },
        )

        with urllib.request.urlopen(req, timeout=20) as resp:
            result = json.loads(resp.read().decode("utf-8"))

        content = result.get("choices", [{}])[0].get("message", {}).get("content", "{}")
        return _extract_json(content)
    except Exception:
        return None


def _fallback_roast(report: AnalysisReport) -> Dict[str, Any]:
    """Deterministic fallback roast when LLM is unavailable."""
    score = report.scores["Overall"]
    verdict, emoji = _verdict_from_score(score)

    if score >= 75:
        headline = "Your code is... actually pretty good"
        pool = FALLBACK_ROAST_LINES_HIGH
    elif score >= 40:
        headline = "Your code needs some serious work"
        pool = FALLBACK_ROAST_LINES_MED
    else:
        headline = "Your code is a dumpster fire"
        pool = FALLBACK_ROAST_LINES_LOW

    import random
    random.seed(hash(str(report.scores)))
    num_lines = min(4, max(2, len(report.issues) // 10))
    roast_lines = random.sample(pool, min(num_lines, len(pool)))

    return {
        "headline": headline,
        "roast_lines": roast_lines,
        "verdict": verdict,
        "verdict_emoji": emoji,
    }

def generate_roast(report: AnalysisReport, files: List[FileResult]) -> Dict[str, Any]:
    score = report.scores["Overall"]
    verdict, emoji = _verdict_from_score(score)

    # Try LLM first
    llm_result = _call_llm(report, files)
    if llm_result:
        # Validate and normalize LLM response
        headline = str(llm_result.get("headline", "")).strip()
        if not headline or len(headline.split()) > 20:
            headline = _fallback_roast(report)["headline"]

        roast_lines = llm_result.get("roast_lines", [])
        if not isinstance(roast_lines, list) or len(roast_lines) < 3:
            roast_lines = _fallback_roast(report)["roast_lines"]
        roast_lines = [str(l).strip() for l in roast_lines if str(l).strip()][:8]

        llm_verdict = str(llm_result.get("verdict", "")).strip()
        if llm_verdict in ("SHIP IT", "NEEDS WORK", "BURN IT DOWN"):
            verdict = llm_verdict
            emoji = str(llm_result.get("verdict_emoji", emoji)).strip() or emoji
    else:
        fallback = _fallback_roast(report)
        headline = fallback["headline"]
        roast_lines = fallback["roast_lines"]

    file_counts: Dict[str, int] = {}
    for issue in report.issues:
        file_counts[issue.file] = file_counts.get(issue.file, 0) + 1
    hotspot_files = sorted(file_counts.items(), key=lambda x: -x[1])[:5]
    hotspot_files = [{"file": f, "count": c} for f, c in hotspot_files]

    category_counts: Dict[str, int] = {}
    severity_counts: Dict[str, int] = {}
    for issue in report.issues:
        category_counts[issue.category] = category_counts.get(issue.category, 0) + 1
        severity_counts[issue.severity] = severity_counts.get(issue.severity, 0) + 1

    return {
        "score": score,
        "headline": headline,
        "verdict": verdict,
        "verdict_emoji": emoji,
        "files_scanned": report.total_files,
        "total_lines": report.total_lines,
        "issues_count": len(report.issues),
        "issues": [asdict(i) for i in report.issues],
        "roast_lines": roast_lines,
        "hotspot_files": hotspot_files,
        "category_counts": category_counts,
        "severity_counts": severity_counts,
    }

# ============================================================
# GitHub archive download
# ============================================================

def parse_github_url(url: str):
    """Parse GitHub URL into owner, repo, ref."""
    url = url.strip().rstrip("/")
    url = re.sub(r"^https?://(www\.)?", "https://", url)
    if not url.startswith("https://"):
        url = "https://" + url

    patterns = [
        r"github\.com/([^/]+)/([^/]+)/tree/([^/]+)",
        r"github\.com/([^/]+)/([^/]+)",
    ]
    for pat in patterns:
        m = re.search(pat, url)
        if m:
            groups = m.groups()
            if len(groups) == 3:
                return groups[0], groups[1], groups[2]
            elif len(groups) == 2:
                return groups[0], groups[1], "main"
    raise ValueError("Invalid GitHub URL. Expected format: https://github.com/owner/repo")

def _validate_zip_member(dest: str, member_name: str) -> bool:
    """Check for Zip Slip path traversal."""
    target = os.path.realpath(os.path.join(dest, member_name))
    dest_real = os.path.realpath(dest)
    return target.startswith(dest_real + os.sep) or target == dest_real

def download_github_archive(owner: str, repo: str, ref: str, dest: str) -> str:
    """Download repo archive and extract to dest."""
    token = os.environ.get("GITHUB_TOKEN", "")
    url = f"https://api.github.com/repos/{owner}/{repo}/zipball/{urllib.request.quote(ref, safe='')}"
    headers = {"Accept": "application/vnd.github.v3+json"}
    if token:
        headers["Authorization"] = f"token {token}"

    req = urllib.request.Request(url, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            data = resp.read()
    except urllib.error.HTTPError as e:
        if e.code == 404:
            raise RuntimeError("Repository not found or ref does not exist.")
        elif e.code == 403:
            raise RuntimeError("GitHub API rate limit exceeded. Try again later.")
        raise RuntimeError("Failed to download repository.")

    zip_path = os.path.join(dest, "repo.zip")
    with open(zip_path, "wb") as f:
        f.write(data)

    import zipfile
    with zipfile.ZipFile(zip_path) as zf:
        for member in zf.infolist():
            if not _validate_zip_member(dest, member.filename):
                raise RuntimeError("Malformed archive detected.")
        zf.extractall(dest)

    extracted = [d for d in os.listdir(dest) if os.path.isdir(os.path.join(dest, d))]
    if not extracted:
        raise RuntimeError("No directory found in archive")
    return os.path.join(dest, extracted[0])

# ============================================================
# CORS helper
# ============================================================

ALLOWED_ORIGINS = {
    "https://roast-web-six.vercel.app",
    "http://localhost:3000",
    "http://127.0.0.1:3000",
}

def set_cors_headers(handler_instance):
    origin = handler_instance.headers.get("Origin", "")
    if origin in ALLOWED_ORIGINS:
        handler_instance.send_header("Access-Control-Allow-Origin", origin)
    handler_instance.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
    handler_instance.send_header("Access-Control-Allow-Headers", "Content-Type")

def send_json(handler_instance, status: int, data: dict):
    handler_instance.send_response(status)
    handler_instance.send_header("Content-Type", "application/json")
    set_cors_headers(handler_instance)
    handler_instance.end_headers()
    handler_instance.wfile.write(json.dumps(data).encode())

# ============================================================
# HTTP Handler
# ============================================================

MAX_REQUEST_BODY_BYTES = 8192

class handler(BaseHTTPRequestHandler):
    def do_POST(self):
        content_length = int(self.headers.get("Content-Length", 0))
        if content_length > MAX_REQUEST_BODY_BYTES:
            send_json(self, 413, {"error": "Request body too large"})
            return
        body = self.rfile.read(content_length)
        try:
            data = json.loads(body)
        except json.JSONDecodeError:
            send_json(self, 400, {"error": "Invalid JSON"})
            return

        url = data.get("url", "")
        if not url:
            send_json(self, 400, {"error": "URL is required"})
            return

        try:
            owner, repo, ref = parse_github_url(url)
        except ValueError:
            send_json(self, 400, {"error": "Invalid GitHub URL. Expected format: https://github.com/owner/repo"})
            return

        _log(f"POST /api/roast url={url}")

        try:
            with tempfile.TemporaryDirectory() as tmpdir:
                repo_path = download_github_archive(owner, repo, ref, tmpdir)
                files = scan_repo(repo_path, max_files=50)
                if not files:
                    send_json(self, 400, {"error": "No scannable code files found."})
                    return

                report = analyze(files)
                result = generate_roast(report, files)

                import hashlib
                result["id"] = hashlib.md5(url.encode()).hexdigest()[:12]
                result["url"] = url
                result["repo_name"] = f"{owner}/{repo}"
                result["created_at"] = __import__("datetime").datetime.utcnow().isoformat() + "Z"

                _log(f"POST /api/roast done score={result['score']} issues={result['issues_count']}")
                send_json(self, 200, result)

        except RuntimeError as e:
            send_json(self, 500, {"error": str(e)})
        except Exception:
            send_json(self, 500, {"error": "An unexpected error occurred during analysis."})

    def do_GET(self):
        from urllib.parse import urlparse, parse_qs
        parsed = urlparse(self.path)
        params = parse_qs(parsed.query)

        # Health check
        if self.path == "/api/roast" or self.path == "/api/roast/":
            send_json(self, 200, {
                "status": "ok",
                "message": "Roast My Code API is running",
            })
            return

        roast_id = params.get("id", [None])[0]
        if not roast_id:
            send_json(self, 400, {"error": "id parameter required"})
            return

        send_json(self, 404, {"error": "Roast results are generated on-demand. Please roast this repo again to see results."})

    def do_OPTIONS(self):
        self.send_response(200)
        set_cors_headers(self)
        self.end_headers()

    def log_message(self, format, *args):
        _log(format % args)

def _log(msg: str):
    import sys
    print(f"[roast] {msg}", file=sys.stderr)
