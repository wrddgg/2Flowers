---
name: "wanwu-flower-core"
description: "Translates visual input plus user intent into bouquet concepts, remake previews, and shareable floral outputs. Invoke when a user wants to turn an image, scene, mood, or portrait into floral expression."
---

# Wanwu Flower Core

`wanwu-flower-core` is the product-level orchestration skill for `万物生花`.

Use this skill when the user wants to:

- turn an image, scene, portrait, abstract artwork, or mood into a bouquet
- continue from bouquet generation into editing, remake, tutorial, or sharing
- ask for the `万物生花` full workflow instead of a single isolated backend API
- get a product-consistent floral interpretation instead of generic image generation

Do not use this skill for:

- generic code review or bug fixing
- unrelated image generation tasks
- workflows that are not meant to follow the `万物生花` product logic

## Core Product Promise

This skill does **not** treat the task as plain "generate a flower image".

It treats the task as:

1. understand why an input feels meaningful
2. translate that feeling into floral language
3. keep the result explainable and editable
4. continue into remake, tutorial, and shareable outputs when needed

In short:

`视觉/语音输入 -> 感觉理解 -> 花艺表达 -> 现实承接 -> 结果沉淀`

## Invocation Checklist

Invoke this skill when at least one of the following is true:

- user explicitly asks to “把这个画面/感觉变成花”
- user wants bouquet generation based on image + voice intent
- user wants `万物生花`-style interpretation instead of object recognition
- user wants remake preview, bouquet card, tutorial, or share flow based on an earlier bouquet result
- user wants a reusable floral-expression agent workflow

## Routing Decision

Use `wanwu-flower-core` as the entry skill when the request spans multiple stages or the user is still speaking in product language.

Typical examples:

- “把这张图变成一束花”
- “先识别一下这个感觉，再给我三种花束方案”
- “基于刚才的结果继续做复刻、教程和分享”
- “我想把万物生花封装成一个完整 Agent 能力”

Prefer a child skill instead when the user is clearly asking for one stage only:

- only understand the input -> `wanwu-input-interpret`
- only generate bouquet variants -> `wanwu-bouquet-generate`
- only make a realistic remake brief -> `wanwu-remake-plan`
- only produce tutorial/share/card outputs -> `wanwu-share-workflow`

## Workflow

### 1. Classify the input

First determine what kind of input this is:

- `scene`: atmosphere, environment, event, landscape, installation, stage, abstract scene
- `flower`: bouquet or floral work itself
- `life`: relationship, gift context, real-life occasion, mixed emotional situation
- `portrait`: person-focused image, selfie, styled portrait, camera-driven mood
- `abstract-tech`: abstract art, digital stage, countdown screen, neon installation, technology event

Important:

- `portrait` is a product interpretation lens, even if the backend mode remains `life`
- `abstract-tech` is a planning lens, usually built on top of `scene`

### 2. Extract product-relevant semantics

Always prioritize the semantics that help floral translation, not generic captioning.

Focus on:

- `dominant_color_palette`: 1-2 major colors that occupy most of the image
- emotional tone
- scene semantics
- relationship or occasion semantics
- portrait temperament, makeup tone, camera distance, light quality
- whether the image needs multiple interpretation options

Rules:

- for abstract inputs, do **not** force concrete object guesses
- for technology-event inputs, prefer concrete scene semantics like launch, stage, neon, exhibition, future, installation
- for portrait inputs, extract mood and styling, not the literal person identity

### 3. Decide reference strength

Reference is optional. It is not always beneficial.

Use **weak or no reference** when:

- the input is abstract art
- the input is a technology-event / abstract-tech scene
- the input is portrait-driven and the key value is temperament transfer
- available references are clearly mismatched

Use reference only when it genuinely stabilizes floral structure or packaging direction.

Never force reference usage just because reference assets exist.

## Bouquet Generation Rules

### 4. Generate 3 clearly different bouquet directions

The default expectation is 3 bouquet variants with meaningful differentiation.

Each variant should expose:

- bouquet image
- title
- summary / explanation
- fit scenes
- usage goal
- reality advice
- flower anchor information for editing

### 5. Enforce floral structure simplicity

Unless a stronger product constraint overrides it, keep bouquet composition manageable:

- use four floral roles where possible:
  - main flowers
  - transition flowers
  - accent flowers
  - linear flowers
- keep each role to 1-2 species
- keep total major species around 4-6
- keep bouquet explainable and remake-friendly

### 6. Map dominant color to main flowers

When dominant colors are strong, especially for abstract inputs:

- align major bouquet color blocks with `dominant_color_palette`
- let main flowers carry the main color relationship
- avoid drifting into unrelated warm/cute/homey defaults if the input is clearly futuristic or theatrical

### 7. Strict no-person policy

This is a hard rule.

Generated bouquet results must not contain:

- people
- faces
- hands
- body parts
- silhouettes
- reflections of people
- poster people
- statue-like human figures
- outfit fragments
- photography props that read as a human presence

