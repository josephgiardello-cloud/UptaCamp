# Plan Alignment Status (May 20, 2026)

This file tracks alignment against the requested implementation plan.

## 1. Architecture & Code Organization

- [x] 1.1 God Object split started (`src/renderer`, `src/input`, `src/controllers`, `src/utils` exist)
- [~] 1.1 Main loop fully migrated to controller pipeline
  - Current: legacy `cribbage_pygame.py` loop delegates core phase updates via `GameController`
  - Current: event/action flow now routes through `EventHandler.get_actions()` + `GameController.process(actions)`
  - Current: gameplay event loop uses normalized action pipeline instead of direct pygame event dispatch to phase handlers
  - Current: intro/settings loop now consumes normalized `EventHandler` actions (with raw-event passthrough for compatibility handlers)
  - Remaining: factor large intro/settings conditionals into dedicated input/controller components
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

- [~] 4.1 Frame/animation efficiency work is partially present
- [~] 4.2 AI lag mitigation is partial (timeouts/fallbacks exist in strategy)
- [~] 4.3 Asset preloading/caching is present; deeper memory optimization optional

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

- Added debug-validation postcondition hook calls in `engine.py` mutating methods.
- Added dependency injection support for AI discard strategy in `engine.py`.
- Added tests covering injected strategy path and validation hook invocation in `tests/test_engine.py`.
- Implemented normalized event action mapping in `src/input/event_handler.py` (keyboard/mouse/settings/quit).
- Added `GameController.process(actions)` dispatch path in `src/controllers/game_controller.py`.
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
- Added `src/compat.py` and updated `main.py` to import classic mode entrypoint from `src.compat` rather than directly from `cribbage_pygame`.
- Updated `tests/test_main_entrypoint.py` to mock `run_classic_client` at the `main.py` boundary.
- Re-ran focused entry/controller tests after compat boundary refactor (`.venv\\Scripts\\python.exe -m pytest tests/test_main_entrypoint.py tests/test_game_controller.py -q`, all passing).
- Started 6.4.2 cleanup by removing dead legacy global `show_computer_hand` from `cribbage_pygame.py` (no callsites).
- Fixed indentation regression in gameplay action loop and re-validated focused suites (`.venv\\Scripts\\python.exe -m pytest tests/test_main_entrypoint.py tests/test_game_controller.py tests/test_game_logic.py -q`, 22 passed).
- Continued 6.4.2 cleanup by removing additional dead globals `ctx` and `state` from `cribbage_pygame.py`.
- Continued 6.4.2 cleanup by removing dead `winner_index` global and routing winner state solely through `_CLASSIC_SESSION.winner`.
- Continued 6.4.2 cleanup by removing dead legacy alias `_rank_index` from `cribbage_pygame.py`.
- Completed a full safe global sweep for 6.4.2; no additional removable globals were found without breaking legacy compatibility references.
- Marked `cribbage_pygame.py` as deprecated at module header level and documented `main.py -> src.compat.run_classic_client()` as the supported runtime path.
- Cleared repo Ruff lint baseline (`.venv\\Scripts\\python.exe -m ruff check .` -> all checks passed).
- Re-validated focused suites including voice manager tests (`.venv\\Scripts\\python.exe -m pytest tests/test_main_entrypoint.py tests/test_game_controller.py tests/test_game_logic.py tests/test_voice_manager.py -q` -> 31 passed).
- Ran full test suite (`.venv\\Scripts\\python.exe -m pytest -q`) -> 139 passed.
