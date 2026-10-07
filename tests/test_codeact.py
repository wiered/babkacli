from pathlib import Path

import pytest

from src.codeact.codeact import CodeAct
from src.codeact.files import CodeActFiles, CodeActFilesError
from src.codeact.search import CodeActSearch, CodeActSearchError


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


def test_codeact_exposes_stable_code_act_search_instance():
    actor = CodeAct()
    first = actor.search
    second = actor.search

    assert isinstance(first, CodeActSearch)
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


def test_codeact_ls_multiple_paths_applies_ignore(workspace):
    for name in ["src", "tests"]:
        (workspace / name / "skip").mkdir(parents=True)
        (workspace / name / "keep.txt").write_text("", encoding="utf-8")
    files = CodeAct().files
    result = files.ls(paths=["tests", "src"], ignore=["skip"])
    assert result == {
        "directories": [files.ls(name, ignore=["skip"]) for name in ["tests", "src"]]
    }
    assert all(
        [entry["name"] for entry in directory["entries"]] == ["keep.txt"]
        for directory in result["directories"]
    )


@pytest.mark.parametrize("paths", [[], "src", [""], [1]])
def test_codeact_ls_rejects_invalid_paths(paths):
    with pytest.raises(CodeActFilesError, match="'paths'"):
        CodeAct().files.ls(paths=paths)


def test_codeact_read_and_write_round_trip(workspace):
    files = CodeAct().files
    files.write("nested/x.txt", "hello")

    assert files.read("nested/x.txt") == {
        "path": str(Path("nested") / "x.txt"),
        "content": "hello",
    }


def test_codeact_readfiles_reads_multiple(workspace):
    files = CodeAct().files
    files.write("a.txt", "one")
    files.write("sub/b.txt", "two")

    out = files.readfiles(["a.txt", "sub/b.txt"])
    assert out == {
        "files": [
            {"path": "a.txt", "content": "one"},
            {"path": str(Path("sub") / "b.txt"), "content": "two"},
        ],
    }


def test_codeact_readfiles_rejects_empty_paths():
    with pytest.raises(CodeActFilesError, match="non-empty"):
        CodeAct().files.readfiles([])


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


def test_codeact_search_grep(workspace):
    (workspace / "a.txt").write_text("one\ntwo\nthree\n", encoding="utf-8")
    (workspace / "sub").mkdir()
    (workspace / "sub" / "b.txt").write_text("two here\n", encoding="utf-8")

    s = CodeAct().search
    hits = s.search(r"two", ".")["matches"]
    paths_lines = {(m["path"], m["line"], m["text"]) for m in hits}
    assert ("a.txt", 2, "two") in paths_lines
    assert ("sub/b.txt", 1, "two here") in paths_lines


def test_codeact_search_rejects_bad_regex(workspace):
    with pytest.raises(CodeActSearchError, match="Invalid regular expression"):
        CodeAct().search.search("(")


def test_codeact_findfiles_substring_and_glob(workspace):
    (workspace / "foo.py").write_text("", encoding="utf-8")
    (workspace / "bar").mkdir()
    (workspace / "bar" / "foo_utils.txt").write_text("", encoding="utf-8")

    s = CodeAct().search
    assert "foo.py" in s.findfiles("foo")["files"]
    assert s.findfiles("*.py")["files"] == ["foo.py"]
    assert s.findfiles("bar/*.txt")["files"] == ["bar/foo_utils.txt"]


def test_codeact_readfolder_tree(workspace):
    (workspace / "pkg").mkdir()
    (workspace / "pkg" / "mod.py").write_text("", encoding="utf-8")

    tree = CodeAct().search.readfolder(".", max_depth=3)["tree"]
    assert tree["name"] == "."
    assert tree["type"] == "dir"
    names = {c["name"] for c in tree["children"]}
    assert "pkg" in names
    pkg = next(c for c in tree["children"] if c["name"] == "pkg")
    assert pkg["children"][0]["name"] == "mod.py"


def test_codeact_readfolder_truncates(workspace):
    for i in range(20):
        (workspace / f"f{i}.txt").write_text("", encoding="utf-8")

    out = CodeAct().search.readfolder(".", max_depth=2, max_entries=5)
    assert out["truncated"] is True
