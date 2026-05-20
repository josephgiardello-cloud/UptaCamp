"""Game controller and application state management.

This module contains extracted game-loop orchestration logic while still
delegating to the legacy compatibility module during migration.
"""

from __future__ import annotations

from typing import Any

from src.input import EventHandler
from src.renderer import BoardRenderer, RenderingContext


class GameController:
    """Orchestrates game logic and updates."""

    def __init__(self, engine: Any, legacy_module: Any | None = None):
        """Initialize game controller.

        Args:
            engine: CribbageEngine instance
            legacy_module: Optional cribbage_pygame-like module for migration
        """
        self.engine = engine
        self._legacy = legacy_module

    def _get_legacy_module(self) -> Any:
        """Resolve and cache the legacy compatibility module."""
        if self._legacy is None:
            import cribbage_pygame as legacy_module

            self._legacy = legacy_module
        return self._legacy

    def _current_phase(self) -> str:
        """Get the current game phase from legacy state."""
        legacy = self._get_legacy_module()
        session = getattr(legacy, "_CLASSIC_SESSION", None)
        if session is not None and hasattr(session, "phase"):
            return str(session.phase)
        return str(getattr(legacy, "game_phase", "intro"))

    def handle_discard(self, event: Any) -> None:
        """Run discard-phase handler for a single event."""
        self._get_legacy_module().handle_discard(event)

    def handle_pegging(self, event: Any | None = None, *, auto_player: bool = False) -> None:
        """Run pegging-phase handler for a single event or auto-tick."""
        self._get_legacy_module().handle_pegging(event, auto_player=auto_player)

    def handle_counting(self) -> None:
        """Run counting-phase handler."""
        self._get_legacy_module().handle_counting()

    def transition_phase(self, target_phase: str, *, force: bool = False) -> None:
        """Transition to a target phase using legacy transition logic."""
        self._get_legacy_module()._transition_phase(target_phase, force=force)

    def check_for_winner(self) -> int | None:
        """Evaluate and return winner index if any."""
        return self._get_legacy_module()._check_for_winner()

    def update(self, *, auto_player: bool = False) -> None:
        """Update game state for current frame.

        During migration, this orchestrates phase-specific legacy handlers.
        """
        phase = self._current_phase()
        if phase == "pegging":
            self.handle_pegging(None, auto_player=auto_player)
        elif phase == "counting":
            self.handle_counting()

    def handle_action(self, action_type: str, action_data: Any) -> None:
        """Handle a player action.

        Args:
            action_type: Type of action ("discard", "pegging", etc.)
            action_data: Action-specific data
        """
        if action_type == "discard":
            self.handle_discard(action_data)
            return
        if action_type == "pegging":
            self.handle_pegging(action_data)
            return
        if action_type == "counting":
            self.handle_counting()
            return
        if action_type == "transition":
            payload = action_data if isinstance(action_data, dict) else {}
            target_phase = str(payload.get("phase", ""))
            if not target_phase:
                raise ValueError("transition action requires a non-empty 'phase'")
            self.transition_phase(target_phase, force=bool(payload.get("force", False)))
            return
        if action_type == "check_winner":
            self.check_for_winner()
            return

        raise ValueError(f"Unsupported action_type: {action_type}")

    def process(self, actions: list[dict[str, Any]]) -> None:
        """Process normalized input actions.

        UI-level pygame events are routed by current phase to preserve legacy
        behavior during migration.
        """
        for action in actions:
            action_type = str(action.get("type", "")).lower()
            if not action_type or action_type == "quit":
                continue

            if action_type in {"discard", "pegging", "counting", "transition", "check_winner"}:
                self.handle_action(action_type, action)
                continue

            if action_type in {"mousedown", "mousebuttondown", "mousebuttonup", "mousemove", "mousemotion"}:
                phase = self._current_phase()
                if phase == "discard":
                    self.handle_discard(action)
                elif phase == "pegging":
                    self.handle_pegging(action)
                continue

            if action_type in {"keydown", "keyup", "ai_level_change", "settings_toggle", "reset_hand", "online_mode", "ai_level_select", "settings_input", "settings_backspace", "settings_submit", "settings_cancel"}:
                legacy = self._get_legacy_module()
                key_value = action.get("key")
                if hasattr(legacy, "handle_key_press") and key_value is not None:
                    legacy.handle_key_press(key_value)
                continue


class GameApplication:
    """Encapsulates application state and manages component lifecycle.

    Consolidates global state into a single application object,
    replacing module-level globals with instance attributes.
    """

    def __init__(self):
        """Initialize game application with all components."""
        # Core game logic
        self.engine: Any = None
        self.game_state: Any = None

        # Rendering
        self.screen: Any = None
        self.clock: Any = None
        self.assets: Any = None
        self.rendering_context: RenderingContext | None = None
        self.renderer: BoardRenderer | None = None

        # Controllers and handlers
        self.game_controller: GameController | None = None
        self.event_handler: EventHandler | None = None

        # Settings and state
        self.settings: Any = None
        self.player_name: str = "Player"
        self.ui_style: str = "classic"
        self.running: bool = False

    def initialize(self, width: int = 1920, height: int = 1080) -> None:
        """Initialize all application components.

        Args:
            width: Display width (default 1920)
            height: Display height (default 1080)
        """
        # TODO: Initialize pygame, load assets, create engine, etc.
        if self.screen and self.assets:
            self.rendering_context = RenderingContext(
                screen=self.screen,
                assets=self.assets,
                ui_style=self.ui_style,
            )
            self.renderer = BoardRenderer(self.rendering_context)
        # Initialize event handler (doesn't need screen, just processes pygame events)
        self.event_handler = EventHandler()

    def handle_input(self) -> bool:
        """Process input events.

        Returns:
            False if quit requested, True otherwise
        """
        if not self.event_handler:
            return True
        if self.event_handler.should_quit():
            return False
        actions = self.event_handler.get_actions()
        if self.game_controller:
            self.game_controller.process(actions)
        for action in actions:
            action_type = str(action.get("type", "")).lower()
            if action_type == "quit":
                return False
        return True

    def update(self) -> None:
        """Update application state for current frame."""
        if self.game_controller:
            self.game_controller.update()
        if self.rendering_context:
            self.rendering_context.update_size()

    def render(self) -> None:
        """Render current frame."""
        if self.renderer and self.game_state:
            self.renderer.draw_board(self.game_state)
            self.renderer.finalize_frame()

    def shutdown(self) -> None:
        """Clean up and shutdown application."""
        # TODO: Save state, close resources
        self.running = False

    @property
    def is_running(self) -> bool:
        """Check if application is running."""
        return self.running
