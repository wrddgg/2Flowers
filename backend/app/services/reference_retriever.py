from __future__ import annotations

from app.schemas.reference import ReferenceItem
from app.schemas.semantic import SemanticResult


TAG_EXPANSIONS = {
    "克制": ["分寸感", "正式送礼", "冷静"],
    "治愈": ["轻治愈", "安抚", "安心"],
    "温暖": ["安心", "陪伴", "家人"],
    "祝贺": ["升职", "庆祝", "积极"],
    "感谢": ["正式", "送礼", "尊重"],
    "朋友": ["朋友", "送礼", "朋友生日"],
    "同事": ["同事", "探望", "正式送礼"],
    "领导": ["领导", "感谢", "正式送礼"],
    "家人": ["家人", "节日", "日常关怀"],
    "妈妈": ["妈妈", "家人", "节日"],
    "恋人": ["恋人", "纪念日", "约会"],
    "自用": ["收藏", "空间装饰", "桌花", "居家"],
    "gift": ["送礼", "正式送礼", "祝福"],
    "self": ["收藏", "自用", "桌花", "空间装饰"],
    "decorate": ["空间装饰", "桌花", "居家"],
    "celebrate": ["升职", "生日", "纪念日", "庆祝"],
    "表达氛围": ["氛围", "场景", "收藏"],
}

INTENT_PREFERENCES = {
    "gift": ["送礼", "正式送礼", "祝福", "节日", "生日", "纪念日", "探望", "升职", "感谢"],
    "self": ["收藏", "自用", "桌花", "空间装饰", "居家", "日常"],
    "decorate": ["空间装饰", "桌花", "居家", "客厅", "日常"],
    "celebrate": ["升职", "生日", "纪念日", "庆祝", "节日"],
    "表达氛围": ["氛围", "场景", "收藏", "雨景", "晚霞", "海边"],
}

REFERENCE_MATCH_THRESHOLD = 55
REFERENCE_MAX_MATCHES = 3


