"""万物生花 · 后端 API（接口1 图像识别 / 接口3 制作教程 / 接口4 分享卡片）"""
import threading
import time
import uuid
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any

import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from clients import (
    call_text_json,
    call_vision_json,
    dataurl_to_inline,
    text2image,
)
from compose import compose_card
from config import get_settings
from prompts import (
    PROMPT_ANALYZE_IMAGE,
    PROMPT_GENERATE_TUTORIAL,
    PROMPT_SHARE_TEXT,
)

settings = get_settings()
app = FastAPI(title="万物生花 API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

UPLOAD_DIR = Path(settings.upload_dir)
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
app.mount("/uploads", StaticFiles(directory=str(UPLOAD_DIR)), name="uploads")


# ---------------------------------------------------------------------------
# 统一响应
# ---------------------------------------------------------------------------
def ok(data: Any) -> dict:
    return {"code": 0, "data": data, "message": "ok"}


def fail(message: str, code: int = 1) -> dict:
    return {"code": code, "data": None, "message": message}


def public_url(local_path: str) -> str:
    """把 uploads 下的本地路径转为可公网访问的 URL"""
    rel = Path(local_path).relative_to(UPLOAD_DIR).as_posix()
    base = settings.public_base.rstrip("/")
    return f"{base}/uploads/{rel}" if base else f"/uploads/{rel}"


# ---------------------------------------------------------------------------
# 请求模型（与前端实际传参一致：均为 JSON，图片用 dataURL）
# ---------------------------------------------------------------------------
class AnalyzeImageReq(BaseModel):
    image: str  # dataURL


class GenerateTutorialReq(BaseModel):
    bouquet_image: str = ""
    flowers: list[str] = []
    with_images: bool = True  # 是否为每步生成配图


class GenerateCardReq(BaseModel):
    before: str  # dataURL
    after: str   # dataURL
    title: str | None = None


# ---------------------------------------------------------------------------
# 接口1：图像识别
# ---------------------------------------------------------------------------
@app.post("/api/analyze-image")
def analyze_image(req: AnalyzeImageReq):
    try:
        image_url = dataurl_to_inline(req.image)
        result = call_vision_json(PROMPT_ANALYZE_IMAGE, [image_url])
        result.setdefault("title", "未命名画面")
        result.setdefault("style", "自然 · 光影")
        result.setdefault("palette", ["#E8A87C", "#C38D9E", "#8E6C8A", "#F2D49B"])
        result.setdefault("mood", "温柔、治愈")
        result.setdefault("content", "")
        result.setdefault("scene", {"person": False, "place": None, "architecture": None, "time": None})
        result.setdefault("segments", [])
        return ok(result)
    except Exception as e:
        import traceback
        traceback.print_exc()
        return fail(f"图像识别失败: {e}")


# ---------------------------------------------------------------------------
# 接口3：制作教程（异步任务模式）
#   POST /api/generate-tutorial  -> 立即返回 task_id + 文本步骤
#   GET  /api/tutorial-status    -> 轮询配图进度，全部完成后返回完整 steps
# ---------------------------------------------------------------------------
TUTORIAL_TASKS: dict[str, dict] = {}
TUTORIAL_TASKS_LOCK = threading.Lock()
TUTORIAL_TASK_TTL = 3600  # 任务结果保留1小时


def _set_task(task_id: str, **fields):
    with TUTORIAL_TASKS_LOCK:
        if task_id in TUTORIAL_TASKS:
            TUTORIAL_TASKS[task_id].update(fields)


def _gen_step_image(task_id: str, idx: int, step: dict, flowers_text: str):
    """生成单张步骤配图（线程池并行）"""
    try:
        ip = step.get("image_prompt") or step.get("description", "")
        full_prompt = (
            f"插花教学步骤图：{ip}。"
            f"花材包含{flowers_text}。画面干净、主体突出、光线均匀，"
            f"半写实教学插画风格，适合新手跟做。"
        )
        local = UPLOAD_DIR / "tutorial" / f"{task_id}_step{step.get('step', idx+1)}.png"
        text2image(full_prompt, str(local), size="1K")
        url = public_url(str(local))
    except Exception as e:
        url = ""
        print(f"step {step.get('step')} 配图失败: {e}")
    with TUTORIAL_TASKS_LOCK:
        task = TUTORIAL_TASKS.get(task_id)
        if task:
            task["steps"][idx]["image_url"] = url
            task["done"] += 1


def _tutorial_worker(task_id: str, steps: list, flowers_text: str):
    """后台线程：并行生成全部步骤配图"""
    try:
        with ThreadPoolExecutor(max_workers=5) as pool:
            for i, st in enumerate(steps):
                pool.submit(_gen_step_image, task_id, i, st, flowers_text)
        _set_task(task_id, status="done", finished_at=time.time())
    except Exception as e:
        _set_task(task_id, status="error", message=str(e), finished_at=time.time())


@app.post("/api/generate-tutorial")
def generate_tutorial(req: GenerateTutorialReq):
    try:
        if not req.flowers:
            return fail("缺少花材列表 flowers")
        flowers_text = "、".join(req.flowers)
        prompt = PROMPT_GENERATE_TUTORIAL.replace("{flowers}", flowers_text)
        result = call_text_json(prompt)
        steps = result.get("steps", [])
        if not steps:
            return fail("教程生成失败：未返回步骤")

        for st in steps:
            st["image_url"] = ""

        if not req.with_images:
            return ok({"task_id": "", "status": "done", "steps": steps})

        task_id = uuid.uuid4().hex[:12]
        with TUTORIAL_TASKS_LOCK:
            # 顺便清理过期任务
            now = time.time()
            for k in [k for k, v in TUTORIAL_TASKS.items()
                      if now - v.get("created_at", now) > TUTORIAL_TASK_TTL]:
                TUTORIAL_TASKS.pop(k, None)
            TUTORIAL_TASKS[task_id] = {
                "status": "processing",
                "steps": steps,
                "total": len(steps),
                "done": 0,
                "created_at": now,
                "finished_at": None,
            }
        threading.Thread(
            target=_tutorial_worker, args=(task_id, steps, flowers_text), daemon=True
        ).start()

        return ok({
            "task_id": task_id,
            "status": "processing",
            "total": len(steps),
            "steps": steps,  # 文本已就绪，可先行展示
        })
    except Exception as e:
        import traceback
        traceback.print_exc()
        return fail(f"制作教程失败: {e}")


@app.get("/api/tutorial-status")
def tutorial_status(task_id: str):
    with TUTORIAL_TASKS_LOCK:
        task = TUTORIAL_TASKS.get(task_id)
        if not task:
            return fail("任务不存在或已过期", code=404)
        return ok({
            "task_id": task_id,
            "status": task["status"],
            "total": task["total"],
            "done": task["done"],
            "steps": task["steps"],
        })


# ---------------------------------------------------------------------------
# 接口4：生成分享卡片（合成对比图 + 文案 + BGM）
# ---------------------------------------------------------------------------
@app.post("/api/generate-card")
def generate_card(req: GenerateCardReq):
    try:
        cid = uuid.uuid4().hex[:12]
        local = UPLOAD_DIR / "card" / f"{cid}.jpg"
        compose_card(req.before, req.after, req.title or "", str(local))

        text_prompt = PROMPT_SHARE_TEXT.replace("{title}", req.title or "这束花")
        text_result = call_text_json(text_prompt)

        return ok({
            "card_image": public_url(str(local)),
            "share_text": text_result.get("share_text", "把任何画面，变成一束花 #万物生花"),
            "bgm_options": text_result.get("bgm_options", []),
        })
    except Exception as e:
        import traceback
        traceback.print_exc()
        return fail(f"生成分享卡片失败: {e}")


@app.get("/api/health")
def health():
    return ok({"status": "up", "time": int(time.time())})


if __name__ == "__main__":
    uvicorn.run("main:app", host=settings.host, port=settings.port, reload=False)
