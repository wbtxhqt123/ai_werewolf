from __future__ import annotations
import json
import random
import re
from typing import TYPE_CHECKING, Any
import os
from openai import OpenAI

from config import LLM_MODEL, LLM_API_BASE_URL, LLM_API_KEY_ENV
from game.controllers import Controller, SafeController
from game.player import Player, Witch, Werewolf, Seer, Guard, Hunter, BlackWerewolfKing
from game.log import LogEntry, LogType

if TYPE_CHECKING:
    from game.game import Game


class LLMClient:
    """Handles communication with a Large Language Model API.

    This client is designed to be compatible with any API that follows the OpenAI
    interface. It retrieves API credentials and model configurations from the main
    `config.py` file, allowing for flexible integration with different LLM providers.

    Attributes:
        client: An instance of the `OpenAI` client, configured with the appropriate
            API key, base URL, and model name.
    """
    def __init__(self, api_key: str | None = None, base_url: str | None = None, model: str | None = None, provider: str | None = None):
        """Initializes the LLM client.

        Args:
            api_key: The API key for the LLM service. If not provided, it will be
                loaded from the environment variable specified in the config.
            base_url: The base URL for the LLM API. If not provided, the default
                from the config is used.
            model: The name of the model to use. If not provided, the default from
                the config is used.
            provider: The name of the LLM provider (e.g., 'openai', 'groq'). This
                is used to look up the provider-specific configuration.
        """
        from config import LLM_PROVIDERS, DEFAULT_PROVIDER, LLM_API_KEY_ENV, LLM_API_BASE_URL, LLM_MODEL
        
        # Determine provider config
        if provider and provider in LLM_PROVIDERS:
            provider_config = LLM_PROVIDERS[provider]
            self.base_url = base_url or provider_config["base_url"] or None
            self.model = model or provider_config["model"]
            api_key_env = provider_config["api_key_env"]
            self.api_key = api_key or os.getenv(api_key_env)
        else:
            # Fallback to global defaults
            self.base_url = base_url or LLM_API_BASE_URL or None
            self.model = model or LLM_MODEL
            self.api_key = api_key or (os.getenv(LLM_API_KEY_ENV) if LLM_API_KEY_ENV else None)

        if not self.model:
            default_models = {
                "openai": "gpt-4o",
                "doubao": "doubao-seed-1-6-flash-250828",
                "gemini": "gemini-1.5-flash",
                "qwen": "qwen-plus",
                "deepseek": "deepseek-chat",
                "groq": "llama-3.3-70b-versatile",
            }
            self.model = default_models.get(provider or "", "gpt-4o")

        if self.api_key:
            self.api_key = self.api_key.strip()
        else:
            print(f"Warning: API Key not found for provider {provider} or environment.")
        
        self.temperature: float | None = None
        self.client = OpenAI(
            base_url=self.base_url,
            api_key=self.api_key,
        )

    def get_completion(self, prompt: str, json_mode: bool = True, temperature: float | None = None) -> str:
        """Sends a prompt to the LLM and returns the generated completion.

        Args:
            prompt: The complete prompt to send to the model.
            json_mode: When True, requests structured JSON object output from the API.
            temperature: Optional sampling temperature override.

        Returns:
            The content of the LLM's response as a string. In case of an API error,
            it returns a JSON string with an error message.
        """
        messages = [
            {
                "role": "user",
                "content": prompt
            }
        ]
        try:
            kwargs: dict[str, Any] = {
                "model": self.model,
                "messages": messages,
            }
            eff_temp = temperature if temperature is not None else self.temperature
            if eff_temp is not None:
                kwargs["temperature"] = eff_temp
            if json_mode:
                kwargs["response_format"] = {"type": "json_object"}
            try:
                response = self.client.chat.completions.create(**kwargs)
            except Exception as api_err:
                err_str = str(api_err).lower()
                if json_mode and ("response_format" in err_str or "json_object" in err_str):
                    kwargs.pop("response_format", None)
                    response = self.client.chat.completions.create(**kwargs)
                elif "temperature" in err_str and "temperature" in kwargs:
                    kwargs.pop("temperature", None)
                    response = self.client.chat.completions.create(**kwargs)
                else:
                    raise
            return response.choices[0].message.content
        except Exception as e:
            import traceback
            traceback.print_exc()
            print(f"Error calling LLM API: {e}")
            # Fallback to a safe default to prevent crashes.
            return json.dumps({"thought": f"Error calling LLM: {e}", "action": {}})

# This is a placeholder. In a real scenario, you would use a library like openai
# and have API key management.
class MockLLMClient:
    """A mock version of the LLM client for testing and development.

    This class simulates the behavior of the `LLMClient` without making actual API
    calls. It returns pre-defined or randomized responses based on keywords found
    in the prompt, which is useful for running the game without an active internet
    connection or API key.
    """
    temperature: float | None = None

    def get_completion(self, prompt: str) -> str:
        print("\n--- LLM PROMPT ---")
        print(prompt)
        print("--- END PROMPT ---\n")

        # This mock implementation uses simple keyword matching to generate a plausible
        # JSON response for different actions.
        if "what do you say?" in prompt.lower():
            action = {"speech": "I think we should vote out someone suspicious."}
        elif "who do you vote to execute?" in prompt.lower():
            action = {"vote": None} # Abstain by default
        elif "run for sheriff?" in prompt.lower():
            action = {"run_for_sheriff": random.choice([True, False])}
        elif "withdraw_sheriff" in prompt.lower() or "退水" in prompt.lower():
            action = {"withdraw_sheriff": False}
        elif "vote for to be sheriff?" in prompt.lower():
            action = {"vote_for_sheriff": None} # Abstain
        elif "choose a player to eliminate" in prompt.lower():
            action = {"kill": None} # Should pick a target
        elif "witch" in prompt.lower() and "save" in prompt.lower():
             action = {"save": None, "poison": None}
        else:
            action = {}

        response = {
            "thought": "As a mock LLM, I'm making a semi-random decision based on keywords in the prompt.",
            "action": action
        }
        return json.dumps(response)


def extract_json(response_str: str) -> dict:
    """Extracts and parses a JSON dictionary from an LLM response string.

    Handles markdown code fences (```json ... ```), conversational preambles/postambles,
    and embedded JSON objects.

    Args:
        response_str: The raw string response from the LLM.

    Returns:
        The parsed dictionary.

    Raises:
        json.JSONDecodeError: If no valid JSON dictionary can be extracted.
    """
    if not response_str or not isinstance(response_str, str):
        raise json.JSONDecodeError("Response is empty or not a string", str(response_str), 0)

    text = response_str.strip()

    # 1. Try direct parsing
    try:
        parsed = json.loads(text)
        if isinstance(parsed, dict):
            return parsed
    except json.JSONDecodeError:
        pass

    # 2. Extract from markdown code fences: ```json ... ``` or ``` ... ```
    fence_pattern = r"```(?:json)?\s*([\s\S]*?)\s*```"
    fence_matches = re.findall(fence_pattern, text, re.IGNORECASE)
    for block in fence_matches:
        try:
            parsed = json.loads(block.strip())
            if isinstance(parsed, dict):
                return parsed
        except json.JSONDecodeError:
            pass

    # 3. Regex extraction: search for outermost JSON object candidate
    brace_match = re.search(r"\{[\s\S]*\}", text)
    if brace_match:
        try:
            parsed = json.loads(brace_match.group(0))
            if isinstance(parsed, dict):
                return parsed
        except json.JSONDecodeError:
            pass

    # 4. Balanced brace scan for embedded JSON objects (handles commentary around braces)
    start = -1
    depth = 0
    in_string = False
    escape = False
    for i, ch in enumerate(text):
        if escape:
            escape = False
            continue
        if ch == "\\":
            if in_string:
                escape = True
            continue
        if ch == '"':
            in_string = not in_string
            continue
        if in_string:
            continue

        if ch == "{":
            if depth == 0:
                start = i
            depth += 1
        elif ch == "}":
            if depth > 0:
                depth -= 1
                if depth == 0 and start != -1:
                    candidate = text[start : i + 1]
                    try:
                        parsed = json.loads(candidate)
                        if isinstance(parsed, dict):
                            return parsed
                    except json.JSONDecodeError:
                        pass
                    start = -1

    raise json.JSONDecodeError(f"Could not extract valid JSON object from response: {text[:100]}...", text, 0)


