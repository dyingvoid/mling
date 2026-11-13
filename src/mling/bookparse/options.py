from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class Options:
    dehyphenate: bool = False
    keep_blank_pages: bool = True
