from __future__ import annotations

import json
import os
import re
import time
from functools import lru_cache
from pathlib import Path
from typing import Any, Protocol

import httpx

from app.config.runtime import is_test_mode
from app.schemas.input import AnalyzeInsights, AnalyzeInputRequest, ElementCandidate, InterpretationOption
from app.schemas.mode import ModeResult
from app.schemas.provider_api import ProviderTagTaxonomy, SemanticRecognitionApiRequest
from app.schemas.semantic import SemanticResult
from app.services.mode_detector import ModeDetector
from app.services.semantic_parser import SemanticParser
from app.utils.image_assets import to_provider_image_input
from app.utils.text import new_id

MOCK_ANALYSIS_BASELINE_FILE = Path(__file__).resolve().parent.parent / "data" / "mock_analysis_baselines.json"


class SemanticRecognizer(Protocol):
    def recognize(
        self,
        request: AnalyzeInputRequest,
        content_profile: dict[str, object],
    ) -> AnalyzeInsights: ...


class MockSemanticRecognizer:
    def __init__(self) -> None:
        self.mode_detector = ModeDetector()
        self.semantic_parser = SemanticParser()

    def recognize(
        self,
        request: AnalyzeInputRequest,
        content_profile: dict[str, object],
    ) -> AnalyzeInsights:
        baseline = _find_mock_analysis_baseline(request)
        if baseline:
            return AnalyzeInsights.model_validate(baseline)

        mode_result = self.mode_detector.detect(request.voice_text, content_profile)
        semantic_result = self.semantic_parser.parse(
            mode_result.detected_mode,
            request.voice_text,
            content_profile,
        )
        detected_elements = _build_mock_detected_elements(mode_result.detected_mode, request.voice_text, content_profile)
        interpretation_options = _build_mock_interpretation_options(mode_result, semantic_result, detected_elements)
        recommended = next((item.option_id for item in interpretation_options if item.recommended), None)
        return AnalyzeInsights(
            mode_result=mode_result,
            semantic_result=semantic_result,
            detected_elements=detected_elements,
            needs_user_choice=len(interpretation_options) > 1 and len(detected_elements) > 1,
            interpretation_options=interpretation_options,
            planner_summary=_build_mock_planner_summary(interpretation_options),
            recommended_interpretation_id=recommended,
        )


