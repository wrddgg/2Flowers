from __future__ import annotations

import json
import os
import time
from functools import lru_cache
from typing import Any, Protocol

import httpx

from app.config.runtime import is_test_mode
from app.schemas.bouquet import (
    BouquetResult,
    FlowerInfo,
    FlowerMaterialPlan,
    GenerateBouquetRequest,
    GenerationVariantPlan,
)
from app.schemas.provider_api import (
    GeneratedBouquetImage,
    ImageGenerationApiRequest,
    ImageGenerationApiResponse,
    ImageGenerationConstraints,
    ProviderReferenceInput,
)
from app.services.workflow_clients import call_multimodal_json, resolve_workflow_text_config
from app.services.bouquet_generator import BouquetGenerator
from app.utils.image_assets import to_provider_image_input
from app.utils.text import new_id

SCENE_CONSTRAINTS = {
    "礼宾赠礼": "场景为礼宾赠礼或正式拜访。花束需要体现尊重、欢迎、克制和仪式感，整体为中小型，总枝数控制在11-16枝。采用挺拔、舒展且便于单手持握的结构，主花数量少而精，线性花拉开轮廓，枝叶之间保留明显呼吸空间。视觉上高级、得体，不抢夺人物注意力。禁止过度甜美、强烈恋爱暗示、儿童化装饰、巨大花团和过于私人化的花语。",
    "庆祝纪念": "场景为生日、毕业、获奖或重要纪念。花束需要传递喜悦、活力和向上生长的情绪，整体为中等饱满度，总枝数控制在14-20枝。轮廓应有轻微上扬或向外绽放的动势，主花醒目，点缀花具有节奏感，适合合影和社交分享。配色可以明快，但必须来自输入画面的色彩关系。禁止过度庄重、沉闷低垂、廉价彩虹配色以及用大量花材制造虚假热闹。",
    "恋人赠礼": "场景为恋人赠礼。花束需要表达明确、浓烈但不俗艳的爱意，整体为中等偏饱满结构，总枝数控制在18-24枝。主花形成集中而清晰的情感焦点，过渡花营造包裹感，点缀花增加细腻层次，线性花向外延伸情绪。通过色彩浓度、花瓣质感和聚焦关系表现爱意，不依靠盲目增加花量。禁止礼宾式疏离感、夸张心形、满屏红玫瑰以及婚礼手捧球式密集堆叠。",
    "日常居家": "场景为自我陶冶情操、日常疗愈或家居摆放。花束需要自然、松弛、耐看，整体为小型至中小型，总枝数控制在8-14枝。减少包装感和强仪式感，保留自然枝条与花材原有姿态，适合插入普通花瓶并长期观看。色彩柔和但不能寡淡，结构轻盈、有呼吸感，重点表现平静和生活气息。禁止复杂包装、亮片装饰、过度饱满和强烈商业礼花感。",
}

STYLE_CONSTRAINTS = {
    "东方留白": "采用东方留白风格。使用自然非对称构图，花束中保留约35%-50%的视觉留白，通过高位主枝、中位副枝和低位基底枝建立清晰的高低关系。主花数量少而有焦点，线性花负责延伸轮廓，枝叶之间必须留出呼吸空间。配色克制，以输入画面的主色为基础，只设置一个小面积强调色。禁止密集圆团、左右对称、封闭轮廓和把所有空隙全部填满。",
    "法式浪漫": "采用法式浪漫花园风格。整体呈松弛的椭圆形或轻微S形轮廓，花材层层展开但不紧密压缩，保留约25%-35%的自然空隙。使用柔和曲线、渐变色彩和不同花瓣质感营造浪漫感，主花与小型点缀花之间形成自然过渡。花束应像刚从花园采集后经过专业整理，精致但不过度规整。禁止婚礼手捧球式圆团、蕾丝堆砌、过度粉嫩和刻意对称。",
    "清新自然": "采用清新自然风格。模拟花材在自然环境中的生长状态，花枝长度错落、方向舒展，整体轻盈、透气并带有微风感。主花保持一个明确视觉焦点，点缀花分散形成节奏，线性花向上或向侧面自然伸展。配色清澈、明快，保留约30%-40%的呼吸空间。自然不等于杂乱，必须保持清晰轮廓和视觉重心。禁止随机插放、花头平均分布、塑料感和过度包装。",
    "现代艺术": "采用现代艺术与雕塑感风格。使用简洁、鲜明的几何轮廓和具有方向性的线条，强调花材之间的形态对比、负空间和视觉张力。整体配色控制在2-3个主要色系，可以使用现实存在但形态独特的花材，形成具有展览感的单一视觉焦点。结构可以大胆，但必须符合真实插花的支撑逻辑并能够实际制作。禁止为了科技感加入虚假霓虹花、金属花瓣、无重力悬浮和不可实现的复杂结构。",
}

DEFAULT_SCENE_BY_MODE = {
    "scene": "日常居家",
    "flower": "庆祝纪念",
    "life": "礼宾赠礼",
}

DEFAULT_STYLE_BY_FOCUS = {
    "atmosphere": "东方留白",
    "color": "法式浪漫",
    "persona": "清新自然",
    "material": "现代艺术",
    "premium": "现代艺术",
    "coherence": "东方留白",
    "symbolism": "法式浪漫",
}

LAYOUT_POINTS = {
    "mass": [[0.5, 0.26], [0.36, 0.38], [0.64, 0.38], [0.44, 0.54], [0.58, 0.56]],
    "layered": [[0.52, 0.24], [0.35, 0.35], [0.68, 0.42], [0.4, 0.57], [0.62, 0.65]],
    "airy": [[0.5, 0.2], [0.3, 0.34], [0.72, 0.4], [0.42, 0.58], [0.62, 0.7]],
    "focal": [[0.52, 0.3], [0.38, 0.42], [0.64, 0.44], [0.46, 0.58], [0.58, 0.64]],
}

