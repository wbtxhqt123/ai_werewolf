from __future__ import annotations
from abc import ABC, abstractmethod
import time
import random
from typing import TYPE_CHECKING, Any
import threading

if TYPE_CHECKING:
    from .player import Player
    from .game import Game

class Controller(ABC):
    """Defines the interface for controlling a player's actions.

    This abstract class provides a set of methods that game states can call to get a
    player's decision for various actions, such as speaking, voting, or using a role's
    special ability. Implementations can range from human input to AI-driven logic.
    """
    game: Game
    is_human: bool = False

    @abstractmethod
    def get_speech(self, player: Player) -> str:
        """Called when the player needs to make a speech.

        Args:
            player: The player who is speaking.

        Returns:
            The speech content as a string.
        """
        pass

    @abstractmethod
    def get_vote(self, player: Player, potential_targets: list[Player]) -> Player | None:
        """Called when the player needs to vote to execute another player.

        Args:
            player: The player who is voting.
            potential_targets: A list of players who can be voted for.

        Returns:
            The player to be executed, or None to abstain.
        """
        pass

    @abstractmethod
    def get_werewolf_target(self, player: Player, potential_targets: list[Player]) -> Player | None:
        """Called when a Werewolf needs to choose a target to kill.

        Args:
            player: The Werewolf player choosing the target.
            potential_targets: A list of players who can be targeted.

        Returns:
            The player to be killed, or None to abstain.
        """
        pass
    
    @abstractmethod
    def get_witch_save_decision(self, player: Player, target: Player) -> bool:
        """Called when the Witch must decide whether to use their save potion.

        Args:
            player: The Witch player.
            target: The player who was attacked by werewolves.

        Returns:
            True to save the player, False otherwise.
        """
        pass

    @abstractmethod
    def get_witch_poison_target(self, player: Player, potential_targets: list[Player]) -> Player | None:
        """Called when the Witch can use their poison potion.

        Args:
            player: The Witch player.
            potential_targets: A list of players who can be poisoned.

        Returns:
            The player to be poisoned, or None to abstain.
        """
        pass

    @abstractmethod
    def get_vote_for_sheriff(self, player: Player, potential_targets: list[Player]) -> Player | None:
        """Called when the player needs to vote for a Sheriff.

        Args:
            player: The player who is voting.
            potential_targets: A list of candidates for Sheriff.

        Returns:
            The chosen candidate, or None to abstain.
        """
        pass

    @abstractmethod
    def get_join_election_decision(self, player: Player) -> bool:
        """Called when the player can decide to run for Sheriff.

        Args:
            player: The player making the decision.

        Returns:
            True to run for Sheriff, False otherwise.
        """
        pass

    @abstractmethod
    def get_seer_target(self, player: Player, potential_targets: list[Player]) -> Player | None:
        """Called when the Seer needs to choose a player to check.

        Args:
            player: The Seer player.
            potential_targets: A list of players who can be checked.

        Returns:
            The player to be checked, or None to abstain.
        """
        pass

    @abstractmethod
    def get_guard_protect(self, player: Player, potential_targets: list[Player]) -> Player | None:
        """Called when the Guard needs to choose a player to protect.

        Args:
            player: The Guard player.
            potential_targets: A list of players who can be protected.

        Returns:
            The player to be protected, or None to abstain.
        """
        pass

    @abstractmethod
    def get_hunter_shoot_target(self, player: Player, potential_targets: list[Player]) -> Player | None:
        """Called when the Hunter dies and must choose a player to shoot.

        Args:
            player: The Hunter player.
            potential_targets: A list of players who can be shot.

        Returns:
            The player to be shot, or None to abstain.
        """
        pass

    @abstractmethod
    def get_speech_order_decision(self, player: Player) -> str:
        """Called when the Sheriff must decide the speech order.

        Args:
            player: The Sheriff player.

        Returns:
            'clockwise' or 'counter_clockwise'.
        """
        pass

    @abstractmethod
    def get_sheriff_death_decision(self, player: Player, potential_targets: list[Player]) -> Player | None:
        """Called when the Sheriff dies and must pass the badge.

        Args:
            player: The deceased Sheriff player.
            potential_targets: A list of players who can receive the badge.

        Returns:
            The player to receive the badge, or None to destroy it.
        """
        pass

    def get_sheriff_withdraw_decision(self, player: Player) -> bool:
        """Called when a Sheriff candidate can decide whether to withdraw (退水) after campaign speeches.

        Args:
            player: The candidate player making the decision.

        Returns:
            True to withdraw from the Sheriff election, False to stay in the race.
        """
        return False

