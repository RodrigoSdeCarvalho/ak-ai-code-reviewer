from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from datetime import date


@dataclass
class Member:
    id: int
    name: str
    email: str
    joined_on: date
    plot: str | None = None
    active: bool = True


def normalise_email(email: str) -> str:
    return email.strip().casefold()


class MemberDirectory:
    def __init__(self, members: Iterable[Member] = ()) -> None:
        self._by_id: dict[int, Member] = {}
        self._id_by_email: dict[str, int] = {}
        for member in members:
            self.add(member)

    def add(self, member: Member) -> None:
        key = normalise_email(member.email)
        if key in self._id_by_email:
            raise ValueError(f"a member with email {member.email!r} already exists")
        if member.id in self._by_id:
            raise ValueError(f"member id {member.id} is already taken")
        self._by_id[member.id] = member
        self._id_by_email[key] = member.id

    def get(self, member_id: int) -> Member | None:
        return self._by_id.get(member_id)

    def by_email(self, email: str) -> Member | None:
        member_id = self._id_by_email.get(normalise_email(email))
        return None if member_id is None else self._by_id[member_id]

    def plot_holders(self) -> list[Member]:
        return sorted((m for m in self._by_id.values() if m.active and m.plot), key=lambda m: m.plot or "")

    def waiting_list(self) -> list[Member]:
        return sorted(
            (m for m in self._by_id.values() if m.active and not m.plot),
            key=lambda m: (m.joined_on, m.id),
        )
