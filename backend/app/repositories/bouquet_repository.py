from __future__ import annotations

from copy import deepcopy
from functools import lru_cache

from app.schemas.bouquet import BouquetResult


class BouquetRepository:
    def __init__(self) -> None:
        self._results: dict[str, BouquetResult] = {}

    def save_many(self, results: list[BouquetResult]) -> list[BouquetResult]:
        for result in results:
            self._results[result.result_id] = deepcopy(result)
        return results

    def save_one(self, result: BouquetResult) -> BouquetResult:
        self._results[result.result_id] = deepcopy(result)
        return result

    def get_result(self, result_id: str) -> BouquetResult | None:
        result = self._results.get(result_id)
        return deepcopy(result) if result else None


@lru_cache(maxsize=1)
def get_bouquet_repository() -> BouquetRepository:
    return BouquetRepository()
