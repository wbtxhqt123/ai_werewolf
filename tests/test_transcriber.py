import os
import tempfile
import unittest
import wave
from unittest.mock import MagicMock, patch

import numpy as np
from starlette.testclient import TestClient

from web.server import app
from web.transcriber import (
    AudioTranscriber,
    FasterWhisperBackend,
    ParaformerBackend,
    SenseVoiceBackend,
    clean_transcription_text,
    load_audio_16k_mono,
)


def _create_temp_wav(sample_rate: int = 16000, channels: int = 1, duration_sec: float = 0.25) -> str:
    """Creates a temporary 16-bit PCM WAV file for testing."""
    num_samples = int(sample_rate * duration_sec)
    t = np.linspace(0, duration_sec, num_samples, endpoint=False)
    tone = (0.3 * np.sin(2 * np.pi * 440.0 * t) * 32767).astype(np.int16)
    if channels > 1:
        tone = np.repeat(tone[:, None], channels, axis=1).reshape(-1)

    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".wav")
    tmp.close()
    with wave.open(tmp.name, "wb") as wf:
        wf.setnchannels(channels)
        wf.setsampwidth(2)
        wf.setframerate(sample_rate)
        wf.writeframes(tone.tobytes())
    return tmp.name


class TestTranscriber(unittest.TestCase):

    def test_clean_transcription_text_strips_sensevoice_tags(self):
        raw = "<|zh|><|NEUTRAL|><|Speech|><|withitn|> 我觉得 Player 3 是预言家，2号是汗跳狼，看警会流 <|emo_unknown|>"
        self.assertEqual(clean_transcription_text(raw), "我觉得 Player 3 是预言家，2号是悍跳狼，看警徽流")
        self.assertEqual(clean_transcription_text(""), "")

    @patch.object(ParaformerBackend, "__init__", lambda self, **kwargs: None)
    @patch.object(ParaformerBackend, "transcribe", return_value="我是预言家，警徽流留3号和5号")
    def test_audio_transcriber_paraformer_default(self, mock_transcribe):
        transcriber = AudioTranscriber(backend="paraformer")
        self.assertEqual(transcriber.backend_name, "paraformer")
        info = transcriber.get_info()
        self.assertEqual(info["backend"], "paraformer")
        self.assertIn("Paraformer-Large", info["model"])

        result = transcriber.transcribe("dummy.wav", language="zh")
        self.assertEqual(result, "我是预言家，警徽流留3号和5号")
        mock_transcribe.assert_called_once_with("dummy.wav", language="zh")

    def test_load_audio_16k_mono_wav_and_resampling(self):
        wav_48k_stereo = _create_temp_wav(sample_rate=48000, channels=2, duration_sec=0.2)
        try:
            samples, sr = load_audio_16k_mono(wav_48k_stereo, target_sr=16000)
            self.assertEqual(sr, 16000)
            self.assertEqual(samples.dtype, np.float32)
            self.assertAlmostEqual(samples.shape[0], int(16000 * 0.2), delta=5)
            self.assertTrue(np.max(np.abs(samples)) <= 1.0)
        finally:
            if os.path.exists(wav_48k_stereo):
                os.remove(wav_48k_stereo)

    @patch.object(SenseVoiceBackend, "__init__", lambda self, **kwargs: None)
    @patch.object(SenseVoiceBackend, "transcribe", return_value="我是预言家，昨晚查杀了 Player 2")
    def test_audio_transcriber_sensevoice_default(self, mock_transcribe):
        transcriber = AudioTranscriber(backend="sensevoice")
        self.assertEqual(transcriber.backend_name, "sensevoice")
        info = transcriber.get_info()
        self.assertEqual(info["backend"], "sensevoice")
        self.assertIn("SenseVoiceSmall", info["model"])

        result = transcriber.transcribe("dummy.wav", language="zh")
        self.assertEqual(result, "我是预言家，昨晚查杀了 Player 2")
        mock_transcribe.assert_called_once_with("dummy.wav", language="zh")

    @patch.object(SenseVoiceBackend, "__init__", side_effect=RuntimeError("sherpa-onnx not installed"))
    @patch.object(FasterWhisperBackend, "__init__", lambda self, **kwargs: None)
    @patch.object(FasterWhisperBackend, "transcribe", return_value="I think Player 4 is a werewolf.")
    def test_audio_transcriber_fallback_to_faster_whisper(self, mock_fw_transcribe, _mock_sv_init):
        transcriber = AudioTranscriber(backend="sensevoice", whisper_model="large-v3-turbo")
        self.assertEqual(transcriber.backend_name, "faster-whisper")
        info = transcriber.get_info()
        self.assertEqual(info["backend"], "faster-whisper")
        self.assertIn("large-v3-turbo", info["model"])

        result = transcriber.transcribe("dummy.wav", language="en")
        self.assertEqual(result, "I think Player 4 is a werewolf.")
        mock_fw_transcribe.assert_called_once_with("dummy.wav", language="en")

    def test_api_transcribe_endpoint_with_form_language(self):
        wav_path = _create_temp_wav(sample_rate=16000, channels=1, duration_sec=0.15)
        mock_transcriber = MagicMock()
        mock_transcriber.transcribe.return_value = "3号玩家是金水，Please vote Player 5"
        mock_transcriber.get_info.return_value = {
            "backend": "sensevoice",
            "model": "SenseVoiceSmall (int8 ONNX)",
            "device": "auto",
        }

        client = TestClient(app)
        try:
            with patch("web.transcriber.get_transcriber", return_value=mock_transcriber):
                with open(wav_path, "rb") as f:
                    response = client.post(
                        "/api/transcribe",
                        files={"file": ("recording.wav", f, "audio/wav")},
                        data={"language": "zh", "backend": "sensevoice"},
                    )
            self.assertEqual(response.status_code, 200)
            payload = response.json()
            self.assertEqual(payload["text"], "3号玩家是金水，Please vote Player 5")
            self.assertEqual(payload["backend"], "sensevoice")
            self.assertEqual(mock_transcriber.transcribe.call_args.kwargs["language"], "zh")
        finally:
            if os.path.exists(wav_path):
                os.remove(wav_path)

    def test_api_transcribe_status_endpoint(self):
        client = TestClient(app)
        response = client.get("/api/transcribe/status")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn("ready", data)
        self.assertIn("backend", data)
        self.assertIn("percent", data)
        self.assertIn("status", data)

    def test_api_transcribe_requires_model_ready_before_game(self):
        import web.transcriber as tr_mod

        wav_path = _create_temp_wav(sample_rate=16000, channels=1, duration_sec=0.1)
        client = TestClient(app)
        prev_instance = tr_mod._transcriber
        try:
            tr_mod._transcriber = None
            with open(wav_path, "rb") as f:
                response = client.post(
                    "/api/transcribe",
                    files={"file": ("recording.wav", f, "audio/wav")},
                    data={"language": "zh"},
                )
            self.assertEqual(response.status_code, 503)
            self.assertIn("not downloaded/loaded yet", response.json()["detail"])
        finally:
            tr_mod._transcriber = prev_instance
            if os.path.exists(wav_path):
                os.remove(wav_path)

    def test_api_transcribe_prepare_endpoint_updates_progress(self):
        client = TestClient(app)
        mock_status = {
            "status": "downloading",
            "backend": "sensevoice",
            "model": "SenseVoiceSmall (int8 ONNX)",
            "percent": 42.5,
            "downloaded_bytes": 100000000,
            "total_bytes": 235000000,
            "ready": False,
            "message": "Downloading SenseVoiceSmall (95.4 / 224.1 MB)...",
        }
        with patch("web.transcriber.start_model_preparation", return_value=mock_status) as mock_prep:
            res = client.post("/api/transcribe/prepare", json={"backend": "sensevoice"})
            self.assertEqual(res.status_code, 200)
            data = res.json()
            self.assertEqual(data["status"], "downloading")
            self.assertEqual(data["percent"], 42.5)
            mock_prep.assert_called_once_with(backend="sensevoice", whisper_model=None)


if __name__ == "__main__":
    unittest.main()
