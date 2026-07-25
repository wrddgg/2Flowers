from __future__ import annotations

from app.schemas.bouquet import BouquetResult
from app.schemas.emotion import (
    BudgetLevel,
    EmotionBuildResponse,
    EmotionRemakePreviewRequest,
    EmotionRemakePreviewResponse,
    GiftCard,
    OwnCard,
    OwnOption,
    RemakePlan,
    RemakeSubstitute,
    SaveCard,
)
from app.services.workflow_clients import create_result_path, public_upload_url, text2image
from app.utils.scoring import overlap_score


BUDGET_LABELS = {
    "premium": "完整复刻",
    "balanced": "平衡复刻",
    "budget": "轻预算复刻",
}

BUDGET_FLOWER_LIMIT = {
    "premium": 4,
    "balanced": 3,
    "budget": 2,
}

BUDGET_STEM_RANGE = {
    "premium": [14, 20],
    "balanced": [10, 14],
    "budget": [6, 9],
}

SEASON_LABELS = {
    12: "冬季",
    1: "冬季",
    2: "冬季",
    3: "春季",
    4: "春季",
    5: "春季",
    6: "夏季",
    7: "夏季",
    8: "夏季",
    9: "秋季",
    10: "秋季",
    11: "秋季",
}

FLOWER_SUBSTITUTIONS = [
    {
        "keywords": ["芍药", "牡丹"],
        "months": {4, 5, 6},
        "off_season_replacement": "花园玫瑰",
        "off_season_reason": "芍药和牡丹花期短，非当季时用层次接近的花园玫瑰更容易采购。",
        "budget_replacement": "康乃馨",
        "budget_reason": "预算收束时可用花型饱满、采购稳定的康乃馨保留团簇感。",
    },
    {
        "keywords": ["郁金香"],
        "months": {12, 1, 2, 3, 4},
        "off_season_replacement": "洋桔梗",
        "off_season_reason": "郁金香非长季供应时，洋桔梗更稳定，也能保留轻盈杯状花感。",
        "budget_replacement": "单头玫瑰",
        "budget_reason": "预算更紧时用单头玫瑰保留明确花型，成本更可控。",
    },
    {
        "keywords": ["铃兰"],
        "months": {4, 5, 6},
        "off_season_replacement": "小苍兰",
        "off_season_reason": "铃兰零售获取难度高，用小苍兰更符合日常花店采购现实。",
        "budget_replacement": "小雏菊",
        "budget_reason": "预算版可用小雏菊保留轻巧白花点缀。",
    },
    {
        "keywords": ["洋牡丹", "花毛茛"],
        "months": {2, 3, 4, 5},
        "off_season_replacement": "玫瑰",
        "off_season_reason": "洋牡丹短季明显，非当季时改用玫瑰更容易稳定出货。",
        "budget_replacement": "喷头玫瑰",
        "budget_reason": "预算版用喷头玫瑰替代，仍能保留层层展开的感觉。",
    },
    {
        "keywords": ["绣球"],
        "months": {5, 6, 7, 8, 9},
        "off_season_replacement": "康乃馨",
        "off_season_reason": "非绣球旺季时可用成组康乃馨做团面，落地性更高。",
        "budget_replacement": "康乃馨",
        "budget_reason": "预算友好时康乃馨能较好承接绣球的大面积块面感。",
    },
    {
        "keywords": ["蝴蝶兰", "兰花"],
        "months": set(range(1, 13)),
        "off_season_replacement": "白玫瑰",
        "off_season_reason": "花束型蝴蝶兰成本和取材波动较大，用白玫瑰更适合常规定制。",
        "budget_replacement": "白玫瑰",
        "budget_reason": "预算版优先保留干净高级感，改用白玫瑰更稳妥。",
    },
    {
        "keywords": ["雪柳", "飞燕草", "大飞燕"],
        "months": {3, 4, 5, 6},
        "off_season_replacement": "尤加利",
        "off_season_reason": "线性材料不稳定时，用尤加利和金鱼草组合更容易实现结构线条。",
        "budget_replacement": "尤加利",
        "budget_reason": "预算版优先保留线条，不强求昂贵枝材。",
    },
]