FLOWER_LIBRARY = {
    "白洋桔梗": {"type": "主花", "meaning": "温柔、克制", "role": "负责留白和轻盈的主体层"},
    "蓝绣球": {"type": "结构花", "meaning": "包裹感与体量", "role": "提供稳定色块与结构支撑"},
    "尤加利": {"type": "叶材", "meaning": "清爽、松弛", "role": "拉开空间并让轮廓更自然"},
    "白玫瑰": {"type": "主花", "meaning": "纯净、分寸感", "role": "作为视觉焦点压住甜度"},
    "银叶菊": {"type": "配叶", "meaning": "冷静、柔化边界", "role": "柔和花束边界并增加冷感层次"},
    "蓝星花": {"type": "点缀花", "meaning": "清透、安静", "role": "补充细小星点与空气感"},
    "橙玫瑰": {"type": "主花", "meaning": "热烈、庆祝", "role": "构成暖色主焦点"},
    "粉康乃馨": {"type": "辅助花", "meaning": "温柔、亲近", "role": "提供更柔和的情绪过渡"},
    "落日飞燕": {"type": "线条花", "meaning": "上扬、梦幻", "role": "拉开外轮廓和向上节奏"},
    "飞燕草": {"type": "线条花", "meaning": "自由、上扬", "role": "提供灵动的纵向线条"},
    "白芍药": {"type": "主花", "meaning": "柔软、丰盈", "role": "增加花头层次和温柔体量"},
    "奶油玫瑰": {"type": "主花", "meaning": "安心、温暖", "role": "形成柔和而高级的核心花面"},
    "洋甘菊": {"type": "点缀花", "meaning": "日常、治愈", "role": "加入轻松的日常氛围"},
    "香雪兰": {"type": "辅助花", "meaning": "轻柔、细腻", "role": "补足香气感和细碎层次"},
    "绿铃草": {"type": "线条花", "meaning": "舒展、轻松", "role": "延展外轮廓并保持呼吸感"},
    "白郁金香": {"type": "主花", "meaning": "安静、利落", "role": "建立清爽干净的主轮廓"},
    "蕨叶": {"type": "叶材", "meaning": "自然、松弛", "role": "让整体更接近日常自然状态"},
    "粉玫瑰": {"type": "主花", "meaning": "温柔、亲近", "role": "承担友好和柔软的主情绪"},
    "珍珠梅": {"type": "点缀花", "meaning": "精致、轻巧", "role": "补充细小层次和礼物感"},
    "香槟玫瑰": {"type": "主花", "meaning": "成熟、祝贺", "role": "承接正式而明亮的赠礼语气"},
    "向日葵": {"type": "主花", "meaning": "积极、向上", "role": "形成强烈的庆祝视觉中心"},
    "金鱼草": {"type": "线条花", "meaning": "挺拔、利落", "role": "增强结构的向上感"},
    "白百合": {"type": "主花", "meaning": "庄重、安稳", "role": "增强正式感与仪式感"},
    "康乃馨": {"type": "辅助花", "meaning": "照顾、温暖", "role": "让关系表达更有人情味"},
    "风铃草": {"type": "辅助花", "meaning": "松弛、呼吸感", "role": "补足轻盈层次与松弛感"},
    "麦穗": {"type": "线条花", "meaning": "自然、生长感", "role": "强化野生和生长方向"},
    "火鹤": {"type": "焦点花", "meaning": "表达力、热烈", "role": "形成明确的视觉重击点"},
    "重瓣康乃馨": {"type": "辅助花", "meaning": "丰盛、饱满", "role": "增加饱满度和情绪厚度"},
    "郁金香": {"type": "主花", "meaning": "纪念感、利落", "role": "形成简洁有力的主轮廓"},
    "蕾丝花": {"type": "点缀花", "meaning": "梦幻、柔和", "role": "让恋爱感更细腻而不俗气"},
    "绿掌": {"type": "结构叶材", "meaning": "利落、清爽", "role": "收紧轮廓并提升现代感"},
    "橙洋桔梗": {"type": "辅助花", "meaning": "轻庆祝、温暖", "role": "柔和过渡主色层次"},
    "乒乓菊": {"type": "点缀花", "meaning": "轻快、礼物感", "role": "增加圆润和活泼感"},
}

FOCUS_FLOWER_HINTS = {
    "atmosphere": ["白洋桔梗", "银叶菊", "蓝星花", "尤加利"],
    "color": ["橙玫瑰", "粉康乃馨", "香槟玫瑰", "橙洋桔梗"],
    "persona": ["白郁金香", "风铃草", "香雪兰", "粉玫瑰"],
    "material": ["火鹤", "白芍药", "麦穗", "绿掌"],
    "premium": ["香槟玫瑰", "白郁金香", "白百合", "奶油玫瑰"],
    "coherence": ["白玫瑰", "白洋桔梗", "尤加利", "银叶菊"],
    "symbolism": ["向日葵", "白百合", "郁金香", "康乃馨"],
}

SCENE_FLOWER_HINTS = {
    "礼宾赠礼": ["白百合", "香槟玫瑰", "绿掌", "金鱼草"],
    "庆祝纪念": ["向日葵", "香槟玫瑰", "橙玫瑰", "金鱼草"],
    "恋人赠礼": ["奶油玫瑰", "郁金香", "蕾丝花", "粉玫瑰"],
    "日常居家": ["白洋桔梗", "洋甘菊", "香雪兰", "尤加利"],
}

STYLE_FLOWER_HINTS = {
    "东方留白": ["白洋桔梗", "白郁金香", "银叶菊", "绿铃草"],
    "法式浪漫": ["奶油玫瑰", "白芍药", "香雪兰", "蕾丝花"],
    "清新自然": ["风铃草", "飞燕草", "洋甘菊", "尤加利"],
    "现代艺术": ["火鹤", "绿掌", "白百合", "蓝绣球"],
}

FLOWER_ZONE_POINTS = {
    "mass": {
        "focal_center": [[0.5, 0.3], [0.48, 0.36]],
        "main_left": [[0.38, 0.38], [0.34, 0.46]],
        "main_right": [[0.63, 0.39], [0.66, 0.47]],
        "upper_line": [[0.48, 0.18], [0.6, 0.2]],
        "side_structure": [[0.28, 0.42], [0.72, 0.44]],
        "outer_leaf": [[0.24, 0.62], [0.76, 0.62], [0.5, 0.7]],
        "accent": [[0.44, 0.52], [0.58, 0.54], [0.36, 0.56]],
    },
    "layered": {
        "focal_center": [[0.52, 0.34], [0.48, 0.42]],
        "main_left": [[0.39, 0.42], [0.34, 0.53]],
        "main_right": [[0.64, 0.44], [0.69, 0.55]],
        "upper_line": [[0.42, 0.18], [0.62, 0.22], [0.76, 0.3]],
        "side_structure": [[0.3, 0.33], [0.72, 0.36]],
        "outer_leaf": [[0.28, 0.68], [0.74, 0.7], [0.48, 0.78]],
        "accent": [[0.46, 0.56], [0.58, 0.62], [0.4, 0.63]],
    },
    "airy": {
        "focal_center": [[0.5, 0.38], [0.46, 0.46]],
        "main_left": [[0.34, 0.46], [0.28, 0.57]],
        "main_right": [[0.66, 0.44], [0.74, 0.56]],
        "upper_line": [[0.46, 0.14], [0.66, 0.18], [0.26, 0.24]],
        "side_structure": [[0.24, 0.36], [0.76, 0.4]],
        "outer_leaf": [[0.18, 0.68], [0.82, 0.66], [0.5, 0.78]],
        "accent": [[0.42, 0.58], [0.6, 0.6], [0.32, 0.64]],
    },
    "focal": {
        "focal_center": [[0.52, 0.28], [0.5, 0.36]],
        "main_left": [[0.4, 0.4], [0.36, 0.5]],
        "main_right": [[0.64, 0.42], [0.68, 0.52]],
        "upper_line": [[0.56, 0.14], [0.38, 0.2]],
        "side_structure": [[0.28, 0.46], [0.74, 0.48]],
        "outer_leaf": [[0.24, 0.7], [0.78, 0.68], [0.5, 0.78]],
        "accent": [[0.46, 0.56], [0.58, 0.58], [0.34, 0.6]],
    },
}

