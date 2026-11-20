

import pytest

from scripts.devdoc.secret_scanner import SecretScanner


@pytest.fixture
def scanner():
    return SecretScanner()


def test_clean_content_has_no_findings(scanner):
    content = "Ordinary project documentation."

    result = scanner.scan(content)

    assert result.findings == []
    assert result.redacted_content == content
    assert result.contains_private_key is False


def test_detects_aws_access_key(scanner):
    secret = "AKIAIOSFODNN7EXAMPLE"
    result = scanner.scan(f"AWS key: {secret}")

    assert secret not in result.redacted_content
    assert "AWS access key" in result.findings


def test_detects_and_redacts_aws_secret_access_key(scanner):
    secret = "a" * 40
    result = scanner.scan(f'aws_secret_access_key = "{secret}"')

    assert secret not in result.redacted_content
    assert "[REDACTED]" in result.redacted_content


def test_detects_github_token(scanner):
    secret = "ghp_" + ("A" * 36)
    result = scanner.scan(f"token = {secret}")

    assert secret not in result.redacted_content
    assert "GitHub token" in result.findings


def test_detects_github_fine_grained_token(scanner):
    secret = "github_pat_" + ("A" * 30)
    result = scanner.scan(f"token = {secret}")

    assert secret not in result.redacted_content


def test_detects_and_redacts_generic_api_key(scanner):
    secret = "example_api_key_value_12345"
    result = scanner.scan(f'api_key = "{secret}"')

    assert secret not in result.redacted_content


def test_detects_and_redacts_password(scanner):
    secret = "ExamplePassword123"
    result = scanner.scan(f'password = "{secret}"')

    assert secret not in result.redacted_content


def test_detects_and_redacts_bearer_token(scanner):
    secret = "A" * 32
    result = scanner.scan(f"Authorization: Bearer {secret}")

    assert secret not in result.redacted_content


def test_detects_private_key_material(scanner):
    content = """
-----BEGIN RSA PRIVATE KEY-----
example-private-key-material
-----END RSA PRIVATE KEY-----
"""
    result = scanner.scan(content)

    assert result.contains_private_key is True
    assert "example-private-key-material" not in result.redacted_content


def test_redacts_multiple_secrets(scanner):
    aws_key = "AKIAIOSFODNN7EXAMPLE"
    github_token = "ghp_" + ("B" * 36)

    result = scanner.scan(f"AWS={aws_key}\nGitHub={github_token}")

    assert aws_key not in result.redacted_content
    assert github_token not in result.redacted_content


def test_preserves_surrounding_content(scanner):
    result = scanner.scan(
        "Configuration example: AKIAIOSFODNN7EXAMPLE\nEnd of file."
    )

    assert "Configuration example:" in result.redacted_content
    assert "End of file." in result.redacted_content


def test_rejects_non_string_content(scanner):
    with pytest.raises(ValueError):
        scanner.scan(123)


def test_empty_content_is_valid(scanner):
    result = scanner.scan("")

    assert result.redacted_content == ""
    assert result.findings == []


def test_detects_aws_temporary_access_key(scanner):
    secret = "ASIA1234567890ABCDEF"
    result = scanner.scan(f"AWS_ACCESS_KEY_ID={secret}")

    assert secret not in result.redacted_content
    assert "AWS access key" in result.findings


def test_detects_unquoted_password(scanner):
    secret = "ExamplePassword123"
    result = scanner.scan(f"password={secret}")

    assert secret not in result.redacted_content


def test_detects_unquoted_api_key(scanner):
    secret = "example_api_key_value_12345"
    result = scanner.scan(f"api_key={secret}")

    assert secret not in result.redacted_content


def test_detects_pkcs8_private_key(scanner):
    content = """
-----BEGIN PRIVATE KEY-----
example-private-key-material
-----END PRIVATE KEY-----
"""
    result = scanner.scan(content)

    assert result.contains_private_key is True


def test_detects_incomplete_private_key_block(scanner):
    content = """
-----BEGIN RSA PRIVATE KEY-----
example-private-key-material
"""
    result = scanner.scan(content)

    assert result.contains_private_key is True


def test_clean_aws_documentation_is_preserved(scanner):
    content = """
AWS_ACCESS_KEY_ID is an environment variable.
Use IAM roles instead of storing credentials.
"""
    result = scanner.scan(content)

    assert result.redacted_content == content
    assert result.findings == []
