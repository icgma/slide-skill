import os
import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock

from slide_skill.mimo_tts import (
    MIMO_PRESET_VOICES,
    MIMO_BASE_URL,
    _get_client,
    _mime_for_path,
    generate_audio,
    list_mimo_voices,
)


def test_mimo_preset_voices_count():
    assert len(MIMO_PRESET_VOICES) == 9


def test_mimo_preset_voices_contains_chinese_and_english():
    assert "冰糖" in MIMO_PRESET_VOICES
    assert "Mia" in MIMO_PRESET_VOICES


def test_mime_for_mp3():
    assert _mime_for_path(Path("test.mp3")) == "audio/mpeg"


def test_mime_for_wav():
    assert _mime_for_path(Path("test.wav")) == "audio/wav"


def test_mime_for_unsupported():
    with pytest.raises(ValueError, match="Unsupported audio format"):
        _mime_for_path(Path("test.flac"))
    with pytest.raises(ValueError, match="Unsupported audio format"):
        _mime_for_path(Path("test.ogg"))


def test_list_mimo_voices_returns_eight():
    assert len(list_mimo_voices()) == 8


def test_list_mimo_voices_structure():
    voices = list_mimo_voices()
    for voice in voices:
        assert "name" in voice
        assert "id" in voice
        assert "language" in voice
        assert "gender" in voice


@patch.dict("os.environ", clear=True)
def test_get_client_missing_key():
    with pytest.raises(RuntimeError, match="MIMO_API_KEY environment variable is not set"):
        _get_client()


@patch.dict("os.environ", clear=True)
def test_generate_audio_missing_key():
    with pytest.raises(RuntimeError, match="MIMO_API_KEY environment variable is not set"):
        generate_audio("Hello", Path("out.wav"))


@patch.dict("os.environ", {"MIMO_API_KEY": "fake_key"}, clear=True)
@patch("slide_skill.mimo_tts._get_client")
def test_generate_audio_invalid_voice(mock_get_client):
    with pytest.raises(ValueError, match="Unknown preset voice"):
        generate_audio("Hello", Path("out.wav"), voice="invalid_voice")
