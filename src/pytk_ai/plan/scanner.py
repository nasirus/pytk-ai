from __future__ import annotations


def scan_compound(command: str) -> tuple[list[tuple[str, str | None]], str | None]:
    segments: list[tuple[str, str | None]] = []
    start = 0
    quote: str | None = None
    escape = False
    index = 0
    while index < len(command):
        char = command[index]
        if escape:
            escape = False
            index += 1
            continue
        if char == "\\" and quote != "'":
            escape = True
            index += 1
            continue
        if quote is not None:
            if char == quote:
                quote = None
            index += 1
            continue
        if char in ('"', "'"):
            quote = char
            index += 1
            continue

        if command.startswith("&&", index):
            segments.append((command[start:index].strip(), "&&"))
            index += 2
            start = index
            continue
        if command.startswith("||", index):
            segments.append((command[start:index].strip(), "||"))
            index += 2
            start = index
            continue
        if char == ";":
            segments.append((command[start:index].strip(), ";"))
            index += 1
            start = index
            continue
        if char == "|":
            segments.append((command[start:index].strip(), "|"))
            return segments, command[index + 1 :].lstrip()
        if (
            char == "&"
            and not command.startswith("&>", index)
            and (index == 0 or command[index - 1] != ">")
        ):
            if not command.startswith("&&", index):
                segments.append((command[start:index].strip(), "&"))
                index += 1
                start = index
                continue
        index += 1

    segments.append((command[start:].strip(), None))
    return segments, None
