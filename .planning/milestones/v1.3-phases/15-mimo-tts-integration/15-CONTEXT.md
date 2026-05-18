# Phase 15 Context: MiMo TTS Integration

**Milestone:** v1.3
**Created:** 2026-05-01

## Problem

Current TTS implementation only supports edge-tts (Microsoft Edge neural voices). Xiaomi's MiMo-V2.5-TTS offers significantly more advanced capabilities:
- 8 high-quality preset voices (Chinese + English)
- Voice design from text description (no audio sample needed)
- Voice cloning from audio sample (clone any voice with a short recording)
- Rich style control via natural language or audio tags
- Currently free (限时免费)

## Solution

Add MiMo as a second TTS engine alongside edge-tts. The implementation should:
1. Create a new `mimo_tts.py` module with MiMo-specific logic
2. Refactor `narrate.py` to support an engine abstraction (edge-tts vs mimo)
3. Update CLI with `--engine`, `--voice-clone`, `--voice-design`, `--style` flags
4. Add `mimo` optional dependency in pyproject.toml

## Key API Details

- **Base URL**: `https://api.xiaomimimo.com/v1` (OpenAI-compatible)
- **Auth**: `MIMO_API_KEY` environment variable
- **Models**:
  - `mimo-v2.5-tts` — preset voices (冰糖, 茉莉, 苏打, 白桦, Mia, Chloe, Milo, Dean)
  - `mimo-v2.5-tts-voicedesign` — voice from text description
  - `mimo-v2.5-tts-voiceclone` — voice from audio sample
- **Messages**: `user` = style instructions, `assistant` = text to synthesize
- **Audio output**: WAV format, base64-encoded in response
- **Voice clone input**: mp3/wav, max 10MB base64, prefix `data:{MIME_TYPE};base64,{BASE64}`

## Files to Change

1. `tools/slide/src/slide_skill/mimo_tts.py` — NEW: MiMo TTS backend
2. `tools/slide/src/slide_skill/narrate.py` — Refactor to support engine selection
3. `tools/slide/src/slide_skill/cli.py` — Add MiMo CLI flags
4. `pyproject.toml` — Add `mimo` optional dependency
