from __future__ import annotations

from datetime import datetime

from kanban.models import Board, Card, Forbidden, KanbanError, NotFound, Role
from kanban.store import BoardStore

MAX_TITLE_LENGTH = 200
MAX_LABELS = 10


class BoardService:
    def __init__(self, store: BoardStore) -> None:
        self._store = store

    def _require_role(self, board_id: int, user_id: int, *allowed: Role) -> Board:
        board = self._store.board(board_id)
        role = board.role_of(user_id)
        if role is None:
            # Boards are private: non-members get the same answer as for a missing board.
            raise NotFound(f"no board {board_id}")
        if role not in allowed:
            raise Forbidden(f"{role.value} cannot do this on board {board_id}")
        return board

    def _require_viewer(self, board_id: int, user_id: int) -> Board:
        return self._require_role(board_id, user_id, Role.VIEWER, Role.EDITOR, Role.ADMIN)

    def _require_editor(self, board_id: int, user_id: int) -> Board:
        return self._require_role(board_id, user_id, Role.EDITOR, Role.ADMIN)

    def create_board(self, owner_id: int, name: str, columns: list[str]) -> Board:
        if not columns or len(set(columns)) != len(columns):
            raise KanbanError("a board needs at least one column and column names must be unique")
        return self._store.add_board(name.strip(), owner_id, columns)

    def share(self, board_id: int, actor_id: int, user_id: int, role: Role) -> Board:
        board = self._require_role(board_id, actor_id, Role.ADMIN)
        if user_id == board.owner_id:
            raise KanbanError("the owner already has full access")
        board.members[user_id] = role
        return board

    def add_card(
        self, board_id: int, actor_id: int, column: str, title: str, now: datetime, description: str = ""
    ) -> Card:
        board = self._require_editor(board_id, actor_id)
        if column not in board.columns:
            raise KanbanError(f"board {board_id} has no column {column!r}")
        title = title.strip()
        if not title or len(title) > MAX_TITLE_LENGTH:
            raise KanbanError(f"card titles must be 1 to {MAX_TITLE_LENGTH} characters")
        return self._store.add_card(board_id, column, title, description, now)

    def view_card(self, card_id: int, actor_id: int) -> Card:
        card = self._store.card(card_id)
        self._require_viewer(card.board_id, actor_id)
        return card

    def list_column(self, board_id: int, actor_id: int, column: str) -> list[Card]:
        board = self._require_viewer(board_id, actor_id)
        if column not in board.columns:
            raise KanbanError(f"board {board_id} has no column {column!r}")
        return self._store.cards_in_column(board_id, column)

    def edit_card(
        self,
        card_id: int,
        actor_id: int,
        now: datetime,
        title: str | None = None,
        description: str | None = None,
        labels: list[str] | None = None,
    ) -> Card:
        card = self._store.card(card_id)
        self._require_editor(card.board_id, actor_id)
        if title is not None:
            title = title.strip()
            if not title or len(title) > MAX_TITLE_LENGTH:
                raise KanbanError(f"card titles must be 1 to {MAX_TITLE_LENGTH} characters")
        if labels is not None and len(labels) > MAX_LABELS:
            raise KanbanError(f"a card can have at most {MAX_LABELS} labels")
        if title is not None:
            card.title = title
        if description is not None:
            card.description = description
        if labels is not None:
            card.labels = sorted(set(labels))
        card.updated_at = now
        return card
