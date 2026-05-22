# Plan Alignment Status (May 21, 2026)

This file tracks alignment against the requested implementation plan.

## 1. Architecture & Code Organization

- [x] 1.1 God Object split started (`src/renderer`, `src/input`, `src/controllers`, `src/utils` exist)
- [x] 1.1 Main runtime loop migration is complete for the primary entrypoint
  - Current: `main.py` runs the state-driven runtime path as the default and supported launch path.
  - Current: deprecated `--classic-client` flag has been removed from the CLI surface.
  - Current: event/action flow routes through `EventHandler.get_actions()` + `GameController.process(actions)`.
  - Current: legacy compatibility file retirement is complete (`cribbage_pygame.py` removed).
- [x] 1.2 Mixed state management baseline (`CribbageEngine.state` is primary state model)
- [x] 1.2 Debug validation method exists and now runs after key mutating engine methods
- [x] 1.3 Global variables encapsulation (runtime-scoped)
  - Current: classic runtime loop now flows through `GameApplication` fields for controller, event handler, running state, and settings/name/style sync.
- [x] 1.4 Dependency injection baseline
  - Added `CribbageEngine.ai_discard(strategy=None)` for injectable strategy in tests

## 2. Bert Learning AI

- [x] 2.1 Q-learning update API exists in `bert_agent.py`
- [~] 2.1 Runtime update wiring is partial
  - Current: end-of-hand learning update is wired in `engine.count_hands` for level 5
  - Remaining: per-pegging-step transition updates and terminal game reward update wiring
- [~] 2.2 State-vector and DQN scaffolding exists
  - Current: vector encoder + DQN wrapper present in `bert_agent.py`
  - Remaining: full replay-buffer training loop integrated with runtime/agent policy
- [~] 2.3 Training loop exists (`train_bert.py`) but is synthetic/headless sampling
  - Remaining: full engine-driven `step()` loop for complete episode simulation
- [~] 2.4 Reward shaping partially present
  - Current: end-of-hand reward and pegging sample reward functions
  - Remaining: standardized reward function integrated in runtime decision pipeline

## 3. Online Multiplayer

- [x] 3.1 Backend evidence exists (`online_api_server.py`, `online_ws_server.py`, `online_backend.py`, tests)
- [~] 3.2 Turn validation maturity
  - Current: backend + tests exist
  - Remaining: verify server-authoritative move validation model against full production checklist

## 4. Performance & Resource Usage

- [x] 4.1 Frame/animation migration baseline is complete
  - Current: `src/renderer/animation_manager.py` is now a concrete manager with keyed animation lifecycle and compatibility delegation for card flights/popups/shake.
- [~] 4.2 AI lag mitigation is partial (timeouts/fallbacks exist in strategy)
- [x] 4.3 Asset preloading/caching baseline is complete
  - Current: `src/utils/asset_loader.py` now provides concrete image/font loading, caching, and preload helpers for cards/backgrounds.

## 5. Code Quality & Maintainability

- [~] 5.1 Type hints are present in many core modules; not complete repo-wide strictness
- [~] 5.2 Some long functions remain in legacy UI module
- [~] 5.3 Magic numbers reduced in AI with constants, not fully normalized across legacy UI
- [x] 5.4 Error handling baseline exists in critical engine paths
- [x] 5.5 Critical-path tests exist and are active

## 6. Documentation

- [x] 6.1 Core public APIs have docstrings in key modules
- [x] 6.2 Architecture diagram exists in `docs/architecture.md`
- [x] 6.3 Deployment guide exists in `DEPLOYMENT.md`

## 7. Production Readiness

- [~] 7.1 Release messaging currently advertises online stack; keep if backend remains shipped
- [x] 7.2 Auto-save/checkpoint behavior exists in gameplay flow
- [~] 7.3 Low-performance mode tuning can be expanded

## 8. Critical Bug Fixes

- [x] 8.1 Invalid discard hand length fallback exists in `ai_strategy._choose_discard_indices_impl`
- [x] 8.2 Mutable default arg issue avoided in inspected core modules
- [x] 8.3 Timeout support exists for expensive discard levels in `ai_strategy.choose_discard_indices`
- [~] 8.4 Voice manager async behavior should be verified end-to-end

## Recent changes in this pass

- Cut over `main.py` to the state-driven runtime as the only supported execution path.
- Removed deprecated `--classic-client` from `main.py` CLI arguments.
- Updated `tests/test_main_entrypoint.py` to validate state-runtime defaults after flag removal.
- Updated `README.md` run instructions to state-driven defaults and removed obsolete `adapter.py` from project layout.

