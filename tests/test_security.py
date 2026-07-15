"""Tests for security module."""

from roast.analyzer import SECURITY, analyze
from roast.scanner import FileResult


def test_eval_usage_generates_security_issue() -> None:
    file = FileResult(
        path="app/utils.py",
        content='result = eval(user_input)\n',
        language="python",
        line_count=1,
    )
    report = analyze([file])
    sec_issues = [
        i for i in report.issues
        if i.category == SECURITY and "eval()" in i.description
    ]
    assert len(sec_issues) == 1
    assert sec_issues[0].severity == "high"


def test_exec_usage_generates_security_issue() -> None:
    file = FileResult(
        path="app/danger.py",
        content='exec(dynamic_code)\n',
        language="python",
        line_count=1,
    )
    report = analyze([file])
    sec_issues = [
        i for i in report.issues
        if i.category == SECURITY and "exec()" in i.description
    ]
    assert len(sec_issues) == 1


def test_hardcoded_password_generates_security_issue() -> None:
    file = FileResult(
        path="config.py",
        content='password = "supersecret123"\n',
        language="python",
        line_count=1,
    )
    report = analyze([file])
    sec_issues = [
        i for i in report.issues
        if i.category == SECURITY and "Hardcoded password" in i.description
    ]
    assert len(sec_issues) >= 1


def test_hardcoded_api_key_generates_security_issue() -> None:
    file = FileResult(
        path="config.py",
        content='api_key = "sk-1234567890abcdef"\n',
        language="python",
        line_count=1,
    )
    report = analyze([file])
    sec_issues = [
        i for i in report.issues
        if i.category == SECURITY and "API key" in i.description
    ]
    assert len(sec_issues) >= 1


def test_sql_injection_generates_security_issue() -> None:
    file = FileResult(
        path="db.py",
        content='cursor.execute(f"SELECT * FROM users WHERE id = {user_id}")\n',
        language="python",
        line_count=1,
    )
    report = analyze([file])
    sec_issues = [
        i for i in report.issues
        if i.category == SECURITY and "SQL injection" in i.description
    ]
    assert len(sec_issues) == 1


def test_shell_true_generates_security_issue() -> None:
    file = FileResult(
        path="utils.py",
        content='subprocess.run(cmd, shell=True)\n',
        language="python",
        line_count=1,
    )
    report = analyze([file])
    sec_issues = [
        i for i in report.issues
        if i.category == SECURITY and "shell=True" in i.description
    ]
    assert len(sec_issues) == 1


def test_os_system_generates_security_issue() -> None:
    file = FileResult(
        path="utils.py",
        content='os.system(command)\n',
        language="python",
        line_count=1,
    )
    report = analyze([file])
    sec_issues = [
        i for i in report.issues
        if i.category == SECURITY and "os.system()" in i.description
    ]
    assert len(sec_issues) == 1


def test_pickle_usage_generates_security_issue() -> None:
    file = FileResult(
        path="data.py",
        content='data = pickle.loads(raw_bytes)\n',
        language="python",
        line_count=1,
    )
    report = analyze([file])
    sec_issues = [
        i for i in report.issues
        if i.category == SECURITY and "pickle" in i.description
    ]
    assert len(sec_issues) == 1


def test_yaml_load_generates_security_issue() -> None:
    file = FileResult(
        path="config.py",
        content='data = yaml.load(raw_yaml)\n',
        language="python",
        line_count=1,
    )
    report = analyze([file])
    sec_issues = [
        i for i in report.issues
        if i.category == SECURITY and "yaml.load()" in i.description
    ]
    assert len(sec_issues) == 1


def test_js_eval_generates_security_issue() -> None:
    file = FileResult(
        path="app.js",
        content='eval(userCode)\n',
        language="javascript",
        line_count=1,
    )
    report = analyze([file])
    sec_issues = [
        i for i in report.issues
        if i.category == SECURITY and "eval()" in i.description
    ]
    assert len(sec_issues) == 1


def test_js_innerhtml_generates_security_issue() -> None:
    file = FileResult(
        path="app.js",
        content='element.innerHTML = userInput\n',
        language="javascript",
        line_count=1,
    )
    report = analyze([file])
    sec_issues = [
        i for i in report.issues
        if i.category == SECURITY and "innerHTML" in i.description
    ]
    assert len(sec_issues) == 1


def test_clean_code_has_no_security_issues() -> None:
    file = FileResult(
        path="app.py",
        content='def greet(name: str) -> str:\n    return f"Hello, {name}"\n',
        language="python",
        line_count=2,
    )
    report = analyze([file])
    sec_issues = [i for i in report.issues if i.category == SECURITY]
    assert len(sec_issues) == 0


def test_security_score_in_report() -> None:
    file = FileResult(
        path="bad.py",
        content='eval(x)\nexec(y)\nos.system(cmd)\n',
        language="python",
        line_count=3,
    )
    report = analyze([file])
    assert SECURITY in report.scores
    assert report.scores[SECURITY] < 100


def test_security_score_affects_overall() -> None:
    secure_file = FileResult(
        path="clean.py",
        content='x = 1\n',
        language="python",
        line_count=1,
    )
    insecure_file = FileResult(
        path="bad.py",
        content='eval(x)\nexec(y)\nos.system(cmd)\npassword = "123"\n',
        language="python",
        line_count=4,
    )
    clean_report = analyze([secure_file])
    bad_report = analyze([insecure_file])
    assert bad_report.scores["Overall"] < clean_report.scores["Overall"]