FLOWER_CATEGORY_LABELS = {
    "main": "主花材",
    "transition": "过渡花材",
    "accent": "点缀花材",
    "linear": "线性花材",
}

FLOWER_CATEGORY_STEM_RANGES = {
    "main": [2, 4],
    "transition": [2, 4],
    "accent": [1, 3],
    "linear": [1, 2],
}

FLOWER_CATEGORY_LIMITS = {
    "main": 2,
    "transition": 2,
    "accent": 1,
    "linear": 1,
}

DEFAULT_CATEGORY_SPECIES_BY_SCENE = {
    "礼宾赠礼": {
        "main": ["香槟玫瑰", "白百合"],
        "transition": ["绿掌", "康乃馨"],
        "accent": ["珍珠梅"],
        "linear": ["金鱼草"],
    },
    "庆祝纪念": {
        "main": ["向日葵", "橙玫瑰"],
        "transition": ["橙洋桔梗", "粉康乃馨"],
        "accent": ["乒乓菊"],
        "linear": ["金鱼草"],
    },
    "恋人赠礼": {
        "main": ["奶油玫瑰", "郁金香"],
        "transition": ["香雪兰", "粉玫瑰"],
        "accent": ["蕾丝花"],
        "linear": ["绿铃草"],
    },
    "日常居家": {
        "main": ["白洋桔梗", "白郁金香"],
        "transition": ["香雪兰", "尤加利"],
        "accent": ["洋甘菊"],
        "linear": ["尤加利"],
    },
}

FLOWER_RECOGNITION_SYSTEM_PROMPT = (
    "你是“万物生花”的花材锚点识别专家。"
    "你的目标不是完整检测整束花，而是为用户交互挑出每种主要花材的一朵代表花。"
    "请只识别真实可见、名字合理、适合作为交互锚点的花材。"
    "不确定就跳过，不要乱猜，不要输出虚构花名。"
    "只输出严格 JSON。"
)

FLOWER_NAME_PREFIXES = [
    "浅粉",
    "深蓝",
    "暖白",
    "香槟",
    "奶油",
    "重瓣",
    "白",
    "粉",
    "蓝",
    "橙",
    "黄",
    "红",
]


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
        raw_plans = request.variant_plans or self.generator_default_plan(request)
        plan_used = [_decorate_variant_plan(plan, request) for plan in raw_plans]
        results = self.generator.generate(request, bouquet_templates, reference_map)
        return _enrich_bouquet_results(results, request, plan_used, reference_map), plan_used

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
            selected_scene=request.selected_scene,
            selected_style=request.selected_style,
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
        plan_used = [_decorate_variant_plan(plan, request) for plan in self._resolve_variant_plans(contract_request)]
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
        return _enrich_bouquet_results(merged_results, request, plan_used, reference_map), plan_used

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
        if request.selected_scene:
            lines.append(f"指定场景：{request.selected_scene}")
            lines.append(f"场景硬约束：{SCENE_CONSTRAINTS.get(request.selected_scene, request.selected_scene)}")
        if request.selected_style:
            lines.append(f"指定风格：{request.selected_style}")
            lines.append(f"风格硬约束：{STYLE_CONSTRAINTS.get(request.selected_style, request.selected_style)}")
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
        engine = os.getenv("IMAGE_GENERATION_ENGINE", "dashscope").lower()
        if engine == "doubao":
            return self._call_doubao_generation_api(request=request, variant=variant)

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

    def _call_doubao_generation_api(
        self,
        request: ImageGenerationApiRequest,
        variant: GenerationVariantPlan,
    ) -> ImageGenerationApiResponse:
        """火山引擎方舟（ARK）images/generations 同步生图。

        配置项：
          DOUBAO_BASE_URL  默认 https://ark.cn-beijing.volces.com/api/v3
          DOUBAO_API_KEY   方舟 API Key（也可回落 ARK_API_KEY / IMAGE_GENERATION_API_KEY / DASHSCOPE_API_KEY）
          DOUBAO_IMAGE_MODEL 默认 doubao-seedream-5.0-lite
        """
        base_url = (
            os.getenv("DOUBAO_BASE_URL")
            or "https://ark.cn-beijing.volces.com/api/v3"
        )
        api_key = (
            os.getenv("DOUBAO_API_KEY")
            or os.getenv("ARK_API_KEY")
            or os.getenv("IMAGE_GENERATION_API_KEY")
            or os.getenv("DASHSCOPE_API_KEY")
        )
        model = os.getenv("DOUBAO_IMAGE_MODEL") or "doubao-seedream-5.0-lite"
        if not api_key:
            raise RuntimeError("未配置火山方舟生图的 API KEY（DOUBAO_API_KEY）。")

        endpoint = f"{base_url.rstrip('/')}/images/generations"
        prompt = self._build_generation_prompt(request, variant)
        size = self._map_doubao_size(request.generation_constraints.aspect_ratio)
        payload: dict[str, Any] = {
            "model": model,
            "prompt": prompt,
            "response_format": "url",
            "watermark": False,
        }
        if size:
            payload["size"] = size

        started_at = time.perf_counter()
        try:
            with httpx.Client(timeout=120.0) as client:
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
            raise RuntimeError(f"火山方舟生图失败：{exc}") from exc

        latency_ms = int((time.perf_counter() - started_at) * 1000)
        data = response.json()
        images = self._extract_doubao_images(data)
        if not images:
            raise RuntimeError(f"火山方舟生图未返回图片：{data}")
        return ImageGenerationApiResponse(
            request_id=str(data.get("id") or new_id("doubao")),
            provider_name="doubao",
            model_name=model,
            images=images,
            latency_ms=latency_ms,
        )

    def _extract_doubao_images(self, data: dict[str, Any]) -> list[GeneratedBouquetImage]:
        images: list[GeneratedBouquetImage] = []
        for item in data.get("data", []) or []:
            if not isinstance(item, dict):
                continue
            image_url = item.get("url")
            b64 = item.get("b64_json")
            if image_url:
                final_url = str(image_url)
            elif b64:
                final_url = f"data:image/png;base64,{b64}"
            else:
                continue
            images.append(
                GeneratedBouquetImage(
                    image_url=final_url,
                    prompt_summary="doubao_generation",
                    revised_prompt=str(item.get("revised_prompt") or ""),
                    seed=None,
                    provider_metadata={"engine": "doubao"},
                )
            )
        return images

    def _map_doubao_size(self, aspect_ratio: str) -> str | None:
        # doubao-seedream-5.0-lite 要求图片至少 3686400 像素，按各比例取满足下限的尺寸
        size_map = {
            "1:1": "1920x1920",   # 3686400
            "4:5": "1728x2160",   # 3732480
            "3:4": "1664x2218",   # 3690752
            "16:9": "2560x1440",  # 3686400
            "9:16": "1440x2560",  # 3686400
        }
        return size_map.get(aspect_ratio) or "1920x1920"

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
            f"指定场景：{variant.scene_preset or request.selected_scene or '未指定'}",
            f"指定风格：{variant.style_preset or request.selected_style or '未指定'}",
            f"形式结构：{variant.composition_style}",
            f"材料丰富度：{variant.material_richness}",
            f"花材种类上限：{variant.species_count_cap}",
            f"主花占比：{variant.dominant_flower_ratio:.2f}",
            f"配色策略：{variant.color_strategy}",
            f"花束密度：{variant.bouquet_density}",
            "材料硬约束：花材必须固定分为主花材、过渡花材、点缀花材、线性花材四类。",
            "材料硬约束：每类只允许 1-2 种花材，每种 1-4 枝，总种类控制在 4-6 种。",
            "材料硬约束：各类花材必须清晰可辨，便于后续用户查看、替换、教程制作和再次识别。",
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
                    scene_preset=_normalize_scene_preset(item.get("scene_preset"), request.mode),
                    style_preset=_normalize_style_preset(item.get("style_preset"), focus),
                    explanation=str(item.get("explanation") or "").strip(),
                    fit_scenes=_normalize_string_list(item.get("fit_scenes")),
                    usage_goal=str(item.get("usage_goal") or "").strip(),
                    reality_advice=str(item.get("reality_advice") or "").strip(),
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
            "每个方案还要给出 scene_preset、style_preset、explanation、fit_scenes、usage_goal、reality_advice。\n"
            "focus 只能是 atmosphere / color / persona / material / premium / coherence / symbolism。\n"
            "reference_strategy 只能是 none / light / strong。\n"
            "composition_style 只能是 mass / layered / airy / focal。\n"
            "material_richness 只能是 single / limited / mixed。\n"
            "color_strategy 只能是 single_tone / dual_tone / accent。\n"
            "bouquet_density 只能是 dense / medium / airy。\n"
            "scene_preset 只能是 礼宾赠礼 / 庆祝纪念 / 恋人赠礼 / 日常居家。\n"
            "style_preset 只能是 东方留白 / 法式浪漫 / 清新自然 / 现代艺术。\n"
            "请控制方案数量为 3 个，并确保侧重点明显不同。\n"
            f"mode={request.mode}\n"
            f"creative_mode={request.creative_mode}\n"
            f"selected_interpretation_label={request.selected_interpretation_label or '未指定'}\n"
            f"selected_scene={request.selected_scene or '未指定'}\n"
            f"selected_style={request.selected_style or '未指定'}\n"
            f"semantic_summary={request.semantic_result.semantic_summary}\n"
            f"scene_tags={','.join(request.semantic_result.scene_tags)}\n"
            f"emotion_tags={','.join(request.semantic_result.emotion_tags)}\n"
            f"visual_tags={','.join(request.semantic_result.visual_tags)}\n"
            f"translation_axes={','.join(request.semantic_result.translation_axes)}\n"
            f"generation_goals={goals}\n"
            f"references={references}\n"
            '输出 JSON 结构：{"variant_plans":[{"variant_id":"plan_1","title":"氛围还原","focus":"atmosphere","prompt_directive":"...","reference_strategy":"light","composition_style":"mass","material_richness":"single","species_count_cap":2,"dominant_flower_ratio":0.82,"color_strategy":"single_tone","bouquet_density":"dense","scene_preset":"庆祝纪念","style_preset":"东方留白","explanation":"...","fit_scenes":["生日现场","朋友庆祝"],"usage_goal":"适合表达祝贺与记忆留存","reality_advice":"适合做成单手可持的中小型花束"}]}'
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
                scene_preset=_normalize_scene_preset(request.selected_scene, request.mode),
                style_preset=_normalize_style_preset(request.selected_style, "atmosphere"),
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
                scene_preset=_normalize_scene_preset(request.selected_scene, request.mode),
                style_preset=_normalize_style_preset(request.selected_style, "persona"),
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
                scene_preset=_normalize_scene_preset(request.selected_scene, request.mode),
                style_preset=_normalize_style_preset(request.selected_style, "symbolism"),
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


