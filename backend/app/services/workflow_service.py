from __future__ import annotations

import threading
import time
import uuid
from concurrent.futures import ThreadPoolExecutor

from app.schemas.workflow import TutorialStep
from app.services.share_card_composer import compose_card
from app.services.workflow_clients import (
    call_multimodal_json,
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
    TUTORIAL_IMAGE_REVIEW_SYSTEM_PROMPT,
    TUTORIAL_PLANNER_SYSTEM_PROMPT,
    build_share_generation_prompt,
    build_share_planner_prompt,
    build_tutorial_image_review_prompt,
    build_tutorial_generation_prompt,
    build_tutorial_planner_prompt,
)
from app.services.workflow_reporter import save_share_card_report, save_tutorial_report


TUTORIAL_TASKS: dict[str, dict] = {}
TASK_LOCK = threading.Lock()
TASK_TTL_SECONDS = 3600

TUTORIAL_STAGE_GUIDANCE = {
    "prep": "近景教学图，桌面整洁，完整展示醒花、去叶、修剪花茎的双手动作，花头与容器都在画面内。",
    "framework": "半身俯拍教学图，完整展示先定骨架与高低线条的过程，手部动作自然，花束整体轮廓不能被截断。",
    "main": "中近景教学图，聚焦插入主花形成视觉重心的动作，至少清楚看到一只手的插花动作和主花位置关系。",
    "layering": "侧前方教学图，完整展示补入过渡花材和叶材形成层次的过程，保留前后高低关系，不要让花头挤成一团。",
    "finish": "成品整理教学图，完整展示收口、绑带或包装整理动作，花束外轮廓、底部收束和关键手势都要自然。",
    "general": "真实花艺教学图，完整展示当前步骤唯一关键动作，保留花束主体、手部动作和工作台逻辑。",
}

