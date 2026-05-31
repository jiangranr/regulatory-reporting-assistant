import json
from typing import Iterator

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


def stream_text(messages: list[dict[str, str]], model: str | None = None) -> Iterator[str]:
    """流式调用 LLM，逐 token yield 文本片段。

    使用 OpenAI 兼容的 stream=True 协议，解析 SSE data 行。
    遇到网络/协议错误时抛 LLMClientError。
    """
    settings = get_settings()
    if not settings.llm_api_base or not settings.llm_api_key:
        raise LLMClientError("LLM API base or key is not configured")

    selected_model = model or settings.llm_model
    base_url = settings.llm_api_base.rstrip("/")
    payload = {
        "model": selected_model,
        "messages": messages,
        "stream": True,
    }

    try:
        with httpx.Client(timeout=settings.llm_timeout_seconds) as client:
            with client.stream(
                "POST",
                f"{base_url}/chat/completions",
                headers={
                    "Authorization": f"Bearer {settings.llm_api_key}",
                    "Content-Type": "application/json",
                },
                json=payload,
            ) as response:
                response.raise_for_status()
                for line in response.iter_lines():
                    line = line.strip()
                    if not line or not line.startswith("data: "):
                        continue
                    chunk_str = line[6:]
                    if chunk_str == "[DONE]":
                        break
                    try:
                        chunk = json.loads(chunk_str)
                        delta = chunk["choices"][0]["delta"]
                        content = delta.get("content") or ""
                        if content:
                            yield content
                    except (json.JSONDecodeError, KeyError, IndexError):
                        pass
    except httpx.HTTPError as exc:
        raise LLMClientError(f"LLM stream request failed: {exc}") from exc


# ── Embedding ────────────────────────────────────────────────────────────


def embed_texts(texts: list[str]) -> list[list[float]]:
    """把一批文本转成向量。

    走 OpenAI 兼容协议（POST /v1/embeddings），适用于：
    - DashScope compatible-mode（https://dashscope.aliyuncs.com/compatible-mode/v1）
    - SiliconFlow / 智谱 / OpenAI 等所有 OpenAI 风格 API

    分批策略：单次最多 settings.embedding_batch_size 条
      （DashScope 上限 25 条；OpenAI 上限 2048 条，安全起见默认 25）

    向后兼容：
    - 入参为空列表 → 直接返回 []
    - 任何提供方层错误抛 LLMClientError，由调用方决定降级策略
      （concept_matcher 在该路径失败时降级为路 1 + 路 2，不抛给业务方）
    """

    if not texts:
        return []

    settings = get_settings()
    if not settings.embedding_api_base or not settings.embedding_api_key:
        raise LLMClientError("Embedding API base or key is not configured")

    base_url = settings.embedding_api_base.rstrip("/")
    batch_size = max(1, settings.embedding_batch_size)
    all_vectors: list[list[float]] = []

    for offset in range(0, len(texts), batch_size):
        batch = texts[offset : offset + batch_size]
        payload = {"model": settings.embedding_model, "input": batch}
        try:
            with httpx.Client(timeout=settings.embedding_timeout_seconds) as client:
                response = client.post(
                    f"{base_url}/embeddings",
                    headers={
                        "Authorization": f"Bearer {settings.embedding_api_key}",
                        "Content-Type": "application/json",
                    },
                    json=payload,
                )
                response.raise_for_status()
                data = response.json()
        except httpx.HTTPError as exc:
            raise LLMClientError(f"Embedding request failed: {exc}") from exc
        except json.JSONDecodeError as exc:
            raise LLMClientError(f"Embedding response not JSON: {exc}") from exc

        try:
            # OpenAI 兼容响应：{"data":[{"embedding":[...], "index":i}, ...]}
            # 兼容部分提供方未返回 index 字段的情况，按数组顺序兜底
            items = data["data"]
            if any("index" in it for it in items):
                items = sorted(items, key=lambda x: x.get("index", 0))
            for item in items:
                all_vectors.append(item["embedding"])
        except (KeyError, IndexError, TypeError) as exc:
            raise LLMClientError(f"Embedding response malformed: {data}") from exc

    if len(all_vectors) != len(texts):
        raise LLMClientError(
            f"Embedding count mismatch: got {len(all_vectors)} for {len(texts)} texts"
        )
    return all_vectors
