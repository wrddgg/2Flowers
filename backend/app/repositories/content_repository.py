from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any
from urllib.parse import urlparse


DATA_FILE = Path(__file__).resolve().parent.parent / "data" / "content_knowledge_base.json"
ANNOTATED_ASSET_FILE = Path(__file__).resolve().parent.parent / "data" / "annotated_asset_library.json"


class ContentRepository:
    def __init__(self, data_file: Path | None = None) -> None:
        self.data_file = data_file or DATA_FILE
        self._dataset = self._load()
        self._annotated_assets = self._load_json(ANNOTATED_ASSET_FILE)

    def _load(self) -> dict[str, Any]:
        return self._load_json(self.data_file)

    def _load_json(self, path: Path) -> dict[str, Any]:
        with path.open("r", encoding="utf-8") as file:
            return json.load(file)

    @property
    def dataset(self) -> dict[str, Any]:
        return self._dataset

    @property
    def annotated_assets(self) -> dict[str, Any]:
        return self._annotated_assets

    def get_content_profile(self, content_id: str) -> dict[str, Any] | None:
        return self._dataset.get("content_profiles", {}).get(content_id)

    def get_content_or_asset_profile(self, content_id: str, image_url: str | None = None) -> dict[str, Any] | None:
        content_profile = self.get_content_profile(content_id)
        if content_profile:
            return content_profile

        asset_group = self.get_asset_group_by_id(content_id)
        if asset_group:
            return self._build_profile_from_asset_group(asset_group)

        if image_url:
            asset_group = self.find_asset_group_by_image(image_url)
            if asset_group:
                return self._build_profile_from_asset_group(asset_group)

        return None

    def list_references(self, mode: str | None = None) -> list[dict[str, Any]]:
        references = self._dataset.get("references", [])
        if mode is None:
            return references
        return [item for item in references if item["mode"] == mode]

    def get_reference_map(self) -> dict[str, dict[str, Any]]:
        merged_map = {item["reference_id"]: item for item in self._dataset.get("references", [])}
        for item in self._build_asset_reference_candidates():
            merged_map[item["reference_id"]] = item
        return merged_map

    def list_bouquet_templates(self, mode: str) -> list[dict[str, Any]]:
        return self._dataset.get("bouquet_templates", {}).get(mode, [])

    def list_asset_groups(self, mode: str | None = None) -> list[dict[str, Any]]:
        groups: list[dict[str, Any]] = []
        groups.extend(self._annotated_assets.get("scene_groups", []))
        groups.extend(self._annotated_assets.get("flower_groups", []))
        groups.extend(self._annotated_assets.get("life_groups", []))
        if mode is None:
            return groups
        return [item for item in groups if item.get("mode") == mode]

    def get_asset_group_by_id(self, group_id: str) -> dict[str, Any] | None:
        for item in self.list_asset_groups():
            if item.get("group_id") == group_id:
                return item
        return None

    def find_asset_group_by_image(self, image_url: str) -> dict[str, Any] | None:
        image_name = self._extract_image_name(image_url)
        if not image_name:
            return None
        for item in self.list_asset_groups():
            if image_name in item.get("images", []):
                return item
        return None

    def list_reference_candidates(self, mode: str) -> list[dict[str, Any]]:
        asset_candidates = self._build_asset_reference_candidates()
        if asset_candidates:
            return asset_candidates
        return self.list_references(mode)

    def _build_asset_reference_candidates(self) -> list[dict[str, Any]]:
        candidates: list[dict[str, Any]] = []
        for group in self._annotated_assets.get("flower_groups", []):
            images = group.get("images", [])
            if not images:
                continue

            flower_types: list[str] = []
            flower_types.extend(group.get("main_flowers", []))
            flower_types.extend(group.get("secondary_flowers", []))

            reference_options = ["color", "structure", "flower_types"]
            if group.get("package_style"):
                reference_options.append("wrapping")

            candidates.append(
                {
                    "reference_id": group["group_id"],
                    "title": group["title"],
                    "source_type": "image",
                    "cover_url": f"/library/assets/{images[0]}",
                    "mode": "flower",
                    "flower_types": flower_types,
                    "visual_tags": group.get("visual_tags", []),
                    "emotion_tags": group.get("emotion_tags", []),
                    "scene_tags": group.get("scene_tags", []),
                    "reference_options": reference_options,
                    "fit_for": group.get("fit_for", []),
                    "package_style": group.get("package_style", []),
                    "asset_source": True,
                }
            )
        return candidates

    def _build_profile_from_asset_group(self, group: dict[str, Any]) -> dict[str, Any]:
        relation_tags: list[str] = []
        if group.get("target_relation"):
            relation_tags.append(str(group["target_relation"]))
        relation_tags.extend(group.get("fit_for", []))

        subject_tags = [str(group.get("title", ""))]
        if group.get("recommended_bouquet_title"):
            subject_tags.append(str(group["recommended_bouquet_title"]))

        return {
            "base_mode": group.get("mode", "scene"),
            "subject_tags": [item for item in subject_tags if item],
            "scene_tags": list(group.get("scene_tags", [])),
            "emotion_tags": list(group.get("emotion_tags", [])),
            "visual_tags": list(group.get("visual_tags", [])),
            "color_palette": list(group.get("color_palette", [])),
            "relation_tags": relation_tags,
            "group_id": group.get("group_id"),
            "images": list(group.get("images", [])),
            "source_type": "annotated_asset",
        }

    def _extract_image_name(self, image_url: str) -> str | None:
        parsed = urlparse(image_url)
        candidate = parsed.path or image_url
        name = Path(candidate).name
        return name or None


@lru_cache(maxsize=1)
def get_content_repository() -> ContentRepository:
    return ContentRepository()
