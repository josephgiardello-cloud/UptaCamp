from abc import ABC, abstractmethod


class GameStateBase(ABC):
    @abstractmethod
    def handle_event(self, event, engine, assets, app):
        pass

    @abstractmethod
    def update(self, engine, dt: int, app):
        pass

    @abstractmethod
    def draw(self, screen, engine, assets, app):
        pass
