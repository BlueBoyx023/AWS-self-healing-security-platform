import subprocess

import pytest

from scripts.devdoc.change_classifier import ChangeClassifier
from scripts.devdoc.context_builder import ContextBuilder
from scripts.devdoc.git_analyzer import GitChangeAnalyzer


def git(repository, *arguments):
    return subprocess.run(
        ["git", *arguments],
        cwd=repository,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()


def commit_all(repository, message):
    git(repository, "add", "--all")
    git(repository, "commit", "-m", message)


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


def test_detects_committed_changes_after_baseline(git_repo):
    baseline = git(git_repo, "rev-parse", "HEAD")
    (git_repo / "README.md").write_text("# Committed change\n", encoding="utf-8")
    commit_all(git_repo, "Change documentation")

    result = GitChangeAnalyzer(git_repo).analyze(baseline)

    assert result["changes"] == [
        {"path": "README.md", "status": "modified"}
    ]


def test_detects_committed_added_file(git_repo):
    baseline = git(git_repo, "rev-parse", "HEAD")
    (git_repo / "committed_addition.py").write_text("VALUE = 1\n", encoding="utf-8")
    commit_all(git_repo, "Add module")

    result = GitChangeAnalyzer(git_repo).analyze(baseline)

    assert result["changes"] == [
        {"path": "committed_addition.py", "status": "added"}
    ]


def test_detects_committed_deleted_file(git_repo):
    baseline = git(git_repo, "rev-parse", "HEAD")
    (git_repo / "README.md").unlink()
    commit_all(git_repo, "Delete documentation")

    result = GitChangeAnalyzer(git_repo).analyze(baseline)

    assert result["changes"] == [
        {"path": "README.md", "status": "deleted"}
    ]


def test_detects_committed_rename(git_repo):
    baseline = git(git_repo, "rev-parse", "HEAD")
    git(git_repo, "mv", "README.md", "PROJECT_README.md")
    commit_all(git_repo, "Rename documentation")

    result = GitChangeAnalyzer(git_repo).analyze(baseline)

    assert result["changes"] == [
        {
            "path": "PROJECT_README.md",
            "old_path": "README.md",
            "status": "renamed",
        }
    ]


def test_detects_staged_and_unstaged_changes_together(git_repo):
    (git_repo / "README.md").write_text("# Staged version\n", encoding="utf-8")
    git(git_repo, "add", "README.md")
    (git_repo / "lambda" / "remediation.py").write_text(
        "def remediate():\n    return True\n", encoding="utf-8"
    )

    result = GitChangeAnalyzer(git_repo).analyze("HEAD")

    assert {(item["path"], item["status"]) for item in result["changes"]} == {
        ("README.md", "modified"),
        ("lambda/remediation.py", "modified"),
    }


def test_includes_committed_staged_unstaged_and_untracked_changes(git_repo):
    baseline = git(git_repo, "rev-parse", "HEAD")
    (git_repo / "lambda" / "remediation.py").write_text(
        "def remediate():\n    return 'committed'\n", encoding="utf-8"
    )
    commit_all(git_repo, "Commit remediation change")

    (git_repo / "README.md").write_text("# Staged\n", encoding="utf-8")
    git(git_repo, "add", "README.md")
    (git_repo / "README.md").write_text("# Unstaged\n", encoding="utf-8")
    new_file = git_repo / "untracked docs" / "notes.md"
    new_file.parent.mkdir()
    new_file.write_text("# Notes\n", encoding="utf-8")

    result = GitChangeAnalyzer(git_repo).analyze(baseline)
    actual = {(item["path"], item["status"]) for item in result["changes"]}

    assert actual == {
        ("README.md", "modified"),
        ("lambda/remediation.py", "modified"),
        ("untracked docs/notes.md", "added"),
    }
    assert len(result["changes"]) == len(actual)


def test_uses_merge_base_for_diverged_baseline(git_repo):
    common_commit = git(git_repo, "rev-parse", "HEAD")
    git(git_repo, "branch", "baseline")

    (git_repo / "baseline_only.py").write_text("BASELINE = True\n", encoding="utf-8")
    commit_all(git_repo, "Commit on baseline branch")

    git(git_repo, "checkout", "-b", "feature", common_commit)
    (git_repo / "feature_only.py").write_text("FEATURE = True\n", encoding="utf-8")
    commit_all(git_repo, "Commit on feature branch")

    result = GitChangeAnalyzer(git_repo).analyze("baseline")

    assert result["changes"] == [
        {"path": "feature_only.py", "status": "added"}
    ]


@pytest.mark.parametrize("baseline", [None, "", "missing-reference"])
def test_rejects_missing_baseline(git_repo, baseline):
    with pytest.raises(ValueError):
        GitChangeAnalyzer(git_repo).analyze(baseline)


def test_rejects_baseline_without_merge_base(git_repo):
    unrelated_baseline = git(git_repo, "rev-parse", "HEAD")
    git(git_repo, "checkout", "--orphan", "unrelated")
    (git_repo / "unrelated.txt").write_text("unrelated history\n", encoding="utf-8")
    commit_all(git_repo, "Unrelated root commit")

    with pytest.raises(ValueError):
        GitChangeAnalyzer(git_repo).analyze(unrelated_baseline)


def test_deleted_files_are_not_included_as_context(git_repo):
    (git_repo / "README.md").unlink()

    report = GitChangeAnalyzer(git_repo).analyze("HEAD")
    context = ContextBuilder(git_repo).build(ChangeClassifier().classify(report))

    assert report["changes"] == [{"path": "README.md", "status": "deleted"}]
    assert context["files"] == []
    assert context["skipped_files"][0]["path"] == "README.md"
