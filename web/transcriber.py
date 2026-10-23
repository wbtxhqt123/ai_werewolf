import logging
import os
import re
import shutil
import subprocess
import threading
import urllib.request
import wave
from typing import Any, Callable, Dict, Optional, Tuple, Union

import numpy as np

from config import ASR_CONFIG

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Domain-specific prompt for Whisper to boost Werewolf terminology and bilingual ZH/EN accuracy
WEREWOLF_DOMAIN_PROMPT_ZH = (
    "简体中文，English。狼人杀游戏发言：预言家、女巫、猎人、守卫、白狼王、狼人、村民、"
    "警长、上警、退水、金水、查杀、银水、自刀、悍跳、倒钩、冲票、归票、"
    "1号玩家、2号玩家、3号玩家、4号玩家、5号玩家、6号玩家、7号玩家、8号玩家、9号玩家、Player 1、Player 2。"
)
WEREWOLF_DOMAIN_PROMPT_EN = (
    "Werewolf social deduction game speech (English & Chinese): "
    "Seer, Witch, Hunter, Guard, Black Werewolf King, Werewolf, Villager, Sheriff, "
    "Player 1, Player 2, Player 3, Player 4, Player 5, Player 6, Player 7, Player 8, Player 9."
)

SENSEVOICE_TAG_PATTERN = re.compile(r"<\|[^|>]+?\|>")

# Thread-safe global progress state for pre-game model downloading & initialization
_progress_lock = threading.Lock()
_download_state: Dict[str, Any] = {
    "status": "not_downloaded",  # "not_downloaded" | "downloading" | "loading" | "ready" | "error"
    "backend": ASR_CONFIG.get("backend", "sensevoice"),
    "model": "SenseVoiceSmall (int8 ONNX)"
    if ASR_CONFIG.get("backend", "sensevoice") == "sensevoice"
    else f"Faster-Whisper ({ASR_CONFIG.get('whisper_model', 'large-v3-turbo')})",
    "percent": 0.0,
    "downloaded_bytes": 0,
    "total_bytes": 0,
    "current_file": "",
    "message": "Voice model not downloaded yet.",
    "error": None,
}


def _update_progress(**kwargs: Any) -> None:
    with _progress_lock:
        _download_state.update(kwargs)


def get_download_status() -> Dict[str, Any]:
    """Returns a snapshot of the current model download/readiness state."""
    with _progress_lock:
        snapshot = dict(_download_state)
    snapshot["ready"] = snapshot.get("status") == "ready" and _transcriber is not None
    return snapshot


def is_model_cached(
    backend: Optional[str] = None,
    sensevoice_repo_id: Optional[str] = None,
    whisper_model: Optional[str] = None,
    cache_dir: Optional[str] = None,
) -> bool:
    """Checks whether the selected ASR model files already exist on disk."""
    backend_name = (backend or ASR_CONFIG.get("backend", "sensevoice")).strip().lower()
    resolved_cache = cache_dir or ASR_CONFIG.get(
        "cache_dir", os.path.join(os.path.expanduser("~"), ".cache", "werewolf_asr")
    )

    if backend_name == "sensevoice":
        repo_id = sensevoice_repo_id or ASR_CONFIG.get(
            "sensevoice_repo_id",
            "csukuangfj/sherpa-onnx-sense-voice-zh-en-ja-ko-yue-2024-07-17",
        )
        if os.path.isdir(repo_id):
            has_model = os.path.exists(os.path.join(repo_id, "model.int8.onnx")) or os.path.exists(
                os.path.join(repo_id, "model.onnx")
            )
            has_tokens = os.path.exists(os.path.join(repo_id, "tokens.txt"))
            return has_model and has_tokens

        model_dir = os.path.join(resolved_cache, "sensevoice")
        has_model = os.path.exists(os.path.join(model_dir, "model.int8.onnx")) or os.path.exists(
            os.path.join(model_dir, "model.onnx")
        )
        has_tokens = os.path.exists(os.path.join(model_dir, "tokens.txt"))
        return has_model and has_tokens and os.path.getsize(os.path.join(model_dir, "tokens.txt")) > 0

    # faster-whisper check
    w_model = whisper_model or ASR_CONFIG.get("whisper_model", "large-v3-turbo")
    if os.path.isdir(w_model):
        return os.path.exists(os.path.join(w_model, "model.bin"))
    fw_dir = os.path.join(resolved_cache, "faster_whisper", w_model.replace("/", "--"))
    return os.path.exists(os.path.join(fw_dir, "model.bin"))


