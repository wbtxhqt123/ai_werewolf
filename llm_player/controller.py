from __future__ import annotations
import json
import random
import re
from typing import TYPE_CHECKING, Any
import os
from openai import OpenAI

from config import LLM_MODEL, LLM_API_BASE_URL, LLM_API_KEY_ENV
from game.controllers import Controller, SafeController
from game.player import Player, Witch, Werewolf, Seer, Guard, Hunter
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
        
        self.client = OpenAI(
            base_url=self.base_url,
            api_key=self.api_key,
        )

    def get_completion(self, prompt: str) -> str:
        """Sends a prompt to the LLM and returns the generated completion.

        Args:
            prompt: The complete prompt to send to the model.

        Returns:
            The content of the LLM's response as a string. In case of an API error,
            it returns a JSON string with an error message.
        """
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {
                        "role": "user",
                        "content": prompt
                    }
                ]
            )
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
        self.language = language
        self.last_witch_decision: dict | None = None
        self.prompt_dir = os.path.join(os.path.dirname(__file__), "prompts")
        self.fallback_controller = fallback_controller or SafeController()
        if game:
            self.fallback_controller.game = game

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
        # Construct path: prompts/{language}/{prompt_type}/{name}.txt
        path_parts = [self.prompt_dir, self.language]
        if prompt_type:
            path_parts.append(prompt_type)
        path_parts.append(f"{name}.txt")
        
        file_path = os.path.join(*path_parts)
        
        try:
            with open(file_path, "r", encoding='utf-8') as f:
                return f.read()
        except FileNotFoundError:
            # Fallback to English if the prompt is not available in the selected language.
            if self.language != "en":
                print(f"Warning: Prompt not found for language '{self.language}', falling back to 'en': {file_path}")
                path_parts[1] = "en"
                file_path = os.path.join(*path_parts)
                with open(file_path, "r", encoding='utf-8') as f:
                    return f.read()
            raise

    def _find_player_by_name(self, name: str | None, potential_targets: list[Player] | None = None) -> Player | None:
        """Utility function to find a Player object from their name, optionally restricted to valid targets.

        Args:
            name: The name of the player to find.
            potential_targets: Optional list of valid target players to restrict the lookup.

        Returns:
            The `Player` object if found and valid, otherwise None.
        """
        if not name or not isinstance(name, str):
            return None
        candidates = potential_targets if potential_targets is not None else (self.game.players if getattr(self, "game", None) else [])
        for p in candidates:
            if p.name == name:
                return p
        return None

    def _get_llm_response(self, prompt: str) -> dict:
        """Retrieves and parses a JSON response from the LLM.

        This method includes a retry mechanism to handle cases where the LLM returns
        malformed JSON. If parsing fails, it sends corrective feedback on subsequent
        attempts. If parsing fails after multiple attempts, it returns a default
        error dictionary.

        Args:
            prompt: The prompt to send to the LLM.

        Returns:
            A dictionary parsed from the LLM's JSON response.
        """
        max_retries = 3
        current_prompt = prompt
        last_error = ""

        for attempt in range(max_retries):
            response_str = self.llm_client.get_completion(current_prompt)
            try:
                return extract_json(response_str)
            except (json.JSONDecodeError, ValueError) as e:
                last_error = str(e)
                print(f"Attempt {attempt + 1}/{max_retries} failed: LLM returned invalid JSON: {response_str}")
                if attempt == max_retries - 1:
                    return {"thought": "Invalid JSON response from LLM after retries.", "action": {}}

                # Construct corrective feedback for the next retry attempt
                snippet = response_str[:200] if response_str else ""
                if self.language == "en":
                    feedback = (
                        f"\n\n[Correction Notice: Your previous output was not valid JSON ({last_error}). "
                        f"Previous raw output: {snippet!r}. "
                        "Please return strictly valid JSON matching the required format, without markdown fences or extraneous text.]"
                    )
                else:
                    feedback = (
                        f"\n\n[修正提示：您上一次的输出不是合法的 JSON 格式（错误：{last_error}）。"
                        f"原输出片段：{snippet!r}。"
                        "请严格仅返回符合格式要求的有效 JSON 对象，不要添加 markdown 代码块标记或无关的文字。]"
                    )
                current_prompt = prompt + feedback

        return {"thought": "Failed to get valid response.", "action": {}}

    def _build_status_prompt(self, player: Player) -> str:
        """Constructs the comprehensive status section of the main prompt.

        This method gathers all relevant information for the LLM to make an informed
        decision, including the player's role, game state, visible logs, and memory.

        Args:
            player: The player for whom the prompt is being built.

        Returns:
            A formatted string containing the full status and history for the player.
        """
        sheriff_status = "You are the Sheriff." if player.is_sheriff else ""
        player_status = ", ".join([f"{p.name} ({'alive' if p.is_alive else 'dead'})" for p in self.game.players])

        visible_log = "Nothing has happened yet."
        if player.logs:
            filtered_entries = [
                entry for entry in player.logs
                if entry.log_type not in (LogType.PLAYER_THINKING, LogType.PLAYER_DONE_THINKING, LogType.THOUGHT)
            ]
            if filtered_entries:
                visible_log = "\n".join([f"- {log_entry.get_text(self.language)}" for log_entry in filtered_entries])

        long_term_memory = ""
        if player.long_term_memory:
            long_term_memory = f"\nLong Term Memory:\n{player.long_term_memory}"

        # Role-specific information is added to give the LLM crucial context.
        role_info = "You have no special information."
        if isinstance(player.role, Witch):
            role_info = (f"- You have {'a save potion' if player.role.has_save else 'no save potion'} left.\n"
                         f"- You have {'a poison potion' if player.role.has_poison else 'no poison potion'} left.")
            if player.role.has_save and self.game.state.__class__.__name__ == "WitchNightState" and self.game.night_kill_target:
                 role_info += f"\n- Tonight, the werewolves targeted: {self.game.night_kill_target.name}."
        elif isinstance(player.role, Werewolf):
            werewolf_team = [p.name for p in self.game.players if p.is_alive and isinstance(p.role, Werewolf)]
            role_info = f"- Your fellow werewolves are: {', '.join(werewolf_team)}."
        elif isinstance(player.role, Seer):
            role_info = "- You are the Seer. You can check one player's identity each night."
        elif isinstance(player.role, Guard):
            role_info = "- You are the Guard. You can protect one player each night."
            if player.role.last_protected:
                role_info += f"\n- Last night you protected {player.role.last_protected.name}. You cannot protect them again tonight."
        elif isinstance(player.role, Hunter):
            role_info = "- You are the Hunter. If you die (except by poison), you can shoot someone."

        status_prompt_template = self._load_prompt("status", "status")
        return status_prompt_template.format(
            player=player,
            sheriff_status=sheriff_status,
            game=self.game,
            player_status=player_status,
            role_info=role_info,
            visible_log=visible_log + long_term_memory
        )

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
        if self.game:
            self.game.log(LogEntry(
                log_type=LogType.PLAYER_THINKING,
                message={"en": f"{player.name} is thinking...", "zh": f"{player.name} 正在思考..."},
                source=player,
                camps=["All"]
            ))

        try:
            max_retries = 3
            for attempt in range(max_retries):
                try:
                    base_rules = self._load_prompt("", "base_rules")
                    characteristic_prompt = self._load_prompt("characteristic", self.personality)
                    status_prompt = self._build_status_prompt(player)
                    action_prompt_template = self._load_prompt("action", action_name)
                    action_prompt = action_prompt_template.format(**format_kwargs)

                    prompt = f"{base_rules}\n\n{characteristic_prompt}\n\n--- CURRENT STATUS ---\n{status_prompt}\n\n--- ACTION REQUIRED ---\n{action_prompt}"
                    
                    response = self._get_llm_response(prompt)
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
                    print(f"Attempt {attempt + 1}/{max_retries} failed for {player.name}: {e}")
                    if attempt == max_retries - 1:
                        print(f"All attempts failed. Falling back to SafeController.")
                        return self._get_fallback_decision(player, action_name, format_kwargs)
            
            return self._get_fallback_decision(player, action_name, format_kwargs)
        finally:
            if self.game:
                self.game.log(LogEntry(
                    log_type=LogType.PLAYER_DONE_THINKING,
                    message={"en": f"{player.name} finished thinking.", "zh": f"{player.name} 思考完毕。"},
                    source=player,
                    camps=["All"]
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

    def get_speech(self, player: Player) -> str:
        action = self._get_decision(player, "speech", {})
        return action.get("speech", "...")

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
        visible_log = "Nothing has happened yet."
        if logs_to_summarize:
            filtered_entries = [
                entry for entry in logs_to_summarize
                if entry.log_type not in (LogType.PLAYER_THINKING, LogType.PLAYER_DONE_THINKING, LogType.THOUGHT)
            ]
            if filtered_entries:
                visible_log = "\n".join([f"- {log_entry.get_text(self.language)}" for log_entry in filtered_entries])

        prompt_template = self._load_prompt("memory", "summarize_day")
        prompt = prompt_template.format(
            visible_log=visible_log,
            long_term_memory=player.long_term_memory or "None"
        )

        response = self._get_llm_response(prompt)
        summary = response.get("summary")
        
        if summary:
            player.long_term_memory = summary
            print(f"Summarized history for {player.name}.")