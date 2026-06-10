import json
import logging
import uuid
from contextvars import ContextVar

# Per-request trace ID, visible in all log lines emitted while handling that request.
# Set by RequestIdMiddleware from the incoming X-Request-ID header (or a fresh UUID).
_trace_id: ContextVar[str] = ContextVar("trace_id", default="-")


def get_trace_id() -> str:
    return _trace_id.get()


def set_trace_id(tid: str) -> None:
    _trace_id.set(tid or "-")


class _JsonFormatter(logging.Formatter):
    """Emit each log record as a single JSON line for CloudWatch Logs Insights."""

    def format(self, record: logging.LogRecord) -> str:
        data: dict = {
            "ts": self.formatTime(record, "%Y-%m-%dT%H:%M:%S"),
            "level": record.levelname,
            "logger": record.name,
            "trace_id": _trace_id.get(),
            "msg": record.getMessage(),
        }
        if record.exc_info:
            data["exc"] = self.formatException(record.exc_info)
        return json.dumps(data, ensure_ascii=False)


def setup_logging(level: int = logging.INFO) -> None:
    """Replace the root logger's handlers with a single JSON stream handler."""
    formatter = _JsonFormatter()
    handler = logging.StreamHandler()
    handler.setFormatter(formatter)
    root = logging.getLogger()
    root.handlers.clear()
    root.addHandler(handler)
    root.setLevel(level)


class RequestIdMiddleware:
    """Raw ASGI middleware: reads X-Request-ID from the request (or mints a UUID),
    binds it to _trace_id so every log line emitted during this request includes it,
    and echoes it in the X-Request-ID response header.
    """

    def __init__(self, app) -> None:
        self._app = app

    async def __call__(self, scope, receive, send) -> None:
        if scope["type"] != "http":
            await self._app(scope, receive, send)
            return

        headers = {k.lower(): v for k, v in scope.get("headers", [])}
        rid = (headers.get(b"x-request-id", b"") or b"").decode() or str(uuid.uuid4())
        token = _trace_id.set(rid)

        async def _send_with_header(message):
            if message["type"] == "http.response.start":
                # Append X-Request-ID to response headers.
                headers_list = list(message.get("headers", []))
                headers_list.append((b"x-request-id", rid.encode()))
                message = {**message, "headers": headers_list}
            await send(message)

        try:
            await self._app(scope, receive, _send_with_header)
        finally:
            _trace_id.reset(token)