ACTION_SCHEMAS: dict[str, dict[str, Any]] = {
    "speech": {
        "keys": ("speech",),
        "type": "non_empty_str",
        "example": '{"thought": "...", "action": {"speech": "Your speech here"}}',
    },
    "vote": {
        "keys": ("vote",),
        "type": "optional_target",
        "example": '{"thought": "...", "action": {"vote": "Player 1"}}',
    },
    "werewolf_kill": {
        "keys": ("kill",),
        "type": "optional_target",
        "example": '{"thought": "...", "action": {"kill": "Player 1"}}',
    },
    "witch_action": {
        "keys": ("save", "poison"),
        "type": "witch",
        "example": '{"thought": "...", "action": {"save": false, "poison": null}}',
    },
    "vote_for_sheriff": {
        "keys": ("vote_for_sheriff",),
        "type": "optional_target",
        "example": '{"thought": "...", "action": {"vote_for_sheriff": "Player 1"}}',
    },
    "run_for_sheriff": {
        "keys": ("run_for_sheriff",),
        "type": "bool",
        "example": '{"thought": "...", "action": {"run_for_sheriff": true}}',
    },
    "withdraw_sheriff": {
        "keys": ("withdraw_sheriff",),
        "type": "bool",
        "example": '{"thought": "...", "action": {"withdraw_sheriff": false}}',
    },
    "seer_action": {
        "keys": ("check",),
        "type": "optional_target",
        "example": '{"thought": "...", "action": {"check": "Player 1"}}',
    },
    "guard_protect": {
        "keys": ("protect",),
        "type": "optional_target",
        "example": '{"thought": "...", "action": {"protect": "Player 1"}}',
    },
    "hunter_shoot": {
        "keys": ("shoot",),
        "type": "optional_target",
        "example": '{"thought": "...", "action": {"shoot": "Player 1"}}',
    },
    "decide_speech_order": {
        "keys": ("speech_order",),
        "type": "speech_order",
        "example": '{"thought": "...", "action": {"speech_order": "clockwise"}}',
    },
    "sheriff_death": {
        "keys": ("pass_badge",),
        "type": "optional_target",
        "example": '{"thought": "...", "action": {"pass_badge": "Player 1"}}',
    },
    "summarize_day": {
        "keys": ("summary",),
        "type": "top_level_str",
        "example": '{"summary": "..."}',
    },
}


def _coerce_bool(val: Any) -> bool | None:
    if isinstance(val, bool):
        return val
    if isinstance(val, str):
        low = val.strip().lower()
        if low in ("true", "yes", "1"):
            return True
        if low in ("false", "no", "0", "none", "null", ""):
            return False
    return None


def _coerce_optional_target(val: Any) -> tuple[bool, str | None]:
    if val is None or val is False:
        return True, None
    if isinstance(val, int) and not isinstance(val, bool):
        return True, f"Player {val}"
    if isinstance(val, str):
        clean = val.strip()
        if clean.lower() in ("", "none", "null", "abstain", "弃票", "不投", "不使用", "不开枪"):
            return True, None
        return True, clean
    return False, None


PERSONALITY_TEMPERATURES: dict[str, float] = {
    "analytical": 0.55,
    "cautious": 0.60,
    "silent": 0.65,
    "diplomat": 0.70,
    "follower": 0.72,
    "paranoid": 0.80,
    "emotional": 0.85,
    "aggressive": 0.88,
    "manipulative": 0.90,
    "random": 0.95,
}


def _normalize_thought(val: Any) -> str | None:
    """Normalizes the 'thought' field whether the LLM returns a string, dict, or list."""
    if val is None:
        return None
    if isinstance(val, str):
        return val.strip()
    if isinstance(val, dict):
        parts = [f"[{k}] {v}" for k, v in val.items() if v is not None and str(v).strip()]
        return " | ".join(parts) if parts else None
    if isinstance(val, list):
        parts = [str(item).strip() for item in val if item is not None and str(item).strip()]
        return " | ".join(parts) if parts else None
    return str(val).strip()


def validate_and_normalize_response(parsed: dict, action_name: str | None = None) -> dict:
    """Validates and normalizes a parsed LLM JSON response against the expected schema for `action_name`.

    Raises:
        ValueError: If the JSON structure does not match the required schema for `action_name`.
    """
    if not isinstance(parsed, dict):
        raise ValueError("Top-level JSON value must be an object/dictionary.")

    if "thought" in parsed:
        parsed["thought"] = _normalize_thought(parsed.get("thought"))

    if not action_name or action_name not in ACTION_SCHEMAS:
        return parsed

    schema = ACTION_SCHEMAS[action_name]
    expected_keys: tuple[str, ...] = schema["keys"]
    schema_type: str = schema["type"]
    example: str = schema["example"]

    if schema_type == "top_level_str":
        key = expected_keys[0]
        val = parsed.get(key)
        if val is None and isinstance(parsed.get("action"), dict):
            val = parsed["action"].get(key)
        if not isinstance(val, str) or not val.strip():
            raise ValueError(f"Missing or empty '{key}' string. Expected format: {example}")
        parsed[key] = val.strip()
        return parsed

    action = parsed.get("action")
    # Auto-normalize if the LLM placed the action key(s) at the top level instead of inside "action"
    if not isinstance(action, dict) or not any(k in action for k in expected_keys):
        if any(k in parsed for k in expected_keys):
            action = {k: parsed[k] for k in expected_keys if k in parsed}
            parsed["action"] = action

    if not isinstance(action, dict) or not action:
        raise ValueError(f"Missing or empty 'action' object for '{action_name}'. Expected format: {example}")

    if schema_type == "witch":
        if "save" not in action and "poison" not in action:
            raise ValueError(f"Witch action must contain 'save' and/or 'poison'. Expected format: {example}")
        save_val = _coerce_bool(action.get("save", False))
        if save_val is None:
            raise ValueError(f"Invalid 'save' value in witch_action (must be boolean). Expected format: {example}")
        ok, poison_val = _coerce_optional_target(action.get("poison"))
        if not ok:
            raise ValueError(f"Invalid 'poison' value in witch_action (must be player name or null). Expected format: {example}")
        action["save"] = save_val
        action["poison"] = poison_val
        return parsed

    key = expected_keys[0]
    if key not in action:
        raise ValueError(f"Missing required key '{key}' inside 'action'. Expected format: {example}")

    raw_val = action[key]
    if schema_type == "non_empty_str":
        if not isinstance(raw_val, str) or not raw_val.strip():
            raise ValueError(f"Field 'action.{key}' must be a non-empty string. Expected format: {example}")
        action[key] = raw_val.strip()
        if "withdraw" in action:
            w_val = _coerce_bool(action.get("withdraw"))
            action["withdraw"] = bool(w_val) if w_val is not None else False
    elif schema_type == "bool":
        coerced = _coerce_bool(raw_val)
        if coerced is None:
            raise ValueError(f"Field 'action.{key}' must be a boolean (true/false). Expected format: {example}")
        action[key] = coerced
    elif schema_type == "speech_order":
        if not isinstance(raw_val, str) or raw_val.strip() not in ("clockwise", "counter_clockwise"):
            raise ValueError(
                f"Field 'action.{key}' must be 'clockwise' or 'counter_clockwise'. Expected format: {example}"
            )
        action[key] = raw_val.strip()
    elif schema_type == "optional_target":
        ok, target_val = _coerce_optional_target(raw_val)
        if not ok:
            raise ValueError(
                f"Field 'action.{key}' must be a player name string or null. Expected format: {example}"
            )
        action[key] = target_val

    return parsed