class EmotionBuilder:
    def build(
        self,
        result: BouquetResult,
        voice_context: str,
        reference_candidates: list[dict[str, object]],
    ) -> EmotionBuildResponse:
        target = self._extract_target(voice_context)
        own_candidates = self._build_own_candidates(result, voice_context, reference_candidates)
        return EmotionBuildResponse(
            save_card=SaveCard(
                title=f"把{result.title}留成一束花",
                copy_text=f"{result.summary} 这是一张适合收藏、发布或继续分享的结果卡片。",
            ),
            gift_card=GiftCard(
                target=target,
                reason=self._build_reason(voice_context, result.tags),
            ),
            own_card=OwnCard(
                options=["同感觉现货版", "预算友好版", "轻量桌花版"],
                candidates=own_candidates,
            ),
        )

    def build_remake_preview(
        self,
        *,
        result: BouquetResult,
        request: EmotionRemakePreviewRequest,
        reference_candidates: list[dict[str, object]],
    ) -> EmotionRemakePreviewResponse:
        own_candidates = self._build_own_candidates(result, request.voice_context, reference_candidates)
        option = next((item for item in own_candidates if item.option_type == request.option_type), None)
        if option is None:
            raise ValueError(f"未知的复刻方案 option_type={request.option_type}")

        budget_level = self._resolve_budget_level(request.budget_level, request.option_type, result)
        plan = self._build_remake_plan(
            result=result,
            option=option,
            budget_level=budget_level,
            season_month=request.season_month,
        )
        preview_image_url, preview_status = self._generate_remake_preview(result, plan)
        return EmotionRemakePreviewResponse(
            option_type=option.option_type,
            option_title=option.title,
            preview_image_url=preview_image_url,
            preview_status=preview_status,
            budget_level=budget_level,
            generation_brief=option.generation_brief,
            plan=plan,
        )

    def _extract_target(self, voice_context: str) -> str:
        for keyword in ["朋友", "同事", "领导", "恋人", "家人", "妈妈"]:
            if keyword in voice_context:
                return f"适合送给{keyword}"
        return "适合收藏或作为礼物表达"

    def _build_reason(self, voice_context: str, tags: list[str]) -> str:
        if "别太甜" in voice_context or "克制" in tags:
            return "整体表达更有分寸，保留情绪但不会显得过分亲密。"
        if "升职" in voice_context:
            return "这束花更偏祝贺与鼓励，适合阶段性节点表达。"
        return "整体情绪明确，既有记忆点，也方便在现实场景里承接。"

    def _build_own_candidates(
        self,
        result: BouquetResult,
        voice_context: str,
        reference_candidates: list[dict[str, object]],
    ) -> list[OwnOption]:
        normalized_candidates = [
            candidate
            for candidate in reference_candidates
            if str(candidate.get("mode")) == "flower"
        ]
        scored = self._score_candidates(result, voice_context, normalized_candidates)

        categories = [
            ("same_feeling", "同感觉现货版"),
            ("budget_friendly", "预算友好版"),
            ("light_table", "轻量桌花版"),
        ]
        used_ids: set[str] = set()
        own_options: list[OwnOption] = []
        for option_type, label in categories:
            candidate = self._pick_candidate_for_category(option_type, scored, used_ids)
            if not candidate:
                continue
            used_ids.add(str(candidate["reference_id"]))
            own_options.append(
                OwnOption(
                    option_type=option_type,
                    title=label,
                    bouquet_group_id=str(candidate["reference_id"]),
                    bouquet_title=str(candidate["title"]),
                    reason=self._build_option_reason(option_type, candidate, voice_context),
                    generation_brief=self._build_generation_brief(option_type, candidate, voice_context),
                    should_generate_after_select=True,
                    image_url="",
                    tags=list(candidate.get("visual_tags", []))[:2] + list(candidate.get("emotion_tags", []))[:1],
                )
            )
        return own_options

    def _score_candidates(
        self,
        result: BouquetResult,
        voice_context: str,
        candidates: list[dict[str, object]],
    ) -> list[dict[str, object]]:
        merged_tags = set(result.tags)
        for keyword in ["朋友", "同事", "领导", "恋人", "家人", "妈妈", "升职", "生日", "探望", "纪念日", "感谢", "节日"]:
            if keyword in voice_context:
                merged_tags.add(keyword)

        scored: list[dict[str, object]] = []
        for candidate in candidates:
            score = 0
            score += overlap_score(list(merged_tags), list(candidate.get("emotion_tags", [])), 15)
            score += overlap_score(list(merged_tags), list(candidate.get("scene_tags", [])), 12)
            score += overlap_score(list(merged_tags), list(candidate.get("fit_for", [])), 10)

            title = str(candidate.get("title", ""))
            if "预算" in voice_context and "野生" in title:
                score += 6
            if "领导" in voice_context and "祝贺" in title:
                score += 8
            if "朋友" in voice_context and "生日" in title:
                score += 5

            item = dict(candidate)
            item["_score"] = score
            scored.append(item)

        scored.sort(key=lambda item: int(item.get("_score", 0)), reverse=True)
        return scored

    def _pick_candidate_for_category(
        self,
        option_type: str,
        scored: list[dict[str, object]],
        used_ids: set[str],
    ) -> dict[str, object] | None:
        for candidate in scored:
            reference_id = str(candidate.get("reference_id"))
            if reference_id in used_ids:
                continue
            title = str(candidate.get("title", ""))
            visual_tags = list(candidate.get("visual_tags", []))
            scene_tags = list(candidate.get("scene_tags", []))

            if option_type == "same_feeling":
                return candidate
            if option_type == "budget_friendly":
                if "野生感" in title or "轻家居感" in visual_tags or "日常关怀" in scene_tags:
                    return candidate
            if option_type == "light_table":
                if "轻家居感" in visual_tags or "留白" in visual_tags or "日常关怀" in scene_tags:
                    return candidate

        for candidate in scored:
            reference_id = str(candidate.get("reference_id"))
            if reference_id not in used_ids:
                return candidate
        return None

    def _build_option_reason(self, option_type: str, candidate: dict[str, object], voice_context: str) -> str:
        bouquet_title = str(candidate.get("title", "这组花束"))
        if option_type == "same_feeling":
            return f"{bouquet_title} 和当前结果的情绪方向最接近，适合直接作为现实承接方案。"
        if option_type == "budget_friendly":
            return f"{bouquet_title} 更偏轻量和日常，适合做预算更友好的现实版本。"
        return f"{bouquet_title} 更适合摆放或轻量拥有，适合转成桌花或小体量版本。"

    def _build_generation_brief(self, option_type: str, candidate: dict[str, object], voice_context: str) -> str:
        bouquet_title = str(candidate.get("title", "当前方案"))
        scene_tags = list(candidate.get("scene_tags", []))
        visual_tags = list(candidate.get("visual_tags", []))
        emotion_tags = list(candidate.get("emotion_tags", []))
        brief_parts = [f"以“{bouquet_title}”为现实承接方向"]
        if option_type == "same_feeling":
            brief_parts.append("保留原生成花图的主要情绪和色彩关系")
        elif option_type == "budget_friendly":
            brief_parts.append("在保留核心感觉的前提下收束预算与材料复杂度")
        else:
            brief_parts.append("把当前花束转成更适合日常摆放和轻量拥有的版本")
        if voice_context:
            brief_parts.append(f"兼顾用户语境“{voice_context}”")
        tags = scene_tags[:1] + visual_tags[:1] + emotion_tags[:1]
        if tags:
            brief_parts.append(f"重点保留 { '、'.join(tags) }")
        return "，".join(brief_parts) + "。"

    def _resolve_budget_level(
        self,
        requested_budget: BudgetLevel,
        option_type: str,
        result: BouquetResult,
    ) -> str:
        if requested_budget != "auto":
            return requested_budget

        flower_count = len({flower.name for flower in result.flowers if flower.name})
        if option_type == "budget_friendly":
            return "budget"
        if option_type == "light_table":
            return "budget" if flower_count <= 2 else "balanced"
        if flower_count >= 4:
            return "premium"
        return "balanced"

    def _build_remake_plan(
        self,
        *,
        result: BouquetResult,
        option: OwnOption,
        budget_level: str,
        season_month: int | None,
    ) -> RemakePlan:
        source_flowers = self._ordered_unique([flower.name for flower in result.flowers if flower.name])
        selected_flowers, substitutes = self._resolve_selected_flowers(
            source_flowers=source_flowers,
            option_type=option.option_type,
            budget_level=budget_level,
            season_month=season_month,
        )
        preserve_points = self._build_preserve_points(result, option, budget_level)
        seasonality_note = self._build_seasonality_note(season_month, substitutes)
        estimated_stem_range = self._build_estimated_stem_range(option.option_type, budget_level)
        composition_note = self._build_composition_note(result, option.option_type, budget_level)
        packaging_note = self._build_packaging_note(result, option.option_type, budget_level)
        materials_note = self._build_materials_note(option.option_type, budget_level, selected_flowers, substitutes)
        preview_prompt = self._build_preview_prompt(
            result=result,
            option=option,
            budget_level=budget_level,
            season_month=season_month,
            estimated_stem_range=estimated_stem_range,
            selected_flowers=selected_flowers,
            substitutes=substitutes,
            preserve_points=preserve_points,
            composition_note=composition_note,
            packaging_note=packaging_note,
            materials_note=materials_note,
        )
        return RemakePlan(
            title=f"{option.title}·{BUDGET_LABELS[budget_level]}",
            budget_level=budget_level,
            seasonality_note=seasonality_note,
            estimated_stem_range=estimated_stem_range,
            preserve_points=preserve_points,
            selected_flowers=selected_flowers,
            substitute_flowers=substitutes,
            composition_note=composition_note,
            packaging_note=packaging_note,
            materials_note=materials_note,
            preview_prompt=preview_prompt,
        )

    def _resolve_selected_flowers(
        self,
        *,
        source_flowers: list[str],
        option_type: str,
        budget_level: str,
        season_month: int | None,
    ) -> tuple[list[str], list[RemakeSubstitute]]:
        if not source_flowers:
            source_flowers = ["玫瑰", "洋桔梗", "尤加利"]

        limit = BUDGET_FLOWER_LIMIT[budget_level]
        if option_type == "light_table":
            limit = min(limit, 2 if budget_level == "budget" else 3)
        selected: list[str] = []
        substitutes: list[RemakeSubstitute] = []
        seen_replacements: set[str] = set()

        for flower_name in source_flowers:
            replacement, reason = self._resolve_flower_replacement(flower_name, budget_level, season_month)
            if replacement != flower_name:
                key = f"{flower_name}->{replacement}"
                if key not in seen_replacements:
                    substitutes.append(
                        RemakeSubstitute(
                            source_flower=flower_name,
                            replacement_flower=replacement,
                            reason=reason,
                        )
                    )
                    seen_replacements.add(key)
            chosen = replacement or flower_name
            if chosen not in selected:
                selected.append(chosen)
            if len(selected) >= limit:
                break

        while len(selected) < min(limit, 3):
            for fallback_flower in ["玫瑰", "洋桔梗", "康乃馨", "尤加利"]:
                if fallback_flower not in selected:
                    selected.append(fallback_flower)
                if len(selected) >= min(limit, 3):
                    break

        return selected[:limit], substitutes

    def _resolve_flower_replacement(
        self,
        flower_name: str,
        budget_level: str,
        season_month: int | None,
    ) -> tuple[str, str]:
        normalized = flower_name.strip()
        for rule in FLOWER_SUBSTITUTIONS:
            if not any(keyword in normalized for keyword in rule["keywords"]):
                continue
            if season_month is not None and season_month not in rule["months"]:
                return str(rule["off_season_replacement"]), str(rule["off_season_reason"])
            if budget_level == "budget":
                return str(rule["budget_replacement"]), str(rule["budget_reason"])
            if budget_level == "balanced" and "蝴蝶兰" in normalized:
                return str(rule["budget_replacement"]), "平衡预算下优先选择采购更稳定、束形更容易控制的替代花材。"
            return normalized, ""
        if budget_level == "budget" and any(keyword in normalized for keyword in ["玫瑰", "蔷薇"]):
            return "喷头玫瑰", "预算版适合用喷头玫瑰保留花量感，同时控制单支成本。"
        return normalized, ""

    def _build_preserve_points(self, result: BouquetResult, option: OwnOption, budget_level: str) -> list[str]:
        points = [f"保留“{result.title}”的主色调和整体情绪，不做偏离原图的花材换风格。"] 
        if option.option_type == "same_feeling":
            points.append("尽量复刻原花束的轮廓、主花占比和送礼气质，做成更像花店现货的版本。")
        elif option.option_type == "budget_friendly":
            points.append("减少花材种类与总支数，但保留最有记忆点的主花和色块关系。")
        else:
            points.append("将花束压缩成更适合桌面或轻量摆放的体量，保持正面观感和留白。")
        if result.style_preset:
            points.append(f"构图继续参考“{result.style_preset}”的审美表达，保持画面高级感。")
        elif result.scene_preset:
            points.append(f"整体情境继续贴合“{result.scene_preset}”的使用场景。")
        if budget_level == "budget":
            points.append("优先保留一到两种主花，其他部分用常见配花和叶材完成结构。")
        return points[:3]

    def _build_seasonality_note(self, season_month: int | None, substitutes: list[RemakeSubstitute]) -> str:
        if season_month is None:
            if substitutes:
                return "未指定月份，已按常规花店常备花材优先处理，并对难稳定采购的花材做了替代。"
            return "未指定月份，默认按普通城市花店全年常备花材去做现实复刻。"
        season_name = SEASON_LABELS.get(season_month, "当季")
        if substitutes:
            return f"按 {season_month} 月（{season_name}）估算，部分短花期或采购波动较大的花材已替换为更常见的同感觉材料。"
        return f"按 {season_month} 月（{season_name}）估算，当前主要花材基本可在日常花店采购。"

    def _build_materials_note(
        self,
        option_type: str,
        budget_level: str,
        selected_flowers: list[str],
        substitutes: list[RemakeSubstitute],
    ) -> str:
        base = f"主用 { '、'.join(selected_flowers) } 做现实版本。"
        if option_type == "light_table":
            base += " 结构上更适合做低矮桌花或短束，便于实体摆放。"
        elif option_type == "budget_friendly":
            base += " 通过减少花材层级和支数来控制预算，但不牺牲核心氛围。"
        else:
            base += " 保留更完整的主花层次，优先做成花店可交付的成品花束。"
        if budget_level == "budget":
            base += " 包装和叶材建议简化，避免把预算消耗在复杂辅材上。"
        if substitutes:
            preview = "；".join(
                f"{item.source_flower}->{item.replacement_flower}" for item in substitutes[:3]
            )
            base += f" 已处理的关键替代包括：{preview}。"
        return base

    def _build_estimated_stem_range(self, option_type: str, budget_level: str) -> list[int]:
        base_range = list(BUDGET_STEM_RANGE[budget_level])
        if option_type == "light_table":
            return [max(4, base_range[0] - 2), max(6, base_range[1] - 3)]
        return base_range

    def _build_composition_note(self, result: BouquetResult, option_type: str, budget_level: str) -> str:
        if option_type == "same_feeling":
            return "维持原卡片花束的主视觉重心与前后层次，只把细节收束到更像现实花店可交付的结构。"
        if option_type == "budget_friendly":
            return "保留主花色块和第一眼记忆点，减少外围材料与复杂线条，让结构更简洁耐看。"
        if budget_level == "budget":
            return "优先做低重心、短束或小桌花结构，用更少材料维持正面观感。"
        return "整体压缩成更适合日常摆放的轻量结构，正面观感清晰，轮廓干净。"

    def _build_packaging_note(self, result: BouquetResult, option_type: str, budget_level: str) -> str:
        style = result.style_preset or ""
        if option_type == "light_table":
            return "包装尽量简化，可弱化外包装存在感，优先像花店短束或桌花样片。"
        if budget_level == "budget":
            return "建议使用单层韩素纸或牛皮纸等常见包装，不做大面积复杂褶边。"
        if style == "东方留白":
            return "包装保持克制留白，避免厚重多层纸张抢走花面。"
        if style == "法式浪漫":
            return "包装可略有柔和褶皱，但不能过分蓬松或婚礼化。"
        return "包装以常见花店材料为主，弱化复杂装饰，突出花面本身。"

    def _build_preview_prompt(
        self,
        *,
        result: BouquetResult,
        option: OwnOption,
        budget_level: str,
        season_month: int | None,
        estimated_stem_range: list[int],
        selected_flowers: list[str],
        substitutes: list[RemakeSubstitute],
        preserve_points: list[str],
        composition_note: str,
        packaging_note: str,
        materials_note: str,
    ) -> str:
        lines = [
            "角色：你是高端花店的花艺总监兼接单花艺师，需要把卡片花束转成现实可制作的定制预览图。",
            "请生成一张用于给花店沟通定制的现实花束预览图。",
            "目标不是艺术概念图，而是花店能照着接单和报价的现实样片。",
            "必须是可落地、可采购、符合日常花店制作逻辑的真实花束照片，不要插画感，不要幻想植物。",
            f"目标来源：{result.title}。原始摘要：{result.summary}",
            f"复刻方向：{option.title}。预算档位：{BUDGET_LABELS[budget_level]}。",
            f"预计总支数控制在 {estimated_stem_range[0]}-{estimated_stem_range[1]} 支。",
            f"现实花材只使用常见且容易购买的材料：{'、'.join(selected_flowers)}。",
            f"复刻重点：{'；'.join(preserve_points)}",
            f"构图说明：{composition_note}",
            f"包装说明：{packaging_note}",
            f"材料说明：{materials_note}",
        ]
        if substitutes:
            substitute_text = "；".join(
                f"{item.source_flower} 改为 {item.replacement_flower}，原因：{item.reason}"
                for item in substitutes[:4]
            )
            lines.append(f"替代策略：{substitute_text}")
        if season_month is not None:
            lines.append(f"请按照 {season_month} 月的实际花市供应去控制花材选择和丰度。")
        if result.scene_preset:
            lines.append(f"使用情境仍然贴合：{result.scene_preset}。")
        if result.style_preset:
            lines.append(f"审美风格继续保持：{result.style_preset}。")
        lines.extend(
            [
                "构图上适度复刻原卡片花束的主次层次、色块关系和镜头情境，但不要做超现实夸张结构。",
                "如果预算较低，可以减少花材种类和数量，用重复主花与简洁叶材维持高级感，不要为了显贵强行增加昂贵花材。",
                "审美原则：像真实城市花店会出的高级定制样片，克制、好看、能报价、能复刻，不要网红滤镜感和假高级堆砌。",
                "画面要求：单束花为主体，真实包装，花店样片质感，柔和自然光，背景干净，审美克制。",
            ]
        )
        return "\n".join(lines)

    def _generate_remake_preview(self, result: BouquetResult, plan: RemakePlan) -> tuple[str, str]:
        try:
            output_path = create_result_path("emotion_remake", result.result_id, ".png")
            generated_path = text2image(plan.preview_prompt, str(output_path), size="1K")
            return public_upload_url(generated_path), "generated"
        except Exception:
            return result.image_url, "fallback"

    def _ordered_unique(self, values: list[str]) -> list[str]:
        ordered: list[str] = []
        seen: set[str] = set()
        for value in values:
            normalized = str(value).strip()
            if not normalized or normalized in seen:
                continue
            seen.add(normalized)
            ordered.append(normalized)
        return ordered
