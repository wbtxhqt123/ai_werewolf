import unittest
import threading
import time
from unittest.mock import MagicMock

from web.controller import WebController
from web.server import GameManager, GameSession
from game.player import Player, Villager
from game.game import Game


class TestWebConcurrency(unittest.TestCase):

    def test_web_controller_timeout_speech(self):
        # Short timeout for testing
        ctrl = WebController(timeout=0.05)
        player = Player("Player 1", Villager())
        speech = ctrl.get_speech(player)
        self.assertEqual(speech, "...")

    def test_web_controller_timeout_vote(self):
        ctrl = WebController(timeout=0.05)
        p1 = Player("Player 1", Villager())
        p2 = Player("Player 2", Villager())
        vote = ctrl.get_vote(p1, [p2])
        self.assertIsNone(vote)

    def test_web_controller_timeout_choice_options(self):
        ctrl = WebController(timeout=0.05)
        p1 = Player("Player 1", Villager())
        p2 = Player("Player 2", Villager())
        # Werewolf choice defaults to first option when timed out
        target = ctrl.get_werewolf_target(p1, [p2])
        self.assertEqual(target, p2)

    def test_web_controller_timeout_yes_no(self):
        ctrl = WebController(timeout=0.05)
        p1 = Player("Player 1", Villager())
        p2 = Player("Player 2", Villager())
        save = ctrl.get_witch_save_decision(p1, p2)
        self.assertFalse(save)

    def test_web_controller_successful_input_before_timeout(self):
        ctrl = WebController(timeout=2.0)
        p1 = Player("Player 1", Villager())

        def provide_input():
            time.sleep(0.02)
            ctrl.set_input("I am an innocent villager.")

        threading.Thread(target=provide_input).start()
        speech = ctrl.get_speech(p1)
        self.assertEqual(speech, "I am an innocent villager.")

    def test_game_manager_ttl_and_eviction(self):
        gm = GameManager()

        # Mock sessions
        mock_game = MagicMock()
        mock_game.state = None
        mock_ctrl = MagicMock()

        # Thread 1: alive (active game)
        t_active = MagicMock()
        t_active.is_alive.return_value = True

        # Thread 2: finished (done game)
        t_done = MagicMock()
        t_done.is_alive.return_value = False

        id_active = gm.create_game(mock_game, mock_ctrl, t_active)
        id_done = gm.create_game(mock_game, mock_ctrl, t_done)

        # Both exist initially
        self.assertIsNotNone(gm.get_game(id_active))
        self.assertIsNotNone(gm.get_game(id_done))

        # Backdate access time for id_done by 700s (> finished_ttl 600s)
        gm.active_games[id_done].last_accessed_at = time.time() - 700

        # Run cleanup
        pruned = gm.cleanup_expired_games(active_ttl_seconds=7200, finished_ttl_seconds=600)
        self.assertIn(id_done, pruned)
        self.assertNotIn(id_active, pruned)

        self.assertIsNone(gm.get_game(id_done))
        self.assertIsNotNone(gm.get_game(id_active))


if __name__ == "__main__":
    unittest.main()
