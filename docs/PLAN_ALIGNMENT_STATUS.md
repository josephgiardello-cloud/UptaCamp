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
- [~] 1.3 Global variables encapsulation
  - Current: `GameApplication` class exists in `src/controllers/game_controller.py`
  - Remaining: route all runtime globals in `cribbage_pygame.py` through `GameApplication`
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
