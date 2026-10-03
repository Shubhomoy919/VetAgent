"""Small-sample statistics: Wilson score intervals and the exact McNemar test."""

import math


def wilson(k: int, n: int, z: float = 1.959963984540054) -> tuple[float, float] | None:
    """95% Wilson score interval for k successes out of n. None when n == 0."""
    if n <= 0:
        return None
    if not 0 <= k <= n:
        raise ValueError(f"k={k} must be between 0 and n={n}")
    p = k / n
    denom = 1 + z * z / n
    centre = (p + z * z / (2 * n)) / denom
    half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / denom
    # The exact bounds at k = 0 and k = n are 0 and 1; avoid floating-point residue like 5e-17.
    lo = 0.0 if k == 0 else max(0.0, centre - half)
    hi = 1.0 if k == n else min(1.0, centre + half)
    return lo, hi


def mcnemar_exact(b: int, c: int) -> float | None:
    """Two-sided exact McNemar p-value from the discordant counts b and c.

    b = pairs where only the first condition succeeded, c = only the second.
    Under H0 the discordant pairs split 50/50, so p = 2 · P(X ≤ min(b, c)), X ~ Bin(b + c, ½), capped at 1.
    None when there are no discordant pairs (the test is undefined).
    """
    if b < 0 or c < 0:
        raise ValueError("counts must be non-negative")
    n = b + c
    if n == 0:
        return None
    k = min(b, c)
    tail = sum(math.comb(n, i) for i in range(k + 1)) / 2**n
    return min(1.0, 2 * tail)
