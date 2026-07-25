from __future__ import annotations

from pathlib import Path
from urllib.parse import urlparse

from app.repositories.content_repository import ContentRepository
from app.utils.scoring import overlap_score
from app.utils.text import contains_any


FILENAME_TOKEN_MAP = {
    "sunset": ["晚霞", "日落", "海边"],
    "rain": ["雨天", "下雨", "安静"],
    "window": ["窗边", "室内"],
    "seaside": ["海边", "旅行"],
    "sea": ["海边", "开阔"],
    "windy": ["风", "旷野"],
    "field": ["旷野", "自然"],
    "room": ["房间", "家"],
    "cream": ["奶白", "居家"],
    "dining": ["餐桌", "家人"],
    "table": ["桌面", "日常"],
    "cafe": ["咖啡馆", "独处"],
    "coffee": ["咖啡馆", "朋友见面"],
    "street": ["街景", "城市"],
    "night": ["夜晚", "夜色"],
    "pink": ["粉白", "生日"],
    "blue": ["蓝白", "克制"],
    "white": ["白色", "留白"],
    "champagne": ["香槟色", "祝贺"],
    "wild": ["野生感", "自由"],
    "red": ["红橙", "热烈"],
    "orange": ["红橙", "纪念"],
    "promotion": ["升职", "祝贺", "朋友"],
    "birthday": ["生日", "朋友"],
    "mother": ["妈妈", "家人"],
    "visit": ["探望", "同事"],
    "colleague": ["同事", "探望"],
    "couple": ["恋人", "纪念日"],
    "anniversary": ["纪念日", "恋人"],
    "thanks": ["感谢", "正式"],
    "leader": ["领导", "感谢"],
    "gift": ["送礼"],
    "bouquet": ["花束", "送礼"],
}

MODE_HINT_KEYWORDS = {
    "scene": ["晚霞", "海边", "窗边", "雨天", "房间", "街景", "咖啡馆", "场景"],
    "flower": ["花束", "包装", "桌花", "花艺", "花材"],
    "life": ["朋友", "同事", "领导", "恋人", "妈妈", "送礼", "升职", "生日", "纪念日"],
}


