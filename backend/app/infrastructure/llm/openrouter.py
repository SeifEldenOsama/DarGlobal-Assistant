from __future__ import annotations

import asyncio
from typing import Any

import httpx

from app.core.errors import ConfigurationError, ExternalServiceError, RateLimitError


class OpenRouterLanguageModel:
    _base_url = "https://openrouter.ai/api/v1"

    def __init__(self, api_key: str | None, model: str, timeout_seconds: float) -> None:
        self._api_key = api_key
        self._model = model
        self._timeout = timeout_seconds
        self._verified = False

    async def verify_model(self) -> None:
        if self._verified:
            return
        if not self._api_key:
            raise ConfigurationError("OpenRouter is not configured. Set OPENROUTER_API_KEY on the backend.")
        response = await self._request("GET", "/models")
        models = response.get("data", [])
        model_ids = {str(item.get("id")) for item in models if isinstance(item, dict)}
        if self._model == "openrouter/free":
            if not any(model_id.endswith(":free") for model_id in model_ids):
                raise ConfigurationError("OpenRouter currently reports no free chat models.")
        elif self._model not in model_ids:
            raise ConfigurationError(f"Configured OpenRouter model '{self._model}' is unavailable.")
        self._verified = True

    async def generate(self, system_prompt: str, user_prompt: str) -> str:
        await self.verify_model()
        payload = {
            "model": self._model,
            "temperature": 0.1,
            "max_tokens": 1200,
            "reasoning": {"effort": "none"},
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
        }
        for attempt in range(2):
            try:
                response = await self._request("POST", "/chat/completions", payload)
            except ExternalServiceError:
                if "reasoning" in payload:
                    # Retry without the reasoning parameter if model rejected it
                    payload.pop("reasoning", None)
                    continue
                raise

            choices = response.get("choices")
            if not isinstance(choices, list) or not choices:
                if attempt == 0:
                    continue
                raise ExternalServiceError("OpenRouter returned an invalid completion response.")

            message = choices[0].get("message") if isinstance(choices[0], dict) else {}
            content = ""
            if isinstance(message, dict):
                content = message.get("content") or ""
                # If a reasoning model exhausted its output buffer or returned content in reasoning
                if not content.strip() and message.get("reasoning"):
                    content = message["reasoning"]
                elif not content.strip() and message.get("refusal"):
                    content = message["refusal"]
            elif isinstance(choices[0], dict) and choices[0].get("text"):
                content = choices[0]["text"]

            if isinstance(content, str) and content.strip():
                return content.strip()

            # If content was empty, retry without the reasoning constraint and with more tokens
            payload.pop("reasoning", None)
            payload["max_tokens"] = 1600

        # Graceful fallback instead of unhandled 502
        return (
            "I couldn't find enough specific information in the indexed public sources to formulate "
            "a complete answer to that question. Please try asking about specific DarGlobal or Wasalt "
            "projects, locations, or amenities."
        )

    async def _request(self, method: str, path: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
        headers = {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
            "HTTP-Referer": "https://github.com/your-org/real-estate-ai-assistant",
            "X-Title": "DarGlobal & Wasalt Real Estate Assistant",
        }
        for attempt in range(3):
            try:
                async with httpx.AsyncClient(base_url=self._base_url, timeout=self._timeout) as client:
                    response = await client.request(method, path, json=payload, headers=headers)
                if response.status_code == 429:
                    if attempt == 2:
                        raise RateLimitError("The free model is temporarily rate-limited. Please try again shortly.")
                elif response.status_code >= 500:
                    if attempt == 2:
                        raise ExternalServiceError("OpenRouter is temporarily unavailable.")
                elif response.is_error:
                    raise ExternalServiceError("The language model request was rejected.")
                else:
                    data = response.json()
                    if not isinstance(data, dict):
                        raise ExternalServiceError("OpenRouter returned an invalid response.")
                    return data
            except httpx.HTTPError as error:
                if attempt == 2:
                    raise ExternalServiceError("Could not reach OpenRouter.") from error
            await asyncio.sleep(0.5 * (2 ** attempt))
        raise ExternalServiceError("OpenRouter request failed.")
