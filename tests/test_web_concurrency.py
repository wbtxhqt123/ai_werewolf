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

    def test_web_controller_set_timeout(self):
        ctrl = WebController(timeout=60.0)
        self.assertEqual(ctrl.timeout, 60.0)
        ctrl.set_timeout(180.0)
        self.assertEqual(ctrl.timeout, 180.0)

    def test_web_controller_dynamic_timeout_extension(self):
        ctrl = WebController(timeout=0.08)
        p1 = Player("Player 1", Villager())

        def extend_and_input():
            time.sleep(0.04)
            ctrl.set_timeout(0.3)
            time.sleep(0.08)  # at ~0.12s, which exceeds initial 0.08s
            ctrl.set_input("Survived timeout extension!")

        threading.Thread(target=extend_and_input).start()
        speech = ctrl.get_speech(p1)
        self.assertEqual(speech, "Survived timeout extension!")

    def test_api_update_settings(self):
        from starlette.testclient import TestClient
        from web.server import app, game_manager

        mock_game = MagicMock()
        mock_ctrl = WebController(timeout=60.0)
        mock_thread = MagicMock()
        mock_thread.is_alive.return_value = True

        game_id = game_manager.create_game(mock_game, mock_ctrl, mock_thread)
        client = TestClient(app)

        response = client.post("/api/game/settings", json={"game_id": game_id, "turn_timeout": 180.0})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["turn_timeout"], 180.0)
        self.assertEqual(mock_ctrl.timeout, 180.0)

    def test_api_start_game_with_turn_timeout(self):
        from starlette.testclient import TestClient
        from web.server import app, game_manager

        client = TestClient(app)
        start_payload = {
            "num_players": 6,
            "user_role": "Villager",
            "turn_timeout": 300.0,
            "language": "en"
        }
        response = client.post("/api/game/start", json=start_payload)
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn("game_id", data)
        game_id = data["game_id"]

        session = game_manager.get_game(game_id)
        self.assertIsNotNone(session)
        self.assertEqual(session.web_controller.timeout, 300.0)

    def test_api_role_and_operations_privacy_during_active_game(self):
        from starlette.testclient import TestClient
        from web.server import app, game_manager
        from game.controllers import RandomController

        web_ctrl = WebController(timeout=60.0)
        game = Game(
            {"Player 1": web_ctrl, "Player 2": RandomController()},
            player_role="Villager",
            language="en",
        )
        mock_thread = MagicMock()
        mock_thread.is_alive.return_value = True

        game_id = game_manager.create_game(game, web_ctrl, mock_thread)
        client = TestClient(app)

        # 1. During active game, Player 2's role must be masked as "Unknown"
        state_res = client.get(f"/api/game/{game_id}/state")
        self.assertEqual(state_res.status_code, 200)
        players_payload = {p["name"]: p["role"] for p in state_res.json()["players"]}
        self.assertEqual(players_payload["Player 1"], "Villager")
        self.assertEqual(players_payload["Player 2"], "Unknown")

        # 2. During active game, querying Player 2's operations is forbidden
        op_res = client.get(f"/api/game/{game_id}/player/Player 2/operations")
        self.assertEqual(op_res.status_code, 403)

        # 3. Once game finishes, roles and operations are accessible
        mock_thread.is_alive.return_value = False
        state_res_after = client.get(f"/api/game/{game_id}/state")
        players_after = {p["name"]: p["role"] for p in state_res_after.json()["players"]}
        self.assertNotEqual(players_after["Player 2"], "Unknown")

        op_res_after = client.get(f"/api/game/{game_id}/player/Player 2/operations")
        self.assertEqual(op_res_after.status_code, 200)

        game_manager.remove_game(game_id)

    def test_api_evaluate_and_multi_turn_chat(self):
        from starlette.testclient import TestClient
        from web.server import app, game_manager
        from game.controllers import RandomController

        web_ctrl = WebController()
        game = Game(
            {"Player 1": web_ctrl, "Player 2": RandomController()},
            player_role="Villager",
            language="zh",
        )
        game.winner = "Villagers"
        mock_thread = MagicMock()
        mock_thread.is_alive.return_value = False

        game_id = game_manager.create_game(game, web_ctrl, mock_thread)
        client = TestClient(app)

        eval_res = client.post("/api/game/evaluate", json={
            "game_id": game_id,
            "mode": "mean",
            "language": "zh"
        })
        self.assertEqual(eval_res.status_code, 200)
        self.assertIn("evaluation", eval_res.json())

        chat_res = client.post("/api/game/evaluation/chat", json={
            "game_id": game_id,
            "message": "我第一天投得很准吧？"
        })
        self.assertEqual(chat_res.status_code, 200)
        self.assertIn("reply", chat_res.json())
        self.assertTrue(len(chat_res.json()["reply"]) > 0)

        game_manager.remove_game(game_id)

    def test_api_post_game_argue_with_selected_ais(self):
        from starlette.testclient import TestClient
        from web.server import app, game_manager
        from game.controllers import RandomController

        web_ctrl = WebController()
        game = Game(
            {
                "Player 1": web_ctrl,
                "Player 2": RandomController(),
                "Player 3": RandomController(),
            },
            player_role="Villager",
            language="zh",
        )
        game.winner = "Werewolves"
        mock_thread = MagicMock()
        mock_thread.is_alive.return_value = False

        game_id = game_manager.create_game(game, web_ctrl, mock_thread)
        client = TestClient(app)

        argue_res = client.post("/api/game/argue", json={
            "game_id": game_id,
            "selected_players": ["Player 2", "Player 3"],
            "message": "你们两个为什么第一天联手投我？",
            "language": "zh"
        })
        self.assertEqual(argue_res.status_code, 200)
        replies = argue_res.json().get("replies", [])
        self.assertEqual(len(replies), 2)
        self.assertEqual(replies[0]["player"], "Player 2")
        self.assertEqual(replies[1]["player"], "Player 3")
        self.assertTrue(len(replies[0]["reply"]) > 0)
        self.assertTrue(len(replies[1]["reply"]) > 0)

        game_manager.remove_game(game_id)


if __name__ == "__main__":
    unittest.main()
