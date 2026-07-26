---
name: "wanwu-bouquet-generate"
description: "Generates bouquet concepts and variants from interpreted semantics. Invoke when a floral workflow needs explainable bouquet directions rather than generic image generation."
---

# Wanwu Bouquet Generate

`wanwu-bouquet-generate` is the bouquet creation skill for `万物生花`.

Use this skill when the user wants to:

- turn interpreted image semantics into bouquet variants
- get multiple bouquet directions with clear differences
- preserve `万物生花` product style instead of generic flower rendering
- generate bouquet outputs that stay editable, explainable, and remake-friendly

Typical requests include:

- “根据刚才的识别结果直接给我三束花。”
- “不要泛泛的图，给我三种真正不同的花艺方向。”
- “这张科技图不要走居家审美，直接出花束方案。”
- “先给我可编辑、后面还能复刻的花束版本。”

Do not use this skill when the task is mainly:

- understanding the source input
- building a realistic remake procurement plan
- producing tutorial steps or share cards

## Goal

This skill converts bouquet-ready semantics into floral proposals that feel intentional and product-grade.

The output should not be "a nice flower image".

It should be:

- visually coherent
- clearly named
- emotionally explainable
- structurally manageable
- compatible with later editing and remake

## Required Inputs

Before running this skill, gather or assume:

- input lens from interpretation
- `dominant_color_palette` if applicable
- emotion or scene summary
- reference strategy decision
- any user constraints on scene, style, price, or gifting meaning

If those are missing, first use `wanwu-input-interpret`.

## Core Generation Rule

Default expectation: produce 3 bouquet variants with real differentiation.

Each variant should differ in a meaningful way, such as:

- color emphasis
- silhouette
- emotional tension
- packaging direction
- realism vs expressiveness balance

Do not generate 3 near-duplicates with shallow renaming.

## Composition Simplicity

Prefer a restrained structure that supports later recognition and remake:

- four floral roles where possible:
  - main flowers
  - transition flowers
  - accent flowers
  - linear flowers
- keep each role to about 1-2 species
- keep the bouquet explainable
- avoid uncontrolled material explosion

This is a product decision, not just an aesthetic preference.

## Color Mapping Rule

When the interpreted input includes strong dominant colors:

- let the main flowers carry the main color relationship
- keep secondary materials supportive, not distracting
- preserve the input's first-impression color logic

Especially for abstract and `abstract-tech` inputs:

- do not drift into unrelated cute, pastel, homey defaults
- keep the bouquet aligned with the extracted palette and atmosphere

## Reference Use

Reference is optional and should be treated as a stabilizer, not a dependency.

Disable or weaken reference when:

- input is abstract
- input is `abstract-tech`
- input is portrait-led
- reference assets would drag the style into the wrong aesthetic

Use reference when:

- bouquet structure needs stabilization
- packaging language benefits from examples
- the user explicitly wants closer floral resemblance

## Hard No-Person Constraint

This is a strict product rule.

The generated bouquet result must not contain:

- people
- faces
- hands
- hair
- skin
- silhouettes
- human reflections
- posters with people
- statues or dolls that read as people
- outfit fragments

Even when the input is portrait-based, only the temperament transfers.

## Specialized Templates

### Abstract-Tech

When the input reads as stage, neon, countdown, exhibition, or future-facing abstract energy:

- prefer a modern-art bouquet direction
- titles and summaries should lean toward pulse, installation, release, neon, celebration, future
- avoid rainy-window, tabletop, home-healing defaults
- reference should usually be weak or disabled

### Portrait

When the input reads as portrait photography or styling mood:

- translate makeup palette, camera intimacy, restraint, and emotional posture into flowers
- keep the bouquet giftable or displayable
- never reproduce the human figure or styling props directly

## Variant Content

Each bouquet variant should ideally expose:

- title
- summary
- bouquet image or image plan
- fit scenes
- why it matches the input
- editable flower-anchor context when available
- reality hints for later remake

Prefer preserving these keys or equivalent concepts:

- `variant_id`
- `title`
- `summary`
- `fit_scenes`
- `image_url` or image result
- `flowers`
- `planned_flowers`
- `recognized_flowers`
- `flower_recognition_status`
- `reality_advice`

## Backend Mapping

When the current backend is available, this skill should usually map to:

1. optional `POST /api/reference/search`
2. `POST /api/bouquet/generate`
3. optional bouquet editing routes if the user wants local modification after choosing a variant

Only call reference search if the previous interpretation stage decided references are helpful.

## Handoff To Next Stage

This skill can hand off in two directions:

- to `wanwu-remake-plan` when the user wants a realistic florist-facing continuation
- to `wanwu-share-workflow` when the user wants tutorial, comparison, or presentation assets

If the user wants editing, keep flower-anchor data aligned with the chosen bouquet result before any later continuation.

## Example

Example user request:

- “根据刚才的识别结果，给我三种明显不同的花束方向。”

Example stage output:

```json
{
  "bouquet_variants": [
    {
      "variant_id": "plan_neon_field",
      "title": "Neon Field",
      "summary": "Uses electric blue and violet as the main floral blocks, with sharp silhouette and release-stage tension.",
      "fit_scenes": ["launch gift", "exhibition display"],
      "flowers": [{"id": "main_rose_blue", "name": "rose", "role": "main"}],
      "flower_recognition_status": "recognized"
    },
    {
      "variant_id": "plan_future_installation",
      "title": "Future Installation",
      "summary": "More sculptural and spatial, with stronger line flowers and cleaner negative space.",
      "fit_scenes": ["gallery", "brand event"],
      "flowers": [{"id": "main_lily_white", "name": "lily", "role": "main"}],
      "flower_recognition_status": "recognized"
    }
  ],
  "selected_reference_ids": [],
  "reference_strategy": "none"
}
```

## Success Standard

This skill is successful when the user can clearly choose between bouquet directions instead of seeing three decorative near-duplicates.

## Quality Standard

A strong bouquet generation result should:

- feel like a deliberate floral translation
- be easy to compare across 3 variants
- keep visual hierarchy clean
- stay within product-friendly material complexity
- preserve room for editing, remake, tutorial, and sharing

## Recommended Handoff

After this skill:

- use `wanwu-remake-plan` when the user wants realistic reconstruction or florist communication
- use `wanwu-share-workflow` when the user wants tutorials, cards, or narrative packaging
