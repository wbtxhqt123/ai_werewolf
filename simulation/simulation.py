from __future__ import annotations
import random
import os
import datetime
import sys
import multiprocessing
from pathlib import Path
from typing import Any

# Add the project root to the Python path
project_root = Path(__file__).parent.parent
if str(project_root) not in sys.path:
    sys.path.append(str(project_root))

from game.game import Game
from game.controllers import Controller, RandomController
from game.player import Player, Werewolf, Witch, Seer, Guard, Hunter, BlackWerewolfKing
from game.log import LogEntry, LogType
from game.events.game_flow import PhaseChanged, GameOver
from game.events.day_events import PlayerDied


class RuleViolationError(AssertionError):
    """Raised when a game invariant or rule is violated during simulation."""
    pass


class RuleOracle:
    """Runtime model checker that verifies Werewolf game logic invariants at every phase and log entry."""

    def __init__(self, game: Game):
        self.game = game
        self.phase_history: list[tuple[int, str]] = []
        self.shots_fired_by: set[str] = set()
        self.witch_saves_used: int = 0
        self.witch_poisons_used: int = 0
        self.witch_actions_by_night: dict[int, list[str]] = {}
        self.guard_targets_by_night: dict[int, str | None] = {}
        self.game_over_count: int = 0
        self.badge_destroyed: bool = False

        # Track death chains (within a day announcement or execution chain) to verify:
        # 1. All shots happen before any last words in that chain
        # 2. Last words happen in exact reverse death order (c -> b -> a)
        self.current_chain_deaths: list[str] = []
        self.current_chain_last_words: list[str] = []
        self.in_last_words_phase_of_chain: bool = False

        game.event_bus.subscribe(PhaseChanged, self.on_phase_changed)
        game.event_bus.subscribe(PlayerDied, self.on_player_died)
        game.event_bus.subscribe(GameOver, self.on_game_over)
        game.add_log_listener(self.on_log)

    def _fail(self, msg: str):
        raise RuleViolationError(f"[Day {self.game.day}, State={getattr(self.game.state, 'name', None)}] {msg}")

    def on_player_died(self, event: PlayerDied):
        self.current_chain_deaths.append(event.player.name)

    def on_game_over(self, event: GameOver):
        self.game_over_count += 1
        if self.game_over_count > 1:
            self._fail(f"GameOver emitted multiple times ({self.game_over_count})")

        living = [p for p in self.game.players if p.is_alive]
        wolves = [p for p in living if isinstance(p.role, Werewolf)]
        living_plain_villagers = [p for p in living if type(p.role) is not Werewolf and getattr(p.role, "name", None) == "Villager"]
        living_gods = [
            p for p in living
            if p.role is not None and not isinstance(p.role, Werewolf) and getattr(p.role, "name", None) != "Villager"
        ]

        if event.winner == "Villagers":
            if len(wolves) != 0:
                self._fail(f"Villagers won but {len(wolves)} werewolves are still alive")
        elif event.winner == "Werewolves":
            if len(living_plain_villagers) > 0 and len(living_gods) > 0:
                self._fail(
                    f"Werewolves won prematurely: living_plain_villagers={len(living_plain_villagers)}, living_gods={len(living_gods)}"
                )

    def on_log(self, entry: LogEntry):
        # 1. Witch save & poison invariants
        if entry.log_type == LogType.WITCH_ACTION:
            action = entry.data.get("action")
            night = entry.day or self.game.day
            self.witch_actions_by_night.setdefault(night, []).append(action)
            if len(self.witch_actions_by_night[night]) > 1:
                self._fail(f"Witch used multiple potions on Night {night}: {self.witch_actions_by_night[night]}")
            if action == "save":
                self.witch_saves_used += 1
                if self.witch_saves_used > 1:
                    self._fail("Witch used save potion more than once")
                if entry.source and entry.target and entry.source == entry.target:
                    self._fail("Witch saved herself")
            elif action == "poison":
                self.witch_poisons_used += 1
                if self.witch_poisons_used > 1:
                    self._fail("Witch used poison potion more than once")

        # Witch should not see werewolf attack target once save potion is already used
        if entry.log_type == LogType.ACTION and entry.visible_to_roles and "Witch" in entry.visible_to_roles:
            en_msg = entry.get_text("en")
            if "This player was targeted by the werewolves:" in en_msg and self.witch_saves_used >= 1:
                self._fail("Witch was shown werewolf kill target after save potion was already consumed")

        # 2. Guard consecutive protection invariant
        if entry.log_type == LogType.GUARD_PROTECT:
            night = entry.day or self.game.day
            target_name = entry.target.name if entry.target else None
            prev_target = self.guard_targets_by_night.get(night - 1)
            if target_name and prev_target == target_name:
                self._fail(f"Guard protected {target_name} on consecutive nights ({night - 1} and {night})")
            self.guard_targets_by_night[night] = target_name

        # 3. Hunter / Black Werewolf King shooting invariants
        if entry.log_type in (LogType.HUNTER_SHOOT, LogType.BLACKWEREWOLFKING_SHOOT):
            shooter = entry.source
            if not shooter:
                self._fail("Shoot log missing source player")
            if not isinstance(shooter.role, (Hunter, BlackWerewolfKing)):
                self._fail(f"Non-shooter role {shooter.role} fired a shot")
            if shooter.death_reason == "poison":
                self._fail(f"{shooter.name} shot despite dying from poison")
            if shooter.name in self.shots_fired_by:
                self._fail(f"{shooter.name} fired more than one shot in the same game")
            self.shots_fired_by.add(shooter.name)
            if self.in_last_words_phase_of_chain:
                self._fail(
                    f"{shooter.name} fired a shot AFTER last words had already started in the current death chain"
                )

        # 4. Last words ordering invariant
        if entry.log_type == LogType.SPEECH and entry.source:
            en_msg = entry.get_text("en")
            if "last words):" in en_msg:
                self.in_last_words_phase_of_chain = True
                self.current_chain_last_words.append(entry.source.name)

        # 5. Badge destruction permanence
        if entry.log_type == LogType.SYSTEM and "destroyed the badge" in entry.get_text("en"):
            self.badge_destroyed = True

    def _verify_and_reset_death_chain(self):
        """Verifies that if multiple players left last words in a chain, they spoke in reverse death order (c -> b -> a)."""
        if len(self.current_chain_last_words) > 1:
            # Filter current_chain_deaths to those who gave last words
            speakers_set = set(self.current_chain_last_words)
            deaths_with_last_words = [p for p in self.current_chain_deaths if p in speakers_set]
            expected_reverse_order = list(reversed(deaths_with_last_words))
            if self.current_chain_last_words != expected_reverse_order:
                self._fail(
                    f"Last words order {self.current_chain_last_words} did not match reverse death order {expected_reverse_order} "
                    f"(death order was {self.current_chain_deaths})"
                )
        self.current_chain_deaths.clear()
        self.current_chain_last_words.clear()
        self.in_last_words_phase_of_chain = False

    def on_phase_changed(self, event: PhaseChanged):
        phase = event.phase_name
        day = event.day
        self.phase_history.append((day, phase))

        # Reset death chain tracking at boundaries between dawn and daytime execution
        if phase in ("night_begin", "sheriff_speech_order", "speech", "vote", "day_end"):
            self._verify_and_reset_death_chain()

        # Day 1 order invariant: sheriff_election must happen before day_announcement on Day 1
        if day == 1 and phase == "day_announcement":
            day1_phases = [p for d, p in self.phase_history if d == 1]
            if "sheriff_election" not in day1_phases:
                self._fail("Day 1 reached day_announcement before sheriff_election")

        # Status-flag hygiene invariants when entering speech, vote, or night_begin
        if phase in ("sheriff_speech_order", "speech", "vote", "night_begin"):
            candidates = [p.name for p in self.game.players if p.is_sheriff_candidate]
            if candidates:
                self._fail(f"is_sheriff_candidate flag leaked into {phase}: {candidates}")
            tied = [p.name for p in self.game.players if p.is_tie]
            if tied:
                self._fail(f"is_tie flag leaked into {phase}: {tied}")

        # Sheriff uniqueness & destroyed badge invariant
        sheriffs = [p for p in self.game.players if p.is_sheriff]
        if len(sheriffs) > 1:
            self._fail(f"Multiple players marked is_sheriff simultaneously: {[p.name for p in sheriffs]}")
        if self.badge_destroyed and (sheriffs or self.game.sheriff is not None):
            self._fail("Sheriff exists after badge was destroyed")

        # Active-play voting power invariant: if we enter daytime speech, game must not already be won
        if phase == "speech":
            winner = self.game.check_win_condition()
            if winner is not None:
                self._fail(f"Entered daytime speech when win condition '{winner}' was already met")


