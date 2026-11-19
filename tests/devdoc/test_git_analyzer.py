import subprocess

import pytest

from scripts.devdoc.git_analyzer import GitChangeAnalyzer


@pytest.fixture
def git_repo(tmp_path):
    subprocess.run(
        ["git", "init"],
        cwd=tmp_path,
        check=True,
        capture_output=True,
    )

    subprocess.run(
        ["git", "config", "user.name", "DevDoc Test"],
        cwd=tmp_path,
        check=True,
    )

    subprocess.run(
        ["git", "config", "user.email", "devdoc-test@example.com"],
        cwd=tmp_path,
        check=True,
    )

    (tmp_path / "README.md").write_text(
        "# Test Project\n",
        encoding="utf-8",
    )

    (tmp_path / "lambda").mkdir()
    (tmp_path / "lambda" / "remediation.py").write_text(
        "def remediate():\n    pass\n",
        encoding="utf-8",
    )

    subprocess.run(
        ["git", "add", "."],
        cwd=tmp_path,
        check=True,
    )

    subprocess.run(
        ["git", "commit", "-m", "Initial commit"],
        cwd=tmp_path,
        check=True,
        capture_output=True,
    )

    return tmp_path


def test_detects_modified_file(git_repo):
    (git_repo / "README.md").write_text(
        "# Updated Project\n",
        encoding="utf-8",
    )

    analyzer = GitChangeAnalyzer(git_repo)
    result = analyzer.analyze("HEAD")

    assert any(
        change["path"] == "README.md"
        and change["status"] == "modified"
        for change in result["changes"]
    )


def test_detects_added_file(git_repo):
    (git_repo / "new_module.py").write_text(
        "VALUE = 1\n",
        encoding="utf-8",
    )

    analyzer = GitChangeAnalyzer(git_repo)
    result = analyzer.analyze("HEAD")

    assert any(
        change["path"] == "new_module.py"
        and change["status"] == "added"
        for change in result["changes"]
    )


def test_detects_deleted_file(git_repo):
    (git_repo / "README.md").unlink()

    analyzer = GitChangeAnalyzer(git_repo)
    result = analyzer.analyze("HEAD")

    assert any(
        change["path"] == "README.md"
        and change["status"] == "deleted"
        for change in result["changes"]
    )


def test_detects_renamed_file(git_repo):
    (git_repo / "README.md").rename(
        git_repo / "PROJECT_README.md"
    )

    analyzer = GitChangeAnalyzer(git_repo)
    result = analyzer.analyze("HEAD")

    assert any(
        change["status"] == "renamed"
        and change["old_path"] == "README.md"
        and change["path"] == "PROJECT_README.md"
        for change in result["changes"]
    )


def test_rejects_invalid_git_reference(git_repo):
    analyzer = GitChangeAnalyzer(git_repo)

    with pytest.raises(ValueError):
        analyzer.analyze("invalid-reference")


def test_excludes_secret_files(git_repo):
    (git_repo / ".env").write_text(
        "API_KEY=secret-value\n",
        encoding="utf-8",
    )

    analyzer = GitChangeAnalyzer(git_repo)
    result = analyzer.analyze("HEAD")

    assert not any(
        change["path"] == ".env"
        for change in result["changes"]
    )


def test_excludes_generated_files(git_repo):
    generated = git_repo / "__pycache__"
    generated.mkdir()

    (generated / "module.pyc").write_bytes(b"generated")

    analyzer = GitChangeAnalyzer(git_repo)
    result = analyzer.analyze("HEAD")

    assert not any(
        "__pycache__" in change["path"]
        for change in result["changes"]
    )


def test_returns_structured_report(git_repo):
    (git_repo / "README.md").write_text(
        "# Changed\n",
        encoding="utf-8",
    )

    analyzer = GitChangeAnalyzer(git_repo)
    result = analyzer.analyze("HEAD")

    assert result["baseline"] == "HEAD"
    assert isinstance(result["changes"], list)
    assert isinstance(result["summary"], dict)
    assert result["summary"]["total_changes"] == 1
