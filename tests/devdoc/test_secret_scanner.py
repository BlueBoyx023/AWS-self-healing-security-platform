

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


@pytest.mark.parametrize("key_type", ["EC", "OPENSSH", "DSA"])
def test_detects_and_redacts_additional_private_key_formats(scanner, key_type):
    material = f"synthetic-{key_type.lower()}-private-key-material"
    content = (
        f"-----BEGIN {key_type} PRIVATE KEY-----\n"
        f"{material}\n"
        f"-----END {key_type} PRIVATE KEY-----"
    )

    result = scanner.scan(content)

    assert result.contains_private_key is True
    assert "Private key material" in result.findings
    assert "[REDACTED]" in result.redacted_content
    assert material not in result.redacted_content


def test_detects_incomplete_private_key_block(scanner):
    content = """
-----BEGIN RSA PRIVATE KEY-----
example-private-key-material
"""
    result = scanner.scan(content)

    assert result.contains_private_key is True


@pytest.mark.parametrize(
    ("name", "value"),
    [
        ("STRIPE_SECRET_KEY", "sk_" + "live_" + "syntheticvalue1234567890"),
        ("SLACK_BOT_TOKEN", "xoxb-1234567890-synthetic"),
        ("CLIENT_SECRET", "synthetic-client-secret-value"),
        ("SECRET", "synthetic-generic-secret-value"),
        ("AWS_SESSION_TOKEN", "synthetic-aws-session-token-value"),
    ],
)
def test_detects_and_redacts_additional_credential_assignments(
    scanner,
    name,
    value,
):
    result = scanner.scan(f'{name} = "{value}"')

    assert value not in result.redacted_content
    assert "[REDACTED]" in result.redacted_content
    assert result.findings


def test_redacted_credential_placeholder_is_not_a_new_finding(scanner):
    result = scanner.scan('api_key = "[REDACTED]"')

    assert result.findings == []
    assert result.redacted_content == 'api_key = "[REDACTED]"'


def test_detects_and_redacts_unassigned_provider_tokens(scanner):
    stripe_key = "sk_" + "live_" + "syntheticvalue1234567890"
    slack_token = "xoxb-1234567890-synthetic"

    result = scanner.scan(f"{stripe_key}\n{slack_token}")

    assert stripe_key not in result.redacted_content
    assert slack_token not in result.redacted_content
    assert "Stripe API key" in result.findings
    assert "Slack token" in result.findings


def test_detects_encrypted_private_key_material(scanner):
    content = (
        "-----BEGIN ENCRYPTED PRIVATE KEY-----\n"
        "synthetic-encrypted-private-key-material\n"
        "-----END ENCRYPTED PRIVATE KEY-----"
    )

    result = scanner.scan(content)

    assert result.contains_private_key is True
    assert "synthetic-encrypted-private-key-material" not in result.redacted_content


def test_clean_aws_documentation_is_preserved(scanner):
    content = """
AWS_ACCESS_KEY_ID is an environment variable.
Use IAM roles instead of storing credentials.
"""
    result = scanner.scan(content)

    assert result.redacted_content == content
    assert result.findings == []


@pytest.mark.parametrize("value", [
    "postgresql://dev_user:synthetic-password@db.example.test:5432/app",
    "mysql://dev_user:synthetic-password@db.example.test/app",
    "mariadb://dev_user:synthetic-password@db.example.test:3306/app",
    "mongodb://dev_user:synthetic-password@db.example.test:27017/app?authSource=admin",
    "mongodb+srv://dev_user:synthetic-password@cluster.example.test/app?retryWrites=true&w=majority",
    "redis://dev_user:synthetic-password@cache.example.test:6379/0",
])
def test_detects_and_redacts_database_connection_credentials(scanner, value):
    result = scanner.scan(value)
    assert "synthetic-password" not in result.redacted_content
    assert value not in result.redacted_content
    assert "Database connection string" in result.findings


def test_detects_and_redacts_jwt_like_credential(scanner):
    token = "eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiJzeW50aGV0aWMifQ.synthetic-signature"
    result = scanner.scan("credential=" + token)
    assert token not in result.redacted_content
    assert "JWT-like token" in result.findings


def test_redacts_credentials_embedded_in_https_url(scanner):
    value = "https://synthetic-user:synthetic-password@example.test/path"
    result = scanner.scan(value)
    assert value not in result.redacted_content
    assert "synthetic-password" not in result.redacted_content
    assert "URL credentials" in result.findings


@pytest.mark.parametrize("name", ["access_token", "refresh_token", "oauth_token"])
def test_detects_oauth_token_assignments(scanner, name):
    token = "synthetic-oauth-token-1234567890"
    result = scanner.scan(f"{name}={token}")
    assert token not in result.redacted_content
    assert "OAuth token" in result.findings


def test_incomplete_private_key_redacts_following_material(scanner):
    content = "-----BEGIN PRIVATE KEY-----\nsynthetic-private-key-material\nother bytes"
    result = scanner.scan(content)
    assert result.contains_private_key
    assert "synthetic-private-key-material" not in result.redacted_content
    assert "other bytes" not in result.redacted_content
