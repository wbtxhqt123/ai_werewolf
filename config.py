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
