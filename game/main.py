from .game import Game
from .controllers import HumanController, RandomController
from .events.game_flow import GameStarted

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

def run_game():
    """Sets up and runs a standard command-line game.

    This function defines a default player configuration with one human player and
    three AI players, then starts the game loop.
    """
    players_with_controllers = {
        "Player 1 (AI)": RandomController(),
        "Player 2 (AI)": RandomController(),
        "Player 3 (AI)": RandomController(),
        "Player 4 (AI)": RandomController(),
    }
    game = setup_game(players_with_controllers)
    game.event_bus.publish(GameStarted())
    game.start()

if __name__ == "__main__":
    run_game()
