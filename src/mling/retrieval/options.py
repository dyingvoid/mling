from __future__ import annotations

from dataclasses import dataclass

DEFAULT_LIMIT = 5


@dataclass(frozen=True, slots=True)
class RetrievalOptions:
    book_name: str
    query: str
    limit: int = DEFAULT_LIMIT
    from_page: int | None = None
    to_page: int | None = None

    def validate(self) -> None:
        if not self.book_name.strip():
            raise ValueError("book name must not be empty")
        if not self.query.strip():
            raise ValueError("query must not be empty")
        if self.limit < 1:
            raise ValueError("limit must be greater than zero")
        for name, page in (("from_page", self.from_page), ("to_page", self.to_page)):
            if page is not None and page < 1:
                raise ValueError(f"{name} must be greater than zero")
        if (
            self.from_page is not None
            and self.to_page is not None
            and self.from_page > self.to_page
        ):
            raise ValueError("from_page must not be greater than to_page")
