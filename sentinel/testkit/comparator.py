"""Regression exact JSON comparator."""

from __future__ import annotations

from sentinel.testkit.types import DiffEntry

_OMITTED = object()


def _valid_json_pointer(p: str) -> bool:
    return p == "" or p.startswith("/")


def _should_omit(path: str, ignore_paths: tuple[str, ...]) -> bool:
    for p in ignore_paths:
        if not _valid_json_pointer(p):
            continue
        if p == "":
            return True
        if path == p:
            return True
        if path.startswith(p + "/"):
            return True
    return False


def _prune_ignored(value: object, path: str, ignore_paths: tuple[str, ...]) -> object:
    if not ignore_paths:
        return value
    if _should_omit(path, ignore_paths):
        return _OMITTED
    if isinstance(value, dict):
        out: dict[str, object] = {}
        for key in sorted(value.keys()):
            key_path = _join_path(path, str(key))
            child = _prune_ignored(value[key], key_path, ignore_paths)
            if child is _OMITTED:
                continue
            out[key] = child
        return out
    if isinstance(value, list):
        out_list: list[object] = []
        for idx in range(len(value)):
            idx_path = _join_path(path, str(idx))
            child = _prune_ignored(value[idx], idx_path, ignore_paths)
            if child is _OMITTED:
                continue
            out_list.append(child)
        return out_list
    return value


def _escape_token(token: str) -> str:
    return token.replace("~", "~0").replace("/", "~1")


def _join_path(base: str, token: str) -> str:
    escaped = _escape_token(token)
    if base == "":
        return f"/{escaped}"
    return f"{base}/{escaped}"


def compare_json(expected: object, actual: object, ignore_paths: tuple[str, ...] = ()) -> list[DiffEntry]:
    """Compare two JSON-compatible values and return structured diffs."""
    if ignore_paths:
        pe = _prune_ignored(expected, "", ignore_paths)
        pa = _prune_ignored(actual, "", ignore_paths)
        exp_in: object = None if pe is _OMITTED else pe
        act_in: object = None if pa is _OMITTED else pa
    else:
        exp_in, act_in = expected, actual

    diffs: list[DiffEntry] = []

    def walk(exp: object, act: object, path: str) -> None:
        if isinstance(exp, dict) and isinstance(act, dict):
            exp_keys = set(exp.keys())
            act_keys = set(act.keys())

            for key in sorted(exp_keys - act_keys):
                key_path = _join_path(path, str(key))
                diffs.append(
                    DiffEntry(record_type="missing", path=key_path, expected=exp[key], actual=None)
                )

            for key in sorted(act_keys - exp_keys):
                key_path = _join_path(path, str(key))
                diffs.append(
                    DiffEntry(record_type="extra", path=key_path, expected=None, actual=act[key])
                )

            for key in sorted(exp_keys & act_keys):
                key_path = _join_path(path, str(key))
                walk(exp[key], act[key], key_path)
            return

        if isinstance(exp, list) and isinstance(act, list):
            min_len = min(len(exp), len(act))
            for idx in range(min_len):
                idx_path = _join_path(path, str(idx))
                walk(exp[idx], act[idx], idx_path)

            for idx in range(min_len, len(exp)):
                idx_path = _join_path(path, str(idx))
                diffs.append(
                    DiffEntry(record_type="missing", path=idx_path, expected=exp[idx], actual=None)
                )

            for idx in range(min_len, len(act)):
                idx_path = _join_path(path, str(idx))
                diffs.append(
                    DiffEntry(record_type="extra", path=idx_path, expected=None, actual=act[idx])
                )
            return

        if exp != act or type(exp) is not type(act):
            diffs.append(
                DiffEntry(record_type="mismatch", path=path, expected=exp, actual=act)
            )

    walk(exp_in, act_in, "")
    return diffs

