from types import SimpleNamespace

import pytest

from src.utils.ai import _validate_response, build_client, complete


def test_retired_github_endpoint_reports_configuration_fix(monkeypatch):
    monkeypatch.setenv("AI_ENDPOINT", "https://models.github.ai/inference")
    with pytest.raises(RuntimeError, match="AI_ENDPOINT"):
        build_client()


def test_non_json_success_response_reports_endpoint_problem():
    def invalid_json():
        raise ValueError("Expecting value")

    response = SimpleNamespace(status_code=200, json=invalid_json)
    with pytest.raises(RuntimeError, match="HTTP 200"):
        _validate_response(SimpleNamespace(http_response=response))


@pytest.mark.parametrize("choices", [[], [SimpleNamespace(message=None)]])
def test_empty_completion_reports_actionable_error(choices):
    client = SimpleNamespace(complete=lambda **kwargs: SimpleNamespace(choices=choices))
    with pytest.raises(RuntimeError, match="AI API"):
        complete(client, messages=[], model="gemma4:latest")


@pytest.mark.parametrize("model", ["deepseek-flash", "deepseek-v4-pro"])
def test_deepseek_routes_to_cloud_with_its_token(monkeypatch, model):
    from src.utils import ai

    monkeypatch.setenv("AI_ENDPOINT", "http://localhost:11434/v1")
    monkeypatch.setenv("AI_API_KEY", "local-key")
    monkeypatch.setenv("DEEPSEEK_TOKEN", "deepseek-test-key")
    monkeypatch.setattr(ai, "ChatCompletionsClient", lambda **kwargs: kwargs)
    client = ai.build_client(model)
    assert client["endpoint"] == "https://api.deepseek.com"
    assert client["credential"].key == "deepseek-test-key"


def test_deepseek_requires_own_token(monkeypatch):
    monkeypatch.delenv("DEEPSEEK_TOKEN", raising=False)
    monkeypatch.setenv("AI_API_KEY", "other-provider-key")
    with pytest.raises(RuntimeError, match="DEEPSEEK_TOKEN"):
        build_client("deepseek-flash")


def test_local_model_does_not_use_deepseek_token(monkeypatch):
    from src.utils import ai

    monkeypatch.setenv("AI_ENDPOINT", "http://localhost:11434/v1")
    monkeypatch.delenv("AI_API_KEY", raising=False)
    monkeypatch.setenv("DEEPSEEK_TOKEN", "deepseek-test-key")
    monkeypatch.setattr(ai, "ChatCompletionsClient", lambda **kwargs: kwargs)
    client = ai.build_client("gemma4:latest")
    assert client["endpoint"] == "http://localhost:11434/v1"
    assert client["credential"].key == "ollama"


def test_environment_default_can_select_deepseek(monkeypatch):
    from src.utils import ai

    monkeypatch.setenv("AI_MODEL", "deepseek-v4-pro")
    monkeypatch.setenv("DEEPSEEK_TOKEN", "deepseek-test-key")
    monkeypatch.setattr(ai, "ChatCompletionsClient", lambda **kwargs: kwargs)
    assert ai.default_model() == "deepseek-v4-pro"
    assert ai.build_client()["endpoint"] == "https://api.deepseek.com"
