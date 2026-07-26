---
name: "wanwu-input-interpret"
description: "Interprets image, mood, scene, or portrait input into bouquet-ready semantics. Invoke when a floral workflow needs product-style semantic understanding before generation."
---

# Wanwu Input Interpret

`wanwu-input-interpret` is the semantic understanding skill for `万物生花`.

Use this skill when the user wants to:

- turn an image, mood, scene, portrait, or abstract artwork into bouquet-readable meaning
- understand what should be extracted before floral generation
- classify a difficult input into the right product lens
- decide whether reference search should be used, weakened, or skipped

Typical requests include:

- “先别生图，先告诉我这张图适合怎么理解成花。”
- “这张抽象画应该提取什么关键信息？”
- “这张人像拍摄图适合什么花艺方向？”
- “这类科技展演图是不是不该走参考图库？”

Do not use this skill when the main task is already clearly about:

- generating bouquet variants
- producing a remake plan
- creating tutorial or share outputs
- generic image captioning unrelated to floral translation

## Goal

This skill does not aim to describe everything in the image.

It aims to extract the parts that help floral expression:

- dominant colors
- emotional tone
- scene semantics
- portrait temperament
- occasion or relationship meaning
- ambiguity that should trigger multiple interpretation options

## Input Lenses

Classify the input into one or more of these lenses:

- `scene`: environment, event, atmosphere, installation, stage, abstract scene
- `flower`: an existing bouquet or floral work
- `life`: gifting, relationship, memory, occasion, mixed real-life context
- `portrait`: person-centered image where the value is mood, styling, and camera feeling
- `abstract-tech`: abstract art, digital exhibition, countdown screen, neon event, tech-stage visual

Important:

- `portrait` is about translating temperament, not keeping the literal person
- `abstract-tech` is about reading stage energy, neon rhythm, and future-facing semantics

## Extraction Priorities

Always prioritize bouquet-relevant semantics over generic recognition.

Extract:

- `dominant_color_palette`: 1-2 colors that occupy most of the image
- emotional keywords that meaningfully affect floral tone
- scene or occasion cues that affect bouquet direction
- if portrait-driven: makeup palette, light quality, camera distance, emotional restraint
- if flower-driven: structure, material hierarchy, silhouette, color balance

## Rules For Difficult Inputs

### Abstract Inputs

When the image is abstract, texture-led, or color-block-led:

- do not force concrete object guesses
- first summarize the dominant color relationship
- then describe motion, density, rhythm, temperature, and emotional texture

### Technology Or Stage Inputs

When the image feels like a launch, countdown, exhibition, or digital stage:

- prefer concrete words like stage, release, neon, installation, countdown, pulse, future
- avoid drifting into generic healing, home, rainy-window, or tabletop semantics

### Portrait Inputs

When the source is a portrait, selfie, or strong camera-led image:

- extract the person's presented temperament, not their identity
- focus on styling, palette, light, emotional distance, and pose restraint
- prepare semantics for transformation into flowers
- never preserve the human figure as an output requirement

## Reference Strategy Decision

This skill should explicitly decide whether references help.

Use weak or no reference when:

- the input is abstract
- the input is `abstract-tech`
- the input is portrait-led and temperament transfer matters more than bouquet imitation
- the reference pool is obviously mismatched

Use reference when:

- the user wants closer floral structure
- the input is already bouquet-like
- packaging, structure, or silhouette stability matters

## Ambiguity Handling

Offer multiple interpretation directions when the input could reasonably map to different bouquet meanings.

Examples:

- abstract image: color-led vs emotion-led
- portrait: palette-led vs temperament-led
- scene: celebration-led vs memory-led

The purpose is not indecision. The purpose is to keep later bouquet generation explainable.

## Expected Output Shape

This skill should leave behind a bouquet-ready interpretation with:

- input lens
- 1-2 dominant colors
- emotional and scene summary
- whether references should be used
- whether multiple generation directions are needed
- special warnings such as strict no-person carryover

Prefer preserving these keys or equivalent concepts:

- `input_mode`
- `dominant_color_palette`
- `semantic_summary`
- `emotion_tags`
- `scene_tags`
- `reference_strategy`
- `needs_multi_direction`
- `special_warnings`

## Backend Mapping

When the current backend is available, this skill should usually map to:

1. `POST /api/input/analyze`
2. optional `POST /api/reference/search` only after deciding references are truly helpful

The interpretation step should happen before reference retrieval strategy is finalized, not after.

## Handoff To Next Stage

This skill hands off to `wanwu-bouquet-generate`.

The next stage should be able to answer:

- what kind of input this is
- which 1-2 colors matter most
- what emotional or scene tension should be preserved
- whether reference should be used, weakened, or disabled
- whether one generation direction is enough or multiple variants are needed

## Example

Example user request:

- “先别生图，先帮我判断这张科技感海报应该怎么理解成花。”

Example stage output:

```json
{
  "input_mode": "abstract-tech",
  "dominant_color_palette": ["electric blue", "violet"],
  "semantic_summary": "A future-facing launch-stage mood with neon pulse, countdown tension, and immersive light energy.",
  "emotion_tags": ["excited", "tense", "celebratory"],
  "scene_tags": ["stage", "countdown", "installation", "launch"],
  "reference_strategy": "none",
  "needs_multi_direction": true,
  "special_warnings": ["strict_no_person_carryover", "avoid_homey_aesthetics"]
}
```

## Success Standard

This skill is successful when bouquet generation no longer needs to guess the product meaning of the source.

## Quality Bar

Good output from this skill should make the next stage easier to execute:

- bouquet generation gets clearer style anchors
- abstract inputs stop being over-literalized
- portrait inputs stop leaking human imagery into bouquet outputs
- technology scenes stop collapsing into old homey aesthetics
