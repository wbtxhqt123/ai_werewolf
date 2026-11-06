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

    def test_human_werewolf_has_priority_for_night_kill_target(self):
        from game.controllers import SafeController
        from game.states.night_states import WerewolfNightState
        from game.player import Werewolf, Villager

        human_ctrl = WebController()
        ai_ctrl_1 = SafeController()
        ai_ctrl_2 = SafeController()

        game = Game(
            {
                "Player 1": ai_ctrl_1,
                "Player 2": human_ctrl,
                "Player 3": ai_ctrl_2,
                "Player 4": SafeController(),
            },
            language="zh",
        )
        p1, p2, p3, p4 = game.players
        p1.role = Werewolf()
        p2.role = Werewolf()
        p3.role = Werewolf()
        p4.role = Villager()

        whisper_order = []
        ai_ctrl_1.get_speech = lambda p: (whisper_order.append(p.name) or "建议刀4号")
        ai_ctrl_2.get_speech = lambda p: (whisper_order.append(p.name) or "同意刀4号")
        human_ctrl.get_speech = lambda p: (whisper_order.append(p.name) or "好，刀4号")
        human_ctrl.get_werewolf_target = MagicMock(return_value=p4)
        ai_ctrl_1.get_werewolf_target = MagicMock(return_value=p1)
        ai_ctrl_2.get_werewolf_target = MagicMock(return_value=p1)

        state = WerewolfNightState(game)
        state.handle()

        # AI wolves whisper before human wolf, and human wolf always chooses the final kill target
        self.assertEqual(whisper_order[-1], "Player 2")
        human_ctrl.get_werewolf_target.assert_called_once()
        ai_ctrl_1.get_werewolf_target.assert_not_called()
        ai_ctrl_2.get_werewolf_target.assert_not_called()
        self.assertEqual(game.night_kill_target, p4)

    def test_sheriff_candidate_withdrawal_and_auto_election(self):
        from game.controllers import SafeController
        from game.states.sheriff_states import SheriffSpeechState, SheriffWithdrawState, SheriffVoteState
        from game.log import LogType

        game = Game(
            {
                "Player 1": SafeController(),
                "Player 2": SafeController(),
                "Player 3": SafeController(),
                "Player 4": SafeController(),
            },
            language="zh",
        )
        p1, p2, p3, p4 = game.players
        for p in (p1, p2, p3):
            p.is_sheriff_candidate = True
        game.election_players = [p1, p2, p3]
        game.initial_election_players = [p1, p2, p3]

        # P1 withdraws during speech; P2 and P3 stay during speech
        def p1_speech(player):
            setattr(player, "withdrew_in_speech", True)
            return "我是好人，上警表水，我退水。"

        p1.controller.get_speech = p1_speech
        p2.controller.get_speech = lambda p: "我是真预言家！"
        p3.controller.get_speech = lambda p: "我也是上警看局势的。"

        speech_state = SheriffSpeechState(game)
        speech_state.handle()

        self.assertFalse(p1.is_sheriff_candidate)
        self.assertEqual(game.election_players, [p2, p3])
        next_state, _ = speech_state.transition()
        self.assertEqual(next_state, "sheriff_withdraw")

        # In SheriffWithdrawState, P3 withdraws, leaving only P2 -> P2 auto-elected Sheriff!
        p2.controller.get_sheriff_withdraw_decision = lambda p: False
        p3.controller.get_sheriff_withdraw_decision = lambda p: True

        withdraw_state = SheriffWithdrawState(game)
        withdraw_state.handle()

        self.assertEqual(game.sheriff, p2)
        self.assertTrue(p2.is_sheriff)
        self.assertFalse(p3.is_sheriff_candidate)
        next_after_withdraw, _ = withdraw_state.transition()
        self.assertEqual(next_after_withdraw, "day_announcement")

        withdraw_logs = [e for e in game.game_log if e.log_type == LogType.SHERIFF_WITHDRAW]
        self.assertEqual(len(withdraw_logs), 2)

    def test_dead_player_spectator_mode_and_seat_selection(self):
        from starlette.testclient import TestClient
        from web.server import app, game_manager
        from game.controllers import SafeController
        from game.log import LogEntry, LogType

        client = TestClient(app)

        # 1. Start game with custom seat = 3
        start_res = client.post("/api/game/start", json={
            "num_players": 6,
            "user_role": "Villager",
            "user_seat": 3,
            "language": "zh"
        })
        self.assertEqual(start_res.status_code, 200)
        start_data = start_res.json()
        self.assertEqual(start_data["human_player"], "Player 3")
        game_id = start_data["game_id"]

        session = game_manager.get_game(game_id)
        self.assertIsNotNone(session)
        session.game_instance.stop()

        # 2. Spectate blocked while human player is alive
        human_p = session.game_instance.get_player_by_name("Player 3")
        self.assertTrue(human_p.is_alive)
        mock_thread = MagicMock()
        mock_thread.is_alive.return_value = True
        session.game_thread = mock_thread

        spec_blocked = client.post("/api/game/spectate", json={"game_id": game_id})
        self.assertEqual(spec_blocked.status_code, 403)

        # 3. Once human player is dead and no pending input, spectate unlocks all roles & thoughts
        human_p.is_alive = False
        session.web_controller.pending_request = None
        spec_ok = client.post("/api/game/spectate", json={"game_id": game_id})
        self.assertEqual(spec_ok.status_code, 200)
        self.assertTrue(spec_ok.json()["spectator_mode"])

        state_res = client.get(f"/api/game/{game_id}/state")
        state_json = state_res.json()
        self.assertTrue(state_json["spectator_mode"])
        self.assertEqual(state_json["human_player"], "Player 3")
        for p_info in state_json["players"]:
            self.assertNotEqual(p_info["role"], "Unknown")

        # 4. Verify that after spectator mode is enabled, new AI THOUGHT and night logs are visible to the spectator
        ai_player = session.game_instance.get_player_by_name("Player 1")
        prev_log_len = len(session.web_controller.get_logs(0))
        session.game_instance.log(
            LogEntry(
                log_type=LogType.THOUGHT,
                message={"en": "(Player 1 thought): Secret wolf plan", "zh": "(Player 1 思考): 秘密狼人计划"},
                source=ai_player,
                visible_to_players=[ai_player],
            )
        )
        new_logs = session.web_controller.get_logs(prev_log_len)
        self.assertEqual(len(new_logs), 1)
        self.assertEqual(new_logs[0]["type"], "THOUGHT")

        # 5. LLM test endpoint without API key returns random mode
        llm_test_res = client.post("/api/llm/test", json={"language": "zh"})
        self.assertEqual(llm_test_res.status_code, 200)
        self.assertEqual(llm_test_res.json()["mode"], "random")

        game_manager.remove_game(game_id)

    def test_llm_and_web_controller_sheriff_withdrawal_end_to_end(self):
        import json
        from llm_player.controller import LLMController
        from game.states.sheriff_states import SheriffSpeechState, SheriffVoteState
        from game.player import Seer, Villager, Werewolf
        from game.controllers import SafeController

        mock_llm = MagicMock()
        llm_ctrl = LLMController(personality="cautious", llm_client=mock_llm, language="zh")
        web_ctrl = WebController(timeout=2.0)

        game = Game(
            {
                "Player 1": web_ctrl,
                "Player 2": llm_ctrl,
                "Player 3": SafeController(),
                "Player 4": SafeController(),
            },
            language="zh",
        )
        p1, p2, p3, p4 = game.players
        p1.role = Villager()
        p2.role = Villager()
        p3.role = Seer()
        p4.role = Werewolf()

        for p in (p1, p2, p3):
            p.is_sheriff_candidate = True
        game.election_players = [p1, p2, p3]
        game.initial_election_players = [p1, p2, p3]

        speech_state = SheriffSpeechState(game)
        game.state = speech_state

        # 1. WebController candidate submits {"speech": "", "withdraw": True}
        def feed_web_withdraw():
            while web_ctrl.pending_request is None:
                time.sleep(0.01)
            self.assertIn("Withdraw", web_ctrl.pending_request.get("options") or [])
            web_ctrl.set_input({"speech": "", "withdraw": True})

        t = threading.Thread(target=feed_web_withdraw)
        t.start()
        p1_speech = web_ctrl.get_speech(p1)
        t.join()
        self.assertEqual(p1_speech, "我选择退水。")
        self.assertTrue(getattr(p1, "withdrew_in_speech", False))

        # 2. LLMController natural-phrase withdrawal ("我退水了") sets withdrew_in_speech=True
        mock_llm.get_completion.return_value = json.dumps({
            "thought": "上警表水后退水",
            "action": {"speech": "我是好人，上警表个水，我退水了。"}
        })
        p2_speech = llm_ctrl.get_speech(p2)
        self.assertIn("退水", p2_speech)
        self.assertTrue(getattr(p2, "withdrew_in_speech", False))

        # 3. Negated phrase ("我绝不退水") does NOT set withdrew_in_speech
        setattr(p2, "withdrew_in_speech", False)
        mock_llm.get_completion.return_value = json.dumps({
            "thought": "死战到底",
            "action": {"speech": "我是真预言家，我绝不退水！"}
        })
        llm_ctrl.get_speech(p2)
        self.assertFalse(getattr(p2, "withdrew_in_speech", False))

        # 4. Real Seer skips LLM call (0 tokens) in get_sheriff_withdraw_decision
        mock_llm.get_completion.reset_mock()
        p3.controller = llm_ctrl
        self.assertFalse(llm_ctrl.get_sheriff_withdraw_decision(p3))
        mock_llm.get_completion.assert_not_called()

        # 5. In SheriffVoteState, withdrawn candidate P1 (who was in initial_election_players) cannot vote; only P4 votes
        game.election_players = [p2, p3]
        p1.is_sheriff_candidate = False
        p1_vote_mock = MagicMock(return_value=p2)
        p4_vote_mock = MagicMock(return_value=p3)
        p1.controller.get_vote_for_sheriff = p1_vote_mock
        p4.controller.get_vote_for_sheriff = p4_vote_mock

        vote_state = SheriffVoteState(game)
        vote_state.handle()
        p1_vote_mock.assert_not_called()
        p4_vote_mock.assert_called_once()
        self.assertEqual(game.sheriff, p3)


if __name__ == "__main__":
    unittest.main()
