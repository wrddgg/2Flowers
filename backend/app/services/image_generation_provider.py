from __future__ import annotations

import json
import os
import time
from functools import lru_cache
from typing import Any, Protocol

import httpx

from app.config.runtime import is_test_mode
from app.schemas.bouquet import BouquetResult, GenerateBouquetRequest, GenerationVariantPlan
from app.schemas.provider_api import (
    GeneratedBouquetImage,
    ImageGenerationApiRequest,
    ImageGenerationApiResponse,
    ImageGenerationConstraints,
    ProviderReferenceInput,
)
from app.services.bouquet_generator import BouquetGenerator
from app.utils.image_assets import to_provider_image_input
from app.utils.text import new_id


class ImageGenerationProvider(Protocol):
    def generate(
        self,
        request: GenerateBouquetRequest,
        bouquet_templates: list[dict[str, object]],
        reference_map: dict[str, dict[str, object]],
    ) -> tuple[list[BouquetResult], list[GenerationVariantPlan]]: ...


class MockImageGenerationProvider:
    def __init__(self) -> None:
        self.generator = BouquetGenerator()

    def generate(
        self,
        request: GenerateBouquetRequest,
        bouquet_templates: list[dict[str, object]],
        reference_map: dict[str, dict[str, object]],
    ) -> tuple[list[BouquetResult], list[GenerationVariantPlan]]:
        plan_used = request.variant_plans or self.generator_default_plan(request)
        return self.generator.generate(request, bouquet_templates, reference_map), plan_used

    def generator_default_plan(self, request: GenerateBouquetRequest) -> list[GenerationVariantPlan]:
        return [
            GenerationVariantPlan(
                variant_id="mock_atmosphere",
                title="氛围还原",
                focus="atmosphere",
                prompt_directive="优先还原输入里的情绪氛围、色调和空气感。",
                reference_strategy=request.reference_strategy,
                composition_style="mass",
                material_richness="single",
                species_count_cap=2,
                dominant_flower_ratio=0.82,
                color_strategy="single_tone",
                bouquet_density="dense",
            ),
            GenerationVariantPlan(
                variant_id="mock_premium",
                title="气质拔高",
                focus="premium",
                prompt_directive="优先提升成品气质与精致度，但保持原输入的核心感觉。",
                reference_strategy=request.reference_strategy,
                composition_style="layered",
                material_richness="limited",
                species_count_cap=3,
                dominant_flower_ratio=0.72,
                color_strategy="dual_tone",
                bouquet_density="medium",
            ),
            GenerationVariantPlan(
                variant_id="mock_symbolism",
                title="花语对齐",
                focus="symbolism",
                prompt_directive="优先强化花语、对象关系和象征意义的对齐。",
                reference_strategy=request.reference_strategy,
                composition_style="focal",
                material_richness="limited",
                species_count_cap=3,
                dominant_flower_ratio=0.68,
                color_strategy="accent",
                bouquet_density="medium",
            ),
        ]


