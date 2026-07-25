from __future__ import annotations

import json
import os
import re
import shutil
from pathlib import Path

import httpx

from app.config.env import load_environment
from app.repositories.content_repository import get_content_repository
from app.schemas.bouquet import GenerateBouquetRequest
from app.schemas.input import AnalyzeInputRequest, SelectionBox
from app.schemas.mode import ModeResult
from app.services.image_generation_provider import ApiImageGenerationProvider, _resolve_planner_client_config
from app.services.reference_retriever import ReferenceRetriever
from app.services.semantic_recognizer import (
    ApiSemanticRecognizer,
    _build_mock_detected_elements,
    _build_mock_interpretation_options,
    _build_mock_planner_summary,
    _clamp_confidence,
    _normalize_mode,
    _pick_recommended_interpretation,
)
from app.utils.image_assets import to_provider_image_input


def _parse_json_object(content: str) -> dict:
    content = content.strip()
    if not content:
        return {}
    try:
        return json.loads(content)
    except json.JSONDecodeError:
        pass
    match = re.search(r"\{.*\}", content, flags=re.DOTALL)
    if not match:
        return {}
    try:
        return json.loads(match.group(0))
    except json.JSONDecodeError:
        return {}


def _build_markdown_report(snapshot: dict, report_root: Path) -> str:
    assets = snapshot["assets"]
    analyze = snapshot["analyze"]
    planner = snapshot["planner"]
    generation = snapshot["generation"]
    references = snapshot["reference_search"]["references"]

    def _link(rel_path: str) -> str:
        return rel_path.replace("\\", "/")

    lines: list[str] = [
        "# 场景识图与生花过程报告：窗边雨夜（含图版）",
        "",
        "## 1. 本次审阅范围",
        "",
        "本报告基于正式 API 重跑当前新版 prompt，覆盖以下阶段：",
        "",
        "- 场景识图",
        "- 参考检索",
        "- 生花规划",
        "- 分方案正式生图",
        "",
        "完整结构化快照见：",
        f"- [scene_window_rain_full_flow_snapshot.json]({_link('./scene_window_rain_full_flow_snapshot.json')})",
        "",
        "## 2. 图片对照",
        "",
        f"- 输入图：[input_scene_window_rain_01.png]({_link('./' + assets['input'])})",
    ]
    for idx, rel_path in enumerate(assets["references"], start=1):
        lines.append(f"- 参考图 {idx}：[reference_{idx}]({_link('./' + rel_path)})")
    for idx, rel_path in enumerate(assets["results"], start=1):
        lines.append(f"- 结果图 {idx}：[result_{idx}]({_link('./' + rel_path)})")

    lines.extend(
        [
            "",
            "## 3. 识图结果摘要",
            "",
            f"- `detected_mode`: `{analyze['normalized']['mode_result']['detected_mode']}`",
            f"- `confidence`: `{analyze['normalized']['mode_result']['confidence']}`",
            f"- `needs_user_choice`: `{analyze['normalized']['needs_user_choice']}`",
            f"- `recommended_interpretation_id`: `{analyze['normalized']['recommended_interpretation_id']}`",
            f"- 语义摘要：{analyze['normalized']['semantic_result']['semantic_summary']}",
            f"- 规划说明：{analyze['normalized']['planner_summary']}",
            "",
            "## 4. 阶段 Prompt",
            "",
            "### 4.1 识图 Prompt",
            "",
            "```text",
            analyze["prompt"],
            "```",
            "",
            "### 4.2 生花规划 Prompt",
            "",
            "```text",
            planner["prompt"],
            "```",
            "",
            "### 4.3 生图 Prompt",
            "",
        ]
    )

    for idx, item in enumerate(generation["prompts"], start=1):
        lines.extend(
            [
                f"#### 方案 {idx}：{item['title']} / {item['focus']}",
                "",
                "```text",
                item["prompt"],
                "```",
                "",
            ]
        )

    lines.extend(
        [
            "## 5. 参考检索结果",
            "",
        ]
    )
    for idx, ref in enumerate(references, start=1):
        lines.extend(
            [
                f"### 参考 {idx}",
                "",
                f"- 标题：`{ref['title']}`",
                f"- `reference_id`: `{ref['reference_id']}`",
                f"- score: `{ref['score']}`",
                f"- reason: {ref['reason']}",
                f"- 匹配标签：`{' / '.join(ref['matched_tags'])}`",
                "",
            ]
        )

    lines.extend(
        [
            "## 6. 规划结果",
            "",
            f"- 规划模型：`{planner.get('model', '')}`",
        ]
    )
    if planner.get("error"):
        lines.extend(
            [
                f"- 规划调用异常：`{planner['error']}`",
                "",
            ]
        )
    for idx, plan in enumerate(planner["plan_used"], start=1):
        lines.extend(
            [
                f"### 规划方案 {idx}",
                "",
                f"- 标题：`{plan['title']}`",
                f"- focus：`{plan['focus']}`",
                f"- reference_strategy：`{plan['reference_strategy']}`",
                f"- composition_style：`{plan.get('composition_style', '')}`",
                f"- material_richness：`{plan.get('material_richness', '')}`",
                f"- species_count_cap：`{plan.get('species_count_cap', '')}`",
                f"- dominant_flower_ratio：`{plan.get('dominant_flower_ratio', '')}`",
                f"- color_strategy：`{plan.get('color_strategy', '')}`",
                f"- bouquet_density：`{plan.get('bouquet_density', '')}`",
                f"- 指令：{plan['prompt_directive']}",
                "",
            ]
        )

    lines.extend(
        [
            "## 7. 结果图索引",
            "",
        ]
    )
    for idx, result in enumerate(generation["results"], start=1):
        lines.extend(
            [
                f"### 结果图 {idx}",
                "",
                f"- 图片：[result_{idx}]({_link('./' + assets['results'][idx - 1])})",
                f"- 标题：`{result['title']}`",
                f"- generation_focus：`{result.get('generation_focus', '')}`",
                f"- summary：{result['summary']}",
                "",
            ]
        )
    return "\n".join(lines) + "\n"