class HumanController(Controller):
    """A controller that allows a human to play via the command line.

    This controller prompts the user for input for each decision point in the game.
    It is marked as human, which can be used for special handling in the game logic.
    """
    is_human = True

    def get_speech(self, player: Player) -> str:
        from .utils import get_text_input
        return get_text_input(f"{player.name}, it's your turn to speak.")

    def get_vote(self, player: Player, potential_targets: list[Player]) -> Player | None:
        from .utils import get_player_choice
        print(f"\n{player.name}, it's your turn to vote.")
        return get_player_choice("Who do you vote to execute?", potential_targets, allow_abstain=True)

    def get_werewolf_target(self, player: Player, potential_targets: list[Player]) -> Player | None:
        from .utils import get_player_choice
        print(f"\n{player.name}, you will choose the target.")
        return get_player_choice("Choose a player to eliminate:", potential_targets)

    def get_witch_save_decision(self, player: Player, target: Player) -> bool:
        from .utils import get_yes_no_choice
        return get_yes_no_choice(f"Do you want to use your save potion on {target.name}?")

    def get_witch_poison_target(self, player: Player, potential_targets: list[Player]) -> Player | None:
        from .utils import get_player_choice, get_yes_no_choice
        if get_yes_no_choice("Do you want to use your poison potion tonight?"):
            return get_player_choice("Choose a player to poison:", potential_targets)
        return None

    def get_vote_for_sheriff(self, player: Player, potential_targets: list[Player]) -> Player | None:
        from .utils import get_player_choice
        print(f"\n{player.name}, it's your turn to vote for sheriff.")
        return get_player_choice("Who do you vote for to be sheriff?", potential_targets)

    def get_join_election_decision(self, player: Player) -> bool:
        from .utils import get_yes_no_choice
        return get_yes_no_choice(f"{player.name}, do you want to run for sheriff?")

    def get_seer_target(self, player: Player, potential_targets: list[Player]) -> Player | None:
        from .utils import get_player_choice
        print(f"\n{player.name}, you will choose a player to check.")
        return get_player_choice("Choose a player to check their identity:", potential_targets)

    def get_guard_protect(self, player: Player, potential_targets: list[Player]) -> Player | None:
        from .utils import get_player_choice
        print(f"\n{player.name}, you will choose a player to protect.")
        return get_player_choice("Choose a player to protect:", potential_targets, allow_abstain=True)

    def get_hunter_shoot_target(self, player: Player, potential_targets: list[Player]) -> Player | None:
        from .utils import get_player_choice
        print(f"\n{player.name}, you have died. You can shoot someone.")
        return get_player_choice("Choose a player to shoot:", potential_targets, allow_abstain=True)

    def get_speech_order_decision(self, player: Player) -> str:
        print(f"\n{player.name}, you are the Sheriff. Please decide the speech order.")
        while True:
            choice = input("Choose speech order (1: Clockwise, 2: Counter-clockwise): ").strip()
            if choice == "1":
                return "clockwise"
            elif choice == "2":
                return "counter_clockwise"
            print("Invalid choice. Please enter 1 or 2.")

    def get_sheriff_death_decision(self, player: Player, potential_targets: list[Player]) -> Player | None:
        from .utils import get_player_choice
        print(f"\n{player.name}, you have died and must decide what to do with the Sheriff badge.")
        return get_player_choice("Choose a player to pass the badge to (or abstain to destroy it):", potential_targets, allow_abstain=True)

    def get_sheriff_withdraw_decision(self, player: Player) -> bool:
        from .utils import get_yes_no_choice
        return get_yes_no_choice(f"{player.name}, do you want to withdraw from the Sheriff election (退水)?")

