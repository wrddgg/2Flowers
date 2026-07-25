from __future__ import annotations

import threading
import time
import uuid
from concurrent.futures import ThreadPoolExecutor

from app.schemas.workflow import TutorialStep
from app.services.share_card_composer import compose_card
from app.services.workflow_clients import (
    create_result_path,
    has_wan_image_config,
    call_text_json,
    public_upload_url,
    resolve_workflow_planner_config,
    resolve_workflow_text_config,
    text2image,
)
from app.services.workflow_prompts import (
    SHARE_EXPERT_SYSTEM_PROMPT,
    SHARE_PLANNER_SYSTEM_PROMPT,
    TUTORIAL_EXPERT_SYSTEM_PROMPT,
    TUTORIAL_PLANNER_SYSTEM_PROMPT,
    build_share_generation_prompt,
    build_share_planner_prompt,
    build_tutorial_generation_prompt,
    build_tutorial_planner_prompt,
)
from app.services.workflow_reporter import save_share_card_report, save_tutorial_report


TUTORIAL_TASKS: dict[str, dict] = {}
TASK_LOCK = threading.Lock()
TASK_TTL_SECONDS = 3600


def generate_tutorial_payload(*, flowers: list[str], bouquet_image: str = "", with_images: bool = True) -> dict:
    if not flowers:
        raise ValueError("缺少花材列表 flowers")

    tutorial_bundle = build_tutorial_steps(flowers, bouquet_image=bouquet_image)
    steps = tutorial_bundle["steps"]
    report_paths = save_tutorial_report(
        {
            "created_at": time.strftime("%Y-%m-%d %H:%M:%S"),
            "request": {
                "flowers": flowers,
                "bouquet_image": bouquet_image,
                "with_images": with_images,
            },
            "planner": tutorial_bundle["planner"],
            "generation": tutorial_bundle["generation"],
        }
    )
    if not with_images or not has_wan_image_config():
        return {
            "task_id": "",
            "status": "done",
            "total": len(steps),
            "done": len([step for step in steps if step["image_url"]]),
            "steps": steps,
            "report": report_paths,
        }

    task_id = uuid.uuid4().hex[:12]
    now = time.time()
    with TASK_LOCK:
        for expired_id in [key for key, value in TUTORIAL_TASKS.items() if now - value.get("created_at", now) > TASK_TTL_SECONDS]:
            TUTORIAL_TASKS.pop(expired_id, None)
        TUTORIAL_TASKS[task_id] = {
            "status": "processing",
            "steps": steps,
            "total": len(steps),
            "done": 0,
            "created_at": now,
            "finished_at": None,
        }

    flowers_text = "、".join(flowers)
    threading.Thread(target=_tutorial_worker, args=(task_id, flowers_text), daemon=True).start()
    return {
        "task_id": task_id,
        "status": "processing",
        "total": len(steps),
        "done": 0,
        "steps": steps,
        "report": report_paths,
    }


def tutorial_status_payload(task_id: str) -> dict | None:
    with TASK_LOCK:
        task = TUTORIAL_TASKS.get(task_id)
        if not task:
            return None
        return {
            "task_id": task_id,
            "status": task["status"],
            "total": task["total"],
            "done": task["done"],
            "steps": task["steps"],
        }


def generate_card_payload(
    *,
    source: str = "",
    before: str,
    after: str,
    title: str | None = None,
    source_context: str = "",
    scene_reason: str = "",
) -> dict:
    card_path = create_result_path("card", "compare", ".jpg")
    compose_card(source, before, after, title or "", str(card_path))
    share_bundle = build_share_text(title or "这束花", source_context=source_context, scene_reason=scene_reason)
    payload = {
        "card_image": public_upload_url(card_path),
        "share_text": share_bundle["result"]["share_text"],
        "scene_reason": share_bundle["result"]["scene_reason"],
        "bgm_options": share_bundle["result"]["bgm_options"],
        "compare_layout": "triple" if source else "double",
    }
    payload["report"] = save_share_card_report(
        {
            "created_at": time.strftime("%Y-%m-%d %H:%M:%S"),
            "request": {
                "title": title or "这束花",
                "source_context": source_context,
                "scene_reason": scene_reason,
                "has_source": bool(source),
            },
            "planner": share_bundle["planner"],
            "generation": {
                **share_bundle["generation"],
                "card_image": payload["card_image"],
                "result": {
                    "share_text": payload["share_text"],
                    "scene_reason": payload["scene_reason"],
                    "bgm_options": payload["bgm_options"],
                },
            },
        },
        source or before,
        after,
    )
    return payload


