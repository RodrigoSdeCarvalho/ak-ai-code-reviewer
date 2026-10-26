from __future__ import annotations

from datetime import datetime

from kanban.models import Board, Card, NotFound


class BoardStore:
    def __init__(self) -> None:
        self._boards: dict[int, Board] = {}
        self._cards: dict[int, Card] = {}
        self._next_board_id = 1
        self._next_card_id = 1

    def add_board(self, name: str, owner_id: int, columns: list[str]) -> Board:
        board = Board(id=self._next_board_id, name=name, owner_id=owner_id, columns=list(columns))
        self._boards[board.id] = board
        self._next_board_id += 1
        return board

    def board(self, board_id: int) -> Board:
        board = self._boards.get(board_id)
        if board is None:
            raise NotFound(f"no board {board_id}")
        return board

    def add_card(self, board_id: int, column: str, title: str, description: str, now: datetime) -> Card:
        card = Card(
            id=self._next_card_id,
            board_id=board_id,
            column=column,
            title=title,
            description=description,
            created_at=now,
            updated_at=now,
        )
        self._cards[card.id] = card
        self._next_card_id += 1
        self.insert(card)
        return card

    def card(self, card_id: int) -> Card:
        card = self._cards.get(card_id)
        if card is None:
            raise NotFound(f"no card {card_id}")
        return card

    def cards_in_column(self, board_id: int, column: str) -> list[Card]:
        found = [
            c for c in self._cards.values() if c.board_id == board_id and c.column == column and not c.archived
        ]
        return sorted(found, key=lambda c: c.position)

    def cards_on_board(self, board_id: int) -> list[Card]:
        found = [c for c in self._cards.values() if c.board_id == board_id and not c.archived]
        return sorted(found, key=lambda c: (c.column, c.position))

    def detach(self, card: Card) -> None:
        """Close the gap a card leaves in its current column."""
        for other in self.cards_in_column(card.board_id, card.column):
            if other.id != card.id and other.position > card.position:
                other.position -= 1

    def insert(self, card: Card, position: int | None = None) -> None:
        """Place a card in its current column, shifting the cards below it down by one."""
        others = [c for c in self.cards_in_column(card.board_id, card.column) if c.id != card.id]
        if position is None or position > len(others):
            position = len(others)
        for other in others:
            if other.position >= position:
                other.position += 1
        card.position = position
