import unittest
from unittest.mock import MagicMock
import json

from llm_player.controller import extract_json, LLMController
from game.controllers import RandomController
from game.player import Player, Villager
from game.game import Game


class TestLLMRobustness(unittest.TestCase):

    def test_extract_json_pure(self):
        raw = '{"thought": "I suspect player 2", "action": {"vote": "Player 2"}}'
        data = extract_json(raw)
        self.assertEqual(data["thought"], "I suspect player 2")
        self.assertEqual(data["action"]["vote"], "Player 2")

    def test_extract_json_markdown_fence(self):
        raw = '```json\n{"thought": "Guarding player 1", "action": {"protect": "Player 1"}}\n```'
        data = extract_json(raw)
        self.assertEqual(data["thought"], "Guarding player 1")
        self.assertEqual(data["action"]["protect"], "Player 1")

    def test_extract_json_markdown_fence_without_tag(self):
        raw = '```\n{"thought": "No poison tonight", "action": {"poison": null}}\n```'
        data = extract_json(raw)
        self.assertEqual(data["action"]["poison"], None)

    def test_extract_json_conversational_chatter(self):
        raw = (
            "Certainly! Here is my werewolf decision:\n\n"
            '```json\n{"thought": "Targeting the seer", "action": {"kill": "Player 3"}}\n```\n'
            "Let me know if you need anything else!"
        )
        data = extract_json(raw)
        self.assertEqual(data["thought"], "Targeting the seer")
        self.assertEqual(data["action"]["kill"], "Player 3")

    def test_extract_json_bare_with_preamble_and_postamble(self):
        raw = (
            "Here is the result:\n"
            '{"thought": "Abstaining", "action": {"vote": null}}\n'
            "End of response."
        )
        data = extract_json(raw)
        self.assertEqual(data["action"]["vote"], None)

    def test_extract_json_with_braces_in_strings(self):
        raw = '{"thought": "Player 1 said {hello} and {goodbye}", "action": {"target": "Player 1"}}'
        data = extract_json(raw)
        self.assertEqual(data["thought"], "Player 1 said {hello} and {goodbye}")
        self.assertEqual(data["action"]["target"], "Player 1")

    def test_extract_json_invalid(self):
        with self.assertRaises(json.JSONDecodeError):
            extract_json("This is definitely not json at all.")

    def test_llm_controller_retry_feedback_en(self):
        mock_client = MagicMock()
        # First attempt returns invalid json, second returns valid json in markdown block
        mock_client.get_completion.side_effect = [
            "Not valid json here",
            '```json\n{"thought": "Recovered", "action": {"speech": "Hello"}}\n```'
        ]
        controller = LLMController(llm_client=mock_client, language="en")
        res = controller._get_llm_response("Base prompt")

        self.assertEqual(res["thought"], "Recovered")
        self.assertEqual(mock_client.get_completion.call_count, 2)
        # Check that the second prompt contains English corrective feedback
        second_prompt = mock_client.get_completion.call_args_list[1][0][0]
        self.assertIn("Correction Notice", second_prompt)
        self.assertIn("Base prompt", second_prompt)

    def test_llm_controller_retry_feedback_zh(self):
        mock_client = MagicMock()
        mock_client.get_completion.side_effect = [
            "错误的格式",
            '{"thought": "恢复成功", "action": {}}'
        ]
        controller = LLMController(llm_client=mock_client, language="zh")
        res = controller._get_llm_response("基础提示词")

        self.assertEqual(res["thought"], "恢复成功")
        self.assertEqual(mock_client.get_completion.call_count, 2)
        second_prompt = mock_client.get_completion.call_args_list[1][0][0]
        self.assertIn("修正提示", second_prompt)

    def test_random_controller_localization(self):
        player = Player("Player 1", Villager())

        # Chinese default
        rc_zh = RandomController(language="zh")
        rc_zh._think = lambda: None  # Skip sleep
        self.assertEqual(rc_zh.get_speech(player), "我是AI玩家。我在努力寻找狼人。")

        # English
        rc_en = RandomController(language="en")
        rc_en._think = lambda: None
        self.assertEqual(rc_en.get_speech(player), "I am an AI player. I'm trying to find the werewolves.")

        # Inherit language from Game instance
        rc_game = RandomController()
        rc_game._think = lambda: None
        game = Game({"Player 1": rc_game}, language="en")
        rc_game.game = game
        self.assertEqual(rc_game.get_speech(player), "I am an AI player. I'm trying to find the werewolves.")


if __name__ == "__main__":
    unittest.main()
