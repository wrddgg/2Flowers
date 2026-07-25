from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any

from app.services.share_card_composer import save_dataurl_image


REPORT_ROOT = Path(__file__).resolve().parents[2] / "reports" / "workflow_runtime"


def save_tutorial_report(snapshot: dict[str, Any]) -> dict[str, str]:
    run_name = f"tutorial_{datetime.now().strftime('%Y%m%d_%H%M%S_%f')}"
    report_dir = _prepare_report_dir(run_name)
    json_path = report_dir / f"{run_name}_snapshot.json"
    md_path = report_dir / f"{run_name}_report.md"

    json_path.write_text(json.dumps(snapshot, ensure_ascii=False, indent=2), encoding="utf-8")
    md_path.write_text(_build_tutorial_markdown(snapshot), encoding="utf-8")
    return {
        "snapshot": str(json_path),
        "markdown": str(md_path),
    }


def save_share_card_report(snapshot: dict[str, Any], before_dataurl: str, after_dataurl: str) -> dict[str, str]:
    run_name = f"share_card_{datetime.now().strftime('%Y%m%d_%H%M%S_%f')}"
    report_dir = _prepare_report_dir(run_name)
    assets_dir = report_dir / "assets"
    before_path = assets_dir / "before.jpg"
    after_path = assets_dir / "after.jpg"
    save_dataurl_image(before_dataurl, str(before_path))
    save_dataurl_image(after_dataurl, str(after_path))

    snapshot = {
        **snapshot,
        "assets": {
            "before": "./assets/before.jpg",
            "after": "./assets/after.jpg",
            **snapshot.get("assets", {}),
        },
    }

    json_path = report_dir / f"{run_name}_snapshot.json"
    md_path = report_dir / f"{run_name}_report.md"
    json_path.write_text(json.dumps(snapshot, ensure_ascii=False, indent=2), encoding="utf-8")
    md_path.write_text(_build_share_card_markdown(snapshot), encoding="utf-8")
    return {
        "snapshot": str(json_path),
        "markdown": str(md_path),
    }


def _prepare_report_dir(run_name: str) -> Path:
    dated_dir = REPORT_ROOT / datetime.now().strftime("%Y%m%d")
    report_dir = dated_dir / run_name
    report_dir.mkdir(parents=True, exist_ok=True)
    return report_dir


def _build_tutorial_markdown(snapshot: dict[str, Any]) -> str:
    planner = snapshot["planner"]
    generation = snapshot["generation"]
    steps = generation["steps"]
    lines = [
        "# 接口3 过程报告",
        "",
        f"- 生成时间：{snapshot['created_at']}",
        f"- 花材：{'、'.join(snapshot['request']['flowers'])}",
        f"- with_images：{snapshot['request']['with_images']}",
        "",
        "## 规划阶段",
        "",
        "### Planner System Prompt",
        "",
        "```text",
        planner["system_prompt"],
        "```",
        "",
        "### Planner Prompt",
        "",
        "```text",
        planner["prompt"],
        "```",
        "",
        "### Planner Result",
        "",
        "```json",
        json.dumps(planner["plan"], ensure_ascii=False, indent=2),
        "```",
        "",
        "## 教学生成阶段",
        "",
        "### Expert System Prompt",
        "",
        "```text",
        generation["system_prompt"],
        "```",
        "",
        "### Expert Prompt",
        "",
        "```text",
        generation["prompt"],
        "```",
        "",
        "### Steps",
        "",
    ]
    for step in steps:
        lines.extend(
            [
                f"#### Step {step['step']} · {step['title']}",
                "",
                f"- 描述：{step['description']}",
                f"- 配图提示：{step['image_prompt']}",
                f"- 配图结果：{step.get('image_url') or '(待生成)'}",
                "",
            ]
        )
    return "\n".join(lines)


def _build_share_card_markdown(snapshot: dict[str, Any]) -> str:
    planner = snapshot["planner"]
    generation = snapshot["generation"]
    lines = [
        "# 接口4 过程报告",
        "",
        f"- 生成时间：{snapshot['created_at']}",
        f"- 标题：{snapshot['request']['title']}",
        "",
        "## 输入素材",
        "",
        f"- 原画面：![before]({snapshot['assets']['before']})",
        f"- 我的作品：![after]({snapshot['assets']['after']})",
        "",
        "## 策划阶段",
        "",
        "### Planner System Prompt",
        "",
        "```text",
        planner["system_prompt"],
        "```",
        "",
        "### Planner Prompt",
        "",
        "```text",
        planner["prompt"],
        "```",
        "",
        "### Planner Result",
        "",
        "```json",
        json.dumps(planner["plan"], ensure_ascii=False, indent=2),
        "```",
        "",
        "## 文案生成阶段",
        "",
        "### Expert System Prompt",
        "",
        "```text",
        generation["system_prompt"],
        "```",
        "",
        "### Expert Prompt",
        "",
        "```text",
        generation["prompt"],
        "```",
        "",
        "### 结果",
        "",
        f"- 分享文案：{generation['result']['share_text']}",
        f"- 卡片图片：{generation['card_image']}",
        "",
        "```json",
        json.dumps(generation["result"]["bgm_options"], ensure_ascii=False, indent=2),
        "```",
        "",
    ]
    return "\n".join(lines)
