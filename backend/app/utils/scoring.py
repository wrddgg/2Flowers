def overlap_score(source: list[str], target: list[str], weight: int) -> int:
    source_set = set(source)
    target_set = set(target)
    return len(source_set & target_set) * weight
