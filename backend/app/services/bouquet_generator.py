from __future__ import annotations

from app.schemas.bouquet import BouquetResult, GenerateBouquetRequest, ReferenceUsage
from app.utils.text import new_id


class BouquetGenerator:
    MAX_REFERENCE_COUNT = 3

    def generate(
        self,
        request: GenerateBouquetRequest,
        bouquet_templates: list[dict[str, object]],
        reference_map: dict[str, dict[str, object]],
    ) -> list[BouquetResult]:
        selected_references = [
            reference_map[reference_id]
            for reference_id in request.selected_reference_ids
            if reference_id in reference_map
        ][: self.MAX_REFERENCE_COUNT]

        templates = bouquet_templates[:3]
        results: list[BouquetResult] = []
        for template in templates:
            best_reference = self._pick_best_reference(
                template=template,
                selected_references=selected_references,
                semantic_result=request.semantic_result,
            )
            image_url = self._pick_image_url(
                template_image_url=str(template["image_url"]),
                reference=best_reference,
                reference_strategy=request.reference_strategy,
            )
            summary = self._build_summary(
                base_summary=str(template["summary"]),
                reference_strategy=request.reference_strategy,
                selected_reference=best_reference,
                semantic_summary=request.semantic_result.semantic_summary,
            )
            results.append(
                BouquetResult(
                    result_id=new_id(str(template["template_id"])),
                    title=str(template["title"]),
                    image_url=image_url,
                    tags=list(template["tags"]),
                    summary=summary,
                    reference_used=[
                        ReferenceUsage(
                            reference_id=item["reference_id"],
                            strength=request.reference_strategy,
                            title=str(item.get("title", "")),
                            cover_url=str(item.get("cover_url", "")),
                            reason=item.get("reason"),
                            matched_tags=list(item.get("matched_tags", [])),
                            score=item.get("score"),
                        )
                        for item in selected_references
                    ],
                    flowers=list(template["flowers"]),
                )
            )
        return results

    def _build_summary(
        self,
        base_summary: str,
        reference_strategy: str,
        selected_reference: dict[str, object] | None,
        semantic_summary: str,
    ) -> str:
        if reference_strategy == "none" or not selected_reference:
            return f"{base_summary}，当前未使用外部参考，主要依据输入语义生成。"

        strategy_text = {
            "light": "轻参考了真实花内容",
            "strong": "强参考了真实花内容",
        }.get(reference_strategy, "参考了真实花内容")
        return f"{base_summary}，{strategy_text}中的配色、结构或气质方向，并保持了“{semantic_summary}”中的核心感觉。"

    def _pick_best_reference(
        self,
        template: dict[str, object],
        selected_references: list[dict[str, object]],
        semantic_result,
    ) -> dict[str, object] | None:
        if not selected_references:
            return None

        query_tags = set(semantic_result.scene_tags)
        query_tags.update(semantic_result.emotion_tags)
        query_tags.update(semantic_result.visual_tags)
        query_tags.update(semantic_result.relation_tags)
        query_tags.update(template.get("tags", []))

        def score_reference(reference: dict[str, object]) -> int:
            candidate_tags = set(reference.get("scene_tags", []))
            candidate_tags.update(reference.get("emotion_tags", []))
            candidate_tags.update(reference.get("visual_tags", []))
            candidate_tags.update(reference.get("fit_for", []))
            return len(query_tags & candidate_tags)

        return max(selected_references, key=score_reference)

    def _pick_image_url(
        self,
        template_image_url: str,
        reference: dict[str, object] | None,
        reference_strategy: str,
    ) -> str:
        if reference_strategy == "none" or not reference:
            return template_image_url
        return str(reference.get("cover_url", template_image_url))