class ApiSemanticRecognizer:
    """Alibaba Cloud / OpenAI-compatible multimodal semantic recognizer."""

    def _system_prompt(self) -> str:
        return (
            "你是“万物生花”的花艺识别专家。"
            "你的职责是看懂用户给出的图像、焦点区域和文本，把它们转译成后续花艺匹配真正需要的结构化语义。"
            "你不是直接决定最终花束长什么样的审美总监，因此不要急着把所有可见元素都翻译成花材要求。"
            "请输出严格 JSON，不要输出 Markdown。"
        )

    def build_api_request(
        self,
        request: AnalyzeInputRequest,
        content_profile: dict[str, object],
    ) -> SemanticRecognitionApiRequest:
        taxonomy = ProviderTagTaxonomy(
            element_types=["scene", "flower", "person", "portrait", "gift_context", "global"],
            scene_tags=_as_str_list(content_profile.get("scene_tags", [])),
            emotion_tags=_as_str_list(content_profile.get("emotion_tags", [])),
            visual_tags=_as_str_list(content_profile.get("visual_tags", [])),
            relation_tags=_as_str_list(content_profile.get("relation_tags", [])),
            use_intents=["表达氛围", "gift", "self", "decorate", "celebrate"],
        )
        candidate_tags = []
        candidate_tags.extend(_as_str_list(content_profile.get("subject_tags", [])))
        candidate_tags.extend(_as_str_list(content_profile.get("scene_tags", [])))
        candidate_tags.extend(_as_str_list(content_profile.get("emotion_tags", [])))
        candidate_tags.extend(_as_str_list(content_profile.get("visual_tags", [])))
        candidate_tags.extend(_as_str_list(content_profile.get("relation_tags", [])))
        return SemanticRecognitionApiRequest(
            request_id=new_id("semantic_api"),
            image_url=request.image_url,
            selection_box=request.selection_box,
            voice_text=request.voice_text,
            candidate_tags=_unique(candidate_tags),
            taxonomy=taxonomy,
        )

    def recognize(
        self,
        request: AnalyzeInputRequest,
        content_profile: dict[str, object],
    ) -> AnalyzeInsights:
        contract_request = self.build_api_request(request, content_profile)
        base_url = os.getenv("SEMANTIC_API_URL") or os.getenv("QWEN_BASE_URL")
        api_key = os.getenv("SEMANTIC_API_KEY") or os.getenv("DASHSCOPE_API_KEY")
        model = os.getenv("SEMANTIC_MODEL") or os.getenv("QWEN_VL_MODEL") or "qwen-vl-max"
        if not base_url or not api_key:
            raise RuntimeError("未配置语义识别 API 的 URL 或 KEY。")

        payload = {
            "model": model,
            "messages": [
                {
                    "role": "system",
                    "content": self._system_prompt(),
                },
                {
                    "role": "user",
                    "content": [
                        {"type": "image_url", "image_url": {"url": to_provider_image_input(contract_request.image_url)}},
                        {"type": "text", "text": self._build_prompt(contract_request)},
                    ],
                },
            ],
            "temperature": 0.1,
        }

        endpoint = f"{base_url.rstrip('/')}/chat/completions"
        started_at = time.perf_counter()
        try:
            with httpx.Client(timeout=90.0) as client:
                response = client.post(
                    endpoint,
                    headers={
                        "Authorization": f"Bearer {api_key}",
                        "Content-Type": "application/json",
                    },
                    json=payload,
                )
                response.raise_for_status()
        except httpx.HTTPError as exc:
            raise RuntimeError(f"语义识别 API 调用失败：{exc}") from exc

        latency_ms = int((time.perf_counter() - started_at) * 1000)
        data = response.json()
        content = self._extract_message_text(data)
        parsed = self._parse_json_object(content)

        fallback_mode = str(content_profile.get("base_mode", "scene"))
        interpretation_options = self._normalize_interpretation_options(
            parsed.get("interpretation_options"),
            fallback_mode=fallback_mode,
            content_profile=content_profile,
            request=contract_request,
        )
        recommended_interpretation_id = str(parsed.get("recommended_interpretation_id") or "").strip() or None
        recommended_interpretation = _pick_recommended_interpretation(interpretation_options, recommended_interpretation_id)
        primary_payload = recommended_interpretation.semantic_result.model_dump() if recommended_interpretation else parsed
        detected_mode = _normalize_mode(
            recommended_interpretation.recommended_mode if recommended_interpretation else parsed.get("mode"),
            fallback_mode,
        )
        mode_result = ModeResult(
            detected_mode=detected_mode,
            confidence=_clamp_confidence(parsed.get("confidence"), fallback=0.82),
            evidence=_as_str_list(parsed.get("evidence", [])) or ["multimodal_api"],
        )

        semantic_result = self._normalize_semantic_result(
            values=primary_payload,
            detected_mode=detected_mode,
            content_profile=content_profile,
            request=contract_request,
            fallback_text=content,
        )
        if not semantic_result.subject_tags:
            semantic_result.subject_tags = _as_str_list(content_profile.get("subject_tags", []))[:3]

        if latency_ms <= 0:
            mode_result.evidence.append("api_latency_missing")
        detected_elements = self._normalize_detected_elements(parsed.get("detected_elements"))
        if not detected_elements:
            detected_elements = _build_mock_detected_elements(detected_mode, request.voice_text, content_profile)
        if not interpretation_options:
            interpretation_options = _build_mock_interpretation_options(mode_result, semantic_result, detected_elements)
        planner_summary = str(parsed.get("planner_summary") or "").strip()
        if not planner_summary:
            planner_summary = _build_mock_planner_summary(interpretation_options)
        return AnalyzeInsights(
            mode_result=mode_result,
            semantic_result=semantic_result,
            detected_elements=detected_elements,
            needs_user_choice=bool(parsed.get("needs_user_choice")) and len(interpretation_options) > 1,
            interpretation_options=interpretation_options,
            planner_summary=planner_summary,
            recommended_interpretation_id=recommended_interpretation.option_id if recommended_interpretation else recommended_interpretation_id,
        )

    def _build_prompt(self, request: SemanticRecognitionApiRequest) -> str:
        taxonomy = {
            "allowed_modes": request.allowed_modes,
            "scene_tags": request.taxonomy.scene_tags,
            "emotion_tags": request.taxonomy.emotion_tags,
            "visual_tags": request.taxonomy.visual_tags,
            "relation_tags": request.taxonomy.relation_tags,
            "use_intents": request.taxonomy.use_intents,
            "candidate_tags": request.candidate_tags,
        }
        selection = request.selection_box.model_dump()
        return (
            "你是“万物生花”的花艺识别专家，目标不是写一段泛化图像描述，而是提取后续花艺匹配真正需要的语义。\n"
            "“万物生花”的意思是：把用户看到的人、场景、情绪和关系，转译成合适的花艺表达与生花方向。\n"
            "在多专家工作流里，你负责‘看懂并提炼’，不是负责最终审美定稿；因此请区分‘图里看到了什么’与‘后续一定要用什么花材’。\n"
            "请结合图片、selection_box 焦点区域和用户补充文本，先识别元素类型，再给出 1 到 3 个最值得保留的解读候选，输出一个严格 JSON 对象。\n\n"
            "判断优先级：\n"
            "1. 先识别图中主要元素，可用 element_type 包括：scene、flower、person、portrait、gift_context、global。\n"
            "2. 再判断主解读 mode：scene 表示氛围/空间/景别，flower 表示花束或花艺成品本身，life 表示带有人、关系、送礼对象或人生事件的现实情境。纯人像、自拍、个人气质图，一般仍归入 life，但要在 interpretation_options 中显式给出 portrait/person 视角。\n"
            "3. 如果只识别到单一强元素，可直接给出一个主解读；如果存在多种合理视角，必须返回 2 到 3 个 interpretation_options，并用 needs_user_choice 标记是否值得让用户选择。\n"
            "4. interpretation_options 中必须包含一种更综合的 global 或全局视角，用来表达系统对整体气质的理解。\n"
            "5. 先尊重图片里真实可见的信息，再用用户文本补充 use_intent、关系对象和用途，不要让文本覆盖明显的视觉事实。\n"
            "6. 只提取能转译为花艺方案的语义，例如氛围、色调、质感、关系、场景、人物气质和用途；不要沉迷于无关细节、品牌、文字或复杂背景。\n"
            "6.1 color_palette 表示你观察到并认为值得保留的视觉主色线索，不等于后续每个生花方案都必须同时使用这些颜色。\n"
            "7. 对每个 interpretation_option，要补充 explanation 和 alignment_axes，说明你是从哪些维度完成花艺转译的，例如色彩对齐、花语对齐、气质对齐、材质对齐、关系语境对齐。\n"
            "8. planner_summary 需要说明为什么保留这些候选解读，以及建议优先尝试哪一个。\n"
            "9. taxonomy 和 candidate_tags 只是候选约束，不是必须照抄；只在确实匹配图片或文本时选择。\n\n"
            "输出规则：\n"
            "1. mode 只能是 scene / flower / life。\n"
            "2. confidence 返回 0 到 1 的小数。\n"
            "3. evidence 提供 2 到 4 个短语，说明你为什么这样判断。\n"
            "4. subject_tags、scene_tags、emotion_tags、visual_tags、relation_tags、color_palette、translation_axes 都尽量短，单项最多 4 个。\n"
            "5. scene_tags、emotion_tags、visual_tags、relation_tags 尽量优先从 taxonomy 中选；没有合适项时再给自然但简洁的中文标签。\n"
            "6. use_intent 只能是 表达氛围 / gift / self / decorate / celebrate。如果缺乏明确送礼或装饰意图，scene 默认优先考虑“表达氛围”。\n"
            "7. semantic_summary 用 1 句话概括这张图最终想传达并适合被转成花束的感觉。\n"
            "8. raw_caption 用 1 句话忠实描述可见内容。\n"
            "9. interpretation_options 最多 3 个，每个 option 都要内嵌一个 semantic_result。\n"
            "10. 只返回 JSON 对象，不要 Markdown，不要解释，不要额外字段。\n\n"
            f"selection_box={json.dumps(selection, ensure_ascii=False)}\n"
            f"voice_text={request.voice_text or '无'}\n"
            f"taxonomy={json.dumps(taxonomy, ensure_ascii=False)}\n\n"
            "输出 JSON 结构："
            '{"mode":"scene","confidence":0.85,"evidence":["..."],'
            '"detected_elements":[{"element_type":"scene","confidence":0.91,"reason":"..."}],'
            '"needs_user_choice":true,"planner_summary":"...",'
            '"recommended_interpretation_id":"option_scene","subject_tags":["..."],'
            '"scene_tags":["..."],"emotion_tags":["..."],"visual_tags":["..."],'
            '"color_palette":["..."],"relation_tags":["..."],"translation_axes":["色彩对齐"],'
            '"use_intent":"表达氛围","semantic_summary":"...","raw_caption":"...",'
            '"interpretation_options":[{"option_id":"option_scene","label":"从场景氛围解读","perspective":"scene",'
            '"recommended_mode":"scene","recommended":true,"explanation":"...",'
            '"alignment_axes":["色彩对齐","花语对齐"],"semantic_result":{"mode":"scene","subject_tags":["..."],'
            '"scene_tags":["..."],"emotion_tags":["..."],"visual_tags":["..."],"color_palette":["..."],'
            '"relation_tags":["..."],"translation_axes":["色彩对齐"],"use_intent":"表达氛围","semantic_summary":"..."}}]}'
        )

    def _extract_message_text(self, data: dict[str, Any]) -> str:
        choices = data.get("choices")
        if not isinstance(choices, list) or not choices:
            raise RuntimeError(f"语义识别 API 返回格式异常：{data}")
        message = choices[0].get("message", {})
        content = message.get("content", "")
        if isinstance(content, str):
            return content
        if isinstance(content, list):
            parts: list[str] = []
            for item in content:
                if isinstance(item, dict) and item.get("type") == "text":
                    parts.append(str(item.get("text", "")))
                elif isinstance(item, str):
                    parts.append(item)
            if parts:
                return "".join(parts)
        raise RuntimeError(f"语义识别 API 未返回文本内容：{data}")

    def _parse_json_object(self, content: str) -> dict[str, Any]:
        content = content.strip()
        if not content:
            raise RuntimeError("语义识别 API 返回空内容。")
        try:
            return json.loads(content)
        except json.JSONDecodeError:
            pass

        match = re.search(r"\{.*\}", content, flags=re.DOTALL)
        if not match:
            raise RuntimeError(f"语义识别 API 未返回有效 JSON：{content}")
        try:
            return json.loads(match.group(0))
        except json.JSONDecodeError as exc:
            raise RuntimeError(f"语义识别 API JSON 解析失败：{content}") from exc

    def _normalize_tags(self, values: object, fallback: object) -> list[str]:
        normalized = _unique(_as_str_list(values))
        if normalized:
            return normalized[:4]
        return _unique(_as_str_list(fallback))[:4]

    def _normalize_semantic_result(
        self,
        values: object,
        detected_mode: str,
        content_profile: dict[str, object],
        request: SemanticRecognitionApiRequest,
        fallback_text: str,
    ) -> SemanticResult:
        payload = values if isinstance(values, dict) else {}
        return SemanticResult(
            mode=detected_mode,  # type: ignore[arg-type]
            subject_tags=self._normalize_tags(payload.get("subject_tags"), content_profile.get("subject_tags", [])),
            scene_tags=self._normalize_tags(payload.get("scene_tags"), request.taxonomy.scene_tags),
            emotion_tags=self._normalize_tags(payload.get("emotion_tags"), request.taxonomy.emotion_tags),
            visual_tags=self._normalize_tags(payload.get("visual_tags"), request.taxonomy.visual_tags),
            color_palette=self._normalize_tags(payload.get("color_palette"), content_profile.get("color_palette", [])),
            relation_tags=self._normalize_tags(payload.get("relation_tags"), request.taxonomy.relation_tags),
            use_intent=_normalize_use_intent(payload.get("use_intent")),
            semantic_summary=str(payload.get("semantic_summary") or payload.get("raw_caption") or fallback_text).strip(),
            translation_axes=self._normalize_tags(payload.get("translation_axes"), []),
        )

    def _normalize_detected_elements(self, values: object) -> list[ElementCandidate]:
        if not isinstance(values, list):
            return []
        items: list[ElementCandidate] = []
        for value in values[:4]:
            if not isinstance(value, dict):
                continue
            element_type = _normalize_element_type(value.get("element_type"))
            if not element_type:
                continue
            items.append(
                ElementCandidate(
                    element_type=element_type,
                    confidence=_clamp_confidence(value.get("confidence"), fallback=0.7),
                    reason=str(value.get("reason") or "").strip(),
                )
            )
        return items

    def _normalize_interpretation_options(
        self,
        values: object,
        fallback_mode: str,
        content_profile: dict[str, object],
        request: SemanticRecognitionApiRequest,
    ) -> list[InterpretationOption]:
        if not isinstance(values, list):
            return []
        options: list[InterpretationOption] = []
        for index, value in enumerate(values[:3], start=1):
            if not isinstance(value, dict):
                continue
            recommended_mode = _normalize_mode(value.get("recommended_mode"), fallback_mode)
            semantic_result = self._normalize_semantic_result(
                values=value.get("semantic_result") or value,
                detected_mode=recommended_mode,
                content_profile=content_profile,
                request=request,
                fallback_text=str(value.get("explanation") or ""),
            )
            option_id = str(value.get("option_id") or f"option_{index}").strip()
            options.append(
                InterpretationOption(
                    option_id=option_id,
                    label=str(value.get("label") or option_id).strip(),
                    perspective=_normalize_perspective(value.get("perspective")),
                    recommended_mode=recommended_mode,  # type: ignore[arg-type]
                    semantic_result=semantic_result,
                    explanation=str(value.get("explanation") or semantic_result.semantic_summary).strip(),
                    alignment_axes=self._normalize_tags(value.get("alignment_axes"), semantic_result.translation_axes),
                    recommended=bool(value.get("recommended")),
                )
            )
        return options


