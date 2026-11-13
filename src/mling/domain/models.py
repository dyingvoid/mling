from __future__ import annotations

from collections.abc import Iterator, Mapping
from dataclasses import dataclass, field
from types import MappingProxyType


@dataclass(frozen=True, slots=True)
class Page:
    number: int
    text: str
    label: str | None = None


@dataclass(frozen=True, slots=True)
class Book:
    title: str
    source: str
    format: str
    pages: tuple[Page, ...]
    metadata: Mapping[str, str] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "metadata", MappingProxyType(dict(self.metadata)))

    def __len__(self) -> int:
        return len(self.pages)

    def __iter__(self) -> Iterator[Page]:
        return iter(self.pages)

    def page(self, number: int) -> Page:
        for page in self.pages:
            if page.number == number:
                return page
        raise KeyError(number)

    def page_text(self, number: int) -> str:
        return self.page(number).text

    @property
    def full_text(self) -> str:
        return "\n\n".join(page.text for page in self.pages if page.text)
