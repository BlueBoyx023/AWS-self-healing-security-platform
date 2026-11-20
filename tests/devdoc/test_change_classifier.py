
import pytest

from scripts.devdoc.change_classifier import ChangeClassifier


@pytest.fixture
def classifier():
    return ChangeClassifier()


def test_security_logic_classification(classifier):
    report = {
        "changes": [
            {"path": "lambda/event_validator.py", "status": "modified"}
        ]
    }

    result = classifier.classify(report)

    assert "Security Logic" in result["classifications"][0]["categories"]


def test_iam_classification(classifier):
    report = {
        "changes": [
            {"path": "policies/iam_policy.json", "status": "added"}
        ]
    }

    result = classifier.classify(report)

    assert "IAM & Permissions" in result["classifications"][0]["categories"]


def test_aws_service_classification(classifier):
    report = {
        "changes": [
            {"path": "lambda/s3_remediation_engine.py", "status": "modified"}
        ]
    }

    result = classifier.classify(report)

    categories = result["classifications"][0]["categories"]

    assert "AWS Services" in categories
    assert "Security Logic" in categories


def test_configuration_classification(classifier):
    report = {
        "changes": [
            {"path": "config/settings.yaml", "status": "modified"}
        ]
    }

    result = classifier.classify(report)

    assert "Configuration" in result["classifications"][0]["categories"]


def test_test_file_classification(classifier):
    report = {
        "changes": [
            {"path": "tests/test_remediation.py", "status": "added"}
        ]
    }

    result = classifier.classify(report)

    categories = result["classifications"][0]["categories"]

    assert "Tests" in categories
    assert "Security Logic" in categories


def test_documentation_classification(classifier):
    report = {
        "changes": [
            {"path": "README.md", "status": "modified"}
        ]
    }

    result = classifier.classify(report)

    assert "Documentation" in result["classifications"][0]["categories"]


def test_general_code_classification(classifier):
    report = {
        "changes": [
            {"path": "utils/helpers.py", "status": "modified"}
        ]
    }

    result = classifier.classify(report)

    assert result["classifications"][0]["categories"] == ["General Code"]


def test_multiple_categories(classifier):
    report = {
        "changes": [
            {"path": "lambda/security/s3_remediation.py", "status": "modified"}
        ]
    }

    result = classifier.classify(report)

    categories = result["classifications"][0]["categories"]

    assert "Security Logic" in categories
    assert "AWS Services" in categories


def test_multiple_changed_files(classifier):
    report = {
        "changes": [
            {"path": "README.md", "status": "modified"},
            {"path": "tests/test_api.py", "status": "added"},
            {"path": "utils/helpers.py", "status": "modified"},
        ]
    }

    result = classifier.classify(report)

    assert result["summary"]["total_files"] == 3


def test_empty_change_report(classifier):
    result = classifier.classify({"changes": []})

    assert result["summary"]["total_files"] == 0
    assert result["classifications"] == []


def test_deleted_file_classification(classifier):
    report = {
        "changes": [
            {"path": "lambda/event_validator.py", "status": "deleted"}
        ]
    }

    result = classifier.classify(report)

    assert result["classifications"][0]["status"] == "deleted"
    assert "Security Logic" in result["classifications"][0]["categories"]


def test_renamed_file_classification(classifier):
    report = {
        "changes": [
            {"path": "lambda/new_validator.py", "status": "renamed"}
        ]
    }

    result = classifier.classify(report)

    assert result["classifications"][0]["status"] == "renamed"
    assert "Security Logic" in result["classifications"][0]["categories"]


def test_invalid_report(classifier):
    with pytest.raises(ValueError):
        classifier.classify("invalid")


def test_missing_changes_list(classifier):
    with pytest.raises(ValueError):
        classifier.classify({})