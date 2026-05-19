from __future__ import annotations


BLOCKED_ENGINES_ZERO_RESULTS_MESSAGE = "SearxNG returned zero results; engines blocked/rate-limited"


class SearxNGBlockedEnginesError(RuntimeError):
    """SearxNG reported blocked/rate-limited engines and no usable results."""
