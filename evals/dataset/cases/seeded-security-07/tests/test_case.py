from datetime import datetime

import pytest
from kanban.models import KanbanError, Role
from kanban.service import BoardService
from kanban.store import BoardStore

T0 = datetime(2026, 5, 4, 9, 0)
T1 = datetime(2026, 5, 4, 11, 30)
ALICE, BOB, CAROL = 1, 2, 3
COLUMNS = ["To do", "Doing", "Done"]


def _two_boards() -> tuple[BoardService, int, int]:
    service = BoardService(BoardStore())
    roadmap = service.create_board(ALICE, "Roadmap", COLUMNS)
    personal = service.create_board(BOB, "Bob's errands", COLUMNS)
    return service, roadmap.id, personal.id


def _titles(service: BoardService, board_id: int, actor: int, column: str) -> list[str]:
    return [c.title for c in service.list_column(board_id, actor, column)]


def test_cards_move_between_columns_and_keep_their_order():
    service, roadmap, _ = _two_boards()
    a = service.add_card(roadmap, ALICE, "To do", "Pricing page", T0)
    b = service.add_card(roadmap, ALICE, "To do", "Onboarding email", T0)
    c = service.add_card(roadmap, ALICE, "To do", "Usage export", T0)
    service.move_card(b.id, ALICE, roadmap, "Doing", T1)
    assert _titles(service, roadmap, ALICE, "To do") == ["Pricing page", "Usage export"]
    assert [x.position for x in service.list_column(roadmap, ALICE, "To do")] == [0, 1]
    service.move_card(c.id, ALICE, roadmap, "Doing", T1, position=0)
    assert _titles(service, roadmap, ALICE, "Doing") == ["Usage export", "Onboarding email"]
    service.move_card(a.id, ALICE, roadmap, "Doing", T1, position=1)
    assert _titles(service, roadmap, ALICE, "Doing") == ["Usage export", "Pricing page", "Onboarding email"]
    assert a.updated_at == T1


def test_member_of_both_boards_can_move_a_card_across():
    service, roadmap, personal = _two_boards()
    service.share(personal, BOB, ALICE, Role.EDITOR)
    card = service.add_card(roadmap, ALICE, "Done", "Ship v2", T0)
    service.move_card(card.id, ALICE, personal, "To do", T1)
    assert _titles(service, personal, BOB, "To do") == ["Ship v2"]
    assert _titles(service, roadmap, ALICE, "Done") == []


def test_outsider_cannot_take_a_card_from_a_board_they_cannot_see():
    service, roadmap, personal = _two_boards()
    card = service.add_card(roadmap, ALICE, "To do", "Q3 hiring plan", T0, description="Two backend roles")
    with pytest.raises(KanbanError):
        service.move_card(card.id, BOB, personal, "To do", T1)
    assert _titles(service, roadmap, ALICE, "To do") == ["Q3 hiring plan"]
    assert _titles(service, personal, BOB, "To do") == []


def test_viewer_cannot_move_cards_off_a_shared_board():
    service, roadmap, personal = _two_boards()
    service.share(roadmap, ALICE, BOB, Role.VIEWER)
    card = service.add_card(roadmap, ALICE, "Doing", "Partner contract", T0)
    with pytest.raises(KanbanError):
        service.move_card(card.id, BOB, personal, "Done", T1)
    assert service.view_card(card.id, ALICE).board_id == roadmap


def test_archived_cards_leave_the_column():
    service, roadmap, _ = _two_boards()
    service.share(roadmap, ALICE, CAROL, Role.EDITOR)
    first = service.add_card(roadmap, ALICE, "To do", "Logo refresh", T0)
    service.add_card(roadmap, ALICE, "To do", "Blog post", T0)
    service.archive_card(first.id, CAROL, T1)
    assert _titles(service, roadmap, ALICE, "To do") == ["Blog post"]
    assert service.list_column(roadmap, ALICE, "To do")[0].position == 0
    with pytest.raises(KanbanError):
        service.move_card(first.id, CAROL, roadmap, "Doing", T1)
