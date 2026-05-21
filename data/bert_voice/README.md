# Bert Voice Dataset Pack

This folder contains seed data and configuration for a constrained Downeast dialog generator.

Files:
- `sources.yaml`: canonical source corpus metadata
- `gold_lines_seed.jsonl`: approved in-voice exemplars
- `negative_lines_seed.jsonl`: reject examples with reason tags
- `lexicon.yaml`: approved vocabulary buckets and forbidden terms
- `thematic_mapping.yaml`: cribbage-to-Maine-life metaphor mapping
- `event_mood_matrix.yaml`: behavior rules by event and mood
- `parameter_rubric.yaml`: target style parameter ranges
- `eval_prompts_seed.jsonl`: holdout evaluation prompt seeds
- `repetition_policy.yaml`: anti-repetition policy settings

Notes:
- These are seed files. Expand line counts to target volumes over time.
- Keep licensing/provenance with each source entry.
- Preserve the rule: trailing paths must not openly admit losing.