class ReferenceRetriever:
    def search(
        self,
        references: list[dict[str, object]],
        mode: str,
        semantic_result: SemanticResult | None,
        semantic_tags: list[str],
        limit: int,
        excluded_reference_ids: list[str] | None = None,
    ) -> list[ReferenceItem]:
        semantic_result = semantic_result or SemanticResult(
            mode=mode,  # type: ignore[arg-type]
            subject_tags=[],
            scene_tags=[],
            emotion_tags=[],
            visual_tags=[],
            color_palette=[],
            relation_tags=[],
            use_intent="表达氛围",
            semantic_summary="空语义输入。",
        )
        excluded_reference_ids = excluded_reference_ids or []
        query = self._build_query_profile(mode=mode, semantic_result=semantic_result, semantic_tags=semantic_tags)

        scored: list[tuple[int, ReferenceItem]] = []
        for item in references:
            if str(item.get("reference_id", "")) in excluded_reference_ids:
                continue
            breakdown = self._score_reference(query=query, item=item)
            score = sum(breakdown.values())
            matched_tags = self._collect_matched_tags(query=query, item=item)
            reason = self._build_reason(breakdown=breakdown, matched_tags=matched_tags)

            scored.append(
                (
                    score,
                    ReferenceItem(
                        **item,
                        reason=reason,
                        score=score,
                        matched_tags=matched_tags,
                        score_breakdown=breakdown,
                    ),
                )
            )

        scored.sort(key=lambda pair: (pair[0], len(pair[1].matched_tags)), reverse=True)
        effective_limit = min(limit, REFERENCE_MAX_MATCHES)
        filtered_results = [
            item
            for score, item in scored
            if self._passes_threshold(score=score, item=item)
        ]
        return filtered_results[:effective_limit]

    def _build_query_profile(
        self,
        mode: str,
        semantic_result: SemanticResult,
        semantic_tags: list[str],
    ) -> dict[str, object]:
        subject_tags = _expanded_tags(semantic_result.subject_tags + semantic_tags)
        scene_tags = _expanded_tags(semantic_result.scene_tags)
        emotion_tags = _expanded_tags(semantic_result.emotion_tags)
        visual_tags = _expanded_tags(semantic_result.visual_tags)
        relation_tags = _expanded_tags(semantic_result.relation_tags)
        intent_tags = _expanded_tags([semantic_result.use_intent])
        return {
            "mode": mode,
            "subject_tags": subject_tags,
            "scene_tags": scene_tags,
            "emotion_tags": emotion_tags,
            "visual_tags": visual_tags,
            "relation_tags": relation_tags,
            "intent_tags": intent_tags,
            "use_intent": semantic_result.use_intent,
        }

    def _score_reference(self, query: dict[str, object], item: dict[str, object]) -> dict[str, int]:
        candidate_mode = str(item["mode"])
        candidate_scene_tags = _as_str_list(item.get("scene_tags", []))
        candidate_emotion_tags = _as_str_list(item.get("emotion_tags", []))
        candidate_visual_tags = _as_str_list(item.get("visual_tags", []))
        candidate_fit_for = _as_str_list(item.get("fit_for", []))
        candidate_flower_types = _as_str_list(item.get("flower_types", []))
        candidate_package_style = _as_str_list(item.get("package_style", []))
        candidate_title = str(item.get("title", ""))
        candidate_subject_tags = _expanded_tags(candidate_flower_types + [candidate_title])

        breakdown = {
            "mode": self._mode_score(input_mode=str(query["mode"]), candidate_mode=candidate_mode),
            "source": 8 if item.get("asset_source") else 0,
            "intent": self._intent_score(
                use_intent=str(query["use_intent"]),
                candidate_scene_tags=candidate_scene_tags,
                candidate_fit_for=candidate_fit_for,
            ),
            "subject": self._weighted_overlap(
                _as_str_list(query["subject_tags"]),
                candidate_subject_tags,
                weight=10,
                cap=2,
            ),
            "scene": self._weighted_overlap(
                _as_str_list(query["scene_tags"]),
                _expanded_tags(candidate_scene_tags),
                weight=9,
                cap=2,
            ),
            "emotion": self._weighted_overlap(
                _as_str_list(query["emotion_tags"]),
                _expanded_tags(candidate_emotion_tags),
                weight=11,
                cap=2,
            ),
            "visual": self._weighted_overlap(
                _as_str_list(query["visual_tags"]),
                _expanded_tags(candidate_visual_tags + candidate_package_style),
                weight=8,
                cap=2,
            ),
            "relation": self._weighted_overlap(
                _as_str_list(query["relation_tags"]),
                _expanded_tags(candidate_fit_for + candidate_scene_tags),
                weight=10,
                cap=2,
            ),
        }
        return breakdown

    def _collect_matched_tags(self, query: dict[str, object], item: dict[str, object]) -> list[str]:
        candidate_tags = set()
        candidate_tags.update(_expanded_tags(_as_str_list(item.get("scene_tags", []))))
        candidate_tags.update(_expanded_tags(_as_str_list(item.get("emotion_tags", []))))
        candidate_tags.update(_expanded_tags(_as_str_list(item.get("visual_tags", []))))
        candidate_tags.update(_expanded_tags(_as_str_list(item.get("fit_for", []))))
        candidate_tags.update(_expanded_tags(_as_str_list(item.get("flower_types", []))))
        candidate_tags.update(_expanded_tags(_as_str_list(item.get("package_style", []))))
        candidate_title = str(item.get("title", ""))
        if candidate_title:
            candidate_tags.add(candidate_title)

        query_tags = set()
        query_tags.update(_as_str_list(query["subject_tags"]))
        query_tags.update(_as_str_list(query["scene_tags"]))
        query_tags.update(_as_str_list(query["emotion_tags"]))
        query_tags.update(_as_str_list(query["visual_tags"]))
        query_tags.update(_as_str_list(query["relation_tags"]))
        query_tags.update(_as_str_list(query["intent_tags"]))
        return sorted(query_tags & candidate_tags)[:6]

    def _build_reason(self, breakdown: dict[str, int], matched_tags: list[str]) -> str:
        top_dimensions = [
            name
            for name, value in sorted(breakdown.items(), key=lambda pair: pair[1], reverse=True)
            if value > 0
        ][:3]
        label_map = {
            "mode": "模式契合",
            "source": "真实素材优先",
            "intent": "用途契合",
            "subject": "主题贴近",
            "scene": "场景贴近",
            "emotion": "情绪贴近",
            "visual": "视觉贴近",
            "relation": "关系贴近",
        }
        reason_parts = [label_map[item] for item in top_dimensions if item in label_map]
        if matched_tags:
            return f"{'、'.join(reason_parts)}，命中标签：{' / '.join(matched_tags[:4])}"
        if reason_parts:
            return f"{'、'.join(reason_parts)}。"
        return "与当前输入的模式和表达方向相近。"

    def _mode_score(self, input_mode: str, candidate_mode: str) -> int:
        if candidate_mode == input_mode:
            return 34
        if candidate_mode == "flower" and input_mode in {"scene", "life"}:
            return 38
        if candidate_mode in {"scene", "life"} and input_mode == "flower":
            return 18
        return 8

    def _intent_score(
        self,
        use_intent: str,
        candidate_scene_tags: list[str],
        candidate_fit_for: list[str],
    ) -> int:
        preferred_tags = set(_expanded_tags(INTENT_PREFERENCES.get(use_intent, [])))
        candidate_tags = set(_expanded_tags(candidate_scene_tags + candidate_fit_for))
        hits = len(preferred_tags & candidate_tags)
        return min(hits, 2) * 7

    def _weighted_overlap(self, source: list[str], target: list[str], weight: int, cap: int) -> int:
        hits = len(set(source) & set(target))
        return min(hits, cap) * weight

    def _passes_threshold(self, score: int, item: ReferenceItem) -> bool:
        if score < REFERENCE_MATCH_THRESHOLD:
            return False
        meaningful_dimensions = [
            "subject",
            "scene",
            "emotion",
            "visual",
            "relation",
            "intent",
        ]
        return any(item.score_breakdown.get(name, 0) > 0 for name in meaningful_dimensions)


def _expanded_tags(tags: list[str]) -> list[str]:
    expanded: list[str] = []
    for tag in tags:
        if not tag:
            continue
        expanded.append(tag)
        expanded.extend(TAG_EXPANSIONS.get(tag, []))
    return _unique(expanded)


def _unique(values: list[str]) -> list[str]:
    seen: set[str] = set()
    ordered: list[str] = []
    for value in values:
        if value not in seen:
            ordered.append(value)
            seen.add(value)
    return ordered


def _as_str_list(values: object) -> list[str]:
    if not isinstance(values, list):
        return []
    return [str(value) for value in values]