- Replaced `src/utils/asset_loader.py` stub with a concrete `AssetManager` implementation (path resolution, image/font caching, background/card preload helpers).
- Replaced `src/renderer/animation_manager.py` stub with a concrete `AnimationManager` (generic keyed animations plus legacy effect compatibility methods).
- Removed `GameApplication` initialize/shutdown TODOs in `src/controllers/game_controller.py`; app lifecycle now wires assets, renderer, animation manager, and running state concretely.
- Routed classic runtime effects usage through `src.renderer.AnimationManager` in `cribbage_pygame.py`.
- Added migration coverage tests in `tests/test_asset_loader.py` and `tests/test_animation_manager.py`.
- Re-ran full suite with latest migration changes (`.venv\\Scripts\\python.exe -m pytest -q .`) -> 180 passed.

- Added debug-validation postcondition hook calls in `engine.py` mutating methods.
- Added dependency injection support for AI discard strategy in `engine.py`.
- Added tests covering injected strategy path and validation hook invocation in `tests/test_engine.py`.
- Implemented normalized event action mapping in `src/input/event_handler.py` (keyboard/mouse/settings/quit).
- Added `GameController.process(actions)` dispatch path in `src/controllers/game_controller.py`.
- Replaced `GameController` legacy-module coupling with explicit runtime hooks API (`hooks=` callsites).
- Removed remaining direct `cribbage_pygame` imports from `src/` and `tests/` by migrating affected tests to `engine.py` + `cards.py` surfaces.
- Re-ran full test suite after hook and test migrations (`.venv\\Scripts\\python.exe -m pytest . --color=no`) -> 178 passed.
- Retired legacy runtime file `cribbage_pygame.py` and removed its packaging/docs references.
- Updated `GameApplication.handle_input()` to use `get_actions()` and `process(actions)` pipeline.
- Added controller tests for phase-based mouse-action dispatch in `tests/test_game_controller.py`.
- Removed accidental early bootstrap `main` block from `cribbage_pygame.py` to avoid pre-initialization execution.
- Switched gameplay loop in `cribbage_pygame.py` from direct `pygame.event.get()` phase dispatch to `EventHandler` action polling + `GameController.process(actions)`.
- Migrated intro/settings event handling in `cribbage_pygame.py` to action-driven processing via `EventHandler.get_actions()`.
- Fixed `VoiceManager` RVC executable detection bug (`shutil_which` typo to `shutil.which`) in `voice_manager.py`.
- Validated voice manager unit coverage remains green with `.venv\\Scripts\\python.exe -m pytest tests/test_voice_manager.py -q` (9 passed).
- Routed `cribbage_pygame.main()` runtime control through `GameApplication` (`game_controller`, `event_handler`, `running`, and settings/name/style sync).
- Added `GameApplication` lifecycle tests in `tests/test_game_controller.py`.
- Validated migration-focused regressions with `.venv\\Scripts\\python.exe -m pytest tests/test_game_controller.py tests/test_main_entrypoint.py -q` (12 passed).
- Removed the temporary `src/compat.py` boundary and completed `main.py` state-runtime-only cutover.
- Updated `tests/test_main_entrypoint.py` to mock `run_classic_client` at the `main.py` boundary.
- Re-ran focused entry/controller tests after compat boundary refactor (`.venv\\Scripts\\python.exe -m pytest tests/test_main_entrypoint.py tests/test_game_controller.py -q`, all passing).
- Started 6.4.2 cleanup by removing dead legacy global `show_computer_hand` from `cribbage_pygame.py` (no callsites).
- Fixed indentation regression in gameplay action loop and re-validated focused suites (`.venv\\Scripts\\python.exe -m pytest tests/test_main_entrypoint.py tests/test_game_controller.py tests/test_game_logic.py -q`, 22 passed).
- Continued 6.4.2 cleanup by removing additional dead globals `ctx` and `state` from `cribbage_pygame.py`.
- Continued 6.4.2 cleanup by removing dead `winner_index` global and routing winner state solely through `_CLASSIC_SESSION.winner`.
- Continued 6.4.2 cleanup by removing dead legacy alias `_rank_index` from `cribbage_pygame.py`.
- Completed a full safe global sweep for 6.4.2; no additional removable globals were found without breaking legacy compatibility references.
- Marked `cribbage_pygame.py` as deprecated and documented state-driven runtime as the supported startup path.
- Cleared repo Ruff lint baseline (`.venv\\Scripts\\python.exe -m ruff check .` -> all checks passed).
- Re-validated focused suites including voice manager tests (`.venv\\Scripts\\python.exe -m pytest tests/test_main_entrypoint.py tests/test_game_controller.py tests/test_game_logic.py tests/test_voice_manager.py -q` -> 31 passed).
- Retired the legacy `adapter.py` bridge and removed adapter-specific test coupling.
- Ran full test suite (`.venv\\Scripts\\python.exe -m pytest -q .`) -> 179 passed.
