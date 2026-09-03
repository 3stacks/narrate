from __future__ import annotations

from dataclasses import dataclass

DEFAULT_MODEL = "openai/gpt-4o-mini-tts-2025-12-15"
DEFAULT_VOICE = "nova"


@dataclass(frozen=True)
class TtsModel:
    id: str
    label: str
    usd_per_million_chars: float
    max_chars: int
    voices: tuple[str, ...]
    default_voice: str
    notes: str


# Prices from OpenRouter /api/v1/models?output_modalities=speech (2026-09-03).
# gpt-4o-mini-tts is the cheap high-quality default: $0.60 / million characters.
# A 100k-word book is roughly 500k characters, about $0.30.
MODELS: dict[str, TtsModel] = {
    "openai/gpt-4o-mini-tts-2025-12-15": TtsModel(
        id="openai/gpt-4o-mini-tts-2025-12-15",
        label="GPT-4o Mini TTS",
        usd_per_million_chars=0.60,
        max_chars=3500,
        voices=(
            "alloy",
            "ash",
            "ballad",
            "coral",
            "echo",
            "fable",
            "nova",
            "onyx",
            "sage",
            "shimmer",
            "verse",
        ),
        default_voice="nova",
        notes="Best quality at the low end. About 30c for a typical novel.",
    ),
    "hexgrad/kokoro-82m": TtsModel(
        id="hexgrad/kokoro-82m",
        label="Kokoro 82M",
        usd_per_million_chars=0.62,
        max_chars=1800,
        voices=(
            "af_sky",
            "af_heart",
            "af_bella",
            "am_michael",
            "am_fenrir",
            "bf_emma",
            "bm_george",
            "bm_lewis",
        ),
        default_voice="af_sky",
        notes="Same ballpark cost as GPT-4o Mini, more voices, a bit more robotic.",
    ),
    "sesame/csm-1b": TtsModel(
        id="sesame/csm-1b",
        label="Sesame CSM 1B",
        usd_per_million_chars=7.00,
        max_chars=1800,
        voices=(
            "read_speech_a",
            "read_speech_b",
            "read_speech_c",
            "read_speech_d",
            "conversational_a",
            "conversational_b",
        ),
        default_voice="read_speech_a",
        notes="Read-speech voices. About $3.50 for a typical novel.",
    ),
    "x-ai/grok-voice-tts-1.0": TtsModel(
        id="x-ai/grok-voice-tts-1.0",
        label="Grok Voice TTS",
        usd_per_million_chars=15.00,
        max_chars=8000,
        voices=("eve", "ara", "rex", "sal", "leo"),
        default_voice="eve",
        notes="Premium. About $7.50 for a typical novel.",
    ),
}


def get_model(model_id: str) -> TtsModel:
    if model_id not in MODELS:
        known = ", ".join(MODELS)
        raise KeyError(f"Unknown TTS model {model_id!r}. Known: {known}")
    return MODELS[model_id]


def estimate_usd(model_id: str, chars: int) -> float:
    model = get_model(model_id)
    return round((chars / 1_000_000) * model.usd_per_million_chars, 4)


def public_catalog() -> list[dict]:
    return [
        {
            "id": model.id,
            "label": model.label,
            "usd_per_million_chars": model.usd_per_million_chars,
            "max_chars": model.max_chars,
            "voices": list(model.voices),
            "default_voice": model.default_voice,
            "notes": model.notes,
        }
        for model in MODELS.values()
    ]