def build_tutorial_steps(flowers: list[str], bouquet_image: str = "") -> dict:
    planner = _build_tutorial_plan(flowers, bouquet_image=bouquet_image)
    if planner:
        try:
            prompt = build_tutorial_generation_prompt(flowers=flowers, plan=planner)
            result = _call_workflow_text_json(
                prompt,
                system_prompt=TUTORIAL_EXPERT_SYSTEM_PROMPT,
            )
            normalized = _normalize_tutorial_steps(result.get("steps") or [])
            if normalized:
                return {
                    "steps": normalized[:5],
                    "planner": planner,
                    "generation": {
                        "system_prompt": TUTORIAL_EXPERT_SYSTEM_PROMPT,
                        "prompt": prompt,
                        "steps": normalized[:5],
                    },
                }
        except Exception:
            pass

    fallback_steps = _fallback_tutorial_steps(flowers, bouquet_image)
    return {
        "steps": fallback_steps,
        "planner": planner or _fallback_tutorial_plan(flowers),
        "generation": {
            "system_prompt": TUTORIAL_EXPERT_SYSTEM_PROMPT,
            "prompt": "(fallback tutorial generation)",
            "steps": fallback_steps,
        },
    }


def build_share_text(title: str, source_context: str = "", scene_reason: str = "") -> dict:
    planner = _build_share_plan(title, source_context=source_context, scene_reason=scene_reason)
    if planner:
        try:
            prompt = build_share_generation_prompt(
                title=title,
                plan=planner,
                source_context=source_context,
                scene_reason=scene_reason,
            )
            result = _call_workflow_text_json(
                prompt,
                system_prompt=SHARE_EXPERT_SYSTEM_PROMPT,
            )
            options = result.get("bgm_options") or []
            share_text = result.get("share_text") or "把任何画面，变成一束花 #万物生花"
            normalized_scene_reason = str(
                result.get("scene_reason") or planner.get("plan", {}).get("why_it_fits_scene") or scene_reason
            ).strip()
            if options:
                return {
                    "planner": planner,
                    "generation": {
                        "system_prompt": SHARE_EXPERT_SYSTEM_PROMPT,
                        "prompt": prompt,
                    },
                    "result": {
                        "share_text": share_text,
                        "scene_reason": normalized_scene_reason or _fallback_scene_reason(title, source_context),
                        "bgm_options": options[:3],
                    },
                }
        except Exception:
            pass

    return {
        "planner": planner or _fallback_share_plan(title, source_context=source_context, scene_reason=scene_reason),
        "generation": {
            "system_prompt": SHARE_EXPERT_SYSTEM_PROMPT,
            "prompt": "(fallback share generation)",
        },
        "result": {
            "share_text": f"把「{title}」变成一束花 #万物生花",
            "scene_reason": scene_reason or _fallback_scene_reason(title, source_context),
            "bgm_options": [
                {"id": "bgm1", "name": "晚风告白", "artist": "花房乐队"},
                {"id": "bgm2", "name": "日落大道", "artist": "慢速列车"},
                {"id": "bgm3", "name": "Bloom", "artist": "Petal"},
            ],
        },
    }


def _tutorial_worker(task_id: str, flowers_text: str) -> None:
    with TASK_LOCK:
        task = TUTORIAL_TASKS.get(task_id)
        if not task:
            return
        steps = task["steps"]

    try:
        with ThreadPoolExecutor(max_workers=min(4, len(steps) or 1)) as pool:
            for index, step in enumerate(steps):
                pool.submit(_generate_step_image, task_id, index, step, flowers_text)
        with TASK_LOCK:
            task = TUTORIAL_TASKS.get(task_id)
            if task:
                task["status"] = "done"
                task["finished_at"] = time.time()
    except Exception as exc:
        with TASK_LOCK:
            task = TUTORIAL_TASKS.get(task_id)
            if task:
                task["status"] = "error"
                task["message"] = str(exc)
                task["finished_at"] = time.time()


def _generate_step_image(task_id: str, index: int, step: dict, flowers_text: str) -> None:
    image_url = ""
    try:
        prompt = (
            f"插花教学步骤图：{step.get('image_prompt') or step.get('description', '')}。"
            f" 花材包含 {flowers_text}。画面干净、主体突出、光线均匀，"
            "半写实教学插画风格，适合新手跟做。"
        )
        local_path = create_result_path("tutorial", f"{task_id}_step{step.get('step', index + 1)}", ".png")
        text2image(prompt, str(local_path), size="1K")
        image_url = public_upload_url(local_path)
    except Exception:
        image_url = ""

    with TASK_LOCK:
        task = TUTORIAL_TASKS.get(task_id)
        if not task:
            return
        task["steps"][index]["image_url"] = image_url
        task["done"] = sum(1 for item in task["steps"] if item.get("image_url"))


