"""Visitor-country enrichment."""

from __future__ import annotations

from dataclasses import replace
from ipaddress import ip_address, ip_network
from typing import Protocol

from pipeline.records import Event

UNKNOWN_COUNTRY = "??"


class LookupTimeout(Exception):
    """A geo lookup did not answer in time; the lookup may be retried."""


class GeoClient(Protocol):
    async def country_for(self, ip: str) -> str: ...


class GeoTable:
    """Country lookup from a static table of CIDR ranges."""

    def __init__(self, ranges: dict[str, str]) -> None:
        self._networks = [(ip_network(cidr), country) for cidr, country in ranges.items()]

    async def country_for(self, ip: str) -> str:
        try:
            address = ip_address(ip)
        except ValueError:
            return UNKNOWN_COUNTRY
        for network, country in self._networks:
            if address in network:
                return country
        return UNKNOWN_COUNTRY


async def enrich(event: Event, geo: GeoClient) -> Event:
    return replace(event, country=await geo.country_for(event.ip))
