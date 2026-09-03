from __future__ import annotations

import time
from pathlib import Path

import httpx

from narrate.voices import TtsModel, get_model

OPENROUTER_SPEECH = "https://openrouter.ai/api/v1/audio/speech"
NARRATION_INSTRUCTIONS = (
    "Read as a calm audiobook narrator. Even pacing, clear diction, no theatrics."
)


class TtsError(RuntimeError):
    pass


def synthesize_chunk(
    *,
    api_key: str,
    model_id: str,
    voice: str,
    text: str,
    dest: Path,
    timeout: float = 120.0,
) -> None:
    model = get_model(model_id)
    if not api_key:
        raise TtsError("OPENROUTER_API_KEY is not set")
    if len(text) > model.max_chars + 200:
        raise TtsError(f"Chunk is {len(text)} chars; model max is {model.max_chars}")

    payload: dict = {
        "model": model.id,
        "input": text,
        "voice": voice,
        "response_format": "mp3",
    }
    if model.id.startswith("openai/"):
        payload["provider"] = {
            "options": {"openai": {"instructions": NARRATION_INSTRUCTIONS}}
        }

    dest.parent.mkdir(parents=True, exist_ok=True)
    last_error = None
    for attempt in range(4):
        try:
            with httpx.Client(timeout=timeout) as client:
                response = client.post(
                    OPENROUTER_SPEECH,
                    headers={
                        "Authorization": f"Bearer {api_key}",
                        "Content-Type": "application/json",
                        "HTTP-Referer": "https://github.com/3stacks/narrate",
                        "X-Title": "narrate",
                    },
                    json=payload,
                )
            if response.status_code == 429 or response.status_code >= 500:
                last_error = f"{response.status_code} {response.text[:300]}"
                time.sleep(2 ** attempt)
                continue
            if response.status_code >= 400:
                raise TtsError(
                    f"OpenRouter TTS {response.status_code}: {response.text[:500]}"
                )
            if len(response.content) < 200:
                raise TtsError("OpenRouter returned empty audio")
            dest.write_bytes(response.content)
            return
        except httpx.HTTPError as exc:
            last_error = str(exc)
            time.sleep(2 ** attempt)
    raise TtsError(f"OpenRouter TTS failed after retries: {last_error}")


def resolve_voice(model: TtsModel, voice: str | None) -> str:
    if not voice:
        return model.default_voice
    if voice not in model.voices:
        raise TtsError(
            f"Voice {voice!r} is not in the catalog for {model.id}. "
            f"Try: {', '.join(model.voices)}"
        )
    return voice
