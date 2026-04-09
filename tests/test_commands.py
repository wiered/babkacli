import json
from pathlib import Path

import pytest

from src.toolcall.commands import (
    CommandExecutionError,
    CommandOutcome,
    codeact,
    createFiles,
    createFolders,
    dispatch_command,
    done,
    ls,
    parse_and_dispatch_agent_response,
    readfiles,
    runpy,
    writefile,
)
from src.toolcall.json_parser import ParsedAgentCommand


@pytest.fixture()
def workspace(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    return tmp_path


def test_ls_lists_directories_before_files_sorted_case_insensitively(workspace):
    (workspace / "b-dir").mkdir()
    (workspace / "A-dir").mkdir()
    (workspace / "z.txt").write_text("z", encoding="utf-8")
    (workspace / "A.txt").write_text("a", encoding="utf-8")

    result = ls()

    assert result["path"] == "."
    assert [entry["name"] for entry in result["entries"]] == ["A-dir", "b-dir", "A.txt", "z.txt"]
    assert [entry["type"] for entry in result["entries"]] == ["dir", "dir", "file", "file"]


def test_readfiles_reads_multiple_files(workspace):
    first = workspace / "first.txt"
    second = workspace / "nested" / "second.txt"
    first.write_text("one", encoding="utf-8")
    second.parent.mkdir()
    second.write_text("two", encoding="utf-8")

    result = readfiles(["first.txt", "nested/second.txt"])

    assert result == {
        "files": [
            {"path": "first.txt", "content": "one"},
            {"path": str(Path("nested") / "second.txt"), "content": "two"},
        ]
    }


def test_writefile_creates_parent_directories_and_reports_bytes(workspace):
    result = writefile("nested/out.txt", "hello")

    assert result == {"path": str(Path("nested") / "out.txt"), "written": True, "bytes": 5}
    assert (workspace / "nested" / "out.txt").read_text(encoding="utf-8") == "hello"


def test_createFolders_creates_multiple_directories(workspace):
    result = createFolders(["src/api", "src/models"])

    assert result == {
        "folders": [
            {"path": str(Path("src") / "api"), "created": True},
            {"path": str(Path("src") / "models"), "created": True},
        ]
    }
    assert (workspace / "src" / "api").is_dir()
    assert (workspace / "src" / "models").is_dir()


def test_createFiles_creates_multiple_files_and_defaults_empty_content(workspace):
    result = createFiles(
        [
            {"path": "src/main.py", "content": "print('hi')\n"},
            {"path": "README.md"},
        ]
    )

    assert result == {
        "files": [
            {"path": str(Path("src") / "main.py"), "written": True, "bytes": len("print('hi')\n".encode("utf-8"))},
            {"path": "README.md", "written": True, "bytes": 0},
        ]
    }
    assert (workspace / "src" / "main.py").read_text(encoding="utf-8") == "print('hi')\n"
    assert (workspace / "README.md").read_text(encoding="utf-8") == ""


def test_runpy_executes_python_files_and_captures_output(workspace):
    script = workspace / "main.py"
    script.write_text(
        "import sys\n"
        "print('hello from script')\n"
        "print(sys.argv[1:])\n",
        encoding="utf-8",
    )

    result = runpy("main.py", args=["--flag"])

    assert result["path"] == "main.py"
    assert result["returncode"] == 0
    assert "hello from script" in result["stdout"]
    assert "['--flag']" in result["stdout"]


def test_runpy_handles_unicode_output(workspace):
    script = workspace / "main.py"
    script.write_text(
        "print('Исходный массив: [1, 2, 3]')\n"
        "print('Время работы quicksort: 0.000001 секунд')\n",
        encoding="utf-8",
    )

    result = runpy("main.py")

    assert result["returncode"] == 0
    assert "Исходный массив" in result["stdout"]
    assert "Время работы quicksort" in result["stdout"]


def test_runpy_returns_empty_strings_for_missing_stream_output(workspace):
    script = workspace / "main.py"
    script.write_text("", encoding="utf-8")

    result = runpy("main.py")

    assert result["stdout"] == ""
    assert result["stderr"] == ""


def test_runpy_rejects_non_python_files(workspace):
    (workspace / "main.txt").write_text("hello", encoding="utf-8")

    with pytest.raises(CommandExecutionError, match="Python file"):
        runpy("main.txt")


def test_codeact_prints_top_level_expression_stdout(workspace):
    (workspace / "shown.txt").write_text("ok", encoding="utf-8")
    result = codeact(code_lines=["ca.files.ls('.')"])
    assert result["returncode"] == 0, result["stderr"]
    assert "entries" in result["stdout"]
    assert "shown.txt" in result["stdout"]


def test_codeact_top_level_print_not_wrapped_with_repr(workspace):
    """Avoid ``print(repr(print(...)))`` appending a stray ``None`` line."""
    result = codeact(code_lines=["print('only')"])
    assert result["returncode"] == 0, result["stderr"]
    assert result["stdout"] == "only\n"
    assert "None" not in result["stdout"]


def test_codeact_long_source_uses_stdin_not_cmdline(workspace):
    """Avoid OS command-line limits when embedding huge source in ``python -c``."""
    padding = "# " + "x" * 12000
    result = codeact(code_lines=[padding, "ca.files.ls('.')"])
    assert result["returncode"] == 0, result["stderr"]
    assert "entries" in result["stdout"]


def test_codeact_runs_multistep_script(workspace):
    (workspace / "n.txt").write_text("42", encoding="utf-8")
    result = codeact(
        code_lines=[
            "paths = ['n.txt']",
            "for p in paths:",
            "    print(ca.files.read(p)['content'])",
        ]
    )
    assert result["returncode"] == 0, result["stderr"]
    assert "42" in result["stdout"]


def test_codeact_rejects_blank_code(workspace):
    with pytest.raises(CommandExecutionError, match="Provide non-empty"):
        codeact("")
    with pytest.raises(CommandExecutionError, match="Provide non-empty"):
        codeact("  \n  ")
    with pytest.raises(CommandExecutionError, match="Provide non-empty"):
        codeact(code_lines=[])
    with pytest.raises(CommandExecutionError, match="Provide non-empty"):
        codeact(code_lines=["", "  "])


def test_codeact_runs_python_with_codeact_in_project_root(monkeypatch):
    project_root = Path(__file__).resolve().parents[1]
    scratch = project_root / "test_project" / "_codeact_cmd_test.txt"
    monkeypatch.chdir(project_root)
    try:
        scratch.unlink(missing_ok=True)
        snippet = (
            "ca = CodeAct()\n"
            'ca.files.write("test_project/_codeact_cmd_test.txt", "probe")\n'
        )
        result = codeact(snippet)
        assert result["returncode"] == 0, result["stderr"]
        assert scratch.read_text(encoding="utf-8") == "probe"
    finally:
        scratch.unlink(missing_ok=True)


def test_parse_and_dispatch_executes_codeact(monkeypatch):
    project_root = Path(__file__).resolve().parents[1]
    scratch = project_root / "test_project" / "_codeact_dispatch_test.txt"
    monkeypatch.chdir(project_root)
    try:
        scratch.unlink(missing_ok=True)
        raw = json.dumps(
            {
                "command": "codeact",
                "code": (
                    'ca = CodeAct()\n'
                    'ca.files.write("test_project/_codeact_dispatch_test.txt", "x")'
                ),
            }
        )
        outcome = parse_and_dispatch_agent_response(raw)
        assert outcome.command == "codeact"
        assert outcome.data["returncode"] == 0
        assert scratch.read_text(encoding="utf-8") == "x"
    finally:
        scratch.unlink(missing_ok=True)


def test_parse_and_dispatch_codeact_prefers_code_lines(monkeypatch):
    project_root = Path(__file__).resolve().parents[1]
    scratch = project_root / "test_project" / "_codeact_lines_dispatch_test.txt"
    monkeypatch.chdir(project_root)
    try:
        scratch.unlink(missing_ok=True)
        raw = json.dumps(
            {
                "command": "codeact",
                "code_lines": [
                    'ca.files.write("test_project/_codeact_lines_dispatch_test.txt", "from_lines")',
                ],
            }
        )
        outcome = parse_and_dispatch_agent_response(raw)
        assert outcome.command == "codeact"
        assert outcome.data["returncode"] == 0
        assert scratch.read_text(encoding="utf-8") == "from_lines"
    finally:
        scratch.unlink(missing_ok=True)


def test_codeact_rejects_code_lines_non_strings():
    with pytest.raises(CommandExecutionError, match="only strings"):
        codeact(code_lines=[1, 2])


def test_done_rejects_blank_result():
    with pytest.raises(CommandExecutionError, match="non-empty string"):
        done("   ")


def test_dispatch_command_returns_normalized_outcome():
    outcome = dispatch_command(ParsedAgentCommand(command="done", arguments={"result": "ok"}))

    assert outcome == CommandOutcome(command="done", data={"result": "ok"})


def test_parse_and_dispatch_agent_response_executes_command(workspace):
    outcome = parse_and_dispatch_agent_response('{"command": "writefile", "path": "a.txt", "content": "x"}')

    assert outcome.command == "writefile"
    assert outcome.data["written"] is True
    assert (workspace / "a.txt").read_text(encoding="utf-8") == "x"
