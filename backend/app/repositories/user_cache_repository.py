from __future__ import annotations

from copy import deepcopy
from functools import lru_cache

from app.schemas.user_cache import SavedBouquetRecord, UserProgressState


class UserCacheRepository:
    def __init__(self) -> None:
        self._progress_by_user: dict[str, UserProgressState] = {}
        self._records_by_user: dict[str, list[SavedBouquetRecord]] = {}

    def save_progress(self, user_id: str, state: UserProgressState) -> UserProgressState:
        self._progress_by_user[user_id] = deepcopy(state)
        return deepcopy(state)

    def get_progress(self, user_id: str) -> UserProgressState | None:
        state = self._progress_by_user.get(user_id)
        return deepcopy(state) if state else None

    def save_record(self, user_id: str, record: SavedBouquetRecord) -> SavedBouquetRecord:
        records = self._records_by_user.setdefault(user_id, [])
        records = [item for item in records if item.record_id != record.record_id and item.result_id != record.result_id]
        records.insert(0, deepcopy(record))
        self._records_by_user[user_id] = records[:50]
        return deepcopy(record)

    def list_records(self, user_id: str) -> list[SavedBouquetRecord]:
        return deepcopy(self._records_by_user.get(user_id, []))

    def clear_all(self) -> None:
        self._progress_by_user.clear()
        self._records_by_user.clear()


@lru_cache(maxsize=1)
def get_user_cache_repository() -> UserCacheRepository:
    return UserCacheRepository()
