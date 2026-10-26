from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import Enum


class Role(Enum):
    OWNER = "owner"
    ADMIN = "admin"
    MEMBER = "member"
    GUEST = "guest"


MANAGER_ROLES = frozenset({Role.OWNER, Role.ADMIN})


class Forbidden(PermissionError):
    pass


class NotAMember(LookupError):
    pass


class AlreadyAMember(ValueError):
    pass


@dataclass
class Member:
    workspace_id: int
    user_id: int
    email: str
    role: Role
    joined_at: datetime
    invite_code: str | None = None


class Directory:
    def __init__(self) -> None:
        self._members: dict[tuple[int, int], Member] = {}

    def add(
        self,
        workspace_id: int,
        user_id: int,
        email: str,
        role: Role,
        joined_at: datetime,
        invite_code: str | None = None,
    ) -> Member:
        key = (workspace_id, user_id)
        if key in self._members:
            raise AlreadyAMember(f"user {user_id} is already in workspace {workspace_id}")
        member = Member(workspace_id, user_id, email.strip().lower(), role, joined_at, invite_code)
        self._members[key] = member
        return member

    def get(self, workspace_id: int, user_id: int) -> Member:
        try:
            return self._members[(workspace_id, user_id)]
        except KeyError:
            raise NotAMember(f"user {user_id} is not in workspace {workspace_id}") from None

    def is_member(self, workspace_id: int, user_id: int) -> bool:
        return (workspace_id, user_id) in self._members

    def members(self, workspace_id: int) -> list[Member]:
        found = [m for (ws, _), m in self._members.items() if ws == workspace_id]
        return sorted(found, key=lambda m: (m.joined_at, m.user_id))

    def require_manager(self, workspace_id: int, user_id: int) -> Member:
        member = self.get(workspace_id, user_id)
        if member.role not in MANAGER_ROLES:
            raise Forbidden("workspace admin role required")
        return member

    def change_role(self, workspace_id: int, actor_id: int, user_id: int, role: Role) -> Member:
        actor = self.require_manager(workspace_id, actor_id)
        target = self.get(workspace_id, user_id)
        if Role.OWNER in (role, target.role) and actor.role is not Role.OWNER:
            raise Forbidden("only the owner can grant or change ownership")
        target.role = role
        return target

    def remove(self, workspace_id: int, actor_id: int, user_id: int) -> None:
        if actor_id != user_id:
            self.require_manager(workspace_id, actor_id)
        target = self.get(workspace_id, user_id)
        if target.role is Role.OWNER:
            raise Forbidden("the owner cannot be removed")
        del self._members[(workspace_id, user_id)]