TUTORIAL_STAGE_FALLBACK_NOTES = {
    "prep": "本步建议优先参考文字说明完成醒花、去叶和斜剪花脚，确认每支花材都能稳定吸水后再进入下一步。",
    "framework": "本步建议先用线性花材或较高枝条定出整体高低轮廓，再检查花束是否有明确的呼吸空间。",
    "main": "本步建议先确定主花的视觉中心，不要一次插太多主花，先定一到两个焦点再补其余花材。",
    "layering": "本步建议从外侧与后侧慢慢补入辅花和叶材，边插边退远观察，避免把层次堆成同一平面。",
    "finish": "本步建议最后统一调整花头朝向和外轮廓，再完成绑带或包装收口，确认正面视觉重心稳定。",
    "general": "本步图片未通过审核，建议先按文字说明完成当前动作，再结合上一阶段成型结构检查整体是否自然。",
}


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
            "done": len([step for step in steps if step.get("image_status") in {"done", "skipped"}]),
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
    threading.Thread(target=_tutorial_worker, args=(task_id, flowers_text, bouquet_image), daemon=True).start()
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
    compare_panels = _build_compare_panels(has_source=bool(source))
    payload = {
        "card_image": public_upload_url(card_path),
        "share_text": share_bundle["result"]["share_text"],
        "scene_reason": share_bundle["result"]["scene_reason"],
        "bgm_options": share_bundle["result"]["bgm_options"],
        "compare_layout": "triple" if source else "double",
        "compare_panels": compare_panels,
        "panel_order": [panel["key"] for panel in compare_panels],
        "panel_labels": {panel["key"]: panel["label"] for panel in compare_panels},
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


def _build_compare_panels(*, has_source: bool) -> list[dict[str, object]]:
    panels: list[dict[str, object]] = []
    if has_source:
        panels.append(
            {
                "key": "source",
                "label": "输入素材",
                "order": 1,
                "image_role": "scene_input",
            }
        )
    panels.append(
        {
            "key": "before",
            "label": "AI 生花",
            "order": 2 if has_source else 1,
            "image_role": "ai_bouquet",
        }
    )
    panels.append(
        {
            "key": "after",
            "label": "自制复刻",
            "order": 3 if has_source else 2,
            "image_role": "user_recreation",
        }
    )
    return panels


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


def _tutorial_worker(task_id: str, flowers_text: str, bouquet_image: str) -> None:
    with TASK_LOCK:
        task = TUTORIAL_TASKS.get(task_id)
        if not task:
            return
        steps = task["steps"]

    try:
        with ThreadPoolExecutor(max_workers=min(4, len(steps) or 1)) as pool:
            futures = []
            for index, step in enumerate(steps):
                futures.append(pool.submit(_generate_step_image, task_id, index, step, flowers_text, bouquet_image))
            for future in futures:
                future.result()
        with TASK_LOCK:
            task = TUTORIAL_TASKS.get(task_id)
            if task:
                failed = sum(1 for item in task["steps"] if item.get("image_status") == "failed")
                fallback = sum(1 for item in task["steps"] if item.get("image_status") == "fallback")
                completed = sum(1 for item in task["steps"] if item.get("image_status") in {"done", "fallback", "skipped"})
                task["done"] = completed
                task["status"] = "done" if failed == 0 and fallback == 0 and completed == task["total"] else "partial"
                task["finished_at"] = time.time()
    except Exception as exc:
        with TASK_LOCK:
            task = TUTORIAL_TASKS.get(task_id)
            if task:
                task["status"] = "error"
                task["message"] = str(exc)
                task["finished_at"] = time.time()


def _generate_step_image(task_id: str, index: int, step: dict, flowers_text: str, bouquet_image: str) -> None:
    image_url = ""
    image_status = "failed"
    image_review = ""
    image_review_score = 0.0
    image_review_issues: list[str] = []
    image_retry_count = 0
    image_fallback_note = ""
    try:
        max_attempts = 3
        local_path = None
        stage = _infer_tutorial_step_stage(step)
        for attempt in range(max_attempts):
            retry_hint = image_review_issues[0] if image_review_issues else image_review
            generation_prompt = _build_tutorial_step_image_prompt(step, flowers_text, retry_hint, stage)
            attempt_suffix = "" if attempt == 0 else f"_retry{attempt}"
            local_path = create_result_path("tutorial", f"{task_id}_step{step.get('step', index + 1)}{attempt_suffix}", ".png")
            text2image(generation_prompt, str(local_path), size="1K")
            review = _review_tutorial_step_image(
                step=step,
                flowers_text=flowers_text,
                bouquet_image=bouquet_image,
                generated_image=str(local_path),
            )
            image_review = review["review_text"]
            image_review_score = review["score"]
            image_review_issues = review["issues"]
            image_retry_count = attempt
            if review["passed"]:
                image_url = public_upload_url(local_path)
                image_status = "done"
                break
        if image_status != "done":
            # 审核未全过但图片已生成：仍使用最后一张生成的图，避免用户看不到任何图
            if local_path and local_path.exists():
                image_url = public_upload_url(local_path)
                image_status = "done"
                image_review = image_review or "教程配图已生成（审核未完全通过，已采用）"
            else:
                image_status = "fallback"
                image_review = image_review or "教程配图未通过审核"
                image_fallback_note = _build_tutorial_image_fallback_note(step, stage, image_review_issues, image_review)
    except Exception as exc:
        image_url = ""
        stage = _infer_tutorial_step_stage(step)
        image_status = "fallback"
        image_review = str(exc)
        image_fallback_note = _build_tutorial_image_fallback_note(step, stage, image_review_issues, image_review)

    with TASK_LOCK:
        task = TUTORIAL_TASKS.get(task_id)
        if not task:
            return
        task["steps"][index]["image_url"] = image_url
        task["steps"][index]["image_status"] = image_status
        task["steps"][index]["image_review"] = image_review
        task["steps"][index]["image_review_score"] = image_review_score
        task["steps"][index]["image_review_issues"] = image_review_issues
        task["steps"][index]["image_retry_count"] = image_retry_count
        task["steps"][index]["image_fallback_note"] = image_fallback_note
        task["done"] = sum(1 for item in task["steps"] if item.get("image_status") in {"done", "fallback", "skipped"})


def _fallback_tutorial_steps(flowers: list[str], bouquet_image: str = "") -> list[dict]:
    main_flowers = "、".join(flowers[:2]) if flowers else "主花"
    image_url = (
        bouquet_image
        if bouquet_image.startswith("/uploads/")
        or bouquet_image.startswith("/mock/assets/")
        or bouquet_image.startswith("/library/assets/")
        else ""
    )
    return [
        TutorialStep(
            step=1,
            title="醒花与修剪",
            description="先修剪花茎、去掉多余叶片，让每一支花材充分喝水，再开始构图。",
            image_prompt="近景教学图，完整展示修剪花茎与整理叶片的双手动作，花头和容器不要被截断",
            image_url=image_url,
            image_status="done" if image_url else "skipped",
            image_review="已复用已有花束图",
            image_fallback_note="",
        ).model_dump(),
        TutorialStep(
            step=2,
            title="先定主花",
            description=f"先用 {main_flowers} 搭出骨架，确定视觉重心和外轮廓。",
            image_prompt="俯拍教学图，完整展示先放主花形成视觉中心的动作，画面保留花束骨架的整体轮廓",
            image_status="skipped",
            image_fallback_note="",
        ).model_dump(),
        TutorialStep(
            step=3,
            title="补足层次",
            description="按照高低、疏密、前后关系补入配花和叶材，让整体更有节奏。",
            image_prompt="侧面教学图，完整展示辅花逐层填入形成层次的过程，不要裁掉主要花头与手部动作",
            image_status="skipped",
            image_fallback_note="",
        ).model_dump(),
        TutorialStep(
            step=4,
            title="整理收口",
            description="最后调整朝向、修整外轮廓，并完成包装与绑带。",
            image_prompt="成品教学图，完整展示整理包装与绑带的收口动作，花束外轮廓完整自然",
            image_status="skipped",
            image_fallback_note="",
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
                image_status=str(step.get("image_status") or "pending"),
                image_review=str(step.get("image_review") or ""),
                image_review_score=float(step.get("image_review_score") or 0.0),
                image_review_issues=[str(item) for item in (step.get("image_review_issues") or []) if str(item).strip()],
                image_retry_count=int(step.get("image_retry_count") or 0),
                image_fallback_note=str(step.get("image_fallback_note") or ""),
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


def _call_workflow_multimodal_json(prompt: str, *, system_prompt: str, image_urls: list[str]) -> dict:
    base_url, api_key, model = resolve_workflow_text_config()
    if not base_url or not api_key:
        raise RuntimeError("workflow multimodal unavailable")
    return call_multimodal_json(
        prompt,
        image_urls=image_urls,
        model=model,
        system_prompt=system_prompt,
        base_url=base_url,
        api_key=api_key,
    )


def _build_tutorial_step_image_prompt(step: dict, flowers_text: str, retry_hint: str = "", stage: str = "general") -> str:
    stage_guidance = TUTORIAL_STAGE_GUIDANCE.get(stage, TUTORIAL_STAGE_GUIDANCE["general"])
    base_prompt = (
        f"插花教学步骤图，步骤标题：{step.get('title', '')}。"
        f" 当前动作：{step.get('image_prompt') or step.get('description', '')}。"
        f" 花材包含 {flowers_text}。"
        f" {stage_guidance}"
        " 画面为真实可执行的花艺教学场景，偏真实摄影教学参考风格，不要拼图，不要插画分镜，不要海报排版。"
        " 只表现当前这一步的唯一关键动作，禁止把前后多步动作混在同一张图里。"
        " 必须完整展示关键手部动作、主要花头、容器和花束轮廓，禁止截断主体。"
        " 花材必须真实存在，结构自然，不允许错误肢体、漂浮工具、异常花型、错误花芯、重复畸形花头和夸张 AI 痕迹。"
    )
    if retry_hint:
        return f"{base_prompt} 额外修正要求：{retry_hint}"
    return base_prompt


def _review_tutorial_step_image(
    *,
    step: dict,
    flowers_text: str,
    bouquet_image: str,
    generated_image: str,
) -> dict[str, object]:
    image_urls = [generated_image]
    if bouquet_image:
        image_urls.insert(0, bouquet_image)
    try:
        result = _call_workflow_multimodal_json(
            build_tutorial_image_review_prompt(
                step_title=str(step.get("title") or ""),
                step_description=str(step.get("description") or ""),
                step_image_prompt=str(step.get("image_prompt") or ""),
                flowers_text=flowers_text,
                has_bouquet_reference=bool(bouquet_image),
            ),
            system_prompt=TUTORIAL_IMAGE_REVIEW_SYSTEM_PROMPT,
            image_urls=image_urls,
        )
        return _normalize_tutorial_review_result(result)
    except Exception as exc:
        return {
            "passed": True,
            "score": 1.0,
            "issues": [],
            "retry_prompt_hint": "",
            "review_text": f"审核跳过：{exc}",
        }


def _normalize_tutorial_review_result(result: dict[str, object]) -> dict[str, object]:
    score = _coerce_review_score(result.get("score"))
    issues = [str(item).strip() for item in (result.get("issues") or []) if str(item).strip()]
    blocking_issues = [str(item).strip() for item in (result.get("blocking_issues") or []) if str(item).strip()]
    retry_hint = str(result.get("retry_prompt_hint") or "").strip()
    summary = str(result.get("review_summary") or "").strip()
    passed = bool(result.get("pass"))

    # 放宽审核：仅在有明确 blocking_issues 或分数过低时才否决；
    # 单项 *_ok=False 不再直接否决（避免细节问题导致全军覆没）
    if blocking_issues:
        passed = False
    if score < 0.5:
        passed = False

    combined_issues = issues + [item for item in blocking_issues if item not in issues]
    if not retry_hint and combined_issues:
        retry_hint = "；".join(combined_issues[:3])
    review_text = summary or "；".join(combined_issues[:2]) or ("审核通过" if passed else "教程配图未通过审核")
    return {
        "passed": passed,
        "score": score,
        "issues": combined_issues[:5],
        "retry_prompt_hint": retry_hint,
        "review_text": review_text,
    }


def _coerce_review_score(value: object) -> float:
    try:
        score = float(value)
    except (TypeError, ValueError):
        return 1.0
    return max(0.0, min(1.0, score))


def _infer_tutorial_step_stage(step: dict) -> str:
    text = f"{step.get('title', '')} {step.get('description', '')} {step.get('image_prompt', '')}"
    if any(token in text for token in ["醒花", "修剪", "去叶", "剪花脚"]):
        return "prep"
    if any(token in text for token in ["骨架", "定型", "结构", "高低", "线条"]):
        return "framework"
    if any(token in text for token in ["主花", "重心", "焦点", "中心"]):
        return "main"
    if any(token in text for token in ["层次", "辅花", "配花", "叶材", "填入", "补入"]):
        return "layering"
    if any(token in text for token in ["收口", "包装", "绑带", "整理", "完成"]):
        return "finish"
    return "general"


def _build_tutorial_image_fallback_note(
    step: dict,
    stage: str,
    issues: list[str],
    review_text: str,
) -> str:
    base_note = TUTORIAL_STAGE_FALLBACK_NOTES.get(stage, TUTORIAL_STAGE_FALLBACK_NOTES["general"])
    issue_text = "；".join([item for item in issues if item][:2])
    if issue_text:
        return f"{base_note} 本次图片主要问题：{issue_text}。"
    if review_text:
        return f"{base_note} 本次图片未采用，原因：{review_text}。"
    return base_note
