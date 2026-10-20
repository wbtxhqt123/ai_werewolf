from __future__ import annotations
from abc import ABC, abstractmethod
from typing import TYPE_CHECKING
from .log import LogEntry

if TYPE_CHECKING:
    from .controllers import Controller

class Role(ABC):
    """Defines the interface for a player's role in the game.

    Each role has a name, a description, and belongs to a camp (Villagers or Werewolves).
    The role determines the player's abilities and win conditions.
    """
    @property
    @abstractmethod
    def name(self) -> str:
        """The name of the role (e.g., 'Villager', 'Werewolf')."""
        pass

    @property
    @abstractmethod
    def description(self) -> str:
        """A brief description of the role's abilities and objectives."""
        pass

    @property
    @abstractmethod
    def camp(self) -> str:
        """The camp the role belongs to ('Villagers' or 'Werewolves')."""
        pass

    @property
    def name_zh(self) -> str:
        """The Chinese name of the role."""
        return self.name

    @property
    def description_zh(self) -> str:
        """The Chinese description of the role's abilities and objectives."""
        return self.description

class Villager(Role):
    """
    A simple villager with no special powers.
    """
    @property
    def name(self) -> str:
        return "Villager"

    @property
    def name_zh(self) -> str:
        return "村民"

    @property
    def description(self) -> str:
        return "Find and vote out the werewolves."

    @property
    def description_zh(self) -> str:
        return "在白天找出狼人并投票将其放逐。"

    @property
    def camp(self) -> str:
        return "Villagers"

class Werewolf(Role):
    """
    A werewolf who kills at night.
    """
    @property
    def name(self) -> str:
        return "Werewolf"

    @property
    def name_zh(self) -> str:
        return "狼人"

    @property
    def description(self) -> str:
        return "Work with other werewolves to kill villagers at night."

    @property
    def description_zh(self) -> str:
        return "每晚与其他狼人合作袭击村民，白天伪装成好人。"

    @property
    def camp(self) -> str:
        return "Werewolves"

    def kill(self, player: Player):
        """Marks a player to be killed."""
        # The game state will handle the actual killing
        # print(f"Werewolves are targeting {player.name}.")

class Witch(Role):
    """
    A witch who can save one person and poison one person.
    """
    def __init__(self):
        """Initializes the Witch with one save and one poison potion."""
        self.has_save = True
        self.has_poison = True

    @property
    def name(self) -> str:
        return "Witch"

    @property
    def name_zh(self) -> str:
        return "女巫"

    @property
    def description(self) -> str:
        return "You have a potion to save a life and a potion to take a life."

    @property
    def description_zh(self) -> str:
        return "拥有两瓶药：一瓶解药可以救人，一瓶毒药可以毒杀玩家。"

    @property
    def camp(self) -> str:
        return "Villagers"

    def save_player(self, player: Player):
        """Uses the save potion."""
        if self.has_save:
            self.has_save = False
            # print(f"The Witch is saving {player.name}.")
            return True
        return False

    def poison_player(self, player: Player):
        """Uses the poison potion."""
        if self.has_poison:
            self.has_poison = False
            # print(f"The Witch is poisoning {player.name}.")
            return True
        return False

class Seer(Role):
    """
    A seer who can check one person's identity at night.
    """
    @property
    def name(self) -> str:
        return "Seer"

    @property
    def name_zh(self) -> str:
        return "预言家"

    @property
    def description(self) -> str:
        return "You can check one player's identity each night to get their camp (Werewolf or Villager)."

    @property
    def description_zh(self) -> str:
        return "每晚可以查验一名玩家的身份，得知其所属阵营（好人阵营或狼人阵营）。"

    @property
    def camp(self) -> str:
        return "Villagers"

class Guard(Role):
    """
    A guard who can protect one person each night.
    """
    def __init__(self):
        """Initializes the Guard, tracking the last protected player."""
        self.last_protected: Player | None = None

    @property
    def name(self) -> str:
        return "Guard"

    @property
    def name_zh(self) -> str:
        return "守卫"

    @property
    def description(self) -> str:
        return "You can protect one player each night from being killed by werewolves. You cannot protect the same player two nights in a row."

    @property
    def description_zh(self) -> str:
        return "每晚可以守护一名玩家免受狼人袭击，不能连续两晚守护同一名玩家。"

    @property
    def camp(self) -> str:
        return "Villagers"

class Hunter(Role):
    """
    A hunter who can shoot someone when they die (unless poisoned).
    """
    @property
    def name(self) -> str:
        return "Hunter"

    @property
    def name_zh(self) -> str:
        return "猎人"

    @property
    def description(self) -> str:
        return "If you die (except by poison), you can shoot one player to take them with you."

    @property
    def description_zh(self) -> str:
        return "如果出局（被女巫毒死除外），可以开枪带走场上另一名玩家。"

    @property
    def camp(self) -> str:
        return "Villagers"

class BlackWerewolfKing(Werewolf):
    """
    A werewolf king who can shoot someone when they die (unless poisoned).
    """
    @property
    def name(self) -> str:
        return "Black Werewolf King"

    @property
    def name_zh(self) -> str:
        return "黑狼王"

    @property
    def description(self) -> str:
        return "You are a Werewolf. If you die (except by poison), you can shoot one player to take them with you."

    @property
    def description_zh(self) -> str:
        return "属于狼人阵营。如果出局（被女巫毒死除外），可以开枪带走场上另一名玩家。"

    @property
    def camp(self) -> str:
        return "Werewolves"

class Player:
    """Represents a player in the game, including their role, status, and actions.

    Each player has a name, a controller (which can be human or AI), an assigned role,
    and various status flags. The player object also stores logs and memory specific
    to them.
    """
    def __init__(self, name: str, controller: Controller):
        """Initializes a Player instance.

        Args:
            name: The unique name of the player.
            controller: The controller responsible for the player's decisions.
        """
        self.name = name
        self.controller = controller
        self.role: Role | None = None
        self.is_alive = True
        self.is_sheriff = False
        self.is_sheriff_candidate = False
        self.is_tie = False
        self.death_reason: str | None = None # "werewolf", "poison", "execution"
        self.logs: list[LogEntry] = []
        self.long_term_memory: str = ""

    def vote(self, player: Player):
        """Casts a vote to execute another player.

        Args:
            player: The player to vote for.
        """
        # The actual vote handling is done in the game state.
        pass