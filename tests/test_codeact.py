from pathlib import Path

import pytest

from src.codeact.codeact import CodeAct
from src.codeact.files import CodeActFiles, CodeActFilesError


@pytest.fixture()
def workspace(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    return tmp_path


def test_codeact_exposes_stable_code_act_files_instance():
    actor = CodeAct()
    first = actor.files
    second = actor.files

    assert isinstance(first, CodeActFiles)
    assert first is second


def test_codeact_ls_matches_expected_shape(workspace):
    (workspace / "sub").mkdir()
    (workspace / "readme.txt").write_text("x", encoding="utf-8")

    result = CodeAct().files.ls(".")

    assert result["path"] == "."
    names = {e["name"] for e in result["entries"]}
    assert names >= {"sub", "readme.txt"}


def test_codeact_ls_respects_ignore_for_directories(workspace):
    (workspace / "keep").mkdir()
    (workspace / "skip_me").mkdir()
    (workspace / "note.txt").write_text("", encoding="utf-8")

    result = CodeAct().files.ls(".", ignore=["skip_me"])
    names = [e["name"] for e in result["entries"]]

    assert "skip_me" not in names
    assert "keep" in names
    assert "note.txt" in names


def test_codeact_read_and_write_round_trip(workspace):
    files = CodeAct().files
    files.write("nested/x.txt", "hello")

    assert files.read("nested/x.txt") == {
        "path": str(Path("nested") / "x.txt"),
        "content": "hello",
    }


def test_codeact_create_file_and_directory(workspace):
    files = CodeAct().files

    assert files.create("a/b", is_directory=True) == {
        "path": str(Path("a") / "b"),
        "created": True,
    }
    assert (workspace / "a" / "b").is_dir()

    assert files.create("a/c.txt", "hi") == {
        "path": str(Path("a") / "c.txt"),
        "written": True,
        "bytes": 2,
    }
    assert (workspace / "a" / "c.txt").read_text(encoding="utf-8") == "hi"


def test_codeact_create_directory_rejects_non_empty_content():
    with pytest.raises(CodeActFilesError, match="non-empty content"):
        CodeAct().files.create("x", "oops", is_directory=True)


def test_codeact_delete_file_and_directory_tree(workspace):
    files = CodeAct().files
    files.write("t.txt", "")
    (workspace / "d").mkdir()
    (workspace / "d" / "inner.txt").write_text("z", encoding="utf-8")

    assert files.delete("t.txt") == {"path": "t.txt", "deleted": True}
    assert not (workspace / "t.txt").exists()

    assert files.delete("d") == {"path": "d", "deleted": True}
    assert not (workspace / "d").exists()


def test_codeact_delete_rejects_workspace_root(workspace):
    with pytest.raises(CodeActFilesError, match="workspace root"):
        CodeAct().files.delete(".")
