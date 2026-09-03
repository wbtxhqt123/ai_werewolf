import json
import os
from datetime import datetime
from typing import List, Dict, Any

class GameHistory:
    def __init__(self, storage_file: str = "game_history.json"):
        self.storage_file = storage_file
        self.history: List[Dict[str, Any]] = self._load_history()

    def _load_history(self) -> List[Dict[str, Any]]:
        if not os.path.exists(self.storage_file):
            return []
        try:
            with open(self.storage_file, "r", encoding="utf-8") as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError):
            return []

    def _save_history(self):
        try:
            with open(self.storage_file, "w", encoding="utf-8") as f:
                json.dump(self.history, f, ensure_ascii=False, indent=2)
        except IOError as e:
            print(f"Error saving game history: {e}")

    def add_game(self, winner: str, players: List[Dict[str, Any]], logs: List[Dict[str, Any]]):
        game_id = len(self.history) + 1
        timestamp = datetime.now().isoformat()
        
        game_record = {
            "id": game_id,
            "timestamp": timestamp,
            "winner": winner,
            "players": players,
            "logs": logs
        }
        
        self.history.insert(0, game_record) # Add to beginning
        self._save_history()
        return game_id

    def get_history_summary(self) -> List[Dict[str, Any]]:
        """Returns a list of game summaries (without full logs)"""
        return [
            {
                "id": game["id"],
                "timestamp": game["timestamp"],
                "winner": game["winner"],
                "player_count": len(game["players"])
            }
            for game in self.history
        ]

    def get_game_details(self, game_id: int) -> Dict[str, Any] | None:
        for game in self.history:
            if game["id"] == game_id:
                return game
        return None