class ApiImageGenerationProvider:
    """Alibaba Cloud Wan image-generation provider."""

    def _planner_system_prompt(self) -> str:
        return (
            "你是“万物生花”的花艺总监兼审美规划专家。"
            "你的职责不是把输入里的所有要素都保留下来，而是做有审美判断的删减与取舍。"
            "请像资深花艺总监一样，优先判断什么该被保留、什么该被忽略、什么该让位于整体画面。"
            "只输出严格 JSON。"
        )

    def build_api_request(
        self,
        request: GenerateBouquetRequest,
        bouquet_templates: list[dict[str, object]],
        reference_map: dict[str, dict[str, object]],
    ) -> ImageGenerationApiRequest:
        selected_references = []
        for reference_id in request.selected_reference_ids:
            reference = reference_map.get(reference_id)
            if not reference:
                continue
            selected_references.append(
                ProviderReferenceInput(
                    reference_id=str(reference["reference_id"]),
                    title=str(reference["title"]),
                    cover_url=str(reference["cover_url"]),
                    mode=reference["mode"],  # type: ignore[arg-type]
                    score=reference.get("score"),
                    matched_tags=list(reference.get("matched_tags", [])),
                    flower_types=list(reference.get("flower_types", [])),
                    visual_tags=list(reference.get("visual_tags", [])),
                    emotion_tags=list(reference.get("emotion_tags", [])),
                    scene_tags=list(reference.get("scene_tags", [])),
                    package_style=list(reference.get("package_style", [])),
                )
            )

        style_prompt = self._build_style_prompt(request)
        negative_prompt = (
            "不要文字、logo、水印、价签；不要人物、手部、花瓶、桌面陈列；"
            "不要多束花同时出现；不要插画感、CG 感、塑料假花感；"
            "不要畸形花头、重复花材、背景杂乱、主体被裁切、过曝或低清晰度；"
            "不要不存在的花种、凭空造花、违背真实植物结构的花瓣与花芯；"
            "不要白花配纯黑花芯、荧光色花瓣、金属感花朵或不合现实的器官组合。"
        )
        return ImageGenerationApiRequest(
            request_id=new_id("image_api"),
            mode=request.mode,
            semantic_result=request.semantic_result,
            reference_strategy=request.reference_strategy,
            creative_mode=request.creative_mode,
            generation_goals=request.generation_goals,
            selected_interpretation_label=request.selected_interpretation_label,
            selected_references=selected_references,
            variant_plans=request.variant_plans,
            generation_constraints=ImageGenerationConstraints(
                output_count=min(max(len(bouquet_templates[:3]), 1), 3),
                aspect_ratio="3:4",
                preserve_reference_strength=request.reference_strategy,
            ),
            style_prompt=style_prompt,
            negative_prompt=negative_prompt,
        )

    def generate(
        self,
        request: GenerateBouquetRequest,
        bouquet_templates: list[dict[str, object]],
        reference_map: dict[str, dict[str, object]],
    ) -> tuple[list[BouquetResult], list[GenerationVariantPlan]]:
        contract_request = self.build_api_request(request, bouquet_templates, reference_map)
        plan_used = self._resolve_variant_plans(contract_request)
        generated_images = self._generate_variant_images(contract_request, plan_used)
        if not generated_images:
            raise RuntimeError("生图 API 未返回可用图片。")

        base_results = BouquetGenerator().generate(request, bouquet_templates, reference_map)
        merged_results: list[BouquetResult] = []
        for index, result in enumerate(base_results):
            generated = generated_images[min(index, len(generated_images) - 1)]
            plan = plan_used[min(index, len(plan_used) - 1)]
            merged_results.append(
                result.model_copy(
                    update={
                        "image_url": generated.image_url,
                        "generation_focus": plan.focus,
                        "summary": self._merge_summary(
                            base_summary=result.summary,
                            generated=generated,
                            plan=plan,
                        ),
                    }
                )
            )
        return merged_results, plan_used

    def _generate_variant_images(
        self,
        request: ImageGenerationApiRequest,
        variants: list[GenerationVariantPlan],
    ) -> list[GeneratedBouquetImage]:
        images: list[GeneratedBouquetImage] = []
        for variant in variants:
            response = self._call_generation_api(
                request=request,
                variant=variant,
            )
            if not response.images:
                continue
            image = response.images[0].model_copy(
                update={
                    "prompt_summary": variant.title,
                    "provider_metadata": {
                        **response.images[0].provider_metadata,
                        "variant_name": variant.variant_id,
                    },
                }
            )
            images.append(image)
        return images

    def _build_style_prompt(self, request: GenerateBouquetRequest) -> str:
        lines = [
            "把输入语义翻译成一束可售卖、可展示、可落地的真实花束成品图。",
            self._mode_translation_guidance(request.mode),
            f"核心氛围：{request.semantic_result.semantic_summary}",
        ]
        if request.selected_interpretation_label:
            lines.append(f"当前选择的解读：{request.selected_interpretation_label}")
        if request.generation_goals:
            lines.append(f"本轮生成目标：{'、'.join(request.generation_goals[:4])}")
        lines.append(f"创作模式：{request.creative_mode}")
        if request.semantic_result.scene_tags:
            lines.append(f"场景线索：{'、'.join(request.semantic_result.scene_tags[:4])}")
        if request.semantic_result.emotion_tags:
            lines.append(f"情绪目标：{'、'.join(request.semantic_result.emotion_tags[:4])}")
        if request.semantic_result.visual_tags:
            lines.append(f"视觉倾向：{'、'.join(request.semantic_result.visual_tags[:4])}")
        if request.semantic_result.color_palette:
            lines.append(f"建议配色：{'、'.join(request.semantic_result.color_palette[:4])}")
        if request.semantic_result.relation_tags:
            lines.append(f"关系对象：{'、'.join(request.semantic_result.relation_tags[:3])}")
        lines.append(f"参考强度：{request.reference_strategy}")
        return "\n".join(lines)

    def _call_generation_api(
        self,
        request: ImageGenerationApiRequest,
        variant: GenerationVariantPlan,
    ) -> ImageGenerationApiResponse:
        base_url = os.getenv("IMAGE_GENERATION_API_URL") or os.getenv("DASHSCOPE_BASE_URL")
        api_key = os.getenv("IMAGE_GENERATION_API_KEY") or os.getenv("DASHSCOPE_API_KEY")
        model = os.getenv("IMAGE_GENERATION_MODEL") or os.getenv("WAN_IMAGE_MODEL") or "wan2.7-image"
        if not base_url or not api_key:
            raise RuntimeError("未配置生图 API 的 URL 或 KEY。")

        endpoint = f"{base_url.rstrip('/')}/api/v1/services/aigc/image-generation/generation"
        payload = self._build_http_payload(
            request=request,
            model=model,
            variant=variant,
        )
        started_at = time.perf_counter()
        try:
            with httpx.Client(timeout=60.0) as client:
                submit_response = client.post(
                    endpoint,
                    headers={
                        "Authorization": f"Bearer {api_key}",
                        "Content-Type": "application/json",
                        "X-DashScope-Async": "enable",
                    },
                    json=payload,
                )
                submit_response.raise_for_status()
        except httpx.HTTPError as exc:
            raise RuntimeError(f"生图 API 提交失败：{exc}") from exc

        submit_data = submit_response.json()
        task_id = (
            submit_data.get("output", {}).get("task_id")
            or submit_data.get("task_id")
            or submit_data.get("request_id")
        )
        if not task_id:
            raise RuntimeError(f"生图 API 未返回 task_id：{submit_data}")

        result_data = self._poll_generation_task(
            base_url=base_url,
            api_key=api_key,
            task_id=str(task_id),
        )
        latency_ms = int((time.perf_counter() - started_at) * 1000)
        images = self._extract_generated_images(result_data)
        return ImageGenerationApiResponse(
            request_id=f"{task_id}:{variant.variant_id}",
            provider_name="dashscope",
            model_name=model,
            images=images,
            latency_ms=latency_ms,
        )

    def _build_http_payload(
        self,
        request: ImageGenerationApiRequest,
        model: str,
        variant: GenerationVariantPlan,
    ) -> dict[str, Any]:
        content: list[dict[str, str]] = [
            {"text": self._build_generation_prompt(request, variant)}
        ]
        variant_reference_strategy = variant.reference_strategy or request.reference_strategy
        if variant_reference_strategy == "strong":
            for reference in request.selected_references[:2]:
                content.append({"image": to_provider_image_input(reference.cover_url)})

        parameters: dict[str, Any] = {
            "n": 1,
            "watermark": False,
            "prompt_extend": True,
        }
        size = self._map_size(request.generation_constraints.aspect_ratio)
        if size:
            parameters["size"] = size

        return {
            "model": model,
            "input": {
                "messages": [
                    {
                        "role": "user",
                        "content": content,
                    }
                ]
            },
            "parameters": parameters,
        }

    def _build_generation_prompt(
        self,
        request: ImageGenerationApiRequest,
        variant: GenerationVariantPlan,
    ) -> str:
        reference_titles = "、".join(reference.title for reference in request.selected_references[:3])
        prompt_lines = [
            "角色：你是“万物生花”的花艺生图专家，需要把选定解读转成真实、审美统一、适合展示的花束成品图。",
            "你要为“万物生花”生成一张可直接用于前端展示的花束商品图。",
            "“万物生花”的目标，是把用户输入的人、场景、关系和情绪转译成有审美表达的花艺结果。",
            "最终结果必须是一束完整、真实感强、适合前端展示的鲜花花束成品，而不是场景照、概念海报或插画。",
            f"产品模式：{request.mode}",
            "创作任务：先理解输入语义，再把它翻译成花束的配色、花材气质、层次结构、包装方式和整体留白。",
            "风格设定：",
            request.style_prompt,
            f"场景标签：{'、'.join(request.semantic_result.scene_tags) or '无'}",
            f"情绪标签：{'、'.join(request.semantic_result.emotion_tags) or '无'}",
            f"视觉标签：{'、'.join(request.semantic_result.visual_tags) or '无'}",
            f"关系标签：{'、'.join(request.semantic_result.relation_tags) or '无'}",
            f"用途意图：{request.semantic_result.use_intent}",
            f"当前变体：{variant.variant_id}",
            f"变体标题：{variant.title}",
            f"变体焦点：{variant.focus}",
            f"变体要求：{variant.prompt_directive}",
            f"形式结构：{variant.composition_style}",
            f"材料丰富度：{variant.material_richness}",
            f"花材种类上限：{variant.species_count_cap}",
            f"主花占比：{variant.dominant_flower_ratio:.2f}",
            f"配色策略：{variant.color_strategy}",
            f"花束密度：{variant.bouquet_density}",
        ]
        if reference_titles:
            prompt_lines.append(
                f"参考花束：{reference_titles}。请只提炼这些参考的颜色方向、结构层次、包装气质和花材倾向，"
                "把它们转译成新的花束方案。不要复刻同一束花，不要照抄构图，不要生成与参考几乎一样的成品。"
            )
            prompt_lines.append(self._build_reference_distillation(request))
            prompt_lines.append(
                "参考使用原则：参考是灵感来源，不是元素清单。不要试图把每个参考里的花材、包装和配色全部塞进同一束花。"
                "每个方案默认只选择一个最匹配的主参考作为灵感来源，最多借用极少量辅助特征。"
                "如果其他参考不匹配，就完全忽略，不要为了全面覆盖参考而做拼盘式融合。"
            )
        variant_reference_strategy = variant.reference_strategy or request.reference_strategy
        if variant_reference_strategy == "light":
            prompt_lines.append(
                "当前是轻参考：严禁直接复制参考花束的外形、具体主花材组合、花材比例和包装版式，"
                "只允许借用抽象特征。如果输入色调、氛围与参考冲突，必须优先服从输入语义。"
                "你应该优先只保留一个主参考，甚至完全忽略不匹配参考，不要为了融合而融合。"
            )
        elif variant_reference_strategy == "strong":
            prompt_lines.append(
                "当前是强参考：可以更接近参考的色彩和结构，但仍必须保留新的成品感，不能变成同款复刻。"
                "即便是强参考，也优先围绕一个主参考展开，不要机械拼接多个参考的全部元素。"
            )
        if request.creative_mode == "expressive":
            prompt_lines.append(
                "当前是表达优先模式：允许使用更稀有、更高级、现实中较少见的真实花材来放大气质和象征意义。"
                "但花材必须是真实存在的鲜花，不要发明不存在的花。"
            )
        elif request.creative_mode == "commercial":
            prompt_lines.append("当前是现实优先模式：尽量保持成品可售卖、可复刻、符合常见花店落地表达。")
        else:
            prompt_lines.append("当前是混合模式：允许适度发散，但不要脱离现实审美与可理解性。")
        prompt_lines.extend(
            [
                "画面要求：单束花束，主体完整，花头和包装清晰，构图稳定，背景干净，光线自然柔和，真实摄影质感。",
                "表达要求：可以优先还原氛围、色调、人物气质、材料感或花语含义中的某一个主轴，但必须让这一主轴足够鲜明。",
                "构成要求：花材组合要有明确主次和统一画面逻辑，不要为了体现多个参考而堆砌互相冲突的花型、颜色或包装元素。",
                "形式约束：优先通过重复、密度、留白和结构形成美感，不要把输入中的每个语义点都翻译成一种不同花材。",
                f"形式执行：请严格控制在不超过 {variant.species_count_cap} 类主要花材范围内，主花需占到约 {int(variant.dominant_flower_ratio * 100)}% 的视觉体量。",
                f"形式执行：当前方案应呈现 {self._describe_composition_style(variant.composition_style)} 的花束结构，材料丰富度为 {self._describe_material_richness(variant.material_richness)}。",
                f"形式执行：配色策略为 {self._describe_color_strategy(variant.color_strategy)}，花束密度为 {self._describe_bouquet_density(variant.bouquet_density)}。",
                "审美原则：参考图只用于借鉴气质、结构或色块，不要把参考里出现过的颜色和花材尽量都放进这一次结果里。",
                "审美原则：如果某个颜色、花材或包装元素会破坏整体高级感与统一性，就主动舍弃它，而不是勉强保留。",
                "结果要求：鲜花新鲜、有层次、有手工包扎感，适合结果页展示；在 expressive 模式下允许适度使用稀有花材或更高级的组合，但所有花材都必须符合现实植物学常识。",
                "真实性要求：花型结构、花芯颜色、花瓣层次和植物器官必须符合现实中存在的花卉，不允许出现违背常识的白花黑芯、异常器官或虚构花种。",
                f"明确避免：{request.negative_prompt}",
            ]
        )
        return "\n".join(prompt_lines)

    def _mode_translation_guidance(self, mode: str) -> str:
        if mode == "scene":
            return "请把场景氛围转译成花束，不要把原始空间直接画出来；重点体现色调、情绪、留白和气质。"
        if mode == "flower":
            return "请保留花束输入的核心花艺风格，但做成更完整、更商品化、更适合售卖展示的版本。"
        return "请把现实关系和送礼情境转译成花束语气，让花束自然体现对象、分寸和场合。"

    def _build_reference_distillation(self, request: ImageGenerationApiRequest) -> str:
        distilled: list[str] = []
        for reference in request.selected_references[:3]:
            parts: list[str] = [reference.title]
            if reference.visual_tags:
                parts.append(f"视觉={','.join(reference.visual_tags[:3])}")
            if reference.emotion_tags:
                parts.append(f"情绪={','.join(reference.emotion_tags[:3])}")
            if request.reference_strategy == "strong" and reference.flower_types:
                parts.append(f"花材={','.join(reference.flower_types[:4])}")
            if reference.package_style:
                parts.append(f"包装={','.join(reference.package_style[:3])}")
            distilled.append("；".join(parts))
        if not distilled:
            return "未提供可用参考特征。"
        return "参考特征摘要：" + " | ".join(distilled)

    def _resolve_variant_plans(self, request: ImageGenerationApiRequest) -> list[GenerationVariantPlan]:
        if request.variant_plans:
            return request.variant_plans[: request.generation_constraints.output_count]
        planned = self._plan_variants_with_semantic_model(request)
        if planned:
            return planned[: request.generation_constraints.output_count]
        return self._build_default_variant_plan(request)

    def _plan_variants_with_semantic_model(
        self,
        request: ImageGenerationApiRequest,
    ) -> list[GenerationVariantPlan]:
        base_url, api_key, model = _resolve_planner_client_config()
        if not base_url or not api_key:
            return []

        prompt = self._build_variant_planner_prompt(request)
        endpoint = f"{base_url.rstrip('/')}/chat/completions"
        try:
            with httpx.Client(timeout=60.0) as client:
                response = client.post(
                    endpoint,
                    headers={
                        "Authorization": f"Bearer {api_key}",
                        "Content-Type": "application/json",
                    },
                    json={
                        "model": model,
                        "messages": [
                            {
                                "role": "system",
                                "content": self._planner_system_prompt(),
                            },
                            {
                                "role": "user",
                                "content": prompt,
                            },
                        ],
                        "temperature": 0.4,
                    },
                )
                response.raise_for_status()
        except httpx.HTTPError:
            return []

        try:
            content = response.json()["choices"][0]["message"]["content"]
            if isinstance(content, list):
                content = "".join(str(item.get("text", "")) for item in content if isinstance(item, dict))
            parsed = json.loads(str(content))
        except (KeyError, IndexError, TypeError, json.JSONDecodeError):
            return []

        plans = parsed.get("variant_plans")
        if not isinstance(plans, list):
            return []
        normalized: list[GenerationVariantPlan] = []
        for index, item in enumerate(plans[: request.generation_constraints.output_count], start=1):
            if not isinstance(item, dict):
                continue
            focus = _normalize_generation_focus(item.get("focus"))
            normalized.append(
                GenerationVariantPlan(
                    variant_id=str(item.get("variant_id") or f"planned_{index}"),
                    title=str(item.get("title") or f"方案{index}"),
                    focus=focus,  # type: ignore[arg-type]
                    prompt_directive=str(item.get("prompt_directive") or "").strip() or "优先还原核心氛围。",
                    reference_strategy=_normalize_reference_strategy(
                        item.get("reference_strategy"),
                        request.reference_strategy,
                    ),
                    composition_style=_normalize_composition_style(item.get("composition_style")),
                    material_richness=_normalize_material_richness(item.get("material_richness")),
                    species_count_cap=_normalize_species_count_cap(item.get("species_count_cap")),
                    dominant_flower_ratio=_normalize_dominant_flower_ratio(item.get("dominant_flower_ratio")),
                    color_strategy=_normalize_color_strategy(item.get("color_strategy")),
                    bouquet_density=_normalize_bouquet_density(item.get("bouquet_density")),
                )
            )
        return normalized

    def _build_variant_planner_prompt(self, request: ImageGenerationApiRequest) -> str:
        references = "、".join(reference.title for reference in request.selected_references[:3]) or "无"
        goals = "、".join(request.generation_goals[:5]) or "未指定"
        return (
            "你现在以“万物生花”的花艺总监兼审美规划专家身份工作。\n"
            "请为一次“万物生花”的生花任务规划 3 个彼此有明确区分的次生花方案。\n"
            "目标：避免三张结果几乎一样，同时让每一张都能代表一种清晰的解读角度。\n"
            "参考是灵感来源，不是融合清单。不要要求模型把所有参考的元素都拼到同一束花里。\n"
            "每个方案默认只借鉴一个最匹配的主参考，也可以完全忽略不匹配参考。\n"
            "不要规划成多参考平均融合，不要让方案为了覆盖参考而牺牲画面统一性。\n"
            "你的核心工作是做审美取舍：一个好方案可以主动舍弃某些颜色、某些参考、某些语义，只保留最有表现力的部分。\n"
            "如果输入信息很多，请优先提升整体气质、色块统一和材料秩序，不要把丰富信息直接翻译成丰富花材。\n"
            "所有方案都必须坚持现实花材原则：允许稀有，但必须是真实存在的鲜花，不允许虚构花种或异常花芯结构。\n"
            "每个方案都要给出 variant_id、title、focus、prompt_directive、reference_strategy。\n"
            "每个方案还要给出 composition_style、material_richness、species_count_cap、dominant_flower_ratio、color_strategy、bouquet_density。\n"
            "focus 只能是 atmosphere / color / persona / material / premium / coherence / symbolism。\n"
            "reference_strategy 只能是 none / light / strong。\n"
            "composition_style 只能是 mass / layered / airy / focal。\n"
            "material_richness 只能是 single / limited / mixed。\n"
            "color_strategy 只能是 single_tone / dual_tone / accent。\n"
            "bouquet_density 只能是 dense / medium / airy。\n"
            "请控制方案数量为 3 个，并确保侧重点明显不同。\n"
            f"mode={request.mode}\n"
            f"creative_mode={request.creative_mode}\n"
            f"selected_interpretation_label={request.selected_interpretation_label or '未指定'}\n"
            f"semantic_summary={request.semantic_result.semantic_summary}\n"
            f"scene_tags={','.join(request.semantic_result.scene_tags)}\n"
            f"emotion_tags={','.join(request.semantic_result.emotion_tags)}\n"
            f"visual_tags={','.join(request.semantic_result.visual_tags)}\n"
            f"translation_axes={','.join(request.semantic_result.translation_axes)}\n"
            f"generation_goals={goals}\n"
            f"references={references}\n"
            '输出 JSON 结构：{"variant_plans":[{"variant_id":"plan_1","title":"氛围还原","focus":"atmosphere","prompt_directive":"...","reference_strategy":"light","composition_style":"mass","material_richness":"single","species_count_cap":2,"dominant_flower_ratio":0.82,"color_strategy":"single_tone","bouquet_density":"dense"}]}'
        )

    def _build_default_variant_plan(self, request: ImageGenerationApiRequest) -> list[GenerationVariantPlan]:
        defaults = [
            GenerationVariantPlan(
                variant_id="plan_atmosphere",
                title="氛围还原",
                focus="atmosphere",
                prompt_directive="第一次次生花优先还原输入的氛围、光感、空气感和整体色调。",
                reference_strategy=request.reference_strategy,
                composition_style="mass",
                material_richness="single",
                species_count_cap=2,
                dominant_flower_ratio=0.82,
                color_strategy="single_tone",
                bouquet_density="dense",
            ),
            GenerationVariantPlan(
                variant_id="plan_persona",
                title="气质表达",
                focus="persona",
                prompt_directive="第二次次生花优先还原人物或场景体现出的气质、分寸和情绪姿态。",
                reference_strategy=request.reference_strategy,
                composition_style="layered",
                material_richness="limited",
                species_count_cap=3,
                dominant_flower_ratio=0.72,
                color_strategy="dual_tone",
                bouquet_density="medium",
            ),
            GenerationVariantPlan(
                variant_id="plan_symbolism",
                title="花语对齐",
                focus="symbolism",
                prompt_directive="第三次次生花优先还原花语含义、材料象征和关系语境，可适度提高高级感。",
                reference_strategy="none" if request.creative_mode == "expressive" else "light",
                composition_style="focal",
                material_richness="limited",
                species_count_cap=3,
                dominant_flower_ratio=0.65,
                color_strategy="accent",
                bouquet_density="medium",
            ),
        ]
        return defaults[: request.generation_constraints.output_count]

    def _map_size(self, aspect_ratio: str) -> str | None:
        size_map = {
            "1:1": "1024*1024",
            "4:5": "1024*1280",
            "3:4": "1024*1365",
            "16:9": "1280*720",
            "9:16": "720*1280",
        }
        return size_map.get(aspect_ratio)

    def _poll_generation_task(self, base_url: str, api_key: str, task_id: str) -> dict[str, Any]:
        endpoint = f"{base_url.rstrip('/')}/api/v1/tasks/{task_id}"
        last_data: dict[str, Any] | None = None
        with httpx.Client(timeout=30.0) as client:
            for _ in range(60):
                try:
                    response = client.get(
                        endpoint,
                        headers={"Authorization": f"Bearer {api_key}"},
                    )
                    response.raise_for_status()
                except httpx.HTTPError as exc:
                    raise RuntimeError(f"生图任务轮询失败：{exc}") from exc
                data = response.json()
                last_data = data
                output = data.get("output", {})
                task_status = str(output.get("task_status", "")).upper()
                finished = bool(output.get("finished"))
                if task_status == "SUCCEEDED" or finished:
                    return data
                if task_status in {"FAILED", "CANCELED", "UNKNOWN"}:
                    raise RuntimeError(f"生图任务失败：{data.get('message') or data}")
                time.sleep(2)
        raise RuntimeError(f"生图任务超时：{last_data}")

    def _extract_generated_images(self, data: dict[str, Any]) -> list[GeneratedBouquetImage]:
        choices = data.get("output", {}).get("choices", [])
        images: list[GeneratedBouquetImage] = []
        for choice in choices:
            message = choice.get("message", {})
            content = message.get("content", [])
            if not isinstance(content, list):
                continue
            for item in content:
                if not isinstance(item, dict) or item.get("type") != "image":
                    continue
                image_url = item.get("image")
                if not image_url:
                    continue
                images.append(
                    GeneratedBouquetImage(
                        image_url=str(image_url),
                        prompt_summary="wan_generation",
                        revised_prompt="",
                        seed=None,
                        provider_metadata={
                            "task_status": str(data.get("output", {}).get("task_status", "")),
                        },
                    )
                )
        return images

    def _merge_summary(
        self,
        base_summary: str,
        generated: GeneratedBouquetImage,
        plan: GenerationVariantPlan,
    ) -> str:
        if generated.revised_prompt:
            return f"{base_summary}，本次侧重“{plan.title}”，正式生图已完成，模型重写提示词：{generated.revised_prompt}"
        return f"{base_summary}，本次侧重“{plan.title}”，正式生图已完成。"

    def _describe_composition_style(self, value: str) -> str:
        mapping = {
            "mass": "大面积铺陈、靠重复形成饱满色块",
            "layered": "有限材料的高低层次与自然起伏",
            "airy": "留白明显、空气感更强的轻结构",
            "focal": "有明确视觉中心、围绕主花展开",
        }
        return mapping.get(value, value)

    def _describe_material_richness(self, value: str) -> str:
        mapping = {
            "single": "单一或极少数花材重复铺陈",
            "limited": "有限种类、主次明确",
            "mixed": "可以有变化，但仍需统一逻辑",
        }
        return mapping.get(value, value)

    def _describe_color_strategy(self, value: str) -> str:
        mapping = {
            "single_tone": "单色或邻近色统一铺陈",
            "dual_tone": "双主色协调配合",
            "accent": "大面积统一底色 + 少量点睛色",
        }
        return mapping.get(value, value)

    def _describe_bouquet_density(self, value: str) -> str:
        mapping = {
            "dense": "饱满密集，强调色块与体量",
            "medium": "中等密度，主次均衡",
            "airy": "轻盈疏朗，强调留白",
        }
        return mapping.get(value, value)