class SimulationController(RandomController):
    """A fast controller for running simulations without artificial sleep delays."""

    def __init__(self, language: str = "zh", rng: random.Random | None = None):
        super().__init__(language=language)
        self.rng = rng or random.Random()

    def _think(self):
        pass


class EdgeCaseController(SimulationController):
    """Controller configurable to force specific edge-case scenarios (ties, all-candidates, chain shots, etc.)."""

    def __init__(self, mode: str = "random", rng: random.Random | None = None):
        super().__init__(rng=rng)
        self.mode = mode

    def get_join_election_decision(self, player: Player) -> bool:
        if self.mode == "all_candidates":
            return True
        if self.mode == "no_candidates":
            return False
        if self.mode == "tie_cascade":
            return player.name in ("Player 1", "Player 2")
        return self.rng.choice([True, False, False])

    def get_vote_for_sheriff(self, player: Player, potential_targets: list[Player]) -> Player | None:
        if not potential_targets:
            return None
        if self.mode == "all_abstain":
            return None
        if self.mode == "tie_cascade" and len(potential_targets) >= 2:
            idx = int(player.name.replace("Player ", "")) % 2
            return potential_targets[idx]
        return self.rng.choice(potential_targets)

    def get_vote(self, player: Player, potential_targets: list[Player]) -> Player | None:
        if not potential_targets:
            return None
        if self.mode == "all_abstain":
            return None
        if self.mode == "chain_shot":
            # Prioritize voting out Hunter or Black Werewolf King to trigger daytime chained shots
            shooters = [p for p in potential_targets if isinstance(p.role, (Hunter, BlackWerewolfKing))]
            if shooters:
                return shooters[0]
        if self.mode == "tie_cascade" and len(potential_targets) >= 2:
            sorted_targets = sorted(potential_targets, key=lambda p: p.name)
            idx = int(player.name.replace("Player ", "")) % 2
            return sorted_targets[idx]
        return self.rng.choice(potential_targets)

    def get_hunter_shoot_target(self, player: Player, potential_targets: list[Player]) -> Player | None:
        if not potential_targets:
            return None
        if self.mode == "chain_shot":
            # Shoot the other shooter role first to trigger a chain (A -> B -> C)
            other_shooters = [p for p in potential_targets if isinstance(p.role, (Hunter, BlackWerewolfKing))]
            if other_shooters:
                return other_shooters[0]
        return self.rng.choice(potential_targets)


