from __future__ import annotations

from app.schemas.mode import ModeType
from app.schemas.semantic import SemanticResult
from app.utils.text import contains_any


GIFT_KEYWORDS = ["送", "礼物", "朋友", "生日", "升职", "探望"]
SELF_KEYWORDS = ["收藏", "自己", "桌花", "放家里"]
CELEBRATE_KEYWORDS = ["庆祝", "升职", "婚礼", "纪念日"]

RELATION_KEYWORDS = {
    "朋友": "朋友",
    "同事": "同事",
    "领导": "领导",
    "恋人": "恋人",
    "妈妈": "家人",
    "家人": "家人",
}

EMOTION_HINTS = {
    "不要太甜": "克制",
    "高级一点": "高级",
    "暖一点": "温暖",
    "温柔": "温柔",
    "治愈": "治愈",
    "热烈": "热烈",
}


class SemanticParser:
    def parse(
        self,
        mode: ModeType,
        voice_text: str,
        content_profile: dict[str, object] | None,
    ) -> SemanticResult:
        voice_text = voice_text or ""
        profile = content_profile or {}

        subject_tags = list(profile.get("subject_tags", []))
        scene_tags = list(profile.get("scene_tags", []))
        emotion_tags = list(profile.get("emotion_tags", []))
        visual_tags = list(profile.get("visual_tags", []))
        color_palette = list(profile.get("color_palette", []))
        relation_tags = list(profile.get("relation_tags", []))

        if contains_any(voice_text, GIFT_KEYWORDS):
            use_intent = "gift"
        elif contains_any(voice_text, SELF_KEYWORDS):
            use_intent = "self"
        elif contains_any(voice_text, CELEBRATE_KEYWORDS):
            use_intent = "celebrate"
        elif mode == "scene":
            use_intent = "表达氛围"
        else:
            use_intent = "decorate"

        for keyword, relation in RELATION_KEYWORDS.items():
            if keyword in voice_text and relation not in relation_tags:
                relation_tags.append(relation)

        for keyword, emotion in EMOTION_HINTS.items():
            if keyword in voice_text and emotion not in emotion_tags:
                emotion_tags.append(emotion)

        if "预算" in voice_text or "以内" in voice_text:
            scene_tags.append("预算敏感")
        if "送" in voice_text and "送礼" not in scene_tags:
            scene_tags.append("送礼")

        summary = self._build_summary(mode, scene_tags, emotion_tags, visual_tags, relation_tags, use_intent)

        return SemanticResult(
            mode=mode,
            subject_tags=subject_tags,
            scene_tags=_unique(scene_tags),
            emotion_tags=_unique(emotion_tags),
            visual_tags=_unique(visual_tags),
            color_palette=color_palette,
            relation_tags=_unique(relation_tags),
            use_intent=use_intent,
            semantic_summary=summary,
        )

    def _build_summary(
        self,
        mode: ModeType,
        scene_tags: list[str],
        emotion_tags: list[str],
        visual_tags: list[str],
        relation_tags: list[str],
        use_intent: str,
    ) -> str:
        mode_text = {
            "scene": "一个从场景生花的输入",
            "flower": "一个从花再生的输入",
            "life": "一个从人生生花的输入",
        }[mode]
        parts = [mode_text]
        if visual_tags:
            parts.append(f"视觉上偏{visual_tags[0]}")
        if emotion_tags:
            parts.append(f"情绪上更接近{emotion_tags[0]}")
        if relation_tags:
            parts.append(f"关系对象是{relation_tags[0]}")
        parts.append(f"当前用途偏向{use_intent}")
        if scene_tags:
            parts.append(f"场景关键词包括{scene_tags[0]}")
        return "，".join(parts) + "。"


def _unique(values: list[str]) -> list[str]:
    seen: set[str] = set()
    ordered: list[str] = []
    for value in values:
        if value not in seen:
            ordered.append(value)
            seen.add(value)
    return ordered