Even when the input is portrait-based, the output should translate the **temperament**, not render the person.

## Specialized Templates

### Abstract-Tech Template

Use this template when the input feels like:

- launch event
- countdown screen
- stage lighting
- neon installation
- digital exhibition
- futuristic abstract visual

Default behavior:

- weak or disable references
- prefer `现代艺术`
- prefer `庆祝纪念`
- avoid `窗边 / 雨后 / 居家治愈 / 桌花` type defaults
- titles and summaries should lean toward neon, pulse, installation, future, release, celebration

### Portrait Template

Use this template when the input is driven by:

- portrait photography
- selfie temperament
- styling mood
- makeup tone
- controlled camera intimacy

Default behavior:

- weak or disable references
- extract makeup palette, camera mood, posture restraint, emotional distance
- translate the portrait into floral temperament
- never include the person in the generated bouquet image

## Remake and Reality Continuation

### 8. Remake is not a downgrade; it is a translation

When the user moves into remake:

- preserve the bouquet's key visual signature
- generate a realistic communication preview for flower-shop customization
- expose a structured remake plan
- keep similarity reasonably high

Current product policy:

- similarity takes priority over over-strict realism
- seasonality may be softened if it hurts resemblance too much
- budget can reduce stem count and species complexity, but should not destroy the core look

## Editing, Tutorial, and Share

### 9. Editing

If editing is requested:

- use flower anchors as IDs for user interaction
- prefer recognized anchors over static template points
- keep explanations aligned with the current bouquet result

### 10. Tutorial

If tutorial is requested:

- produce step-by-step instructions
- require tutorial images to look like realistic floral teaching steps
- allow fallback text when tutorial images are not reliable

### 11. Share

If share is requested:

- treat source input, AI bouquet, and user remake as a coherent comparison story
- preserve scene reason and narrative explanation

## Preferred Backend Mapping

When the current `万物生花` backend is available, this skill should prefer these stages:

1. `POST /api/input/analyze`
2. optional `POST /api/reference/search`
3. `POST /api/bouquet/generate`
4. optional bouquet editing routes
5. `POST /api/emotion/build`
6. `POST /api/emotion/remake-preview`
7. tutorial and share workflow routes
8. runtime cache routes when progress recovery is needed

## Recommended Execution Order

For a full workflow, prefer this sequence:

1. interpret the source through `wanwu-input-interpret`
2. generate bouquet variants through `wanwu-bouquet-generate`
3. if user chooses one direction, continue into editing or remake
4. use `wanwu-remake-plan` for florist-facing reconstruction
5. use `wanwu-share-workflow` for tutorial, comparison, and presentation outputs

Do not skip straight to remake or sharing when the bouquet direction has not been made explicit yet.

## Stage Handoff Contract

When orchestrating across child skills, preserve these fields whenever available:

- `input_mode`
- `dominant_color_palette`
- `semantic_summary`
- `reference_strategy`
- `selected_reference_ids`
- `bouquet_variants`
- `selected_variant_id`
- `flowers` or recognized flower anchors
- `remake_plan`
- tutorial/share asset status fields

The goal is to keep the workflow explainable across stages instead of regenerating hidden assumptions each time.

## Example Full-Workflow Requests

Examples that should normally invoke this top-level skill:

- “这是一张科技展板，帮我转成花束，并继续给我复刻方案。”
- “这是一个人像拍摄作品，先分析气质，再出 3 束花，最后做分享卡文案。”
- “我想把这段情绪做成花，并且要后面能编辑、能出教程。”

## Example Full-Workflow Output

```json
{
  "input_mode": "portrait",
  "dominant_color_palette": ["dusty pink", "soft brown"],
  "reference_strategy": "none",
  "bouquet_variants": [
    {
      "variant_id": "plan_camera_persona",
      "title": "Camera Persona",
      "summary": "Translates restrained portrait intimacy into a bouquet with soft focal flowers and controlled wrapping.",
      "flowers": [{"id": "main_rose_blush", "name": "rose", "role": "main"}]
    }
  ],
  "selected_variant_id": "plan_camera_persona",
  "remake_plan": {
    "estimated_stem_range": "10-14",
    "composition_note": "Keep the silhouette upright and intimate rather than fully spread."
  },
  "share_assets": {
    "card_title": "From Portrait Mood To Bouquet",
    "image_status": "done"
  }
}
```

## Output Quality Standard

The result should feel like a `万物生花` product response, not a generic AI answer.

That means:

- clear interpretation
- clear stylistic direction
- restrained and coherent bouquet structure
- no accidental people in bouquet images
- room for editing, remake, tutorial, and sharing

## Child Skills

This orchestration skill now delegates to these child skills when the task is focused enough:

- `wanwu-input-interpret`
- `wanwu-bouquet-generate`
- `wanwu-remake-plan`
- `wanwu-share-workflow`

Use `wanwu-flower-core` when the user wants the full product workflow or has not yet narrowed the task to one stage.