@lru_cache
def get_semantic_recognizer() -> SemanticRecognizer:
    if is_test_mode():
        return MockSemanticRecognizer()
    provider = os.getenv("SEMANTIC_PROVIDER", "mock").lower()
    if provider == "api":
        return ApiSemanticRecognizer()
    return MockSemanticRecognizer()


def _as_str_list(values: object) -> list[str]:
    if not isinstance(values, list):
        return []
    return [str(value) for value in values]


def _unique(values: list[str]) -> list[str]:
    seen: set[str] = set()
    ordered: list[str] = []
    for value in values:
        if value not in seen:
            ordered.append(value)
            seen.add(value)
    return ordered


def _normalize_mode(value: object, fallback: str) -> str:
    candidate = str(value or fallback).strip().lower()
    if candidate in {"scene", "flower", "life"}:
        return candidate
    return fallback if fallback in {"scene", "flower", "life"} else "scene"


def _normalize_use_intent(value: object) -> str:
    candidate = str(value or "表达氛围").strip()
    if candidate in {"表达氛围", "gift", "self", "decorate", "celebrate"}:
        return candidate
    return "表达氛围"


def _clamp_confidence(value: object, fallback: float) -> float:
    try:
        confidence = float(value)
    except (TypeError, ValueError):
        confidence = fallback
    return max(0.0, min(1.0, confidence))


