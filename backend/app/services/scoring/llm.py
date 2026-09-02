from __future__ import annotations

import json
import re
from dataclasses import dataclass

import httpx
from openai import AsyncOpenAI

from app.config import settings
from app.models.user_profile import UserProfile
from app.services.crypto import unseal


@dataclass
class LLMConfig:
    provider: str
    model: str
    openai_api_key: str
    ollama_base_url: str


def config_from_profile(profile: UserProfile | None) -> LLMConfig:
    return LLMConfig(
        provider=(profile.llm_provider if profile and profile.llm_provider else settings.llm_provider).lower(),
        model=(profile.llm_model if profile and profile.llm_model else settings.llm_model),
        openai_api_key=(
            unseal(profile.openai_api_key)
            if profile and profile.openai_api_key
            else settings.openai_api_key
        )
        or "",
        ollama_base_url=(
            profile.ollama_base_url if profile and profile.ollama_base_url else settings.ollama_base_url
        ),
    )


class LLMError(RuntimeError):
    pass


def extract_json(text: str) -> dict:
    raw = text.strip()
    if raw.startswith("```"):
        raw = re.sub(r"^```(?:json)?\s*", "", raw)
        raw = re.sub(r"\s*```$", "", raw)
    try:
        data = json.loads(raw)
        if isinstance(data, dict):
            return data
    except json.JSONDecodeError:
        pass
    match = re.search(r"\{[\s\S]*\}", raw)
    if not match:
        raise LLMError("LLM did not return JSON")
    data = json.loads(match.group(0))
    if not isinstance(data, dict):
        raise LLMError("LLM JSON is not an object")
    return data


async def complete(cfg: LLMConfig, *, system: str, user: str, json_mode: bool = True) -> str:
    if cfg.provider == "ollama":
        return await _ollama(cfg, system=system, user=user, json_mode=json_mode)
    return await _openai(cfg, system=system, user=user, json_mode=json_mode)


async def _openai(cfg: LLMConfig, *, system: str, user: str, json_mode: bool) -> str:
    if not cfg.openai_api_key:
        raise LLMError("OpenAI API key is missing")
    client = AsyncOpenAI(api_key=cfg.openai_api_key)
    kwargs: dict = {
        "model": cfg.model,
        "temperature": 0.2,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
    }
    if json_mode:
        kwargs["response_format"] = {"type": "json_object"}
    response = await client.chat.completions.create(**kwargs)
    content = response.choices[0].message.content or ""
    return content


async def _ollama(cfg: LLMConfig, *, system: str, user: str, json_mode: bool) -> str:
    payload = {
        "model": cfg.model,
        "stream": False,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
    }
    if json_mode:
        payload["format"] = "json"
    url = cfg.ollama_base_url.rstrip("/") + "/api/chat"
    async with httpx.AsyncClient(timeout=120.0) as client:
        response = await client.post(url, json=payload)
        response.raise_for_status()
        data = response.json()
    return (data.get("message") or {}).get("content") or ""
