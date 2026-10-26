"""In-memory address book keyed by e-mail address."""

from __future__ import annotations

from dataclasses import dataclass, replace


@dataclass(frozen=True)
class Contact:
    email: str
    name: str
    phone: str | None = None


class AddressBook:
    def __init__(self) -> None:
        self._contacts: dict[str, Contact] = {}

    def __len__(self) -> int:
        return len(self._contacts)

    def get(self, email: str) -> Contact | None:
        return self._contacts.get(email.lower())

    def upsert(self, email: str, name: str, phone: str | None = None) -> bool:
        """Create or update the contact for `email`; return True if it was created.

        An update keeps the stored phone number when `phone` is None.
        """
        key = email.lower()
        existing = self._contacts.get(key)
        if existing is None:
            self._contacts[key] = Contact(key, name, phone)
            return True
        self._contacts[key] = replace(existing, name=name, phone=phone or existing.phone)
        return False

    def remove(self, email: str) -> bool:
        return self._contacts.pop(email.lower(), None) is not None

    def all(self) -> list[Contact]:
        return sorted(self._contacts.values(), key=lambda c: (c.name.lower(), c.email))