def _normalize_element_type(value: object) -> str | None:
    candidate = str(value or "").strip().lower()
    if candidate in {"scene", "flower", "person", "portrait", "gift_context", "global"}:
        return candidate
    return None


def _normalize_perspective(value: object) -> str:
    candidate = str(value or "global").strip().lower()
    if candidate in {"scene", "flower", "person", "portrait", "life", "global"}:
        return candidate
    return "global"


def _pick_recommended_interpretation(
    options: list[InterpretationOption],
    recommended_interpretation_id: str | None,
) -> InterpretationOption | None:
    if recommended_interpretation_id:
        for option in options:
            if option.option_id == recommended_interpretation_id:
                return option
    for option in options:
        if option.recommended:
            return option
    return options[0] if options else None


def _build_mock_detected_elements(
    detected_mode: str,
    voice_text: str,
    content_profile: dict[str, object],
) -> list[ElementCandidate]:
    elements: list[ElementCandidate] = []
    if detected_mode == "scene":
        elements.append(ElementCandidate(element_type="scene", confidence=0.9, reason="画面以环境氛围和空间感为主"))
    elif detected_mode == "flower":
        elements.append(ElementCandidate(element_type="flower", confidence=0.94, reason="主体是现成花束或花艺成品"))
    else:
        elements.append(ElementCandidate(element_type="gift_context", confidence=0.86, reason="包含人物关系或现实场景"))

    lowered = voice_text.lower()
    if any(keyword in voice_text for keyword in ["自己", "人像", "自拍", "照片", "肖像"]) or "portrait" in lowered:
        elements.append(ElementCandidate(element_type="portrait", confidence=0.72, reason="文本暗示可从人物气质出发"))
        elements.append(ElementCandidate(element_type="person", confidence=0.7, reason="存在人物视角候选"))
    if _as_str_list(content_profile.get("relation_tags", [])):
        elements.append(ElementCandidate(element_type="gift_context", confidence=0.76, reason="已有关系或送礼语境标签"))
    elements.append(ElementCandidate(element_type="global", confidence=0.68, reason="始终保留一个全局综合视角"))
    unique: dict[str, ElementCandidate] = {}
    for item in elements:
        unique.setdefault(item.element_type, item)
    return list(unique.values())[:4]


