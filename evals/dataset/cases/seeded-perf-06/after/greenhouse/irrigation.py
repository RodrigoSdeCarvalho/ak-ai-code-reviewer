from __future__ import annotations

import math
from collections.abc import Mapping
from dataclasses import dataclass

from greenhouse.readings import ZoneSummary


@dataclass(frozen=True)
class IrrigationPolicy:
    default_target: float = 35.0
    minutes_per_point: float = 1.5
    max_minutes: int = 30
    max_rejected_share: float = 0.5


@dataclass(frozen=True)
class ZoneAction:
    zone: str
    action: str
    minutes: int = 0
    reason: str = ""


def plan(
    summaries: Mapping[str, ZoneSummary],
    targets: Mapping[str, float],
    policy: IrrigationPolicy | None = None,
) -> list[ZoneAction]:
    policy = policy or IrrigationPolicy()
    actions: list[ZoneAction] = []
    for zone, summary in sorted(summaries.items()):
        if summary.mean is None or summary.rejected_share > policy.max_rejected_share:
            actions.append(ZoneAction(zone, "inspect", reason=f"{summary.rejected} readings out of range"))
            continue
        target = targets.get(zone, policy.default_target)
        deficit = target - summary.mean
        if deficit <= 0:
            actions.append(ZoneAction(zone, "skip", reason=f"moisture {summary.mean} >= target {target}"))
            continue
        minutes = min(policy.max_minutes, math.ceil(deficit * policy.minutes_per_point))
        actions.append(ZoneAction(zone, "water", minutes, reason=f"moisture {summary.mean} < target {target}"))
    return actions


def format_plan(actions: list[ZoneAction]) -> str:
    if not actions:
        return "no zones reported"
    width = max(len(action.zone) for action in actions)
    lines = []
    for action in actions:
        detail = f"{action.minutes} min" if action.action == "water" else action.action
        lines.append(f"{action.zone.ljust(width)}  {detail:<8}  {action.reason}")
    return "\n".join(lines)
