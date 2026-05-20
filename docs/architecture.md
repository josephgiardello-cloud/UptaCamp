<!-- docs/architecture.md: Modular architecture overview -->

# Architecture

## Module Structure

```
cribbage_game/
├── src/                      # Refactored modular code
│   ├── renderer/             # Drawing and visualization
│   ├── input/                # Event handling
│   ├── controllers/          # Game orchestration
│   └── utils/                # Utilities (assets, config)
├── tests/                    # Test suite (98+ tests)
├── tools/                    # Utilities (training, conversion)
├── states/                   # Game state machines
├── assets/                   # Images, sounds, data
└── *.py                      # Legacy monolithic modules (phase-out)
```

## Component Diagram

```
User Input
    ↓
[EventHandler] (src/input/)
    ↓
[GameController] (src/controllers/)
    ├→ [CribbageEngine] (engine.py)
    │  └→ [BertAgent] (bert_agent.py)
    │
    ├→ [GameState] (game_state.py)
    │
    └→ [Validation] (engine.py)
         ↓
    [GameApplication] (src/controllers/)
         ↓
    [BoardRenderer] (src/renderer/)
         ↓
    Display
```

## Module Responsibilities

### `src/renderer/`
- **BoardRenderer**: Draws game board, cards, scores, animations
- **AnimationManager**: Queues and renders card animations

### `src/input/`
- **EventHandler**: Converts pygame events to game actions

### `src/controllers/`
- **GameApplication**: Global state encapsulation (screen, clock, assets, etc.)
- **GameController**: Orchestrates game logic and updates

### `src/utils/`
- **AssetManager**: Loads and caches images, fonts, sounds
- **Settings**: Configuration management

## AI Strategy

```
GameState (hand, scores, phase)
    ↓
[AI Strategy] (ai_strategy.py)
    ├─ Level 1-3: Heuristic rules (fast)
    ├─ Level 4: Monte Carlo with timeout
    └─ Level 5: BertAgent with TD learning
         ↓
    [BertAgent] (bert_agent.py)
    ├─ encode_game_state_as_vector: 20-dim feature
    ├─ Q-learning: TD(0) updates
    ├─ Optional DQN: Neural network (PyTorch)
    └─ Model persistence: bert_model.pkl
         ↓
    Recommended action
```

## Game Flow

1. **Initialization**: GameApplication loads assets, initializes engine
2. **Main Loop**:
   - EventHandler captures input
   - GameController delegates to engine
   - Engine updates state (discard → pegging → counting)
   - AI strategy chooses action at each decision point
   - BertAgent learns from experience (Level 5)
   - BoardRenderer draws updated board
3. **Save/Load**: GameState serialized to file
4. **Shutdown**: GameApplication releases resources

## Testing Strategy

- **98+ unit tests**: Validate game logic, AI decisions, state transitions
- **Coverage**: engine, strategy, scoring, online modes
- **CI/CD**: GitHub Actions on push/PR

## Future Refactoring (Stage 4+)

- Migrate drawing logic from `cribbage_pygame.py` → `src/renderer/`
- Migrate event handling from `cribbage_pygame.py` → `src/input/`
- Migrate game loop from `cribbage_pygame.py` → `src/controllers/`
- Remove monolithic `cribbage_pygame.py` after migration complete

See [DEPLOYMENT.md](../DEPLOYMENT.md) for distribution guide.