def _build_mock_interpretation_options(
    mode_result: ModeResult,
    semantic_result: SemanticResult,
    detected_elements: list[ElementCandidate],
) -> list[InterpretationOption]:
    options: list[InterpretationOption] = [
        InterpretationOption(
            option_id=f"option_{mode_result.detected_mode}",
            label="从当前主视角解读",
            perspective="life" if mode_result.detected_mode == "life" else mode_result.detected_mode,  # type: ignore[arg-type]
            recommended_mode=mode_result.detected_mode,  # type: ignore[arg-type]
            semantic_result=semantic_result,
            explanation="优先保留当前最强的视觉语义，直接进入花艺转译。",
            alignment_axes=_default_alignment_axes(semantic_result),
            recommended=True,
        )
    ]
    element_types = {item.element_type for item in detected_elements}
    if "scene" in element_types and mode_result.detected_mode != "flower":
        options.append(
            InterpretationOption(
                option_id="option_global",
                label="从整体气质解读",
                perspective="global",
                recommended_mode=mode_result.detected_mode,  # type: ignore[arg-type]
                semantic_result=semantic_result.model_copy(
                    update={
                        "translation_axes": _unique(semantic_result.translation_axes + ["整体气质对齐", "色彩对齐"]),
                    }
                ),
                explanation="把场景、情绪和关系合并成一个更完整的花艺方向。",
                alignment_axes=["整体气质对齐", "色彩对齐"],
                recommended=False,
            )
        )
    if "portrait" in element_types or "person" in element_types:
        portrait_semantic = semantic_result.model_copy(
            update={
                "mode": "life",
                "use_intent": "self" if semantic_result.use_intent == "表达氛围" else semantic_result.use_intent,
                "translation_axes": _unique(semantic_result.translation_axes + ["人物气质对齐", "花语对齐"]),
            }
        )
        options.append(
            InterpretationOption(
                option_id="option_portrait",
                label="从人物气质解读",
                perspective="portrait",
                recommended_mode="life",
                semantic_result=portrait_semantic,
                explanation="把人物本身的气质、姿态和分寸转成花束表达。",
                alignment_axes=["人物气质对齐", "花语对齐"],
                recommended=False,
            )
        )
    return options[:3]