def download_file_with_progress(
    url: str,
    dest_path: str,
    progress_callback: Optional[Callable[[int, int], None]] = None,
    chunk_size: int = 262144,
) -> str:
    """Streams a file from `url` to `dest_path` while reporting `(downloaded_bytes, total_bytes)`."""
    os.makedirs(os.path.dirname(dest_path), exist_ok=True)
    part_path = dest_path + ".part"
    req = urllib.request.Request(url, headers={"User-Agent": "Werewolf-ASR-Downloader/1.0"})
    with urllib.request.urlopen(req, timeout=60) as resp:
        total_header = resp.headers.get("Content-Length")
        total_bytes = int(total_header) if total_header and total_header.isdigit() else 0
        downloaded = 0
        with open(part_path, "wb") as out_f:
            while True:
                chunk = resp.read(chunk_size)
                if not chunk:
                    break
                out_f.write(chunk)
                downloaded += len(chunk)
                if progress_callback:
                    progress_callback(downloaded, total_bytes)
    os.replace(part_path, dest_path)
    return dest_path


def clean_transcription_text(text: str) -> str:
    """Removes special ASR control/emotion tags (e.g., <|zh|><|NEUTRAL|><|Speech|>) and normalizes whitespace."""
    if not text:
        return ""
    cleaned = SENSEVOICE_TAG_PATTERN.sub("", text)
    return re.sub(r"\s+", " ", cleaned).strip()


def load_audio_16k_mono(audio_path: str, target_sr: int = 16000) -> Tuple[np.ndarray, int]:
    """Loads an audio file from disk and converts it into a 16kHz mono float32 numpy array in [-1.0, 1.0]."""
    if not os.path.exists(audio_path) or os.path.getsize(audio_path) == 0:
        raise ValueError("Audio file is empty or does not exist.")

    # 1. Fast path: built-in wave module for PCM WAV files
    try:
        with wave.open(audio_path, "rb") as wf:
            channels = wf.getnchannels()
            sample_width = wf.getsampwidth()
            sample_rate = wf.getframerate()
            num_frames = wf.getnframes()
            raw_bytes = wf.readframes(num_frames)

            if sample_width == 2:
                samples = np.frombuffer(raw_bytes, dtype=np.int16).astype(np.float32) / 32768.0
            elif sample_width == 4:
                samples = np.frombuffer(raw_bytes, dtype=np.int32).astype(np.float32) / 2147483648.0
            elif sample_width == 1:
                samples = (np.frombuffer(raw_bytes, dtype=np.uint8).astype(np.float32) - 128.0) / 128.0
            else:
                raise ValueError(f"Unsupported WAV sample width: {sample_width}")

            if channels > 1:
                samples = samples.reshape(-1, channels).mean(axis=1)

            if sample_rate != target_sr and samples.size > 0:
                duration = samples.shape[0] / float(sample_rate)
                target_length = max(1, int(round(duration * target_sr)))
                old_indices = np.linspace(0.0, 1.0, num=samples.shape[0], endpoint=False)
                new_indices = np.linspace(0.0, 1.0, num=target_length, endpoint=False)
                samples = np.interp(new_indices, old_indices, samples).astype(np.float32)

            return samples, target_sr
    except (wave.Error, EOFError):
        pass

    # 2. Try faster-whisper / PyAV decoder (handles WebM, MP4, M4A, MP3, WAV without system ffmpeg)
    try:
        from faster_whisper.audio import decode_audio

        samples = decode_audio(audio_path, sampling_rate=target_sr)
        return np.asarray(samples, dtype=np.float32), target_sr
    except Exception:
        pass

    # 3. Try system ffmpeg CLI if installed on Mac/PC
    ffmpeg_bin = shutil.which("ffmpeg")
    if ffmpeg_bin:
        cmd = [
            ffmpeg_bin,
            "-nostdin",
            "-threads",
            "0",
            "-i",
            audio_path,
            "-f",
            "s16le",
            "-ac",
            "1",
            "-acodec",
            "pcm_s16le",
            "-ar",
            str(target_sr),
            "-",
        ]
        proc = subprocess.run(cmd, capture_output=True, check=False)
        if proc.returncode == 0 and proc.stdout:
            samples = np.frombuffer(proc.stdout, dtype=np.int16).astype(np.float32) / 32768.0
            return samples, target_sr

    raise RuntimeError(
        "Unable to decode non-WAV audio format. Either send 16kHz WAV audio from the client, "
        "install 'faster-whisper' (bundles PyAV), or install 'ffmpeg'."
    )