@lru_cache
def get_image_generation_provider() -> ImageGenerationProvider:
    if is_test_mode():
        return MockImageGenerationProvider()
    provider = os.getenv("IMAGE_GENERATION_PROVIDER", "mock").lower()
    if provider == "api":
        return ApiImageGenerationProvider()
    return MockImageGenerationProvider()


def _normalize_generation_focus(value: object) -> str:
    candidate = str(value or "atmosphere").strip().lower()
    if candidate in {"atmosphere", "color", "persona", "material", "premium", "coherence", "symbolism"}:
        return candidate
    return "atmosphere"


def _resolve_planner_client_config() -> tuple[str | None, str | None, str]:
    base_url = (
        os.getenv("PLANNER_API_URL")
        or os.getenv("SEMANTIC_API_URL")
        or os.getenv("QWEN_BASE_URL")
    )
    api_key = (
        os.getenv("PLANNER_API_KEY")
        or os.getenv("SEMANTIC_API_KEY")
        or os.getenv("DASHSCOPE_API_KEY")
    )
    model = (
        os.getenv("PLANNER_MODEL")
        or os.getenv("AESTHETIC_MODEL")
        or os.getenv("SEMANTIC_MODEL")
        or os.getenv("QWEN_VL_MODEL")
        or "qwen-vl-max"
    )
    return base_url, api_key, model


