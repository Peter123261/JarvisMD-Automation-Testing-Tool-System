def get_criterion_score(entry):
    """Unified way to extract score from old (number) and new (dict) formats."""
    if isinstance(entry, dict):
        return entry.get("score", 0)
    elif isinstance(entry, (int, float)):
        return entry
    else:
        return 0


def validate_criterion_score(score, max_score):
    """
    Ensure score is a valid float, clamped to [0, max_score].
    Protects against under/overscores and type errors.
    """
    try:
        value = float(score)
    except (TypeError, ValueError):
        return 0
    if max_score is None:
        max_score = 0
    try:
        max_score_val = float(max_score)
    except (TypeError, ValueError):
        max_score_val = 0
    if max_score_val < 0:
        max_score_val = 0
    return max(0.0, min(value, max_score_val))