class LLMController(Controller):
    """A sophisticated controller that uses an LLM to drive player decisions.

    This controller constructs detailed prompts based on the current game state, the
    player's role, and their personality. It sends these prompts to an LLM and parses
    the JSON response to determine the player's action. It also includes a fallback
    mechanism to a simpler controller in case of errors.
    """

    def __init__(self, personality: str = "cautious", llm_client: Any | None = None, game: Game | None = None, language: str = "zh", llm_config: dict | None = None, fallback_controller: Controller | None = None):
        """Initializes the LLM-based controller.

        Args:
            personality: The personality trait for the AI (e.g., 'cautious',
                'aggressive'). This determines which characteristic prompt to use.
            llm_client: An optional, pre-configured LLM client. If not provided, a
                new one is created based on `llm_config` or a `MockLLMClient` is used.
            game: The main `Game` object, which provides context.
            language: The language for the prompts ('en' or 'zh').
            llm_config: A dictionary with LLM provider details (provider, model,
                api_key, base_url).
            fallback_controller: A simpler controller (like `SafeController`) to use
                if the LLM fails.
        """
        if llm_config:
            # Create a new client specific to this controller if config is provided
            self.llm_client = LLMClient(
                provider=llm_config.get("provider"),
                model=llm_config.get("model"),
                api_key=llm_config.get("api_key"),
                base_url=llm_config.get("base_url")
            )
        else:
            self.llm_client = llm_client or MockLLMClient()
            
        if game:
            self.game = game
        self.personality = personality
        self.temperature = PERSONALITY_TEMPERATURES.get(personality, 0.75)
        self.language = language
        self.last_witch_decision: dict | None = None
        self.prompt_dir = os.path.join(os.path.dirname(__file__), "prompts")
        self.fallback_controller = fallback_controller or SafeController()
        if game:
            self.fallback_controller.game = game

    def _get_effective_language(self) -> str:
        """Returns the current active language, syncing with self.game.language if set."""
        if getattr(self, "game", None) and getattr(self.game, "language", None):
            self.language = self.game.language
        return self.language

    def _load_prompt(self, prompt_type: str, name: str) -> str:
        """Loads a specific prompt template from the filesystem.

        Prompts are organized by language, type (action, characteristic, etc.), and name.
        If a prompt is not found in the specified language, it falls back to English.

        Args:
            prompt_type: The category of the prompt (e.g., 'action', 'status').
            name: The name of the prompt file (without the .txt extension).

        Returns:
            The content of the prompt template as a string.
        """
        lang = self._get_effective_language()
        # Construct path: prompts/{language}/{prompt_type}/{name}.txt
        path_parts = [self.prompt_dir, lang]
        if prompt_type:
            path_parts.append(prompt_type)
        path_parts.append(f"{name}.txt")
        
        file_path = os.path.join(*path_parts)
        
        try:
            with open(file_path, "r", encoding='utf-8') as f:
                return f.read()
        except FileNotFoundError:
            # Fallback to English if the prompt is not available in the selected language.
            if lang != "en":
                print(f"Warning: Prompt not found for language '{lang}', falling back to 'en': {file_path}")
                path_parts[1] = "en"
                file_path = os.path.join(*path_parts)
                with open(file_path, "r", encoding='utf-8') as f:
                    return f.read()
            raise

    def _find_player_by_name(self, name: str | None, potential_targets: list[Player] | None = None) -> Player | None:
        """Utility function to find a Player object from their name, optionally restricted to valid targets.

        Args:
            name: The name of the player to find (supports 'Player N', 'N号玩家', 'N号', 'PN').
            potential_targets: Optional list of valid target players to restrict the lookup.

        Returns:
            The `Player` object if found and valid, otherwise None.
        """
        if not name or not isinstance(name, str):
            return None
        candidates = potential_targets if potential_targets is not None else (self.game.players if getattr(self, "game", None) else [])
        clean = name.strip()
        for p in candidates:
            if p.name == clean:
                return p
        # Also match seat numbers like "3号玩家", "3号", "P3", "Player 3" -> "Player 3"
        m = re.match(r"^(?:player\s*|p\s*)?(\d{1,2})\s*(?:号(?:玩家)?)?$", clean, re.IGNORECASE)
        if m:
            seat_name = f"Player {int(m.group(1))}"
            for p in candidates:
                if p.name == seat_name:
                    return p
        return None

    def _get_llm_response(self, prompt: str, action_name: str | None = None) -> dict:
        """Retrieves, parses, and validates a JSON response from the LLM.

        This method includes a retry mechanism to handle cases where the LLM returns
        malformed JSON or a JSON object missing required action keys. If parsing or
        schema validation fails, it sends corrective feedback on subsequent attempts.
        If all attempts fail, it returns a default error dictionary.

        Args:
            prompt: The prompt to send to the LLM.
            action_name: Optional action identifier to validate the response schema against.

        Returns:
            A dictionary parsed and normalized from the LLM's JSON response.
        """
        max_retries = 3
        current_prompt = prompt
        last_error = ""
        lang = self._get_effective_language()

        for attempt in range(max_retries):
            if hasattr(self.llm_client, "temperature"):
                self.llm_client.temperature = self.temperature
            response_str = self.llm_client.get_completion(current_prompt)
            try:
                parsed = extract_json(response_str)
                return validate_and_normalize_response(parsed, action_name=action_name)
            except (json.JSONDecodeError, ValueError) as e:
                last_error = str(e)
                print(f"Attempt {attempt + 1}/{max_retries} failed: LLM returned invalid JSON/schema: {last_error} | raw={response_str}")
                if attempt == max_retries - 1:
                    return {"thought": "Invalid JSON response from LLM after retries.", "action": {}}

                # Construct corrective feedback for the next retry attempt
                snippet = response_str[:200] if response_str else ""
                schema_hint = ""
                if action_name and action_name in ACTION_SCHEMAS:
                    schema_hint = f" Required format: {ACTION_SCHEMAS[action_name]['example']}."
                if lang == "en":
                    feedback = (
                        f"\n\n[Correction Notice: Your previous output was not valid JSON or did not match the required schema ({last_error})."
                        f"{schema_hint} "
                        f"Previous raw output: {snippet!r}. "
                        "Please return strictly valid JSON matching the required format, without markdown fences or extraneous text.]"
                    )
                else:
                    zh_hint = (
                        f" 期望的 JSON 格式示例：{ACTION_SCHEMAS[action_name]['example']}。"
                        if (action_name and action_name in ACTION_SCHEMAS)
                        else ""
                    )
                    feedback = (
                        f"\n\n[修正提示：您上一次的输出不是合法的 JSON 格式或缺少必需字段（错误：{last_error}）。"
                        f"{zh_hint}"
                        f"原输出片段：{snippet!r}。"
                        "请严格仅返回符合格式要求的有效 JSON 对象，不要添加 markdown 代码块标记或无关的文字。]"
                    )
                current_prompt = prompt + feedback

        return {"thought": "Failed to get valid response.", "action": {}}

    def _build_vote_ledger(self, is_zh: bool) -> str:
        """Formats historical votes into a compact ledger for Vote-Pattern Analysis (看票型)."""
        vote_history = getattr(self.game, "vote_history", None) if getattr(self, "game", None) else None
        if not vote_history:
            return ""
        lines: list[str] = []
        for record in vote_history:
            phase = record.get("phase", "")
            votes = record.get("votes", {})
            result = record.get("result", "")
            if is_zh:
                pairs = "，".join([f"{voter}->{target or '弃票'}" for voter, target in votes.items()])
                lines.append(f"  * [{phase}] {pairs}（结果：{result}）")
            else:
                pairs = ", ".join([f"{voter}->{target or 'Abstain'}" for voter, target in votes.items()])
                lines.append(f"  * [{phase}] {pairs} (Result: {result})")
        header = "\n历史票型记录（用于看票型盘逻辑）：\n" if is_zh else "\nHistorical Vote Ledger (for vote-pattern deduction):\n"
        return header + "\n".join(lines)

    def _build_personal_tactical_lens(self, player: Player, is_zh: bool) -> str:
        """Assigns each player seat a distinct analytical entry point and role-specific trick focus
        so players sharing the same LLM model never produce identical thoughts."""
        players = getattr(self.game, "players", []) if getattr(self, "game", None) else []
        seat_idx = players.index(player) if player in players else 0

        if isinstance(player.role, Werewolf):
            all_wolves = [p for p in players if isinstance(p.role, Werewolf)]
            wolf_idx = all_wolves.index(player) if player in all_wolves else 0
            if is_zh:
                wolf_styles = [
                    "【你的本局狼人战术定位：悍跳主攻位】你倾向于主动争夺话语权（如第1天上警悍跳预言家，给好人发“金水”拉拢或给硬骨头发“查杀”施压；若队友已悍跳，则强势带节奏主推好人）。",
                    "【你的本局狼人战术定位：深水倒钩位】你倾向于伪装成理性客观的闭眼好人（如留在警下投票、站边真预言家拿好人信任，必要时甚至果断“卖队友/倒钩”踩一脚暴露的狼队友以坐实自己的好人身份，留到决赛圈抗推好人）。",
                    "【你的本局狼人战术定位：煽动冲锋/抿神位】你倾向于在发言中抓好人的口误与票型漏洞，替悍跳狼队友打掩护（冲锋），或暗中观察谁像女巫/守卫/猎人（抿神）以便夜晚精准刀神屠边；若被集火可适当“穿神职衣服”挡推。",
                ]
                return wolf_styles[wolf_idx % len(wolf_styles)]
            else:
                wolf_styles_en = [
                    "[Your Personal Werewolf Playstyle: Aggro Fake-Seer / Pace-Setter] You prefer seizing the initiative (e.g., running for Sheriff to fake-claim Seer with a strategic Gold Water or Wolf Check; or if a teammate already jumped Seer, aggressively driving the daytime mislynch).",
                    "[Your Personal Werewolf Playstyle: Deep-Cover Busser (倒钩)] You prefer disguising as an objective Villager (staying off the Sheriff ballot to cast a key vote, siding with the real Seer to earn trust, and even 'bussing' an exposed wolf teammate to survive into the endgame).",
                    "[Your Personal Werewolf Playstyle: Flanker & God-Hunter (冲锋/抿神)] You focus on exploiting flaws in good players' speeches to support your fake-Seer teammate, reading subtle cues to identify hidden Gods (Witch/Guard/Hunter) for night kills, and fake-claiming a God role if pushed on the block.",
                ]
                return wolf_styles_en[wolf_idx % len(wolf_styles_en)]

        if is_zh:
            good_lenses = [
                "【你的专属盘逻辑视角：票型与抱团审计】思考时优先对照《历史票型记录》，重点抓谁在警长竞选和放逐投票中暗中保人、分票或跟风冲票。",
                "【你的专属盘逻辑视角：发言矛盾与视角审计】思考时重点抓谁的发言前后矛盾、谁存在“开天眼”（知道了好人不该知道的信息）、谁在空洞划水和稀泥。",
                "【你的专属盘逻辑视角：真假预言家对跳与警徽流审计】思考时重点对比起跳预言家的查验心路历程、警徽流合理性，分辨谁是真预言家、谁是悍跳狼、谁是倒钩狼。",
                "【你的专属盘逻辑视角：屠边局神民掩护与反套路审计】思考时重点评估当前狼人是试图“屠神”还是“屠民”，警惕狼人“自刀骗解药（骗银水）”或“穿神职衣服逃脱放逐”。",
            ]
            return good_lenses[seat_idx % len(good_lenses)]
        else:
            good_lenses_en = [
                "[Your Personal Analytical Lens: Vote-Matrix & Alignment Auditor] Prioritize cross-checking the Historical Vote Ledger to catch who is protecting suspects, splitting votes, or bandwagoning.",
                "[Your Personal Analytical Lens: Contradiction & Perspective Detector] Focus on catching players whose speeches contradict earlier claims, who slip up with insider wolf knowledge, or who hide behind vague filler.",
                "[Your Personal Analytical Lens: Seer Counter-Claim & Badge-Flow Critic] Scrutinize competing Seer claims, the logic behind their check targets, and their badge flow plans to separate real Seer, fake Seer, and bussing wolves.",
                "[Your Personal Analytical Lens: Slaughter-the-Side & Bluff Counter] Evaluate whether wolves are hunting Gods or Villagers, and stay alert for wolf tricks like Night 1 self-knifing to bait Witch's save or fake-claiming God roles on the block.",
            ]
            return good_lenses_en[seat_idx % len(good_lenses_en)]

    def _build_status_prompt(self, player: Player) -> str:
        """Constructs the comprehensive status section of the main prompt.

        This method gathers all relevant information for the LLM to make an informed
        decision, including the player's role, game state, visible logs, and memory.

        Args:
            player: The player for whom the prompt is being built.

        Returns:
            A formatted string containing the full status and history for the player.
        """
        from game.utils import STATE_TRANSLATIONS

        lang = self._get_effective_language()
        is_zh = lang == "zh"

        if is_zh:
            sheriff_status = "你是警长。" if player.is_sheriff else ""
            player_status = "，".join([f"{p.name} ({'存活' if p.is_alive else '死亡'})" for p in self.game.players])
            visible_log = "目前还没有发生任何事情。"
        else:
            sheriff_status = "You are the Sheriff." if player.is_sheriff else ""
            player_status = ", ".join([f"{p.name} ({'alive' if p.is_alive else 'dead'})" for p in self.game.players])
            visible_log = "Nothing has happened yet."

        if player.logs:
            # Keep the player's OWN prior THOUGHT entries so they maintain strategic continuity across phases,
            # while excluding UI thinking indicators and any other player's thoughts.
            filtered_entries = [
                entry for entry in player.logs
                if entry.log_type not in (LogType.PLAYER_THINKING, LogType.PLAYER_DONE_THINKING)
                and (entry.log_type != LogType.THOUGHT or entry.source == player)
            ]
            if filtered_entries:
                visible_log = "\n".join([f"- {log_entry.get_text(lang)}" for log_entry in filtered_entries])

        vote_ledger = self._build_vote_ledger(is_zh)
        long_term_memory = ""
        if player.long_term_memory:
            long_term_memory = f"\n长期记忆：\n{player.long_term_memory}" if is_zh else f"\nLong Term Memory:\n{player.long_term_memory}"

        personal_lens = self._build_personal_tactical_lens(player, is_zh)

        # Role-specific information is added to give the LLM crucial context.
        if is_zh:
            role_info = (
                "- 你是普通村民，没有夜间特殊技能。\n"
                "- 进阶套路提示：通过听发言逻辑与【看票型】找出悍跳狼、冲锋狼与深水倒钩狼；在屠边局中注意替真神职打掩护（必要时可适当模糊身份替神职挡刀，但若被真神职质疑需及时退水表水）。\n"
                f"- {personal_lens}"
            )
            if isinstance(player.role, Witch):
                role_info = (f"- 你是女巫。你还有{'一瓶解药' if player.role.has_save else '0瓶解药（已用完）'}。\n"
                             f"- 你还有{'一瓶毒药' if player.role.has_poison else '0瓶毒药（已用完）'}。\n"
                             "- 进阶套路提示：屠边局中神职全部出局则狼人直接获胜。前期请隐藏女巫身份；警惕狼人第1夜【自刀骗药】（骗取银水身份混入好人阵营），但第1夜救人通常能保住关键轮次并防止好人阵营崩盘；毒药留给铁狼或悍跳狼，带队归票时可报出银水信息。\n"
                             f"- {personal_lens}")
                if player.role.has_save and self.game.state.__class__.__name__ == "WitchNightState" and self.game.night_kill_target:
                    role_info += f"\n- 今晚狼人袭击的目标是：{self.game.night_kill_target.name}。"
            elif isinstance(player.role, Werewolf):
                all_wolves = [p for p in self.game.players if isinstance(p.role, Werewolf)]
                king_player = next((p for p in all_wolves if isinstance(p.role, BlackWerewolfKing)), None)
                pack_desc = [
                    f"{p.name} ({'黑狼王' if isinstance(p.role, BlackWerewolfKing) else '普通狼人'}, {'存活' if p.is_alive else '已出局'})"
                    for p in all_wolves
                ]
                king_info = (
                    f"本局黑狼王是：{king_player.name}（{'就是你本人' if king_player == player else '你的狼队友'}，非毒死出局时可开枪带人）。"
                    if king_player
                    else "本局没有黑狼王。"
                )
                role_info = (f"- 狼人阵营全员名单：{', '.join(pack_desc)}。\n"
                             f"- {king_info}\n"
                             "- 狼人高阶战术套路：本局为屠边规则（杀光所有神职或杀光所有普通村民即可获胜）。请灵活运用狼人套路：\n"
                             "  1)【悍跳预言家】：派1名狼人上警起跳预言家争夺警徽，可发好人“金水”拉票，或发“查杀”施压；\n"
                             "  2)【倒钩与冲锋】：切勿全员抱团！至少安排队友打“倒钩”（站边真预言家、必要时踩悍跳狼队友一脚以做高自己身份）和“冲锋”（配合悍跳狼归票抗推好人）；\n"
                             "  3)【自刀骗药与抿神】：第1夜可考虑自刀骗女巫解药拿“银水”做高身份（注意风险），被推上PK台时可【穿神职衣服】（假跳猎人/守卫/女巫）自保或诈出真神职。\n"
                             f"- {personal_lens}")
            elif isinstance(player.role, Seer):
                role_info = ("- 你是预言家。你每晚可以查验一名玩家的身份。\n"
                             "- 进阶套路提示：作为好人核心信息位，第1天务必上警竞选警长，清晰报出昨晚【查验结果（金水/查杀）】、查验心路历程，并安排好【警徽流】（预告今晚及明晚准备查验谁，以便若夜里被刀无遗言时通过移交或撕毁警徽传递查验结果）。面对悍跳狼时重点点破其逻辑漏洞与警下票型。\n"
                             f"- {personal_lens}")
            elif isinstance(player.role, Guard):
                role_info = ("- 你是守卫。你每晚可以守护一名玩家。\n"
                             "- 进阶套路提示：前期务必深藏身份扮作普通村民，避免被狼人抿出身份刀死；第1夜女巫大概率使用解药，建议【空守或自守】以防与女巫“同守同救（奶穿）”救死好人；中后期优先守护已跳明的真预言家或女巫，打出平安夜。\n"
                             f"- {personal_lens}")
                if player.role.last_protected:
                    role_info += f"\n- 昨晚你守护了 {player.role.last_protected.name}，今晚不能连续守护同一个人。"
            elif isinstance(player.role, Hunter):
                role_info = ("- 你是猎人。如果你出局（被女巫毒死除外），你可以开枪带走一名玩家。\n"
                             "- 进阶套路提示：前期深藏身份避免被狼人针对或被女巫盲毒（被毒无法开枪）；若有狼人假跳猎人【穿你衣服】，或你被当成抗推位时，果断拍出猎人身份震慑全场。\n"
                             f"- {personal_lens}")
        else:
            role_info = (
                "- You are a plain Villager with no night ability.\n"
                "- Advanced Tactics: Use speech logic and the Historical Vote Ledger to spot Fake-Seer wolves (悍跳), Flanker wolves (冲锋), and Deep-Cover Bussers (倒钩). Under Slaughter-the-Side rules, help shield God roles and never give wolves a free mislynch.\n"
                f"- {personal_lens}"
            )
            if isinstance(player.role, Witch):
                role_info = (f"- You have {'a save potion' if player.role.has_save else 'no save potion'} left.\n"
                             f"- You have {'a poison potion' if player.role.has_poison else 'no poison potion'} left.\n"
                             "- Advanced Tactics: Under Slaughter-the-Side rules, Werewolves win if all God roles die; stay hidden early. Beware of Night 1 Werewolf self-knife (自刀骗药) to earn 'Silver Water' trust, though saving on Night 1 usually preserves crucial tempo. Save your poison for confirmed wolves or fake-Seers.\n"
                             f"- {personal_lens}")
                if player.role.has_save and self.game.state.__class__.__name__ == "WitchNightState" and self.game.night_kill_target:
                     role_info += f"\n- Tonight, the werewolves targeted: {self.game.night_kill_target.name}."
            elif isinstance(player.role, Werewolf):
                all_wolves = [p for p in self.game.players if isinstance(p.role, Werewolf)]
                king_player = next((p for p in all_wolves if isinstance(p.role, BlackWerewolfKing)), None)
                pack_desc = [
                    f"{p.name} ({'Black Werewolf King' if isinstance(p.role, BlackWerewolfKing) else 'Werewolf'}, {'alive' if p.is_alive else 'dead'})"
                    for p in all_wolves
                ]
                king_info = (
                    f"The Black Werewolf King is {king_player.name} ({'YOU' if king_player == player else 'your teammate'}, can shoot a player upon dying unless poisoned)."
                    if king_player
                    else "There is no Black Werewolf King in this game."
                )
                role_info = (f"- Werewolf Pack Roster: {', '.join(pack_desc)}.\n"
                             f"- {king_info}\n"
                             "- Advanced Werewolf Playbook: Under Slaughter-the-Side rules, eliminate all Gods OR all Villagers. Use meta-game tricks:\n"
                             "  1) [Fake-Claim Seer (悍跳)]: Send 1 wolf to run for Sheriff and claim Seer, giving a 'Gold Water' (good check) to buy trust or a 'Wolf Check' (查杀) to pressure a target;\n"
                             "  2) [Deep-Cover Bussing (倒钩) & Aggro Support (冲锋)]: Never vote as a monolith! Have one teammate bus/criticize the fake-Seer to look like a pure villager while another pushes the mislynch;\n"
                             "  3) [Self-Knife (自刀骗药) & Fake God Claims (穿衣服)]: Consider Night 1 self-knife to bait Witch's save, or claim Hunter/Guard when on the execution block to survive.\n"
                             f"- {personal_lens}")
            elif isinstance(player.role, Seer):
                role_info = ("- You are the Seer. You can check one player's identity each night.\n"
                             "- Advanced Tactics: Run for Sheriff on Day 1, clearly state your Night 1 check result (Gold Water / Wolf Check), explain why you checked that seat, and set a [Sheriff Badge Flow (警徽流)] (announcing who you will check tonight so passing/destroying the badge at dawn reveals the result even without Last Words).\n"
                             f"- {personal_lens}")
            elif isinstance(player.role, Guard):
                role_info = ("- You are the Guard. You can protect one player each night.\n"
                             "- Advanced Tactics: Stay hidden early as a plain villager; on Night 1, consider guarding nobody or yourself to avoid the deadly Guard+Witch save conflict (同守同救奶穿) on the Night 1 victim. Later, protect confirmed Seer/Witch to create peaceful nights.\n"
                             f"- {personal_lens}")
                if player.role.last_protected:
                    role_info += f"\n- Last night you protected {player.role.last_protected.name}. You cannot protect them again tonight."
            elif isinstance(player.role, Hunter):
                role_info = ("- You are the Hunter. If you die (except by poison), you can shoot someone.\n"
                             "- Advanced Tactics: Hide your God identity early to avoid wolf God-hunting or accidental Witch poison; if a werewolf fake-claims Hunter (stealing your role) or the village tries to execute you, reveal boldly.\n"
                             f"- {personal_lens}")

        role_display_name = (
            getattr(player.role, "name_zh", player.role.name)
            if (is_zh and player.role)
            else (player.role.name if player.role else "Unknown")
        )
        state_cls_name = self.game.state.__class__.__name__ if getattr(self.game, "state", None) else "None"
        phase_display_name = STATE_TRANSLATIONS.get(state_cls_name, state_cls_name) if is_zh else state_cls_name

        status_prompt_template = self._load_prompt("status", "status")
        return status_prompt_template.format(
            player=player,
            role_name=role_display_name,
            phase_name=phase_display_name,
            sheriff_status=sheriff_status,
            game=self.game,
            player_status=player_status,
            role_info=role_info,
            visible_log=visible_log + vote_ledger + long_term_memory
        )

    def _get_thinking_visibility(self, player: Player) -> dict[str, Any]:
        """Determines who can see PLAYER_THINKING / PLAYER_DONE_THINKING logs so night actions never leak."""
        state_cls_name = (
            self.game.state.__class__.__name__
            if (getattr(self, "game", None) and getattr(self.game, "state", None))
            else ""
        )
        if state_cls_name == "WerewolfNightState":
            return {
                "visible_to_roles": ["Werewolf", "Black Werewolf King"],
                "camps": ["Werewolves"],
            }
        if state_cls_name in ("GuardNightState", "WitchNightState", "SeerNightState", "NightBeginState", "NightEndState"):
            return {
                "visible_to_players": [player],
                "camps": [],
            }
        return {"camps": ["All"]}

    def _get_decision(self, player: Player, action_name: str, format_kwargs: dict) -> dict:
        """Orchestrates the process of getting a decision from the LLM.

        This core method assembles the final prompt from multiple templates (base rules,
        personality, status, and the specific action). It then calls the LLM, parses
        the response, logs the AI's "thought" process, and returns the final action.

        Args:
            player: The player making the decision.
            action_name: The name of the action being performed (e.g., 'speech', 'vote').
            format_kwargs: A dictionary of values to format into the action prompt.

        Returns:
            A dictionary representing the action to be taken, parsed from the LLM response.
        """
        thinking_vis = self._get_thinking_visibility(player)
        if self.game:
            self.game.log(LogEntry(
                log_type=LogType.PLAYER_THINKING,
                message={"en": f"{player.name} is thinking...", "zh": f"{player.name} 正在思考..."},
                source=player,
                **thinking_vis,
            ))

        try:
            try:
                lang = self._get_effective_language()
                base_rules = self._load_prompt("", "base_rules")
                characteristic_prompt = self._load_prompt("characteristic", self.personality)
                status_prompt = self._build_status_prompt(player)
                action_prompt_template = self._load_prompt("action", action_name)
                action_prompt = action_prompt_template.format(**format_kwargs)

                if lang == "zh":
                    prompt = f"{base_rules}\n\n{characteristic_prompt}\n\n--- 当前状态 ---\n{status_prompt}\n\n--- 需要执行的行动 ---\n{action_prompt}"
                else:
                    prompt = f"{base_rules}\n\n{characteristic_prompt}\n\n--- CURRENT STATUS ---\n{status_prompt}\n\n--- ACTION REQUIRED ---\n{action_prompt}"

                response = self._get_llm_response(prompt, action_name=action_name)
                thought = response.get('thought')
                print(f"LLM ({player.name}) thought: {thought}")

                # Log the thought process for debugging and transparency.
                if thought and self.game:
                    self.game.log(LogEntry(
                        log_type=LogType.THOUGHT,
                        message={"en": f"({player.name} thought): {thought}", "zh": f"({player.name} 思考): {thought}"},
                        source=player,
                        visible_to_players=[player]
                    ))

                action = response.get("action", {})
                if not action:
                    raise ValueError("Empty action received from LLM")
                return action

            except Exception as e:
                print(f"All attempts failed for {player.name}: {e}. Falling back to SafeController.")
                return self._get_fallback_decision(player, action_name, format_kwargs)
        finally:
            if self.game:
                self.game.log(LogEntry(
                    log_type=LogType.PLAYER_DONE_THINKING,
                    message={"en": f"{player.name} finished thinking.", "zh": f"{player.name} 思考完毕。"},
                    source=player,
                    **thinking_vis,
                ))

    def _get_fallback_decision(self, player: Player, action_name: str, format_kwargs: dict) -> dict:
        """Generates a safe, default action when the LLM fails.

        This method is called after repeated failures to get a valid response from the
        LLM. It uses the `fallback_controller` (typically a `SafeController`) to generate
        a passive, non-disruptive action, ensuring the game can continue without errors.

        Args:
            player: The player for whom the decision is being made.
            action_name: The name of the action requiring a fallback.
            format_kwargs: The original arguments for the action prompt.

        Returns:
            A dictionary containing a safe, default action.
        """
        if not self.fallback_controller:
            return {}

        # This maps the LLM action name to the corresponding method on the fallback controller.
        # It returns a dictionary in the format expected by the calling `get_*` method.
        if action_name == "speech":
            return {"speech": self.fallback_controller.get_speech(player)}
        elif action_name == "vote":
            return {"vote": None} # SafeController.get_vote returns None
        elif action_name == "werewolf_kill":
            return {"kill": None}
        elif action_name == "witch_action":
             return {"save": False, "poison": None}
        elif action_name == "vote_for_sheriff":
            return {"vote_for_sheriff": None}
        elif action_name == "run_for_sheriff":
            return {"run_for_sheriff": False}
        elif action_name == "withdraw_sheriff":
            return {"withdraw_sheriff": False}
        elif action_name == "seer_action":
            return {"check": None}
        elif action_name == "guard_protect":
            return {"protect": None}
        elif action_name == "hunter_shoot":
            return {"shoot": None}
        elif action_name == "decide_speech_order":
            return {"speech_order": "clockwise"}
        elif action_name == "sheriff_death":
            return {"pass_badge": "destroy_badge"}
            
        return {}

    def _build_speech_context(self, player: Player) -> str:
        """Builds phase-specific tactical guidance for the player's speech."""
        lang = self._get_effective_language()
        is_zh = lang == "zh"
        state_cls_name = self.game.state.__class__.__name__ if (getattr(self, "game", None) and getattr(self.game, "state", None)) else ""
        day_num = getattr(self.game, "day", 1) if getattr(self, "game", None) else 1

        if state_cls_name == "WerewolfNightState":
            if is_zh:
                night1_extra = (
                    "今晚是第 1 夜，请重点分工：1) 谁在天亮后上警【悍跳预言家】（发谁“金水”拉票，或发谁“查杀”施压，留什么警徽流）；"
                    "2) 谁留在警下投出关键警长票或打【倒钩】（站边真预言家做高身份）；"
                    "3) 今晚是正常刀外置位好人，还是由悍跳狼/黑狼王【自刀骗解药】拿女巫银水；"
                    if day_num == 1
                    else "请结合白天各玩家的发言与历史票型，【抿神】判断谁是预言家、女巫、守卫或猎人，评估屠神与屠民哪条路线更快，商量今晚刀谁以及明天谁主推带节奏；"
                )
                return (
                    f"【当前场景：狼人夜间秘密频道（仅狼人队友可见，好人听不到）】"
                    f"请直接对你的狼队友说话：{night1_extra}"
                    f"明确提出你建议今晚袭击的目标座位号与白天战术安排（控制在 2-4 句话）。"
                )
            else:
                night1_extra = (
                    "Since this is Night 1, assign roles: 1) Who runs for Sheriff to [Fake-Claim Seer (悍跳)] (giving a Gold Water or Wolf Check); "
                    "2) Who stays off the ballot to vote for Sheriff or plays [Deep-Cover Busser (倒钩)]; "
                    "3) Whether to knife an outside player or attempt a [Night 1 Self-Knife (自刀骗药)] to bait the Witch's save. "
                    if day_num == 1
                    else "Based on daytime speeches and the Vote Ledger, deduce who the remaining Gods (Seer/Witch/Guard/Hunter) or Villagers are, decide whether God-wipe or Villager-wipe is faster, and agree on tonight's kill target. "
                )
                return (
                    f"[Context: Private Werewolf Night Channel (visible ONLY to werewolf teammates)] "
                    f"Speak directly to your werewolf pack: {night1_extra}"
                    f"State clearly who you suggest killing tonight and your daytime tactical plan (keep it to 2-4 sentences)."
                )

        if state_cls_name == "SheriffSpeechState":
            if is_zh:
                return (
                    "【当前场景：警长竞选演说】你正在竞选警长（拥有 1.5 票投票权并决定发言顺序）。"
                    "请向全场发表你的竞选演说：如果你是真预言家，请直接报出昨晚的查验结果（金水/查杀）、查验心路历程并留好【警徽流】（今晚及明晚查谁），绝不退水；"
                    "如果你是悍跳狼人，请逼真地伪装预言家报出编造的查验结果（金水拉拢好人或查杀施压）与警徽流，争夺警徽；"
                    "如果你是上警表水/诈身份的好人，或者决定让路给真预言家/狼队友的候选人，请说明上警理由与站边判断，并可在发言末尾宣布“我退水”（或在 JSON 的 action 中附上 `\"withdraw\": true`）（控制在 2-4 句话）。"
                )
            else:
                return (
                    "[Context: Sheriff Election Campaign Speech] You are campaigning for Sheriff (1.5x vote weight and speech order control). "
                    "If you are the real Seer, reveal your Night 1 check result (Gold Water / Wolf Check), your reasoning, and your [Badge Flow (警徽流)] plan, and never withdraw; "
                    "if you are a Werewolf fake-claiming Seer, deliver a convincing fabricated check result and badge plan to win the badge; "
                    "if you are a good player who only ran to share reads or wish to step down for the real Seer, explain your stance and state 'I withdraw' (or include `\"withdraw\": true` inside `action`) (keep it to 2-4 sentences)."
                )

        if state_cls_name == "TieSpeechState":
            if is_zh:
                return (
                    "【当前场景：平票 PK 辩护发言】你目前处于平票 PK 环节。"
                    "请犀利指出平票对手发言与票型中的逻辑漏洞，坚定表水为自己辩护（若你是神职或急需自保的狼人，可考虑亮身份/穿神职衣服施压），并号召其他玩家把票投给对手（控制在 2-4 句话）。"
                )
            else:
                return (
                    "[Context: Tie-Breaker PK Speech] You are in a tie-breaker runoff. "
                    "Attack the contradictions and voting record of your tied opponent, defend your stance (claiming or bluffing a key role if necessary to survive), and rally voters to eliminate your opponent (keep it to 2-4 sentences)."
                )

        if state_cls_name == "LastWordsState":
            if is_zh:
                return (
                    "【当前场景：出局遗言】你已经出局，正在发表最后的遗言。"
                    "注意你已无法继续参与后续投票，切勿说“看大家一会儿怎么投我”之类的话；"
                    "如果你是好人或神职，请交代清楚你的真实底牌、技能使用记录（如银水/刀口/守护记录）以及你通过票型锁定的狼人座位号；"
                    "如果你是狼人，请在遗言中继续伪装好人或假神职（如假装被冤死的预言家/守卫/女巫），误导好人视线并掩护存活的狼队友（控制在 2-4 句话）。"
                )
            else:
                return (
                    "[Context: Last Words (Eliminated)] You have been eliminated and are giving your final Last Words. "
                    "Do NOT speak as if you are still alive to vote; if you are on the Villager side, clearly reveal your true role, ability history, and wolf suspects; "
                    "if you are a Werewolf, keep bluffing as a wronged villager or God role to mislead the village and protect your surviving pack (keep it to 2-4 sentences)."
                )

        if is_zh:
            return (
                "【当前场景：白天公开发言】请结合昨晚死讯、真假预言家对跳（金水/查杀/警徽流）、《历史票型记录》与之前发言进行深度推理："
                "点出具体的玩家座位号（如“X号”），明确说明你站边哪位预言家、怀疑谁在冲锋或倒钩（如果你是狼人，请按你的定位执行悍跳带队、倒钩卖队友或冲锋抗推好人），并明确表态你今天准备归票/投票给谁（控制在 2-4 句话，拒绝复读和空话）。"
            )
        else:
            return (
                "[Context: Daytime Public Speech] Analyze last night's casualties, competing Seer claims (Gold Water/Wolf Check/Badge Flow), and the Historical Vote Ledger: "
                "reference specific seat numbers (e.g., 'Player X'), state which Seer claim you back, call out suspected flankers or bussers (or execute your werewolf bluff/bus strategy if you are a wolf), and state clearly who you intend to vote for today (keep it to 2-4 sentences, no generic filler)."
            )

    def get_speech(self, player: Player) -> str:
        speech_context = self._build_speech_context(player)
        action = self._get_decision(player, "speech", {"speech_context": speech_context})
        speech_text = action.get("speech", "...")
        state_cls_name = self.game.state.__class__.__name__ if (getattr(self, "game", None) and getattr(self.game, "state", None)) else ""
        if state_cls_name == "SheriffSpeechState" and not isinstance(player.role, Seer):
            explicit_withdraw = bool(action.get("withdraw", False))
            if not explicit_withdraw and isinstance(speech_text, str):
                has_negation = bool(re.search(r"(不退水|不会退水|绝不退水|don'?t\s+withdraw|not\s+withdraw|never\s+withdraw)", speech_text, re.IGNORECASE))
                has_withdraw_phrase = bool(re.search(r"(我选择退水|我宣布退水|我退水|在此退水|表完水退水|退水了|i\s+withdraw(?:\s+from\s+the\s+sheriff)?)", speech_text, re.IGNORECASE))
                if has_withdraw_phrase and not has_negation:
                    explicit_withdraw = True
            if explicit_withdraw:
                setattr(player, "withdrew_in_speech", True)
        return speech_text

    def get_vote(self, player: Player, potential_targets: list[Player]) -> Player | None:
        targets_str = ", ".join([p.name for p in potential_targets])
        action = self._get_decision(player, "vote", {"potential_targets": targets_str})
        target_name = action.get("vote")
        return self._find_player_by_name(target_name, potential_targets)

    def get_werewolf_target(self, player: Player, potential_targets: list[Player]) -> Player | None:
        targets_str = ", ".join([p.name for p in potential_targets])
        action = self._get_decision(player, "werewolf_kill", {"potential_targets": targets_str})
        target_name = action.get("kill")
        return self._find_player_by_name(target_name, potential_targets)

    def get_witch_save_decision(self, player: Player, target: Player) -> bool:
        poison_targets_str = ", ".join([p.name for p in self.game.players if p.is_alive])
        self.last_witch_decision = self._get_decision(player, "witch_action", {
            "werewolf_target": target.name if target else "None",
            "poison_targets": poison_targets_str
        })
        return bool(self.last_witch_decision.get("save", False))

    def get_witch_poison_target(self, player: Player, potential_targets: list[Player]) -> Player | None:
        # The Witch's action (save and poison) may have been decided in `get_witch_save_decision`,
        # or if `get_witch_save_decision` was skipped (e.g. no save potion left, or Witch was targeted,
        # or no werewolf target), we query the LLM now for the poison decision.
        decision = self.last_witch_decision
        self.last_witch_decision = None

        if decision is None:
            poison_targets_str = ", ".join([p.name for p in potential_targets])
            decision = self._get_decision(player, "witch_action", {
                "werewolf_target": "None",
                "poison_targets": poison_targets_str
            })

        if decision.get("save", False):
            return None

        target_name = decision.get("poison")
        return self._find_player_by_name(target_name, potential_targets)

    def get_vote_for_sheriff(self, player: Player, potential_targets: list[Player]) -> Player | None:
        targets_str = ", ".join([p.name for p in potential_targets])
        action = self._get_decision(player, "vote_for_sheriff", {"potential_targets": targets_str})
        target_name = action.get("vote_for_sheriff")
        return self._find_player_by_name(target_name, potential_targets)

    def get_join_election_decision(self, player: Player) -> bool:
        action = self._get_decision(player, "run_for_sheriff", {})
        return bool(action.get("run_for_sheriff", False))

    def get_seer_target(self, player: Player, potential_targets: list[Player]) -> Player | None:
        targets_str = ", ".join([p.name for p in potential_targets])
        action = self._get_decision(player, "seer_action", {"potential_targets": targets_str})
        target_name = action.get("check")
        return self._find_player_by_name(target_name, potential_targets)

    def get_guard_protect(self, player: Player, potential_targets: list[Player]) -> Player | None:
        targets_str = ", ".join([p.name for p in potential_targets])
        action = self._get_decision(player, "guard_protect", {"potential_targets": targets_str})
        target_name = action.get("protect")
        return self._find_player_by_name(target_name, potential_targets)

    def get_hunter_shoot_target(self, player: Player, potential_targets: list[Player]) -> Player | None:
        targets_str = ", ".join([p.name for p in potential_targets])
        action = self._get_decision(player, "hunter_shoot", {"potential_targets": targets_str})
        target_name = action.get("shoot")
        return self._find_player_by_name(target_name, potential_targets)

    def get_speech_order_decision(self, player: Player) -> str:
        action = self._get_decision(player, "decide_speech_order", {})
        order = action.get("speech_order", "clockwise")
        return order if order in ("clockwise", "counter_clockwise") else "clockwise"

    def get_sheriff_death_decision(self, player: Player, potential_targets: list[Player]) -> Player | None:
        targets_str = ", ".join([p.name for p in potential_targets])
        action = self._get_decision(player, "sheriff_death", {"potential_targets": targets_str})
        target_name = action.get("pass_badge")
        if target_name == "destroy_badge":
            return None
        return self._find_player_by_name(target_name, potential_targets)

    def get_sheriff_withdraw_decision(self, player: Player) -> bool:
        # Real Seer never withdraws from Sheriff election (0 token cost)
        if isinstance(player.role, Seer):
            return False
        # If this player already hard-claimed Seer during SheriffSpeechState, keep them in the race (0 token cost)
        if getattr(self, "game", None):
            my_sheriff_speeches = [
                e.get_text("zh") + " " + e.get_text("en")
                for e in self.game.game_log
                if e.log_type == LogType.SPEECH and e.source == player and e.state == "SheriffSpeechState"
            ]
            combined = " ".join(my_sheriff_speeches)
            if re.search(r"(我是预言家|我跳预言家|真预言家|昨晚查验了|i\s+am\s+the\s+(?:real\s+)?seer|i\s+checked\s+player)", combined, re.IGNORECASE):
                return False

        candidates = getattr(self.game, "election_players", []) if getattr(self, "game", None) else []
        candidates_str = ", ".join([p.name for p in candidates])
        action = self._get_decision(player, "withdraw_sheriff", {"candidates": candidates_str})
        return bool(action.get("withdraw_sheriff", False))

    def summarize_history(self, player: Player, logs_to_summarize: list[LogEntry]):
        """Uses the LLM to summarize the events of the day for a player.

        To prevent the prompt from exceeding the LLM's context window, this method
        is called at the end of each day. It takes the day's logs, combines them with
        the existing long-term memory, and asks the LLM to create a new, concise
        summary. This summary then becomes the player's new long-term memory.

        Args:
            player: The player whose history is being summarized.
            logs_to_summarize: The list of `LogEntry` objects from the current day.
        """
        lang = self._get_effective_language()
        is_zh = lang == "zh"
        visible_log = "目前还没有发生任何事情。" if is_zh else "Nothing has happened yet."
        if logs_to_summarize:
            filtered_entries = [
                entry for entry in logs_to_summarize
                if entry.log_type not in (LogType.PLAYER_THINKING, LogType.PLAYER_DONE_THINKING, LogType.THOUGHT)
            ]
            if filtered_entries:
                visible_log = "\n".join([f"- {log_entry.get_text(lang)}" for log_entry in filtered_entries])

        prompt_template = self._load_prompt("memory", "summarize_day")
        prompt = prompt_template.format(
            visible_log=visible_log,
            long_term_memory=player.long_term_memory or ("无" if is_zh else "None")
        )

        response = self._get_llm_response(prompt, action_name="summarize_day")
        summary = response.get("summary")
        
        if summary:
            player.long_term_memory = summary
            print(f"Summarized history for {player.name}.")