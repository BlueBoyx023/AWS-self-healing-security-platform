

import pytest

from scripts.devdoc.context_builder import ContextBuilder


@pytest.fixture
def repository(tmp_path):
    (tmp_path / ".git").mkdir()
    return tmp_path


@pytest.fixture
def builder(repository):
    return ContextBuilder(repository)


def test_collect_python_file(repository, builder):
    (repository / "example.py").write_text(
        "print('Hello')",
        encoding="utf-8",
    )

    report = {
        "classifications": [
            {
                "path": "example.py",
                "status": "modified",
                "categories": ["General Code"],
            }
        ]
    }

    result = builder.build(report)

    assert result["summary"]["collected_files"] == 1
    assert result["files"][0]["content"] == "print('Hello')"


def test_collect_documentation_file(repository, builder):
    (repository / "README.md").write_text(
        "# Project",
        encoding="utf-8",
    )

    result = builder.build({
        "classifications": [
            {"path": "README.md", "status": "modified"}
        ]
    })

    assert result["files"][0]["content"] == "# Project"


def test_exclude_env_file(repository, builder):
    (repository / ".env").write_text(
        "SECRET=value",
        encoding="utf-8",
    )

    result = builder.build({
        "classifications": [
            {"path": ".env", "status": "modified"}
        ]
    })

    assert result["summary"]["collected_files"] == 0
    assert result["summary"]["skipped_files"] == 1


def test_exclude_venv_directory(repository, builder):
    venv = repository / ".venv"
    venv.mkdir()
    (venv / "example.py").write_text(
        "print('test')",
        encoding="utf-8",
    )

    result = builder.build({
        "classifications": [
            {"path": ".venv/example.py", "status": "modified"}
        ]
    })

    assert result["summary"]["collected_files"] == 0


def test_exclude_unsupported_file(repository, builder):
    (repository / "image.png").write_bytes(b"image")

    result = builder.build({
        "classifications": [
            {"path": "image.png", "status": "modified"}
        ]
    })

    assert result["summary"]["collected_files"] == 0


def test_file_size_limit(repository):
    (repository / "large.py").write_text(
        "A" * 100,
        encoding="utf-8",
    )

    builder = ContextBuilder(
        repository,
        max_file_bytes=50,
    )

    result = builder.build({
        "classifications": [
            {"path": "large.py", "status": "modified"}
        ]
    })

    assert result["summary"]["collected_files"] == 0
    assert "maximum file size" in result["skipped_files"][0]["reason"]


def test_total_context_size_limit(repository):
    (repository / "first.py").write_text(
        "A" * 10,
        encoding="utf-8",
    )
    (repository / "second.py").write_text(
        "B" * 10,
        encoding="utf-8",
    )

    builder = ContextBuilder(
        repository,
        max_total_bytes=15,
    )

    result = builder.build({
        "classifications": [
            {"path": "first.py", "status": "modified"},
            {"path": "second.py", "status": "modified"},
        ]
    })

    assert result["summary"]["collected_files"] == 1
    assert result["summary"]["skipped_files"] == 1


def test_reject_invalid_report(builder):
    with pytest.raises(ValueError):
        builder.build("invalid")


def test_reject_missing_classifications(builder):
    with pytest.raises(ValueError):
        builder.build({})


def test_reject_path_traversal(repository, builder):
    outside = repository.parent / "outside.py"
    outside.write_text("secret", encoding="utf-8")

    result = builder.build({
        "classifications": [
            {"path": "../outside.py", "status": "modified"}
        ]
    })

    assert result["summary"]["collected_files"] == 0
    assert result["summary"]["skipped_files"] == 1


def test_missing_file_is_skipped(builder):
    result = builder.build({
        "classifications": [
            {"path": "missing.py", "status": "modified"}
        ]
    })

    assert result["summary"]["collected_files"] == 0
    assert result["summary"]["skipped_files"] == 1


def test_empty_classification_report(builder):
    result = builder.build({"classifications": []})

    assert result["files"] == []
    assert result["summary"]["total_files"] == 0


def test_invalid_repository_path():
    with pytest.raises(ValueError):
        ContextBuilder("nonexistent_repository_path")


