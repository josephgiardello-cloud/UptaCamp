# Bert Dialog Lane Map (Level 5)

This map defines the score-gap-driven dialog and intent lanes for Bert Plus.

Score gap means:
- `score_gap = bert_score - player_score`

## Mood Lanes

| Gap Range | Mood Lane | Tone | Play Posture |
| --- | --- | --- | --- |
| `<= -20` | `boiling` | cutthroat, exact, no-slack | `cutthroat` |
| `-19 .. -15` | `hot` | determined, deliberate, tightening | `deliberate` |
| `-14 .. -10` | `frustrated` | annoyed, sharpening | `balanced` |
| `-9 .. -5` | `frustrated` | irritated but controlled | `balanced` |
| `-4 .. +4` | `neutral` | dry, observational | `balanced` |
| `+5 .. +9` | `focused` | sly confidence | `balanced` |
| `+10 .. +14` | `stoic` | smug confidence | `balanced` |
| `+15 .. +19` | `clinical` | condescending control | `deliberate` |
| `>= +20` | `clinical` | openly patronizing command | `deliberate` |

## Point-Band Progression Overlay

Every Downeast line can receive a progression sentence based on score gap bands:

- trailing: `-5`, `-10`, `-15`, `-20`
- leading: `+5`, `+10`, `+15`, `+20`

This guarantees a natural-feeling transition across the full short-game spread.

## Event Lanes

Events route through mood lanes first, then event context.

- `level_selected`: sets opening persona tone from current lane.
- `game_start`: establishes immediate pressure/pace voice.
- `round_start`: momentum statement with lane-appropriate intensity.
- `cards_dealt`: dealer-aware language + lane pressure.
- `go_called`: lane response to pass and count pressure.
- `go_point`: lane reaction to incremental score gain.
- `last_card`: lane phrasing for close-out point.
- `pegging_score`: lane-specific phrasing for local swing.
- `pegging_31`: lane and pressure-aware milestone line.
- `hand_scored`: lane summary + score-gap framing.
- `crib_scored`: dealer/crib value + lane tone.
- `player_won` / `bert_won`: lane-specific postgame voice.

## Level 5 Learning Overlay

On top of lane output, Level 5 can append a one-time learning acknowledgment when a new cue appears.

Current cues:
- player big hand (`player_hand_points >= 10`)
- player strong crib while Bert is non-dealer (`crib_points >= 6`)
- late-count go tendency (`pegging_total >= 27`)
- trailing go-point grind (`score_gap <= -10`)

Acknowledgment style:
- always Downeast-coded
- always includes a warning memory signal ("I'll remember that")
- one-time per cue in current runtime memory

## Behavioral Intent

Because a game is short (~5 minutes), lane transitions must be obvious quickly:
- Down 5 should already sound irritated.
- Down 15 should sound deliberate and determined.
- Down 20 should sound cutthroat and exact.
- Up 5/10/15/20 should escalate from sly to smug to condescending to openly patronizing.
- Learning acknowledgments should feel sparse, meaningful, and threatening in a dry Downeast way.