class SenseVoiceBackend:
    """Alibaba SenseVoiceSmall backend powered by sherpa-onnx (int8 quantized ONNX)."""

    def __init__(
        self,
        repo_id: str,
        cache_dir: str,
        num_threads: int = 4,
        device: str = "auto",
    ):
        try:
            import sherpa_onnx
        except ImportError as e:
            raise RuntimeError(
                "SenseVoiceSmall backend requires 'sherpa-onnx'. "
                "Please install audio dependencies via: pip install -r requirements-audio.txt"
            ) from e

        self.repo_id = repo_id
        self.cache_dir = cache_dir
        self.num_threads = max(1, int(num_threads))
        self.provider = self._resolve_provider(device)

        model_path, tokens_path = self._ensure_model_files()
        _update_progress(
            status="loading",
            percent=95.0,
            message="Loading SenseVoiceSmall into memory...",
        )
        logger.info(
            f"Loading SenseVoiceSmall ONNX model from {model_path} "
            f"(provider={self.provider}, threads={self.num_threads})"
        )
        self.recognizer = sherpa_onnx.OfflineRecognizer.from_sense_voice(
            model=model_path,
            tokens=tokens_path,
            num_threads=self.num_threads,
            use_itn=True,
            debug=False,
            provider=self.provider,
        )

    @staticmethod
    def _resolve_provider(device: str) -> str:
        if not device or device == "auto":
            return "cpu"
        dev = device.lower()
        if dev in ("cuda", "coreml", "cpu"):
            return dev
        return "cpu"

    def _ensure_model_files(self) -> Tuple[str, str]:
        """Downloads or locates SenseVoiceSmall int8 ONNX model and tokens.txt with real-time byte progress."""
        if os.path.isdir(self.repo_id):
            local_dir = self.repo_id
            int8_candidate = os.path.join(local_dir, "model.int8.onnx")
            fp32_candidate = os.path.join(local_dir, "model.onnx")
            model_path = int8_candidate if os.path.exists(int8_candidate) else fp32_candidate
            tokens_path = os.path.join(local_dir, "tokens.txt")
            if not os.path.exists(model_path) or not os.path.exists(tokens_path):
                raise FileNotFoundError(
                    f"SenseVoice model directory '{local_dir}' must contain model.int8.onnx (or model.onnx) and tokens.txt"
                )
            return model_path, tokens_path

        target_dir = os.path.join(self.cache_dir, "sensevoice")
        os.makedirs(target_dir, exist_ok=True)
        model_path = os.path.join(target_dir, "model.int8.onnx")
        tokens_path = os.path.join(target_dir, "tokens.txt")

        base_url = f"https://huggingface.co/{self.repo_id}/resolve/main"

        if not os.path.exists(tokens_path) or os.path.getsize(tokens_path) == 0:
            _update_progress(
                status="downloading",
                current_file="tokens.txt",
                percent=2.0,
                message="Downloading tokens.txt...",
            )
            download_file_with_progress(f"{base_url}/tokens.txt", tokens_path)

        if not os.path.exists(model_path) or os.path.getsize(model_path) == 0:
            def on_progress(downloaded: int, total: int) -> None:
                pct = (downloaded / total * 90.0 + 3.0) if total > 0 else 50.0
                mb_done = downloaded / (1024 * 1024)
                mb_total = total / (1024 * 1024) if total > 0 else 230.0
                _update_progress(
                    status="downloading",
                    current_file="model.int8.onnx",
                    downloaded_bytes=downloaded,
                    total_bytes=total,
                    percent=round(min(93.0, pct), 1),
                    message=f"Downloading SenseVoiceSmall ({mb_done:.1f} / {mb_total:.1f} MB)...",
                )

            _update_progress(
                status="downloading",
                current_file="model.int8.onnx",
                percent=3.0,
                message="Downloading SenseVoiceSmall (model.int8.onnx)...",
            )
            download_file_with_progress(
                f"{base_url}/model.int8.onnx",
                model_path,
                progress_callback=on_progress,
            )

        return model_path, tokens_path

    def transcribe(self, audio_path: str, language: Optional[str] = None) -> str:
        samples, sample_rate = load_audio_16k_mono(audio_path, target_sr=16000)
        if samples.size == 0:
            return ""
        stream = self.recognizer.create_stream()
        stream.accept_waveform(sample_rate, samples)
        self.recognizer.decode_stream(stream)
        raw_text = getattr(stream.result, "text", "") or ""
        return clean_transcription_text(raw_text)


