from __future__ import annotations

from boxoffice.models import Role, User


class Unauthorized(Exception):
    """No user is signed in."""


class Forbidden(PermissionError):
    """The signed-in user may not perform this action."""


def require_login(user: User | None) -> User:
    if user is None:
        raise Unauthorized("sign in required")
    return user


def require_role(user: User | None, *roles: Role) -> User:
    signed_in = require_login(user)
    if signed_in.role not in roles:
        allowed = ", ".join(role.value for role in roles)
        raise Forbidden(f"requires one of: {allowed}")
    return signed_in


def is_staff(user: User) -> bool:
    return user.role in (Role.STAFF, Role.ADMIN)


def can_refund(user: User, holder_id: int) -> bool:
    return user.id == holder_id or is_staff(user)
