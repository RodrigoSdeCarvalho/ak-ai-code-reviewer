from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum


class Role(Enum):
    VIEWER = "viewer"
    EDITOR = "editor"
    ADMIN = "admin"


class KanbanError(Exception):
    pass


class NotFound(KanbanError, LookupError):
    pass


class Forbidden(KanbanError):
    pass


@dataclass
class Board:
    id: int
    name: str
    owner_id: int
    columns: list[str]
    members: dict[int, Role] = field(default_factory=dict)

    def role_of(self, user_id: int) -> Role | None:
        if user_id == self.owner_id:
            return Role.ADMIN
        return self.members.get(user_id)


@dataclass
class Card:
    id: int
    board_id: int
    column: str
    title: str
    description: str = ""
    position: int = 0
    labels: list[str] = field(default_factory=list)
    archived: bool = False
    created_at: datetime | None = None
    updated_at: datetime | None = None
