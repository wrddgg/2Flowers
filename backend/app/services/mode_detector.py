from __future__ import annotations

from app.schemas.mode import ModeResult
from app.utils.text import contains_any


FLOWER_KEYWORDS = ["花束", "配色", "这朵", "包装", "删掉", "换花", "花艺"]
LIFE_KEYWORDS = ["她", "他", "朋友", "生日", "升职", "送", "恋人", "妈妈", "同事"]
SCENE_KEYWORDS = ["晚霞", "房间", "下雨", "场景", "窗边", "海边", "街景", "把这场"]


class ModeDetector:
    def detect(self, voice_text: str, content_profile: dict[str, object] | None) -> ModeResult:
        voice_text = voice_text or ""
        evidence: list[str] = []
        scores = {"scene": 0.2, "flower": 0.2, "life": 0.2}

        if content_profile:
            base_mode = str(content_profile.get("base_mode", "scene"))
            scores[base_mode] += 0.35
            evidence.append(f"content:{base_mode}")
            for tag in content_profile.get("subject_tags", []):
                evidence.append(f"subject:{tag}")

        flower_hits = contains_any(voice_text, FLOWER_KEYWORDS)
        life_hits = contains_any(voice_text, LIFE_KEYWORDS)
        scene_hits = contains_any(voice_text, SCENE_KEYWORDS)

        scores["flower"] += len(flower_hits) * 0.12
        scores["life"] += len(life_hits) * 0.12
        scores["scene"] += len(scene_hits) * 0.10

        evidence.extend(f"voice:{keyword}" for keyword in flower_hits + life_hits + scene_hits)

        detected_mode = max(scores, key=scores.get)
        confidence = min(round(scores[detected_mode], 2), 0.97)

        return ModeResult(
            detected_mode=detected_mode,  # type: ignore[arg-type]
            confidence=confidence,
            evidence=evidence[:6],
        )