def _default_alignment_axes(semantic_result: SemanticResult) -> list[str]:
    axes: list[str] = []
    if semantic_result.color_palette or semantic_result.visual_tags:
        axes.append("色彩对齐")
    if semantic_result.emotion_tags:
        axes.append("情绪气质对齐")
    if semantic_result.relation_tags:
        axes.append("关系语境对齐")
    if not axes:
        axes.append("整体气质对齐")
    return axes[:3]


def _build_mock_planner_summary(options: list[InterpretationOption]) -> str:
    if len(options) <= 1:
        return "当前输入以单一主视角为主，可以直接进入参考检索和生花。"
    labels = "、".join(option.label for option in options[:3])
    return f"当前输入存在多种合理解读，建议先在 {labels} 中选一个主方向，再进入后续生花。"


@lru_cache(maxsize=1)
def _load_mock_analysis_baselines() -> dict[str, Any]:
    if not MOCK_ANALYSIS_BASELINE_FILE.exists():
        return {}
    with MOCK_ANALYSIS_BASELINE_FILE.open("r", encoding="utf-8") as file:
        return json.load(file)


def _find_mock_analysis_baseline(request: AnalyzeInputRequest) -> dict[str, Any] | None:
    baselines = _load_mock_analysis_baselines()
    image_name = Path(request.image_url).name
    for key in (request.content_id, image_name):
        if key and key in baselines:
            return baselines[key]
    return None
