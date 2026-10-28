import unittest
from unittest.mock import MagicMock
from game.game import Game
from game.log import LogEntry, LogType
from game.player import Player, Villager, Werewolf
from game.controllers import Controller, HumanController, RandomController
from web.controller import WebController
from game.states.day_states import DayEndState
from game.events.day_events import PlayerDied, PlayerVoted


class MockAIController(RandomController):
    def __init__(self, summary_result="AI summarized memory", fail=False):
        super().__init__()
        self.summary_result = summary_result
        self.fail = fail
        self.summarized = False

    def summarize_history(self, player, logs_to_summarize):
        self.summarized = True
        if self.fail:
            raise RuntimeError("API timeout")
        player.long_term_memory = self.summary_result


class TestLoggingSystem(unittest.TestCase):
    def test_log_entry_get_text(self):
        # Multilingual dict
        entry = LogEntry(
            log_type=LogType.SYSTEM,
            message={"en": "Hello world", "zh": "你好世界"}
        )
        self.assertEqual(entry.get_text("zh"), "你好世界")
        self.assertEqual(entry.get_text("en"), "Hello world")
        # Missing language falls back to zh/en
        self.assertEqual(entry.get_text("fr"), "你好世界")

        # Plain string
        str_entry = LogEntry(
            log_type=LogType.SYSTEM,
            message="Raw string message"
        )
        self.assertEqual(str_entry.get_text("zh"), "Raw string message")
        self.assertEqual(str_entry.get_text("en"), "Raw string message")

    def test_thought_privacy(self):
        human_ctrl = HumanController()
        ai_ctrl_1 = RandomController()
        ai_ctrl_2 = RandomController()

        p_human = Player("Player 1", human_ctrl)
        p_ai_1 = Player("Player 2", ai_ctrl_1)
        p_ai_2 = Player("Player 3", ai_ctrl_2)

        p_human.role = Villager()
        p_ai_1.role = Werewolf()
        p_ai_2.role = Villager()

        controllers = {
            "Player 1": human_ctrl,
            "Player 2": ai_ctrl_1,
            "Player 3": ai_ctrl_2,
        }
        game = Game(controllers)

        thought_entry = LogEntry(
            log_type=LogType.THOUGHT,
            message={"en": "I suspect Player 3", "zh": "我怀疑 Player 3"},
            source=p_ai_1,
            visible_to_players=[p_ai_1]
        )
        game.log(thought_entry)

        # Thought must be preserved in total game_log for evaluation
        self.assertIn(thought_entry, game.game_log)

        # Only the thinking AI sees its own thought; other AI and human player do NOT
        self.assertTrue(game._is_visible(thought_entry, p_ai_1))
        self.assertFalse(game._is_visible(thought_entry, p_ai_2))
        self.assertFalse(game._is_visible(thought_entry, p_human))

    def test_web_controller_log_listener_and_indexing(self):
        web_ctrl = WebController()
        ai_ctrl = RandomController()

        controllers = {
            "Player 1": web_ctrl,
            "Player 2": ai_ctrl,
        }
        game = Game(controllers, player_role="Villager")
        game.add_log_listener(web_ctrl.add_log)

        # Initial setup logs should already be caught
        initial_logs = web_ctrl.get_logs(0)
        self.assertGreater(len(initial_logs), 0)
        initial_count = len(initial_logs)

        # Add a public log
        public_entry = LogEntry(
            log_type=LogType.SYSTEM,
            message={"en": "Day 1 arrives", "zh": "第一天到来了"},
            camps=["All"]
        )
        game.log(public_entry)

        # Add a secret log visible only to Player 2
        p2 = game.get_player_by_name("Player 2")
        secret_entry = LogEntry(
            log_type=LogType.SYSTEM,
            message={"en": "Secret werewolf chat", "zh": "狼人悄悄话"},
            visible_to_players=[p2]
        )
        game.log(secret_entry)

        # Add another public log
        public_entry_2 = LogEntry(
            log_type=LogType.SYSTEM,
            message={"en": "Execution starts", "zh": "开始处决"},
            camps=["All"]
        )
        game.log(public_entry_2)

        # Retrieve newly arrived logs starting from initial_count
        new_logs = web_ctrl.get_logs(initial_count)
        # Should contain exactly the two public logs, not the secret log
        self.assertEqual(len(new_logs), 2)
        messages = [l["message"]["zh"] for l in new_logs]
        self.assertIn("第一天到来了", messages)
        self.assertIn("开始处决", messages)
        self.assertNotIn("狼人悄悄话", messages)

        # Indexing test: querying with start_index = initial_count + 2 should return empty
        self.assertEqual(len(web_ctrl.get_logs(initial_count + 2)), 0)

    def test_day_end_preserves_full_logs_without_summarization_wipe(self):
        ctrl1 = MockAIController()
        ctrl2 = MockAIController()

        controllers = {
            "Player 1": ctrl1,
            "Player 2": ctrl2,
        }
        game = Game(controllers)
        p1 = game.get_player_by_name("Player 1")
        p2 = game.get_player_by_name("Player 2")

        dummy_log = LogEntry(
            log_type=LogType.SPEECH,
            message="Some speech",
            camps=["All"]
        )
        p1.logs.append(dummy_log)
        p2.logs.append(dummy_log)

        state = DayEndState(game)
        state.handle()

        # Full chronological logs are preserved across days without dusk wipe
        self.assertFalse(ctrl1.summarized)
        self.assertIn(dummy_log, p1.logs)
        self.assertIn(dummy_log, p2.logs)

    def test_death_and_vote_unification(self):
        controllers = {
            "Player 1": RandomController(),
            "Player 2": RandomController(),
        }
        game = Game(controllers)
        p1 = game.get_player_by_name("Player 1")
        p2 = game.get_player_by_name("Player 2")

        died_events = []
        voted_events = []
        game.event_bus.subscribe(PlayerDied, lambda e: died_events.append(e))
        game.event_bus.subscribe(PlayerVoted, lambda e: voted_events.append(e))

        # Test record_death
        game.record_death(p1, reason="poison", phase="night")
        self.assertFalse(p1.is_alive)
        self.assertEqual(p1.death_reason, "poison")
        self.assertEqual(len(game.death), 1)
        self.assertEqual(game.death[0]["player"], "Player 1")
        self.assertEqual(game.death[0]["reason"], "poison")
        self.assertEqual(len(died_events), 1)
        self.assertEqual(died_events[0].player, p1)

        # Duplicate death recording should be safely ignored
        game.record_death(p1, reason="poison", phase="night")
        self.assertEqual(len(game.death), 1)
        self.assertEqual(len(died_events), 1)

        # Test record_vote
        game.record_vote("Day 1 Vote", {p2: p1}, result="Player 1 Executed")
        self.assertEqual(len(game.vote_history), 1)
        self.assertEqual(game.vote_history[0]["phase"], "Day 1 Vote")
        self.assertEqual(game.vote_history[0]["votes"]["Player 2"], "Player 1")
        self.assertEqual(len(voted_events), 1)
        self.assertEqual(voted_events[0].voter, p2)
        self.assertEqual(voted_events[0].target, p1)


if __name__ == "__main__":
    unittest.main()
