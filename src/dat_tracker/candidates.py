"""Fuse boundary candidates from multiple proposal sources."""

from __future__ import annotations


def label_support(
    *,
    cut_sec: float,
    sources: dict[str, list[float]],
    tolerance_sec: float,
) -> set[str]:
    """Return source names that have a candidate near cut_sec."""
    hits: set[str] = set()
    for name, cuts in sources.items():
        if any(abs(cut_sec - c) <= tolerance_sec for c in cuts):
            hits.add(name)
    return hits


def fuse_candidate_cuts(
    sources: dict[str, list[float]],
    *,
    merge_tolerance_sec: float,
    require_sources: tuple[str, ...] | None = None,
) -> list[float]:
    """Merge nearby cuts across sources; optionally keep only multi-source hits.

    Endpoints (global min/max across all sources) are always retained.
    Merged cut time is the mean of clustered proposals.
    """
    if not sources:
        return []

    tagged: list[tuple[float, str]] = []
    for name, cuts in sources.items():
        for cut in cuts:
            tagged.append((float(cut), name))
    if not tagged:
        return []

    tagged.sort(key=lambda item: item[0])
    clusters: list[list[tuple[float, str]]] = [[tagged[0]]]
    for cut, name in tagged[1:]:
        if cut - clusters[-1][-1][0] <= merge_tolerance_sec:
            clusters[-1].append((cut, name))
        else:
            clusters.append([(cut, name)])

    all_times = [c for c, _ in tagged]
    start = min(all_times)
    end = max(all_times)

    fused: list[float] = []
    for cluster in clusters:
        mean = sum(c for c, _ in cluster) / len(cluster)
        names = {name for _, name in cluster}
        is_endpoint = abs(mean - start) <= merge_tolerance_sec or abs(
            mean - end
        ) <= merge_tolerance_sec
        if require_sources and not is_endpoint:
            if not set(require_sources).issubset(names):
                continue
        fused.append(mean)

    # Ensure exact-ish endpoints present.
    if not fused or abs(fused[0] - start) > merge_tolerance_sec:
        fused.insert(0, start)
    if abs(fused[-1] - end) > merge_tolerance_sec:
        fused.append(end)
    return fused