class VisionSemanticExtractor:
    """First-pass semantic extraction backed by the annotated asset library.

    This version does not depend on a real vision model yet. It scores annotated
    asset groups using image filename hints plus voice text, so we can provide a
    stable fallback path before we swap in embedding or multimodal inference.
    """

    def __init__(self, repository: ContentRepository) -> None:
        self.repository = repository

    def extract(self, image_url: str, voice_text: str) -> dict[str, object] | None:
        query_terms = self._collect_query_terms(image_url=image_url, voice_text=voice_text)
        if not query_terms:
            if image_url.startswith("data:image/"):
                return self._build_generic_profile(voice_text)
            return None

        scored_groups: list[tuple[int, dict[str, object]]] = []
        for group in self.repository.list_asset_groups():
            score = self._score_group(group=group, query_terms=query_terms, voice_text=voice_text)
            if score <= 0:
                continue
            scored_groups.append((score, group))

        if not scored_groups:
            if image_url.startswith("data:image/"):
                return self._build_generic_profile(voice_text)
            return None

        scored_groups.sort(key=lambda item: item[0], reverse=True)
        best_score, best_group = scored_groups[0]
        if best_score < 18:
            if image_url.startswith("data:image/"):
                return self._build_generic_profile(voice_text)
            return None

        top_groups = [group for _, group in scored_groups[:3]]
        return self._build_profile_from_matches(query_terms=query_terms, matched_groups=top_groups)

    def _collect_query_terms(self, image_url: str, voice_text: str) -> list[str]:
        query_terms: list[str] = []
        image_name = self._extract_image_name(image_url)
        stem = Path(image_name).stem.lower()

        for part in stem.replace("-", "_").split("_"):
            if not part or part.isdigit():
                continue
            query_terms.append(part)
            query_terms.extend(FILENAME_TOKEN_MAP.get(part, []))

        for mode, keywords in MODE_HINT_KEYWORDS.items():
            if contains_any(voice_text, keywords):
                query_terms.append(mode)
            query_terms.extend(contains_any(voice_text, keywords))

        query_terms.extend(
            contains_any(
                voice_text,
                [
                    "克制",
                    "治愈",
                    "安静",
                    "轻治愈",
                    "温暖",
                    "正式",
                    "祝贺",
                    "感谢",
                    "朋友",
                    "同事",
                    "领导",
                    "恋人",
                    "家人",
                    "妈妈",
                    "日常",
                    "送礼",
                    "纪念日",
                    "生日",
                ],
            )
        )
        return _unique(query_terms)

    def _score_group(self, group: dict[str, object], query_terms: list[str], voice_text: str) -> int:
        search_terms: list[str] = []
        search_terms.append(str(group.get("group_id", "")))
        search_terms.append(str(group.get("title", "")))
        search_terms.extend(group.get("images", []))
        search_terms.extend(group.get("visual_tags", []))
        search_terms.extend(group.get("emotion_tags", []))
        search_terms.extend(group.get("scene_tags", []))
        search_terms.extend(group.get("fit_for", []))

        if group.get("target_relation"):
            search_terms.append(str(group["target_relation"]))
        if group.get("recommended_bouquet_title"):
            search_terms.append(str(group["recommended_bouquet_title"]))
        if group.get("alternate_bouquet_title"):
            search_terms.append(str(group["alternate_bouquet_title"]))

        score = 0
        score += overlap_score(query_terms, search_terms, 6)

        group_mode = str(group.get("mode", "scene"))
        if group_mode in query_terms:
            score += 10

        title = str(group.get("title", ""))
        if title and title in voice_text:
            score += 12

        if group_mode == "life" and contains_any(voice_text, ["朋友", "同事", "领导", "恋人", "妈妈", "家人"]):
            score += 4
        if group_mode == "flower" and contains_any(voice_text, ["花束", "桌花", "包装", "花艺"]):
            score += 4
        if group_mode == "scene" and contains_any(voice_text, ["场景", "窗边", "晚霞", "海边", "房间", "街景"]):
            score += 4

        return score

    def _build_profile_from_matches(
        self,
        query_terms: list[str],
        matched_groups: list[dict[str, object]],
    ) -> dict[str, object]:
        primary_group = matched_groups[0]
        base_mode = str(primary_group.get("mode", "scene"))

        subject_tags = [str(primary_group.get("title", ""))]
        relation_tags: list[str] = []
        scene_tags: list[str] = []
        emotion_tags: list[str] = []
        visual_tags: list[str] = []
        color_palette: list[str] = []

        for group in matched_groups:
            if group.get("target_relation"):
                relation_tags.append(str(group["target_relation"]))
            relation_tags.extend(group.get("fit_for", []))
            scene_tags.extend(group.get("scene_tags", []))
            emotion_tags.extend(group.get("emotion_tags", []))
            visual_tags.extend(group.get("visual_tags", []))
            color_palette.extend(group.get("color_palette", []))

        subject_tags.extend([term for term in query_terms if term in {"晚霞", "窗边", "雨天", "海边", "升职", "生日", "感谢", "领导"}])

        return {
            "base_mode": base_mode,
            "subject_tags": _unique([item for item in subject_tags if item]),
            "scene_tags": _unique(scene_tags)[:5],
            "emotion_tags": _unique(emotion_tags)[:5],
            "visual_tags": _unique(visual_tags)[:5],
            "color_palette": _unique(color_palette)[:4],
            "relation_tags": _unique(relation_tags),
            "source_type": "vision_semantic_fallback",
            "matched_group_ids": [str(group.get("group_id", "")) for group in matched_groups],
        }

    def _extract_image_name(self, image_url: str) -> str:
        parsed = urlparse(image_url)
        candidate = parsed.path or image_url
        return Path(candidate).name

    def _build_generic_profile(self, voice_text: str) -> dict[str, object]:
        if contains_any(voice_text, ["朋友", "同事", "领导", "恋人", "妈妈", "家人", "升职", "生日", "感谢"]):
            return {
                "base_mode": "life",
                "subject_tags": ["现实情境", "送礼表达"],
                "scene_tags": _unique(contains_any(voice_text, ["升职", "生日", "感谢", "送礼", "纪念日"])) or ["送礼"],
                "emotion_tags": _unique(contains_any(voice_text, ["克制", "治愈", "温暖", "正式", "祝贺"])) or ["克制", "温暖"],
                "visual_tags": ["干净", "利落"],
                "color_palette": [],
                "relation_tags": _unique(contains_any(voice_text, ["朋友", "同事", "领导", "恋人", "妈妈", "家人"])),
                "source_type": "generic_upload_fallback",
            }

        return {
            "base_mode": "scene",
            "subject_tags": ["上传画面", "待转译场景"],
            "scene_tags": _unique(contains_any(voice_text, ["窗边", "海边", "雨天", "房间", "街景"])) or ["场景"],
            "emotion_tags": _unique(contains_any(voice_text, ["克制", "治愈", "安静", "温暖", "轻治愈"])) or ["治愈", "克制"],
            "visual_tags": _unique(contains_any(voice_text, ["留白", "冷色", "暖色", "空气感"])) or ["空气感"],
            "color_palette": [],
            "relation_tags": [],
            "source_type": "generic_upload_fallback",
        }


def _unique(values: list[str]) -> list[str]:
    seen: set[str] = set()
    ordered: list[str] = []
    for value in values:
        if value not in seen:
            ordered.append(value)
            seen.add(value)
    return ordered
