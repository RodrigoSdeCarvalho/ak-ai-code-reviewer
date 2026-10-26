from __future__ import annotations

from dataclasses import dataclass, field

from loyalty.settings import Settings


@dataclass
class Request:
    method: str
    path: str
    headers: dict[str, str] = field(default_factory=dict)  # header names in lower case
    member_id: int | None = None  # set by the session middleware from the session cookie
    body: dict | None = None


@dataclass
class Response:
    status: int
    body: dict | None = None
    headers: dict[str, str] = field(default_factory=dict)


@dataclass(frozen=True)
class Reward:
    id: str
    name: str
    cost: int


class PointsLedger:
    def __init__(self, rewards: list[Reward]) -> None:
        self._rewards = {reward.id: reward for reward in rewards}
        self._balances: dict[int, int] = {}
        self.redemptions: list[tuple[int, str]] = []

    def credit(self, member_id: int, points: int) -> None:
        self._balances[member_id] = self._balances.get(member_id, 0) + points

    def balance(self, member_id: int) -> int:
        return self._balances.get(member_id, 0)

    def rewards(self) -> list[Reward]:
        return sorted(self._rewards.values(), key=lambda reward: (reward.cost, reward.id))

    def redeem(self, member_id: int, reward_id: str) -> int:
        reward = self._rewards.get(reward_id)
        if reward is None:
            raise KeyError(reward_id)
        balance = self.balance(member_id)
        if reward.cost > balance:
            raise ValueError("not enough points")
        self._balances[member_id] = balance - reward.cost
        self.redemptions.append((member_id, reward_id))
        return self._balances[member_id]


class LoyaltyApi:
    def __init__(self, settings: Settings, ledger: PointsLedger) -> None:
        self._settings = settings
        self._ledger = ledger

    def handle(self, request: Request) -> Response:
        origin = request.headers.get("origin")
        allowed = origin is not None and origin.rstrip("/").lower() in self._settings.allowed_origins
        if request.method == "OPTIONS":
            response = Response(204)
            if allowed:
                response.headers["Access-Control-Allow-Methods"] = "GET, POST"
                response.headers["Access-Control-Allow-Headers"] = "content-type"
                response.headers["Access-Control-Max-Age"] = str(self._settings.cors_max_age)
        else:
            response = self._route(request)
        response.headers["Vary"] = "Origin"
        if allowed:
            response.headers["Access-Control-Allow-Origin"] = origin
            response.headers["Access-Control-Allow-Credentials"] = "true"
        return response

    def _route(self, request: Request) -> Response:
        if request.method == "GET" and request.path == "/v1/rewards":
            rewards = [{"id": r.id, "name": r.name, "cost": r.cost} for r in self._ledger.rewards()]
            return Response(200, {"program": self._settings.program_name, "rewards": rewards})
        if request.path not in ("/v1/balance", "/v1/redeem"):
            return Response(404, {"error": "not found"})
        if request.member_id is None:
            return Response(401, {"error": "sign in to see your points"})
        if request.method == "GET" and request.path == "/v1/balance":
            return Response(200, {"member": request.member_id, "points": self._ledger.balance(request.member_id)})
        if request.method == "POST" and request.path == "/v1/redeem":
            return self._redeem(request.member_id, request.body or {})
        return Response(405, {"error": "method not allowed"})

    def _redeem(self, member_id: int, body: dict) -> Response:
        reward_id = body.get("reward")
        if not isinstance(reward_id, str):
            return Response(400, {"error": "reward is required"})
        try:
            points = self._ledger.redeem(member_id, reward_id)
        except KeyError:
            return Response(404, {"error": f"no reward {reward_id!r}"})
        except ValueError as exc:
            return Response(409, {"error": str(exc)})
        return Response(200, {"member": member_id, "points": points})