def _normalize_scene_preset(value: object, mode: object) -> str:
    candidate = str(value or "").strip()
    if candidate in SCENE_CONSTRAINTS:
        return candidate
    return DEFAULT_SCENE_BY_MODE.get(str(mode), "庆祝纪念")


def _normalize_style_preset(value: object, focus: object) -> str:
    candidate = str(value or "").strip()
    if candidate in STYLE_CONSTRAINTS:
        return candidate
    return DEFAULT_STYLE_BY_FOCUS.get(str(focus), "东方留白")


def _normalize_string_list(value: object) -> list[str]:
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    if isinstance(value, str) and value.strip():
        return [part.strip() for part in value.split("、") if part.strip()]
    return []


def _decorate_variant_plan(plan: GenerationVariantPlan, request: GenerateBouquetRequest) -> GenerationVariantPlan:
    scene_preset = plan.scene_preset or _normalize_scene_preset(request.selected_scene, request.mode)
    style_preset = plan.style_preset or _normalize_style_preset(request.selected_style, plan.focus)
    fit_scenes = plan.fit_scenes or _default_fit_scenes(scene_preset)
    usage_goal = plan.usage_goal or _build_usage_goal(scene_preset, request)
    explanation = plan.explanation or _build_plan_explanation(plan, request, scene_preset, style_preset)
    reality_advice = plan.reality_advice or _build_reality_advice(plan, request, scene_preset, style_preset)
    return plan.model_copy(
        update={
            "scene_preset": scene_preset,
            "style_preset": style_preset,
            "fit_scenes": fit_scenes,
            "usage_goal": usage_goal,
            "explanation": explanation,
            "reality_advice": reality_advice,
        }
    )


def _enrich_bouquet_results(
    results: list[BouquetResult],
    request: GenerateBouquetRequest,
    plan_used: list[GenerationVariantPlan],
    reference_map: dict[str, dict[str, object]],
) -> list[BouquetResult]:
    selected_references = [
        reference_map[reference_id]
        for reference_id in request.selected_reference_ids
        if reference_id in reference_map
    ]
    enriched: list[BouquetResult] = []
    for index, result in enumerate(results):
        plan = plan_used[min(index, len(plan_used) - 1)] if plan_used else None
        planned_flowers = _build_material_plans(result, plan, selected_references, request)
        fallback_flowers = _build_anchor_flowers_from_plans(
            result_id=result.result_id,
            planned_flowers=planned_flowers,
            plan=plan,
        )
        recognized_flowers = _recognize_generated_flowers(
            result=result,
            plan=plan,
            planned_flowers=planned_flowers,
            fallback_flowers=fallback_flowers,
        )
        flowers = recognized_flowers or fallback_flowers
        recognition_status = _resolve_flower_recognition_status(flowers)
        recognition_summary = _build_flower_recognition_summary(
            flowers=flowers,
            planned_flowers=planned_flowers,
            recognition_status=recognition_status,
        )
        enriched.append(
            result.model_copy(
                update={
                    "planned_flowers": planned_flowers,
                    "recognized_flowers": flowers,
                    "flowers": flowers,
                    "flower_recognition_status": recognition_status,
                    "flower_recognition_summary": recognition_summary,
                    "scene_preset": plan.scene_preset if plan else _normalize_scene_preset(request.selected_scene, request.mode),
                    "style_preset": plan.style_preset if plan else _normalize_style_preset(request.selected_style, "atmosphere"),
                    "explanation": plan.explanation if plan else "",
                    "fit_scenes": list(plan.fit_scenes) if plan else [],
                    "usage_goal": plan.usage_goal if plan else "",
                    "reality_advice": plan.reality_advice if plan else "",
                }
            )
        )
    return enriched


