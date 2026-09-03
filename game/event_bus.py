from collections import defaultdict
from typing import Callable, Type

from game.events.base import Event

class EventBus:
    def __init__(self):
        self.listeners: dict[Type[Event], list[Callable]] = defaultdict(list)

    def subscribe(self, event_type: Type[Event], callback: Callable):
        self.listeners[event_type].append(callback)

    def publish(self, event: Event):
        for callback in self.listeners[type(event)]:
            callback(event)
