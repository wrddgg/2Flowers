from __future__ import annotations

from copy import deepcopy

from app.schemas.bouquet import BouquetResult, EditBouquetRequest
from app.utils.text import new_id


class BouquetEditor:
    def edit(self, source: BouquetResult, request: EditBouquetRequest) -> BouquetResult:
        result = deepcopy(source)
        result.result_id = new_id(f"{source.result_id}_{request.action}")

        if request.action == "delete_flower":
            result = self._delete_flower(result, request.target.flower_id)
            result.summary = "已移除指定花朵，整体表达更克制也更聚焦。"
            result.tags = self._merge_tags(result.tags, ["更克制", "已调整"])
        elif request.action == "replace_region":
            result.summary = f"已根据“{request.instruction or '替换局部'}”完成局部替换，保留原有主情绪。"
            result.tags = self._merge_tags(result.tags, ["局部替换", "更贴合意图"])
        elif request.action == "repaint_region":
            result.summary = f"已完成局部重绘，新的画面表达更贴近“{request.instruction or '当前需求'}”。"
            result.tags = self._merge_tags(result.tags, ["重绘", "二次共创"])
        elif request.action == "voice_adjust":
            result.summary = f"已根据语音指令“{request.instruction}”微调花束方向。"
            result.tags = self._merge_tags(result.tags, ["语音微调", "共创完成"])

        return result

    def _delete_flower(self, result: BouquetResult, flower_id: str | None) -> BouquetResult:
        if not result.flowers:
            return result
        if flower_id:
            kept = [flower for flower in result.flowers if flower.flower_id != flower_id]
            result.flowers = kept or result.flowers[:-1]
        else:
            result.flowers = result.flowers[:-1]
        return result

    def _merge_tags(self, current: list[str], appended: list[str]) -> list[str]:
        merged = current[:]
        for value in appended:
            if value not in merged:
                merged.append(value)
        return merged
