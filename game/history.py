from __future__ import annotations
import json
import os
from datetime import datetime
from typing import List, Dict, Any, Optional

WEREWOLF_ROLES = {"Werewolf", "Black Werewolf King"}


class GameHistory:
    def __init__(self, storage_file: str = "game_history.json"):
        self.storage_file = storage_file
        self.history: List[Dict[str, Any]] = self._load_history()

    def _load_history(self) -> List[Dict[str, Any]]:
        if not os.path.exists(self.storage_file):
            return []
        try:
            with open(self.storage_file, "r", encoding="utf-8") as f:
                data = json.load(f)
                return data if isinstance(data, list) else []
        except (json.JSONDecodeError, IOError):
            return []

    def _save_history(self):
        try:
            with open(self.storage_file, "w", encoding="utf-8") as f:
                json.dump(self.history, f, ensure_ascii=False, indent=2)
        except IOError as e:
            print(f"Error saving game history: {e}")

    @staticmethod
    def _compute_human_meta(winner: str, players: List[Dict[str, Any]]) -> tuple[str, bool]:
        human = (
            next((p for p in players if p.get("is_human")), None)
            or next((p for p in players if p.get("name") == "Player 1"), None)
        )
        if not human and players:
            human = players[0]
        human_role = (human.get("role") if human else None) or "Unknown"
        is_wolf = human_role in WEREWOLF_ROLES
        if winner == "Werewolves":
            human_won = is_wolf
        elif winner == "Villagers":
            human_won = not is_wolf and human_role != "Unknown"
        else:
            human_won = False
        return human_role, human_won

    @staticmethod
    def _compute_rounds(game: Dict[str, Any]) -> int:
        if isinstance(game.get("rounds"), int) and game["rounds"] > 0:
            return game["rounds"]
        max_round = 1
        for log in game.get("logs", []):
            r = log.get("day") or log.get("round") or 1
            if isinstance(r, int) and r > max_round:
                max_round = r
        return max_round

    def add_game(
        self,
        winner: str,
        players: List[Dict[str, Any]],
        logs: List[Dict[str, Any]],
        votes: Optional[List[Dict[str, Any]]] = None,
        deaths: Optional[List[Dict[str, Any]]] = None,
        rounds: Optional[int] = None,
    ) -> int:
        existing_ids = [
            int(g["id"])
            for g in self.history
            if isinstance(g.get("id"), (int, str)) and str(g.get("id")).isdigit()
        ]
        game_id = (max(existing_ids) + 1) if existing_ids else 1
        timestamp = datetime.now().isoformat()
        human_role, human_won = self._compute_human_meta(winner, players)

        computed_rounds = rounds
        if not computed_rounds:
            computed_rounds = max(
                (int(l.get("day") or l.get("round") or 1) for l in logs),
                default=1,
            )

        game_record: Dict[str, Any] = {
            "id": game_id,
            "timestamp": timestamp,
            "winner": winner,
            "human_role": human_role,
            "human_won": human_won,
            "rounds": computed_rounds,
            "players": players,
            "logs": logs,
        }
        if votes is not None:
            game_record["votes"] = votes
        if deaths is not None:
            game_record["deaths"] = deaths

        self.history.insert(0, game_record)  # Add to beginning (newest first)
        self._save_history()
        return game_id

    def get_history_summary(self) -> List[Dict[str, Any]]:
        """Returns a list of game summaries (without full logs)."""
        summaries = []
        for game in self.history:
            players = game.get("players", [])
            winner = game.get("winner", "")
            human_role = game.get("human_role")
            human_won = game.get("human_won")
            if not human_role or human_won is None:
                human_role, human_won = self._compute_human_meta(winner, players)
            rounds = self._compute_rounds(game)
            summaries.append({
                "id": game["id"],
                "timestamp": game.get("timestamp", ""),
                "winner": winner,
                "player_count": len(players),
                "human_role": human_role,
                "human_won": human_won,
                "rounds": rounds,
                "players": [
                    {
                        "name": p.get("name"),
                        "role": p.get("role", "Unknown"),
                        "is_alive": p.get("is_alive", False),
                    }
                    for p in players
                ],
            })
        return summaries

    def reconstruct_records(self, game: Dict[str, Any]) -> Dict[str, List[Dict[str, Any]]]:
        """Returns or reconstructs structured votes and deaths for a historical game."""
        votes = game.get("votes")
        deaths = game.get("deaths")
        logs = game.get("logs", [])

        if votes is None:
            reconstructed_votes = []
            for log in logs:
                if log.get("type") == "VOTE_RESULT" and isinstance(log.get("data"), dict):
                    data = log["data"]
                    raw_votes = data.get("votes") or {}
                    votes_by_voter: Dict[str, str] = {}
                    # VOTE_RESULT log data.votes maps {target: [voter1, voter2]}
                    for target_name, voter_list in raw_votes.items():
                        if isinstance(voter_list, list):
                            for voter in voter_list:
                                votes_by_voter[voter] = target_name
                        elif isinstance(voter_list, str):
                            # Already {voter: target}
                            votes_by_voter[target_name] = voter_list
                    reconstructed_votes.append({
                        "day": log.get("day") or log.get("round") or 1,
                        "phase": data.get("phase", "Execution Vote"),
                        "votes": votes_by_voter,
                        "result": data.get("result", "None"),
                        "sheriff": data.get("sheriff"),
                    })
            votes = reconstructed_votes

        if deaths is None:
            reconstructed_deaths = []
            seen_dead = set()
            for log in logs:
                ltype = log.get("type")
                day_num = log.get("day") or log.get("round") or 1
                state = log.get("state") or ""
                target = log.get("target")
                if ltype == "PLAYER_ELIMINATED" and target and target not in seen_dead:
                    seen_dead.add(target)
                    phase = "night" if state == "DayAnnouncementState" else "day"
                    reason = "night" if phase == "night" else "vote"
                    reconstructed_deaths.append({
                        "player": target,
                        "day": day_num,
                        "phase": phase,
                        "reason": reason,
                    })
                elif ltype in ("HUNTER_SHOOT", "BLACKWEREWOLFKING_SHOOT") and target and target not in seen_dead:
                    seen_dead.add(target)
                    reconstructed_deaths.append({
                        "player": target,
                        "day": day_num,
                        "phase": "day",
                        "reason": "hunter_shot" if ltype == "HUNTER_SHOOT" else "black_werewolf_king_shot",
                    })
            deaths = reconstructed_deaths

        return {"votes": votes, "deaths": deaths}

    def reconstruct_player_operations(
        self, game: Dict[str, Any], player_name: str = "Player 1"
    ) -> Dict[str, Any]:
        """Reconstructs role-specific operation history for any player in a historical game."""
        players = game.get("players", [])
        player_Map = {p.get("name"): p for p in players if p.get("name")}
        player = player_Map.get(player_name)
        if not player:
            return {}

        role_name = player.get("role") or "Villager"
        logs = game.get("logs", [])
        history: Dict[str, Any] = {"role": role_name}

        if role_name in WEREWOLF_ROLES:
            teammates = [
                p["name"]
                for p in players
                if p.get("role") in WEREWOLF_ROLES and p.get("name") != player_name
            ]
            kings = [
                p["name"]
                for p in players
                if p.get("role") == "Black Werewolf King"
            ]
            history["teammates"] = teammates
            history["king"] = kings[0] if kings else None

            kills = []
            for log in logs:
                if log.get("type") == "WEREWOLF_TARGET":
                    kills.append({
                        "night": log.get("day") or log.get("round") or 1,
                        "target": log.get("target"),
                    })
            history["kills"] = kills

        if role_name == "Witch":
            saved = []
            poisoned = []
            saved_details = []
            poisoned_details = []
            for log in logs:
                if log.get("type") == "WITCH_ACTION" and (log.get("source") in (player_name, None)):
                    target_name = log.get("target") or "no one"
                    night_num = log.get("day") or log.get("round") or 1
                    action = (log.get("data") or {}).get("action")
                    if action == "save":
                        saved.append(target_name)
                        saved_details.append({"night": night_num, "target": target_name})
                    elif action == "poison":
                        poisoned.append(target_name)
                        poisoned_details.append({"night": night_num, "target": target_name})
            history["saved"] = saved
            history["poisoned"] = poisoned
            history["saved_details"] = saved_details
            history["poisoned_details"] = poisoned_details

        if role_name == "Seer":
            checked = []
            for log in logs:
                if log.get("type") == "SEER_CHECK" and (log.get("source") in (player_name, None)):
                    target_name = log.get("target")
                    if target_name:
                        target_role = (player_Map.get(target_name) or {}).get("role", "Villager")
                        result_raw = (log.get("data") or {}).get("result")
                        is_wolf = (result_raw in ("Werewolf", "Werewolves")) or (target_role in WEREWOLF_ROLES)
                        checked.append({
                            "night": log.get("day") or log.get("round") or 1,
                            "player": target_name,
                            "camp": "Werewolves" if is_wolf else "Villagers",
                        })
            history["checked"] = checked

        if role_name == "Guard":
            protected = []
            protected_details = []
            for log in logs:
                if log.get("type") == "GUARD_PROTECT" and (log.get("source") in (player_name, None)):
                    target_name = log.get("target")
                    if target_name:
                        protected.append(target_name)
                        protected_details.append({
                            "night": log.get("day") or log.get("round") or 1,
                            "target": target_name,
                        })
            history["protected"] = protected
            history["protected_details"] = protected_details

        if role_name in ("Hunter", "Black Werewolf King"):
            shot = []
            shot_details = []
            target_log_type = "HUNTER_SHOOT" if role_name == "Hunter" else "BLACKWEREWOLFKING_SHOOT"
            for log in logs:
                if log.get("type") == target_log_type and log.get("source") == player_name:
                    target_name = log.get("target")
                    if target_name:
                        day_num = log.get("day") or log.get("round") or 1
                        shot.append(target_name)
                        shot_details.append({"day": day_num, "target": target_name})
            history["shot"] = shot
            history["shot_details"] = shot_details

        public_shots = []
        for log in logs:
            if log.get("type") in ("HUNTER_SHOOT", "BLACKWEREWOLFKING_SHOOT"):
                public_shots.append({
                    "day": log.get("day") or log.get("round") or 1,
                    "shooter": log.get("source") or "Unknown",
                    "role": "Hunter" if log.get("type") == "HUNTER_SHOOT" else "Black Werewolf King",
                    "target": log.get("target") or "no one",
                })
        history["public_shots"] = public_shots

        return history

    def get_game_details(self, game_id: int) -> Dict[str, Any] | None:
        for game in self.history:
            if game.get("id") == game_id:
                players = game.get("players", [])
                logs = game.get("logs", [])
                winner = game.get("winner", "")
                human_role, human_won = self._compute_human_meta(winner, players)
                rounds = self._compute_rounds(game)

                # Infer final sheriff if not explicitly stored on player dicts
                last_sheriff = None
                for log in logs:
                    if log.get("type") == "SHERIFF_ELECTED" and log.get("target"):
                        last_sheriff = log.get("target")

                normalized_players = []
                for p in players:
                    p_copy = dict(p)
                    if "is_sheriff" not in p_copy:
                        p_copy["is_sheriff"] = bool(last_sheriff and p_copy.get("name") == last_sheriff)
                    normalized_players.append(p_copy)

                normalized_logs = []
                for idx, log in enumerate(logs):
                    l_copy = dict(log)
                    day_val = l_copy.get("day") or l_copy.get("round") or 1
                    l_copy["day"] = day_val
                    l_copy["round"] = day_val
                    if "id" not in l_copy:
                        l_copy["id"] = idx
                    normalized_logs.append(l_copy)

                records = self.reconstruct_records(game)

                return {
                    **game,
                    "human_role": human_role,
                    "human_won": human_won,
                    "rounds": rounds,
                    "players": normalized_players,
                    "logs": normalized_logs,
                    "votes": records["votes"],
                    "deaths": records["deaths"],
                }
        return None

