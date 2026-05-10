"""
Clause explainer — 100% free AI pipeline
=========================================
Tier 1: Groq  (free API — Llama 3.3 70B, fast)
Tier 2: HuggingFace Inference API  (free, no key needed)
Tier 3: Template fallback  (always works)
"""
from __future__ import annotations

import hashlib
import sys
from functools import lru_cache

import requests

try:
    import redis as _redis_mod
except Exception:
    _redis_mod = None  # type: ignore[assignment]

from app.core.config import get_settings

settings = get_settings()

_SYSTEM = (
    "You are a legal analyst helping ordinary people understand contract clauses. "
    "Explain the clause in 2-3 plain English sentences. Focus on what the person signing "
    "is agreeing to and any practical risks. Be concise, avoid legal jargon."
)

_GROQ_URL   = "https://api.groq.com/openai/v1/chat/completions"
_GROQ_MODEL = "llama-3.3-70b-versatile"
_HF_URL     = "https://api-inference.huggingface.co/models/mistralai/Mistral-7B-Instruct-v0.3"


class ClauseExplainer:
    def __init__(self) -> None:
        self.cache = self._build_cache()

    def _build_cache(self):
        if _redis_mod is None:
            return None
        try:
            client = _redis_mod.Redis.from_url(settings.redis_url, decode_responses=True)
            client.ping()
            return client
        except Exception:
            return None

    def _cache_key(self, category: str, risk_level: str, clause_text: str) -> str:
        digest = hashlib.sha256(
            f'{category}|{risk_level}|{clause_text}'.encode()
        ).hexdigest()
        return f'clauseguard:explain:{digest}'

    def explain(self, category: str, risk_level: str, clause_text: str) -> str:
        key = self._cache_key(category, risk_level, clause_text)
        if self.cache:
            try:
                cached = self.cache.get(key)
                if cached:
                    return cached
            except Exception:
                pass

        result = (
            self._groq(category, risk_level, clause_text)
            or self._huggingface(category, risk_level, clause_text)
            or self._template(category, risk_level)
        )

        if self.cache:
            try:
                self.cache.setex(key, 60 * 60 * 24 * 7, result)
            except Exception:
                pass

        return result

    def _prompt_messages(self, category: str, risk_level: str, clause_text: str) -> list[dict]:
        return [
            {"role": "system", "content": _SYSTEM},
            {"role": "user", "content": (
                f"Category: {category}\nRisk Level: {risk_level}\n"
                f"Clause text: {clause_text[:600]}\n\n"
                "Explain what this clause means for the person signing it."
            )},
        ]

    def _groq(self, category: str, risk_level: str, clause_text: str) -> str | None:
        if not settings.groq_api_key:
            return None
        try:
            resp = requests.post(
                _GROQ_URL,
                headers={
                    "Authorization": f"Bearer {settings.groq_api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": _GROQ_MODEL,
                    "messages": self._prompt_messages(category, risk_level, clause_text),
                    "max_tokens": 200,
                    "temperature": 0.3,
                },
                timeout=15,
            )
            if resp.status_code == 200:
                return resp.json()["choices"][0]["message"]["content"].strip() or None
        except Exception as exc:
            print(f"[explainer] Groq error: {exc}", file=sys.stderr)
        return None

    def _huggingface(self, category: str, risk_level: str, clause_text: str) -> str | None:
        try:
            prompt = (
                f"<s>[INST] {_SYSTEM}\n\n"
                f"Category: {category}, Risk: {risk_level}\n"
                f"Clause: {clause_text[:400]}\n\n"
                "Explain this in 2-3 plain English sentences. [/INST]"
            )
            headers: dict = {"Content-Type": "application/json"}
            if settings.huggingface_api_key:
                headers["Authorization"] = f"Bearer {settings.huggingface_api_key}"
            resp = requests.post(
                _HF_URL,
                headers=headers,
                json={"inputs": prompt, "parameters": {"max_new_tokens": 150, "temperature": 0.3, "return_full_text": False}},
                timeout=20,
            )
            if resp.status_code == 200:
                data = resp.json()
                if isinstance(data, list) and data:
                    return data[0].get("generated_text", "").strip() or None
        except Exception as exc:
            print(f"[explainer] HuggingFace error: {exc}", file=sys.stderr)
        return None

    def _template(self, category: str, risk_level: str) -> str:
        leverage = "You are giving up significant leverage" if risk_level in {"critical", "high"} else "This is a routine contract point"
        standard = "It is more unusual or one-sided than a standard clause." if risk_level in {"critical", "high"} else "It looks standard for this kind of contract."
        return f"{leverage} in the {category.lower()} clause. {standard}"


@lru_cache(maxsize=1)
def get_claude_explainer() -> ClauseExplainer:
    return ClauseExplainer()
