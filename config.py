ROLE_CONFIG = {
    6: {
        "Werewolf": 2,
        "Villager": 2,
        "Seer": 1,
        "Witch": 1
    },
    9: {
        "Black Werewolf King": 1,
        "Werewolf": 2,
        "Villager": 3,
        "Seer": 1,
        "Witch": 1,
        "Hunter": 1
    },
    12: {
        "Black Werewolf King": 1,
        "Werewolf": 3,
        "Villager": 4,
        "Seer": 1,
        "Witch": 1,
        "Hunter": 1,
        "Guard": 1
    }
}

HISTORY_DIR = "history"

GAME_RULES = {
    "allow_guard_and_save_conflict": True
}

# LLM Configuration
LLM_MODEL = ""
LLM_API_BASE_URL = ""
LLM_API_KEY_ENV = ""

DEFAULT_PROVIDER = "openai"

LLM_PROVIDERS = {
    "openai": {
        "model": "",
        "api_key_env": "OPENAI_API_KEY",
        "base_url": ""
    },
    "groq": {
        "model": "",
        "api_key_env": "GROQ_API_KEY",
        "base_url": ""
    }
}

# Speech-to-Text (ASR) Configuration
# Supported backends:
#   - "paraformer": Alibaba FunASR Paraformer-Large (ONNX via sherpa-onnx, ~220MB, high-accuracy ZH/EN + Werewolf jargon)
#   - "faster-whisper": Whisper models via MLX-Whisper (Mac Metal GPU) or CTranslate2 (CUDA/CPU, e.g. "large-v3-turbo", ~800MB)
#   - "sensevoice": Alibaba SenseVoiceSmall (legacy ONNX via sherpa-onnx, ~230MB)
import os as _os

ASR_CONFIG = {
    "backend": _os.getenv("ASR_BACKEND", "paraformer"),
    "paraformer_repo_id": _os.getenv(
        "ASR_PARAFORMER_REPO",
        "csukuangfj/sherpa-onnx-paraformer-zh-2024-03-09",
    ),
    "sensevoice_repo_id": _os.getenv(
        "ASR_SENSEVOICE_REPO",
        "csukuangfj/sherpa-onnx-sense-voice-zh-en-ja-ko-yue-2024-07-17",
    ),
    "whisper_model": _os.getenv("ASR_WHISPER_MODEL", "large-v3-turbo"),
    "device": _os.getenv("ASR_DEVICE", "auto"),
    "compute_type": _os.getenv("ASR_COMPUTE_TYPE", "int8"),
    "num_threads": int(_os.getenv("ASR_NUM_THREADS", str(min(8, _os.cpu_count() or 4)))),
    "cache_dir": _os.getenv("ASR_CACHE_DIR", _os.path.join(_os.path.expanduser("~"), ".cache", "werewolf_asr")),
}