class SimulationGame(Game):
    """A subclass of `Game` tailored for running fast, oracle-verified simulations."""

    def __init__(
        self,
        players_with_controllers: dict[str, Controller],
        simulation_id: int,
        app=None,
        player_role: str | None = None,
        save_logs: bool = False,
        enable_oracle: bool = True,
    ):
        self.simulation_id = simulation_id
        self.save_logs = save_logs
        super().__init__(players_with_controllers, player_role)
        self.oracle = RuleOracle(self) if enable_oracle else None

    def _write_log_to_file(self):
        """Only writes logs to disk when explicitly requested (`save_logs=True`)."""
        if not self.save_logs:
            return
        now = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        pid = os.getpid()
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
                f.write("\n")


def setup_simulation_game(
    simulation_id: int,
    num_players: int | None = None,
    mode: str = "random",
    seed: int | None = None,
    save_logs: bool = False,
) -> SimulationGame:
    """Sets up a single game instance for a simulation run across standard 6, 9, and 12 player modes."""
    rng = random.Random(seed if seed is not None else simulation_id)
    if num_players is None:
        num_players = rng.choice([6, 9, 12])
    players_with_controllers: dict[str, Controller] = {
        f"Player {i+1}": EdgeCaseController(mode=mode, rng=rng) for i in range(num_players)
    }
    return SimulationGame(
        players_with_controllers,
        simulation_id=simulation_id,
        save_logs=save_logs,
        enable_oracle=True,
    )


