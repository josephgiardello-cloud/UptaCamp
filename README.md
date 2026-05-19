# UptaCamp - The Camp Cribbage Game 🃏

A fun, interactive **Cribbage card game** built with Python and Pygame. Play against an intelligent AI opponent with adjustable difficulty levels.

## Table of Contents

- [Overview](#overview)
- [Screenshots](#screenshots)
- [Features](#features)
- [Tech Stack](#tech-stack)
- [Installation](#installation)
- [How to Play](#how-to-play)
- [Difficulty Levels](#difficulty-levels)
- [Development](#development)
- [Contributing](#contributing)
- [License](#license)

## Overview

**UptaCamp** is a fully playable Cribbage implementation featuring:
- Accurate Cribbage game rules and scoring
- Intelligent AI opponent with 3 difficulty levels
- Beautiful card graphics and UI
- Automatic hand scoring and counting
- Support for multiple rounds with running scores

Cribbage is a classic two-player card game known for its unique scoring system and strategic depth. If you're new to Cribbage, start with the **Easy** difficulty to learn the rules!

## Screenshots

Each image below is a curated single-shot representation of a key game stage.

### 1. Title / Welcome Screen
![Upta title screen](screenshots/readme_title.png)

Select AI difficulty and start a new game.

### 2. Discard Phase
![Discard phase](screenshots/readme_discard.png)

Each player receives 6 cards and discards 2 to the crib.

### 3. Pegging Phase
![Pegging phase](screenshots/readme_pegging.png)

Players alternate cards up to 31, scoring for fifteens, pairs, runs, go, and last card.

### 4. End-Of-Hand Counting
![Counting phase](screenshots/readme_counting.png)

Hand totals and crib scoring are displayed before moving to the next round.

## Features

✅ **Complete Cribbage Game**
- Deal, discard, pegging, and counting phases
- Accurate hand scoring (pairs, runs, fifteens, flush, nobs)
- Automatic crib scoring
- Winner detection at 121 points
- **End-of-round scoring breakdown** showing detailed point contributions

✅ **Premium Presentation**
- Maine-themed card back textures on opponent's cards
- Floating score popups and card flight animations during pegging
- Screen shake effects on 31-point plays
- Smooth tweened card movements and transitions
- Real-time hand scoring breakdown display

✅ **Intelligent AI**
- Level 1 (Easy): Random play
- Level 2 (Medium): Monte Carlo evaluation across unseen cards
- Level 3 (Hard): Opponent risk estimation without hand peeking

✅ **User-Friendly Interface**
- Click or press keys to select difficulty
- Drag-and-drop card selection for discard phase
- Clear game phase indicators and messages
- Real-time scoring display with pegging totals
- End-of-hand scoring recap panels (15s, pairs, runs, flush, nobs)
- Responsive window sizing

✅ **Flexible Gameplay**
- Choose AI difficulty before each game
- Track scores across multiple rounds
- Switch difficulty mid-session with F2
- Non-blocking capture mode for screenshots (game continues unless --exit-after-capture flag)
- Automated one-hand gameplay video capture (intro screen -> end of hand)

✅ **Online And Competitive Foundation**
- Persistent online backend with room invites and strict turn-order validation
- Async-safe turn submission with idempotency keys (retry-safe client behavior)
- Matchmaking queue pairing for ranked games
- ELO ratings updates, match history, and player profile stats
- Bot decision telemetry capture and CSV export for tuning workflows
- Self-play ladder simulation tooling for large-scale AI benchmark runs

## Tech Stack

| Component | Technology |
|-----------|------------|
| **Language** | Python 3.10+ |
| **GUI Framework** | Pygame |
| **Game Logic** | Custom Cribbage engine |
| **Scoring** | cards.py module |
| **Assets** | PNG card graphics (SVG source) |

## Installation

### Prerequisites
- Python 3.10 or later
- pip (Python package manager)

### Steps

1. **Clone the repository**
   ```bash
   git clone https://github.com/josephgiardello-cloud/UptaCamp.git
   cd UptaCamp
   ```

2. **Create a virtual environment** (recommended)
   ```bash
   python -m venv .venv
   .venv\Scripts\activate          # On Windows
   source .venv/bin/activate      # On macOS/Linux
   ```

3. **Install dependencies**
   ```bash
   pip install pygame
   ```

4. **Run the game**
   ```bash
   python cribbage_pygame.py
   ```

## How to Play

### Starting a Game
1. Launch the game: `python cribbage_pygame.py`
2. Press **Enter** to start
3. Choose AI difficulty with **1** (Easy), **2** (Medium), or **3** (Hard)

### Game Phases

#### Discard Phase
- You're dealt 6 cards
- Select 2 cards to discard to the "crib"
- The AI automatically selects its discards
- One card is cut as the "starter"

#### Pegging Phase
- Take turns playing cards from your 4-card hand
- Keep a running total (max 31 points)
- Score points for:
  - **Pairs**: Same rank (2 points)
  - **Pairs Royal**: Three of a kind (6 points)
  - **Double Pair Royal**: Four of a kind (12 points)
  - **Fifteens**: Cards totaling 15 (2 points each)
  - **Thirty-One**: Exactly 31 (2 points)
  - **Runs**: Consecutive ranks (3+ cards)
- Play "Go" if you can't play without exceeding 31
- Last card played earns 1 point

#### Counting Phase
- Score your hand against the starter card
- The dealer scores the crib for bonus points

### Scoring Rules
- **Fifteens**: Each combination of cards totaling 15 = 2 points
- **Pairs**: Cards of same rank = 2 points (3+ pairs multiply)
- **Runs**: 3+ consecutive cards = points equal to run length
- **Flush**: 4+ cards of same suit = 4 points (5 cards = 5 points)
- **Nobs**: Jack of same suit as starter = 1 point

### Winning
First player to reach **121 points** wins!

## Difficulty Levels

### Level 1: Easy 🌱
- AI plays randomly
- Perfect for learning the rules
- ~40% win rate for new players

### Level 2: Medium 🌳
- AI evaluates all possible starting hands
- Uses Monte Carlo method for discard selection
- ~60% win rate for experienced players

### Level 3: Hard 🌲
- AI predicts opponent replies without peeking
- Simulates 140+ possible opponent hands per move
- Avoids risky plays at dangerous totals
- ~85% win rate for most players

**Pro Tip**: Switch difficulty with **F2** during gameplay!

## Development

### Project Structure
```
UptaCamp/
├── cribbage_pygame.py        # Main game
├── cards.py                  # Scoring engine
├── convert_card_assets.py    # Asset utilities
├── assets/
│   └── cards/                # Card PNG images (52 standard deck)
├── tests/                    # Unit tests (coming soon)
├── docs/                     # Detailed documentation
├── pyproject.toml            # Project configuration
├── README.md                 # This file
├── LICENSE                   # MIT License
└── .gitignore               # Git ignore rules
```

### Running Tests
```bash
pytest tests/
```

### Linting & Code Quality
```bash
ruff check .
black --check .
```

### Building Card Assets (Optional)
If you modify card SVG files:
```bash
python convert_card_assets.py
```

### Capture Screenshots And Video

Capture the title screen screenshot:
```bash
python cribbage_pygame.py --capture-title screenshots/readme_title.png --exit-after-capture
```

Capture the discard phase screenshot:
```bash
python cribbage_pygame.py --capture-discard screenshots/readme_discard.png --exit-after-capture
```

Capture a pegging-phase gameplay screenshot:
```bash
python cribbage_pygame.py --capture-gameplay screenshots/readme_pegging.png --exit-after-capture
```

Capture a short video clip that starts on the title screen, auto-plays one full hand, and stops at end-of-hand scoring:
```bash
python cribbage_pygame.py --capture-video screenshots/gameplay_hand.mp4
```

Optional tuning flags:
```bash
python cribbage_pygame.py \
   --capture-video screenshots/gameplay_hand.mp4 \
   --capture-video-fps 30 \
   --capture-video-intro-seconds 1.5 \
   --capture-video-end-seconds 1.2 \
   --capture-video-max-seconds 90
```

Notes:
- Video encoding uses `ffmpeg` if available on PATH.
- If `ffmpeg` is missing, frame PNGs are still saved to a sibling `*_frames` folder.

## Online Backend (Deep Mode)

Run the online API server:

```bash
python online_api_server.py --host 127.0.0.1 --port 8787 --db online_state.db
```

Run the websocket push server:

```bash
python online_ws_server.py --host 127.0.0.1 --port 8790 --db online_state.db
```

API examples:

```bash
# Create/login player session (returns player_id + session_token)
curl -X POST http://127.0.0.1:8787/players \
   -H "Content-Type: application/json" \
   -d '{"display_name":"Alice"}'

# Create invite room
curl -X POST http://127.0.0.1:8787/invites/create \
   -H "Authorization: Bearer <SESSION_TOKEN>" \
   -H "Content-Type: application/json" \
   -d '{"host_player_id":"p1"}'

# Submit signed turn with idempotency protection
curl -X POST http://127.0.0.1:8787/matches/<match_id>/turns \
   -H "Authorization: Bearer <SESSION_TOKEN>" \
   -H "Content-Type: application/json" \
   -d '{"player_id":"p1","action_type":"deal_ready","payload":{"ready":true},"idempotency_key":"req-123","signature":"<HMAC_SHA256_SIGNATURE>"}'
```

The Pygame online client flow is available in [main.py](main.py):
- Intro -> Online Match
- Login
- Create Room / Join Room / Quick Match
- Live phase-based turn loop (deal/discard/pegging/counting)

WebSocket protocol:
- Client sends initial auth payload: `{ "match_id", "player_id", "session_token" }`
- Server pushes `match_snapshot` and `turn_update` events
- Client falls back to HTTP polling when websocket is unavailable

Run self-play ladder (large AI benchmark batches):

```bash
python tools/self_play_ladder.py --db online_state.db --rounds-per-pair 500 --seed 11
```

Export bot telemetry for analysis:

```bash
python tools/export_bot_telemetry.py --db online_state.db --out bot_telemetry.csv
```

## Production Stack (Docker)

Start API + websocket servers with shared SQLite data:

```bash
docker compose up --build
```

Services:
- API: `http://127.0.0.1:8787`
- WebSocket: `ws://127.0.0.1:8790`

## Environment

- `UPTACAMP_DB_PATH`: SQLite path for online backend state (default `online_state.db`)

## Contributing

We welcome contributions! Please read [CONTRIBUTING.md](CONTRIBUTING.md) for our development process and guidelines.

### Quick Start
1. Fork the repository
2. Create a feature branch (`git checkout -b feature/your-feature`)
3. Make your changes
4. Run tests: `pytest tests/`
5. Commit with a clear message
6. Push to your fork
7. Open a Pull Request

### Bug Reports
Found a bug? Please open an [Issue](https://github.com/josephgiardello-cloud/UptaCamp/issues) with:
- Description of the problem
- Steps to reproduce
- Expected vs. actual behavior
- Screenshots (if applicable)

## License

This project is licensed under the **MIT License** - see [LICENSE](LICENSE) for details.

MIT License permits:
- ✅ Commercial use
- ✅ Modification
- ✅ Distribution
- ✅ Private use

But requires:
- ⚠️ License and copyright notice

## Credits

- **Game Logic**: Cribbage rules implementation
- **AI**: Monte Carlo and opponent simulation algorithms
- **UI**: Pygame framework
- **Card Assets**: Digital card graphics

---

**Questions?** Open an issue or check our [CODE_OF_CONDUCT.md](CODE_OF_CONDUCT.md) for community guidelines.

**Happy Playing! 🎮**
