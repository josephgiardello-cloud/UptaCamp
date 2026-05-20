<!-- docs/MIGRATION_PLAN.md: Stage 6 Architecture Migration Progress -->

# Stage 6: Full cribbage_pygame.py Migration

**Goal**: Modularize monolithic `cribbage_pygame.py` into discrete src/ components.

## Phase 1: Drawing Logic → src/renderer/

### BoardRenderer Tasks
- [ ] **6.1.1** Extract `_draw_board_frame()` → `draw_background()`
- [ ] **6.1.2** Extract `_draw_score_panel()` → `draw_scores()`
- [ ] **6.1.3** Extract `_draw_crib_area()` → `draw_crib()`
- [ ] **6.1.4** Extract `_draw_game_header()` → `draw_header()`
- [ ] **6.1.5** Extract `_draw_label()` → helper utility
- [ ] **6.1.6** Extract `_draw_scaled_card()` → helper utility
- [ ] **6.1.7** Integrate into main loop via `draw_board(game_state)`
- [ ] **6.1.8** Test + commit

### AnimationManager Tasks
- [ ] **6.1.9** Extract card animation logic
- [ ] **6.1.10** Extract phase transition animations
- [ ] **6.1.11** Integrate into renderer update loop
- [ ] **6.1.12** Test + commit

## Phase 2: Event Handling → src/input/

### EventHandler Tasks
- [ ] **6.2.1** Extract pygame.event.get() polling
- [ ] **6.2.2** Extract mouse event handlers (card selection)
- [ ] **6.2.3** Extract keyboard event handlers (settings, AI level)
- [ ] **6.2.4** Extract settings modal input handling
- [ ] **6.2.5** Return action dict instead of direct state mutation
- [ ] **6.2.6** Integrate into main loop via `handle_events(event)`
- [ ] **6.2.7** Test + commit

## Phase 3: Game Loop → src/controllers/

### GameController Tasks
- [x] **6.3.1** Extract phase handlers (deal, discard, pegging, counting)
- [x] **6.3.2** Extract `_transition_phase()` logic
- [x] **6.3.3** Extract `_check_for_winner()` logic
- [x] **6.3.4** Create `GameController.update()` orchestrator
- [x] **6.3.5** Replace main game loop with controller calls
- [ ] **6.3.6** Test + commit

### GameApplication Tasks
- [ ] **6.3.7** Move pygame.init(), screen setup to `initialize()`
- [ ] **6.3.8** Move asset loading to `initialize()`
- [ ] **6.3.9** Encapsulate globals (player_name, settings, etc.)
- [ ] **6.3.10** Create main() that uses GameApplication
- [ ] **6.3.11** Test + commit

## Phase 4: Integration & Cleanup

- [ ] **6.4.1** Update main.py to import from src/
- [ ] **6.4.2** Delete unused global variables from cribbage_pygame.py
- [ ] **6.4.3** Create src/compat.py for any transition utilities
- [ ] **6.4.4** Full test suite + ruff check
- [ ] **6.4.5** Final commit + mark cribbage_pygame.py deprecated

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