def _normalize_reference_strategy(value: object, fallback: str) -> str:
    candidate = str(value or fallback).strip().lower()
    if candidate in {"none", "light", "strong"}:
        return candidate
    return fallback if fallback in {"none", "light", "strong"} else "light"


def _normalize_composition_style(value: object) -> str:
    candidate = str(value or "mass").strip().lower()
    if candidate in {"mass", "layered", "airy", "focal"}:
        return candidate
    return "mass"


def _normalize_material_richness(value: object) -> str:
    candidate = str(value or "limited").strip().lower()
    if candidate in {"single", "limited", "mixed"}:
        return candidate
    return "limited"


def _normalize_color_strategy(value: object) -> str:
    candidate = str(value or "dual_tone").strip().lower()
    if candidate in {"single_tone", "dual_tone", "accent"}:
        return candidate
    return "dual_tone"


def _normalize_bouquet_density(value: object) -> str:
    candidate = str(value or "medium").strip().lower()
    if candidate in {"dense", "medium", "airy"}:
        return candidate
    return "medium"


def _normalize_species_count_cap(value: object) -> int:
    try:
        count = int(value)
    except (TypeError, ValueError):
        count = 3
    return max(1, min(6, count))


def _normalize_dominant_flower_ratio(value: object) -> float:
    try:
        ratio = float(value)
    except (TypeError, ValueError):
        ratio = 0.7
    return max(0.4, min(1.0, ratio))