def run_single_simulation(simulation_id: int, max_days: int = 25) -> dict[str, Any]:
    """Runs a single seeded game simulation with the RuleOracle and returns telemetry."""
    modes = ["random", "random", "random", "chain_shot", "all_candidates", "no_candidates", "tie_cascade"]
    mode = modes[simulation_id % len(modes)]
    num_players = [6, 9, 12][simulation_id % 3]

    game = setup_simulation_game(simulation_id, num_players=num_players, mode=mode, seed=simulation_id)
    game.event_bus.publish( PhaseChanged(phase_name="init", day=0) ) if False else None

    # Step through the state machine with a max_days guard to catch infinite loops
    from game.events.game_flow import GameStarted
    game.event_bus.publish(GameStarted(game=game))
    game.set_state("night_begin", day=game.day)

    steps = 0
    while game.state and game.running:
        steps += 1
        if game.day > max_days or steps > 500:
            # In all_abstain / tie_cascade modes, if no one dies during day votes, werewolves still kill at night;
            # exceeding max_days indicates a genuine progression bug.
            raise RuleViolationError(
                f"Simulation #{simulation_id} (mode={mode}, players={num_players}) exceeded max_days={max_days} / steps={steps}"
            )
        game.state.handle()
        next_state_name, next_state_kwargs = game.state.transition()
        if next_state_name:
            game.set_state(next_state_name, **(next_state_kwargs or {}))
        else:
            game.state = None

    if game.oracle:
        game.oracle._verify_and_reset_chain_if_needed = game.oracle._verify_and_reset_death_chain()

    return {
        "simulation_id": simulation_id,
        "num_players": num_players,
        "mode": mode,
        "winner": game.winner,
        "days": game.day,
        "deaths": len(game.death),
        "shots": len(game.oracle.shots_fired_by) if game.oracle else 0,
    }


def run_parallel_simulations(n: int = 200) -> dict[str, Any]:
    """Executes `n` simulations in parallel, verifying invariants and printing a summary report."""
    from tqdm import tqdm

    print(f"Running {n} oracle-verified game simulations in parallel...")
    with multiprocessing.Pool() as pool:
        results = list(
            tqdm(
                pool.imap_unordered(run_single_simulation, range(1, n + 1)),
                total=n,
                desc="Simulating Games",
            )
        )

    villager_wins = sum(1 for r in results if r["winner"] == "Villagers")
    werewolf_wins = sum(1 for r in results if r["winner"] == "Werewolves")
    avg_days = sum(r["days"] for r in results) / max(1, len(results))
    total_shots = sum(r["shots"] for r in results)

    summary = {
        "total_games": len(results),
        "villager_wins": villager_wins,
        "werewolf_wins": werewolf_wins,
        "avg_days": round(avg_days, 2),
        "total_shots": total_shots,
    }
    print(f"All {n} simulations passed RuleOracle checks! Summary: {summary}")
    return summary


if __name__ == "__main__":
    run_parallel_simulations(200)
