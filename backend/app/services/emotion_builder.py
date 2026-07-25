from __future__ import annotations

from app.schemas.bouquet import BouquetResult
from app.schemas.emotion import EmotionBuildResponse, GiftCard, OwnCard, OwnOption, SaveCard
from app.utils.scoring import overlap_score


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