class RandomController(Controller):
    """A controller for an AI player that makes purely random decisions.

    This controller simulates a basic AI by choosing actions randomly from the available
    options. It includes a simulated "thinking" time to make the AI's actions feel
    more natural.
    """

    def __init__(self, language: str = "zh"):
        self.language = language

    def _think(self):
        """Simulates a short delay to make the AI's actions less instantaneous."""
        think_time = random.uniform(1, 3)
        print(f"AI is thinking for {think_time:.1f} seconds...")
        time.sleep(think_time)

    def get_speech(self, player: Player) -> str:
        self._think()
        lang = getattr(self, "language", "zh")
        if hasattr(self, "game") and getattr(self.game, "language", None):
            lang = self.game.language
        if lang == "en":
            return "I am an AI player. I'm trying to find the werewolves."
        return "我是AI玩家。我在努力寻找狼人。"

    def get_vote(self, player: Player, potential_targets: list[Player]) -> Player | None:
        self._think()
        if not potential_targets:
            return None
        return random.choice(potential_targets)

    def get_werewolf_target(self, player: Player, potential_targets: list[Player]) -> Player | None:
        self._think()
        if not potential_targets:
            return None
        return random.choice(potential_targets)

    def get_witch_save_decision(self, player: Player, target: Player) -> bool:
        self._think()
        # The AI has a 50% chance of using the save potion.
        return random.choice([True, False])

    def get_witch_poison_target(self, player: Player, potential_targets: list[Player]) -> Player | None:
        self._think()
        # The AI has a 50% chance of using the poison potion.
        if random.choice([True, False]) and potential_targets:
            return random.choice(potential_targets)
        return None

    def get_vote_for_sheriff(self, player: Player, potential_targets: list[Player]) -> Player | None:
        self._think()
        if not potential_targets:
            return None
        # The AI has a 50% chance of abstaining from the vote.
        if random.choice([True, False]):
            return random.choice(potential_targets)
        return None

    def get_join_election_decision(self, player: Player) -> bool:
        self._think()
        # The AI has a 33% chance of running for Sheriff.
        return random.choice([True, False, False])

    def get_seer_target(self, player: Player, potential_targets: list[Player]) -> Player | None:
        self._think()
        if not potential_targets:
            return None
        return random.choice(potential_targets)

    def get_guard_protect(self, player: Player, potential_targets: list[Player]) -> Player | None:
        self._think()
        if not potential_targets:
            return None
        # The AI has an 80% chance of protecting a random player.
        if random.random() < 0.8:
            return random.choice(potential_targets)
        return None

    def get_hunter_shoot_target(self, player: Player, potential_targets: list[Player]) -> Player | None:
        self._think()
        if not potential_targets:
            return None
        # The AI will always shoot a random player if possible.
        return random.choice(potential_targets)

    def get_speech_order_decision(self, player: Player) -> str:
        self._think()
        return random.choice(["clockwise", "counter_clockwise"])

    def get_sheriff_death_decision(self, player: Player, potential_targets: list[Player]) -> Player | None:
        self._think()
        if not potential_targets:
            return None
        # The AI has an 80% chance of passing the badge and a 20% chance of destroying it.
        if random.random() < 0.8:
            return random.choice(potential_targets)
        return None

class SafeController(Controller):
    """A controller that consistently makes safe or passive decisions.

    This controller is designed to be non-disruptive and predictable. It will typically
    abstain from actions, refuse to use items, and provide minimal speech. It can be
    useful for testing or as a fallback to prevent errors.
    """

    def get_speech(self, player: Player) -> str:
        return "..."

    def get_vote(self, player: Player, potential_targets: list[Player]) -> Player | None:
        return None  # Abstain

    def get_werewolf_target(self, player: Player, potential_targets: list[Player]) -> Player | None:
        # Werewolves must kill if possible, but safe fallback might be random or None (no kill)
        # If we return None, it means "no kill" which is a valid strategy but maybe not "safe" for the werewolf team.
        # However, for a "Safe" controller intended to prevent crashes, returning None is safest.
        return None

    def get_witch_save_decision(self, player: Player, target: Player) -> bool:
        return False

    def get_witch_poison_target(self, player: Player, potential_targets: list[Player]) -> Player | None:
        return None

    def get_vote_for_sheriff(self, player: Player, potential_targets: list[Player]) -> Player | None:
        return None

    def get_join_election_decision(self, player: Player) -> bool:
        return False

    def get_seer_target(self, player: Player, potential_targets: list[Player]) -> Player | None:
        return None

    def get_guard_protect(self, player: Player, potential_targets: list[Player]) -> Player | None:
        return None

    def get_hunter_shoot_target(self, player: Player, potential_targets: list[Player]) -> Player | None:
        return None

    def get_speech_order_decision(self, player: Player) -> str:
        return "clockwise"

    def get_sheriff_death_decision(self, player: Player, potential_targets: list[Player]) -> Player | None:
        return None  # Destroy badge by default