def _build_variant_flowers(
    result: BouquetResult,
    plan: GenerationVariantPlan | None,
    selected_references: list[dict[str, object]],
    request: GenerateBouquetRequest,
) -> list[FlowerInfo]:
    planned_flowers = _build_material_plans(result, plan, selected_references, request)
    return _build_anchor_flowers_from_plans(
        result_id=result.result_id,
        planned_flowers=planned_flowers,
        plan=plan,
    )


def _resolve_target_flower_count(plan: GenerationVariantPlan | None) -> int:
    if not plan:
        return 3
    richness_bonus = {
        "single": 0,
        "limited": 1,
        "mixed": 2,
    }.get(plan.material_richness, 1)
    return max(2, min(plan.species_count_cap + richness_bonus, 5))


def _build_material_plans(
    result: BouquetResult,
    plan: GenerationVariantPlan | None,
    selected_references: list[dict[str, object]],
    request: GenerateBouquetRequest,
) -> list[FlowerMaterialPlan]:
    candidate_names = _collect_variant_flower_candidates(result, plan, selected_references, request)
    grouped: dict[str, list[str]] = {key: [] for key in FLOWER_CATEGORY_LABELS}

    for flower_name in candidate_names:
        category = _classify_flower_material_category(flower_name)
        if len(grouped[category]) >= FLOWER_CATEGORY_LIMITS[category]:
            continue
        if flower_name not in grouped[category]:
            grouped[category].append(flower_name)

    for category in FLOWER_CATEGORY_LABELS:
        for fallback_name in _default_species_for_category(category, plan, request):
            if len(grouped[category]) >= FLOWER_CATEGORY_LIMITS[category]:
                break
            if fallback_name not in grouped[category]:
                grouped[category].append(fallback_name)

    material_plans: list[FlowerMaterialPlan] = []
    for category in ["main", "transition", "accent", "linear"]:
        species = grouped[category][: FLOWER_CATEGORY_LIMITS[category]]
        if not species:
            continue
        material_plans.append(
            FlowerMaterialPlan(
                category=category,  # type: ignore[arg-type]
                category_label=FLOWER_CATEGORY_LABELS[category],
                species=species,
                stem_count_range=_resolve_stem_count_range(category, plan),
                strategy=_build_material_strategy(category, species, plan),
            )
        )
    return material_plans


def _build_anchor_flowers_from_plans(
    *,
    result_id: str,
    planned_flowers: list[FlowerMaterialPlan],
    plan: GenerationVariantPlan | None,
) -> list[FlowerInfo]:
    anchors: list[FlowerInfo] = []
    running_index = 0
    for material in planned_flowers:
        for species_index, flower_name in enumerate(material.species):
            placement_zone, point = _resolve_material_anchor_position(material.category, species_index, plan)
            anchors.append(
                _build_anchor_flower(
                    result_id=result_id,
                    flower_name=flower_name,
                    anchor_index=running_index,
                    category=material.category,
                    point=point,
                    placement_zone=placement_zone,
                    confidence=max(0.62, 0.9 - running_index * 0.05),
                    plan=plan,
                    detection_origin="planned_fallback",
                    source_hint="material_plan",
                    visible_reason=f"按{material.category_label}结构预设一个代表花锚点，便于用户交互替换。",
                )
            )
            running_index += 1
    return anchors


def _recognize_generated_flowers(
    *,
    result: BouquetResult,
    plan: GenerationVariantPlan | None,
    planned_flowers: list[FlowerMaterialPlan],
    fallback_flowers: list[FlowerInfo],
) -> list[FlowerInfo]:
    if not result.image_url or is_test_mode():
        return fallback_flowers

    base_url, api_key, model = resolve_workflow_text_config()
    if not base_url or not api_key:
        return fallback_flowers

    try:
        payload = call_multimodal_json(
            _build_flower_anchor_recognition_prompt(result, plan, planned_flowers),
            image_urls=[result.image_url],
            model=model,
            system_prompt=FLOWER_RECOGNITION_SYSTEM_PROMPT,
            base_url=base_url,
            api_key=api_key,
        )
        recognized = _normalize_recognized_flowers(
            payload=payload,
            result_id=result.result_id,
            plan=plan,
            planned_flowers=planned_flowers,
            fallback_flowers=fallback_flowers,
        )
        return recognized or fallback_flowers
    except Exception:
        return fallback_flowers


def _build_flower_anchor_recognition_prompt(
    result: BouquetResult,
    plan: GenerationVariantPlan | None,
    planned_flowers: list[FlowerMaterialPlan],
) -> str:
    material_lines = []
    for material in planned_flowers:
        material_lines.append(
            f"- {material.category}/{material.category_label}: 候选花材 { '、'.join(material.species) }"
        )
    return (
        "请查看这张已经生成完成的花束成品图，并为后续“修改花图”交互挑出代表花锚点。\n"
        "任务目标：每种主要花材只挑一朵最清晰、最能代表该花材的花，返回名字和归一化坐标。\n"
        "规则：\n"
        "1. 只返回适合作为点击锚点的花，不要把同一种花重复返回多次。\n"
        "2. 优先从候选花材里识别；如果图上明显不是候选，但能确定是同类常见真实花材，也可以输出更合理的真实花名。\n"
        "3. 不确定就跳过，不要为了凑数量而乱猜。\n"
        "4. point 采用 0~1 之间的 [x,y] 归一化坐标，落在那朵代表花的中心附近即可。\n"
        "5. anchors 最多返回 6 个，尽量覆盖主花材、过渡花材、点缀花材、线性花材。\n"
        f"当前结果标题：{result.title}\n"
        f"当前结果摘要：{result.summary}\n"
        f"当前方案：{plan.title if plan else '默认方案'}\n"
        f"当前风格：{plan.style_preset if plan else result.style_preset or '未指定'}\n"
        f"当前场景：{plan.scene_preset if plan else result.scene_preset or '未指定'}\n"
        "候选花材清单：\n"
        + "\n".join(material_lines)
        + '\n输出 JSON：{"anchors":[{"category":"main","name":"白玫瑰","point":[0.52,0.31],"confidence":0.9,"visible_reason":"主视觉区域可见典型玫瑰花头"}]}'
    )


