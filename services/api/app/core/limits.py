"""Bounded ingress protection for a single-process demo deployment."""

from collections import OrderedDict
from time import monotonic

from starlette.responses import JSONResponse
from starlette.types import ASGIApp, Message, Receive, Scope, Send


class IngressLimits:
    def __init__(
        self, app: ASGIApp, max_bytes: int = 3 * 1024 * 1024, requests_per_minute: int = 120
    ) -> None:
        self.app = app
        self.max_bytes = max_bytes
        self.limit = requests_per_minute
        self.windows: OrderedDict[str, tuple[float, int]] = OrderedDict()

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
            while self.windows and next(iter(self.windows.values()))[0] + 60 <= now:
                self.windows.popitem(last=False)
            peer = str((scope.get("client") or ("unknown", 0))[0])
            # Do not trust client-controlled X-Forwarded-For or bearer values.
            start, count = self.windows.get(peer, (now, 0))
            if count >= self.limit or (peer not in self.windows and len(self.windows) >= 10000):
                await reject(429, "rate_limited", "Слишком много запросов. Повторите через минуту.")
                return
            self.windows[peer] = (start, count + 1)
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
