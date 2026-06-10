"""RFC 6901 JSON Pointer resolution shared across Sentinel evaluation layers."""

from __future__ import annotations


def _decode_pointer_token(token: str) -> str:
    decoded: list[str] = []
    idx = 0
    while idx < len(token):
        char = token[idx]
        if char != "~":
            decoded.append(char)
            idx += 1
            continue
        if idx + 1 >= len(token):
            raise ValueError("malformed pointer escape")
        next_char = token[idx + 1]
        if next_char == "0":
            decoded.append("~")
        elif next_char == "1":
            decoded.append("/")
        else:
            raise ValueError("malformed pointer escape")
        idx += 2
    return "".join(decoded)


def resolve_json_pointer(document: object, path: str) -> tuple[bool, object | None]:
    """Resolve a JSON Pointer (RFC 6901) against *document*.

    Returns ``(True, value)`` when the pointer resolves to a value, or
    ``(False, None)`` when the path does not exist in the document.
    Raises ``ValueError`` for structurally malformed pointers.

    Root-document shorthands: both ``""`` (empty string, per RFC 6901) and
    ``"/"`` are accepted as referring to the whole document.
    """
    if path == "" or path == "/":
        return True, document
    if not path.startswith("/"):
        raise ValueError("malformed pointer path")

    tokens = path[1:].split("/")
    current: object = document

    for raw_token in tokens:
        token = _decode_pointer_token(raw_token)
        if isinstance(current, dict):
            if token not in current:
                return False, None
            current = current[token]
            continue
        if isinstance(current, list):
            if token == "-":
                raise ValueError("malformed array index token")
            try:
                index = int(token)
            except ValueError as exc:
                raise ValueError("malformed array index token") from exc
            if str(index) != token:
                raise ValueError("malformed array index token")
            if index < 0 or index >= len(current):
                return False, None
            current = current[index]
            continue
        return False, None

    return True, current
