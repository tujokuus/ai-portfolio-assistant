"""Small ATX-heading scanner; intentionally not a full Markdown parser."""

import re
from collections.abc import Iterator

_HEADING = re.compile(r"^ {0,3}(#{1,6})(?:[ \t]+(.*)|[ \t]*)$")
_FENCE = re.compile(r"^ {0,3}(`{3,}|~{3,})(.*)$")


def headings(text: str) -> Iterator[tuple[int, int, str]]:
    """Yield (character offset, level, title), ignoring fenced code blocks."""
    offset = 0
    fence_char = ""
    fence_length = 0
    for line in text.splitlines(keepends=True):
        value = line.rstrip("\r\n")
        fence = _FENCE.match(value)
        if fence_char:
            if (
                fence
                and fence[1][0] == fence_char
                and len(fence[1]) >= fence_length
                and not fence[2].strip()
            ):
                fence_char = ""
        elif fence:
            fence_char = fence[1][0]
            fence_length = len(fence[1])
        else:
            heading = _HEADING.match(value)
            if heading:
                title = re.sub(r"[ \t]+#+[ \t]*$", "", heading[2] or "").strip()
                yield offset, len(heading[1]), title
        offset += len(line)

