from pathlib import Path

from src.cli import main, run_once


def test_run_once_executes_agent_command():
    result = run_once('{"command": "done", "result": "ok"}')

    assert result == {"command": "done", "result": "ok"}


def test_main_once_uses_workspace_directory(tmp_path, capsys):
    workspace = tmp_path / "test_project"

    exit_code = main(
        [
            "--workspace",
            str(workspace),
            "--once",
            '{"command": "writefile", "path": "nested/out.txt", "content": "hi"}',
        ]
    )

    captured = capsys.readouterr()

    assert exit_code == 0
    assert Path.cwd() == workspace.resolve()
    assert (workspace / "nested" / "out.txt").read_text(encoding="utf-8") == "hi"
    assert '"written": true' in captured.out
