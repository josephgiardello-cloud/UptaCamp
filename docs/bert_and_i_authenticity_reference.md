# Bert & I Authenticity Reference for Level 5 Bert

Last updated: 2026-05-20
Scope: Grounded voice guidance for dialog expansion in this project.

## 1) What this file is for
This document is the source-of-truth voice reference for expanding Level 5 Bert dialog while avoiding parody drift.

Use it to:
- keep Bert in a dry, workmanlike, Down East storytelling register
- decide what can be treated as factual vs stylized
- add new lines that match game state and mood without breaking character

## 2) Source notes and confidence
### Primary sources consulted
- Wikipedia: Bert & I (retrieved 2026-05-20)
- Wayback Archive: Tim Sample page "What about Bert and I?" (retrieved 2026-05-20)
- Boothbay Register: "Tim Sample reflects on a life with Maine humor" (retrieved 2026-05-20)

### Reliability notes
- The Wikipedia page itself flags that it needs additional citations and is a stub.
- The Tim Sample archived page is useful firsthand context but is still not a formal linguistic corpus.
- The Boothbay Register page provides rich interview material, including direct quotes from Tim Sample about dialect and attitude; this is strong cultural context but still not a full transcript corpus for linguistic frequency claims.
- One Bangor Daily News reference linked from Wikipedia was not extractable in-tool during this pass.

### Confidence tiers for this doc
- High confidence: who created/performed the material, broad setting, and storytelling nature.
- Medium-high confidence: Maine humor attitude traits described by Tim Sample in interview quotes (unflappable delivery, pragmatic worldview, place-rooted identity).
- Low confidence: any attempt to treat Bert & I wording as literal speech documentation of all Downeast Mainers.

## 3) Verified baseline facts to preserve
From the consulted sources:
- Bert & I refers to collections of Maine/Down East humor stories.
- The stories were made famous mostly by Marshall Dodge and Bob Bryan.
- The title characters are fishermen, tied to the vessel Bluebird (later Bluebird II), operating from Kennebunkport.
- The material is known for dry wit, folk storytelling cadence, and work-detail texture.
- The recordings popularized a stylized "Yankee" Maine voice for broader audiences.

Interpretation for this project:
- Bert is best modeled as a crafted regional storytelling persona, not a strict transcript of one historical individual's real-life speech.

Boothbay/Tim Sample reference points to preserve:
- Dockside elder speakers (as described by Sample) modeled an unflappable, slow-burn response style.
- The humor attitude favors pragmatism over dramatics: acknowledge events, do not overreact, keep moving.
- "Sense of place" is central: maritime work, woods/water labor, and identity rooted in Maine daily life.
- Dialect includes old-fashioned forms, but delivery carries the character more than heavy phonetic spelling.

## 4) Voice DNA for game dialog
### Core style
- Dry, understated confidence.
- Practical, trade-grounded observations.
- Sparse but pointed humor.
- Emotional control; mood leaks through word choice, not direct declaration.
- Unflappable pacing: respond to chaos with calm, often with delayed or wry framing.
- Pragmatic philosophy: treat events as part of the workday, not melodrama.

### Sentence behavior
- Prefer short to medium lines.
- Avoid over-explaining intent.
- Use concrete nouns and verbs over abstract tactical narration.
- Keep rhythm conversational, not theatrical.
- In tense moments, lower the temperature verbally instead of escalating volume.
- Favor dry reframes ("seen worse," "keep the keel straight") over declarations of emotion.

### Domain imagery to favor
- tide, current, rail, deck, keel, hooks, knots, nets, haul, weather, harbor

### Dialect usage policy
- Light regional markers are acceptable in moderation (for example "ayuh", "bub", "wicked").
- Do not over-phoneticize spelling.
- Do not turn every line into accent performance.

## 5) Hard guardrails for Level 5 expansion
These are mandatory for newly generated lines:

1. No explicit strategy self-narration.
- Avoid lines like "I am playing aggressive/deliberate/cutthroat now."
- Mood and pressure must be implied through phrasing.

2. Score mention policy.
- Bert may openly reference score when ahead.
- When losing, Bert must not openly admit he is losing.
- Losing-state tone should be implied via edge, irritation, or tightening language.

3. No stereotype caricature.
- Avoid cartoon "backwoods" exaggeration or novelty dialect spam.

4. Preserve competence.
- Bert should sound experienced and trade-aware, never buffoonish.

## 6) Event-to-tone mapping
Use these tendencies when adding lines:

- game_start / round_start:
  - neutral or ahead: composed, tidy, measured
  - behind: sharper edge, implied pressure, no open admission of being behind

- cards_dealt:
  - dealer context: practical discard language
  - behind: tightening language (clean tosses, no waste)

- pegging_score / go_point / pegging_31:
  - terse, count-aware, concrete
  - frustration appears as clipped commentary, not explicit score confession

- hand_scored / crib_scored:
  - summarize outcomes in practical terms
  - if ahead, score can be spoken plainly
  - if behind, use weather/work metaphors instead of numeric self-disclosure

- bert_won / player_won:
  - bert_won can include explicit score line
  - player_won should remain controlled and competitive without self-pity

## 7) Level 5 learning expansion protocol
When adding new "learned" dialog paths:

- Trigger design:
  - tie each learned cue to a concrete recurring board pattern
  - examples: repeated late-count go, repeated high-value hand, repeated crib donation pattern

- Response design:
  - first recognition: brief warning/notice line in-voice
  - subsequent occurrences: adapt line choice without repeating the same warning every hand

- Persistence design:
  - store cue keys in a stable set/map
  - keep cue names pattern-based (not player-personal)

- Safety design:
  - no claims of impossible memory detail
  - no out-of-character tactical monologues

## 8) Recommended quality checks before shipping new lines
For each new dialog set, confirm:
- style: sounds dry and practical, not performative
- authenticity: includes domain-grounded imagery, limited dialect markers
- policy: no explicit losing admission on trailing paths
- policy: no explicit strategy-mode declaration
- coverage: at least 2-3 variants per critical event/mood lane
- tests: assertions are robust to variant phrasing, not brittle to one exact string

## 9) Known limits and future improvements
Current limits:
- This reference is grounded in accessible public summaries and archived commentary, not a full linguistic corpus.

Future upgrades for higher authenticity:
- add transcripts from original Bert & I recordings where rights allow
- add region-specific oral history corpora for comparison
- build a phrase-frequency bank and style checks from approved source text
- split vocabulary by scenario (friendly, needling, irritated, closing-out)

## 10) Quick implementation checklist
When writing a new Bert line, ask:
- Is this practical and understated?
- Is this implied mood rather than declared mood?
- If trailing, did I avoid openly admitting he is losing?
- If ahead, is any score mention concise and natural?
- Would this still sound right if read aloud in a dry storytelling cadence?
