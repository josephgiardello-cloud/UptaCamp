# Training Protocol

This repo uses a lightweight tabular learning agent with posture shaping, not a deep neural stack. That means the highest ROI comes from focused, staged training with strict evaluation gates instead of one long blind run.

## Training Goal

Raise Barnabas and Bert in a way that:

- keeps levels 1 through 3 aligned to a sane beginner/medium/hard ladder,
- keeps level 4 only modestly above hard and still trainable,
- keeps level 5 (Barnabas) as the current house boss,
- and makes level 6 a stronger learned variant without collapsing into level 4 behavior.

## Recalculated Training Budget

These are practical targets based on the current codebase and the existing training scripts:

- **Level 4 / Bert improvement target**: about **4,000 to 6,000 focused episodes** from a strong checkpoint to become modestly but clearly better than hard level AI.
- **Level 5 / Barnabas specialization target**: about **8,000 to 10,000 focused episodes** after bootstrapping from Bert to stay above level 4 while remaining beatable by an excellent player.
- **Combined near-term budget**: about **12,000 to 18,000 focused episodes** to get a credible, stable improvement cycle.
- **If starting from scratch**: budget **20,000 to 30,000 total episodes** across both agents.
- **To chase an external top-tier cribbage bot**: expect **35,000 to 50,000+ focused episodes** plus better search/self-play sampling. Raw episode count alone will not close that gap reliably.

These numbers are lower than a blind run because they assume the improved ROI methods below are in place.

## Best ROI Methods

### 1. Evaluate with real game completion

Use full-game evaluation that always resolves to a winner, rather than capped rounds that can stall.

Recommended metrics:

- win rate,
- average score differential,
- average hand differential,
- blunder rate on discard and pegging.

### 2. Train from checkpoints, not from one moving target

Use a ladder of saved models and only promote a new checkpoint if it beats the previous champion by a clear margin.

Suggested gate:

- evaluate every **1,500 to 2,000 episodes**,
- run at least **150 games vs level 3**, **150 games vs level 4**, and **150 games vs the current champion snapshot**,
- promote only if the candidate is at least **54% win rate** against the current champion and does not regress against level 3.

### 3. Bias training toward high-impact decisions

Spend more samples on discard and pegging states that matter most:

- awkward 5-lead decisions,
- crib-leak situations,
- endgame totals near 112-121,
- pegging choices with multiple legal cards.

### 4. Mix opponents instead of using one opponent type

Best ROI mix for focused training:

- **45%** current Barnabas snapshot,
- **35%** current level 6 snapshot,
- **20%** hard level AI.

That mix gives variety without wasting most samples on weak play.

## Suggested Schedule

### Phase 1: Bert lift

- Run **4,000 to 6,000 episodes**.
- Goal: make level 4 modestly stronger than level 3 and reduce obvious discard/pegging leaks.
- Keep only checkpoints that beat the previous checkpoint by a meaningful margin.

### Phase 2: Barnabas specialization

- Bootstrap Barnabas from the best Bert checkpoint.
- Run **8,000 to 10,000 episodes**.
- Goal: keep Barnabas above hard and level 4, while sharpening endgame and crib pressure without making him feel unreachable.

### Phase 3: Stabilization pass

- Run **1,500 to 3,000 additional episodes** only on the champion checkpoint.
- Goal: reduce variance and clean up late-game mistakes.

## Practical Rule Of Thumb

If you want the shortest useful answer:

- **~12k to 18k focused episodes** gets you a strong internal house AI.
- **~20k to 30k focused episodes** gets you a more stable version of that strength.
- **35k+ focused episodes** is where you start paying for diminishing returns unless evaluation and opponent mix are very strong.

## What Not To Do

- Do not rely on one large run with no evaluation gate.
- Do not train only against random legal moves.
- Do not count capped or stalled benchmark runs as real progress.
- Do not promote every checkpoint automatically.
