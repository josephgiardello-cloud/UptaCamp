from abc import ABC, abstractmethod

class GameStateBase(ABC):
    @abstractmethod
    def handle_event(self, event, engine, assets):
        pass

    @abstractmethod
    def update(self, engine, dt: int):
        pass

    @abstractmethod
    def draw(self, screen, engine, assets):
        pass
