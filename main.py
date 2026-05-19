import pygame
import argparse
from cribbage_engine import CribbageEngine
from asset_manager import AssetManager
from states.intro import IntroState

def main():
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument('--debug-play', action='store_true')
    args, _ = parser.parse_known_args()

    pygame.init()
    screen = pygame.display.set_mode((1200, 800))
    clock = pygame.time.Clock()

    assets = AssetManager()
    engine = CribbageEngine()

    # Start in IntroState (state machine pattern)
    current_state = IntroState()
    running = True
    while running:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
            else:
                # State handles event and may return a new state
                new_state = current_state.handle_event(event, engine, assets)
                if new_state is not current_state:
                    if args.debug_play:
                        print(
                            f"[state] {current_state.__class__.__name__} -> {new_state.__class__.__name__} "
                            f"on event={pygame.event.event_name(event.type)}"
                        )
                    current_state = new_state

        # State updates logic (if needed)
        current_state.update(engine, clock.get_time())
        # State draws itself
        current_state.draw(screen, engine, assets)

        pygame.display.flip()
        clock.tick(60)

if __name__ == "__main__":
    main()
