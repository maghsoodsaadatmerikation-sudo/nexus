"""Fail-closed template substitution shared by Studio build stages.

Unlike ``assert`` or unchecked str.replace(), this check remains active
under optimized Python and catches missing or duplicated template anchors.
"""


def replace_exact(source: str, needle: str, replacement: str, *, expected: int = 1) -> str:
    """Replace only when the template contains exactly the expected anchors."""
    if not needle or expected < 1:
        raise ValueError("Invalid template substitution contract")
    count = source.count(needle)
    if count != expected:
        raise ValueError(
            f"Studio template anchor {needle!r}: expected {expected}, found {count}"
        )
    return source.replace(needle, replacement)
