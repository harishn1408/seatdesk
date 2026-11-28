"""Algorithms toolkit and cosine similarity using only the Python standard library."""
import math


def merge_sorted(a, b, key=lambda x: x):
    """Merge two sorted lists in O(n + m) time; ties pick from `a` first."""
    merged = []
    i = 0
    j = 0
    len_a = len(a)
    len_b = len(b)
    while i < len_a and j < len_b:
        if key(a[i]) <= key(b[j]):
            merged.append(a[i])
            i += 1
        else:
            merged.append(b[j])
            j += 1
    if i < len_a:
        merged.extend(a[i:])
    if j < len_b:
        merged.extend(b[j:])
    return merged


def second_highest_fare(fares):
    """Return the second-largest distinct value in `fares` in one O(n) pass, or None."""
    first = None
    second = None
    for fare in fares:
        if first is None or fare > first:
            if first is not None and fare != first:
                second = first
            first = fare
        elif fare != first and (second is None or fare > second):
            second = fare
    return second


def duplicate_bookings(bookings):
    """Return sorted (passenger_id, trip_id) pairs that occur more than once."""
    counts: dict[tuple[int, int], int] = {}
    for booking in bookings:
        pair = (booking["passenger_id"], booking["trip_id"])
        counts[pair] = counts.get(pair, 0) + 1
    return sorted(pair for pair, count in counts.items() if count > 1)


def pairs_for_budget_nested(fares, budget):
    """Return all (i, j) pairs with i < j summing to `budget` and comparison count."""
    pairs = []
    comparisons = 0
    n = len(fares)
    for i in range(n):
        for j in range(i + 1, n):
            comparisons += 1
            if fares[i] + fares[j] == budget:
                pairs.append((i, j))
    return pairs, comparisons


def pairs_for_budget_hashed(fares, budget):
    """Return all (i, j) pairs with i < j summing to `budget` and dict lookup count."""
    seen: dict[int, list[int]] = {}
    pairs = []
    lookups = 0
    for j, fare in enumerate(fares):
        lookups += 1
        need = budget - fare
        if need in seen:
            for i in seen[need]:
                pairs.append((i, j))
        seen.setdefault(fare, []).append(j)
    pairs.sort()
    return pairs, lookups


def cosine_similarity(a, b):
    """Return hand-written cosine similarity between vectors `a` and `b`."""
    if len(a) != len(b):
        raise ValueError("Vectors must have the same length")
    dot = sum(x * y for x, y in zip(a, b))
    mag_a = math.sqrt(sum(x * x for x in a))
    mag_b = math.sqrt(sum(y * y for y in b))
    if mag_a == 0.0 or mag_b == 0.0:
        return 0.0
    return dot / (mag_a * mag_b)
