---
name: "wanwu-share-workflow"
description: "Packages bouquet results into tutorials, comparison stories, and shareable outputs. Invoke when a floral workflow needs cards, teaching steps, or presentation-ready narrative assets."
---

# Wanwu Share Workflow

`wanwu-share-workflow` is the presentation and continuation skill for `万物生花`.

Use this skill when the user wants to:

- turn bouquet results into tutorial steps
- create share cards or comparison outputs
- present source input, AI bouquet, and remake as one story
- prepare product-style outputs for demo, review, or social sharing

Typical requests include:

- “把这次结果整理成一个分享卡。”
- “我需要给评委展示这条链路，帮我包装成成品故事。”
- “给我教程步骤和配套文案。”
- “把原图、AI 花束和复刻图做成一页可讲的材料。”

Do not use this skill when the task is mainly:

- interpreting the source input
- generating bouquet variants
- building the remake plan itself

## Goal

This skill packages the workflow result so it can be understood, taught, and shared.

It should preserve the product narrative:

`原始触发 -> AI 理解 -> 花束表达 -> 现实承接 -> 成果展示`

## Tutorial Workflow

When tutorial output is requested:

- produce step-by-step floral guidance
- keep steps believable for real floral making
- make each step visually and semantically distinct
- allow text fallback when generated tutorial images are unreliable

Important:

- a missing tutorial image should not collapse the full tutorial
- fallback should still preserve stage meaning
- each step should sound like floral teaching, not generic decoration advice

## Share Card Workflow

When share output is requested:

- treat the source input, AI bouquet result, and remake result as one coherent comparison story
- keep the explanation tied to why the bouquet matches the source
- preserve the user's emotional or scene trigger

Useful share elements include:

- source image
- bouquet image
- remake or edited result
- short reason summary
- scene-fit explanation

Prefer preserving these keys or equivalent concepts:

- `card_title`
- `story_summary`
- `source_image`
- `bouquet_image`
- `remake_image`
- `tutorial_steps`
- `image_status`
- `fallback_copy`

## Product Narrative Rule

The share result should explain more than visual beauty.

It should communicate:

- what was interpreted
- how that became flowers
- why this bouquet direction fits
- how it can be remade or continued

## Writing Style

Prefer:

- concise, memorable titles
- product-demo-friendly summaries
- clear comparison language
- confident but not exaggerated explanation

Avoid:

- empty poetic filler
- generic AI art captions
- summaries that ignore the source trigger

## Backend Mapping

When the current backend is available, this skill should prefer:

1. tutorial workflow routes
2. share card or comparison asset routes
3. runtime cache routes when shareable records need to be recovered later

This stage should reuse upstream outputs instead of reinterpreting the source from scratch.

## Fallback Policy

This skill should explicitly tolerate partial failure.

For example:

- tutorial text can remain available when tutorial image generation falls back
- share narrative can proceed when some visual assets are delayed
- state should remain explainable through status fields such as `done`, `fallback`, `skipped`, or `failed` when the backend provides them

## Example

Example user request:

- “把原图、AI 花束和复刻方案整理成一页能给评委讲的分享材料。”

Example stage output:

```json
{
  "card_title": "From Neon Stage To Bouquet",
  "story_summary": "The source image was interpreted as a future-facing launch scene, then translated into a modern floral direction with strong blue-violet contrast.",
  "source_image": "/uploads/source.jpg",
  "bouquet_image": "/uploads/bouquet.jpg",
  "remake_image": "/uploads/remake.jpg",
  "tutorial_steps": [
    "Set the blue-violet focal flowers first.",
    "Build vertical movement with line flowers.",
    "Compress filler volume to preserve negative space."
  ],
  "image_status": "fallback",
  "fallback_copy": "Tutorial text is available even though one visual step is still being regenerated."
}
```

## Success Standard

This skill is successful when another person can understand the product value of the result quickly, even without watching the full generation process.

## Quality Standard

A strong output from this skill should:

- be presentation-ready
- keep the bouquet story understandable at a glance
- remain useful even when some generated assets degrade
- feel like a polished `万物生花` product artifact instead of raw generation output
