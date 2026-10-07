"""Shared AI transport and actionable response validation."""

import json
import os
from typing import Any
from urllib.parse import urlparse

from azure.ai.inference import ChatCompletionsClient
from azure.core.credentials import AzureKeyCredential
from azure.core.pipeline.policies import AzureKeyCredentialPolicy

from . import config as _config  # noqa: F401 - load .env before reading settings

GITHUB_ENDPOINT = "https://models.github.ai/inference"
DEEPSEEK_ENDPOINT = "https://api.deepseek.com"
SELECTABLE_MODELS = ("gemma4:latest", "deepseek-flash", "deepseek-v4-pro")


def default_model() -> str:
    return os.getenv("AI_MODEL") or os.getenv("GITHUB_MODEL", "gemma4:latest")


def build_client(model: str | None = None) -> ChatCompletionsClient:
    selected_model = model or default_model()
    is_deepseek = selected_model.lower().startswith("deepseek-")
    endpoint = (
        DEEPSEEK_ENDPOINT
        if is_deepseek
        else os.getenv("AI_ENDPOINT") or "http://localhost:11434/v1"
    ).rstrip("/")
    if urlparse(endpoint).hostname in {
        "models.github.ai",
        "models.inference.ai.azure.com",
    }:
        raise RuntimeError(
            "GitHub Models закрыт с 30 июля 2026 года. Укажите AI_ENDPOINT, "
            "AI_API_KEY и AI_MODEL другого провайдера в .env. "
            "AI_ENDPOINT — базовый URL API без /chat/completions."
        )
    token = os.getenv("DEEPSEEK_TOKEN") if is_deepseek else os.getenv("AI_API_KEY")
    if urlparse(endpoint).hostname in {"localhost", "127.0.0.1", "::1"}:
        token = token or "ollama"
    if not token:
        setting = "DEEPSEEK_TOKEN" if is_deepseek else "AI_API_KEY"
        raise RuntimeError(f"Укажите {setting} в .env для выбранной модели.")
    credential = AzureKeyCredential(token)
    return ChatCompletionsClient(
        endpoint=endpoint,
        credential=credential,
        authentication_policy=AzureKeyCredentialPolicy(
            credential, "Authorization", prefix="Bearer"
        ),
        connection_timeout=15,
        read_timeout=300,
    )


def _validate_response(pipeline_response: Any) -> None:
    response = pipeline_response.http_response
    if response.status_code != 200:
        return
    try:
        response.json()
    except (ValueError, json.JSONDecodeError) as exc:
        raise RuntimeError(
            "AI API вернул пустой ответ или данные вместо JSON "
            f"(HTTP {response.status_code}). Проверьте AI_ENDPOINT: нужен базовый "
            "URL API без /chat/completions, а не адрес веб-страницы."
        ) from exc


def complete(client: Any, *, messages: list[Any], model: str) -> Any:
    response = client.complete(
        messages=messages,
        model=model,
        temperature=0.2,
        response_format="json_object",
        model_extras={"reasoning_effort": "none"},
        raw_response_hook=_validate_response,
    )
    if not response.choices:
        raise RuntimeError("AI API вернул ответ без вариантов завершения (choices).")
    message = response.choices[0].message
    if not message or not message.content or not message.content.strip():
        raise RuntimeError(
            "AI API вернул пустое сообщение. Проверьте модель и ограничения ответа."
        )
    return response
