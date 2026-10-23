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

    def test_llm_controller_validates_potential_targets(self):
        mock_client = MagicMock()
        # LLM tries to vote for Player 1 (not in potential_targets)
        mock_client.get_completion.return_value = '{"thought": "Vote self", "action": {"vote": "Player 1"}}'
        controller = LLMController(llm_client=mock_client, language="en")
        game = Game({"Player 1": controller, "Player 2": RandomController(), "Player 3": RandomController()}, language="en")
        p1, p2, p3 = game.players
        # Only p2 and p3 are valid targets
        vote_target = controller.get_vote(p1, [p2, p3])
        self.assertIsNone(vote_target)

    def test_llm_controller_witch_poison_without_prior_save_call(self):
        from game.player import Witch
        mock_client = MagicMock()
        mock_client.get_completion.return_value = '{"thought": "Poison Player 2", "action": {"save": false, "poison": "Player 2"}}'
        controller = LLMController(llm_client=mock_client, language="en")
        game = Game({"Player 1": controller, "Player 2": RandomController()}, language="en")
        p1, p2 = game.players
        p1.role = Witch()
        p1.role.has_save = False  # Save potion already used on an earlier night

        # Directly call get_witch_poison_target without calling get_witch_save_decision
        poison_target = controller.get_witch_poison_target(p1, [p1, p2])
        self.assertEqual(poison_target, p2)

    def test_llm_controller_find_player_by_localized_seat_labels(self):
        controller = LLMController(language="zh")
        game = Game({"Player 1": controller, "Player 2": RandomController(), "Player 3": RandomController()}, language="zh")
        p1, p2, p3 = game.players
        self.assertEqual(controller._find_player_by_name("Player 2", [p2, p3]), p2)
        self.assertEqual(controller._find_player_by_name("2号玩家", [p2, p3]), p2)
        self.assertEqual(controller._find_player_by_name("2号", [p2, p3]), p2)
        self.assertEqual(controller._find_player_by_name("P3", [p2, p3]), p3)

    def test_llm_controller_status_prompt_localized_zh(self):
        from game.player import Seer
        controller = LLMController(language="zh")
        game = Game({"Player 1": controller, "Player 2": RandomController()}, language="zh")
        p1 = game.players[0]
        p1.role = Seer()
        p1.is_sheriff = True
        status_zh = controller._build_status_prompt(p1)
        self.assertIn("你的角色是 预言家", status_zh)
        self.assertIn("你是警长。", status_zh)
        self.assertIn("存活", status_zh)
        self.assertNotIn("You are the Sheriff", status_zh)
        self.assertNotIn("You are the Seer", status_zh)

    def test_llm_controller_retries_on_wrong_action_schema_and_recovers(self):
        mock_client = MagicMock()
        # 1st attempt: valid JSON, but wrong key ("target" instead of "vote")
        # 2nd attempt: valid JSON with expected "vote" key
        mock_client.get_completion.side_effect = [
            '{"thought": "Voting player 2", "action": {"target": "Player 2"}}',
            '{"thought": "Fixed key", "action": {"vote": "Player 2"}}',
        ]
        controller = LLMController(llm_client=mock_client, language="en")
        game = Game({"Player 1": controller, "Player 2": RandomController()}, language="en")
        p1, p2 = game.players
        target = controller.get_vote(p1, [p2])
        self.assertEqual(target, p2)
        self.assertEqual(mock_client.get_completion.call_count, 2)
        second_prompt = mock_client.get_completion.call_args_list[1][0][0]
        self.assertIn("Missing required key 'vote'", second_prompt)

    def test_llm_controller_normalizes_top_level_action_keys(self):
        mock_client = MagicMock()
        # LLM forgot to nest under "action" and returned {"thought": "...", "speech": "..."}
        mock_client.get_completion.return_value = '{"thought": "Speak directly", "speech": "I am a villager."}'
        controller = LLMController(llm_client=mock_client, language="en")
        game = Game({"Player 1": controller, "Player 2": RandomController()}, language="en")
        p1 = game.players[0]
        speech = controller.get_speech(p1)
        self.assertEqual(speech, "I am a villager.")
        self.assertEqual(mock_client.get_completion.call_count, 1)

    def test_night_thinking_privacy_and_werewolf_king_knowledge(self):
        from game.player import Werewolf, BlackWerewolfKing, Seer
        from game.states.night_states import WerewolfNightState, SeerNightState
        from game.log import LogType

        mock_client = MagicMock()
        mock_client.get_completion.return_value = '{"thought": "Night move", "action": {"speech": "Kill P1", "check": "Player 2"}}'
        wolf_ctrl = LLMController(llm_client=mock_client, language="zh")
        seer_ctrl = LLMController(llm_client=mock_client, language="zh")

        game = Game(
            {
                "Player 1": RandomController(),
                "Player 2": wolf_ctrl,
                "Player 3": RandomController(),
                "Player 4": seer_ctrl,
            },
            language="zh",
        )
        p1, p2, p3, p4 = game.players
        p1.role = Villager()
        p2.role = Werewolf()
        p3.role = BlackWerewolfKing()
        p4.role = Seer()

        # 1. Verify Werewolf AI knows teammates AND who is Black Werewolf King
        status_wolf = wolf_ctrl._build_status_prompt(p2)
        self.assertIn("Player 3 (黑狼王, 存活)", status_wolf)
        self.assertIn("本局黑狼王是：Player 3", status_wolf)

        # 2. Verify PLAYER_THINKING during WerewolfNightState is visible to Werewolves (p2, p3) but NOT Villagers/Seer (p1, p4)
        game.state = WerewolfNightState(game)
        game.game_log.clear()
        p1.logs.clear()
        p2.logs.clear()
        p3.logs.clear()
        p4.logs.clear()
        wolf_ctrl.get_speech(p2)

        p1_thinking = [e for e in p1.logs if e.log_type == LogType.PLAYER_THINKING]
        p3_thinking = [e for e in p3.logs if e.log_type == LogType.PLAYER_THINKING]
        self.assertEqual(len(p1_thinking), 0)
        self.assertEqual(len(p3_thinking), 1)

        # 3. Verify PLAYER_THINKING during SeerNightState is private to Seer only
        game.state = SeerNightState(game)
        p1.logs.clear()
        p2.logs.clear()
        p4.logs.clear()
        seer_ctrl.get_seer_target(p4, [p1, p2, p3])

        self.assertEqual(len([e for e in p1.logs if e.log_type == LogType.PLAYER_THINKING]), 0)
        self.assertEqual(len([e for e in p2.logs if e.log_type == LogType.PLAYER_THINKING]), 0)
        self.assertEqual(len([e for e in p4.logs if e.log_type == LogType.PLAYER_THINKING]), 1)


if __name__ == "__main__":
    unittest.main()
