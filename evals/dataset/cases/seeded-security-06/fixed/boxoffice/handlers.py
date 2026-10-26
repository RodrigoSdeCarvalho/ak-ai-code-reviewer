from __future__ import annotations

from collections.abc import Callable

from boxoffice.auth import Forbidden, Unauthorized, can_refund, require_login, require_role
from boxoffice.models import Request, Response, Role, Ticket
from boxoffice.store import EventClosed, NotFound, SoldOut, TicketStore

Handler = Callable[[Request], Response]

MAX_PER_ORDER = 10
MAX_COMPS_PER_REQUEST = 50


def _ticket_body(ticket: Ticket) -> dict[str, object]:
    return {
        "id": ticket.id,
        "event_id": ticket.event_id,
        "holder_id": ticket.holder_id,
        "price_paid_cents": ticket.price_paid_cents,
        "status": ticket.status.value,
        "comp": ticket.is_comp,
    }


class BoxOfficeApi:
    def __init__(self, store: TicketStore) -> None:
        self._store = store
        self._routes: dict[str, Handler] = {
            "event.get": self.get_event,
            "tickets.buy": self.buy_tickets,
            "tickets.refund": self.refund_ticket,
            "event.cancel": self.cancel_event,
            "event.attendees": self.attendee_list,
            "tickets.comp": self.comp_tickets,
        }

    def handle(self, route: str, request: Request) -> Response:
        handler = self._routes.get(route)
        if handler is None:
            return Response(404, {"error": f"unknown route {route}"})
        try:
            return handler(request)
        except Unauthorized as exc:
            return Response(401, {"error": str(exc)})
        except Forbidden as exc:
            return Response(403, {"error": str(exc)})
        except NotFound as exc:
            return Response(404, {"error": f"not found: {exc}"})
        except (SoldOut, EventClosed) as exc:
            return Response(409, {"error": f"unavailable: {exc}"})
        except (KeyError, ValueError) as exc:
            return Response(400, {"error": f"bad request: {exc}"})

    def get_event(self, request: Request) -> Response:
        event = self._store.event(int(request.params["event_id"]))
        return Response(
            200,
            {
                "id": event.id,
                "name": event.name,
                "price_cents": event.price_cents,
                "remaining": self._store.remaining(event.id),
                "status": event.status.value,
            },
        )

    def buy_tickets(self, request: Request) -> Response:
        user = require_login(request.user)
        quantity = int(request.params.get("quantity", "1"))
        if quantity > MAX_PER_ORDER:
            raise ValueError(f"at most {MAX_PER_ORDER} tickets per order")
        tickets = self._store.sell(int(request.params["event_id"]), user.id, quantity)
        return Response(201, {"tickets": [_ticket_body(t) for t in tickets]})

    def refund_ticket(self, request: Request) -> Response:
        user = require_login(request.user)
        ticket = self._store.ticket(int(request.params["ticket_id"]))
        if not can_refund(user, ticket.holder_id):
            raise Forbidden("not your ticket")
        return Response(200, _ticket_body(self._store.refund(ticket.id)))

    def cancel_event(self, request: Request) -> Response:
        require_role(request.user, Role.ADMIN)
        refunded = self._store.cancel_event(int(request.params["event_id"]))
        return Response(200, {"refunded": refunded})

    def attendee_list(self, request: Request) -> Response:
        require_role(request.user, Role.STAFF, Role.ADMIN)
        event_id = int(request.params["event_id"])
        counts = self._store.attendees(event_id)
        rows = [{"holder_id": holder, "tickets": n} for holder, n in sorted(counts.items())]
        return Response(200, {"event_id": event_id, "attendees": rows, "total": sum(counts.values())})

    def comp_tickets(self, request: Request) -> Response:
        user = require_role(request.user, Role.STAFF, Role.ADMIN)
        quantity = int(request.params.get("quantity", "1"))
        if quantity > MAX_COMPS_PER_REQUEST:
            raise ValueError(f"at most {MAX_COMPS_PER_REQUEST} complimentary tickets per request")
        tickets = self._store.issue_comps(
            int(request.params["event_id"]),
            int(request.params["holder_id"]),
            quantity,
            issued_by=user.id,
            note=request.params.get("note", ""),
        )
        return Response(201, {"tickets": [_ticket_body(t) for t in tickets]})