def _normalize_recognized_flowers(
    *,
    payload: dict[str, Any],
    result_id: str,
    plan: GenerationVariantPlan | None,
    planned_flowers: list[FlowerMaterialPlan],
    fallback_flowers: list[FlowerInfo],
) -> list[FlowerInfo]:
    anchors = payload.get("anchors")
    if not isinstance(anchors, list):
        return fallback_flowers

    recognized: list[FlowerInfo] = []
    category_counts: dict[str, int] = {key: 0 for key in FLOWER_CATEGORY_LABELS}
    for item in anchors:
        if not isinstance(item, dict):
            continue
        raw_flower_name = str(item.get("name") or "").strip()
        category = _normalize_material_category(item.get("category"), raw_flower_name)
        if not raw_flower_name or category_counts[category] >= FLOWER_CATEGORY_LIMITS[category]:
            continue
        flower_name = _resolve_allowed_recognized_name(raw_flower_name, category, planned_flowers)
        if not flower_name:
            continue
        placement_zone, fallback_point = _resolve_material_anchor_position(category, category_counts[category], plan)
        point = _normalize_anchor_point(item.get("point"), fallback_point)
        raw_visible_reason = str(item.get("visible_reason") or "").strip()
        visible_reason = raw_visible_reason or "图像中可见该类花材的代表花头。"
        if flower_name != raw_flower_name:
            visible_reason = f"{visible_reason} 名称已按当前方案收敛为“{flower_name}”。"
        recognized.append(
            _build_anchor_flower(
                result_id=result_id,
                flower_name=flower_name,
                anchor_index=len(recognized),
                category=category,
                point=point,
                placement_zone=placement_zone,
                confidence=_normalize_anchor_confidence(item.get("confidence")),
                plan=plan,
                detection_origin="recognized",
                source_hint="image_recognition",
                visible_reason=visible_reason,
            )
        )
        category_counts[category] += 1

    return _merge_recognized_with_fallback(recognized, fallback_flowers)


def _merge_recognized_with_fallback(
    recognized: list[FlowerInfo],
    fallback_flowers: list[FlowerInfo],
) -> list[FlowerInfo]:
    merged: list[FlowerInfo] = []
    seen_keys: set[str] = set()
    covered_categories: set[str] = set()

    for flower in recognized:
        key = f"{flower.category}:{flower.name}"
        if key in seen_keys:
            continue
        merged.append(flower)
        seen_keys.add(key)
        covered_categories.add(flower.category)

    for flower in fallback_flowers:
        key = f"{flower.category}:{flower.name}"
        if key in seen_keys:
            continue
        if flower.category in covered_categories and len(merged) >= 4:
            continue
        merged.append(flower)
        seen_keys.add(key)
        covered_categories.add(flower.category)

    return merged[:6]


def _build_anchor_flower(
    *,
    result_id: str,
    flower_name: str,
    anchor_index: int,
    category: str,
    point: list[float],
    placement_zone: str,
    confidence: float,
    plan: GenerationVariantPlan | None,
    detection_origin: str,
    source_hint: str,
    visible_reason: str,
) -> FlowerInfo:
    profile = FLOWER_LIBRARY.get(flower_name, {})
    role = _build_anchor_role(category, plan, profile)
    label_side = _resolve_label_side(point, placement_zone)
    return FlowerInfo(
        flower_id=f"{result_id}_{category}_{anchor_index + 1}",
        name=flower_name,
        type=str(profile.get("type") or FLOWER_CATEGORY_LABELS[category]),
        meaning=str(profile.get("meaning") or "用于帮助用户定位和替换该类花材"),
        role=role,
        category=category,  # type: ignore[arg-type]
        category_label=FLOWER_CATEGORY_LABELS[category],
        point=point,
        confidence=confidence,
        placement_zone=placement_zone,
        label_side=label_side,
        source_hint=source_hint,
        detection_origin=detection_origin,
        visible_reason=visible_reason,
    )


def _build_anchor_role(category: str, plan: GenerationVariantPlan | None, profile: dict[str, object]) -> str:
    base = str(profile.get("role") or "承担当前方案中的关键花材角色")
    category_copy = {
        "main": "主视觉焦点",
        "transition": "过渡与层次衔接",
        "accent": "点缀和节奏补充",
        "linear": "轮廓延展与线条建立",
    }.get(category, "当前花束结构")
    if plan:
        return f"作为“{plan.title}”里的{category_copy}锚点，{base}"
    return f"作为{category_copy}锚点，{base}"


def _classify_flower_material_category(flower_name: str) -> str:
    profile = FLOWER_LIBRARY.get(flower_name, {})
    normalized = f"{flower_name} {profile.get('type', '')}"
    if any(token in normalized for token in ["线条", "飞燕", "金鱼草", "麦穗", "尤加利", "绿铃草"]):
        return "linear"
    if "点缀" in normalized or flower_name in {"蓝星花", "洋甘菊", "珍珠梅", "蕾丝花", "乒乓菊"}:
        return "accent"
    if any(token in normalized for token in ["主花", "焦点", "玫瑰", "百合", "郁金香", "向日葵", "芍药", "火鹤"]):
        return "main"
    return "transition"


def _default_species_for_category(
    category: str,
    plan: GenerationVariantPlan | None,
    request: GenerateBouquetRequest,
) -> list[str]:
    scene_key = plan.scene_preset if plan else _normalize_scene_preset(request.selected_scene, request.mode)
    scene_defaults = DEFAULT_CATEGORY_SPECIES_BY_SCENE.get(scene_key, DEFAULT_CATEGORY_SPECIES_BY_SCENE["庆祝纪念"])
    defaults = list(scene_defaults.get(category, []))
    semantic_defaults = [
        name for name in _flowers_from_semantic(request.semantic_result.color_palette, request.semantic_result.visual_tags)
        if _classify_flower_material_category(name) == category
    ]
    relation_defaults = [
        name for name in _flowers_from_relation(request.semantic_result.relation_tags)
        if _classify_flower_material_category(name) == category
    ]
    merged: list[str] = []
    for name in semantic_defaults + relation_defaults + defaults:
        if name not in merged:
            merged.append(name)
    return merged


def _resolve_stem_count_range(category: str, plan: GenerationVariantPlan | None) -> list[int]:
    base = list(FLOWER_CATEGORY_STEM_RANGES[category])
    if not plan:
        return base
    if plan.bouquet_density == "airy":
        return [max(1, base[0] - 1), max(base[0], base[1] - 1)]
    if plan.bouquet_density == "dense" and category in {"main", "transition"}:
        return [base[0] + 1, base[1] + 1]
    return base


