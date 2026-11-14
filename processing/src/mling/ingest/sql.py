from __future__ import annotations


def quote_identifier(name: str) -> str:
    if not name:
        raise ValueError("identifier must not be empty")
    return '"' + name.replace('"', '""') + '"'
