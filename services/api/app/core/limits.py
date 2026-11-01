"""Bounded ingress protection for a single-process demo deployment."""

from collections import OrderedDict
from time import monotonic

from starlette.responses import JSONResponse
from starlette.types import ASGIApp, Message, Receive, Scope, Send


class IngressLimits:
    AUTH_PATHS = frozenset(
        {"/api/v1/auth/register", "/api/v1/auth/sessions", "/api/v1/pilot/sessions"}
    )

    def __init__(
        self,
        app: ASGIApp,
        max_bytes: int = 3 * 1024 * 1024,
        requests_per_minute: int = 120,
        auth_requests_per_minute: int = 10,
    ) -> None:
        self.app = app
        self.max_bytes = max_bytes
        self.limit = requests_per_minute
        self.auth_limit = auth_requests_per_minute
        self.windows: OrderedDict[str, tuple[float, int]] = OrderedDict()
        self.auth_windows: OrderedDict[str, tuple[float, int]] = OrderedDict()

    @staticmethod
    def _limited(
        windows: OrderedDict[str, tuple[float, int]],
        peer: str,
        limit: int,
        now: float,
    ) -> bool:
        while windows and next(iter(windows.values()))[0] + 60 <= now:
            windows.popitem(last=False)
        start, count = windows.get(peer, (now, 0))
        if count >= limit or (peer not in windows and len(windows) >= 10_000):
            return True
        windows[peer] = (start, count + 1)
        return False

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        async def safe_send(message: Message) -> None:
            if message["type"] == "http.response.start":
                message["headers"] = [
                    *message.get("headers", []),
                    (b"cache-control", b"no-store"),
                    (b"x-content-type-options", b"nosniff"),
                    (b"referrer-policy", b"no-referrer"),
                ]
            await send(message)

        async def reject(status: int, code: str, message: str) -> None:
            response = JSONResponse(
                {"error": {"code": code, "message": message}},
                status_code=status,
                headers={"Retry-After": "60"} if status == 429 else None,
            )
            await response(scope, receive, safe_send)

        if scope["method"] in {"POST", "PUT", "PATCH", "DELETE"}:
            now = monotonic()
            peer = str((scope.get("client") or ("unknown", 0))[0])
            if scope.get("path") in self.AUTH_PATHS and self._limited(
                self.auth_windows, peer, self.auth_limit, now
            ):
                await reject(
                    429,
                    "auth_rate_limited",
                    "Слишком много попыток входа. Повторите через минуту.",
                )
                return
            if self._limited(self.windows, peer, self.limit, now):
                await reject(429, "rate_limited", "Слишком много запросов. Повторите через минуту.")
                return
            body = bytearray()
            while True:
                message = await receive()
                if message["type"] == "http.disconnect":
                    return
                body.extend(message.get("body", b""))
                if len(body) > self.max_bytes:
                    await reject(413, "request_too_large", "Запрос слишком большой.")
                    return
                if not message.get("more_body", False):
                    break

            async def replay() -> Message:
                return {"type": "http.request", "body": bytes(body), "more_body": False}

            await self.app(scope, replay, safe_send)
        else:
            await self.app(scope, receive, safe_send)
