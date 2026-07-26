---
name: "wanwu-remake-plan"
description: "Builds realistic remake guidance from a bouquet result. Invoke when a floral workflow needs florist-facing reconstruction advice, substitutions, or reality-aware preview planning."
---

# Wanwu Remake Plan

`wanwu-remake-plan` is the reality-translation skill for `万物生花`.

Use this skill when the user wants to:

- turn an AI bouquet result into a realistic remake direction
- communicate with a florist or physical maker
- understand substitutions, stem counts, packaging, or composition advice
- keep resemblance while adapting to budget or real-world availability

Typical requests include:

- “把这束 AI 花改成现实里能做的版本。”
- “我想拿去和花店沟通，给我一个复刻简报。”
- “预算有限，但尽量保持和原图像。”
- “告诉我哪些必须保留，哪些可以替换。”

Do not use this skill when the task is only:

- interpreting the source image
- generating the first bouquet variants
- creating tutorial or share outputs

## Goal

This skill turns "beautiful concept" into "actionable remake guidance".

The remake result should help a real florist or maker understand:

- what must be preserved
- what can be substituted
- what the bouquet should feel like in real life
- how budget and availability change the execution

## Input Assumptions

This skill should start from an existing bouquet direction or chosen bouquet result.

Useful inputs include:

- bouquet title and summary
- key flowers and color blocks
- structure or silhouette
- user budget
- delivery or gifting context
- any realism constraints

## Core Policy

Similarity is important.

Current `万物生花` policy is:

- preserve the bouquet's key visual signature
- do not over-sacrifice resemblance for rigid realism
- seasonality can be softened if it damages similarity too much
- budget should reduce complexity carefully, not destroy the core look

## What To Preserve

Always identify the signature elements first:

- main color relationship
- silhouette and volume
- focal flower impression
- emotional tone
- packaging attitude

These are the parts that define whether the remake still feels like the original.

## What Can Change

Adaptable layers may include:

- specific substitute flowers
- stem count compression
- supporting materials
- wrapping materials
- realism-friendly simplification

Substitutions should stay visually loyal before they become botanically perfect.

## Expected Output Shape

This skill should try to produce a florist-facing remake plan with:

- preserved signature summary
- recommended substitute logic
- `estimated_stem_range`
- `composition_note`
- `packaging_note`
- budget-aware guidance
- warnings when resemblance will noticeably drop

Prefer preserving these keys or equivalent concepts:

- `signature_summary`
- `must_keep_elements`
- `substitution_plan`
- `estimated_stem_range`
- `composition_note`
- `packaging_note`
- `budget_guidance`
- `similarity_risk`

## Backend Mapping

When the current backend is available, this skill should usually map to:

1. `POST /api/emotion/build`
2. `POST /api/emotion/remake-preview`

If bouquet selection has not happened yet, do not start this stage early.

## Handoff To Next Stage

This skill often hands off to `wanwu-share-workflow` when the user wants:

- a source-vs-bouquet-vs-remake comparison card
- demo-ready narrative packaging
- a presentation artifact for review or judging

## Example

Example user request:

- “把选中的这束 AI 花整理成能给花店沟通的复刻方案。”

Example stage output:

```json
{
  "signature_summary": "Keep the electric blue-violet color contrast, upright silhouette, and celebratory stage energy.",
  "must_keep_elements": [
    "blue-violet main color block",
    "clean upward silhouette",
    "modern wrapping tone"
  ],
  "substitution_plan": [
    {
      "from": "rare imported blue rose",
      "to": "tinted garden rose",
      "reason": "better availability while preserving the visual focal point"
    }
  ],
  "estimated_stem_range": "12-16",
  "composition_note": "Keep the center tight and lift the line flowers slightly backward.",
  "packaging_note": "Use matte charcoal or cool gray wrapping paper with minimal ribbon.",
  "budget_guidance": "Reduce secondary filler first; do not cut the main focal flowers.",
  "similarity_risk": "medium-low"
}
```

## Tone Of The Result

The result should read like a practical communication brief, not a vague art critique.

It should help a real person answer:

- what flowers should I prepare
- how many stems roughly
- what shape should I make
- what wrapping or presentation matters
- which parts are non-negotiable

## Editing Continuation

If the bouquet has flower-anchor data:

- keep remake explanations aligned with those recognized flowers
- prefer explainable substitutions over hidden substitutions

## Quality Standard

A strong remake plan should:

- keep resemblance high
- stay realistic enough to communicate
- be concise but actionable
- expose the tradeoff between fidelity and practicality
