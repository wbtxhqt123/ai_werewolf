from game.game import Game
from game.controllers import HumanController
from llm_player.controller import LLMController

def setup_game(players_with_controllers: dict, player_role: str | None = None) -> Game:
    """Initializes and configures a new game instance.

    Args:
        players_with_controllers: A dictionary mapping player names to the
            controller instances that will manage them.
        player_role: An optional string specifying the desired role for a human
            player, if one is present in the game.

    Returns:
        A fully configured `Game` object, ready to be started.
    """
    return Game(players_with_controllers, player_role=player_role)

def main():
    """Sets up and runs a command-line game with LLM-powered players.

    This function configures a game with one human player and three AI players,
    each with a distinct personality, controlled by the `LLMController`.
    """
    players_with_controllers = {
        "Player 1": HumanController(),
        "Player 2": LLMController(personality="cautious", language="zh"),
        "Player 3": LLMController(personality="aggressive", language="zh"),
        "Player 4": LLMController(personality="analytical", language="zh"),
    }
    game = setup_game(players_with_controllers)
    game.start()

if __name__ == "__main__":
    main()