def _build_material_strategy(category: str, species: list[str], plan: GenerationVariantPlan | None) -> str:
    category_goal = {
        "main": "负责主视觉焦点和用户第一眼记忆点",
        "transition": "负责连接主花与外围材料，避免结构生硬断开",
        "accent": "负责节奏、细节和轻盈点缀",
        "linear": "负责拉出外轮廓和空间方向",
    }.get(category, "负责当前花束结构")
    plan_text = f"当前方案“{plan.title}”中，" if plan else ""
    return f"{plan_text}{'、'.join(species)} {category_goal}。"


def _resolve_material_anchor_position(
    category: str,
    species_index: int,
    plan: GenerationVariantPlan | None,
) -> tuple[str, list[float]]:
    composition_style = plan.composition_style if plan else "mass"
    zone_points = FLOWER_ZONE_POINTS.get(composition_style, FLOWER_ZONE_POINTS["mass"])
    ordered_zones = {
        "main": ["focal_center", "main_left", "main_right"],
        "transition": ["main_right", "side_structure", "main_left"],
        "accent": ["accent", "accent"],
        "linear": ["upper_line", "upper_line"],
    }.get(category, ["focal_center"])
    zone = ordered_zones[min(species_index, len(ordered_zones) - 1)]
    points = zone_points.get(zone) or [[0.5, 0.5]]
    point = points[min(species_index, len(points) - 1)]
    return zone, point


def _normalize_material_category(value: object, flower_name: str) -> str:
    candidate = str(value or "").strip().lower()
    mapping = {
        "main": "main",
        "主花": "main",
        "主花材": "main",
        "transition": "transition",
        "过渡": "transition",
        "过渡花材": "transition",
        "accent": "accent",
        "点缀": "accent",
        "点缀花材": "accent",
        "linear": "linear",
        "线性": "linear",
        "线性花材": "linear",
    }
    if candidate in mapping:
        return mapping[candidate]
    return _classify_flower_material_category(flower_name)


def _resolve_allowed_recognized_name(
    flower_name: str,
    category: str,
    planned_flowers: list[FlowerMaterialPlan],
) -> str | None:
    allowed_species = _allowed_species_for_category(category, planned_flowers)
    if not allowed_species:
        return flower_name if flower_name in FLOWER_LIBRARY else None
    if flower_name in allowed_species:
        return flower_name

    raw_canonical = _canonicalize_flower_name(flower_name)
    exact_family_matches = [
        candidate for candidate in allowed_species
        if _canonicalize_flower_name(candidate) == raw_canonical
    ]
    if exact_family_matches:
        return exact_family_matches[0]

    if flower_name in FLOWER_LIBRARY and _classify_flower_material_category(flower_name) == category:
        return flower_name
    return None


def _allowed_species_for_category(category: str, planned_flowers: list[FlowerMaterialPlan]) -> list[str]:
    for material in planned_flowers:
        if material.category == category:
            return list(material.species)
    return []


def _canonicalize_flower_name(flower_name: str) -> str:
    canonical = str(flower_name).strip()
    while True:
        matched_prefix = next((prefix for prefix in FLOWER_NAME_PREFIXES if canonical.startswith(prefix)), "")
        if not matched_prefix or len(canonical) <= len(matched_prefix):
            break
        canonical = canonical[len(matched_prefix):]
    return canonical or str(flower_name).strip()


def _normalize_anchor_point(value: object, fallback_point: list[float]) -> list[float]:
    if isinstance(value, list) and len(value) >= 2:
        try:
            x = float(value[0])
            y = float(value[1])
            if 0.0 <= x <= 1.0 and 0.0 <= y <= 1.0:
                return [x, y]
        except (TypeError, ValueError):
            pass
    return fallback_point


def _normalize_anchor_confidence(value: object) -> float:
    try:
        confidence = float(value)
    except (TypeError, ValueError):
        confidence = 0.78
    return max(0.0, min(1.0, confidence))


def _resolve_flower_recognition_status(flowers: list[FlowerInfo]) -> str:
    if any(flower.detection_origin == "recognized" for flower in flowers):
        return "recognized"
    return "planned_fallback"


def _build_flower_recognition_summary(
    *,
    flowers: list[FlowerInfo],
    planned_flowers: list[FlowerMaterialPlan],
    recognition_status: str,
) -> str:
    planned_categories = "、".join(material.category_label for material in planned_flowers) or "主花材"
    recognized_count = sum(1 for flower in flowers if flower.detection_origin == "recognized")
    fallback_count = sum(1 for flower in flowers if flower.detection_origin != "recognized")
    if recognition_status == "recognized":
        return (
            f"本次已基于最终生成图识别出 {recognized_count} 个代表花锚点，"
            f"其余 {fallback_count} 个锚点由当前方案的 {planned_categories} 结构补齐。"
        )
    return f"本次未启用生成后识别，当前锚点由方案规划的 {planned_categories} 结构提供。"


def _collect_variant_flower_candidates(
    result: BouquetResult,
    plan: GenerationVariantPlan | None,
    selected_references: list[dict[str, object]],
    request: GenerateBouquetRequest,
) -> list[str]:
    ordered: list[str] = []
    seen: set[str] = set()

    def push(names: list[str]) -> None:
        for name in names:
            cleaned = str(name).strip()
            if not cleaned or cleaned in seen:
                continue
            ordered.append(cleaned)
            seen.add(cleaned)

    if plan:
        push(FOCUS_FLOWER_HINTS.get(plan.focus, []))
        push(SCENE_FLOWER_HINTS.get(plan.scene_preset or "", []))
        push(STYLE_FLOWER_HINTS.get(plan.style_preset or "", []))
    if plan and plan.reference_strategy == "strong":
        for reference in selected_references[:2]:
            push([str(item) for item in reference.get("flower_types", []) if str(item).strip()])
    push(_flowers_from_semantic(request.semantic_result.color_palette, request.semantic_result.visual_tags))
    push(_flowers_from_relation(request.semantic_result.relation_tags))
    if plan and plan.reference_strategy != "none":
        for reference in selected_references[:2]:
            push([str(item) for item in reference.get("flower_types", []) if str(item).strip()])
    push([flower.name for flower in result.flowers])
    if len(ordered) < 2:
        push(["白洋桔梗", "尤加利", "白玫瑰"])
    return ordered


def _flowers_from_semantic(color_palette: list[str], visual_tags: list[str]) -> list[str]:
    text = " ".join(list(color_palette) + list(visual_tags))
    if any(token in text for token in ["蓝", "冷", "雾", "留白"]):
        return ["蓝绣球", "白洋桔梗", "银叶菊", "蓝星花"]
    if any(token in text for token in ["粉", "柔", "暖白"]):
        return ["粉玫瑰", "奶油玫瑰", "香雪兰", "蕾丝花"]
    if any(token in text for token in ["黄", "橙", "红", "暖"]):
        return ["向日葵", "香槟玫瑰", "橙玫瑰", "橙洋桔梗"]
    if any(token in text for token in ["绿", "自然", "野生"]):
        return ["绿铃草", "尤加利", "风铃草", "飞燕草"]
    return []