class FasterWhisperBackend:
    """Whisper backend powered by CTranslate2 (`faster-whisper`)."""

    REPO_MAP = {
        "large-v3-turbo": "mobiuslabsgmbh/faster-whisper-large-v3-turbo",
        "turbo": "mobiuslabsgmbh/faster-whisper-large-v3-turbo",
        "small": "Systran/faster-whisper-small",
        "base": "Systran/faster-whisper-base",
        "medium": "Systran/faster-whisper-medium",
        "large-v3": "Systran/faster-whisper-large-v3",
    }

    def __init__(
        self,
        model_size: str = "large-v3-turbo",
        device: str = "auto",
        compute_type: str = "int8",
        num_threads: int = 4,
        cache_dir: Optional[str] = None,
    ):
        try:
            from faster_whisper import WhisperModel
        except ImportError as e:
            raise RuntimeError(
                "Faster-Whisper backend requires 'faster-whisper'. "
                "Please install audio dependencies via: pip install -r requirements-audio.txt"
            ) from e

        resolved_device, resolved_compute = self._resolve_device_and_compute(device, compute_type)
        self.model_size = model_size
        self.cache_dir = cache_dir or os.path.join(os.path.expanduser("~"), ".cache", "werewolf_asr")
        local_model_dir = self._ensure_whisper_files(model_size)

        _update_progress(
            status="loading",
            percent=95.0,
            message=f"Loading Faster-Whisper ({model_size}) into memory...",
        )
        logger.info(
            f"Loading Faster-Whisper model '{model_size}' "
            f"(device={resolved_device}, compute_type={resolved_compute}, threads={num_threads})"
        )
        self.model = WhisperModel(
            local_model_dir,
            device=resolved_device,
            compute_type=resolved_compute,
            cpu_threads=max(1, int(num_threads)),
            download_root=self.cache_dir,
        )

    def _ensure_whisper_files(self, model_size: str) -> str:
        if os.path.isdir(model_size):
            return model_size

        repo_id = self.REPO_MAP.get(model_size, model_size if "/" in model_size else f"Systran/faster-whisper-{model_size}")
        target_dir = os.path.join(self.cache_dir, "faster_whisper", model_size.replace("/", "--"))
        os.makedirs(target_dir, exist_ok=True)

        base_url = f"https://huggingface.co/{repo_id}/resolve/main"
        small_files = ["config.json", "tokenizer.json", "vocabulary.json", "vocabulary.txt", "preprocessor_config.json"]
        for idx, fname in enumerate(small_files):
            fpath = os.path.join(target_dir, fname)
            if not os.path.exists(fpath):
                try:
                    _update_progress(
                        status="downloading",
                        current_file=fname,
                        percent=float(idx + 1),
                        message=f"Downloading {fname}...",
                    )
                    download_file_with_progress(f"{base_url}/{fname}", fpath)
                except Exception:
                    pass

        model_bin_path = os.path.join(target_dir, "model.bin")
        if not os.path.exists(model_bin_path) or os.path.getsize(model_bin_path) == 0:
            def on_progress(downloaded: int, total: int) -> None:
                pct = (downloaded / total * 88.0 + 5.0) if total > 0 else 50.0
                mb_done = downloaded / (1024 * 1024)
                mb_total = total / (1024 * 1024) if total > 0 else 800.0
                _update_progress(
                    status="downloading",
                    current_file="model.bin",
                    downloaded_bytes=downloaded,
                    total_bytes=total,
                    percent=round(min(93.0, pct), 1),
                    message=f"Downloading Faster-Whisper {model_size} ({mb_done:.1f} / {mb_total:.1f} MB)...",
                )

            _update_progress(
                status="downloading",
                current_file="model.bin",
                percent=5.0,
                message=f"Downloading Faster-Whisper ({model_size})...",
            )
            download_file_with_progress(f"{base_url}/model.bin", model_bin_path, progress_callback=on_progress)

        return target_dir

    @staticmethod
    def _resolve_device_and_compute(device: str, compute_type: str) -> Tuple[str, str]:
        resolved_device = "cpu"
        if device and device.lower() in ("cuda", "cpu"):
            resolved_device = device.lower()
        elif not device or device.lower() == "auto":
            try:
                import ctranslate2

                if ctranslate2.get_cuda_device_count() > 0:
                    resolved_device = "cuda"
            except Exception:
                resolved_device = "cpu"

        resolved_compute = compute_type or ("int8_float16" if resolved_device == "cuda" else "int8")
        if resolved_device == "cpu" and resolved_compute in ("float16", "int8_float16"):
            resolved_compute = "int8"
        return resolved_device, resolved_compute

    def transcribe(self, audio_path: str, language: Optional[str] = None) -> str:
        samples, _ = load_audio_16k_mono(audio_path, target_sr=16000)
        if samples.size == 0:
            return ""

        norm_lang = None
        if language and language.lower() in ("zh", "en"):
            norm_lang = language.lower()

        prompt = WEREWOLF_DOMAIN_PROMPT_ZH if norm_lang != "en" else WEREWOLF_DOMAIN_PROMPT_EN

        segments, _info = self.model.transcribe(
            samples,
            language=None if norm_lang == "auto" else norm_lang,
            initial_prompt=prompt,
            vad_filter=True,
            vad_parameters={"min_silence_duration_ms": 400},
            beam_size=2,
            condition_on_previous_text=False,
        )
        text = " ".join(seg.text.strip() for seg in segments if seg.text and seg.text.strip())
        return clean_transcription_text(text)


