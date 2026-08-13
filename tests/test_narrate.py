"""Tests for TTS audio narration."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from slide_skill.narrate import narrate_slide, list_available_voices


class _FakeCommunicate:
    def __init__(self, text: str, voice: str) -> None:
        self.text = text
        self.voice = voice

    async def save(self, output_path: str) -> None:
        Path(output_path).write_bytes(b"fake-mp3" * 256)


async def _fake_list_voices():
    return [
        {"ShortName": "en-US-AriaNeural"},
        {"ShortName": "zh-CN-XiaoxiaoNeural"},
        {"ShortName": "zh-CN-YunxiNeural"},
        {"ShortName": "ja-JP-NanamiNeural"},
        {"ShortName": "fr-FR-DeniseNeural"},
        {"ShortName": "de-DE-KatjaNeural"},
        {"ShortName": "es-ES-ElviraNeural"},
        {"ShortName": "it-IT-ElsaNeural"},
        {"ShortName": "ko-KR-SunHiNeural"},
        {"ShortName": "pt-BR-FranciscaNeural"},
        {"ShortName": "en-GB-SoniaNeural"},
    ]


class TTSTest(unittest.TestCase):
    def test_generate_audio_en(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            with patch("edge_tts.Communicate", _FakeCommunicate):
                audio = narrate_slide("Hello, world.", Path(tmp) / "test.mp3", voice="en-US-AriaNeural")
            self.assertTrue(audio.exists())
            self.assertGreater(audio.stat().st_size, 1000)

    def test_generate_audio_zh(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            with patch("edge_tts.Communicate", _FakeCommunicate):
                audio = narrate_slide("你好，这是一个测试。", Path(tmp) / "test.mp3", voice="zh-CN-XiaoxiaoNeural")
            self.assertTrue(audio.exists())
            self.assertGreater(audio.stat().st_size, 1000)

    def test_list_voices_zh(self) -> None:
        with patch("edge_tts.list_voices", _fake_list_voices):
            voices = list_available_voices("zh-CN")
        self.assertGreater(len(voices), 0)
        self.assertTrue(any("Xiaoxiao" in v for v in voices))

    def test_list_voices_all(self) -> None:
        with patch("edge_tts.list_voices", _fake_list_voices):
            voices = list_available_voices()
        self.assertGreater(len(voices), 10)


class NarrateCLItest(unittest.TestCase):
    def test_narrate_command_exists(self) -> None:
        from slide_skill.cli import main
        import subprocess
        result = subprocess.run(
            ["slide-skill", "narrate", "--help"],
            capture_output=True, text=True
        )
        self.assertEqual(result.returncode, 0)
        self.assertIn("voice", result.stdout)

    def test_voices_command_exists(self) -> None:
        import subprocess
        result = subprocess.run(
            ["slide-skill", "voices", "--help"],
            capture_output=True, text=True
        )
        self.assertEqual(result.returncode, 0)


if __name__ == "__main__":
    unittest.main()