def test_invalid_size_limits(repository):
    with pytest.raises(ValueError):
        ContextBuilder(repository, max_file_bytes=0)

def test_context_builder_redacts_aws_access_key(tmp_path):
    from scripts.devdoc.context_builder import ContextBuilder

    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / ".git").mkdir()

    secret = "AKIAIOSFODNN7EXAMPLE"
    (repo / "config.py").write_text(
        f'AWS_ACCESS_KEY = "{secret}"',
        encoding="utf-8",
    )

    builder = ContextBuilder(repo)

    result = builder.build({
        "baseline": "HEAD",
        "classifications": [
            {"path": "config.py", "status": "modified", "categories": []}
        ],
    })

    content = result["files"][0]["content"]

    assert secret not in content
    assert "[REDACTED]" in content
    assert "AWS access key" in result["files"][0]["secret_findings"]


def test_context_builder_skips_private_key_file(tmp_path):
    from scripts.devdoc.context_builder import ContextBuilder

    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / ".git").mkdir()

    (repo / "config.py").write_text(
        "-----BEGIN RSA PRIVATE KEY-----\n"
        "private-key-material\n"
        "-----END RSA PRIVATE KEY-----",
        encoding="utf-8",
    )

    builder = ContextBuilder(repo)

    result = builder.build({
        "baseline": "HEAD",
        "classifications": [
            {"path": "config.py", "status": "modified", "categories": []}
        ],
    })

    assert result["files"] == []
    assert result["skipped_files"][0]["reason"] == (
        "File contains private-key material."
    )


def test_context_builder_skips_encrypted_private_key_file(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / ".git").mkdir()
    (repo / "config.py").write_text(
        "-----BEGIN ENCRYPTED PRIVATE KEY-----\n"
        "synthetic-encrypted-key-material\n"
        "-----END ENCRYPTED PRIVATE KEY-----",
        encoding="utf-8",
    )

    result = ContextBuilder(repo).build({
        "classifications": [
            {"path": "config.py", "status": "modified", "categories": []}
        ],
    })

    assert result["files"] == []
    assert result["skipped_files"][0]["reason"] == (
        "File contains private-key material."
    )


def test_context_builder_redacts_github_token(tmp_path):
    from scripts.devdoc.context_builder import ContextBuilder

    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / ".git").mkdir()

    secret = "ghp_" + ("A" * 36)

    (repo / "config.py").write_text(
        f'TOKEN = "{secret}"',
        encoding="utf-8",
    )

    builder = ContextBuilder(repo)

    result = builder.build({
        "baseline": "HEAD",
        "classifications": [
            {"path": "config.py", "status": "modified", "categories": []}
        ],
    })

    content = result["files"][0]["content"]

    assert secret not in content
    assert "[REDACTED]" in content


def test_context_builder_never_returns_detected_secret(tmp_path):
    from scripts.devdoc.context_builder import ContextBuilder

    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / ".git").mkdir()

    secret = "example_api_key_value_12345"

    (repo / "config.py").write_text(
        f'api_key = "{secret}"',
        encoding="utf-8",
    )

    builder = ContextBuilder(repo)

    result = builder.build({
        "baseline": "HEAD",
        "classifications": [
            {"path": "config.py", "status": "modified", "categories": []}
        ],
    })

    assert secret not in str(result)


@pytest.mark.parametrize(
    ("name", "secret"),
    [
        ("STRIPE_SECRET_KEY", "sk_" + "live_" + "syntheticvalue1234567890"),
        ("SLACK_BOT_TOKEN", "xoxb-1234567890-synthetic"),
        ("CLIENT_SECRET", "synthetic-client-secret-value"),
        ("AWS_SESSION_TOKEN", "synthetic-aws-session-token-value"),
    ],
)
def test_context_builder_redacts_additional_credentials(tmp_path, name, secret):
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / ".git").mkdir()
    (repo / "config.py").write_text(
        f'{name} = "{secret}"',
        encoding="utf-8",
    )

    result = ContextBuilder(repo).build({
        "classifications": [
            {"path": "config.py", "status": "modified", "categories": []}
        ],
    })

    assert secret not in str(result)
    assert "[REDACTED]" in result["files"][0]["content"]
