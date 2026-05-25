import json

import httpx

from app.core.config import get_settings


class LLMClientError(RuntimeError):
    pass


def complete_json(messages: list[dict[str, str]], model: str | None = None) -> tuple[dict, str, str]:
    settings = get_settings()
    if not settings.llm_api_base or not settings.llm_api_key:
        raise LLMClientError("LLM API base or key is not configured")

    selected_model = model or settings.llm_model
    try:
        return _complete_json_with_model(messages, selected_model)
    except LLMClientError:
        if not settings.llm_fallback_model or settings.llm_fallback_model == selected_model:
            raise
        return _complete_json_with_model(messages, settings.llm_fallback_model)


def _complete_json_with_model(messages: list[dict[str, str]], model: str) -> tuple[dict, str, str]:
    settings = get_settings()
    base_url = settings.llm_api_base.rstrip("/")
    payload = {
        "model": model,
        "messages": messages,
    }
    try:
        with httpx.Client(timeout=settings.llm_timeout_seconds) as client:
            response = client.post(
                f"{base_url}/chat/completions",
                headers={
                    "Authorization": f"Bearer {settings.llm_api_key}",
                    "Content-Type": "application/json",
                },
                json=payload,
            )
            response.raise_for_status()
            raw = response.text
    except httpx.HTTPError as exc:
        raise LLMClientError(f"LLM request failed: {exc}") from exc

    try:
        data = json.loads(raw)
        content = data["choices"][0]["message"]["content"]
        return json.loads(content), raw, model
    except (KeyError, IndexError, json.JSONDecodeError, TypeError) as exc:
        raise LLMClientError("LLM response is not valid JSON") from exc
