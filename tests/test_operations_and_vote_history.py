import unittest
from game.game import Game
from game.player import (
    Player,
    Villager,
    Werewolf,
    Witch,
    Seer,
    Guard,
    Hunter,
    BlackWerewolfKing,
)
from game.controllers import Controller, RandomController
from game.log import LogEntry, LogType


class TestOperationsAndVoteHistory(unittest.TestCase):
    def setUp(self):
        controllers: dict[str, Controller] = {
            f"Player {i}": RandomController() for i in range(1, 10)
        }
        self.game = Game(controllers, player_role=None)
        # Assign explicit roles for testing
        role_assignments = [
            (self.game.players[0], Werewolf()),
            (self.game.players[1], Werewolf()),
            (self.game.players[2], BlackWerewolfKing()),
            (self.game.players[3], Seer()),
            (self.game.players[4], Witch()),
            (self.game.players[5], Guard()),
            (self.game.players[6], Hunter()),
            (self.game.players[7], Villager()),
            (self.game.players[8], Villager()),
        ]
        for player, role in role_assignments:
            player.role = role

    def test_werewolf_operations_history(self):
        p1 = self.game.players[0]  # Werewolf
        p2 = self.game.players[1]  # Werewolf
        p3 = self.game.players[2]  # Black Werewolf King
        victim1 = self.game.players[7]
        victim2 = self.game.players[8]

        # Simulate Night 1 werewolf kill
        self.game.day = 1
        self.game.log(
            LogEntry(
                log_type=LogType.WEREWOLF_TARGET,
                message="Targeted Player 8",
                source=p1,
                target=victim1,
                visible_to_roles=["Werewolf", "Black Werewolf King"],
                camps=["Werewolves"],
            )
        )

        # Simulate Night 2 werewolf kill
        self.game.day = 2
        self.game.log(
            LogEntry(
                log_type=LogType.WEREWOLF_TARGET,
                message="Targeted Player 9",
                source=p2,
                target=victim2,
                visible_to_roles=["Werewolf", "Black Werewolf King"],
                camps=["Werewolves"],
            )
        )

        history = self.game.get_player_operations_history(p1.name)
        self.assertEqual(history["role"], "Werewolf")
        self.assertIn("Player 2", history["teammates"])
        self.assertIn("Player 3", history["teammates"])
        self.assertEqual(history["king"], "Player 3")

        # Check kills history
        self.assertIn("kills", history)
        self.assertEqual(len(history["kills"]), 2)
        self.assertEqual(history["kills"][0], {"night": 1, "target": victim1.name})
        self.assertEqual(history["kills"][1], {"night": 2, "target": victim2.name})

        # Ensure werewolf CANNOT see seer checks or witch actions
        self.assertNotIn("checked", history)
        self.assertNotIn("saved", history)
        self.assertNotIn("poisoned", history)
        self.assertNotIn("protected", history)

    def test_seer_operations_history(self):
        seer = self.game.players[3]
        target_wolf = self.game.players[0]
        target_villager = self.game.players[7]

        self.game.day = 1
        self.game.log(
            LogEntry(
                log_type=LogType.SEER_CHECK,
                message="Checked wolf",
                source=seer,
                target=target_wolf,
                data={"result": "Werewolf"},
                visible_to_roles=["Seer"],
                camps=["Villagers"],
            )
        )

        self.game.day = 2
        self.game.log(
            LogEntry(
                log_type=LogType.SEER_CHECK,
                message="Checked villager",
                source=seer,
                target=target_villager,
                data={"result": "Villager"},
                visible_to_roles=["Seer"],
                camps=["Villagers"],
            )
        )

        history = self.game.get_player_operations_history(seer.name)
        self.assertEqual(history["role"], "Seer")
        self.assertEqual(len(history["checked"]), 2)
        self.assertEqual(
            history["checked"][0],
            {"night": 1, "player": target_wolf.name, "camp": "Werewolves"},
        )
        self.assertEqual(
            history["checked"][1],
            {"night": 2, "player": target_villager.name, "camp": "Villagers"},
        )

    def test_witch_and_guard_operations_history(self):
        witch = self.game.players[4]
        guard = self.game.players[5]
        target1 = self.game.players[7]
        target2 = self.game.players[8]

        # Witch actions
        self.game.day = 1
        self.game.log(
            LogEntry(
                log_type=LogType.WITCH_ACTION,
                message="Saved target",
                source=witch,
                target=target1,
                data={"action": "save"},
                visible_to_roles=["Witch"],
                camps=["Villagers"],
            )
        )

        self.game.day = 2
        self.game.log(
            LogEntry(
                log_type=LogType.WITCH_ACTION,
                message="Poisoned target",
                source=witch,
                target=target2,
                data={"action": "poison"},
                visible_to_roles=["Witch"],
                camps=["Villagers"],
            )
        )

        witch_history = self.game.get_player_operations_history(witch.name)
        self.assertEqual(witch_history["saved"], [target1.name])
        self.assertEqual(witch_history["poisoned"], [target2.name])
        self.assertEqual(
            witch_history["saved_details"], [{"night": 1, "target": target1.name}]
        )
        self.assertEqual(
            witch_history["poisoned_details"], [{"night": 2, "target": target2.name}]
        )

        # Guard action
        self.game.day = 1
        self.game.log(
            LogEntry(
                log_type=LogType.GUARD_PROTECT,
                message="Protected target",
                source=guard,
                target=target1,
                visible_to_roles=["Guard"],
                camps=["Villagers"],
            )
        )
        guard_history = self.game.get_player_operations_history(guard.name)
        self.assertEqual(guard_history["protected"], [target1.name])
        self.assertEqual(
            guard_history["protected_details"], [{"night": 1, "target": target1.name}]
        )

    def test_hunter_and_public_shots(self):
        hunter = self.game.players[6]
        black_king = self.game.players[2]
        target1 = self.game.players[0]
        target2 = self.game.players[7]
        villager = self.game.players[8]

        self.game.day = 2
        self.game.log(
            LogEntry(
                log_type=LogType.HUNTER_SHOOT,
                message="Hunter shoots target",
                source=hunter,
                target=target1,
                camps=["All"],
            )
        )

        self.game.day = 3
        self.game.log(
            LogEntry(
                log_type=LogType.BLACKWEREWOLFKING_SHOOT,
                message="Black king shoots target",
                source=black_king,
                target=target2,
                camps=["All"],
            )
        )

        # Hunter should see their own shot role, but not know whether another shooter is Hunter or Black Werewolf King
        hunter_history = self.game.get_player_operations_history(hunter.name)
        self.assertEqual(hunter_history["shot"], [target1.name])
        self.assertEqual(
            hunter_history["shot_details"], [{"day": 2, "target": target1.name}]
        )
        self.assertEqual(hunter_history["public_shots"][0]["role"], "Hunter")
        self.assertEqual(hunter_history["public_shots"][1]["role"], "Unknown")

        # Werewolves know their teammates, so they can distinguish Hunter vs Black Werewolf King shots
        werewolf = self.game.players[0]
        werewolf_history = self.game.get_player_operations_history(werewolf.name)
        self.assertEqual(werewolf_history["public_shots"][0]["role"], "Hunter")
        self.assertEqual(werewolf_history["public_shots"][1]["role"], "Black Werewolf King")

        # Villager can see public shots, but does not know whether the shooter is Hunter or Black Werewolf King
        villager_history = self.game.get_player_operations_history(villager.name)
        self.assertEqual(len(villager_history["public_shots"]), 2)
        self.assertEqual(villager_history["public_shots"][0]["shooter"], hunter.name)
        self.assertEqual(villager_history["public_shots"][0]["role"], "Unknown")
        self.assertEqual(villager_history["public_shots"][0]["target"], target1.name)
        self.assertEqual(villager_history["public_shots"][1]["shooter"], black_king.name)
        self.assertEqual(
            villager_history["public_shots"][1]["role"], "Unknown"
        )
        self.assertEqual(villager_history["public_shots"][1]["target"], target2.name)

    def test_vote_history_recording(self):
        p1 = self.game.players[0]
        p2 = self.game.players[1]
        p3 = self.game.players[2]

        # Record Sheriff Election vote
        self.game.day = 1
        sheriff_votes = {p1: p2, p3: "Abstained"}
        self.game.record_vote("Sheriff Election", sheriff_votes, p2.name)

        # Record Execution vote
        exec_votes = {p1: p3, p2: p3, p3: p1}
        self.game.record_vote("Execution Vote", exec_votes, p3.name)

        self.assertEqual(len(self.game.vote_history), 2)
        entry1 = self.game.vote_history[0]
        self.assertEqual(entry1["day"], 1)
        self.assertEqual(entry1["phase"], "Sheriff Election")
        self.assertEqual(entry1["votes"]["Player 1"], "Player 2")
        self.assertEqual(entry1["votes"]["Player 3"], "Abstained")
        self.assertEqual(entry1["result"], "Player 2")

        entry2 = self.game.vote_history[1]
        self.assertEqual(entry2["phase"], "Execution Vote")
        self.assertEqual(entry2["result"], "Player 3")

    def test_api_operations_and_records(self):
        from starlette.testclient import TestClient
        from web.server import app, game_manager
        from web.controller import WebController
        import threading

        web_ctrl = WebController()
        session_id = game_manager.create_game(
            self.game, web_ctrl, threading.Thread(target=lambda: None)
        )

        client = TestClient(app)

        # Test player operations endpoint
        res_op = client.get(f"/api/game/{session_id}/player/Player 1/operations")
        self.assertEqual(res_op.status_code, 200)
        data_op = res_op.json()
        self.assertEqual(data_op["role"], "Werewolf")
        self.assertIn("kills", data_op)
        self.assertIn("teammates", data_op)

        # Test game records endpoint
        res_rec = client.get(f"/api/game/{session_id}/records")
        self.assertEqual(res_rec.status_code, 200)
        data_rec = res_rec.json()
        self.assertIn("votes", data_rec)
        self.assertIn("deaths", data_rec)

        game_manager.remove_game(session_id)

    def test_votes_hidden_until_all_voters_finish(self):
        import time
        from unittest.mock import MagicMock
        from game.states.day_states import VoteState

        p1 = self.game.players[0]
        p2 = self.game.players[1]
        p3 = self.game.players[2]

        for p in self.game.players[3:]:
            p.is_alive = False

        logs_during_p1_vote = []

        def delayed_p1_vote(player, potential_targets):
            time.sleep(0.05)
            # Check if any EXECUTION_VOTE logs were emitted while P1 is still deciding
            for entry in self.game.game_log:
                if entry.log_type == LogType.EXECUTION_VOTE:
                    logs_during_p1_vote.append(entry)
            return p2

        p1.controller.get_vote = delayed_p1_vote
        p2.controller.get_vote = MagicMock(return_value=p3)
        p3.controller.get_vote = MagicMock(return_value=p1)

        state = VoteState(self.game)
        state.handle()

        # While P1 was deciding, NO execution vote logs should have been logged
        self.assertEqual(len(logs_during_p1_vote), 0)

        # After state.handle() completes, all votes should be logged
        exec_logs = [
            e for e in self.game.game_log if e.log_type == LogType.EXECUTION_VOTE
        ]
        self.assertEqual(len(exec_logs), 3)

    def test_sheriff_votes_hidden_until_all_voters_finish(self):
        import time
        from unittest.mock import MagicMock
        from game.states.sheriff_states import SheriffVoteState

        c1 = self.game.players[0]
        c2 = self.game.players[1]
        v1 = self.game.players[2]
        v2 = self.game.players[3]

        self.game.election_players = [c1, c2]
        for p in self.game.players[4:]:
            p.is_alive = False

        logs_during_v1_vote = []

        def delayed_v1_vote(player, potential_targets):
            time.sleep(0.05)
            for entry in self.game.game_log:
                if entry.log_type == LogType.SHERIFF_VOTE:
                    logs_during_v1_vote.append(entry)
            return c1

        v1.controller.get_vote_for_sheriff = delayed_v1_vote
        v2.controller.get_vote_for_sheriff = MagicMock(return_value=c2)

        state = SheriffVoteState(self.game)
        state.handle()

        # While v1 was deciding, NO sheriff vote logs should have been logged
        self.assertEqual(len(logs_during_v1_vote), 0)

        # After state.handle() completes, both votes should be logged
        sheriff_logs = [
            e for e in self.game.game_log if e.log_type == LogType.SHERIFF_VOTE
        ]
        self.assertEqual(len(sheriff_logs), 2)

    def test_sheriff_election_candidates_hidden_until_all_players_decide(self):
        import time
        from unittest.mock import MagicMock
        from game.states.sheriff_states import SheriffElectionState

        p1 = self.game.players[0]
        p2 = self.game.players[1]
        p3 = self.game.players[2]

        # Only 3 players in game for this test
        self.game.players = [p1, p2, p3]

        logs_during_p1_choice = []
        candidates_during_p1_choice = []

        def delayed_p1_choice(player):
            time.sleep(0.05)
            for entry in self.game.game_log:
                if entry.log_type == LogType.SHERIFF_CANDIDATE:
                    logs_during_p1_choice.append(entry)
            for p in self.game.players:
                if getattr(p, "is_sheriff_candidate", False):
                    candidates_during_p1_choice.append(p)
            return True

        p1.controller.get_join_election_decision = delayed_p1_choice
        p2.controller.get_join_election_decision = MagicMock(return_value=True)
        p3.controller.get_join_election_decision = MagicMock(return_value=False)

        state = SheriffElectionState(self.game)
        state.handle()

        # While P1 was choosing, NO candidate logs should have been emitted
        self.assertEqual(len(logs_during_p1_choice), 0)
        # And candidate flags on player models should NOT have been set yet
        self.assertEqual(len(candidates_during_p1_choice), 0)

        # After state.handle() completes, candidate decisions should all be logged
        candidate_logs = [
            e for e in self.game.game_log if e.log_type == LogType.SHERIFF_CANDIDATE
        ]
        self.assertEqual(len(candidate_logs), 3)
        self.assertTrue(p1.is_sheriff_candidate)
        self.assertTrue(p2.is_sheriff_candidate)
        self.assertFalse(p3.is_sheriff_candidate)

        # Verify structured Sheriff Signup summary data is attached for consolidated chat card
        signup_summary_logs = [
            e for e in self.game.game_log if e.data and e.data.get("phase") == "Sheriff Signup"
        ]
        self.assertEqual(len(signup_summary_logs), 1)
        self.assertEqual(signup_summary_logs[0].data["candidates"], ["Player 1", "Player 2"])
        self.assertEqual(signup_summary_logs[0].data["non_candidates"], ["Player 3"])

    def test_vote_result_log_includes_sheriff_weight_metadata(self):
        from unittest.mock import MagicMock
        from game.states.day_states import VoteState

        p1 = self.game.players[0]
        p2 = self.game.players[1]
        p3 = self.game.players[2]
        for p in self.game.players[3:]:
            p.is_alive = False

        # Make Player 1 the Sheriff
        self.game.sheriff = p1
        p1.is_sheriff = True

        p1.controller.get_vote = MagicMock(return_value=p2)
        p2.controller.get_vote = MagicMock(return_value=p3)
        p3.controller.get_vote = MagicMock(return_value=p2)

        state = VoteState(self.game)
        state.handle()

        vote_result_logs = [
            e for e in self.game.game_log if e.log_type == LogType.VOTE_RESULT
        ]
        self.assertEqual(len(vote_result_logs), 1)
        data = vote_result_logs[0].data
        self.assertEqual(data["phase"], "Execution Vote")
        self.assertEqual(data["result"], "Player 2")
        self.assertEqual(data["sheriff"], "Player 1")
        self.assertIn("Player 1", data["votes"]["Player 2"])
        self.assertIn("Player 3", data["votes"]["Player 2"])

    def test_web_controller_masks_shooter_role_for_non_werewolves(self):
        from web.controller import WebController

        villager = self.game.players[8]  # Villager
        werewolf = self.game.players[0]  # Werewolf
        black_king = self.game.players[2]  # Black Werewolf King
        hunter = self.game.players[6]  # Hunter
        target = self.game.players[7]

        villager_ctrl = WebController()
        villager_ctrl.game = self.game
        villager.controller = villager_ctrl

        wolf_ctrl = WebController()
        wolf_ctrl.game = self.game
        werewolf.controller = wolf_ctrl

        king_shot = LogEntry(
            log_type=LogType.BLACKWEREWOLFKING_SHOOT,
            message="Player 3 shoots Player 8!",
            source=black_king,
            target=target,
            camps=["All"],
        )
        hunter_shot = LogEntry(
            log_type=LogType.HUNTER_SHOOT,
            message="Player 7 shoots Player 8!",
            source=hunter,
            target=target,
            camps=["All"],
        )

        villager_ctrl.add_log(king_shot)
        villager_ctrl.add_log(hunter_shot)
        v_logs = villager_ctrl.get_logs()
        self.assertEqual(v_logs[0]["type"], "PLAYER_SHOOT")
        self.assertEqual(v_logs[1]["type"], "PLAYER_SHOOT")

        wolf_ctrl.add_log(king_shot)
        wolf_ctrl.add_log(hunter_shot)
        w_logs = wolf_ctrl.get_logs()
        self.assertEqual(w_logs[0]["type"], "BLACKWEREWOLFKING_SHOOT")
        self.assertEqual(w_logs[1]["type"], "HUNTER_SHOOT")

    def test_multiple_night_deaths_hide_reason_and_order_by_seat(self):
        from game.states.night_states import NightEndState
        from game.states.day_states import DayAnnouncementState

        p2 = self.game.players[1]  # Player 2
        p8 = self.game.players[7]  # Player 8

        # Suppose Player 8 is attacked by werewolves (with Guard+Save conflict) and Player 2 is poisoned by Witch
        self.game.night_kill_target = p8
        self.game.saved_this_night = p8
        self.game.protected_this_night = p8
        self.game.night_poison_target = p2

        night_end = NightEndState(self.game)
        night_end.handle()

        # Ensure no log entry reveals "conflicting magic" or poison publicly
        for entry in self.game.game_log:
            msg_str = str(entry.message)
            self.assertNotIn("conflicting magic", msg_str)
            self.assertNotIn("同守同救", msg_str)

        day_announce = DayAnnouncementState(self.game)
        day_announce.handle()

        # Eliminations must be announced and recorded in seat order (Player 2, then Player 8)
        elim_logs = [e for e in self.game.game_log if e.log_type == LogType.PLAYER_ELIMINATED]
        self.assertEqual([e.target.name for e in elim_logs], ["Player 2", "Player 8"])
        self.assertEqual([d["player"] for d in self.game.death], ["Player 2", "Player 8"])

    def test_game_history_enrichment_and_legacy_reconstruction(self):
        import tempfile
        import os
        from game.history import GameHistory

        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False, encoding="utf-8") as tmp:
            tmp_path = tmp.name
            tmp.write("[]")

        try:
            gh = GameHistory(storage_file=tmp_path)
            legacy_players = [
                {"name": "Player 1", "role": "Seer", "is_alive": True},
                {"name": "Player 2", "role": "Werewolf", "is_alive": False},
                {"name": "Player 3", "role": "Black Werewolf King", "is_alive": False},
            ]
            legacy_logs = [
                {
                    "type": "WEREWOLF_TARGET",
                    "message": {"en": "Wolves targeted Player 1", "zh": "狼人袭击了 Player 1"},
                    "source": "Player 2",
                    "target": "Player 1",
                    "data": {},
                    "camps": ["Werewolves"],
                    "round": 1,
                    "state": "WerewolfNightState",
                },
                {
                    "type": "SEER_CHECK",
                    "message": {"en": "Checked Player 2", "zh": "查验了 Player 2"},
                    "source": "Player 1",
                    "target": "Player 2",
                    "data": {"result": "Werewolf"},
                    "camps": ["Villagers"],
                    "round": 1,
                    "state": "SeerNightState",
                },
                {
                    "type": "SHERIFF_ELECTED",
                    "message": {"en": "Player 1 elected Sheriff", "zh": "Player 1 当选警长"},
                    "source": None,
                    "target": "Player 1",
                    "data": {},
                    "camps": ["All"],
                    "round": 1,
                    "state": "SheriffVoteState",
                },
                {
                    "type": "VOTE_RESULT",
                    "message": {"en": "Player 2 executed.", "zh": "Player 2 被放逐。"},
                    "source": None,
                    "target": None,
                    "data": {
                        "phase": "Execution Vote",
                        "votes": {"Player 2": ["Player 1", "Player 3"], "Abstained": ["Player 2"]},
                        "result": "Player 2",
                        "sheriff": "Player 1",
                    },
                    "camps": ["All"],
                    "round": 2,
                    "state": "VoteState",
                },
                {
                    "type": "PLAYER_ELIMINATED",
                    "message": {"en": "Player 2 eliminated", "zh": "Player 2 出局"},
                    "source": None,
                    "target": "Player 2",
                    "data": {},
                    "camps": ["All"],
                    "round": 2,
                    "state": "ExecutionState",
                },
            ]

            gid = gh.add_game(winner="Villagers", players=legacy_players, logs=legacy_logs)
            self.assertEqual(gid, 1)

            summaries = gh.get_history_summary()
            self.assertEqual(len(summaries), 1)
            self.assertEqual(summaries[0]["human_role"], "Seer")
            self.assertTrue(summaries[0]["human_won"])
            self.assertEqual(summaries[0]["rounds"], 2)

            detail = gh.get_game_details(1)
            self.assertIsNotNone(detail)
            assert detail is not None
            self.assertEqual(detail["human_role"], "Seer")
            self.assertTrue(detail["players"][0]["is_sheriff"])
            self.assertEqual(len(detail["votes"]), 1)
            self.assertEqual(detail["votes"][0]["votes"]["Player 1"], "Player 2")
            self.assertEqual(len(detail["deaths"]), 1)
            self.assertEqual(detail["deaths"][0]["player"], "Player 2")

            seer_ops = gh.reconstruct_player_operations(detail, "Player 1")
            self.assertEqual(seer_ops["role"], "Seer")
            self.assertEqual(len(seer_ops["checked"]), 1)
            self.assertEqual(seer_ops["checked"][0]["player"], "Player 2")
            self.assertEqual(seer_ops["checked"][0]["camp"], "Werewolves")

            wolf_ops = gh.reconstruct_player_operations(detail, "Player 2")
            self.assertEqual(wolf_ops["role"], "Werewolf")
            self.assertIn("Player 3", wolf_ops["teammates"])
            self.assertEqual(wolf_ops["king"], "Player 3")
            self.assertEqual(wolf_ops["kills"][0]["target"], "Player 1")
        finally:
            if os.path.exists(tmp_path):
                os.remove(tmp_path)

    def test_api_historical_game_endpoints_and_rehydration(self):
        from starlette.testclient import TestClient
        from web.server import app, game_history

        client = TestClient(app)
        res_list = client.get("/api/game/history")
        self.assertEqual(res_list.status_code, 200)
        hist_list = res_list.json().get("history", [])
        if hist_list:
            first_id = hist_list[0]["id"]
            res_detail = client.get(f"/api/game/history/{first_id}")
            self.assertEqual(res_detail.status_code, 200)
            detail = res_detail.json()
            self.assertEqual(detail["id"], first_id)
            self.assertIn("votes", detail)
            self.assertIn("deaths", detail)

            # Test rehydrated records, operations, and evaluation via history_<id>
            res_rec = client.get(f"/api/game/history_{first_id}/records")
            self.assertEqual(res_rec.status_code, 200)
            self.assertIn("votes", res_rec.json())

            res_ops = client.get(f"/api/game/history_{first_id}/player/Player 1/operations")
            self.assertEqual(res_ops.status_code, 200)
            self.assertIn("role", res_ops.json())

            res_eval = client.post(
                "/api/game/evaluate",
                json={"game_id": f"history_{first_id}", "mode": "mild", "language": "zh"},
            )
            self.assertEqual(res_eval.status_code, 200)
            self.assertIn("evaluation", res_eval.json())


if __name__ == "__main__":
    unittest.main()
