import random
import os
import datetime
import sys
import multiprocessing
from pathlib import Path
from tqdm import tqdm

# Add the project root to the Python path
project_root = Path(__file__).parent.parent
sys.path.append(str(project_root))

from game.game import Game
from game.controllers import RandomController

class SimulationController(RandomController):
    """A specialized `RandomController` for running simulations.

    This controller inherits from `RandomController` but overrides the `_think` method
    to remove the artificial delay. This allows simulations to run as fast as possible.
    """
    def _think(self):
        """Overrides the base method to eliminate the thinking delay."""
        pass # No more sleeping

class SimulationGame(Game):
    """A subclass of `Game` tailored for running simulations.

    This class overrides the logging mechanism to save game logs to a dedicated
    `simulation_log` directory, making it easier to analyze the results of multiple
    simulation runs.
    """
    def __init__(self, players_with_controllers: dict[str, 'Controller'], simulation_id: int, app=None, player_role: str | None = None):
        """Initializes a simulation game.

        Args:
            players_with_controllers: A dictionary mapping player names to controllers.
            simulation_id: A unique identifier for this simulation run.
            app: Unused parameter, kept for compatibility.
            player_role: The role for a human player, if any.
        """
        super().__init__(players_with_controllers, player_role)
        self.simulation_id = simulation_id

    def _write_log_to_file(self):
        """Overrides the default logging to write logs to a structured simulation directory.

        Each simulation log is saved in `simulation/simulation_log/<timestamp>/` with a
        unique filename incorporating the simulation ID and process ID.
        """
        now = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        pid = os.getpid()
        # Ensure the simulation_log directory exists
        root_dir = os.path.join("simulation", "simulation_log")
        os.makedirs(root_dir, exist_ok=True)
        log_dir = os.path.join(root_dir, now)
        os.makedirs(log_dir, exist_ok=True)
        filename = os.path.join(log_dir, f"game_log_sim{self.simulation_id}_pid{pid}.txt")
        with open(filename, "w", encoding="utf-8") as f:
            for i, entry in enumerate(self.game_log):
                f.write(f"--- Log Entry {i+1} ---\n")
                f.write(f"  Log Type: {entry.log_type.name}\n")
                f.write(f"  Message: {entry.message}\n")
                if entry.source:
                    f.write(f"  Source: {entry.source.name}\n")
                if entry.target:
                    f.write(f"  Target: {entry.target.name}\n")
                if entry.data:
                    f.write(f"  Data: {str(entry.data)}\n")
                if entry.visible_to_roles:
                    f.write(f"  Visible to Roles: {', '.join(entry.visible_to_roles)}\n")
                if entry.camps:
                    f.write(f"  Camps: {', '.join(entry.camps)}\n")
                if entry.visible_to_players:
                    player_names = [p.name for p in entry.visible_to_players]
                    f.write(f"  Visible to Players: {', '.join(player_names)}\n")
                f.write("\n")

def setup_simulation_game(simulation_id: int) -> SimulationGame:
    """Sets up a single game instance for a simulation run.

    It creates a game with a random number of players (between 5 and 10), all
    controlled by the fast `SimulationController`.

    Args:
        simulation_id: The unique ID for this simulation.

    Returns:
        A configured `SimulationGame` object.
    """
    num_players = random.randint(5, 10)
    players_with_controllers = {
        f"Player {i+1}": SimulationController() for i in range(num_players)
    }
    return SimulationGame(players_with_controllers, simulation_id=simulation_id)

def run_single_simulation(simulation_id: int):
    """Initializes and runs a single, complete game simulation.

    Args:
        simulation_id: The unique ID for this simulation run.
    """
    game = setup_simulation_game(simulation_id)
    game.start()

def run_parallel_simulations(n: int):
    """Executes a given number of simulations in parallel using multiple processes.

    This function leverages the `multiprocessing` module to distribute the simulation
    runs across available CPU cores, significantly speeding up the execution of large
    batches of simulations. A `tqdm` progress bar is used to visualize the progress.

    Args:
        n: The total number of simulations to run.
    """
    print(f"Running {n} game simulations in parallel...")
    with multiprocessing.Pool() as pool:
        # `imap_unordered` is used for efficiency, processing results as they complete.
        list(tqdm(pool.imap_unordered(run_single_simulation, range(1, n + 1)), total=n, desc="Simulating Games"))
    print("All simulations finished.")

if __name__ == "__main__":
    num_simulations = 1000
    run_parallel_simulations(num_simulations)