def main() -> None:
    load_environment()
    report_root = Path(__file__).resolve().parent
    assets_dir = report_root / "full_flow_assets"
    assets_dir.mkdir(parents=True, exist_ok=True)

    repo = get_content_repository()
    recognizer = ApiSemanticRecognizer()
    retriever = ReferenceRetriever()
    provider = ApiImageGenerationProvider()

    request = AnalyzeInputRequest(
        content_id="scene_window_rain",
        image_url="/library/assets/scene_window_rain_01.png",
        selection_box=SelectionBox(x=12, y=16, width=180, height=140),
        voice_text="想把这个画面的安静和轻治愈感，变成一束可以送朋友的花。",
    )
    content_profile = repo.get_content_or_asset_profile(request.content_id, request.image_url)
    contract = recognizer.build_api_request(request, content_profile)
    analyze_prompt = recognizer._build_prompt(contract)

    base_url = os.getenv("SEMANTIC_API_URL") or os.getenv("QWEN_BASE_URL")
    api_key = os.getenv("SEMANTIC_API_KEY") or os.getenv("DASHSCOPE_API_KEY")
    model = os.getenv("SEMANTIC_MODEL") or os.getenv("QWEN_VL_MODEL") or "qwen-vl-max"
    if not base_url or not api_key:
        raise RuntimeError("缺少正式语义识别配置。")

    analyze_payload = {
        "model": model,
        "messages": [
            {
                "role": "system",
                "content": recognizer._system_prompt(),
            },
            {
                "role": "user",
                "content": [
                    {"type": "image_url", "image_url": {"url": to_provider_image_input(contract.image_url)}},
                    {"type": "text", "text": analyze_prompt},
                ],
            },
        ],
        "temperature": 0.1,
    }
    endpoint = f"{base_url.rstrip('/')}/chat/completions"
    with httpx.Client(timeout=120.0) as client:
        analyze_response = client.post(
            endpoint,
            headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
            json=analyze_payload,
        )
        analyze_response.raise_for_status()
    raw_analyze = analyze_response.json()
    raw_analyze_content = recognizer._extract_message_text(raw_analyze)
    parsed_analyze = recognizer._parse_json_object(raw_analyze_content)

    fallback_mode = str(content_profile.get("base_mode", "scene"))
    interpretation_options = recognizer._normalize_interpretation_options(
        parsed_analyze.get("interpretation_options"),
        fallback_mode=fallback_mode,
        content_profile=content_profile,
        request=contract,
    )
    recommended_id = str(parsed_analyze.get("recommended_interpretation_id") or "").strip() or None
    recommended = _pick_recommended_interpretation(interpretation_options, recommended_id)
    primary_payload = recommended.semantic_result.model_dump() if recommended else parsed_analyze
    detected_mode = _normalize_mode(
        recommended.recommended_mode if recommended else parsed_analyze.get("mode"),
        fallback_mode,
    )
    mode_result = ModeResult(
        detected_mode=detected_mode,
        confidence=_clamp_confidence(parsed_analyze.get("confidence"), fallback=0.82),
        evidence=recognizer._normalize_tags(parsed_analyze.get("evidence"), ["multimodal_api"])[:4]
        or ["multimodal_api"],
    )
    semantic_result = recognizer._normalize_semantic_result(
        values=primary_payload,
        detected_mode=detected_mode,
        content_profile=content_profile,
        request=contract,
        fallback_text=raw_analyze_content,
    )
    detected_elements = recognizer._normalize_detected_elements(parsed_analyze.get("detected_elements"))
    if not detected_elements:
        detected_elements = _build_mock_detected_elements(detected_mode, request.voice_text, content_profile)
    if not interpretation_options:
        interpretation_options = _build_mock_interpretation_options(mode_result, semantic_result, detected_elements)
    planner_summary = str(parsed_analyze.get("planner_summary") or "").strip() or _build_mock_planner_summary(
        interpretation_options
    )

    reference_candidates = repo.list_reference_candidates(detected_mode)
    references = retriever.search(
        references=reference_candidates,
        mode=detected_mode,
        semantic_result=semantic_result,
        semantic_tags=[],
        limit=3,
        excluded_reference_ids=[],
    )
    selected_reference_ids = [item.reference_id for item in references[:1]]
    selected_interpretation_label = recommended.label if recommended else None

    generate_request = GenerateBouquetRequest(
        mode=detected_mode,
        semantic_result=semantic_result,
        reference_strategy="light",
        selected_reference_ids=selected_reference_ids,
        creative_mode="mixed",
        generation_goals=["贴近当前场景解读", "三张图侧重点明确", "避免直接复制参考花束"],
        selected_interpretation_label=selected_interpretation_label,
    )
    image_contract = provider.build_api_request(
        request=generate_request,
        bouquet_templates=repo.list_bouquet_templates(detected_mode),
        reference_map=repo.get_reference_map(),
    )

    planner_prompt = provider._build_variant_planner_prompt(image_contract)
    planner_base_url, planner_api_key, planner_model = _resolve_planner_client_config()
    planner_endpoint = f"{(planner_base_url or base_url).rstrip('/')}/chat/completions"
    planner_payload = {
        "model": planner_model,
        "messages": [
            {"role": "system", "content": provider._planner_system_prompt()},
            {"role": "user", "content": planner_prompt},
        ],
        "temperature": 0.4,
    }
    planner_error = ""
    parsed_planner: dict[str, object] = {}
    planner_content = ""
    try:
        with httpx.Client(timeout=120.0) as client:
            planner_response = client.post(
                planner_endpoint,
                headers={"Authorization": f"Bearer {(planner_api_key or api_key)}", "Content-Type": "application/json"},
                json=planner_payload,
            )
            planner_response.raise_for_status()
        raw_planner = planner_response.json()
        planner_content = raw_planner["choices"][0]["message"]["content"]
        if isinstance(planner_content, list):
            planner_content = "".join(str(item.get("text", "")) for item in planner_content if isinstance(item, dict))
        planner_content = str(planner_content)
        parsed_planner = _parse_json_object(planner_content)
    except httpx.HTTPError as exc:
        planner_error = str(exc)
        planner_content = f"planner_call_failed: {exc}"

    variant_plans = provider._resolve_variant_plans(image_contract)
    generate_request = generate_request.model_copy(update={"variant_plans": variant_plans})
    results, plan_used = provider.generate(
        request=generate_request,
        bouquet_templates=repo.list_bouquet_templates(detected_mode),
        reference_map=repo.get_reference_map(),
    )

    input_src = Path(r"e:\Hackthon\大区赛\images\scene_window_rain_01.png")
    if input_src.exists():
        shutil.copy2(input_src, assets_dir / "input_scene_window_rain_01.png")

    reference_files: list[str] = []
    for idx, ref in enumerate(references[:3], start=1):
        name = ref.cover_url.split("/")[-1]
        src = Path(r"e:\Hackthon\大区赛\images") / name
        if src.exists():
            target = assets_dir / f"reference_{idx}_{name}"
            shutil.copy2(src, target)
            reference_files.append(target.name)

    result_files: list[str] = []
    with httpx.Client(timeout=300.0, follow_redirects=True) as client:
        for idx, result in enumerate(results, start=1):
            response = client.get(result.image_url)
            response.raise_for_status()
            target = assets_dir / f"result_{idx}.png"
            target.write_bytes(response.content)
            result_files.append(target.name)

    final_contract = provider.build_api_request(
        request=generate_request,
        bouquet_templates=repo.list_bouquet_templates(detected_mode),
        reference_map=repo.get_reference_map(),
    )
    generation_prompts = [
        {
            "variant_id": variant.variant_id,
            "title": variant.title,
            "focus": variant.focus,
            "prompt": provider._build_generation_prompt(final_contract, variant),
        }
        for variant in plan_used
    ]

    snapshot = {
        "analyze": {
            "request": request.model_dump(),
            "prompt": analyze_prompt,
            "raw_model_content": raw_analyze_content,
            "parsed_model_json": parsed_analyze,
            "normalized": {
                "mode_result": mode_result.model_dump(),
                "semantic_result": semantic_result.model_dump(),
                "detected_elements": [item.model_dump() for item in detected_elements],
                "needs_user_choice": bool(parsed_analyze.get("needs_user_choice")) and len(interpretation_options) > 1,
                "interpretation_options": [item.model_dump() for item in interpretation_options],
                "planner_summary": planner_summary,
                "recommended_interpretation_id": recommended.option_id if recommended else recommended_id,
            },
        },
        "reference_search": {
            "references": [item.model_dump() for item in references],
        },
        "planner": {
            "model": planner_model,
            "prompt": planner_prompt,
            "error": planner_error,
            "raw_model_content": planner_content,
            "parsed_model_json": parsed_planner,
            "plan_used": [item.model_dump() for item in plan_used],
        },
        "generation": {
            "request": generate_request.model_dump(),
            "prompts": generation_prompts,
            "results": [item.model_dump() for item in results],
        },
        "assets": {
            "input": "full_flow_assets/input_scene_window_rain_01.png",
            "references": [f"full_flow_assets/{name}" for name in reference_files],
            "results": [f"full_flow_assets/{name}" for name in result_files],
        },
    }
    output = report_root / "scene_window_rain_full_flow_snapshot.json"
    output.write_text(json.dumps(snapshot, ensure_ascii=False, indent=2), encoding="utf-8")
    markdown = _build_markdown_report(snapshot, report_root)
    (report_root / "场景识图与生花过程报告_窗边雨夜_含图版.md").write_text(markdown, encoding="utf-8")
    print(
        json.dumps(
            {
                "saved_snapshot": str(output),
                "saved_markdown": str(report_root / "场景识图与生花过程报告_窗边雨夜_含图版.md"),
                "references": [item.title for item in references],
                "plans": [item.title for item in plan_used],
                "result_files": result_files,
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
