from __future__ import annotations
import os
import json
from typing import TYPE_CHECKING, Any, List

from llm_player.controller import LLMClient

if TYPE_CHECKING:
    from game.game import Game
    from game.player import Player

class GameEvaluator:
    """Evaluates player performance and handles follow-up chat."""

    def __init__(
        self,
        api_key: str | None = None,
        language: str = "zh",
        base_url: str | None = None,
        model: str | None = None,
        provider: str | None = None,
        llm_client: Any | None = None,
    ):
        self.llm_client = llm_client or LLMClient(
            api_key=api_key,
            base_url=base_url,
            model=model,
            provider=provider,
        )
        self.language = language
        self.prompt_dir = os.path.join(os.path.dirname(__file__), "prompts")
        self.current_mode = None
        self.game_summary = ""
        self.player_role = ""
        self.game_result = ""
        self.previous_evaluation = ""

    def _load_prompt(self, prompt_type: str, name: str) -> str:
        """Loads a prompt template from a file."""
        path_parts = [self.prompt_dir, self.language, prompt_type, f"{name}.txt"]
        file_path = os.path.join(*path_parts)
        
        try:
            with open(file_path, "r", encoding='utf-8') as f:
                return f.read()
        except FileNotFoundError:
            # Fallback to English if specific language file not found
            if self.language != "en":
                path_parts[1] = "en"
                file_path = os.path.join(*path_parts)
                with open(file_path, "r", encoding='utf-8') as f:
                    return f.read()
            raise

    def _generate_game_summary(self, game_logs: List[dict], player_name: str) -> str:
        """Summarizes the game logs into a concise text."""
        summary = []
        for log in game_logs:
            # Filter for important events or events related to the player
            msg = log.get('message', '')
            if isinstance(msg, dict):
                msg = msg.get(self.language, msg.get('en', str(msg)))
            
            # Include all logs for now, maybe filter later if too long
            summary.append(f"- {msg}")
        return "\n".join(summary)

    def _call_llm_text(self, prompt: str) -> str:
        try:
            return self.llm_client.get_completion(prompt, json_mode=False)
        except TypeError:
            return self.llm_client.get_completion(prompt)

    def evaluate(self, game_logs: List[dict], player_name: str, player_role: str, game_result: str, mode: str) -> str:
        """Generates an evaluation of the player's performance."""
        self.current_mode = mode
        self.game_summary = self._generate_game_summary(game_logs, player_name)
        role_zh_map = {
            "Villager": "村民",
            "Werewolf": "狼人",
            "Witch": "女巫",
            "Seer": "预言家",
            "Guard": "守卫",
            "Hunter": "猎人",
            "Black Werewolf King": "黑狼王",
            "Unknown": "未知",
        }
        result_zh_map = {
            "Game Over": "游戏结束",
            "Winner: Villagers": "获胜阵营：好人阵营（村民）",
            "Winner: Werewolves": "获胜阵营：狼人阵营",
        }
        if self.language == "zh":
            self.player_role = role_zh_map.get(player_role, player_role)
            self.game_result = result_zh_map.get(game_result, game_result)
        else:
            self.player_role = player_role
            self.game_result = game_result

        prompt_template = self._load_prompt("evaluation", mode)
        prompt = prompt_template.format(
            game_summary=self.game_summary,
            player_role=self.player_role,
            game_result=self.game_result
        )

        self.previous_evaluation = self._call_llm_text(prompt)
        return self.previous_evaluation

    def chat(self, user_message: str) -> str:
        """Responds to the user's message in the context of the evaluation."""
        if not self.previous_evaluation:
            return "Error: No evaluation context found."

        mode_descriptions = {
            "mild": "You are supportive and constructive.",
            "neutral": "You are objective and analytical.",
            "mean": "You are harsh, sarcastic, and critical."
        }
        
        # Localized descriptions
        if self.language == "zh":
             mode_descriptions = {
                "mild": "你是支持和建设性的。",
                "neutral": "你是客观和分析性的。",
                "mean": "你是严厉、讽刺和挑剔的。"
            }

        prompt_template = self._load_prompt("evaluation", "chat")
        prompt = prompt_template.format(
            mode=self.current_mode,
            mode_description=mode_descriptions.get(self.current_mode, ""),
            game_summary=self.game_summary,
            player_role=self.player_role,
            game_result=self.game_result,
            previous_evaluation=self.previous_evaluation,
            user_message=user_message
        )

        return self._call_llm_text(prompt)
