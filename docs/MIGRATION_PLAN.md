<!-- docs/MIGRATION_PLAN.md: Stage 6 Architecture Migration Progress -->

# Stage 6: Full cribbage_pygame.py Migration

**Goal**: Modularize monolithic `cribbage_pygame.py` into discrete src/ components.

## Phase 1: Drawing Logic → src/renderer/

### BoardRenderer Tasks
- [x] **6.1.1** Extract `_draw_board_frame()` → `draw_background()`
- [x] **6.1.2** Extract `_draw_score_panel()` → `draw_scores()`
- [x] **6.1.3** Extract `_draw_crib_area()` → `draw_crib()`
- [x] **6.1.4** Extract `_draw_game_header()` → `draw_header()`
- [x] **6.1.5** Extract `_draw_label()` → helper utility
- [x] **6.1.6** Extract `_draw_scaled_card()` → helper utility
- [x] **6.1.7** Integrate into main loop via `draw_board(game_state)`
- [x] **6.1.8** Test + commit

### AnimationManager Tasks
- [x] **6.1.9** Extract card animation logic
- [x] **6.1.10** Extract phase transition animations
- [x] **6.1.11** Integrate into renderer update loop
- [x] **6.1.12** Test + commit

## Phase 2: Event Handling → src/input/

### EventHandler Tasks
- [x] **6.2.1** Extract pygame.event.get() polling
- [x] **6.2.2** Extract mouse event handlers (card selection)
- [x] **6.2.3** Extract keyboard event handlers (settings, AI level)
- [x] **6.2.4** Extract settings modal input handling
- [x] **6.2.5** Return action dict instead of direct state mutation
- [x] **6.2.6** Integrate into main loop via normalized action pipeline
- [x] **6.2.7** Add coverage for action dispatch paths

## Phase 3: Game Loop → src/controllers/

### GameController Tasks
- [x] **6.3.1** Extract phase handlers (deal, discard, pegging, counting)
- [x] **6.3.2** Extract `_transition_phase()` logic
- [x] **6.3.3** Extract `_check_for_winner()` logic
- [x] **6.3.4** Create `GameController.update()` orchestrator
- [x] **6.3.5** Replace main game loop with controller calls
- [x] **6.3.6** Test + commit

### GameApplication Tasks
- [x] **6.3.7** Move pygame.init(), screen setup to `initialize()`
- [x] **6.3.8** Move asset loading to `initialize()`
- [x] **6.3.9** Encapsulate runtime globals (`settings`, `player_name`, `ui_style`) through `GameApplication`
- [x] **6.3.10** Route classic main loop through `GameApplication` lifecycle fields (controller, event handler, running)
- [x] **6.3.11** Test verification complete (focused controller + entrypoint suite)

## Phase 4: Integration & Cleanup

- [x] **6.4.1** Update main.py to import classic entrypoint via src compatibility layer
- [x] **6.4.2** Delete unused global variables from cribbage_pygame.py (completed safe sweep; removed `show_computer_hand`, `ctx`, `state`, `winner_index`, `_rank_index`)
- [x] **6.4.3** Create src/compat.py for transition utilities
- [x] **6.4.4** Full test suite + ruff check
- [x] **6.4.5** Retire legacy compatibility file and finalize migration closeout

## Metrics
- **Starting**: 1 file (cribbage_pygame.py ~3500 LOC)
- **Target**: 6 files (~500 LOC each) + modular architecture
- **Test Status**: 98/98 passing at each phase
- **Ruff Clean**: Yes

## Session Checkpoints
- Phase 1.1: Drawing extraction + test
- Phase 2: Event handling extraction + test
- Phase 3: Controller extraction + test
- Phase 4: Integration + cleanup

## Notes
- Keep cribbage_pygame.py intact during migration (only extend/call)
- Add compat layer in src/ if needed
- Run full test suite after each phase
- Commits are atomic and describe phase+phase_num

## Current Reality Check (May 21, 2026)
- `src/input/event_handler.py` and `GameController.process(actions)` drive input routing.
- `GameApplication` owns app lifecycle, controller wiring, and render/update flow.
- `main.py` is the only supported runtime entrypoint.
- Renderer and animation logic are owned in `src/renderer/`.
- Legacy `cribbage_pygame.py` has been retired.
