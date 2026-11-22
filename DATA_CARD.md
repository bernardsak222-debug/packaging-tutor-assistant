# Data Card: Packaging Technology Tutor Dialogues (v3.1)

## Summary
Multi-turn tutoring dialogues in English (with a few Pidgin-English examples) for teaching packaging technology to Ghanaian vocational and tertiary students. Used to fine-tune a small language model (Gemma 3) into a Socratic teaching assistant.

## Contents
| split | dialogues | training pairs |
|---|---|---|
| train | 392 | 875 |
| val | 80 | 184 |
| test | 58 | 128 |

Files: `data/train.jsonl`, `val.jsonl`, `test.jsonl`. Each line has `id`, `group` (product), `type` (behaviour) and `messages` (system, user, assistant turns).

## How it was made
- **Synthetic and hand-designed.** No real student data was collected. Dialogues were written with Claude (Anthropic) from 32 hand-written scenario cards (`data_building/cards.py`), one per Ghanaian product (e.g. shea butter, gari, palm oil, smoked fish), listing risks, material options with advantages, drawbacks and cost tiers, and relevant regulators.
- `data_building/build_v3.py` generates the dialogues from the cards, plus 11 instructor-round additions (`instructor_additions_v3a.jsonl`) and 8 Pidgin-English dialogues.
- **Behaviours covered:** guided material choice, wrong-choice correction, student refusing regulations, changed assumptions, stuck or discouraged students, cost and end-of-life questions, out-of-scope requests, safety and verification, over-reliance and copying, holding a position, admitting uncertainty, false premises, price requests, scale-up, burning of plastic, vague input, Pidgin code-switching.
- **Automatic checks:** no invented numbers or shelf-life claims, regulators mentioned only when relevant, no duplicates, length within 768 tokens.
- **Splits are by product.** Held-out products: shea butter and black soap (test); liquid soap, smoked fish, soy milk (validation).

## Intended use
Research and teaching demonstration for packaging coaching. Not a source of regulatory or legal advice.

## Limitations and risks
- Synthetic text: it can sound repetitive and templated.
- Product facts and cost tiers are simplified and have **not been fully verified by a packaging expert** (review CSVs are provided for this).
- Pidgin-English dialogues need a native-speaker check.
- Regulator names (Ghana FDA, Ghana Standards Authority) are named for pointing students to the right body only; rules change and nothing here certifies compliance.
- Limited to 32 products and Ghana-specific context.