class AudioTranscriber:
    """Unified cross-platform speech-to-text manager for Chinese & English gameplay."""

    def __init__(
        self,
        backend: Optional[str] = None,
        whisper_model: Optional[str] = None,
        sensevoice_repo_id: Optional[str] = None,
        device: Optional[str] = None,
        compute_type: Optional[str] = None,
        num_threads: Optional[int] = None,
        cache_dir: Optional[str] = None,
    ):
        self.backend_name = (backend or ASR_CONFIG.get("backend", "sensevoice")).strip().lower()
        self.whisper_model = whisper_model or ASR_CONFIG.get("whisper_model", "large-v3-turbo")
        self.sensevoice_repo_id = sensevoice_repo_id or ASR_CONFIG.get(
            "sensevoice_repo_id",
            "csukuangfj/sherpa-onnx-sense-voice-zh-en-ja-ko-yue-2024-07-17",
        )
        self.device = device or ASR_CONFIG.get("device", "auto")
        self.compute_type = compute_type or ASR_CONFIG.get("compute_type", "int8")
        self.num_threads = int(num_threads or ASR_CONFIG.get("num_threads", 4))
        self.cache_dir = cache_dir or ASR_CONFIG.get(
            "cache_dir", os.path.join(os.path.expanduser("~"), ".cache", "werewolf_asr")
        )

        self.engine = self._init_engine()
        info = self.get_info()
        _update_progress(
            status="ready",
            backend=info["backend"],
            model=info["model"],
            percent=100.0,
            current_file="",
            message=f"{info['model']} is ready.",
            error=None,
        )

    def _init_engine(self) -> Union[SenseVoiceBackend, FasterWhisperBackend]:
        errors = []
        order = (
            ["sensevoice", "faster-whisper"]
            if self.backend_name != "faster-whisper"
            else ["faster-whisper", "sensevoice"]
        )

        for candidate in order:
            try:
                if candidate == "sensevoice":
                    engine = SenseVoiceBackend(
                        repo_id=self.sensevoice_repo_id,
                        cache_dir=self.cache_dir,
                        num_threads=self.num_threads,
                        device=self.device,
                    )
                    self.backend_name = "sensevoice"
                    return engine
                else:
                    engine = FasterWhisperBackend(
                        model_size=self.whisper_model,
                        device=self.device,
                        compute_type=self.compute_type,
                        num_threads=self.num_threads,
                        cache_dir=self.cache_dir,
                    )
                    self.backend_name = "faster-whisper"
                    return engine
            except Exception as e:
                logger.warning(f"ASR backend '{candidate}' unavailable: {e}")
                errors.append(f"{candidate}: {e}")

        err_msg = (
            "No speech-to-text backend could be initialized. "
            "Please install dependencies via `pip install -r requirements-audio.txt`. "
            f"Details: {'; '.join(errors)}"
        )
        _update_progress(status="error", message=err_msg, error=err_msg)
        raise RuntimeError(err_msg)

    def get_info(self) -> Dict[str, str]:
        """Returns metadata about the active transcription backend and model."""
        model_label = (
            "SenseVoiceSmall (int8 ONNX)"
            if self.backend_name == "sensevoice"
            else f"Faster-Whisper ({self.whisper_model})"
        )
        return {
            "backend": self.backend_name,
            "model": model_label,
            "device": self.device,
        }

    def transcribe(self, audio_input: str, language: Optional[str] = None) -> str:
        """Transcribes an audio file path into text (Chinese, English, or mixed)."""
        try:
            text = self.engine.transcribe(audio_input, language=language)
            logger.info(f"[{self.backend_name}] Transcription result: {text}")
            return text
        except Exception as e:
            logger.error(f"Error during transcription with {self.backend_name}: {e}")
            return ""


