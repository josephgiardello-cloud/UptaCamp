import pygame
import argparse
import logging
from app_context import AppContext
from cribbage_engine import CribbageEngine
from asset_manager import AssetManager
from states.intro import IntroState

def _run_state_client(args):
    logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s [%(name)s] %(message)s')
    logger = logging.getLogger(__name__)

    pygame.init()
    screen = pygame.display.set_mode((1200, 800))
    clock = pygame.time.Clock()

    assets = AssetManager()
    engine = CribbageEngine()
    app = AppContext(
        server_url=args.online_url,
        ws_url=args.online_ws_url,
        volume=args.volume,
        animations_enabled=(args.animations != 'off'),
        preferred_online_ai_level=args.online_ai_level,
    )

    # Start in IntroState (state machine pattern)
    current_state = IntroState()
    running = True
    while running:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
            else:
                # State handles event and may return a new state
                try:
                    new_state = current_state.handle_event(event, engine, assets, app)
                    if new_state is not current_state:
                        if args.debug_play:
                            print(
                                f"[state] {current_state.__class__.__name__} -> {new_state.__class__.__name__} "
                                f"on event={pygame.event.event_name(event.type)}"
                            )
                        current_state = new_state
                except Exception as exc:
                    app.last_error = f"Input handling failed: {exc}"
                    logger.exception("state handle_event failed")

        # State updates logic (if needed)
        try:
            current_state.update(engine, clock.get_time(), app)
            # State draws itself
            current_state.draw(screen, engine, assets, app)
        except Exception as exc:
            app.last_error = f"Render/update failed: {exc}"
            logger.exception("state update/draw failed")
            screen.fill((20, 20, 20))
            font = pygame.font.SysFont(None, 30)
            msg = font.render(app.last_error, True, (220, 120, 120))
            screen.blit(msg, (40, 40))

        pygame.display.flip()
        clock.tick(60)


def main():
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument('--debug-play', action='store_true')
    parser.add_argument('--online-url', default='http://127.0.0.1:8787')
    parser.add_argument('--online-ws-url', default='ws://127.0.0.1:8790')
    parser.add_argument('--volume', type=float, default=0.6)
    parser.add_argument('--animations', choices=['on', 'off'], default='on')
    parser.add_argument('--online-ai-level', type=int, default=2)
    parser.add_argument(
        '--new-client',
        action='store_true',
        help='Run the new state-machine client (includes online UI). Default is classic gameplay client.',
    )
    args, _ = parser.parse_known_args()

    # Default path: classic gameplay renderer/loop that matches screenshot-era visuals and mechanics.
    if not args.new_client:
        import cribbage_pygame as classic_client

        return classic_client.main()

    return _run_state_client(args)


if __name__ == "__main__":
    main()
