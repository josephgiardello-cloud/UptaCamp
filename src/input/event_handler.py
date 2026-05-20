"""Event handling logic.

Processes pygame events and translates them to game actions.
Initially acts as a facade, then contains direct implementations.
"""

from typing import Any, Dict


class EventHandler:
    """Processes pygame events and translates them to game actions.

    Events are captured and converted to action dictionaries that can be
    processed by GameController, enabling decoupling from pygame.
    """

    def __init__(self):
        """Initialize event handler."""
        self._last_actions: list[Dict[str, Any]] = []

    def poll_events(self) -> list[Dict[str, Any]]:
        """Poll pygame for events and convert to action dictionaries.

        Returns:
            List of action dictionaries. Each action has a 'type' key and
            action-specific data. Special action type 'QUIT' signals exit.
        """
        import pygame

        actions: list[Dict[str, Any]] = []
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                actions.append({"type": "QUIT", "raw_event": event})
            elif event.type == pygame.KEYDOWN:
                mapped = self.handle_keyboard(event.key, getattr(event, "mod", 0))
                if mapped is not None:
                    mapped["raw_event"] = event
                    actions.append(mapped)
                else:
                    actions.append(
                        {
                            "type": "KEYDOWN",
                            "key": event.key,
                            "mod": getattr(event, "mod", 0),
                            "raw_event": event,
                        }
                    )
            elif event.type == pygame.KEYUP:
                actions.append(
                    {
                        "type": "KEYUP",
                        "key": event.key,
                        "mod": getattr(event, "mod", 0),
                        "raw_event": event,
                    }
                )
            elif event.type == pygame.MOUSEBUTTONDOWN:
                mapped = self.handle_mouse_click(event.pos, event.button)
                if mapped is not None:
                    mapped["raw_event"] = event
                    actions.append(mapped)
                else:
                    actions.append(
                        {
                            "type": "MOUSEBUTTONDOWN",
                            "pos": event.pos,
                            "button": event.button,
                            "raw_event": event,
                        }
                    )
            elif event.type == pygame.MOUSEBUTTONUP:
                actions.append(
                    {
                        "type": "MOUSEBUTTONUP",
                        "pos": event.pos,
                        "button": event.button,
                        "raw_event": event,
                    }
                )
            elif event.type == pygame.MOUSEMOTION:
                actions.append(
                    {
                        "type": "MOUSEMOTION",
                        "pos": event.pos,
                        "rel": event.rel,
                        "buttons": event.buttons,
                        "raw_event": event,
                    }
                )
            elif event.type == pygame.TEXTINPUT:
                mapped = self.handle_settings_input(key=0, text=getattr(event, "text", ""))
                if mapped is not None:
                    mapped["raw_event"] = event
                    actions.append(mapped)
        self._last_actions = actions
        return actions

    def get_actions(self) -> list[Dict[str, Any]]:
        """Return the latest polled actions.

        This mirrors the migration-plan naming while preserving poll_events()
        as the primary API.
        """
        return self.poll_events()

    def handle_keyboard(self, key: int, modifiers: int = 0) -> Dict[str, Any] | None:
        """Handle keyboard event.

        Args:
            key: pygame key constant (e.g., pygame.K_F2)
            modifiers: pygame key modifiers (shift, ctrl, etc.)

        Returns:
            Action dict or None if key not handled
        """
        import pygame

        if key == pygame.K_F2:
            return {"type": "AI_LEVEL_CHANGE"}
        if key == pygame.K_s:
            return {"type": "SETTINGS_TOGGLE"}
        if key == pygame.K_r:
            return {"type": "RESET_HAND"}
        if key == pygame.K_o:
            return {"type": "ONLINE_MODE"}

        number_map = {
            pygame.K_1: 1,
            pygame.K_2: 2,
            pygame.K_3: 3,
            pygame.K_4: 4,
            pygame.K_5: 5,
            pygame.K_KP1: 1,
            pygame.K_KP2: 2,
            pygame.K_KP3: 3,
            pygame.K_KP4: 4,
            pygame.K_KP5: 5,
        }
        level = number_map.get(key)
        if level is not None:
            return {"type": "AI_LEVEL_SELECT", "level": level, "mod": modifiers}
        return None

    def handle_mouse_click(self, pos: tuple[int, int], button: int = 1) -> Dict[str, Any] | None:
        """Handle mouse click event.

        Args:
            pos: (x, y) click position
            button: mouse button (1=left, 2=middle, 3=right)

        Returns:
            Action dict or None if click not handled
        """
        if button != 1:
            return None
        return {"type": "MOUSEBUTTONDOWN", "pos": pos, "button": button}

    def handle_settings_input(self, key: int, text: str = "") -> Dict[str, Any] | None:
        """Handle input while settings modal is open.

        Args:
            key: pygame key constant
            text: text input (for text fields)

        Returns:
            Action dict or None
        """
        if text:
            return {"type": "SETTINGS_INPUT", "text": text}

        if key == 8:  # Backspace
            return {"type": "SETTINGS_BACKSPACE"}
        if key == 13:  # Enter
            return {"type": "SETTINGS_SUBMIT"}
        if key == 27:  # Escape
            return {"type": "SETTINGS_CANCEL"}
        return None

    def should_quit(self) -> bool:
        """Check if a quit event was received.

        Returns:
            True if QUIT event pending
        """
        import pygame

        try:
            return bool(pygame.event.peek(pygame.QUIT))
        except pygame.error:
            return False

    def handle_key_press(self, key: int) -> None:
        """Handle keyboard event.

        Args:
            key: pygame key constant
        """
        _ = key