def _fallback_tutorial_steps(flowers: list[str], bouquet_image: str = "") -> list[dict]:
    main_flowers = "、".join(flowers[:2]) if flowers else "主花"
    image_url = bouquet_image if bouquet_image.startswith("/uploads/") or bouquet_image.startswith("/mock/") else ""
    return [
        TutorialStep(
            step=1,
            title="醒花与修剪",
            description="先修剪花茎、去掉多余叶片，让每一支花材充分喝水，再开始构图。",
            image_prompt="特写：修剪花茎与整理叶片",
            image_url=image_url,
        ).model_dump(),
        TutorialStep(
            step=2,
            title="先定主花",
            description=f"先用 {main_flowers} 搭出骨架，确定视觉重心和外轮廓。",
            image_prompt="俯拍：先放主花形成视觉中心",
        ).model_dump(),
        TutorialStep(
            step=3,
            title="补足层次",
            description="按照高低、疏密、前后关系补入配花和叶材，让整体更有节奏。",
            image_prompt="侧面：辅花逐层填入形成层次",
        ).model_dump(),
        TutorialStep(
            step=4,
            title="整理收口",
            description="最后调整朝向、修整外轮廓，并完成包装与绑带。",
            image_prompt="成品：整理包装与绑带",
        ).model_dump(),
    ]


def _build_tutorial_plan(flowers: list[str], bouquet_image: str = "") -> dict | None:
    try:
        prompt = build_tutorial_planner_prompt(flowers=flowers, bouquet_image=bouquet_image)
        result = _call_workflow_planner_json(
            prompt,
            system_prompt=TUTORIAL_PLANNER_SYSTEM_PROMPT,
        )
        if isinstance(result, dict) and result.get("teaching_focus"):
            return {
                "system_prompt": TUTORIAL_PLANNER_SYSTEM_PROMPT,
                "prompt": prompt,
                "plan": result,
            }
    except Exception:
        return None
    return None


def _build_share_plan(title: str, source_context: str = "", scene_reason: str = "") -> dict | None:
    try:
        prompt = build_share_planner_prompt(title=title, source_context=source_context, scene_reason=scene_reason)
        result = _call_workflow_planner_json(
            prompt,
            system_prompt=SHARE_PLANNER_SYSTEM_PROMPT,
        )
        if isinstance(result, dict) and result.get("primary_angle"):
            return {
                "system_prompt": SHARE_PLANNER_SYSTEM_PROMPT,
                "prompt": prompt,
                "plan": result,
            }
    except Exception:
        return None
    return None


def _fallback_tutorial_plan(flowers: list[str]) -> dict:
    return {
        "system_prompt": TUTORIAL_PLANNER_SYSTEM_PROMPT,
        "prompt": "(fallback tutorial planner)",
        "plan": {
            "teaching_focus": "先骨架后层次",
            "bouquet_structure": "主花定点、辅花补层、最后收口",
            "step_count": 4,
            "must_include_actions": ["醒花与修剪", "定主花骨架", "补辅花叶材", "整理收口"],
            "optional_actions": [],
            "beginner_risks": ["主花高度不稳", "材料堆在一个平面"],
            "advice_for_generator": f"围绕 {'、'.join(flowers[:3])} 保持克制、真实、可执行。",
        },
    }


def _fallback_share_plan(title: str, source_context: str = "", scene_reason: str = "") -> dict:
    return {
        "system_prompt": SHARE_PLANNER_SYSTEM_PROMPT,
        "prompt": "(fallback share planner)",
        "plan": {
            "primary_angle": "情绪转译感",
            "tone": "温柔克制",
            "bgm_mood": "轻治愈",
            "why_it_fits_scene": scene_reason or _fallback_scene_reason(title, source_context),
            "advice_for_copywriter": f"围绕「{title}」写简洁、有记忆点的发布文案。",
        },
    }


def _fallback_scene_reason(title: str, source_context: str = "") -> str:
    if source_context:
        return f"它保留了素材里“{source_context}”的情绪线索，同时把画面气质收束成更适合花艺表达的形式。"
    return f"它延续了“{title}”对应的情绪与视觉重心，所以适合承接原始素材场景。"


def _normalize_tutorial_steps(steps: list[dict]) -> list[dict]:
    normalized: list[dict] = []
    for index, step in enumerate(steps, start=1):
        normalized.append(
            TutorialStep(
                step=int(step.get("step", index)),
                title=str(step.get("title") or f"步骤 {index}"),
                description=str(step.get("description") or "根据花材状态逐步整理花束结构。"),
                image_prompt=str(step.get("image_prompt") or step.get("description") or ""),
                image_url="",
            ).model_dump()
        )
    return normalized


def _call_workflow_planner_json(prompt: str, *, system_prompt: str) -> dict:
    base_url, api_key, model = resolve_workflow_planner_config()
    if not base_url or not api_key:
        raise RuntimeError("workflow planner unavailable")
    return call_text_json(
        prompt,
        model=model,
        system_prompt=system_prompt,
        base_url=base_url,
        api_key=api_key,
    )


def _call_workflow_text_json(prompt: str, *, system_prompt: str) -> dict:
    base_url, api_key, model = resolve_workflow_text_config()
    if not base_url or not api_key:
        raise RuntimeError("workflow text unavailable")
    return call_text_json(
        prompt,
        model=model,
        system_prompt=system_prompt,
        base_url=base_url,
        api_key=api_key,
    )
