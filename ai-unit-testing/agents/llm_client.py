"""
agents/llm_client.py
Thin wrapper around the OpenAI-compatible HTTP API.
All agents share this client.
"""

from __future__ import annotations

import json
import logging
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)


class LLMClient:
    """
    Minimal OpenAI-compatible chat-completion client.
    Uses the openai Python SDK pointed at a configurable base URL.
    """

    def __init__(
        self,
        api_key: str,
        base_url: str,
        model: str,
        temperature: float = 0.2,
        max_tokens: int = 4000,
    ) -> None:
        from openai import OpenAI  # imported here to allow mock mode without openai installed
        self._client = OpenAI(api_key=api_key, base_url=base_url)
        self.model = model
        self.temperature = temperature
        self.max_tokens = max_tokens

    def chat(self, system_prompt: str, user_prompt: str) -> str:
        """
        Send a single chat completion request.
        Returns the raw text content of the assistant's reply.
        Raises on API error.
        """
        logger.debug("LLM call: model=%s temp=%.2f max_tokens=%d",
                     self.model, self.temperature, self.max_tokens)
        response = self._client.chat.completions.create(
            model=self.model,
            temperature=self.temperature,
            max_tokens=self.max_tokens,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            response_format={"type": "json_object"},  # request JSON mode where supported
        )
        return response.choices[0].message.content or ""


def extract_json(raw: str) -> Dict[str, Any]:
    """
    Extract and parse a JSON object from the LLM's raw response.
    Handles responses that wrap JSON in markdown code fences.
    Raises ValueError if no valid JSON is found.
    """
    text = raw.strip()

    # Strip markdown code fences if present
    for fence in ("```json", "```"):
        if text.startswith(fence):
            text = text[len(fence):]
            if "```" in text:
                text = text[:text.rfind("```")]
            break

    try:
        return json.loads(text)
    except json.JSONDecodeError:
        # Try to find the first { ... } block
        start = text.find("{")
        end = text.rfind("}") + 1
        if start != -1 and end > start:
            try:
                return json.loads(text[start:end])
            except json.JSONDecodeError:
                pass
        raise ValueError(f"No valid JSON found in LLM response. Raw: {raw[:300]}")
