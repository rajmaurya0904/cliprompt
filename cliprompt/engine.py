"""Suggestion engine for cliprompt."""

def suggest(history, context):
    """
    Return sorted list of suggested command strings based on history and context.

    Args:
        history: list of command strings from shell history
        context: dict of contextual information (e.g., current directory, prefix)

    Returns:
        list of suggested command strings, sorted by relevance
    """
    # Count frequency of each command in history
    freq = {}
    for cmd in history:
        freq[cmd] = freq.get(cmd, 0) + 1

    # Determine relevance based on context
    prefix = context.get('prefix')
    if prefix is not None:
        # Filter to commands that start with the given prefix
        candidates = {cmd: count for cmd, count in freq.items() if cmd.startswith(prefix)}
    else:
        candidates = freq

    # Sort by frequency descending, then alphabetically ascending for tie-breaking
    sorted_items = sorted(candidates.items(), key=lambda x: (-x[1], x[0]))
    return [cmd for cmd, _ in sorted_items]