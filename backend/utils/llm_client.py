"""
backend/utils/llm_client.py
=============================
Unified LLM client factory.
Transparently routes to:
  - Google Gemini (FREE) via google-generativeai SDK
  - OpenAI GPT-4o (paid) via openai SDK

Both return the same interface: a callable that takes
(system_prompt, user_prompt) → str (JSON string).

Usage:
    from backend.utils.llm_client import get_llm_client
    llm = get_llm_client()
    result_json_str = llm.complete(system, user)
"""

from __future__ import annotations

import json
from abc import ABC, abstractmethod
from typing import Optional

from backend.utils.logger import logger
from config.settings import settings


# ─────────────────────────────────────────────────────────────────────────────
# Abstract base
# ─────────────────────────────────────────────────────────────────────────────

class BaseLLMClient(ABC):
    """Common interface for all LLM backends."""

    @abstractmethod
    def complete(
        self,
        system_prompt: str,
        user_prompt: str,
        temperature: float = 0.2,
        seed: int = 42,
    ) -> str:
        """Returns a JSON string from the model."""
        ...


# ─────────────────────────────────────────────────────────────────────────────
# Google Gemini — FREE tier (gemini-2.0-flash)
# ─────────────────────────────────────────────────────────────────────────────

class GeminiClient(BaseLLMClient):
    """
    Uses google-generativeai SDK.
    Free tier: ~1500 requests/day, no credit card needed.
    Model: gemini-2.0-flash (fast, accurate)
    """

    def __init__(self):
        import google.generativeai as genai
        api_key = settings.GEMINI_API_KEY
        if not api_key:
            raise ValueError(
                "GEMINI_API_KEY not set. Get a free key at: https://aistudio.google.com/apikey"
            )
        genai.configure(api_key=api_key)
        self._genai = genai
        self._model_name = settings.GEMINI_MODEL
        logger.info(f"[LLMClient] Using Google Gemini — model={self._model_name} (FREE tier)")

    def complete(
        self,
        system_prompt: str,
        user_prompt: str,
        temperature: float = 0.2,
        seed: int = 42,
        json_mode: bool = False,
    ) -> str:
        """Call Gemini. Set json_mode=True only when the response must be JSON."""
        gen_cfg_kwargs: dict = {"temperature": temperature}
        if json_mode:
            gen_cfg_kwargs["response_mime_type"] = "application/json"

        model = self._genai.GenerativeModel(
            model_name=self._model_name,
            system_instruction=system_prompt,
            generation_config=self._genai.types.GenerationConfig(**gen_cfg_kwargs),
        )
        try:
            response = model.generate_content(user_prompt)
            return response.text or ""
        except Exception as e:
            logger.error(f"[GeminiClient] API error: {e}")
            raise

    def generate(self, user_prompt: str, temperature: float = 0.2) -> str:
        """Simple single-turn generation (used by proactive scanner)."""
        return self.complete(
            system_prompt="You are a Python bug analysis assistant. Respond with valid JSON only.",
            user_prompt=user_prompt,
            temperature=temperature,
            json_mode=True,
        )


# ───────────────────────────────────────────────────────────────────────────────
# Groq — FREE (Llama 3.3 70B — ~500 tokens/sec, no billing needed)
# ───────────────────────────────────────────────────────────────────────────────

class GroqClient(BaseLLMClient):
    """
    Uses the Groq SDK with Llama 3.3 70B.
    Free tier: 14,400 requests/day, 500k tokens/day, no credit card.
    Sign up: https://console.groq.com
    """

    def __init__(self):
        from groq import Groq
        api_key = settings.GROQ_API_KEY
        if not api_key:
            raise ValueError(
                "GROQ_API_KEY not set. Get a free key at: https://console.groq.com"
            )
        self._client = Groq(api_key=api_key)
        self._model = settings.GROQ_MODEL
        logger.info(f"[LLMClient] ⚡ Using Groq — model={self._model} (FREE, ~500 tok/sec)")

    def complete(
        self,
        system_prompt: str,
        user_prompt: str,
        temperature: float = 0.1,  # FIXED for determinism
        seed: int = 42,
        json_mode: bool = False,
    ) -> str:
        # Enforce deterministic constraints for 8B model usage
        response = self._client.chat.completions.create(
            model=settings.GROQ_MODEL,  # Use whatever is in .env (8b-instant)
            temperature=0.1,            # Hardcoded LOW temperature
            top_p=0.9,
            stream=False,               # Explicitly disable streaming
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user",   "content": user_prompt},
            ],
            max_tokens=4096,
        )
        raw = response.choices[0].message.content or "{}"
        # Strip markdown code fences if LLM wrapped the JSON in ```json...```
        import re
        # Try to extract JSON block from response
        json_match = re.search(r'```(?:json)?\s*(\{.*?\})\s*```', raw, re.DOTALL)
        if json_match:
            return json_match.group(1)
        # If no fences, look for first { to last }
        brace_match = re.search(r'\{.*\}', raw, re.DOTALL)
        if brace_match:
            return brace_match.group(0)
        return raw

    def generate(self, user_prompt: str, temperature: float = 0.1) -> str:
        """Simple single-turn generation (used by proactive scanner)."""
        return self.complete(
            system_prompt="You are a Python bug analysis assistant. Respond with valid JSON only.",
            user_prompt=user_prompt,
            temperature=temperature,
        )


# ───────────────────────────────────────────────────────────────────────────────
# OpenAI GPT-4o — Paid
# ─────────────────────────────────────────────────────────────────────────────

class OpenAIClient(BaseLLMClient):
    """Uses openai SDK with GPT-4o."""

    def __init__(self):
        from openai import OpenAI
        api_key = settings.OPENAI_API_KEY
        if not api_key:
            raise ValueError("OPENAI_API_KEY not set.")
        self._client = OpenAI(api_key=api_key)
        logger.info(f"[LLMClient] Using OpenAI — model={settings.OPENAI_MODEL}")

    def complete(
        self,
        system_prompt: str,
        user_prompt: str,
        temperature: float = 0.2,
        seed: int = 42,
    ) -> str:
        response = self._client.chat.completions.create(
            model=settings.OPENAI_MODEL,
            temperature=temperature,
            seed=seed,
            response_format={"type": "json_object"},
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user",   "content": user_prompt},
            ],
        )
        return response.choices[0].message.content or "{}"


# ─────────────────────────────────────────────────────────────────────────────
# Factory
# ─────────────────────────────────────────────────────────────────────────────

_client_instance: Optional[BaseLLMClient] = None


def reset_llm_client() -> None:
    """Clear the cached singleton so the next get_llm_client() call creates a fresh one."""
    global _client_instance
    _client_instance = None


def get_llm_client() -> BaseLLMClient:
    """
    Returns a singleton LLM client based on LLM_PROVIDER env var.
    Priority: gemini (free) → groq (free) → openai (paid)
    """
    global _client_instance
    if _client_instance is not None:
        return _client_instance

    provider = settings.LLM_PROVIDER.lower()
    if provider == "gemini":
        _client_instance = GeminiClient()
    elif provider == "groq":
        _client_instance = GroqClient()
    elif provider == "openai":
        _client_instance = OpenAIClient()
    else:
        raise ValueError(f"Unknown LLM_PROVIDER='{provider}'. Use 'gemini', 'groq', or 'openai'.")

    return _client_instance