def _flowers_from_relation(relation_tags: list[str]) -> list[str]:
    text = " ".join(relation_tags)
    if any(token in text for token in ["领导", "同事"]):
        return ["白百合", "香槟玫瑰", "绿掌"]
    if "朋友" in text:
        return ["向日葵", "粉玫瑰", "白洋桔梗"]
    if any(token in text for token in ["恋人", "纪念日"]):
        return ["奶油玫瑰", "郁金香", "蕾丝花"]
    if any(token in text for token in ["家人", "妈妈"]):
        return ["康乃馨", "白百合", "香雪兰"]
    return []


def _build_flower_info(
    *,
    result_id: str,
    flower_name: str,
    index: int,
    plan: GenerationVariantPlan | None,
    point: list[float],
) -> FlowerInfo:
    profile = FLOWER_LIBRARY.get(flower_name, {})
    fallback_type = "主花" if index == 0 else "辅助花"
    flower_type = str(profile.get("type") or fallback_type)
    material_category = _classify_flower_material_category(flower_name)
    role = str(profile.get("role") or "补充当前方案的材料层次与花束结构")
    if index == 0:
        role = f"作为 {plan.title if plan else '当前方案'} 的主视觉焦点，{role}" if plan else role
    elif index == 1:
        role = f"作为 {plan.title if plan else '当前方案'} 的第二层结构，{role}" if plan else role
    confidence = max(0.56, 0.93 - index * 0.07)
    placement_zone, point, label_side = _resolve_flower_layout(
        flower_name=flower_name,
        flower_type=flower_type,
        index=index,
        plan=plan,
        default_point=point,
    )
    return FlowerInfo(
        flower_id=f"{result_id}_{index + 1}",
        name=flower_name,
        type=flower_type,
        meaning=str(profile.get("meaning") or "用于支撑当前方案的气质表达"),
        role=role,
        category=material_category,  # type: ignore[arg-type]
        category_label=FLOWER_CATEGORY_LABELS[material_category],
        point=point,
        confidence=confidence,
        placement_zone=placement_zone,
        label_side=label_side,
        source_hint=_resolve_flower_source_hint(flower_name, index, plan),
        detection_origin="planned_fallback",
        visible_reason="按方案花材结构推断得到的默认代表花位置。",
    )


def _resolve_flower_layout(
    *,
    flower_name: str,
    flower_type: str,
    index: int,
    plan: GenerationVariantPlan | None,
    default_point: list[float],
) -> tuple[str, list[float], str]:
    composition_style = plan.composition_style if plan else "mass"
    category = _resolve_flower_layout_category(flower_name, flower_type, index)
    zone_points = FLOWER_ZONE_POINTS.get(composition_style, FLOWER_ZONE_POINTS["mass"])
    points = zone_points.get(category) or [default_point]
    point = points[index % len(points)]
    label_side = _resolve_label_side(point, category)
    return category, point, label_side


def _resolve_flower_layout_category(flower_name: str, flower_type: str, index: int) -> str:
    normalized = f"{flower_name} {flower_type}"
    if index == 0 or "焦点" in normalized:
        return "focal_center"
    if "线条" in normalized:
        return "upper_line"
    if "叶材" in normalized or "配叶" in normalized:
        return "outer_leaf"
    if "结构" in normalized:
        return "side_structure"
    if "点缀" in normalized:
        return "accent"
    if index % 2 == 1:
        return "main_left"
    return "main_right"


def _resolve_label_side(point: list[float], placement_zone: str) -> str:
    x, y = point
    if placement_zone == "upper_line" or y < 0.22:
        return "top"
    if placement_zone == "outer_leaf" and y > 0.64:
        return "bottom"
    return "left" if x >= 0.5 else "right"


def _resolve_flower_source_hint(flower_name: str, index: int, plan: GenerationVariantPlan | None) -> str:
    if index == 0:
        return "plan_primary"
    if plan and flower_name in FOCUS_FLOWER_HINTS.get(plan.focus, []):
        return "focus_hint"
    if plan and flower_name in SCENE_FLOWER_HINTS.get(plan.scene_preset or "", []):
        return "scene_hint"
    if plan and flower_name in STYLE_FLOWER_HINTS.get(plan.style_preset or "", []):
        return "style_hint"
    return "reference_or_template"


def _default_fit_scenes(scene_preset: str) -> list[str]:
    return {
        "礼宾赠礼": ["正式拜访", "商务欢迎", "阶段祝贺"],
        "庆祝纪念": ["生日庆祝", "毕业获奖", "纪念合影"],
        "恋人赠礼": ["纪念日", "约会赠礼", "亲密表达"],
        "日常居家": ["家居摆放", "自我疗愈", "日常陪伴"],
    }.get(scene_preset, [scene_preset])


def _build_usage_goal(scene_preset: str, request: GenerateBouquetRequest) -> str:
    if scene_preset == "礼宾赠礼":
        return "适合表达尊重、欢迎与有分寸的正式心意。"
    if scene_preset == "庆祝纪念":
        return "适合承接庆祝、纪念和需要被看见的开心时刻。"
    if scene_preset == "恋人赠礼":
        return "适合表达明确爱意，同时保留审美上的节制和高级感。"
    if request.mode == "scene":
        return "适合把场景情绪转成可送、可摆、可记录的现实花艺结果。"
    return "适合把当前输入转成现实中可承接、可复刻的花艺表达。"


def _build_plan_explanation(
    plan: GenerationVariantPlan,
    request: GenerateBouquetRequest,
    scene_preset: str,
    style_preset: str,
) -> str:
    focus_copy = {
        "atmosphere": "优先保留输入里的空气感、光线和整体色调",
        "color": "优先强调输入中最有记忆点的色彩关系",
        "persona": "优先承接人物或场景体现出的气质和分寸感",
        "material": "优先通过真实花材的质地与结构建立识别度",
        "premium": "优先提升整体完成度和高级感",
        "coherence": "优先收束杂讯，让整体更统一",
        "symbolism": "优先强化花语和关系语境的对应",
    }.get(plan.focus, "优先完成当前输入的核心花艺转译")
    return (
        f"该方案以“{scene_preset}”为使用场景、以“{style_preset}”为形式方向，"
        f"{focus_copy}，并围绕“{request.semantic_result.semantic_summary}”做减法表达。"
    )


def _build_reality_advice(
    plan: GenerationVariantPlan,
    request: GenerateBouquetRequest,
    scene_preset: str,
    style_preset: str,
) -> str:
    size_copy = {
        "dense": "成品可做成更饱满的中型花束",
        "medium": "成品建议保持中等体量，兼顾展示与持握",
        "airy": "成品建议做成更轻盈的小中型结构",
    }.get(plan.bouquet_density, "成品建议控制在现实中便于持握和摆放的体量")
    return (
        f"{size_copy}，优先保留 {scene_preset} 的场合分寸与 {style_preset} 的结构特征，"
        f"花材种类控制在 {plan.species_count_cap} 类主要花材以内。"
    )
