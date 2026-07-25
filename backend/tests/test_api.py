from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.repositories.bouquet_repository import get_bouquet_repository
from app.repositories.content_repository import get_content_repository
from app.schemas.bouquet import BouquetResult, FlowerInfo, GenerateBouquetRequest
from app.schemas.input import AnalyzeInputRequest, SelectionBox
from app.schemas.semantic import SemanticResult
from app.services.image_generation_provider import (
    ApiImageGenerationProvider,
    MockImageGenerationProvider,
    get_image_generation_provider,
)
from app.services.image_edit_provider import ImageEditProvider
from app.services.reference_retriever import ReferenceRetriever
from app.services.semantic_recognizer import (
    ApiSemanticRecognizer,
    MockSemanticRecognizer,
    get_semantic_recognizer,
)
from app.services.workflow_service import _normalize_tutorial_review_result


client = TestClient(app)


@pytest.fixture(autouse=True)
def _force_test_runtime(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("APP_RUNTIME_MODE", "test")
    get_semantic_recognizer.cache_clear()
    get_image_generation_provider.cache_clear()
    yield
    get_semantic_recognizer.cache_clear()
    get_image_generation_provider.cache_clear()


def _semantic_from_asset_group(group: dict, mode: str) -> SemanticResult:
    return SemanticResult(
        mode=mode,  # type: ignore[arg-type]
        subject_tags=[group.get("title", "")],
        scene_tags=list(group.get("scene_tags", [])),
        emotion_tags=list(group.get("emotion_tags", [])),
        visual_tags=list(group.get("visual_tags", [])),
        color_palette=list(group.get("color_palette", [])),
        relation_tags=[group["target_relation"]] if group.get("target_relation") else [],
        use_intent="表达氛围" if mode == "scene" else "gift",
        semantic_summary=str(group.get("summary", "")),
    )


def test_full_demo_flow() -> None:
    analyze_response = client.post(
        "/api/input/analyze",
        json={
            "content_id": "scene_001",
            "image_url": "/mock/assets/placeholder-scene.png",
            "selection_box": {"x": 10, "y": 20, "width": 200, "height": 150},
            "voice_text": "把这场雨变成花，送给刚升职的朋友，别太甜"
        },
    )
    assert analyze_response.status_code == 200
    analyze_data = analyze_response.json()
    assert analyze_data["mode_result"]["detected_mode"] in {"scene", "life"}
    assert analyze_data["detected_elements"]
    assert analyze_data["interpretation_options"]
    assert analyze_data["recommended_interpretation_id"]

    semantic_result = analyze_data["semantic_result"]
    assert semantic_result["color_swatches"]
    assert semantic_result["color_swatches"][0]["hex"].startswith("#")
    if analyze_data["interpretation_options"]:
        assert analyze_data["interpretation_options"][0]["semantic_result"]["color_swatches"]
    reference_response = client.post(
        "/api/reference/search",
        json={
            "mode": "scene",
            "semantic_tags": ["克制", "治愈", "冷色"],
            "semantic_result": semantic_result,
            "limit": 4
        },
    )
    assert reference_response.status_code == 200
    references = reference_response.json()["references"]
    assert 1 <= len(references) <= 3
    assert references[0]["cover_url"].startswith("/library/assets/")
    assert references[0]["preferred_display_mode"] == "image_only_modal"
    assert references[0]["show_title_by_default"] is False
    assert references[0]["show_reason_by_default"] is False

    generate_response = client.post(
        "/api/bouquet/generate",
        json={
            "mode": "scene",
            "semantic_result": semantic_result,
            "reference_strategy": "light",
            "selected_reference_ids": [references[0]["reference_id"]],
            "selected_scene": "庆祝纪念",
            "selected_style": "东方留白",
        },
    )
    assert generate_response.status_code == 200
    generate_data = generate_response.json()
    results = generate_data["results"]
    assert len(results) == 3
    assert len(generate_data["plan_used"]) == 3
    assert results[0]["image_url"].startswith("/library/assets/")
    assert results[0]["reference_used"][0]["cover_url"].startswith("/library/assets/")
    assert results[0]["reference_used"][0]["preferred_display_mode"] == "image_only_modal"
    assert results[0]["scene_preset"] == "庆祝纪念"
    assert results[0]["style_preset"] == "东方留白"
    assert results[0]["explanation"]
    assert results[0]["fit_scenes"]
    assert results[0]["usage_goal"]
    assert results[0]["reality_advice"]
    assert results[0]["planned_flowers"]
    assert results[0]["recognized_flowers"]
    assert results[0]["planned_flowers"][0]["category"] == "main"
    assert results[0]["recognized_flowers"][0]["category"]
    assert results[0]["recognized_flowers"][0]["detection_origin"] in {"recognized", "planned_fallback"}
    assert results[0]["flowers"][0]["point"]
    assert results[0]["flowers"][0]["placement_zone"]
    assert results[0]["flowers"][0]["label_side"]
    assert results[0]["flowers"][0]["source_hint"]
    assert max(len(item["flowers"]) for item in results) >= 3
    assert [flower["name"] for flower in results[0]["flowers"]] != [flower["name"] for flower in results[1]["flowers"]]
    assert [flower["point"] for flower in results[0]["flowers"]] != [flower["point"] for flower in results[1]["flowers"]]
    assert generate_data["plan_used"][0]["scene_preset"] == "庆祝纪念"

    result_id = results[0]["result_id"]
    flower_id = results[0]["flowers"][0]["flower_id"]

    flower_response = client.get(f"/api/bouquet/{result_id}/flowers/{flower_id}")
    assert flower_response.status_code == 200
    assert flower_response.json()["flower_id"] == flower_id

    edit_response = client.post(
        "/api/bouquet/edit",
        json={
            "result_id": result_id,
            "action": "voice_adjust",
            "target": {},
            "instruction": "更克制一点，更适合送朋友"
        },
    )
    assert edit_response.status_code == 200
    edited_result_id = edit_response.json()["new_result_id"]

    emotion_response = client.post(
        "/api/emotion/build",
        json={
            "result_id": edited_result_id,
            "mode": "scene",
            "voice_context": "送给刚升职的朋友，别太甜"
        },
    )
    assert emotion_response.status_code == 200
    assert "save_card" in emotion_response.json()
    assert emotion_response.json()["own_card"]["candidates"][0]["generation_brief"]
    assert emotion_response.json()["own_card"]["candidates"][0]["image_url"] == ""


def test_flower_mode_analysis_and_strong_reference_generation() -> None:
    analyze_response = client.post(
        "/api/input/analyze",
        json={
            "content_id": "flower_001",
            "image_url": "/mock/assets/placeholder-flower.png",
            "selection_box": {"x": 30, "y": 40, "width": 160, "height": 180},
            "voice_text": "这束花更高级一点，删掉太甜的感觉"
        },
    )
    assert analyze_response.status_code == 200
    analyze_data = analyze_response.json()
    assert analyze_data["mode_result"]["detected_mode"] == "flower"
    assert "高级" in analyze_data["semantic_result"]["emotion_tags"]
    assert analyze_data["interpretation_options"]

    reference_response = client.post(
        "/api/reference/search",
        json={
            "mode": "flower",
            "semantic_tags": ["高级", "粉白", "礼盒感"],
            "semantic_result": analyze_data["semantic_result"],
            "limit": 3
        },
    )
    assert reference_response.status_code == 200
    references = reference_response.json()["references"]
    assert 1 <= len(references) <= 3

    generate_response = client.post(
        "/api/bouquet/generate",
        json={
            "mode": "flower",
            "semantic_result": analyze_data["semantic_result"],
            "reference_strategy": "strong",
            "selected_reference_ids": [item["reference_id"] for item in references[:2]]
        },
    )
    assert generate_response.status_code == 200
    generate_data = generate_response.json()
    results = generate_data["results"]
    assert len(results) == 3
    assert generate_data["plan_used"][0]["focus"]
    assert len(results[0]["reference_used"]) == min(len(references), 2)
    assert "强参考了真实花内容" in results[0]["summary"]
    assert results[0]["image_url"].startswith("/library/assets/")
    assert results[0]["reference_used"][0]["title"]
    assert results[0]["reference_used"][0]["cover_url"].startswith("/library/assets/")
    assert results[0]["planned_flowers"]
    assert 4 <= sum(len(item["species"]) for item in results[0]["planned_flowers"]) <= 6
    assert results[0]["flowers"][0]["point"]
    assert results[0]["flowers"][0]["placement_zone"]
    assert results[0]["flowers"][0]["category_label"]
    assert results[0]["flowers"][0]["visible_reason"]
    assert len(results[0]["flowers"]) >= 2
    assert [flower["name"] for flower in results[0]["flowers"]] != [flower["name"] for flower in results[1]["flowers"]]


def test_reference_matching_prefers_best_semantic_fit() -> None:
    reference_response = client.post(
        "/api/reference/search",
        json={
            "mode": "scene",
            "semantic_tags": ["克制", "治愈", "蓝白"],
            "semantic_result": {
                "mode": "scene",
                "subject_tags": ["窗边雨幕"],
                "scene_tags": ["窗边", "雨天"],
                "emotion_tags": ["克制", "轻治愈"],
                "visual_tags": ["蓝白", "留白"],
                "color_palette": [],
                "relation_tags": [],
                "use_intent": "表达氛围",
                "semantic_summary": "一个偏冷感、克制、治愈的场景输入。"
            },
            "limit": 3
        },
    )
    assert reference_response.status_code == 200
    references = reference_response.json()["references"]
    assert references[0]["reference_id"] == "flower_blue_white"
    assert references[0]["score_breakdown"]["emotion"] > 0
    assert references[0]["score_breakdown"]["visual"] > 0
    assert "克制" in references[0]["matched_tags"] or "治愈" in references[0]["matched_tags"]
    assert len(references) <= 3


def test_reference_matching_filters_out_weak_matches() -> None:
    reference_response = client.post(
        "/api/reference/search",
        json={
            "mode": "scene",
            "semantic_tags": ["完全无关标签A", "完全无关标签B"],
            "semantic_result": {
                "mode": "scene",
                "subject_tags": ["陌生主题"],
                "scene_tags": ["无关场景"],
                "emotion_tags": ["无关情绪"],
                "visual_tags": ["无关视觉"],
                "color_palette": [],
                "relation_tags": [],
                "use_intent": "表达氛围",
                "semantic_summary": "一个几乎没有可匹配线索的输入。"
            },
            "limit": 3
        },
    )
    assert reference_response.status_code == 200
    references = reference_response.json()["references"]
    assert references == []


def test_scene_asset_cases_match_expected_reference_flowers() -> None:
    repository = get_content_repository()
    retriever = ReferenceRetriever()
    reference_candidates = repository.list_reference_candidates("scene")
    scene_cases = {
        "scene_rain": "flower_blue_white",
        "scene_window_rain": "flower_blue_white",
        "scene_room": "flower_cream_family",
        "scene_dining_table": "flower_cream_family",
        "scene_windy_field": "flower_wild_handheld",
        "scene_night_window": "flower_red_orange_anniversary",
    }

    for group_id, expected_reference_id in scene_cases.items():
        group = next(item for item in repository.annotated_assets["scene_groups"] if item["group_id"] == group_id)
        semantic_result = _semantic_from_asset_group(group, mode="scene")
        results = retriever.search(
            references=reference_candidates,
            mode="scene",
            semantic_result=semantic_result,
            semantic_tags=[],
            limit=5,
        )
        assert results, f"{group_id} 未返回参考结果"
        assert results[0].reference_id == expected_reference_id
        assert results[0].score is not None and results[0].score >= 55


def test_flower_asset_cases_match_themselves_as_top_reference() -> None:
    repository = get_content_repository()
    retriever = ReferenceRetriever()
    reference_candidates = repository.list_reference_candidates("flower")

    for group in repository.annotated_assets["flower_groups"]:
        semantic_result = _semantic_from_asset_group(group, mode="flower")
        results = retriever.search(
            references=reference_candidates,
            mode="flower",
            semantic_result=semantic_result,
            semantic_tags=[],
            limit=5,
        )
        assert results, f"{group['group_id']} 未返回参考结果"
        assert results[0].reference_id == group["group_id"]
        assert results[0].score is not None and results[0].score >= 100


def test_demo_mode_can_exclude_self_reference_for_flower_inputs() -> None:
    repository = get_content_repository()
    group = next(item for item in repository.annotated_assets["flower_groups"] if item["group_id"] == "flower_blue_white")
    semantic_result = _semantic_from_asset_group(group, mode="flower")

    reference_response = client.post(
        "/api/reference/search",
        json={
            "mode": "flower",
            "semantic_result": semantic_result.model_dump(),
            "source_asset_id": "flower_blue_white",
            "exclude_source_reference": True,
            "limit": 5,
        },
    )
    assert reference_response.status_code == 200
    references = reference_response.json()["references"]
    assert references
    assert all(item["reference_id"] != "flower_blue_white" for item in references)
    assert references[0]["reference_id"] == "flower_cream_family"


def test_life_mode_delete_flower_and_build_emotion_cards() -> None:
    analyze_response = client.post(
        "/api/input/analyze",
        json={
            "content_id": "life_001",
            "image_url": "/mock/assets/placeholder-life.png",
            "selection_box": {"x": 15, "y": 25, "width": 220, "height": 160},
            "voice_text": "送给刚升职的朋友，别太甜，但要有祝贺感"
        },
    )
    assert analyze_response.status_code == 200
    semantic_result = analyze_response.json()["semantic_result"]

    generate_response = client.post(
        "/api/bouquet/generate",
        json={
            "mode": "life",
            "semantic_result": semantic_result,
            "reference_strategy": "none",
            "selected_reference_ids": []
        },
    )
    assert generate_response.status_code == 200
    result = generate_response.json()["results"][0]
    flower_id = result["flowers"][0]["flower_id"]

    edit_response = client.post(
        "/api/bouquet/edit",
        json={
            "result_id": result["result_id"],
            "action": "delete_flower",
            "target": {"flower_id": flower_id},
            "instruction": "删掉最显眼的那朵花"
        },
    )
    assert edit_response.status_code == 200
    edit_data = edit_response.json()
    assert edit_data["result"]["result_id"] == edit_data["new_result_id"]
    assert len(edit_data["result"]["flowers"]) == len(result["flowers"]) - 1
    assert "更克制" in edit_data["result"]["tags"]

    emotion_response = client.post(
        "/api/emotion/build",
        json={
            "result_id": edit_data["new_result_id"],
            "mode": "life",
            "voice_context": "送给刚升职的朋友，别太甜"
        },
    )
    assert emotion_response.status_code == 200
    emotion_data = emotion_response.json()
    assert emotion_data["gift_card"]["target"] == "适合送给朋友"
    assert "不会显得过分亲密" in emotion_data["gift_card"]["reason"]
    assert emotion_data["save_card"]["copy"]
    assert len(emotion_data["own_card"]["candidates"]) == 3
    assert emotion_data["own_card"]["candidates"][0]["image_url"] == ""
    assert emotion_data["own_card"]["candidates"][0]["generation_brief"]
    assert emotion_data["own_card"]["candidates"][0]["bouquet_group_id"]


def test_emotion_remake_preview_returns_plan_and_fallback_image() -> None:
    analyze_response = client.post(
        "/api/input/analyze",
        json={
            "content_id": "scene_001",
            "image_url": "/mock/assets/placeholder-scene.png",
            "selection_box": {"x": 10, "y": 20, "width": 200, "height": 150},
            "voice_text": "把这场雨变成花，送给刚升职的朋友，别太甜"
        },
    )
    assert analyze_response.status_code == 200
    semantic_result = analyze_response.json()["semantic_result"]

    generate_response = client.post(
        "/api/bouquet/generate",
        json={
            "mode": "scene",
            "semantic_result": semantic_result,
            "reference_strategy": "light",
            "selected_reference_ids": ["flower_blue_white"],
            "selected_scene": "庆祝纪念",
            "selected_style": "东方留白",
        },
    )
    assert generate_response.status_code == 200
    result = generate_response.json()["results"][0]

    response = client.post(
        "/api/emotion/remake-preview",
        json={
            "result_id": result["result_id"],
            "mode": "scene",
            "option_type": "same_feeling",
            "voice_context": "送给刚升职的朋友，别太甜",
            "budget_level": "auto",
            "season_month": 7,
        },
    )
    assert response.status_code == 200
    data = response.json()
    assert data["option_type"] == "same_feeling"
    assert data["option_title"] == "同感觉现货版"
    assert data["preview_status"] == "fallback"
    assert data["preview_image_url"] == result["image_url"]
    assert data["budget_level"] in {"premium", "balanced"}
    assert data["generation_brief"]
    assert data["plan"]["title"].startswith("同感觉现货版")
    assert data["plan"]["selected_flowers"]
    assert data["plan"]["preserve_points"]
    assert "现实花束预览图" in data["plan"]["preview_prompt"]
    assert "7 月" in data["plan"]["seasonality_note"]


def test_emotion_remake_preview_applies_budget_and_season_substitutions() -> None:
    repository = get_bouquet_repository()
    repository.save_one(
        BouquetResult(
            result_id="remake_manual_case",
            title="测试卡片花束",
            image_url="/library/assets/flower_blue_white_01.png",
            tags=["克制", "祝贺"],
            summary="一束蓝白色、气质克制的卡片花束。",
            flowers=[
                FlowerInfo(flower_id="f1", name="芍药", type="主花", meaning="丰盛", role="main"),
                FlowerInfo(flower_id="f2", name="郁金香", type="主花", meaning="轻盈", role="main"),
                FlowerInfo(flower_id="f3", name="铃兰", type="点缀", meaning="纯净", role="accent"),
            ],
            scene_preset="礼宾赠礼",
            style_preset="东方留白",
            fit_scenes=["升职祝贺"],
        )
    )

    response = client.post(
        "/api/emotion/remake-preview",
        json={
            "result_id": "remake_manual_case",
            "mode": "flower",
            "option_type": "budget_friendly",
            "voice_context": "送给升职的朋友",
            "budget_level": "budget",
            "season_month": 11,
        },
    )
    assert response.status_code == 200
    data = response.json()
    assert data["budget_level"] == "budget"
    assert data["preview_status"] == "fallback"
    assert data["plan"]["selected_flowers"] == ["花园玫瑰", "洋桔梗"]
    assert len(data["plan"]["substitute_flowers"]) >= 2
    assert data["plan"]["substitute_flowers"][0]["source_flower"] == "芍药"
    assert "11 月" in data["plan"]["seasonality_note"]
    assert "减少花材种类与总支数" in "".join(data["plan"]["preserve_points"])
    assert "已处理的关键替代包括" in data["plan"]["materials_note"]


def test_not_found_paths_are_stable() -> None:
    analyze_response = client.post(
        "/api/input/analyze",
        json={
            "content_id": "missing_001",
            "image_url": "/mock/assets/placeholder-scene.png",
            "selection_box": {"x": 0, "y": 0, "width": 100, "height": 100},
            "voice_text": "把这个场景变成花"
        },
    )
    assert analyze_response.status_code == 404

    flower_response = client.get("/api/bouquet/not_exists/flowers/not_exists_flower")
    assert flower_response.status_code == 404

    edit_response = client.post(
        "/api/bouquet/edit",
        json={
            "result_id": "not_exists_result",
            "action": "voice_adjust",
            "target": {},
            "instruction": "更温柔一点"
        },
    )
    assert edit_response.status_code == 404

    emotion_response = client.post(
        "/api/emotion/build",
        json={
            "result_id": "not_exists_result",
            "mode": "scene",
            "voice_context": "送给朋友"
        },
    )
    assert emotion_response.status_code == 404

    remake_response = client.post(
        "/api/emotion/remake-preview",
        json={
            "result_id": "not_exists_result",
            "mode": "scene",
            "option_type": "same_feeling",
        },
    )
    assert remake_response.status_code == 404


def test_annotated_asset_library_is_readable() -> None:
    repository = get_content_repository()
    scene_groups = repository.annotated_assets["scene_groups"]
    flower_groups = repository.annotated_assets["flower_groups"]
    life_groups = repository.annotated_assets["life_groups"]
    reference_candidates = repository.list_reference_candidates("scene")

    assert len(scene_groups) == 12
    assert len(flower_groups) == 6
    assert len(life_groups) == 6
    assert any(item["group_id"] == "flower_blue_white" for item in flower_groups)
    assert any(item["reference_id"] == "flower_blue_white" for item in reference_candidates)


def test_annotated_asset_images_exist() -> None:
    repository = get_content_repository()
    image_root = Path(repository.annotated_assets["image_root"])
    all_groups = repository.list_asset_groups()

    missing_images: list[str] = []
    for group in all_groups:
        for image_name in group["images"]:
            image_path = image_root / image_name
            if not image_path.exists():
                missing_images.append(str(image_path))

    assert not missing_images


def test_all_images_are_referenced_by_annotated_assets() -> None:
    repository = get_content_repository()
    image_root = Path(repository.annotated_assets["image_root"])
    all_groups = repository.list_asset_groups()

    referenced_images = {
        image_name
        for group in all_groups
        for image_name in group["images"]
    }
    actual_images = {
        path.name
        for path in image_root.glob("*.png")
    }

    assert referenced_images == actual_images


def test_input_analyze_supports_asset_group_id() -> None:
    analyze_response = client.post(
        "/api/input/analyze",
        json={
            "content_id": "scene_window_rain",
            "image_url": "/library/assets/scene_window_rain_01.png",
            "selection_box": {"x": 12, "y": 16, "width": 180, "height": 140},
            "voice_text": "把这种安静的窗边雨感变成花"
        },
    )
    assert analyze_response.status_code == 200
    data = analyze_response.json()
    assert data["mode_result"]["detected_mode"] == "scene"
    assert data["mode_result"]["confidence"] == 0.87
    assert data["recommended_interpretation_id"] == "option_scene"
    assert data["needs_user_choice"] is False
    assert "窗边" in data["semantic_result"]["scene_tags"]
    assert "朋友" in data["semantic_result"]["relation_tags"]
    assert "轻治愈" in data["semantic_result"]["emotion_tags"]


def test_input_analyze_supports_asset_image_lookup() -> None:
    analyze_response = client.post(
        "/api/input/analyze",
        json={
            "content_id": "unknown_asset_id",
            "image_url": "/library/assets/life_thanks_leader_04.png",
            "selection_box": {"x": 20, "y": 24, "width": 160, "height": 120},
            "voice_text": "感谢领导，更正式一点"
        },
    )
    assert analyze_response.status_code == 200
    data = analyze_response.json()
    assert data["mode_result"]["detected_mode"] == "life"
    assert "领导" in data["semantic_result"]["relation_tags"]
    assert "感谢" in data["semantic_result"]["emotion_tags"]


def test_input_analyze_supports_vision_semantic_fallback() -> None:
    analyze_response = client.post(
        "/api/input/analyze",
        json={
            "content_id": "fallback_unknown_id",
            "image_url": "/uploads/window_rain_memory.png",
            "selection_box": {"x": 18, "y": 20, "width": 220, "height": 160},
            "voice_text": "想要这种安静一点的窗边雨感"
        },
    )
    assert analyze_response.status_code == 200
    data = analyze_response.json()
    assert data["mode_result"]["detected_mode"] == "scene"
    assert "窗边" in data["semantic_result"]["scene_tags"]
    assert any(tag in data["semantic_result"]["emotion_tags"] for tag in ["安静", "轻治愈", "治愈"])


def test_input_analyze_supports_generic_data_url_fallback() -> None:
    analyze_response = client.post(
        "/api/input/analyze",
        json={
            "content_id": "upload_unknown",
            "image_url": "data:image/png;base64,ZmFrZQ==",
            "selection_box": {"x": 0, "y": 0, "width": 128, "height": 128},
            "voice_text": "把这个画面变成更克制一点的花"
        },
    )
    assert analyze_response.status_code == 200
    data = analyze_response.json()
    assert data["mode_result"]["detected_mode"] == "scene"
    assert data["semantic_result"]["emotion_tags"]


def test_image_edit_provider_normalizes_boxes() -> None:
    provider = ImageEditProvider()
    boxes = provider.normalize_boxes([[40, 30, 10, 90], [100, 120, 160, 180]], max_boxes=2)
    assert boxes == [[10, 30, 40, 90], [100, 120, 160, 180]]


def test_generate_tutorial_returns_fallback_steps() -> None:
    response = client.post(
        "/api/generate-tutorial",
        json={
            "bouquet_image": "",
            "flowers": ["白玫瑰", "尤加利叶"],
            "with_images": False,
        },
    )
    assert response.status_code == 200
    data = response.json()
    assert data["code"] == 0
    assert data["data"]["status"] == "done"
    assert len(data["data"]["steps"]) >= 3
    assert all(step["image_status"] in {"done", "skipped"} for step in data["data"]["steps"])
    assert all("image_review" in step for step in data["data"]["steps"])
    assert all("image_review_score" in step for step in data["data"]["steps"])
    assert all("image_review_issues" in step for step in data["data"]["steps"])
    assert all("image_retry_count" in step for step in data["data"]["steps"])
    assert all(step["image_display_fit"] == "contain" for step in data["data"]["steps"])
    assert all(step["image_display_ratio"] == "3:4" for step in data["data"]["steps"])


def test_tutorial_review_normalization_rejects_low_score_and_blocking_issues() -> None:
    review = _normalize_tutorial_review_result(
        {
            "pass": True,
            "score": 0.62,
            "issues": ["花头有些失真"],
            "blocking_issues": ["手部动作错误", "主体被截断"],
            "action_ok": False,
            "composition_ok": False,
            "botany_ok": True,
            "reference_consistency_ok": True,
            "review_summary": "动作和构图都不合格",
            "retry_prompt_hint": "",
        }
    )

    assert review["passed"] is False
    assert review["score"] == 0.62
    assert "手部动作错误" in review["issues"]
    assert "主体被截断" in review["issues"]
    assert review["retry_prompt_hint"]
    assert review["review_text"] == "动作和构图都不合格"


def test_generate_card_returns_local_upload_url() -> None:
    tiny_jpeg = "data:image/jpeg;base64,/9j/4AAQSkZJRgABAQAAAQABAAD/2wCEAAkGBxAQDxAQEA8QEA8PDw8PDw8PDw8PDw8PFREWFhURFRUYHSggGBolHRUVITEhJSkrLi4uFx8zODMsNygtLisBCgoKDg0OGxAQGy0lICUtLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLf/AABEIAAEAAQMBIgACEQEDEQH/xAAXAAADAQAAAAAAAAAAAAAAAAAAAQID/8QAFBABAAAAAAAAAAAAAAAAAAAAAP/aAAwDAQACEAMQAAAB6AAAAP/EABQQAQAAAAAAAAAAAAAAAAAAACD/2gAIAQEAAT8Af//EABQRAQAAAAAAAAAAAAAAAAAAACD/2gAIAQIBAT8Af//EABQRAQAAAAAAAAAAAAAAAAAAACD/2gAIAQMBAT8Af//Z"
    response = client.post(
        "/api/generate-card",
        json={
            "source": tiny_jpeg,
            "before": tiny_jpeg,
            "after": tiny_jpeg,
            "title": "测试花束",
            "source_context": "窗边雨夜",
            "scene_reason": "保留了夜色和克制感",
        },
    )
    assert response.status_code == 200
    data = response.json()
    assert data["code"] == 0
    assert data["data"]["card_image"].startswith("/uploads/card/")
    assert data["data"]["compare_layout"] == "triple"
    assert data["data"]["scene_reason"]
    assert data["data"]["panel_order"] == ["source", "before", "after"]
    assert data["data"]["panel_labels"]["source"] == "输入素材"
    assert data["data"]["compare_panels"][0]["image_role"] == "scene_input"


def test_semantic_api_contract_request_can_be_built() -> None:
    recognizer = ApiSemanticRecognizer()
    repository = get_content_repository()
    content_profile = repository.get_content_or_asset_profile(
        content_id="scene_window_rain",
        image_url="/library/assets/scene_window_rain_01.png",
    )
    assert content_profile is not None

    contract_request = recognizer.build_api_request(
        request=AnalyzeInputRequest(
            content_id="scene_window_rain",
            image_url="/library/assets/scene_window_rain_01.png",
            selection_box=SelectionBox(x=10, y=12, width=120, height=90),
            voice_text="把这种安静的窗边雨感变成花",
        ),
        content_profile=content_profile,
    )

    assert contract_request.image_url.endswith("scene_window_rain_01.png")
    assert "窗边" in contract_request.candidate_tags
    assert "轻治愈" in contract_request.taxonomy.emotion_tags
    prompt = recognizer._build_prompt(contract_request)
    assert "花艺识别专家" in prompt
    assert "万物生花" in prompt
    assert "只返回 JSON 对象" in prompt
    assert "不等于后续每个生花方案都必须同时使用这些颜色" in prompt


def test_image_generation_api_contract_request_can_be_built() -> None:
    provider = ApiImageGenerationProvider()
    repository = get_content_repository()
    reference_map = repository.get_reference_map()
    contract_request = provider.build_api_request(
        request=GenerateBouquetRequest(
            mode="scene",
            semantic_result=SemanticResult(
                mode="scene",
                subject_tags=["窗边雨幕"],
                scene_tags=["窗边", "雨天"],
                emotion_tags=["克制", "轻治愈"],
                visual_tags=["蓝白", "留白"],
                color_palette=[],
                relation_tags=[],
                use_intent="表达氛围",
                semantic_summary="一个偏冷感、克制、治愈的场景输入。",
            ),
            reference_strategy="light",
            selected_reference_ids=["flower_blue_white"],
        ),
        bouquet_templates=repository.list_bouquet_templates("scene"),
        reference_map=reference_map,
    )

    assert contract_request.reference_strategy == "light"
    assert contract_request.creative_mode == "mixed"
    assert contract_request.selected_references[0].reference_id == "flower_blue_white"
    assert "蓝白" in contract_request.selected_references[0].visual_tags
    assert "可售卖" in contract_request.style_prompt
    variant = provider._build_default_variant_plan(contract_request)[0]
    generation_prompt = provider._build_generation_prompt(
        contract_request,
        variant=variant,
    )
    assert "不要复刻同一束花" in generation_prompt
    assert "明确避免" in generation_prompt
    assert "当前变体" in generation_prompt
    assert "轻参考" in generation_prompt
    assert "花材=" not in generation_prompt
    assert "完全忽略不匹配参考" in generation_prompt
    assert "必须符合现实植物学常识" in generation_prompt
    assert "白花黑芯" in generation_prompt
    assert "默认只选择一个最匹配的主参考" in generation_prompt
    assert "不要为了全面覆盖参考而做拼盘式融合" in generation_prompt
    assert "花材种类上限" in generation_prompt
    assert "主花占比" in generation_prompt
    assert "严格控制在不超过" in generation_prompt
    assert "优先通过重复、密度、留白和结构形成美感" in generation_prompt
    assert "花艺生图专家" in generation_prompt
    assert "主动舍弃它" in generation_prompt


def test_light_reference_payload_omits_reference_images() -> None:
    provider = ApiImageGenerationProvider()
    repository = get_content_repository()
    contract_request = provider.build_api_request(
        request=GenerateBouquetRequest(
            mode="scene",
            semantic_result=SemanticResult(
                mode="scene",
                subject_tags=["窗边雨幕"],
                scene_tags=["窗边", "雨天"],
                emotion_tags=["克制", "轻治愈"],
                visual_tags=["蓝白", "留白"],
                color_palette=[],
                relation_tags=[],
                use_intent="表达氛围",
                semantic_summary="一个偏冷感、克制、治愈的场景输入。",
            ),
            reference_strategy="light",
            selected_reference_ids=["flower_blue_white"],
        ),
        bouquet_templates=repository.list_bouquet_templates("scene"),
        reference_map=repository.get_reference_map(),
    )

    payload = provider._build_http_payload(
        contract_request,
        model="wan2.7-image",
        variant=provider._build_default_variant_plan(contract_request)[0],
    )
    content = payload["input"]["messages"][0]["content"]
    assert len(content) == 1
    assert payload["parameters"]["n"] == 1


def test_variant_planner_prompt_avoids_forced_reference_merging() -> None:
    provider = ApiImageGenerationProvider()
    repository = get_content_repository()
    contract_request = provider.build_api_request(
        request=GenerateBouquetRequest(
            mode="scene",
            semantic_result=SemanticResult(
                mode="scene",
                subject_tags=["窗边雨幕"],
                scene_tags=["窗边", "雨天"],
                emotion_tags=["克制", "轻治愈"],
                visual_tags=["暖灯", "朦胧"],
                color_palette=["深蓝", "暖黄"],
                relation_tags=[],
                use_intent="表达氛围",
                semantic_summary="一个偏安静、朦胧、轻治愈的雨夜场景输入。",
                translation_axes=["色彩对齐", "气质对齐"],
            ),
            reference_strategy="light",
            selected_reference_ids=["flower_blue_white", "flower_champagne_congrats"],
        ),
        bouquet_templates=repository.list_bouquet_templates("scene"),
        reference_map=repository.get_reference_map(),
    )

    planner_prompt = provider._build_variant_planner_prompt(contract_request)
    assert "参考是灵感来源，不是融合清单" in planner_prompt
    assert "可以完全忽略不匹配参考" in planner_prompt
    assert "不允许虚构花种或异常花芯结构" in planner_prompt
    assert "默认只借鉴一个最匹配的主参考" in planner_prompt
    assert "不要规划成多参考平均融合" in planner_prompt
    assert "花艺总监兼审美规划专家" in planner_prompt
    assert "主动舍弃某些颜色" in planner_prompt
    assert "species_count_cap" in planner_prompt
    assert "dominant_flower_ratio" in planner_prompt


def test_default_variant_plan_contains_bouquet_form_constraints() -> None:
    provider = ApiImageGenerationProvider()
    repository = get_content_repository()
    contract_request = provider.build_api_request(
        request=GenerateBouquetRequest(
            mode="scene",
            semantic_result=SemanticResult(
                mode="scene",
                subject_tags=["窗边雨幕"],
                scene_tags=["窗边", "雨天"],
                emotion_tags=["克制", "轻治愈"],
                visual_tags=["暖灯", "朦胧"],
                color_palette=["深蓝", "暖黄"],
                relation_tags=[],
                use_intent="表达氛围",
                semantic_summary="一个偏安静、朦胧、轻治愈的雨夜场景输入。",
                translation_axes=["色彩对齐", "气质对齐"],
            ),
            reference_strategy="light",
        ),
        bouquet_templates=repository.list_bouquet_templates("scene"),
        reference_map=repository.get_reference_map(),
    )

    plan = provider._build_default_variant_plan(contract_request)
    assert plan[0].composition_style == "mass"
    assert plan[0].material_richness == "single"
    assert plan[0].species_count_cap <= 2
    assert plan[0].dominant_flower_ratio >= 0.8


def test_strong_reference_payload_keeps_reference_images() -> None:
    provider = ApiImageGenerationProvider()
    repository = get_content_repository()
    contract_request = provider.build_api_request(
        request=GenerateBouquetRequest(
            mode="scene",
            semantic_result=SemanticResult(
                mode="scene",
                subject_tags=["窗边雨幕"],
                scene_tags=["窗边", "雨天"],
                emotion_tags=["克制", "轻治愈"],
                visual_tags=["蓝白", "留白"],
                color_palette=[],
                relation_tags=[],
                use_intent="表达氛围",
                semantic_summary="一个偏冷感、克制、治愈的场景输入。",
            ),
            reference_strategy="strong",
            selected_reference_ids=["flower_blue_white"],
        ),
        bouquet_templates=repository.list_bouquet_templates("scene"),
        reference_map=repository.get_reference_map(),
    )

    payload = provider._build_http_payload(
        contract_request,
        model="wan2.7-image",
        variant=provider._build_default_variant_plan(contract_request)[0],
    )
    content = payload["input"]["messages"][0]["content"]
    assert any("image" in item for item in content[1:])


def test_generate_returns_at_most_three_reference_previews() -> None:
    repository = get_content_repository()
    reference_candidates = repository.list_reference_candidates("flower")
    selected_reference_ids = [item["reference_id"] for item in reference_candidates[:5]]

    generate_response = client.post(
        "/api/bouquet/generate",
        json={
            "mode": "flower",
            "semantic_result": {
                "mode": "flower",
                "subject_tags": ["蓝白克制花束"],
                "scene_tags": ["正式送礼"],
                "emotion_tags": ["克制", "治愈"],
                "visual_tags": ["蓝白", "留白"],
                "color_palette": [],
                "relation_tags": ["朋友"],
                "use_intent": "gift",
                "semantic_summary": "一个偏克制的送礼花束输入。"
            },
            "reference_strategy": "light",
            "selected_reference_ids": selected_reference_ids
        },
    )
    assert generate_response.status_code == 200
    result = generate_response.json()["results"][0]
    assert len(result["reference_used"]) == 3


def test_runtime_mode_forces_mock_providers_in_test(monkeypatch) -> None:
    monkeypatch.setenv("APP_RUNTIME_MODE", "test")
    monkeypatch.setenv("SEMANTIC_PROVIDER", "api")
    monkeypatch.setenv("IMAGE_GENERATION_PROVIDER", "api")
    get_semantic_recognizer.cache_clear()
    get_image_generation_provider.cache_clear()

    assert isinstance(get_semantic_recognizer(), MockSemanticRecognizer)
    assert isinstance(get_image_generation_provider(), MockImageGenerationProvider)

    get_semantic_recognizer.cache_clear()
    get_image_generation_provider.cache_clear()


def test_runtime_mode_allows_api_providers_in_production(monkeypatch) -> None:
    monkeypatch.setenv("APP_RUNTIME_MODE", "production")
    monkeypatch.setenv("SEMANTIC_PROVIDER", "api")
    monkeypatch.setenv("IMAGE_GENERATION_PROVIDER", "api")
    get_semantic_recognizer.cache_clear()
    get_image_generation_provider.cache_clear()

    assert isinstance(get_semantic_recognizer(), ApiSemanticRecognizer)
    assert isinstance(get_image_generation_provider(), ApiImageGenerationProvider)

    get_semantic_recognizer.cache_clear()
    get_image_generation_provider.cache_clear()
