"""MiMo-V2.5-TTS backend: preset voices, voice design, and voice cloning."""

from __future__ import annotations

import base64
import os
from pathlib import Path
from typing import Literal

MIMO_BASE_URL = "https://api.xiaomimimo.com/v1"

MIMO_PRESET_VOICES = ("冰糖", "茉莉", "苏打", "白桦", "Mia", "Chloe", "Milo", "Dean", "mimo_default")

MimoModel = Literal[
    "mimo-v2.5-tts",
    "mimo-v2.5-tts-voicedesign",
    "mimo-v2.5-tts-voiceclone",
]


def _get_client() -> tuple:
    """Return (api_key, module) after verifying dependencies and config."""
    try:
        from openai import OpenAI
    except ImportError as exc:
        raise RuntimeError(
            "MiMo TTS requires the openai package. Install with: pip install -e .[mimo]"
        ) from exc

    api_key = os.environ.get("MIMO_API_KEY")
    if not api_key:
        raise RuntimeError("MIMO_API_KEY environment variable is not set.")

    client = OpenAI(api_key=api_key, base_url=MIMO_BASE_URL)
    return client


def _mime_for_path(path: Path) -> str:
    """Return MIME type for mp3/wav files."""
    suffix = path.suffix.lower()
    if suffix == ".mp3":
        return "audio/mpeg"
    if suffix == ".wav":
        return "audio/wav"
    raise ValueError(f"Unsupported audio format: {suffix}. Use mp3 or wav.")


def generate_audio(
    text: str,
    output_path: Path,
    *,
    voice: str = "冰糖",
    style: str = "",
    model: MimoModel = "mimo-v2.5-tts",
    voice_clone_sample: Path | None = None,
    voice_design_prompt: str | None = None,
) -> Path:
    """Generate audio using MiMo-V2.5-TTS.

    Args:
        text: Text to synthesize (placed in assistant message).
        output_path: Where to save the WAV file.
        voice: Preset voice name (for mimo-v2.5-tts model).
        style: Natural language style instruction (placed in user message).
        model: MiMo model to use.
        voice_clone_sample: Path to mp3/wav audio sample for voice cloning.
        voice_design_prompt: Text description for voice design.

    Returns:
        Path to the generated WAV file.
    """
    client = _get_client()

    messages = []
    user_content = style

    if model == "mimo-v2.5-tts-voicedesign":
        if voice_design_prompt:
            user_content = voice_design_prompt
        elif not user_content:
            user_content = "温暖自然的中文女声"
    elif model == "mimo-v2.5-tts-voiceclone":
        if not voice_clone_sample:
            raise ValueError("voice_clone_sample is required for voice cloning.")
        user_content = user_content or ""
    else:
        if voice not in MIMO_PRESET_VOICES:
            raise ValueError(
                f"Unknown preset voice '{voice}'. Available: {', '.join(MIMO_PRESET_VOICES)}"
            )

    messages.append({"role": "user", "content": user_content})
    messages.append({"role": "assistant", "content": text})

    audio_config: dict = {"format": "wav"}

    if model == "mimo-v2.5-tts-voiceclone" and voice_clone_sample:
        audio_bytes = voice_clone_sample.read_bytes()
        b64 = base64.b64encode(audio_bytes).decode("utf-8")
        mime = _mime_for_path(voice_clone_sample)
        if len(b64) > 10 * 1024 * 1024:
            raise ValueError("Voice clone sample exceeds 10MB base64 limit.")
        audio_config["voice"] = f"data:{mime};base64,{b64}"
    elif model != "mimo-v2.5-tts-voiceclone":
        audio_config["voice"] = voice

    completion = client.chat.completions.create(
        model=model,
        messages=messages,
        audio=audio_config,
    )

    audio_data = completion.choices[0].message.audio.data
    audio_bytes_out = base64.b64decode(audio_data)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_bytes(audio_bytes_out)
    return output_path


def list_mimo_voices() -> list[dict]:
    """Return available MiMo preset voices."""
    return [
        {"name": "冰糖", "id": "冰糖", "language": "中文", "gender": "女性"},
        {"name": "茉莉", "id": "茉莉", "language": "中文", "gender": "女性"},
        {"name": "苏打", "id": "苏打", "language": "中文", "gender": "男性"},
        {"name": "白桦", "id": "白桦", "language": "中文", "gender": "男性"},
        {"name": "Mia", "id": "Mia", "language": "英文", "gender": "女性"},
        {"name": "Chloe", "id": "Chloe", "language": "英文", "gender": "女性"},
        {"name": "Milo", "id": "Milo", "language": "英文", "gender": "男性"},
        {"name": "Dean", "id": "Dean", "language": "英文", "gender": "男性"},
    ]