_transcriber: Optional[AudioTranscriber] = None
_transcriber_lock = threading.Lock()
_prepare_thread: Optional[threading.Thread] = None


def get_transcriber(
    backend: Optional[str] = None,
    whisper_model: Optional[str] = None,
    force_reload: bool = False,
    require_ready: bool = False,
) -> AudioTranscriber:
    """Returns a thread-safe singleton instance of `AudioTranscriber`.

    If `require_ready=True`, raises RuntimeError if the model has not been downloaded
    and initialized prior to starting the game.
    """
    global _transcriber
    with _transcriber_lock:
        if require_ready and _transcriber is None:
            raise RuntimeError(
                "Voice transcription model is not downloaded/loaded yet. "
                "Please download and initialize the voice model in the game lobby before using voice input."
            )
        if (
            _transcriber is None
            or force_reload
            or (backend and backend.lower() != _transcriber.backend_name)
            or (whisper_model and _transcriber.backend_name == "faster-whisper" and whisper_model != _transcriber.whisper_model)
        ):
            _transcriber = AudioTranscriber(
                backend=backend,
                whisper_model=whisper_model,
            )
        return _transcriber


def start_model_preparation(
    backend: Optional[str] = None,
    whisper_model: Optional[str] = None,
) -> Dict[str, Any]:
    """Starts downloading and initializing the selected ASR model in a background thread if not already running."""
    global _prepare_thread
    target_backend = (backend or ASR_CONFIG.get("backend", "sensevoice")).strip().lower()
    target_whisper = whisper_model or ASR_CONFIG.get("whisper_model", "large-v3-turbo")

    current = get_download_status()
    if current["status"] in ("downloading", "loading") and _prepare_thread and _prepare_thread.is_alive():
        return current

    if (
        current["ready"]
        and _transcriber is not None
        and _transcriber.backend_name == target_backend
        and (target_backend != "faster-whisper" or _transcriber.whisper_model == target_whisper)
    ):
        return current

    model_label = (
        "SenseVoiceSmall (int8 ONNX)"
        if target_backend == "sensevoice"
        else f"Faster-Whisper ({target_whisper})"
    )
    _update_progress(
        status="downloading",
        backend=target_backend,
        model=model_label,
        percent=1.0,
        downloaded_bytes=0,
        total_bytes=0,
        current_file="",
        message=f"Preparing {model_label}...",
        error=None,
    )

    def _worker() -> None:
        try:
            get_transcriber(
                backend=target_backend,
                whisper_model=target_whisper,
                force_reload=True,
            )
        except Exception as e:
            logger.error(f"Model preparation failed: {e}")
            _update_progress(
                status="error",
                message=str(e),
                error=str(e),
            )

    _prepare_thread = threading.Thread(target=_worker, daemon=True)
    _prepare_thread.start()
    return get_download_status()
